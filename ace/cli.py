"""CLI plumbing for the implemented audit vertical slice."""
import argparse, os, sys, tempfile
from pathlib import Path
from .adapters import BY_ID, detect
from .audit import run
from .redact import redact
from .schema import canonical
from .patch import propose
from .verify import verify
from .paths import absolute, relative_to

def positive(value):
    try: value=int(value)
    except ValueError: raise argparse.ArgumentTypeError("must be an integer")
    if value < 1: raise argparse.ArgumentTypeError("must be positive")
    return value
def positive_float(value):
    try: value=float(value)
    except ValueError: raise argparse.ArgumentTypeError("must be a number")
    if value <= 0: raise argparse.ArgumentTypeError("must be positive")
    return value
def parser():
    p=argparse.ArgumentParser(prog="ace.py")
    subs=p.add_subparsers(dest="command",required=True)
    a=subs.add_parser("audit",help="inventory one local workspace")
    a.add_argument("workspace"); a.add_argument("--adapter",choices=["auto"]+sorted(BY_ID),default="auto")
    a.add_argument("--tool-config"); a.add_argument("--tool-dump"); a.add_argument("--measurement-csv")
    a.add_argument("--measurement-kind",choices=["measured","estimated","modeled"],default="estimated")
    a.add_argument("--chars-per-token",type=positive_float,default=4.0); a.add_argument("--warn",type=positive,default=2500); a.add_argument("--fail-over",type=positive)
    a.add_argument("--top",type=positive,default=15); a.add_argument("--turns",type=positive,default=20); a.add_argument("--tools-per-server",type=positive,default=10); a.add_argument("--tokens-per-tool",type=positive)
    a.add_argument("--model-session",action="store_true"); a.add_argument("--user",type=positive,default=150); a.add_argument("--assistant",type=positive,default=600); a.add_argument("--tool-output",type=positive,default=1200)
    a.add_argument("--cache-discount",type=float,default=.1); a.add_argument("--price-input",type=positive_float); a.add_argument("--price-cached",type=positive_float); a.add_argument("--price-output",type=positive_float)
    a.add_argument("--json",action="store_true"); a.add_argument("--output")
    s=subs.add_parser("propose",help="create a review-only on-demand-reference candidate")
    s.add_argument("workspace"); s.add_argument("--audit",required=True); s.add_argument("--finding",action="append")
    s.add_argument("--json",action="store_true"); s.add_argument("--output")
    s=subs.add_parser("verify",help="verify a candidate in an isolated copy")
    s.add_argument("workspace"); s.add_argument("--candidate",required=True)
    s.add_argument("--pre-csv"); s.add_argument("--post-csv"); s.add_argument("--completion-standard"); s.add_argument("--harness-id")
    s.add_argument("--pre-kind",choices=["measured","estimated","modeled"],default="estimated"); s.add_argument("--post-kind",choices=["measured","estimated","modeled"],default="estimated")
    s.add_argument("--json",action="store_true"); s.add_argument("--output")
    return p
def resolved_output(root, value):
    """Resolve output ancestry without rejecting macOS's /tmp -> /private/tmp."""
    lexical=absolute(value)
    try: parent=lexical.parent.resolve(strict=True)
    except OSError: raise OSError("output parent is unavailable or unsafe")
    if not parent.is_dir(): raise OSError("output parent is unavailable or unsafe")
    destination=parent / lexical.name
    try: resolved_destination=destination.resolve(strict=False)
    except OSError: raise OSError("output destination is unavailable or unsafe")
    try: resolved_destination.relative_to(root)
    except ValueError: return parent, destination
    raise OSError("output destination is inside workspace")
def write_atomic(root, path, data):
    parent,destination=resolved_output(root,path)
    fd,tmp=tempfile.mkstemp(prefix=".ace-",dir=str(parent)); tmp=Path(tmp)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as out: out.write(data); out.flush(); os.fsync(out.fileno())
        # Pin both writes to the resolved safe parent and recheck before replace.
        fresh_parent,fresh_destination=resolved_output(root,path)
        if fresh_parent != parent or fresh_destination != destination: raise OSError("output destination changed")
        os.replace(str(tmp),str(destination)); os.chmod(str(destination),0o600)
    except Exception:
        try: os.unlink(str(tmp))
        except OSError: pass
        raise
