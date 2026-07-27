from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class WorkflowNode:
    id: str
    type: str
    toolName: Optional[str] = None
    outputKey: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowEdge:
    source: str
    target: str

@dataclass
class WorkflowConfig:
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
