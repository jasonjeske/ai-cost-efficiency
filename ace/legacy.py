"""Stdlib ports of the legacy calculation semantics used by audit."""
import json, re

def est_tokens(text, cpt): return int(round(len(text) / cpt))
def strip_jsonc(text):
    out=[]; i=0; inside=False; esc=False
    while i < len(text):
        c=text[i]
        if inside:
            out.append(c); esc = (not esc and c == "\\")
            if c == '"' and not esc: inside=False
            elif c != "\\": esc=False
            i += 1; continue
        if c == '"': inside=True; out.append(c); i += 1
        elif c == '/' and i+1 < len(text) and text[i+1] == '/':
            i = text.find('\n', i); i = len(text) if i < 0 else i
        elif c == '/' and i+1 < len(text) and text[i+1] == '*':
            end=text.find('*/', i+2); i=len(text) if end < 0 else end+2
        else: out.append(c); i += 1
    return re.sub(r",(\s*[}\]])", r"\1", ''.join(out))
def load_jsonc(text):
    try: return json.loads(text)
    except json.JSONDecodeError: return json.loads(strip_jsonc(text))
def simulate(turns, system, tools, user, assistant, tool_output, discount):
    history=total_in=total_out=fresh=cached=0
    for turn in range(1, turns+1):
        current=system+tools+history+user; new=current if turn == 1 else user+assistant+tool_output
        total_in += current; total_out += assistant; fresh += new; cached += current-new; history += user+assistant+tool_output
    return {"total_input_tokens": total_in, "total_output_tokens": total_out, "fresh_input_tokens": fresh, "cached_input_tokens": cached, "effective_input_tokens_with_cache": int(round(fresh + cached * discount))}
