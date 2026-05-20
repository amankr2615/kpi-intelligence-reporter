import math
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Lightweight in-memory document store
INDUSTRY_BENCHMARKS = [
    {
        "id": "b1",
        "category": "E-Commerce",
        "text": "E-Commerce Industry Benchmark: Average Customer Acquisition Cost (CAC) is $45 to $80. Average Conversion Rate is 2.5% to 3.5%."
    },
    {
        "id": "b2",
        "category": "SaaS",
        "text": "SaaS Industry Benchmark: Average Customer Acquisition Cost (CAC) is $150 to $300. Average monthly churn rate is 3% to 5%."
    },
    {
        "id": "b3",
        "category": "Marketing Ads",
        "text": "Digital Marketing Benchmark: Average Return on Ad Spend (ROAS) across major platforms (Google/Meta) is 2.8x. A ROAS below 2.0 is considered underperforming."
    },
    {
        "id": "b4",
        "category": "Hardware & Consumer Tech",
        "text": "Hardware/Product Benchmark: Average gross margin is 35% to 50%. Unit sales growth week-over-week (WoW) averages 4% during non-holiday periods."
    }
]

class LightweightRAG:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Delay client initialization until actually needed
        self.client = None
        self.document_embeddings = []

    def _init_client(self):
        if self.client is None and self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def _cosine_similarity(self, v1, v2):
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude_v1 = math.sqrt(sum(a * a for a in v1))
        magnitude_v2 = math.sqrt(sum(b * b for b in v2))
        if magnitude_v1 == 0 or magnitude_v2 == 0:
            return 0.0
        return dot_product / (magnitude_v1 * magnitude_v2)

    def _get_embedding(self, text: str) -> list[float]:
        self._init_client()
        if not self.client:
            return []
            
        try:
            response = self.client.models.embed_content(
                model='gemini-embedding-001',
                contents=text
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []

    def initialize_knowledge_base(self):
        """Pre-computes embeddings for the static knowledge base. Run once on startup."""
        logger.info("Initializing RAG Vector Embeddings...")
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
             logger.warning("Skipping RAG initialization: Invalid API Key")
             return
             
        for doc in INDUSTRY_BENCHMARKS:
            emb = self._get_embedding(doc["text"])
            if emb:
                self.document_embeddings.append({
                    "doc": doc,
                    "vector": emb
                })
        logger.info(f"Loaded {len(self.document_embeddings)} benchmarks into Vector Store.")

    def retrieve_context(self, query: str, top_k: int = 2) -> str:
        """Retrieves the most relevant benchmarks for a given query."""
        if not self.document_embeddings:
            return ""

        query_embedding = self._get_embedding(query)
        if not query_embedding:
            return ""

        # Score all documents
        scored_docs = []
        for item in self.document_embeddings:
            score = self._cosine_similarity(query_embedding, item["vector"])
            scored_docs.append((score, item["doc"]["text"]))

        # Sort by highest score first
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Format the top K results
        top_results = [doc_text for score, doc_text in scored_docs[:top_k] if score > 0.5]
        
        if not top_results:
            return ""
            
        return "\n".join(top_results)

# Global RAG instance will be imported by server.py
rag_engine = None

def init_rag(api_key: str):
    global rag_engine
    rag_engine = LightweightRAG(api_key)
    # Fire and forget initialization to prevent blocking startup
    import threading
    threading.Thread(target=rag_engine.initialize_knowledge_base, daemon=True).start()

def get_rag_context(query: str) -> str:
    if rag_engine:
        return rag_engine.retrieve_context(query)
    return ""
