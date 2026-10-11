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
            slide = doc.metadata.get("slide")
            print(f"- {doc.metadata.get('chapter')} | slide {slide}")
            print(f"    {doc.page_content[:90].replace(chr(10), ' ')}...")

    show("What is supervised learning?",
         search_index("What is supervised learning?"))

    show("What is TensorFlow used for?",
         search_index("What is TensorFlow used for?"))

    show("What is a decision tree?",
         search_index("What is a decision tree?"))

    show("Same question, filtered to Unit 1 only",
         search_index("What is a decision tree?", chapter="Unit 1 - Introduction to AI"))