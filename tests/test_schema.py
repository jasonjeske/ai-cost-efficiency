import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from ace.adapters import BY_ID
from ace.audit import run
from ace.patch import propose
from ace.schema import document_id, validate_audit, validate_candidate, validate_verification
from ace.measurement import compare
from ace.verify import verify

class SchemaTests(unittest.TestCase):
    def test_v1_golden_documents(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"workspace"; root.mkdir()
            (root/"CLAUDE.md").write_text("# Rules\n\n## A\n"+"a"*100+"\n\n## B\n"+"b"*100)
            args=SimpleNamespace(chars_per_token=4.0,warn=20,turns=20,tools_per_server=10,tokens_per_tool=None,measurement_kind="estimated",fail_over=None,tool_config=None,tool_dump=None,model_session=False,user=150,assistant=600,tool_output=1200,cache_discount=.1,measurement_csv=None)
            audit=run(root,BY_ID["claude-code"],args); candidate=propose(root,audit)
            options=SimpleNamespace(pre_csv=None,post_csv=None,completion_standard=None,harness_id=None,pre_kind="estimated",post_kind="estimated")
            verification,_=verify(root,candidate,options)
            self.assertEqual(validate_audit(json.loads(json.dumps(audit))),audit)
            self.assertEqual(validate_candidate(json.loads(json.dumps(candidate))),candidate)
            self.assertEqual(validate_verification(json.loads(json.dumps(verification))),verification)
            for document in (audit,candidate,verification): self.assertEqual(document["id"], document["id"].lower())
            # Checked-in v1 documents are public contract fixtures, not values
            # manufactured by this test.
            expected=Path(__file__).resolve().parent/"fixtures"/"expected"
            for path, validator in ((expected/"audit"/"claude-code-v1.json", validate_audit), (expected/"proposal"/"claude-code-v1.json", validate_candidate), (expected/"verification"/"claude-code-v1.json", validate_verification)):
                document=json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(validator(document), document)
                self.assertEqual(document["id"], document["id"].lower())

    def test_checked_in_schemas_are_standalone_and_runtime_shapes_are_strict(self):
        schemas=Path(__file__).resolve().parents[1]/"schemas"
        expected=Path(__file__).resolve().parent/"fixtures"/"expected"
        # Schemas are distributable documents: refs may only point inside the
        # same document, so schema tests need no jsonschema installation.
        for name in ("audit", "candidate", "verification"):
            schema=json.loads((schemas/("ace-"+name+"-v1.schema.json")).read_text())
            self.assertIn("$defs",schema)
            def refs(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key=="$ref": self.assertTrue(item.startswith("#/"),item)
                        else: refs(item)
                elif isinstance(value,list):
                    for item in value: refs(item)
            refs(schema)
        documents={"audit":json.loads((expected/"audit"/"claude-code-v1.json").read_text()),"candidate":json.loads((expected/"proposal"/"claude-code-v1.json").read_text()),"verification":json.loads((expected/"verification"/"claude-code-v1.json").read_text())}
        self.assertEqual(validate_audit(documents["audit"]),documents["audit"])
        self.assertEqual(validate_candidate(documents["candidate"]),documents["candidate"])
        self.assertEqual(validate_verification(documents["verification"]),documents["verification"])
        for mutate in (
            lambda a: a["adapter"].update({"workspace_tool_config":{"state":"available","paths":[1],"root_keys":["mcpServers"]}}),
            lambda a: a["adapter"].update({"workspace_tool_config":{"state":"available","paths":[],"root_keys":[]}}),
            lambda a: a["adapter"].update({"workspace_tool_config":{"state":"unavailable","reason":""}}),
            lambda a: a["adapter"]["tool_definition_dump"].update({"source":"user"}),
            lambda a: a["adapter"]["local_session_usage"].update({"fallback":"user"}),
            lambda a: a["adapter"]["instruction_inventory"].update({"state":"unavailable"}),
        ):
            malformed=copy.deepcopy(documents["audit"]); mutate(malformed); malformed["id"]=document_id(malformed)
            with self.assertRaises(ValueError): validate_audit(malformed)
            candidate=copy.deepcopy(documents["candidate"]); candidate["audit"]=malformed; candidate["audit_id"]=malformed["id"]; candidate["candidate_id"]="sha256:"+__import__('hashlib').sha256(__import__('ace.schema',fromlist=['canonical']).canonical({k:v for k,v in candidate.items() if k not in ('id','candidate_id')})).hexdigest(); candidate["id"]=document_id(candidate)
            with self.assertRaises(ValueError): validate_candidate(candidate)
        measured=copy.deepcopy(documents["verification"])
        measurement=Path(__file__).resolve().parent/"fixtures"/"measurement"
        measured["cpct_comparison"]=compare(measurement/"pre.csv",measurement/"post.csv",measurement/"completion-standard.txt","schema-wire-shape","measured","measured")
        measured["outcome_claim"]=measured["cpct_comparison"]["outcome_claim"]; measured["id"]=document_id(measured)
        self.assertEqual(validate_verification(measured),measured)
        malformed_cpct=copy.deepcopy(measured); malformed_cpct["cpct_comparison"]["classes"][0]["task_class"]="user-controlled"; malformed_cpct["id"]=document_id(malformed_cpct)
        with self.assertRaises(ValueError): validate_verification(malformed_cpct)
if __name__ == "__main__": unittest.main()
