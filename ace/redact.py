"""Conservative report redaction."""
import re
_PATTERNS = (re.compile(r'(?i)(?:api[_-]?key|token|secret|password)\s*[=:]\s*[^\s,;}]+'), re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~-]+'), re.compile(r'\bsk-[A-Za-z0-9_-]+'))
def redact(value):
    text = str(value)
    for pattern in _PATTERNS:
        text = pattern.sub("<redacted>", text)
    return text.replace("/Users/", "<home>/").replace("/home/", "<home>/")
