"""Non-mutating candidate verification in a private temporary copy."""
import hashlib, os, re, shutil, stat, tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from .audit import run
from .adapters import BY_ID
from .measurement import compare
from .legacy import load_jsonc
from .patch import propose, recheck_manifest, safe_relative
from .schema import canonical, document_id, validate_candidate


def _sha(data): return "sha256:"+hashlib.sha256(data).hexdigest()
def _check(name, state, reason=None):
    d={"name":name,"state":state}
    if reason: d["reason"]=reason
    return d

def _numeric(value):
    """Return an exact decimal for a JSON numeric scalar, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number=Decimal(str(value))
    except Exception:
        return None
    return number if number.is_finite() else None

def _delta_scalar(value, baseline, candidate):
    # Keep integral metrics integral. Decimal-string metrics (notably USD) stay
    # JSON strings so no binary float is introduced into the wire report.
    if isinstance(baseline, int) and not isinstance(baseline, bool) and isinstance(candidate, int) and not isinstance(candidate, bool):
        return int(value)
    return format(value, "f")

def _walk_safe(root):
    for base, dirs, files in os.walk(str(root), followlinks=False):
        for name in dirs+files:
            p=Path(base)/name; mode=p.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                raise ValueError("workspace contains special file")

def _copy(root, target):
    _walk_safe(root)
    shutil.copytree(str(root), str(target), symlinks=True, copy_function=shutil.copy2)

def _target(root, path, create=False):
    parts=safe_relative(path).parts; cur=root
    for part in parts[:-1]:
        cur=cur/part
        if cur.is_symlink(): raise ValueError("changed path parent is a symlink")
        if create and not cur.exists(): cur.mkdir(mode=0o755)
    out=root.joinpath(*parts)
    if out.is_symlink(): raise ValueError("changed path is a symlink")
    return out

def _parse_diff(diff, bindings):
    """Parse only the tightly constrained unified diff emitted by patch.py."""
    lines=diff.splitlines(True); i=0; output={}; bound={b["path"] for b in bindings}
    while i < len(lines):
        if not lines[i].startswith("--- "): raise ValueError("invalid candidate diff")
        old=lines[i][4:].rstrip("\n"); i+=1
        if i>=len(lines) or not lines[i].startswith("+++ "): raise ValueError("invalid candidate diff")
        new=lines[i][4:].rstrip("\n"); i+=1
        path=(new[2:] if new.startswith("b/") else None)
        if not path or path not in bound or (old != "/dev/null" and old != "a/"+path): raise ValueError("unbound candidate diff path")
        chunks=[]; saw=False
        while i < len(lines) and not lines[i].startswith("--- "):
            if not re.match(r"^@@ -(?:0|[1-9][0-9]*)(?:,[0-9]+)? \+(?:0|[1-9][0-9]*)(?:,[0-9]+)? @@", lines[i]): raise ValueError("invalid candidate diff header")
            chunks.append(lines[i]); saw=True; i+=1
            while i < len(lines) and not lines[i].startswith("@@ ") and not lines[i].startswith("--- "):
                if not lines[i] or lines[i][0] not in " +-\\": raise ValueError("invalid candidate diff line")
                chunks.append(lines[i]); i+=1
        if not saw or path in output: raise ValueError("duplicate or empty candidate diff")
        output[path]=chunks
    if set(output) != bound: raise ValueError("candidate diff does not cover bindings")
    return output

def _apply(root, candidate):
    parsed=_parse_diff(candidate["diff"], candidate["bindings"])
    by={b["path"]:b for b in candidate["bindings"]}
    # Reconstruct each file from hunks, validating every old/context line. Generated
    # diffs are accepted only when their exact output matches the binding hash.
    for path in sorted(parsed):
        b=by[path]; target=_target(root,path,create=b.get("must_be_absent") is True)
        if b.get("must_be_absent"):
            if target.exists() or target.is_symlink(): raise ValueError("new-file target exists")
            old=[]
        else: old=target.read_text(encoding="utf-8").splitlines(True)
        result=[]; pos=0
        for line in parsed[path]:
            if line.startswith("@@ "):
                match=re.match(r"^@@ -([0-9]+)",line)
                start=int(match.group(1))
                # A new-file hunk conventionally starts at zero; existing hunks use 1-based offsets.
                wanted=0 if start == 0 else start-1
                if wanted < pos or wanted > len(old): raise ValueError("invalid candidate hunk order")
                result.extend(old[pos:wanted]); pos=wanted
                continue
            if line.startswith("\\"): continue
            mark,text=line[0],line[1:]
            if mark == " ":
                if pos>=len(old) or old[pos] != text: raise ValueError("candidate hunk context does not match")
                result.append(text); pos+=1
            elif mark == "-":
                if pos>=len(old) or old[pos] != text: raise ValueError("candidate hunk deletion does not match")
                pos+=1
            elif mark == "+": result.append(text)
        result.extend(old[pos:]); raw="".join(result).encode("utf-8")
        if _sha(raw) != b["postimage_sha256"]: raise ValueError("candidate postimage hash mismatch")
        target.write_bytes(raw); os.chmod(str(target),int(b["mode"],8))

def _args(audit):
    x=audit["assumptions"]
    return SimpleNamespace(chars_per_token=x["chars_per_token"],warn=x["warn"],turns=x["turns"],tools_per_server=x["tools_per_server"],tokens_per_tool=x["tokens_per_tool"],measurement_kind=x["measurement_kind"],fail_over=None,tool_config=None,tool_dump=None,model_session=x.get("model_session",False),user=x.get("user",150),assistant=x.get("assistant",600),tool_output=x.get("tool_output",1200),cache_discount=x.get("cache_discount",.1),price_input=x.get("price_input"),price_cached=x.get("price_cached"),price_output=x.get("price_output"),measurement_csv=None,external_evidence=audit.get("external_evidence",[]))

def _regenerated_audit(root, candidate):
    """Rebuild the proposal baseline, retaining only inert measurement payload."""
    audit=candidate["audit"]
    adapter_id=audit["adapter"]["id"]
    regenerated=run(root,BY_ID[adapter_id],_args(audit))
    # Measurement is optional evidence for CPCT, never proposal scope. It is not
    # regenerated from untrusted files, but retaining it preserves the candidate's
    # deterministic audit envelope without using it to choose a patch.
    regenerated["measurement"]=audit.get("measurement")
    regenerated["id"]=document_id(regenerated)
    comparable=lambda value: {key:item for key,item in value.items() if key not in ("id","measurement")}
    if canonical(comparable(regenerated)) != canonical(comparable(audit)):
        raise ValueError("candidate audit is not authentic to the current workspace")
    return regenerated

def _authenticate(root, candidate):
    regenerated=_regenerated_audit(root,candidate)
    expected=propose(root,regenerated,candidate["selected_findings"])
    if canonical(expected) != canonical(candidate):
        raise ValueError("candidate is not an authentic deterministic proposal")
    return regenerated

def verify(root, candidate, options):
    validate_candidate(candidate)
    checks=[]
    # Everything security-sensitive happens before the temporary copy exists.
    audit=_authenticate(root,candidate)
    recheck_manifest(root,audit)
    for b in candidate["bindings"]:
        p=_target(root,b["path"])
        if b.get("must_be_absent"):
            if p.exists() or p.is_symlink(): raise ValueError("new-file target exists")
        else:
            st=p.lstat()
            if not stat.S_ISREG(st.st_mode) or _sha(p.read_bytes()) != b["preimage_sha256"] or format(stat.S_IMODE(st.st_mode),"04o") != b["mode"]: raise ValueError("candidate preimage is stale")
    parsed=_parse_diff(candidate["diff"],candidate["bindings"])
    expected=[(path,n) for path, lines in parsed.items() for n in range(1,sum(1 for line in lines if line.startswith("@@ "))+1)]
    actual=[(x.get("path"),x.get("hunk")) for x in candidate["rationales"] if isinstance(x,dict)]
    if sorted(actual) != sorted(expected) or len(actual) != len(candidate["rationales"]): raise ValueError("candidate rationales do not match diff hunks")
    checks.append(_check("preconditions","pass"))
    failed=False; temp_clean=False; temporary_root=None; repeated=None; deltas=[]
    ordered=("preconditions","isolated_apply","postimage_hashes","supported_config_parse","supported_config_structure","introduced_reference_targets","repeat_audit","metric_delta")
    def stage(name, action):
        nonlocal failed
        try:
            action(); checks.append(_check(name,"pass")); return True
        except (ValueError, OSError) as e:
            failed=True; checks.append(_check(name,"fail",str(e))); return False
    try:
        with tempfile.TemporaryDirectory() as td:
            temporary_root=Path(td); os.chmod(td,0o700); copy=Path(td)/"workspace"
            if stage("isolated_apply", lambda: (_copy(root,copy), _apply(copy,candidate))):
                def postimages():
                    for b in candidate["bindings"]:
                        p=_target(copy,b["path"])
                        if not p.is_file() or _sha(p.read_bytes()) != b["postimage_sha256"]: raise ValueError("candidate postimage hash mismatch")
                if stage("postimage_hashes", postimages):
                    adapter=candidate["audit"]["adapter"]
                    supported=set((adapter.get("workspace_tool_config") or {}).get("paths", []))
                    config_paths=[b["path"] for b in candidate["bindings"] if b["path"] in supported]
                    if config_paths:
                        parsed_configs={}
                        def parse_configs():
                            for path in config_paths:
                                try: parsed_configs[path]=load_jsonc(_target(copy,path).read_text(encoding="utf-8"))
                                except Exception: raise ValueError("changed supported configuration is malformed")
                        if stage("supported_config_parse", parse_configs):
                            def config_structure():
                                root_key=(adapter.get("workspace_tool_config") or {}).get("root_keys", [None])[0]
                                for data in parsed_configs.values():
                                    servers=data.get(root_key) if isinstance(data,dict) and root_key else None
                                    if not isinstance(servers,dict) or not all(isinstance(x,dict) for x in servers.values()): raise ValueError("changed supported configuration has invalid structure")
                            stage("supported_config_structure", config_structure)
                    else:
                        checks.extend((_check("supported_config_parse","unavailable","no changed supported configuration"), _check("supported_config_structure","unavailable","no changed supported configuration")))
                    if not failed:
                        def references():
                            for b in candidate["bindings"]:
                                if not b["path"].endswith(".md"): continue
                                origin=_target(copy,b["path"])
                                if not stat.S_ISREG(origin.lstat().st_mode): raise ValueError("introduced reference is not regular")
                                for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)",origin.read_text(encoding="utf-8",errors="replace")):
                                    if target.startswith("/") or "://" in target: raise ValueError("introduced reference target is unsafe")
                                    resolved=(origin.parent / target)
                                    try: resolved.relative_to(copy)
                                    except ValueError: raise ValueError("introduced reference target escapes workspace")
                                    if resolved.is_symlink() or not resolved.is_file(): raise ValueError("introduced reference target is missing or unsafe")
                        if stage("introduced_reference_targets", references):
                            def rerun():
                                nonlocal repeated
                                repeated=run(copy,BY_ID[candidate["audit"]["adapter"]["id"]],_args(candidate["audit"]))
                            if stage("repeat_audit", rerun):
                                def metric_delta():
                                    nonlocal deltas
                                    base={m["id"]:m for m in candidate["audit"]["metrics"]}; now={m["id"]:m for m in repeated["metrics"]}
                                    missing=sorted(set(base)^set(now))
                                    if missing: raise ValueError("required metric disappeared or was added: "+", ".join(missing))
                                    for key in sorted(base):
                                        before, after=base[key]["value"], now[key]["value"]
                                        before_number, after_number=_numeric(before), _numeric(after)
                                        if before_number is None or after_number is None:
                                            if before != after: raise ValueError("non-numeric metric changed: "+key)
                                            continue
                                        difference=after_number-before_number
                                        pct=None if before_number == 0 else format(difference/before_number*Decimal(100), "f")
                                        deltas.append({"metric_id":key,"baseline":before,"candidate":after,"absolute_delta":_delta_scalar(difference,before,after),"percentage_delta":pct})
                                stage("metric_delta", metric_delta)
    finally:
        temp_clean = temporary_root is not None and not temporary_root.exists()
    present={x["name"] for x in checks}
    for name in ordered:
        if name not in present: checks.append(_check(name,"unavailable","prior check failed"))
    cpct=None
    if options.pre_csv:
        cpct=compare(options.pre_csv,options.post_csv,options.completion_standard,options.harness_id,options.pre_kind,options.post_kind)
        checks.append(_check("quality_guardrails","pass" if cpct["quality_guardrails_pass"] else "fail"))
        if not cpct["quality_guardrails_pass"]: failed=True
    checks.append(_check("temporary_cleanup","pass" if temp_clean else "fail"))
    if not temp_clean: failed=True
    outcome=cpct["outcome_claim"] if cpct else "pending_insufficient_evidence"
    doc={"document_type":"ace.verification","schema_version":1,"status":"failed" if failed else "ok","candidate_id":candidate["candidate_id"],"baseline_metrics":candidate["audit"]["metrics"],"candidate_metrics":repeated["metrics"] if repeated else [],"deltas":deltas,"checks":checks,"cpct_comparison":cpct,"outcome_claim":outcome,"failure_reasons":[] if not failed else [x.get("reason") for x in checks if x["state"]=="fail" and x.get("reason")]}
    doc["id"]=document_id(doc)
    return doc, (1 if failed else 0)
