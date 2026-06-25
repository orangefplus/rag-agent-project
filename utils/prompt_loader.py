import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_agent_project.utils.config_handler import prompts_config
from rag_agent_project.utils.path_tool import get_abs_path
from rag_agent_project.utils.logger_handler import logger



def load_system_prompt()->str:
    try:
        system_prompt_path=get_abs_path(prompts_config["main_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompt] yaml配置文件中缺少键值对：{str(e)}")
        raise e
    try:
        return open(system_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompt] 读取文件失败：{str(e)}")
        raise e

def load_rag_summarize_prompt()->str:
    try:
        rag_summarize_prompt_path=get_abs_path(prompts_config["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_summarize_prompt] yaml配置文件中缺少键值对：{str(e)}")
        raise e
    try:
        return open(rag_summarize_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_summarize_prompt] 读取文件失败：{str(e)}")
        raise e

def load_report_prompt()->str:
    try:
        report_prompt_path=get_abs_path(prompts_config["report_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_report_prompt] yaml配置文件中缺少键值对：{str(e)}")
        raise e
    try:
        return open(report_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompt] 读取文件失败：{str(e)}")    
        raise e


if __name__ == "__main__":
    system_prompt=load_system_prompt()
    print(system_prompt)