#!/usr/bin/env python3
"""Local Agentic Cost Efficiency audit entry point."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ace.cli import entry
if __name__ == "__main__":
    code=entry()
    try:
        sys.stdout.flush()
    except BrokenPipeError:
        # Avoid CPython's later interpreter-shutdown flush turning a successful
        # closed-consumer invocation into exit status 120.
        null=os.open(os.devnull,os.O_WRONLY)
        try: os.dup2(null,sys.stdout.fileno())
        finally: os.close(null)
        code=0
    sys.exit(code)
