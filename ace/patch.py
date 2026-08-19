"""Conservative, deterministic on-demand-reference proposal generation."""
import difflib
import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath

from .legacy import est_tokens
from .schema import canonical, document_id, validate_audit

_HEADING = re.compile(r"^##(?!#)[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def safe_relative(path):
    """Validate a report path before joining it to a workspace."""
    if not isinstance(path, str) or not path or "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise ValueError("unsafe workspace-relative path")
    p = PurePosixPath(path)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts) or p.as_posix() != path:
        raise ValueError("unsafe workspace-relative path")
    return p


def _regular_at(root, path):
    p = root.joinpath(*safe_relative(path).parts)
    current = root
    for part in safe_relative(path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("workspace path contains a symlink")
    try:
        st = p.lstat()
    except OSError:
        raise ValueError("manifest input is missing")
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("manifest input is not a regular file")
    return p, st


def recheck_manifest(root, audit):
    """Fail closed if any audited input has drifted since the audit."""
    manifest = audit.get("manifest")
    if not isinstance(manifest, list):
        raise ValueError("invalid audit manifest")
    expected = "sha256:" + hashlib.sha256(canonical(manifest)).hexdigest()
    if audit.get("manifest_digest") != expected:
        raise ValueError("invalid audit manifest digest")
    seen = set()
    for item in manifest:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "mode", "role"}:
            raise ValueError("invalid audit manifest entry")
        path = item["path"]
        if path in seen:
            raise ValueError("duplicate audit manifest path")
        seen.add(path)
        p, st = _regular_at(root, path)
        if _sha(p.read_bytes()) != item["sha256"] or format(stat.S_IMODE(st.st_mode), "04o") != item["mode"]:
            raise ValueError("audit input is stale")


def _sections(text):
    """Return level-two section offsets and titles, excluding fenced code."""
    result = []
    fenced = None
    offset = 0
    for line in text.splitlines(True):
        match_fence = _FENCE.match(line)
        if match_fence:
            marker = match_fence.group(1)
            if fenced is None:
                fenced = (marker[0], len(marker))
            elif marker[0] == fenced[0] and len(marker) >= fenced[1]:
                fenced = None
        elif fenced is None:
            match = _HEADING.match(line.rstrip("\r\n"))
            if match:
                result.append((offset, match.group(1).strip()))
        offset += len(line)
    return result


def _slug(path):
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", path)).strip("-").lower() or "instruction"


def _diff(old, new, path, new_file=False):
    before = [] if new_file else old.decode("utf-8").splitlines(True)
    after = new.decode("utf-8").splitlines(True)
    return list(difflib.unified_diff(before, after, "/dev/null" if new_file else "a/" + path,
                                     "b/" + path, n=3, lineterm="\n"))


def _hunks(lines):
    return sum(1 for line in lines if line.startswith("@@ "))


def _candidate_id(document):
    body = dict(document)
    body.pop("id", None)
    body.pop("candidate_id", None)
    return "sha256:" + hashlib.sha256(canonical(body)).hexdigest()


