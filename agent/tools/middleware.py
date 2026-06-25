import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Callable, Any, Optional
from utils.prompt_loader import load_system_prompt, load_report_prompt
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, before_model, wrap_tool_call, dynamic_prompt
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger


class MonitorMiddleware(AgentMiddleware):
    @wrap_tool_call
    def _monitor_tool(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        logger.info(f"[tool monitor]执行工具：{request.tool_call['name']}")
        logger.info(f"[tool monitor]工具参数：{request.tool_call['args']}")
        try:
            result = handler(request)
            logger.info(f"[tool monitor]工具{request.tool_call['name']}返回结果：{result}")
            
            if request.tool_call['name'] == "fill_context_for_report":
                request.runtime.context["report"] = True                              
            return result
        except Exception as e:
            logger.error(f"[tool monitor]工具{request.tool_call['name']}执行异常：{str(e)}")
            raise e


@before_model
def log_before_model(
    state: AgentState,
    runtime: Runtime,
) -> Optional[dict[str, Any]]:
    logger.info(f"[log before model]即将调用模型，带有{len(state)}条消息")
    logger.debug(f"[log before model]{type(state['messages'][-1]).__name__}{state['messages'][-1].content.strip()}")
    return None


@dynamic_prompt
def report_prompt_switch(
    request: Any
):
    is_report = request.runtime.context.get("report", False)
    if is_report:
        return load_report_prompt()
    return load_system_prompt()


monitor_tool = MonitorMiddleware()