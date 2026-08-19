"""Subprocess compatibility matrix for the four immutable legacy scripts."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts"
FIX=ROOT/"tests"/"fixtures"/"legacy"
GOLD=ROOT/"tests"/"fixtures"/"expected"/"legacy"
HASHES={"context-size.py":"5b2535fe7296af2f7a8ee17d0ac73f4ff4dcdef5ad09d435580b7b934cda6f67","instruction-audit.py":"bed9a469e991ba4d140851cf6f3f4d1dff634074ebcef8358247aa3b17f32dc5","session-cost.py":"2dd2a780feb84b77559fc5e175a59c98b6a810cb539ad661b5032e8819160ae4","tool-overhead.py":"d7275a5c82768a2c87542c898f4cbe30d9dc3e22f6cce3188d9fe27f6fa9dca7"}

class LegacyCompatibilityTests(unittest.TestCase):
 def invoke(self, name, *args, stdin=None):
  return subprocess.run([sys.executable,str(SCRIPTS/name),*map(str,args)],input=stdin,text=True,capture_output=True,cwd=ROOT)
 def test_pinned_legacy_scripts(self):
  for name,digest in HASHES.items(): self.assertEqual(hashlib.sha256((SCRIPTS/name).read_bytes()).hexdigest(),digest)
 def test_golden_controlled_json_and_stdin(self):
  cases=(("context-size.py",[FIX/"context","--json"],"context-json.out",None),("instruction-audit.py",[FIX/"repo","--json"],"instruction-json.out",None),("session-cost.py",["--turns","2","--json"],"session-json.out",None),("tool-overhead.py",[FIX/"mcp.jsonc","--json"],"tool-json.out",None),("tool-overhead.py",["-","--json"],"tool-stdin-json.out",(FIX/"tools.json").read_text()))
  for name,args,golden,stdin in cases:
   with self.subTest(name=name,golden=golden):
    result=self.invoke(name,*args,stdin=stdin); self.assertEqual(result.returncode,0,result.stderr)
    normalized=result.stdout.replace(str(ROOT)+"/", "")
    self.assertEqual(json.loads(normalized),json.loads((GOLD/golden).read_text()))
    self.assertEqual(result.stderr,"")
 def test_help_every_documented_program(self):
  for name in HASHES:
   result=self.invoke(name,"--help"); self.assertEqual(result.returncode,0,result.stderr); self.assertIn("usage:",result.stdout.lower())
 def test_options_errors_and_missing_inputs(self):
  matrix=(("context-size.py",["--top","0",FIX/"context"],0),("context-size.py",["does-not-exist"],1),("instruction-audit.py",["--fail-over","1",FIX/"repo"],1),("instruction-audit.py",["--warn","0",FIX/"repo"],0),("session-cost.py",["--turns","0"],2),("session-cost.py",["--cache-discount","2"],2),("tool-overhead.py",["missing.json"],1),("tool-overhead.py",["--tokens-per-tool","0",FIX/"mcp.jsonc"],0),("tool-overhead.py",[],0))
  for name,args,code in matrix:
   with self.subTest(name=name,args=args):
    result=self.invoke(name,*args); self.assertEqual(result.returncode,code,result.stderr)
 def test_malformed_and_unrecognized_tool_json(self):
  for payload, code in (("{", 1), ("[]", 0), ("{\"other\": true}", 1)):
   result=self.invoke("tool-overhead.py","-","--json",stdin=payload)
   self.assertEqual(result.returncode, code)

if __name__ == "__main__": unittest.main()
