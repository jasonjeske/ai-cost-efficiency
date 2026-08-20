"""Privacy-safe validation, exact aggregation, and CPCT comparison."""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from .redact import redact

HEADER=["date","task_id","task_class","model_tier","sessions","turns_total","attempts","input_tokens","cached_input_tokens","output_tokens","completed_to_standard","cost_usd","notes"]

def _decimal(value):
    return format(value, "f")

def _opaque(prefix, value):
    """Stable public identifier for an untrusted CSV label."""
    return prefix + sha256(value.encode("utf-8")).hexdigest()[:16]

def _integer(value, positive=False):
    # int('1.0') is rejected, as are whitespace and signs: CSV fields are a
    # wire format, not permissive user input.
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or (positive and value == "0"):
        raise ValueError
    return int(value)

def _money(value):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError
    number=Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError
    return number

def load(path):
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader=csv.DictReader(handle)
            if reader.fieldnames != HEADER: raise ValueError("measurement CSV has unexpected header")
            rows=list(reader)
    except OSError:
        raise ValueError("measurement CSV is missing or unreadable")
    if not rows: raise ValueError("measurement CSV is empty")
    task_ids=set()
    for row in rows:
        try:
            datetime.strptime(row["date"], "%Y-%m-%d")
            # IDs are validation-only. They never leave this module's public data.
            if not row["task_id"] or row["task_id"].strip() != row["task_id"] or row["task_id"] in task_ids: raise ValueError
            task_ids.add(row["task_id"])
            if not row["task_class"] or not row["model_tier"] or row["completed_to_standard"] not in ("y","n"): raise ValueError
            for key in ("sessions","turns_total","attempts"):
                _integer(row[key], positive=True)
            for key in ("input_tokens","cached_input_tokens","output_tokens"):
                _integer(row[key])
            if row["cost_usd"]:
                _money(row["cost_usd"])
        except (ValueError, InvalidOperation):
            raise ValueError("measurement CSV contains invalid row")
    return rows

def _aggregate(rows):
    groups={}
    for row in rows:
        g=groups.setdefault(row["task_class"], {"attempted":0,"completed":0,"single":0,"tokens":0,"cost":Decimal(0),"all_cost":True,"tiers":set(),"dates":[]})
        done=row["completed_to_standard"] == "y"
        g["attempted"] += 1; g["completed"] += done; g["single"] += done and int(row["attempts"]) == 1
        g["tokens"] += int(row["input_tokens"])+int(row["output_tokens"]); g["tiers"].add(row["model_tier"]); g["dates"].append(row["date"])
        if row["cost_usd"]: g["cost"] += Decimal(row["cost_usd"])
        else: g["all_cost"] = False
    result=[]
    for name,g in sorted(groups.items()):
        unit="usd" if g["all_cost"] else "tokens"; spend=g["cost"] if unit == "usd" else Decimal(g["tokens"])
        completed=Decimal(g["completed"]); attempted=Decimal(g["attempted"])
        result.append({"task_class":_opaque("task-",name),"attempted":g["attempted"],"completed":g["completed"],"completion_rate":_decimal(completed/attempted),"single_pass_rate":_decimal(Decimal(g["single"])/attempted),"spend":_decimal(spend),"unit":unit,"cpct":None if not completed else _decimal(spend/completed),"model_tiers":sorted(_opaque("tier-",tier) for tier in g["tiers"]),"first_date":min(g["dates"]),"last_date":max(g["dates"])})
    return result

def aggregate(path):
    return _aggregate(load(path))

def compare(pre_path, post_path, completion_standard, harness, pre_kind, post_kind):
    try:
        with open(completion_standard,"rb") as handle: standard_hash="sha256:"+sha256(handle.read()).hexdigest()
    except OSError: raise ValueError("completion standard is missing or unreadable")
    pre_rows,post_rows=load(pre_path),load(post_path)
    pre={x["task_class"]:x for x in _aggregate(pre_rows)}; post={x["task_class"]:x for x in _aggregate(post_rows)}
    replay=bool({row["task_id"] for row in pre_rows}&{row["task_id"] for row in post_rows})
    reasons=[]; classes=[]; guardrail=True; all_improved=True; any_regressed=False
    if replay: reasons.append("task IDs overlap across cohorts")
    if set(pre) != set(post): reasons.append("task classes do not match")
    for name in sorted(set(pre)|set(post)):
        a,b=pre.get(name),post.get(name)
        item={"task_class":name,"pre":a,"post":b}
        if not a or not b: item["status"]="pending"; classes.append(item); continue
        cr=[]
        if a["model_tiers"] != b["model_tiers"]: cr.append("model tiers differ")
        if a["unit"] != b["unit"]: cr.append("spend units differ")
        if a["attempted"] < 10 or b["attempted"] < 10: cr.append("fewer than 10 attempts per cohort")
        if replay: cr.append("task IDs overlap across cohorts")
        if datetime.strptime(a["last_date"],"%Y-%m-%d") >= datetime.strptime(b["first_date"],"%Y-%m-%d"): cr.append("pre/post date windows overlap or are unordered")
        # Each cohort must itself cover at least fourteen calendar days.
        if (datetime.strptime(a["last_date"],"%Y-%m-%d")-datetime.strptime(a["first_date"],"%Y-%m-%d")).days < 14 or (datetime.strptime(b["last_date"],"%Y-%m-%d")-datetime.strptime(b["first_date"],"%Y-%m-%d")).days < 14: cr.append("cohort span is less than two weeks")
        if not a["cpct"] or not b["cpct"]: cr.append("zero completed-task denominator")
        if Decimal(b["completion_rate"]) < Decimal(a["completion_rate"]): cr.append("completion rate declined"); guardrail=False; any_regressed=True
        if b["completed"] < a["completed"]: cr.append("completion volume declined"); guardrail=False; any_regressed=True
        reduction=None
        if a["cpct"] and b["cpct"] and a["unit"] == b["unit"]: reduction=(Decimal(a["cpct"])-Decimal(b["cpct"]))/Decimal(a["cpct"])
        item.update({"cpct_reduction":None if reduction is None else _decimal(reduction),"reasons":cr,"status":"pending" if cr else ("improved" if reduction >= Decimal(".10") else "not_improved")})
        if item["status"] != "improved": all_improved=False
        classes.append(item); reasons.extend(name+": "+x for x in cr)
    if any_regressed: outcome="regressed"
    elif reasons: outcome="pending_insufficient_evidence"
    elif all_improved: outcome="improved"
    else: outcome="not_improved"; reasons.append("CPCT reduction is below 10 percent")
    return {"completion_standard_sha256":standard_hash,"harness_id":"sha256:"+sha256(harness.encode()).hexdigest()[:16],"classification":"modeled" if "modeled" in (pre_kind,post_kind) else ("estimated" if "estimated" in (pre_kind,post_kind) else "measured"),"classes":classes,"outcome_claim":outcome,"reasons":sorted(set(reasons)),"quality_guardrails_pass":guardrail}
