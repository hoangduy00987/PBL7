
from langchain.schema import Document
from typing import List
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class BGEHFReranker:
    def __init__(self, top_k: int = 10):
        self.top_k = top_k
        self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-base")
        self.model = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-base")

    def compress_documents(self, documents: List[Document], query: str) -> List[Document]:
        texts = [doc.page_content for doc in documents]
        pairs = [(query, text) for text in texts]
        inputs = self.tokenizer.batch_encode_plus(pairs, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            scores = self.model(**inputs).logits.squeeze(-1)
        top_indices = torch.topk(scores, self.top_k).indices
        return [documents[i] for i in top_indices]
