"""Small, strict standard-library runtime validator for public v1 documents."""
import hashlib, json
from pathlib import PurePosixPath
AUDIT_TOP={"document_type","schema_version","id","status","adapter","assumptions","manifest","manifest_digest","sources","metrics","findings","unknowns","measurement","external_evidence"}
CANDIDATE_TOP={"document_type","schema_version","id","status","audit","audit_id","selected_findings","bindings","diff","rationales","expected_metric_deltas","candidate_id"}
VERIFY_TOP={"document_type","schema_version","id","status","candidate_id","baseline_metrics","candidate_metrics","deltas","checks","cpct_comparison","outcome_claim","failure_reasons"}
SHA="sha256:"
def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def document_id(document):
    body=dict(document); body.pop("id",None); return SHA+hashlib.sha256(canonical(body)).hexdigest()
def _sha(value): return isinstance(value,str) and len(value)==71 and value.startswith(SHA) and all(c in "0123456789abcdef" for c in value[7:])
def _path(path):
    if not isinstance(path,str) or not path or "\\" in path or any(ord(c)<32 or ord(c)==127 for c in path): return False
    p=PurePosixPath(path); return not p.is_absolute() and p.as_posix()==path and all(x not in ("",".","..") for x in p.parts)
def _scalar(value): return (isinstance(value,(int,float,str)) and not isinstance(value,bool))
def _exact(item, keys): return isinstance(item,dict) and set(item)==keys
def _metric(item):
    keys={"id","name","value","unit","classification","confidence","source_ids","calculation"}
    return _exact(item,keys) and all(isinstance(item[x],str) and item[x] for x in ("id","name","unit","calculation")) and _scalar(item["value"]) and item["classification"] in ("measured","estimated","modeled") and item["confidence"] in ("high","medium","low") and isinstance(item["source_ids"],list) and len(item["source_ids"])==len(set(item["source_ids"])) and all(isinstance(x,str) and x for x in item["source_ids"])
def _source(item): return _exact(item,{"id","path","sha256","mode","role"}) and isinstance(item["id"],str) and isinstance(item["path"],str) and _sha(item["sha256"]) and isinstance(item["mode"],str) and len(item["mode"])==4 and all(c in "01234567" for c in item["mode"]) and item["role"] in ("instruction","context","tool_config","external")
def _strings(value, nonempty=False):
    return isinstance(value,list) and all(isinstance(x,str) and (x if nonempty else True) for x in value)
def _adapter(item):
    keys={"id","detection_markers","instruction_inventory","workspace_tool_config","tool_definition_dump","local_session_usage","task_outcomes"}
    if not _exact(item,keys) or item["id"] not in ("claude-code","codex","cursor","vscode-copilot") or not item["detection_markers"] or not _strings(item["detection_markers"],True): return False
    inv=item["instruction_inventory"]; tool=item["workspace_tool_config"]
    if not _exact(inv,{"state","native_patterns"}) or inv["state"]!="available" or not inv["native_patterns"] or not _strings(inv["native_patterns"],True): return False
    if not isinstance(tool,dict): return False
    if tool.get("state")=="available":
        if not _exact(tool,{"state","paths","root_keys"}) or not tool["paths"] or not tool["root_keys"] or not _strings(tool["paths"],True) or not _strings(tool["root_keys"],True): return False
    elif tool.get("state")=="unavailable":
        if not _exact(tool,{"state","reason"}) or not isinstance(tool["reason"],str) or not tool["reason"]: return False
    else: return False
    dump=item["tool_definition_dump"]
    if not _exact(dump,{"state","source"}) or dump["state"]!="available" or dump["source"]!="explicit_input": return False
    return all(_exact(item[x],{"state","fallback"}) and item[x]["state"]=="unavailable" and item[x]["fallback"]=="measurement_csv" for x in ("local_session_usage","task_outcomes"))
