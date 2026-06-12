import os
import re

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.logger_handler import logger
from utils.config_handler import chroma_conf
from utils.file_handler import (
    txt_loader,
    pdf_loader,
    listdir_with_allowed_type,
    get_file_md5_hex,
)
from utils.path_tool import get_abs_path
from model.factory import embed_model


class DocumentPreprocessor:
    """文档预处理"""

    @staticmethod
    def clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        text = re.sub(
            r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""''（）《》【】\s]",
            "",
            text,
        )

        return text

    @staticmethod
    def remove_duplicate_paragraphs(text: str) -> str:
        paragraphs = text.split("\n")

        seen = set()
        unique_paragraphs = []

        for p in paragraphs:
            p_clean = p.strip()

            if p_clean and p_clean not in seen:
                seen.add(p_clean)
                unique_paragraphs.append(p)

        return "\n".join(unique_paragraphs)

    @staticmethod
    def truncate_long_sentences(text: str, max_length: int = 500) -> str:
        sentences = re.split(r"([。！？])", text)

        result = []

        for i in range(0, len(sentences), 2):
            sentence = (
                sentences[i]
                + (sentences[i + 1] if i + 1 < len(sentences) else "")
            )

            if len(sentence) > max_length:
                sentence = sentence[:max_length] + "..."

            result.append(sentence)

        return "".join(result)

    @staticmethod
    def preprocess(text: str) -> str:
        text = DocumentPreprocessor.clean_text(text)
        text = DocumentPreprocessor.remove_duplicate_paragraphs(text)
        text = DocumentPreprocessor.truncate_long_sentences(text)

        return text


