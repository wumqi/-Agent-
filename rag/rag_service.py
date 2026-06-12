"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from utils.cache_handler import redis_cache
from utils.logger_handler import logger


class RagSummarizeService(object):
    CACHE_PREFIX = "rag_summarize"
    RETRIEVE_CACHE_PREFIX = "rag_retrieve"
    
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        # 尝试从缓存获取检索结果
        cached_docs = redis_cache.get(self.RETRIEVE_CACHE_PREFIX, query)
        if cached_docs:
            logger.info(f"检索命中缓存: {query[:30]}...")
            return self._cache_format_to_docs(cached_docs)
        
        # 缓存未命中，执行检索
        docs = self.retriever.invoke(query)
        
        # 缓存检索结果
        redis_cache.set(self.RETRIEVE_CACHE_PREFIX, query, self._docs_to_cache_format(docs))
        
        return docs

    def _docs_to_cache_format(self, docs: list[Document]) -> list[dict]:
        """将文档列表转换为可缓存的格式"""
        return [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in docs
        ]

    def _cache_format_to_docs(self, cached_data: list[dict]) -> list[Document]:
        """将缓存格式转换为文档列表"""
        return [
            Document(page_content=item["page_content"], metadata=item["metadata"])
            for item in cached_data
        ]

    def rag_summarize(self, query: str) -> str:
        # 尝试从缓存获取结果
        cached_result = redis_cache.get(self.CACHE_PREFIX, query)
        if cached_result:
            logger.info(f"命中缓存: {query[:30]}...")
            return cached_result
        
        try:
            content_docs = self.retriever_docs(query)

            context = ""
            counter = 0
            for doc in content_docs:
                counter += 1
                context += f"[参考资料{counter}]:参考资料：{doc.page_content}|参考元数据：{doc.metadata}\n"

            result = self.chain.invoke(
                {
                    "input": query,
                    "context": context,
                }
            )
            
            # 将结果存入缓存
            redis_cache.set(self.CACHE_PREFIX, query, result)
            logger.info(f"缓存已设置: {query[:30]}...")
            
            return result
        except Exception as e:
            logger.error(f"RAG总结失败: {str(e)}")
            return "检索和总结过程中出现错误，请稍后重试"


if __name__ == '__main__':
    rag = RagSummarizeService()
    print(rag.rag_summarize("员工报销流程"))