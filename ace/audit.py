"""Deterministic, local-only audit inventory."""
import hashlib, json, os, stat
from decimal import Decimal
from pathlib import Path
from .adapters import public_record
from .legacy import est_tokens, load_jsonc, simulate
from .schema import canonical, document_id
from .paths import explicit_regular_file
from .measurement import aggregate
INSTRUCTION_NAMES={"AGENTS.md","AGENT.md","CLAUDE.md","CLAUDE.local.md","GEMINI.md",".cursorrules",".windsurfrules",".clinerules","copilot-instructions.md"}
INSTRUCTION_SKIP={".git","node_modules","vendor",".venv","venv","__pycache__","dist","build","out",".next","target","coverage"}
CONTEXT_SKIP=INSTRUCTION_SKIP|{".hg",".svn",".cache",".idea",".vscode"}
BINARY={".png",".jpg",".jpeg",".gif",".webp",".ico",".pdf",".zip",".gz",".tar",".bz2",".xz",".7z",".mp3",".mp4",".mov",".avi",".wav",".woff",".woff2",".ttf",".otf",".eot",".so",".dylib",".dll",".exe",".bin",".sqlite",".db",".parquet",".pyc",".class",".jar"}
def rel(root,p): return p.relative_to(root).as_posix()
def regular(p): return stat.S_ISREG(p.lstat().st_mode)
def source_id(path): return "src-"+hashlib.sha256(path.encode()).hexdigest()[:12]
def record_source(root,p,role,raw=None):
    raw = p.read_bytes() if raw is None else raw; st=p.stat()
    return {"id":source_id(rel(root,p)),"path":rel(root,p),"sha256":"sha256:"+hashlib.sha256(raw).hexdigest(),"mode":format(stat.S_IMODE(st.st_mode),"04o"),"role":role}
def walk(root, skip, allowed_hidden=()):
    unknown=[]
    for base, dirs, files in os.walk(str(root), followlinks=False):
        keep=[]
        for name in dirs:
            p=Path(base)/name
            if p.is_symlink(): unknown.append({"path":rel(root,p),"reason":"symlink not followed"})
            elif name not in skip and not name.startswith(".git") and (not name.startswith(".") or name in allowed_hidden): keep.append(name)
        dirs[:]=keep
        for name in files:
            p=Path(base)/name
            if not regular(p): unknown.append({"path":rel(root,p),"reason":"non-regular file"}); continue
            yield p, unknown
def instruction_files(root):
    out=[]; unknown=[]
    for p, unknown in walk(root, INSTRUCTION_SKIP, (".cursor", ".github")):
        parent=p.parent.as_posix()
        if p.name in INSTRUCTION_NAMES or (parent.endswith("/.cursor/rules") or parent.endswith("/.github/instructions")) and p.name.endswith(".instructions.md"): out.append(p)
    return sorted(set(out), key=lambda x:rel(root,x)), unknown
def context_files(root):
    out=[]; unknown=[]
    for p, unknown in walk(root, CONTEXT_SKIP):
        if p.suffix.lower() in BINARY or b'\0' in p.read_bytes()[:8192]: continue
        out.append(p)
    return out, unknown
def metric(mid,name,value,unit,classification,confidence,sources,calc):
    return {"id":mid,"name":name,"value":value,"unit":unit,"classification":classification,"confidence":confidence,"source_ids":sorted(set(sources)),"calculation":calc}
def _external(label, raw, facts):
    digest="sha256:"+hashlib.sha256(raw).hexdigest(); sid=label+"-"+digest[7:19]
    return {"id":sid,"path":label,"sha256":digest,"mode":"0000","role":"external"}, {"source_id":sid,"sha256":digest,"kind":label,"facts":facts}
def _workspace_tool_path(root, adapter, unknown):
    """Return only a real in-workspace adapter artifact, never a symlink."""
    for name in adapter.tool_paths:
        p=root/name
        try: mode=p.lstat().st_mode
        except OSError: continue
        if stat.S_ISLNK(mode): unknown.append({"capability":"workspace_tool_config","value":None,"reason":"workspace config symlink not followed","fallback":None}); continue
        if stat.S_ISREG(mode): return p
        unknown.append({"capability":"workspace_tool_config","value":None,"reason":"workspace config artifact is not a regular file","fallback":None})
    unknown.append({"capability":"workspace_tool_config","value":None,"reason":"adapter-declared workspace artifact is unavailable","fallback":None})
    return None
