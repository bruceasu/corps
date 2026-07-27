import re
from typing import List, Dict, Set, Any
from collections import deque
from .model import WorkflowNode, WorkflowEdge, WorkflowConfig

class DAGParser:
    def parse(self, config: WorkflowConfig) -> List[WorkflowNode]:
        node_map = {node.id: node for node in config.nodes}
        
        # Build adjacency lists
        dependencies: Dict[str, List[str]] = {node.id: [] for node in config.nodes}
        dependents: Dict[str, List[str]] = {node.id: [] for node in config.nodes}
        
        for edge in config.edges:
            dependencies[edge.target].append(edge.source)
            dependents[edge.source].append(edge.target)
            
        # Detect cycles (simplified)
        self._detect_cycle(dependencies, config.nodes)
        
        # Topological sort (Kahn's algorithm)
        return self._topological_sort(node_map, dependencies, dependents)

    def _detect_cycle(self, dependencies: Dict[str, List[str]], nodes: List[WorkflowNode]):
        visited = set()
        rec_stack = set()
        
        for node in nodes:
            if self._has_cycle_dfs(node.id, dependencies, visited, rec_stack):
                raise ValueError(f"Cycle detected in workflow at node: {node.id}")

    def _has_cycle_dfs(self, node_id: str, dependencies: Dict[str, List[str]], visited: Set[str], rec_stack: Set[str]) -> bool:
        if node_id in rec_stack:
            return True
        if node_id in visited:
            return False
            
        visited.add(node_id)
        rec_stack.add(node_id)
        
        for dep in dependencies.get(node_id, []):
            if self._has_cycle_dfs(dep, dependencies, visited, rec_stack):
                return True
                
        rec_stack.remove(node_id)
        return False

    def _topological_sort(self, node_map: Dict[str, WorkflowNode], dependencies: Dict[str, List[str]], dependents: Dict[str, List[str]]) -> List[WorkflowNode]:
        in_degree = {node_id: len(deps) for node_id, deps in dependencies.items()}
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            node_id = queue.popleft()
            result.append(node_map[node_id])
            
            for dependent in dependents.get(node_id, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
                    
        if len(result) != len(node_map):
            raise ValueError("Circular dependency detected or unreachable nodes in workflow")
            
        return result

class SkillParser:
    def parse_skill(self, skill_definition: Dict[str, Any]) -> WorkflowConfig:
        steps = skill_definition.get("steps", [])
        nodes = []
        edges = []
        
        previous_step_id = None
        output_keys_to_node_id = {}

        for step in steps:
            node = WorkflowNode(
                id=step.get("id"),
                type=step.get("type", "tool"),
                toolName=step.get("toolName"),
                outputKey=step.get("outputKey"),
                arguments=step.get("arguments", {})
            )
            nodes.append(node)
            
            if node.outputKey:
                output_keys_to_node_id[node.outputKey] = node.id
            
            # Auto-infer edges from variable substitution if possible
            # But for simplicity and based on current SKILL.md, steps are sequential
            if previous_step_id:
                edges.append(WorkflowEdge(source=previous_step_id, target=node.id))
            
            previous_step_id = node.id
            
        return WorkflowConfig(nodes=nodes, edges=edges)
