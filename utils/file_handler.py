import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import hashlib
from rag_agent_project.utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

def get_file_md5_hex(filepath:str):
    if not os.path.exists(filepath):
        logger.error(f"[md5计算失败]: {filepath}不存在")
        return None
    if not os.path.isfile(filepath):
        logger.error(f"[md5计算失败]: {filepath}不是文件")
        return None
    md5_obj=hashlib.md5()
    chunk_size=4096 # 4KB
    try:
        with open(filepath, "rb") as f:
            while chunk:=f.read(chunk_size):
                md5_obj.update(chunk)
        md5_hex=md5_obj.hexdigest()
        return md5_hex
    except Exception as e:
        logger.error(f"[md5计算失败]: {filepath} {str(e)}")
        return None

def listdir_with_allowed_type(path:str,allowed_types:tuple[str]):
    files=[]
    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]: {path}不是目录")
        return files
    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path, f))
    return tuple(files)


def pdf_loader(filepath:str,password=None)->list[Document]:
    return PyPDFLoader(filepath,password=password).load()
    

def text_loader(filepath:str)->list[Document]:
    return TextLoader(filepath,encoding="utf-8").load()
