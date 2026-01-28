import os
import json
import numpy as np
from openai import OpenAI
from config import CONFIG

client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])

INDEX_FILE = "knowledge_base.json"

class SimpleVectorStore:
    def __init__(self):
        self.documents = []
        self.embeddings = []
        self.load()

    def add_documents(self, docs):
        # docs is a list of {"content": str, "metadata": dict}
        for doc in docs:
            response = client.embeddings.create(
                input=doc["content"],
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            self.documents.append(doc)
            self.embeddings.append(embedding)
        self.save()

    def save(self):
        data = {
            "documents": self.documents,
            "embeddings": self.embeddings
        }
        with open(INDEX_FILE, "w") as f:
            json.dump(data, f)

    def load(self):
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "r") as f:
                data = json.load(f)
                self.documents = data["documents"]
                self.embeddings = data["embeddings"]

    def search(self, query, k=5):
        if not self.embeddings:
            return []
        
        query_resp = client.embeddings.create(
            input=query,
            model="text-embedding-3-small"
        )
        query_emb = np.array(query_resp.data[0].embedding)
        
        scores = []
        for emb in self.embeddings:
            dist = np.dot(query_emb, np.array(emb))
            scores.append(dist)
        
        indices = np.argsort(scores)[-k:][::-1]
        return [self.documents[i] for i in indices]

vector_store = SimpleVectorStore()

def query_knowledge_base(query, context_type=None):
    results = vector_store.search(query)
    if context_type:
        results = [r for r in results if r["metadata"].get("type") == context_type]
    
    context_text = "\n---\n".join([r["content"] for r in results])
    
    prompt = f"""You are an expert personal assistant. Use the following context from the user's Google Workspace to answer the query.    
    Context:
    {context_text}
    
    Query: {query}
    
    Answer the query agentically, suggesting next steps if appropriate."""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048
    )
    return response.choices[0].message.content
