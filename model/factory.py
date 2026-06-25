import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abc import ABC, abstractmethod
from typing import Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from rag_agent_project.utils.config_handler import rag_config
import openai
from langchain_core.embeddings import Embeddings
import os


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self)->Optional[Embeddings|BaseChatModel]:
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self)->Optional[Embeddings|BaseChatModel]:
        return ChatOpenAI(
            model=rag_config["chat_model_name"],
            api_key=rag_config.get("xf_api_key"),
            base_url=rag_config["xf_chat_base_url"],
            streaming=True,
        )

class XFYunEmbeddings(Embeddings):
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=os.environ.get("XF_API_KEY") or rag_config.get("xf_api_key"),
            base_url=rag_config["xf_embedding_base_url"]
        )
        self.model = rag_config["embedding_model_name"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        response = self.client.embeddings.create(model=self.model, input=[text])
        return response.data[0].embedding

class EmbeddingFactory(BaseModelFactory):
    def generator(self)->Optional[Embeddings|BaseChatModel]:
        return XFYunEmbeddings()

chat_model=ChatModelFactory().generator()
embedding_model=EmbeddingFactory().generator()