class VectorStoreService:

    def __init__(self):

        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"],
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

        self.bm25_retriever = None
        self.ensemble_retriever = None

    # =========================
    # md5工具
    # =========================

    @staticmethod
    def check_md5_hex(md5_for_check: str):

        md5_store_path = get_abs_path(chroma_conf["md5_hex_store"])

        if not os.path.exists(md5_store_path):
            open(md5_store_path, "w", encoding="utf-8").close()
            return False

        with open(md5_store_path, "r", encoding="utf-8") as f:
            for line in f.readlines():

                line = line.strip()

                if line == md5_for_check:
                    return True

        return False

    @staticmethod
    def save_md5_hex(md5_for_check: str):

        md5_store_path = get_abs_path(chroma_conf["md5_hex_store"])

        with open(md5_store_path, "a", encoding="utf-8") as f:
            f.write(md5_for_check + "\n")

    # =========================
    # 文档读取
    # =========================

    def get_file_documents(self, read_path: str):

        try:

            if read_path.endswith("txt"):
                docs = txt_loader(read_path)

            elif read_path.endswith("pdf"):
                docs = pdf_loader(read_path)

            else:
                return []

            processed_docs = []

            for doc in docs:

                if not doc.page_content:
                    continue

                cleaned_content = DocumentPreprocessor.preprocess(
                    doc.page_content
                )

                if cleaned_content.strip():

                    processed_doc = Document(
                        page_content=cleaned_content,
                        metadata=doc.metadata if doc.metadata else {},
                    )

                    processed_docs.append(processed_doc)

            return processed_docs

        except Exception as e:

            logger.error(f"读取文件失败: {read_path}, {str(e)}", exc_info=True)

            return []

    # =========================
    # 构建BM25
    # =========================

    def _build_bm25_retriever(self):

        try:

            all_docs = self.vector_store.get()

            if not all_docs:
                logger.warning("Chroma中没有数据")
                return

            raw_documents = all_docs.get("documents", [])
            raw_metadatas = all_docs.get("metadatas", [])

            if not raw_documents:
                logger.warning("documents为空，无法构建BM25")
                return

            documents = []

            for i, doc_text in enumerate(raw_documents):

                if not doc_text:
                    continue

                metadata = {}

                if i < len(raw_metadatas):
                    metadata = raw_metadatas[i] or {}

                documents.append(
                    Document(
                        page_content=doc_text,
                        metadata=metadata,
                    )
                )

            if not documents:
                logger.warning("有效documents为空")
                return

            self.bm25_retriever = BM25Retriever.from_documents(
                documents
            )

            self.bm25_retriever.k = chroma_conf["k"]

            logger.info(
                f"BM25检索器构建成功，共{len(documents)}条文档"
            )

        except Exception as e:

            logger.error(
                f"构建BM25检索器失败: {str(e)}",
                exc_info=True,
            )

    # =========================
    # 获取检索器
    # =========================

    def get_retriever(self, retriever_type: str = None):
        # 从配置获取检索器类型，默认使用向量检索
        if retriever_type is None:
            retriever_type = chroma_conf.get("retriever_type", "vector")

        vector_retriever = self.vector_store.as_retriever(
            search_kwargs={"k": chroma_conf["k"]}
        )

        if retriever_type == "vector":
            return vector_retriever

        elif retriever_type == "bm25":

            if not self.bm25_retriever:
                self._build_bm25_retriever()

            return self.bm25_retriever

        elif retriever_type == "hybrid":

            if not self.bm25_retriever:
                self._build_bm25_retriever()

            if self.bm25_retriever:

                self.ensemble_retriever = EnsembleRetriever(
                    retrievers=[
                        vector_retriever,
                        self.bm25_retriever,
                    ],
                    weights=[0.6, 0.4],
                )

                return self.ensemble_retriever

            else:

                logger.warning(
                    "BM25不可用，自动降级为向量检索"
                )

                return vector_retriever

        return vector_retriever

    # =========================
    # 加载知识库
    # =========================

    def load_document(self):

        allowed_files_path = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        logger.info(
            f"发现{len(allowed_files_path)}个知识文件"
        )

        for path in allowed_files_path:

            try:

                md5_hex = get_file_md5_hex(path)

                if self.check_md5_hex(md5_hex):

                    logger.info(
                        f"[加载知识库]{path}已存在，跳过"
                    )

                    continue

                documents = self.get_file_documents(path)

                if not documents:

                    logger.warning(
                        f"[加载知识库]{path}无有效内容"
                    )

                    continue

                split_documents = self.spliter.split_documents(
                    documents
                )

                if not split_documents:

                    logger.warning(
                        f"[加载知识库]{path}切分失败"
                    )

                    continue

                source_name = os.path.basename(path)

                for idx, doc in enumerate(split_documents):

                    doc.metadata["source"] = source_name
                    doc.metadata["chunk_index"] = idx

                self.vector_store.add_documents(
                    split_documents
                )

                self.save_md5_hex(md5_hex)

                logger.info(
                    f"[加载知识库]{path}成功，"
                    f"共{len(split_documents)}个chunk"
                )

            except Exception as e:

                logger.error(
                    f"[加载知识库]{path}失败: {str(e)}",
                    exc_info=True,
                )

    # =========================
    # 更新文档
    # =========================

    def update_document(self, file_path: str):

        try:

            md5_hex = get_file_md5_hex(file_path)

            md5_store_path = get_abs_path(
                chroma_conf["md5_hex_store"]
            )

            if os.path.exists(md5_store_path):

                with open(
                    md5_store_path,
                    "r",
                    encoding="utf-8",
                ) as f:

                    lines = f.readlines()

                with open(
                    md5_store_path,
                    "w",
                    encoding="utf-8",
                ) as f:

                    for line in lines:

                        if line.strip() != md5_hex:
                            f.write(line)

            source_name = os.path.basename(file_path)

            all_docs = self.vector_store.get(
                where={"source": source_name}
            )

            if all_docs.get("ids"):

                self.vector_store.delete(
                    ids=all_docs["ids"]
                )

                logger.info(
                    f"删除旧文档成功: {source_name}"
                )

            documents = self.get_file_documents(
                file_path
            )

            if not documents:
                return False

            split_documents = self.spliter.split_documents(
                documents
            )

            for idx, doc in enumerate(split_documents):

                doc.metadata["source"] = source_name
                doc.metadata["chunk_index"] = idx

            self.vector_store.add_documents(
                split_documents
            )

            self.save_md5_hex(md5_hex)

            logger.info(
                f"[更新知识库]{file_path}更新成功"
            )

            return True

        except Exception as e:

            logger.error(
                f"[更新知识库]{file_path}更新失败: {str(e)}",
                exc_info=True,
            )

            return False


if __name__ == "__main__":

    vs = VectorStoreService()

    vs.load_document()

    retriever = vs.get_retriever(
        retriever_type="hybrid"
    )

    if retriever:

        res = retriever.invoke(
            "员工报销流程"
        )

        for r in res:

            print(
                f"来源: {r.metadata.get('source', '未知')}"
            )

            print(r.page_content)

            print("*" * 50)