def validate_audit(document):
    if not isinstance(document,dict) or set(document)-AUDIT_TOP or not (AUDIT_TOP-{"measurement","external_evidence"})<=set(document): raise ValueError("unknown or missing audit field")
    if document.get("document_type")!="ace.audit" or document.get("schema_version")!=1 or document.get("status") not in ("ok","failed_threshold") or not _sha(document.get("id")) or document["id"]!=document_id(document): raise ValueError("invalid audit header")
    required_assumptions={"chars_per_token","warn","turns","tools_per_server","tokens_per_tool","measurement_kind"}
    allowed_assumptions=required_assumptions|{"model_session","user","assistant","tool_output","cache_discount","price_input","price_cached","price_output"}
    a=document["assumptions"]
    if not isinstance(a,dict) or not required_assumptions<=set(a) or set(a)-allowed_assumptions or not isinstance(a["chars_per_token"],(int,float)) or isinstance(a["chars_per_token"],bool) or not all(isinstance(a[x],int) and not isinstance(a[x],bool) for x in ("warn","turns","tools_per_server")) or (a["tokens_per_tool"] is not None and not isinstance(a["tokens_per_tool"],int)) or a["measurement_kind"] not in ("measured","estimated","modeled"): raise ValueError("invalid audit assumptions")
    if not _adapter(document["adapter"]) or not all(isinstance(x,list) for x in (document["sources"],document["manifest"],document["metrics"],document["findings"],document["unknowns"])): raise ValueError("invalid audit payload")
    if document.get("measurement") is not None and not isinstance(document["measurement"],list): raise ValueError("invalid measurement")
    if not _sha(document["manifest_digest"]) or document["manifest_digest"]!=SHA+hashlib.sha256(canonical(document["manifest"])).hexdigest(): raise ValueError("invalid audit manifest digest")
    ids=set(); paths=set()
    for source in document["sources"]:
        if not _source(source) or source["id"] in ids or (source["role"]!="external" and not _path(source["path"])) or (source["role"]=="external" and not source["path"].startswith("external-")): raise ValueError("invalid audit source")
        ids.add(source["id"])
    for item in document["manifest"]:
        if not _exact(item,{"path","sha256","mode","role"}) or not _path(item["path"]): raise ValueError("unsafe audit manifest path")
        if not _sha(item["sha256"]) or not isinstance(item["mode"],str) or item["path"] in paths or item["role"] not in ("instruction","context","tool_config"): raise ValueError("invalid audit manifest entry")
        paths.add(item["path"])
    if not all(_metric(m) and set(m["source_ids"])<=ids for m in document["metrics"]) or len({m["id"] for m in document["metrics"]}) != len(document["metrics"]): raise ValueError("invalid metric")
    for f in document["findings"]:
        if not _exact(f,{"id","baseline_metric_id","baseline","unit","evidence","impact","action_boundary"}) or not isinstance(f["id"],str) or not isinstance(f["baseline_metric_id"],str) or not _scalar(f["baseline"]) or not all(isinstance(f[x],str) for x in ("unit","impact","action_boundary")) or not isinstance(f["evidence"],list) or not all(isinstance(x,str) and x in ids for x in f["evidence"]): raise ValueError("invalid finding")
    for unknown in document["unknowns"]:
        if not isinstance(unknown,dict) or not set(unknown)<= {"path","capability","value","reason","fallback"} or not isinstance(unknown.get("reason"),str) or not unknown["reason"]: raise ValueError("invalid unknown")
        if "path" in unknown and not _path(unknown["path"]): raise ValueError("invalid unknown")
        if "capability" in unknown and unknown["capability"] not in ("workspace_tool_config",): raise ValueError("invalid unknown")
        if "fallback" in unknown and unknown["fallback"] is not None: raise ValueError("invalid unknown")
    for e in document.get("external_evidence",[]):
        if not _exact(e,{"source_id","sha256","kind","facts"}) or e["source_id"] not in ids or not _sha(e["sha256"]) or e["kind"] not in ("external-tool-config","external-tool-dump") or not isinstance(e["facts"],dict) or not all(isinstance(x,int) and x>=0 for x in e["facts"].values()): raise ValueError("invalid external evidence")
    return document
def validate_candidate(document):
    if not isinstance(document,dict) or set(document)!=CANDIDATE_TOP: raise ValueError("unknown or missing candidate field")
    if document.get("document_type")!="ace.candidate" or document.get("schema_version")!=1 or document.get("status") not in ("ok","no_candidate") or not _sha(document.get("id")) or document["id"]!=document_id(document): raise ValueError("invalid candidate header")
    body=dict(document); body.pop("id"); cid=body.pop("candidate_id")
    if not _sha(cid) or cid!=SHA+hashlib.sha256(canonical(body)).hexdigest(): raise ValueError("invalid candidate_id")
    validate_audit(document["audit"])
    if document["audit_id"]!=document["audit"]["id"] or not isinstance(document["diff"],str) or not isinstance(document["bindings"],list) or not isinstance(document["selected_findings"],list) or not all(isinstance(x,str) for x in document["selected_findings"]): raise ValueError("invalid candidate payload")
    paths=[]
    for b in document["bindings"]:
        new=b.get("must_be_absent") is True; keys={"path","postimage_sha256","mode","must_be_absent"} if new else {"path","postimage_sha256","mode","preimage_sha256"}
        if not _exact(b,keys) or not _path(b["path"]) or not _sha(b["postimage_sha256"]) or not isinstance(b["mode"],str) or (not new and not _sha(b["preimage_sha256"])): raise ValueError("invalid candidate binding")
        paths.append(b["path"])
    if paths!=sorted(paths) or len(paths)!=len(set(paths)): raise ValueError("candidate bindings are not sorted")
    for r in document["rationales"]:
        keys={"path","hunk","source_metric_id","finding_id","expected_standing_token_delta","quality_risk","required_human_judgment"}
        if not _exact(r,keys) or not _path(r["path"]) or not isinstance(r["hunk"],int) or r["hunk"]<1 or not isinstance(r["expected_standing_token_delta"],int) or not all(isinstance(r[x],str) for x in keys-{"path","hunk","expected_standing_token_delta"}): raise ValueError("invalid rationale")
    for d in document["expected_metric_deltas"]:
        if not _exact(d,{"metric_id","finding_id","absolute_delta","unit"}) or not isinstance(d["metric_id"],str) or not isinstance(d["finding_id"],str) or not isinstance(d["absolute_delta"],int) or not isinstance(d["unit"],str): raise ValueError("invalid expected delta")
    if document["status"]=="no_candidate" and any(document[x] for x in ("bindings","diff","selected_findings","rationales","expected_metric_deltas")): raise ValueError("invalid no-candidate payload")
    return document
