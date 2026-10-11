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
    def show(title, results):
        print(f"\n=== {title} ===")
        for doc in results:
            print(f"- {doc.metadata.get('source_file')} | {doc.metadata.get('chapter')}")

    q1 = "What are the ACID properties?"
    show("ACID question, no filter", search_index(q1))
    show("ACID question, chapter = Normalization", search_index(q1, chapter="Normalization"))

    q2 = "What is the difference between 2NF and 3NF?"
    show("2NF question, no filter", search_index(q2))
    show("2NF question, chapter = Transactions", search_index(q2, chapter="Transactions"))