def human(doc, top):
    if doc["document_type"] == "ace.candidate":
        lines=["ACE proposal: " + doc["status"], "Selected findings: " + str(len(doc["selected_findings"]))]
        if doc["status"] == "no_candidate": lines.append("No eligible on-demand-reference change.")
        if doc["diff"]: lines.extend(["", doc["diff"].rstrip("\n")])
        return "\n".join(lines)+"\n"
    if doc["document_type"] == "ace.verification":
        lines=["ACE verification: " + doc["status"], "Outcome claim: " + doc["outcome_claim"]]
        for check in doc["checks"]: lines.append("  %s: %s" % (check["name"],check["state"]))
        return "\n".join(lines)+"\n"
    lines=["ACE audit: " + doc["adapter"]["id"], "Status: " + doc["status"], "Metrics:"]
    for m in doc["metrics"][:top]: lines.append("  %s: %s %s (%s)"%(m["name"],m["value"],m["unit"],m["classification"]))
    if doc["findings"]:
        lines.append("Findings:")
        for f in doc["findings"][:top]: lines.append("  %s: %s %s"%(f["id"],f["baseline"],f["unit"]))
    if doc["unknowns"]: lines.append("Unknowns: %d (missing data is not zero use)" % len(doc["unknowns"]))
    return "\n".join(lines)+"\n"
def main(argv=None):
    args=parser().parse_args(argv)
    if args.command == "verify" and any(bool(x) for x in (args.pre_csv,args.post_csv,args.completion_standard,args.harness_id)) and not all((args.pre_csv,args.post_csv,args.completion_standard,args.harness_id)):
        raise AceError(2,"pre/post measurement options are all required together")
    if args.command == "audit" and not 0 <= args.cache_discount <= 1: raise AceError(2,"--cache-discount must be between 0 and 1")
    root=Path(args.workspace)
    if root.is_symlink(): raise AceError(4,"workspace root symlink is unsafe")
    if not root.exists() or not root.is_dir(): raise AceError(3,"workspace is not a readable directory")
    try: root=root.resolve(strict=True)
    except OSError: raise AceError(3,"workspace is not a readable directory")
    if args.output:
        try: resolved_output(root,args.output)
        except OSError as e: raise AceError(4,str(e))
    if args.command == "audit":
        try: adapter=detect(root) if args.adapter == "auto" else BY_ID[args.adapter]
        except ValueError as e: raise AceError(4,str(e))
        try: doc=run(root,adapter,args)
        except ValueError as e: raise AceError(3,str(e))
        top=args.top
    elif args.command == "propose":
        try:
            with open(args.audit,"r",encoding="utf-8") as handle: audit=__import__('json').load(handle)
            doc=propose(root,audit,args.finding)
        except OSError: raise AceError(3,"audit input is missing or unreadable")
        except (__import__('json').JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            message=str(e); raise AceError(4 if "stale" in message or "unsafe" in message or "symlink" in message or "manifest" in message else 3,message)
        top=0
    else:
        try:
            with open(args.candidate,"r",encoding="utf-8") as handle: candidate=__import__('json').load(handle)
            doc, result=verify(root,candidate,args)
        except OSError: raise AceError(3,"candidate input is missing or unreadable")
        except (__import__('json').JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            message=str(e); raise AceError(4 if any(x in message for x in ("stale","unsafe","symlink","preimage","target exists","special","authentic")) else 3,message)
        top=0
    text=(__import__('json').dumps(doc,indent=2,sort_keys=True,ensure_ascii=False)+"\n") if args.json else human(doc,top)
    if args.output:
        try: write_atomic(root,args.output,text.encode("utf-8"))
        except OSError: raise AceError(3,"atomic output failure")
        print("ACE %s written: %s" % (args.command, args.output)); return result if args.command == "verify" else (1 if doc["status"] == "failed_threshold" else 0)
    sys.stdout.write(text); return result if args.command == "verify" else (1 if doc["status"] == "failed_threshold" else 0)
class AceError(Exception):
    def __init__(self,code,message): self.code=code; self.message=message
def entry(argv=None):
    try: return main(argv)
    except BrokenPipeError: return 0
    except AceError as e: sys.stderr.write("ACE[E%d]: %s\n"%(e.code,redact(e.message))); return e.code
    except Exception as e: sys.stderr.write("ACE[E5]: %s\n"%redact(e.__class__.__name__)); return 5
