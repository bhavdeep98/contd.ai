"""
Example 04: RAG (Retrieval-Augmented Generation) Pipeline

A durable RAG workflow that retrieves context from a vector
database and generates responses with an LLM.
"""

from contd.sdk import workflow, step, StepConfig, RetryPolicy


# Simulated vector database
DOCUMENTS = [
    {"id": 1, "text": "Contd.ai provides durable execution for AI workflows.", "embedding": [0.1, 0.2, 0.3]},
    {"id": 2, "text": "Workflows can be paused and resumed automatically.", "embedding": [0.2, 0.3, 0.4]},
    {"id": 3, "text": "Epistemic savepoints capture AI reasoning state.", "embedding": [0.3, 0.4, 0.5]},
    {"id": 4, "text": "Multi-tenancy ensures data isolation between orgs.", "embedding": [0.4, 0.5, 0.6]},
]


def cosine_similarity(a: list, b: list) -> float:
    """Simple cosine similarity."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(x ** 2 for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0


@step()
def embed_query(query: str) -> dict:
    """
    Convert query to embedding vector.
    
    In production, use OpenAI embeddings or similar.
    """
    print(f"Embedding query: {query}")
    # Simulate embedding (in production: call embedding API)
    words = query.lower().split()
    embedding = [0.1 * (i + 1) for i in range(3)]
    return {"query": query, "embedding": embedding}


@step()
def retrieve_documents(query_embedding: list, top_k: int = 3) -> dict:
    """
    Retrieve relevant documents from vector database.
    """
    print(f"Retrieving top {top_k} documents...")
    
    # Calculate similarities
    scored = []
    for doc in DOCUMENTS:
        score = cosine_similarity(query_embedding, doc["embedding"])
        scored.append({"doc": doc, "score": score})
    
    # Sort by score and take top_k
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_docs = scored[:top_k]
    
    return {
        "documents": [s["doc"] for s in top_docs],
        "scores": [s["score"] for s in top_docs]
    }


@step()
def rerank_documents(query: str, documents: list) -> dict:
    """
    Rerank documents for better relevance.
    
    In production, use a cross-encoder model.
    """
    print(f"Reranking {len(documents)} documents...")
    
    # Simple keyword-based reranking (demo)
    query_words = set(query.lower().split())
    
    reranked = []
    for doc in documents:
        doc_words = set(doc["text"].lower().split())
        overlap = len(query_words & doc_words)
        reranked.append({"doc": doc, "relevance": overlap})
    
    reranked.sort(key=lambda x: x["relevance"], reverse=True)
    
    return {"reranked_documents": [r["doc"] for r in reranked]}


@step(StepConfig(
    retry=RetryPolicy(max_attempts=3, backoff_base=2.0)
))
def generate_response(query: str, context_docs: list) -> dict:
    """
    Generate response using LLM with retrieved context.
    
    In production, call OpenAI/Anthropic API.
    """
    print("Generating response with LLM...")
    
    # Build context
    context = "\n".join([doc["text"] for doc in context_docs])
    
    # Simulate LLM response
    response = f"Based on the documentation: {context_docs[0]['text']}"
    
    return {
        "query": query,
        "response": response,
        "sources": [doc["id"] for doc in context_docs]
    }


@step()
def format_output(response: dict) -> dict:
    """Format the final output with citations."""
    print("Formatting output...")
    
    formatted = {
        "answer": response["response"],
        "citations": [f"[{src}]" for src in response["sources"]],
        "confidence": 0.85  # In production, calculate from scores
    }
    
    return formatted


@workflow()
def rag_pipeline(query: str) -> dict:
    """
    Complete RAG pipeline:
    1. Embed the query
    2. Retrieve relevant documents
    3. Rerank for better relevance
    4. Generate response with LLM
    5. Format output with citations
    
    Each step is checkpointed for durability.
    """
    # Step 1: Embed query
    embedded = embed_query(query)
    
    # Step 2: Retrieve documents
    retrieved = retrieve_documents(embedded["embedding"], top_k=3)
    
    # Step 3: Rerank
    reranked = rerank_documents(query, retrieved["documents"])
    
    # Step 4: Generate response
    response = generate_response(query, reranked["reranked_documents"])
    
    # Step 5: Format output
    output = format_output(response)
    
    return output


if __name__ == "__main__":
    result = rag_pipeline("How does Contd.ai handle workflow recovery?")
    print(f"\nRAG Result:")
    print(f"Answer: {result['answer']}")
    print(f"Citations: {result['citations']}")
    print(f"Confidence: {result['confidence']}")
