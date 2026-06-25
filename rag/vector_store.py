import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rag_agent_project.utils.logger_handler import logger
from rag_agent_project.utils.file_handler import listdir_with_allowed_type, text_loader,pdf_loader
import os
from typing import List
from rag_agent_project.utils.path_tool import get_abs_path
from langchain_chroma import Chroma
from rag_agent_project.utils.config_handler import chroma_config
from rag_agent_project.model.factory import embedding_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_agent_project.utils.file_handler import get_file_md5_hex
from langchain_core.documents import Document



class VectorStoreService:
    def __init__(self):
        self.vector_store=Chroma(
            collection_name=chroma_config["collection_name"],
            embedding_function=embedding_model,
            persist_directory=get_abs_path(chroma_config["persist_directory"])
        )   
        self.splitter=RecursiveCharacterTextSplitter(
            chunk_size=chroma_config["chunk_size"],
            chunk_overlap=chroma_config["chunk_overlap"],
            separators=chroma_config["separators"],
            length_function=len,
        )
    def get_retriever(self):
        return self.vector_store.as_retriever(search_type="similarity", search_kwargs={"k": chroma_config["k"]})

    def load_documents(self, documents: list[Document]):
        """
        加载文档到向量数据库
        用md5query_id作为文档id
        去重复文档
        """
        def check_md5_hex(md5_for_check: str) -> bool:
            """
            检查md5字符串是否在文件中
            """
            if not os.path.exists(get_abs_path(chroma_config["md5_hex_store"])):
                open(get_abs_path(chroma_config["md5_hex_store"]), "w",encoding="utf-8").close()
                return False
            with open(get_abs_path(chroma_config["md5_hex_store"]), "r",encoding="utf-8") as f:
                for line in f.readlines():
                    line=line.strip()
                    if line==md5_for_check:
                        return True
                return False
        def save_md5_hex(md5_for_save: str) -> None:
            """
            保存md5字符串到文件
            """
            with open(get_abs_path(chroma_config["md5_hex_store"]), "a",encoding="utf-8") as f:
                f.write(md5_for_save+"\n")
        
        def get_file_documents(read_path: str) -> List[Document]:
            """
            从文件中读取文档
            """
            if read_path.endswith(".txt"):
                return text_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)
            return []

        allowed_file_path=listdir_with_allowed_type(
            get_abs_path(chroma_config["data_path"]),
            tuple(chroma_config["allow_knowledge_file_type"])
            )
        for path in allowed_file_path:
            md5_hex=get_file_md5_hex(path)
            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]: {path}已经存在知识库内")
                continue
            try:
                documents:List[Document]=get_file_documents(path)
                if not documents:
                    logger.warning(f"[加载知识库]: {path}内无文档")
                    continue
                split_documents:List[Document]=self.splitter.split_documents(documents)
                if not split_documents:
                    logger.warning(f"[加载知识库]: {path}分片后无文档")
                    continue
                self.vector_store.add_documents(split_documents)#添加文档到向量数据库
                save_md5_hex(md5_hex)#保存md5字符串到文件
                logger.info(f"[加载知识库]: {path}加载完成")
            except Exception as e:
                logger.error(f"[加载知识库]: {path}加载失败: {str(e)}",exc_info=True)
                continue

if __name__ == "__main__":
    vector_store_service=VectorStoreService()
    vector_store_service.load_documents([])
    retriever=vector_store_service.get_retriever()
    res=retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-"*50)