def propose(root, audit, selected=None):
    """Build one candidate containing every eligible selected finding."""
    validate_audit(audit)
    recheck_manifest(root, audit)
    sources = {source["id"]: source for source in audit["sources"] if isinstance(source, dict)}
    available = {finding["id"]: finding for finding in audit["findings"] if isinstance(finding, dict)}
    if selected:
        unknown = sorted(set(selected) - set(available))
        if unknown:
            raise ValueError("selected finding is not present in audit")
        findings = [available[key] for key in sorted(set(selected))]
    else:
        findings = [available[key] for key in sorted(available)]
    changes = []
    for finding in findings:
        if not finding["id"].startswith("oversized-instruction-") or len(finding.get("evidence", [])) != 1:
            continue
        source = sources.get(finding["evidence"][0])
        if not source or source.get("role") != "instruction":
            continue
        path = source.get("path")
        try:
            p, st = _regular_at(root, path)
            raw = p.read_bytes()
            text = raw.decode("utf-8")
        except (UnicodeDecodeError, ValueError, OSError):
            continue
        if _sha(raw) != source.get("sha256"):
            raise ValueError("audit input is stale")
        sections = _sections(text)
        if not sections:
            continue
        warning = audit["assumptions"].get("warn")
        cpt = audit["assumptions"].get("chars_per_token")
        if not isinstance(warning, int) or not isinstance(cpt, (int, float)) or cpt <= 0:
            raise ValueError("invalid audit assumptions")
        chosen = None
        for index in range(len(sections) - 1, -1, -1):
            start = sections[index][0]
            moved = text[start:]
            digest = hashlib.sha256(raw).hexdigest()[:12]
            reference = "docs/agent-reference/%s-%s.md" % (_slug(path), digest)
            link = os.path.relpath(reference, str(PurePosixPath(path).parent)).replace(os.sep, "/")
            if link.startswith("./"):
                link = link[2:]
            titles = [title for _, title in sections[index:]]
            replacement = "## On-demand reference\n\nSee [%s](%s) when this guidance applies.\n\nSections: %s\n" % ("On-demand reference", link, ", ".join(titles))
            post_text = text[:start] + replacement
            if est_tokens(post_text, cpt) <= warning:
                chosen = (reference, moved, post_text, titles)
                break
        if chosen is None:
            continue
        reference, moved, post_text, titles = chosen
        target = root.joinpath(*safe_relative(reference).parts)
        # Existing targets, including symlinks, are never overwritten.
        if target.exists() or target.is_symlink():
            raise ValueError("on-demand reference target already exists")
        ref_text = "# On-demand reference\n\nThis reference was moved from `%s` to reduce always-on instruction context.\n\n%s" % (path, moved)
        post = post_text.encode("utf-8")
        ref = ref_text.encode("utf-8")
        before_tokens = est_tokens(text, cpt)
        after_tokens = est_tokens(post_text, cpt)
        if after_tokens >= before_tokens:
            continue
        changes.append({"path": path, "old": raw, "new": post, "mode": format(stat.S_IMODE(st.st_mode), "04o"),
                        "reference": reference, "ref": ref, "finding": finding["id"], "metric": finding["baseline_metric_id"],
                        "delta": after_tokens - before_tokens, "titles": titles})
    changes.sort(key=lambda item: item["path"])
    bindings, diff_lines, rationales, deltas = [], [], [], []
    for change in changes:
        for path, old, new, is_new, mode in ((change["path"], change["old"], change["new"], False, change["mode"]),
                                              (change["reference"], b"", change["ref"], True, "0644")):
            lines = _diff(old, new, path, is_new)
            diff_lines.extend(lines)
            binding = {"path": path, "postimage_sha256": _sha(new), "mode": mode}
            if is_new:
                binding["must_be_absent"] = True
            else:
                binding["preimage_sha256"] = _sha(old)
            bindings.append(binding)
            for number in range(1, _hunks(lines) + 1):
                rationales.append({"path": path, "hunk": number, "source_metric_id": change["metric"],
                                   "finding_id": change["finding"], "expected_standing_token_delta": change["delta"],
                                   "quality_risk": "Moved guidance may be needed for every task.",
                                   "required_human_judgment": "Confirm the moved guidance is safe to load on demand."})
        deltas.append({"metric_id": change["metric"], "finding_id": change["finding"], "absolute_delta": change["delta"], "unit": "tokens"})
    bindings.sort(key=lambda binding: binding["path"])
    rationales.sort(key=lambda rationale: (rationale["path"], rationale["hunk"]))
    document = {"document_type": "ace.candidate", "schema_version": 1,
                "status": "ok" if changes else "no_candidate", "audit": audit, "audit_id": audit["id"],
                "selected_findings": [change["finding"] for change in changes], "bindings": bindings,
                "diff": "".join(diff_lines), "rationales": rationales, "expected_metric_deltas": deltas}
    document["candidate_id"] = _candidate_id(document)
    document["id"] = document_id(document)
    return document
