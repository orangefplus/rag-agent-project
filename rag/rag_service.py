"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料总结成一个字符串提交给模型
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rag_agent_project.rag.vector_store import VectorStoreService
from rag_agent_project.utils.prompt_loader import load_rag_summarize_prompt
from langchain_core.prompts import PromptTemplate
from rag_agent_project.model.factory import chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

def print_prompt_text(prompt):
    """
    打印提示文本
    """
    print("*"*50)
    print(prompt.to_string())
    print("*"*50)
    return prompt

class RagSummaryService(object):
    def __init__(self):
        self.vector_store=VectorStoreService()
        self.retriever=self.vector_store.get_retriever()
        self.prompt_text=load_rag_summarize_prompt()
        self.prompt_template=PromptTemplate.from_template(self.prompt_text)
        self.model=chat_model
        self.chain=self.__get_chain()
    
    def __get_chain(self):
        chain=self.prompt_template | print_prompt_text | self.model | StrOutputParser()
        return chain
    def retriver_docs(self,question)->list[Document]:
        return self.retriever.invoke(question)

    def rag_summarize(self,question)->str:
        context_docs=self.retriver_docs(question)
        context=""
        count=0
        for doc in context_docs:
            count+=1
            context+=f"[参考资料{count}]：参考资料{doc.page_content} 参考元数据：{doc.metadata}\n"
        return self.chain.invoke(
            {
                "input":question,
                "context":context
            }
        )

if __name__=="__main__":
    rag_service=RagSummaryService()
    print(rag_service.rag_summarize("空调不制冷怎么排查"))