def _session_metrics(args, instruction_tokens, tool_scenarios):
    result=[]
    for suffix, tools, sources, label in tool_scenarios:
        model=simulate(args.turns,instruction_tokens,tools,args.user,args.assistant,args.tool_output,args.cache_discount)
        model["fixed_prefix_tokens"]=instruction_tokens+tools
        # The wire contract is scalar. Keep all legacy total fields reproducible.
        for key, name in (("fixed_prefix_tokens","fixed prefix"),("total_input_tokens","total input"),("total_output_tokens","total output"),("fresh_input_tokens","fresh input"),("cached_input_tokens","cached input"),("effective_input_tokens_with_cache","effective input with cache")):
            mid="session-"+key.replace("_tokens","").replace("_","-")+suffix
            result.append(metric(mid,"session %s%s"%(name,label),model[key],"tokens","modeled","low",sources,"session-cost.py arithmetic with supplied session assumptions"))
        if args.price_input is not None:
            cached=args.price_cached if args.price_cached is not None else args.price_input
            output=args.price_output if args.price_output is not None else args.price_input
            cost=(model["fresh_input_tokens"]*Decimal(str(args.price_input))+model["cached_input_tokens"]*Decimal(str(cached))+model["total_output_tokens"]*Decimal(str(output)))/Decimal(1000000)
            result.append(metric("session-estimated-cost-usd"+suffix,"session estimated cost"+label,format(cost,".12g"),"usd","modeled","low",sources,"(fresh_input * price_input + cached_input * price_cached + output * price_output) / 1000000"))
    return result