def _cpct_hash(value): return isinstance(value,str) and len(value)==23 and value.startswith(SHA) and all(c in "0123456789abcdef" for c in value[7:])
def _opaque_id(value, prefix): return isinstance(value,str) and len(value)==len(prefix)+16 and value.startswith(prefix) and all(c in "0123456789abcdef" for c in value[len(prefix):])
def _cpct_cohort(item):
    keys={"task_class","attempted","completed","completion_rate","single_pass_rate","spend","unit","cpct","model_tiers","first_date","last_date"}
    return _exact(item,keys) and _opaque_id(item["task_class"],"task-") and all(isinstance(item[x],int) and not isinstance(item[x],bool) and item[x]>=0 for x in ("attempted","completed")) and all(isinstance(item[x],str) for x in ("completion_rate","single_pass_rate","spend","first_date","last_date")) and item["unit"] in ("usd","tokens") and (item["cpct"] is None or isinstance(item["cpct"],str)) and isinstance(item["model_tiers"],list) and all(_opaque_id(x,"tier-") for x in item["model_tiers"])
def _cpct(document):
    if not _exact(document,{"completion_standard_sha256","harness_id","classification","classes","outcome_claim","reasons","quality_guardrails_pass"}): return False
    if not _sha(document["completion_standard_sha256"]) or not _cpct_hash(document["harness_id"]) or document["classification"] not in ("measured","estimated","modeled") or document["outcome_claim"] not in ("improved","pending_insufficient_evidence","not_improved","regressed") or not isinstance(document["reasons"],list) or not all(isinstance(x,str) for x in document["reasons"]) or not isinstance(document["quality_guardrails_pass"],bool) or not isinstance(document["classes"],list): return False
    for item in document["classes"]:
        if not isinstance(item,dict) or not {"task_class","pre","post","status"}<=set(item) or not _opaque_id(item["task_class"],"task-") or item["status"] not in ("pending","improved","not_improved") or (item["pre"] is not None and not _cpct_cohort(item["pre"])) or (item["post"] is not None and not _cpct_cohort(item["post"])): return False
        expected={"task_class","pre","post","status"} if item["status"]=="pending" and (item["pre"] is None or item["post"] is None) else {"task_class","pre","post","status","cpct_reduction","reasons"}
        if set(item)!=expected or ("cpct_reduction" in item and item["cpct_reduction"] is not None and not isinstance(item["cpct_reduction"],str)) or ("reasons" in item and (not isinstance(item["reasons"],list) or not all(isinstance(x,str) for x in item["reasons"]))): return False
    return True
def validate_verification(document):
    if not isinstance(document,dict) or set(document)!=VERIFY_TOP or document.get("document_type")!="ace.verification" or document.get("schema_version")!=1 or document.get("status") not in ("ok","failed") or not _sha(document.get("id")) or document["id"]!=document_id(document) or not _sha(document.get("candidate_id")): raise ValueError("invalid verification document")
    if not all(isinstance(document[x],list) for x in ("baseline_metrics","candidate_metrics","deltas","checks","failure_reasons")) or not all(_metric(x) for x in document["baseline_metrics"]+document["candidate_metrics"]) or not all(isinstance(x,str) for x in document["failure_reasons"]): raise ValueError("invalid verification payload")
    for d in document["deltas"]:
        if not _exact(d,{"metric_id","baseline","candidate","absolute_delta","percentage_delta"}) or not isinstance(d["metric_id"],str) or not _scalar(d["baseline"]) or not _scalar(d["candidate"]) or not _scalar(d["absolute_delta"]) or (d["percentage_delta"] is not None and not isinstance(d["percentage_delta"],str)): raise ValueError("invalid verification delta")
    names={"preconditions","isolated_apply","postimage_hashes","supported_config_parse","supported_config_structure","introduced_reference_targets","repeat_audit","metric_delta","quality_guardrails","temporary_cleanup"}
    if not all(isinstance(c,dict) and set(c) in ({"name","state"},{"name","state","reason"}) and c.get("name") in names and c.get("state") in ("pass","fail","unavailable") and ("reason" not in c or isinstance(c["reason"],str)) for c in document["checks"]): raise ValueError("invalid verification checks")
    if (document["cpct_comparison"] is not None and not _cpct(document["cpct_comparison"])) or document["outcome_claim"] not in ("improved","pending_insufficient_evidence","not_improved","regressed"): raise ValueError("invalid verification outcome")
    return document
