"""
Agent工具层
提供RAG知识检索工具，结合MCP工具供多Agent系统使用。
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_core.tools import tool
from rag.rag_service import RagSummaryService
from utils.logger_handler import logger

# RAG服务单例
_rag_service = None


def _get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = RagSummaryService()
    return _rag_service


@tool(description="从车载知识库中检索与查询相关的专业资料并进行摘要总结。知识库包含：(1) 车载使用手册（座舱功能、空调、车窗、座椅、导航、多媒体等操作说明）；(2) 故障诊断手册（动力系统/充电/制动/电气/灯光/智驾故障排查）；(3) 保养维护手册（保养周期、易损件更换、季节性保养）；(4) 售后政策手册（质保、救援、保养套餐、退换车政策）；(5) 高德地图Skill文档（JSAPI v2.0 安全配置/视图控制/覆盖物/图层/路径规划/POI搜索/热力图、Web Service LBS服务能力、Cursor/Claude/Cline AI IDE集成方式）。入参为query检索词（如「空调不制冷」「高德安全密钥怎么配置」「驾车路径规划策略」），返回专业资料摘要字符串。")
def rag_summarize(query: str) -> str:
    """
    从车载知识库中检索与查询相关的文档，进行摘要总结。
    适用于：车辆功能使用方法、故障诊断建议、保养维护知识、售后政策咨询、高德API/平台使用问题等需要专业知识的问题。
    """
    rag = _get_rag_service()
    return rag.rag_summarize(query)


def get_rag_tool():
    """获取RAG工具"""
    return rag_summarize


if __name__ == "__main__":
    print(rag_summarize.invoke({"query": "空调不制冷怎么办"}))
