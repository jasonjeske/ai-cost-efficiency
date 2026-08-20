"""End-to-end safety tests for the public entry point and checked-in fixtures."""
import ast
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ace.cli import entry, write_atomic
from ace.schema import validate_audit, validate_candidate, validate_verification

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
ADAPTERS = ("claude-code", "codex", "cursor", "vscode-copilot")
FORBIDDEN_MODULES = {"requests", "urllib", "socket", "http", "asyncio", "subprocess"}
FORBIDDEN_CALLS = {"system", "popen", "run", "Popen", "create_connection", "socket"}


def boundary_violations(tree):
    """Find forbidden process/network APIs while preserving ACE's local run()."""
    violations=[]; direct=set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(item.name for item in node.names if item.name.split(".")[0] in FORBIDDEN_MODULES)
        elif isinstance(node, ast.ImportFrom):
            module=(node.module or "").split(".")[0]
            if module in FORBIDDEN_MODULES: violations.append(node.module or "")
            for item in node.names:
                if module not in ("ace", "audit") and item.name in FORBIDDEN_CALLS:
                    direct.add(item.asname or item.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALLS: violations.append(node.func.attr)
            elif isinstance(node.func, ast.Name) and node.func.id in direct: violations.append(node.func.id)
    return violations


def snapshot(root):
    """Capture bytes, modes, and links, including the fixture's actual Git state."""
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            result[relative] = ("link", stat.S_IMODE(mode), os.readlink(path))
        elif stat.S_ISREG(mode):
            result[relative] = ("file", stat.S_IMODE(mode), path.read_bytes())
    return result


class AcceptanceTests(unittest.TestCase):
    def copy_workspace(self, directory, adapter):
        root = Path(directory) / adapter / "workspace"
        shutil.copytree(FIXTURES / "adapters" / adapter / "workspace", root, symlinks=True)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        # Git maintenance can create a transient lock while the immutability
        # snapshot is traversing .git on hosted macOS runners. Disable it in
        # this disposable fixture so the snapshot has a stable Git state.
        subprocess.run(["git", "-C", str(root), "config", "maintenance.auto", "false"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "gc.auto", "0"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture baseline"], check=True)
        return root

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = entry(list(args))
        return code, out.getvalue(), err.getvalue()

    def subprocess(self, *args):
        # sitecustomize makes a network attempt fail inside the child process.
        with tempfile.TemporaryDirectory() as directory:
            hook = Path(directory) / "sitecustomize.py"
            hook.write_text("import socket\ndef deny(*a, **k): raise AssertionError('network disabled')\nsocket.socket = deny\nsocket.create_connection = deny\n")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(directory))
            return subprocess.run([sys.executable, str(ROOT / "scripts" / "ace.py"), *args], text=True, capture_output=True, env=env)

    def chain(self, root, adapter, output):
        output.mkdir(parents=True, exist_ok=True)
        audit, candidate = output / "audit.json", output / "candidate.json"
        run = self.subprocess("audit", str(root), "--adapter", adapter, "--json", "--output", str(audit))
        self.assertEqual(run.returncode, 0, run.stderr)
        run = self.subprocess("propose", str(root), "--audit", str(audit), "--json", "--output", str(candidate))
        self.assertEqual(run.returncode, 0, run.stderr)
        run = self.subprocess("verify", str(root), "--candidate", str(candidate), "--json")
        self.assertEqual(run.returncode, 0, run.stderr)
        documents = json.loads(audit.read_text()), json.loads(candidate.read_text()), json.loads(run.stdout)
        for validator, document in zip((validate_audit, validate_candidate, validate_verification), documents):
            self.assertEqual(validator(document), document)
        return documents

    def test_offline_e2e_all_four_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for adapter in ADAPTERS:
                audit, candidate, verification = self.chain(self.copy_workspace(base, adapter), adapter, base / adapter)
                self.assertEqual(audit["adapter"]["id"], adapter)
                self.assertEqual(candidate["status"], "ok")
                self.assertTrue(candidate["bindings"])
                self.assertEqual(verification["status"], "ok")

    def test_workspace_and_git_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for adapter in ADAPTERS:
                root = self.copy_workspace(base, adapter)
                before = snapshot(root)
                self.chain(root, adapter, base / (adapter + "-output"))
                self.assertEqual(before, snapshot(root), adapter)

    def test_deterministic_json_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_workspace(directory, "claude-code")
            output = Path(directory) / "output"; output.mkdir()
            first = self.subprocess("audit", str(root), "--adapter", "claude-code", "--json")
            second = self.subprocess("audit", str(root), "--adapter", "claude-code", "--json")
            self.assertEqual(first.stdout, second.stdout)
            audit, candidate, verification = self.chain(root, "claude-code", output)
            rendered = "\n".join(json.dumps(x, sort_keys=True) for x in (audit, candidate, verification))
            for forbidden in (str(root), "/Users/fake/home", "ACE_SECRET_CANARY", "sk-TEST-SECRET", "fixture-tool"):
                self.assertNotIn(forbidden, rendered)
            self.assertTrue(first.stdout.endswith("\n"))

    def test_measurement_label_canaries_do_not_escape_audit_or_verification_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.copy_workspace(directory,"claude-code"); base=Path(directory); raw="UNKNOWN_LABEL_CANARY sk-secret /Users/fake/home"
            pre,post=base/"pre.csv",base/"post.csv"
            for source,target in ((FIXTURES/"measurement"/"pre.csv",pre),(FIXTURES/"measurement"/"post.csv",post)):
                target.write_text(source.read_text().replace("single-file-change",raw).replace("mid",raw),encoding="utf-8")
            audit,candidate=base/"audit.json",base/"candidate.json"
            self.assertEqual(self.subprocess("audit",str(root),"--adapter","claude-code","--measurement-csv",str(pre),"--json","--output",str(audit)).returncode,0)
            self.assertNotIn("UNKNOWN_LABEL_CANARY",audit.read_text())
            self.assertEqual(self.subprocess("propose",str(root),"--audit",str(audit),"--json","--output",str(candidate)).returncode,0)
            result=self.subprocess("verify",str(root),"--candidate",str(candidate),"--pre-csv",str(pre),"--post-csv",str(post),"--completion-standard",str(FIXTURES/"measurement"/"completion-standard.txt"),"--harness-id","canary","--json")
            self.assertEqual(result.returncode,0,result.stderr); self.assertNotIn("UNKNOWN_LABEL_CANARY",result.stdout)

    def test_priced_tool_dump_model_session_verify_has_exact_decimal_deltas(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.copy_workspace(directory,"claude-code"); output=Path(directory)/"output"; output.mkdir()
            audit=output/"audit.json"; candidate=output/"candidate.json"
            command=("audit",str(root),"--adapter","claude-code","--tool-dump",str(FIXTURES/"tool-dumps"/"measured.json"),"--model-session","--price-input","1.25","--price-cached","0.125","--price-output","2.5","--json","--output",str(audit))
            self.assertEqual(self.subprocess(*command).returncode,0)
            self.assertEqual(self.subprocess("propose",str(root),"--audit",str(audit),"--json","--output",str(candidate)).returncode,0)
            result=self.subprocess("verify",str(root),"--candidate",str(candidate),"--json")
            self.assertEqual(result.returncode,0,result.stderr)
            doc=json.loads(result.stdout); self.assertEqual(doc["status"],"ok")
            self.assertEqual({m["id"] for m in doc["baseline_metrics"]},{m["id"] for m in doc["candidate_metrics"]})
            usd=[d for d in doc["deltas"] if d["metric_id"].startswith("session-estimated-cost-usd")]
            self.assertTrue(usd); self.assertTrue(all(isinstance(d["absolute_delta"],str) and isinstance(d["percentage_delta"],str) for d in usd))

    def test_new_ace_broken_pipe_exits_zero(self):
        process=subprocess.Popen([sys.executable,str(ROOT/"scripts"/"ace.py"),"audit",str(FIXTURES/"adapters"/"claude-code"/"workspace"),"--adapter","claude-code","--json"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        process.stdout.close()
        _, error=process.communicate()
        self.assertEqual(process.returncode,0,error)

    def test_stale_hash_fails_before_temp_copy(self):
        candidate = json.loads((FIXTURES / "verification" / "stale-candidate.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_workspace(directory, "claude-code")
            path = Path(directory) / "candidate.json"; path.write_text(json.dumps(candidate))
            with patch("ace.verify.tempfile.TemporaryDirectory", side_effect=AssertionError("copy created")):
                code, _, _ = self.invoke("verify", str(root), "--candidate", str(path), "--json")
            self.assertEqual(code, 4)

    def test_verify_uses_and_removes_temp_copy(self):
        candidate = json.loads((FIXTURES / "expected" / "proposal" / "claude-code-v1.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_workspace(directory, "claude-code")
            path = Path(directory) / "candidate.json"; path.write_text(json.dumps(candidate))
            created, writes = [], []
            real_apply = __import__("ace.verify", fromlist=["_apply"])._apply
            class Spy(tempfile.TemporaryDirectory):
                def __enter__(self):
                    value = super().__enter__(); created.append(Path(value)); return value
            def confined(copy, document):
                writes.append(copy)
                self.assertTrue(any(str(copy).startswith(str(item)) for item in created))
                return real_apply(copy, document)
            with patch("ace.verify.tempfile.TemporaryDirectory", Spy), patch("ace.verify._apply", confined):
                code, _, error = self.invoke("verify", str(root), "--candidate", str(path), "--json")
            self.assertEqual(code, 0, error); self.assertTrue(writes); self.assertTrue(all(not item.exists() for item in created))
            # Induce a post-copy failure and prove the same cleanup guarantee.
            created.clear()
            with patch("ace.verify.tempfile.TemporaryDirectory", Spy), patch("ace.verify._apply", side_effect=ValueError("induced post-copy failure")):
                code, _, _ = self.invoke("verify", str(root), "--candidate", str(path), "--json")
            self.assertEqual(code, 1); self.assertTrue(created); self.assertTrue(all(not item.exists() for item in created))

    def test_forged_candidates_fail_before_temp_copy(self):
        source=json.loads((FIXTURES / "expected" / "proposal" / "claude-code-v1.json").read_text())
        def seal(document):
            body=dict(document); body.pop("id"); body.pop("candidate_id")
            document["candidate_id"]="sha256:"+hashlib.sha256(__import__("ace.schema",fromlist=["canonical"]).canonical(body)).hexdigest()
            document["id"]=__import__("ace.schema",fromlist=["document_id"]).document_id(document)
        with tempfile.TemporaryDirectory() as directory:
            root=self.copy_workspace(directory,"claude-code")
            for label,change in (
                ("application source",lambda x: x["bindings"].__setitem__(0,dict(x["bindings"][0],path="CONFIG.py"))),
                ("hook",lambda x: x["bindings"].__setitem__(1,dict(x["bindings"][1],path="hooks/pre-commit"))),
                ("invented finding",lambda x: x["audit"]["findings"][0].__setitem__("impact","invented")),
                ("rationale",lambda x: x["rationales"][0].__setitem__("quality_risk","invented")),
                ("diff",lambda x: x.__setitem__("diff",x["diff"]+"forged\n")),
            ):
                candidate=json.loads(json.dumps(source)); change(candidate)
                if label == "invented finding":
                    candidate["audit"]["id"]=__import__("ace.schema",fromlist=["document_id"]).document_id(candidate["audit"])
                    candidate["audit_id"]=candidate["audit"]["id"]
                seal(candidate); path=Path(directory)/(label.replace(" ","-")+".json"); path.write_text(json.dumps(candidate))
                with self.subTest(label=label), patch("ace.verify.tempfile.TemporaryDirectory",side_effect=AssertionError("copy created")):
                    code,_,error=self.invoke("verify",str(root),"--candidate",str(path),"--json")
                self.assertEqual(code,4,error)

    def test_output_symlink_retarget_cannot_write_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.copy_workspace(directory,"claude-code"); safe=Path(directory)/"safe"; safe.mkdir(); link=Path(directory)/"output"; link.symlink_to(safe,target_is_directory=True)
            real_fsync=os.fsync
            def retarget(fd):
                real_fsync(fd); link.unlink(); link.symlink_to(root,target_is_directory=True)
            with patch("ace.cli.os.fsync",retarget):
                with self.assertRaisesRegex(OSError,"destination changed|inside workspace"): write_atomic(root,link/"report.json",b"report")
            self.assertFalse((root/"report.json").exists())
            self.assertFalse((safe/"report.json").exists())

    def test_stdlib_only_no_node_bun_network_or_services(self):
        import ast
        modules = list((ROOT / "ace").glob("*.py")) + [ROOT / "scripts" / "ace.py"]
        for path in modules:
            self.assertFalse(boundary_violations(ast.parse(path.read_text(), filename=str(path))), path)

    def test_python_38_static_api_compatibility(self):
        post_38_attributes={"is_relative_to", "with_stem", "readlink", "hardlink_to", "removeprefix", "removesuffix"}
        modules=list((ROOT / "ace").glob("*.py"))+[ROOT / "scripts" / "ace.py"]
        for path in modules:
            tree=ast.parse(path.read_text(), filename=str(path))
            used={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
            self.assertFalse(post_38_attributes & used, path)

    def test_ast_boundary_mutations_catch_direct_imports_but_allow_ace_run(self):
        import ast
        for source in ("from subprocess import run as execute\nexecute([])", "from os import system as execute\nexecute('x')"):
            with self.subTest(source=source): self.assertTrue(boundary_violations(ast.parse(source)))
        self.assertFalse(boundary_violations(ast.parse("from ace.audit import run\nrun(None, None, None)")))


if __name__ == "__main__":
    unittest.main()
