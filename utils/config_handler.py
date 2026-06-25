"""配置文件处理工具"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from rag_agent_project.utils.path_tool import get_abs_path

def load_rag_config(config_path:str=get_abs_path("config/rag.yml"),encoding:str="utf-8"):
    try:
        with open(config_path, "r", encoding=encoding) as f:
            content = yaml.safe_load(f)
            return content if content is not None else {}
    except FileNotFoundError:
        print(f"配置文件未找到: {config_path}")
        return {}
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}
def load_chroma_config(config_path:str=get_abs_path("config/chroma.yml"),encoding:str="utf-8"):
    try:
        with open(config_path, "r", encoding=encoding) as f:
            content = yaml.safe_load(f)
            return content if content is not None else {}
    except FileNotFoundError:
        print(f"配置文件未找到: {config_path}")
        return {}
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}
def load_prompts_config(config_path:str=get_abs_path("config/prompts.yml"),encoding:str="utf-8"):
    try:
        with open(config_path, "r", encoding=encoding) as f:
            content = yaml.safe_load(f)
            return content if content is not None else {}
    except FileNotFoundError:
        print(f"配置文件未找到: {config_path}")
        return {}
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}   
def load_agent_config(config_path:str=get_abs_path("config/agent.yml"),encoding:str="utf-8"):
    try:
        with open(config_path, "r", encoding=encoding) as f:
            content = yaml.safe_load(f)
            return content if content is not None else {}
    except FileNotFoundError:
        print(f"配置文件未找到: {config_path}")
        return {}
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}       

rag_config= load_rag_config()
chroma_config= load_chroma_config()
prompts_config= load_prompts_config()
agent_config= load_agent_config()   

if __name__ == "__main__":
    print(rag_config["chat_model_name"])
