from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def search_index(question, k=3, index_path="faiss_index", subject=None, chapter=None):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)

    # Only filter on the fields that were given
    filters = {}
    if subject:
        filters["subject"] = subject
    if chapter:
        filters["chapter"] = chapter

    results = vectorstore.similarity_search(question, k=k, filter=filters or None)
    return results

if __name__ == "__main__":
    question = "What is the difference between 2NF and 3NF?"

    print("=== No filter ===")
    for doc in search_index(question):
        print(f"- {doc.metadata.get('source_file')} | {doc.metadata.get('subject')} | {doc.metadata.get('chapter')}")

    print("\n=== Filter: chapter = Normalization ===")
    for doc in search_index(question, chapter="Normalization"):
        print(f"- {doc.metadata.get('source_file')} | {doc.metadata.get('subject')} | {doc.metadata.get('chapter')}")

    print("\n=== Filter: chapter = Transactions (should return nothing) ===")
    results = search_index(question, chapter="Transactions")
    print(f"Results found: {len(results)}")