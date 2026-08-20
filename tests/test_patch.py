import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "proposal"

class ProposalTests(unittest.TestCase):
    def workspace(self, body):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "workspace"
        root.mkdir()
        (root / "CLAUDE.md").write_text(body, encoding="utf-8")
        return tmp, root

    def command(self, *args):
        return subprocess.run([sys.executable, "scripts/ace.py", *args], cwd=ROOT,
                              text=True, capture_output=True)

    def audit(self, root, destination, warn=100):
        result = self.command("audit", str(root), "--adapter", "claude-code", "--warn", str(warn),
                              "--json", "--output", str(destination))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_eligible_proposal_is_deterministic_and_bound(self):
        body = (FIXTURES / "eligible-CLAUDE.md").read_text(encoding="utf-8")
        tmp, root = self.workspace(body)
        with tmp:
            audit = Path(tmp.name) / "audit.json"; self.audit(root, audit)
            first = self.command("propose", str(root), "--audit", str(audit), "--json")
            second = self.command("propose", str(root), "--audit", str(audit), "--json")
            self.assertEqual(first.returncode, 0, first.stderr); self.assertEqual(first.stdout, second.stdout)
            proposal = json.loads(first.stdout)
            self.assertEqual(proposal["status"], "ok")
            self.assertEqual(len(proposal["bindings"]), 2)
            existing, created = proposal["bindings"]
            self.assertEqual(existing["path"], "CLAUDE.md")
            self.assertIn("preimage_sha256", existing); self.assertEqual(existing["mode"], "0644")
            self.assertTrue(created["must_be_absent"]); self.assertEqual(created["mode"], "0644")
            self.assertIn("--- a/CLAUDE.md", proposal["diff"])
            self.assertIn("/dev/null", proposal["diff"])
            self.assertTrue(proposal["rationales"])
            self.assertEqual((root / "CLAUDE.md").read_text(), body)
            self.assertFalse((root / "docs").exists())

    def test_no_candidate_and_fenced_heading(self):
        body = (FIXTURES / "fenced-heading-CLAUDE.md").read_text(encoding="utf-8")
        tmp, root = self.workspace(body)
        with tmp:
            audit = Path(tmp.name) / "audit.json"; self.audit(root, audit)
            result = self.command("propose", str(root), "--audit", str(audit), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            proposal = json.loads(result.stdout)
            self.assertEqual(proposal["status"], "no_candidate")
            self.assertEqual(proposal["bindings"], [])

    def test_selected_finding_stale_input_path_safety_and_readonly(self):
        body = (FIXTURES / "eligible-CLAUDE.md").read_text(encoding="utf-8")
        tmp, root = self.workspace(body)
        with tmp:
            audit_path = Path(tmp.name) / "audit.json"; self.audit(root, audit_path)
            audit = json.loads(audit_path.read_text())
            finding = audit["findings"][0]["id"]
            # Exact finding selection works and a malicious report path is rejected.
            result = self.command("propose", str(root), "--audit", str(audit_path), "--finding", finding, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            audit["manifest"][0]["path"] = "../outside"
            audit["manifest_digest"] = "sha256:" + __import__("hashlib").sha256(
                __import__("ace.schema", fromlist=["canonical"]).canonical(audit["manifest"])).hexdigest()
            audit["id"] = __import__("ace.schema", fromlist=["document_id"]).document_id(audit)
            audit_path.write_text(json.dumps(audit))
            unsafe = self.command("propose", str(root), "--audit", str(audit_path), "--json")
            self.assertEqual(unsafe.returncode, 4)
            self.assertIn("unsafe", unsafe.stderr)
            self.audit(root, audit_path)
            (root / "CLAUDE.md").write_text(body + "changed")
            stale = self.command("propose", str(root), "--audit", str(audit_path), "--json")
            self.assertEqual(stale.returncode, 4)
            self.audit(root, audit_path)
            os.chmod(root, 0o555)
            try:
                readonly = self.command("propose", str(root), "--audit", str(audit_path), "--json")
                self.assertEqual(readonly.returncode, 0, readonly.stderr)
            finally:
                os.chmod(root, 0o755)

if __name__ == "__main__": unittest.main()
