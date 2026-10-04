from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def search_index(question, k=3, index_path="faiss_index"):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)

    results = vectorstore.similarity_search(question, k=k)
    return [doc.page_content for doc in results]

if __name__ == "__main__":
    question = "What is the difference between 2NF and 3NF?"
    results = search_index(question)

    print(f"Question: {question}\n")
    for i, chunk in enumerate(results):
        print(f"--- Result {i+1} ---")
        print(chunk)
        print()