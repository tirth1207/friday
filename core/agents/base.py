from dataclasses import dataclass, field
from typing import Any


@dataclass
class Agent:

    id: str

    name: str

    role: str

    objective: str

    tools: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )