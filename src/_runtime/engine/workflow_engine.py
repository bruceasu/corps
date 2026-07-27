import logging
from typing import Any, Dict, List, Optional, Callable
from .model import WorkflowConfig, WorkflowNode
from .parser import DAGParser
from .executor import NodeExecutor, ToolNodeExecutor

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(self, execute_tool_func: Callable[[str, Dict[str, Any]], Any], generate_llm_text_func: Optional[Callable[[str, str, str], str]] = None):
        self.dag_parser = DAGParser()
        self.execute_tool_func = execute_tool_func
        self.generate_llm_text_func = generate_llm_text_func

    def execute(self, config: WorkflowConfig, input_data: Dict[str, Any]) -> Dict[str, Any]:
        sorted_nodes = self.dag_parser.parse(config)
        
        # Initial context has 'input'
        context = {"input": input_data}
        
        for node in sorted_nodes:
            logger.info(f"Executing node: {node.id} ({node.type})")
            
            executor = self._get_executor(node)
            output = executor.execute(node, context)
            
            # Merge output into context
            # If node has outputKey, it's already wrapped in executor
            context.update(output)
            
        return context

    def _get_executor(self, node: WorkflowNode) -> NodeExecutor:
        if node.type == "tool":
            return ToolNodeExecutor(self.execute_tool_func)
        elif node.type == "agent":
            from .executor import AgentNodeExecutor
            return AgentNodeExecutor(self.execute_tool_func, self.generate_llm_text_func)
        else:
            raise ValueError(f"Unsupported node type: {node.type}")
