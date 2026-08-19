"""Static, fail-closed adapter capability records."""
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Adapter:
    id: str
    detection_markers: tuple
    instruction_patterns: tuple
    tool_state: str
    tool_paths: tuple = ()
    tool_root_keys: tuple = ()

ADAPTERS = (
    Adapter("claude-code", ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json"),
            ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md"), "available", (".mcp.json",), ("mcpServers",)),
    Adapter("codex", (".codex/",), ("AGENTS.md",), "unavailable"),
    Adapter("cursor", (".cursor/", ".cursorrules"),
            ("AGENTS.md", ".cursorrules", ".cursor/rules/*"), "available", (".cursor/mcp.json",), ("mcpServers",)),
    Adapter("vscode-copilot", (".github/copilot-instructions.md", ".github/instructions/", ".vscode/mcp.json"),
            ("AGENTS.md", ".github/copilot-instructions.md", ".github/instructions/*.instructions.md"), "available", (".vscode/mcp.json",), ("servers",)),
)
BY_ID = {adapter.id: adapter for adapter in ADAPTERS}

def _marker_exists(root, marker):
    path = root / marker.rstrip("/")
    return path.is_dir() if marker.endswith("/") else path.is_file()

def detect(root):
    """Return exactly one matching adapter or raise ValueError without content."""
    hits = [a for a in ADAPTERS if any(_marker_exists(root, marker) for marker in a.detection_markers)]
    if len(hits) != 1:
        names = ", ".join(a.id for a in hits) if hits else "none"
        raise ValueError("adapter detection requires exactly one match; matched: " + names + ". Select --adapter explicitly.")
    return hits[0]

def public_record(adapter):
    tool = {"state": adapter.tool_state}
    if adapter.tool_state == "available":
        tool.update({"paths": list(adapter.tool_paths), "root_keys": list(adapter.tool_root_keys)})
    else:
        tool["reason"] = "no supported JSON or JSONC project artifact in slice 1"
    unavailable = {"state": "unavailable", "fallback": "measurement_csv"}
    return {"id": adapter.id, "detection_markers": list(adapter.detection_markers),
            "instruction_inventory": {"state": "available", "native_patterns": list(adapter.instruction_patterns)},
            "workspace_tool_config": tool,
            "tool_definition_dump": {"state": "available", "source": "explicit_input"},
            "local_session_usage": unavailable, "task_outcomes": unavailable}
