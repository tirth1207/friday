"""Dynamic specialist-agent definitions for FRIDAY.

Dynamic agents are capability profiles, not arbitrary executable code. They can reuse
registered tools immediately while keeping new executable code behind FRIDAY's normal
permission and review gates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.runtime.registry import tool_registry

AGENT_STORE = Path(".friday") / "agents.json"


class AgentDefinition(BaseModel):
    name: str
    role: str
    description: str
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    dynamic: bool = True


def _load() -> list[AgentDefinition]:
    if not AGENT_STORE.exists():
        return []
    try:
        data = json.loads(AGENT_STORE.read_text(encoding="utf-8"))
        return [AgentDefinition.model_validate(item) for item in data]
    except Exception:
        return []


def _save(agents: list[AgentDefinition]) -> None:
    AGENT_STORE.parent.mkdir(parents=True, exist_ok=True)
    AGENT_STORE.write_text(
        json.dumps([agent.model_dump() for agent in agents], indent=2),
        encoding="utf-8",
    )


async def create_agent_definition(
    name: str,
    role: str,
    description: str,
    tools: list[str],
    system_prompt: str = "",
) -> dict[str, Any]:
    """Create/update a dynamic agent profile using existing registered tools."""
    clean_name = " ".join(name.split()).strip()
    if not clean_name:
        raise ValueError("Agent name cannot be empty.")
    if not tools:
        raise ValueError("A dynamic agent must have at least one tool.")

    unknown = [tool for tool in tools if tool_registry.get_metadata(tool) is None]
    if unknown:
        raise ValueError(f"Unknown tools for dynamic agent: {', '.join(unknown)}")

    definition = AgentDefinition(
        name=clean_name,
        role=role.strip(),
        description=description.strip(),
        tools=list(dict.fromkeys(tools)),
        system_prompt=system_prompt.strip(),
        dynamic=True,
    )
    agents = [agent for agent in _load() if agent.name.lower() != clean_name.lower()]
    agents.append(definition)
    _save(agents)
    return {
        "created": True,
        "agent": definition.model_dump(),
        "execution_model": "reuses_registered_tools",
        "note": "Executable code was not generated or executed. New code capabilities require the normal development and permission flow.",
    }


async def list_agent_definitions() -> list[dict[str, Any]]:
    return [agent.model_dump() for agent in _load()]


def get_dynamic_agent(name: str) -> AgentDefinition | None:
    target = name.strip().lower()
    return next((agent for agent in _load() if agent.name.lower() == target), None)