def run(root, adapter, args):
    sources=[]; unknown=[]; metrics=[]; findings=[]; evidence=list(getattr(args,"external_evidence",[]) or [])
    ins,u=instruction_files(root); unknown.extend(u); rows=[]
    for p in ins:
        raw=p.read_bytes(); s=record_source(root,p,"instruction",raw); sources.append(s); rows.append((p,s,est_tokens(raw.decode("utf-8",errors="replace"),args.chars_per_token)))
    rows.sort(key=lambda row:(-row[2],rel(root,row[0]))); total=sum(x[2] for x in rows)
    metrics.append(metric("instruction-standing-tokens","instruction standing tokens",total,"tokens_per_turn","estimated","medium",[x[1]["id"] for x in rows],"sum(round(utf8_replacement_characters / chars_per_token))"))
    for index,(p,s,tokens) in enumerate(rows,1):
        if tokens > args.warn: findings.append({"id":"oversized-instruction-"+str(index),"baseline_metric_id":"instruction-standing-tokens","baseline":tokens,"unit":"tokens","evidence":[s["id"]],"impact":"standing instruction cost","action_boundary":"review on-demand reference; no workspace change is made"})
    ctx,u=context_files(root); unknown.extend(u); crows=[]; recorded={s["path"] for s in sources}
    for p in ctx:
        try: raw=p.read_bytes()
        except OSError: unknown.append({"path":rel(root,p),"reason":"unreadable workspace file"}); continue
        if rel(root,p) not in recorded: sources.append(record_source(root,p,"context",raw)); recorded.add(rel(root,p))
        crows.append((p,len(raw),est_tokens(raw.decode("utf-8",errors="replace"),args.chars_per_token)))
    crows.sort(key=lambda x:(-x[2],rel(root,x[0]))); context_ids=[source_id(rel(root,x[0])) for x in crows]
    metrics += [metric("context-bytes","readable context bytes",sum(x[1] for x in crows),"bytes","measured","high",context_ids,"sum(regular text file bytes)"),metric("context-estimated-tokens","readable context estimate",sum(x[2] for x in crows),"tokens","estimated","medium",context_ids,"sum(per-file round(characters / chars_per_token))")]
    tool_scenarios=[]
    replay={x["kind"]:x for x in evidence if isinstance(x,dict) and isinstance(x.get("facts"),dict)}
    explicit_config = getattr(args,"tool_config",None)
    config_path, config_inside = (explicit_regular_file(root, explicit_config, "tool configuration") if explicit_config else (None, False))
    if config_path is None and adapter.tool_state == "available": config_path=_workspace_tool_path(root,adapter,unknown)
    if adapter.tool_state == "unavailable": unknown.append({"capability":"workspace_tool_config","value":None,"reason":"adapter does not expose supported project config","fallback":None})
    if config_path:
        # Explicit paths were checked before this branch reads them. Adapter paths
        # are independently constrained to real workspace artifacts.
        try:
            if not explicit_config and not regular(config_path): raise ValueError
            raw=config_path.read_bytes(); data=load_jsonc(raw.decode("utf-8"))
        except Exception: raise ValueError("tool configuration is missing or unreadable")
        servers=data.get("mcpServers",data.get("servers")) if isinstance(data,dict) else None
        if not isinstance(servers,dict): raise ValueError("tool configuration has unrecognized shape")
        if config_inside or (not explicit_config):
            sid=source_id(rel(root,config_path)); existing=next((s for s in sources if s["path"]==rel(root,config_path)),None)
            if not existing: sources.append(record_source(root,config_path,"tool_config",raw))
        else:
            ext, fact=_external("external-tool-config",raw,{"server_count":len(servers)}); sources.append(ext); evidence.append(fact); sid=ext["id"]
        low=args.tokens_per_tool if args.tokens_per_tool is not None else 100; high=args.tokens_per_tool if args.tokens_per_tool is not None else 500
        for suffix,value,bound in (("-low",len(servers)*args.tools_per_server*low,"low"),("-high",len(servers)*args.tools_per_server*high,"high")):
            metrics.append(metric("tool-standing-tokens"+suffix,"tool standing estimate "+bound,value,"tokens_per_turn","estimated","low",[sid],"server_count * tools_per_server * tokens_per_tool_"+bound))
            tool_scenarios.append((suffix,value,[x[1]["id"] for x in rows]+[sid]," ("+bound+")"))
    elif "external-tool-config" in replay:
        item=replay["external-tool-config"]; facts=item["facts"]; sid=item["source_id"]
        sources.append({"id":sid,"path":"external-tool-config","sha256":item["sha256"],"mode":"0000","role":"external"})
        low=args.tokens_per_tool if args.tokens_per_tool is not None else 100; high=args.tokens_per_tool if args.tokens_per_tool is not None else 500
        for suffix,value,bound in (("-low",facts["server_count"]*args.tools_per_server*low,"low"),("-high",facts["server_count"]*args.tools_per_server*high,"high")):
            metrics.append(metric("tool-standing-tokens"+suffix,"tool standing estimate "+bound,value,"tokens_per_turn","estimated","low",[sid],"server_count * tools_per_server * tokens_per_tool_"+bound)); tool_scenarios.append((suffix,value,[x[1]["id"] for x in rows]+[sid]," ("+bound+")"))
    if getattr(args,"tool_dump",None):
        p, _=explicit_regular_file(root, args.tool_dump, "tool definition dump")
        try: raw=p.read_bytes(); data=load_jsonc(raw.decode("utf-8")); tools=data if isinstance(data,list) else data["tools"]
        except Exception: raise ValueError("tool definition dump is missing or malformed")
        if not isinstance(tools,list) or not all(isinstance(t,dict) for t in tools): raise ValueError("tool definition dump has unrecognized shape")
        count=sum(est_tokens(json.dumps(t,separators=(",",":"),sort_keys=True),args.chars_per_token) for t in tools)
        ext,fact=_external("external-tool-dump",raw,{"definition_tokens":count,"tool_count":len(tools)}); sources.append(ext); evidence.append(fact)
        metrics.append(metric("tool-definition-tokens","serialized tool definition estimate",count,"tokens_per_turn","estimated","medium",[ext["id"]],"sum(round(compact JSON characters / chars_per_token))")); tool_scenarios.append(("-definitions",count,[x[1]["id"] for x in rows]+[ext["id"]]," (tool definitions)"))
    elif "external-tool-dump" in replay:
        item=replay["external-tool-dump"]; count=item["facts"]["definition_tokens"]; sid=item["source_id"]
        sources.append({"id":sid,"path":"external-tool-dump","sha256":item["sha256"],"mode":"0000","role":"external"}); metrics.append(metric("tool-definition-tokens","serialized tool definition estimate",count,"tokens_per_turn","estimated","medium",[sid],"sum(round(compact JSON characters / chars_per_token))")); tool_scenarios.append(("-definitions",count,[x[1]["id"] for x in rows]+[sid]," (tool definitions)"))
    if getattr(args,"model_session",False): metrics.extend(_session_metrics(args,total,tool_scenarios or [("",0,[x[1]["id"] for x in rows],"")]))
    measurement=aggregate(args.measurement_csv) if getattr(args,"measurement_csv",None) else None
    sources.sort(key=lambda x:(x["path"],x["id"])); manifest=[{"path":s["path"],"sha256":s["sha256"],"mode":s["mode"],"role":s["role"]} for s in sources if s["role"] != "external"]
    assumptions={"chars_per_token":args.chars_per_token,"warn":args.warn,"turns":args.turns,"tools_per_server":args.tools_per_server,"tokens_per_tool":args.tokens_per_tool,"measurement_kind":args.measurement_kind,"model_session":bool(getattr(args,"model_session",False)),"user":args.user,"assistant":args.assistant,"tool_output":args.tool_output,"cache_discount":args.cache_discount,"price_input":getattr(args,"price_input",None),"price_cached":getattr(args,"price_cached",None),"price_output":getattr(args,"price_output",None)}
    doc={"document_type":"ace.audit","schema_version":1,"status":"failed_threshold" if args.fail_over is not None and any(x[2]>args.fail_over for x in rows) else "ok","adapter":public_record(adapter),"assumptions":assumptions,"manifest":manifest,"manifest_digest":"sha256:"+hashlib.sha256(canonical(manifest)).hexdigest(),"sources":sources,"metrics":metrics,"findings":findings,"unknowns":sorted(unknown,key=lambda x:json.dumps(x,sort_keys=True)),"measurement":measurement}
    if evidence: doc["external_evidence"]=sorted(evidence,key=lambda x:x["source_id"])
    doc["id"]=document_id(doc); return doc
