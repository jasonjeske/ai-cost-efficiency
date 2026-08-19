import hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class AuditTests(unittest.TestCase):
    def make_workspace(self, marker, instruction="CLAUDE.md"):
        td=tempfile.TemporaryDirectory(); root=Path(td.name)/"workspace"; root.mkdir()
        (root/instruction).write_text("# Rules\n" + "x"*100 + "\n")
        if marker.endswith("/"): (root/marker[:-1]).mkdir(parents=True)
        else:
            (root/marker).parent.mkdir(parents=True,exist_ok=True)
            key = "servers" if marker.startswith(".vscode") else "mcpServers"
            (root/marker).write_text(json.dumps({key: {}}))
        return td,root
    def audit(self, root, *extra):
        return subprocess.run([sys.executable,"scripts/ace.py","audit",str(root),"--json",*extra],cwd=ROOT,text=True,capture_output=True)
    def test_all_adapter_detection_and_honesty(self):
        for adapter,marker,inst in (("claude-code","CLAUDE.md","CLAUDE.md"),("codex",".codex/","AGENTS.md"),("cursor",".cursor/","AGENTS.md"),("vscode-copilot",".vscode/mcp.json","AGENTS.md")):
            td,root=self.make_workspace(marker,inst)
            with td:
                result=self.audit(root); self.assertEqual(result.returncode,0,result.stderr)
                doc=json.loads(result.stdout); self.assertEqual(doc["adapter"]["id"],adapter)
                if adapter == "codex": self.assertEqual(doc["adapter"]["workspace_tool_config"]["state"],"unavailable")
    def test_deterministic_schema_and_redaction(self):
        td,root=self.make_workspace("CLAUDE.md")
        with td:
            (root/".mcp.json").write_text('{"mcpServers":{"x":{"token":"sk-SECRET_CANARY"}}}')
            a=self.audit(root,"--tool-config",str(root/".mcp.json")); b=self.audit(root,"--tool-config",str(root/".mcp.json"))
            self.assertEqual(a.stdout,b.stdout); self.assertNotIn("SECRET_CANARY",a.stdout)
            from ace.schema import validate_audit
            validate_audit(json.loads(a.stdout))
    def test_explicit_symlink_inputs_are_rejected_before_reading(self):
        td,root=self.make_workspace("CLAUDE.md")
        with td:
            outside=Path(td.name)/"outside"; outside.mkdir()
            config=outside/"config.json"; config.write_text('{"mcpServers":{}}')
            dump=outside/"dump.json"; dump.write_text('[]')
            for option, target in (("--tool-config",config),("--tool-dump",dump)):
                for directory in (root,outside):
                    link=directory/("linked-"+option[2:]); link.symlink_to(target)
                    result=self.audit(root,option,str(link))
                    self.assertEqual(result.returncode,3,result.stderr)
                    self.assertIn("symlink",result.stderr)

    def test_workspace_root_symlink_fails_closed(self):
        td,root=self.make_workspace("CLAUDE.md")
        with td:
            link=Path(td.name)/"workspace-link"; link.symlink_to(root,target_is_directory=True)
            result=self.audit(link,"--adapter","claude-code")
            self.assertEqual(result.returncode,4); self.assertIn("workspace root symlink is unsafe",result.stderr)

    def test_ambiguous_fails_closed(self):
        td,root=self.make_workspace("CLAUDE.md")
        with td:
            (root/".codex").mkdir(); result=self.audit(root)
            self.assertEqual(result.returncode,4); self.assertIn("claude-code, codex",result.stderr)
