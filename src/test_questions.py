from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)

def show(title, results):
    print(f"\n=== {title} ===")
    for d in results:
        m = d.metadata
        print(f"- {m.get('source_type')} | {m.get('source_file')} | "
              f"year={m.get('year')} q={m.get('question_no')} marks={m.get('marks')}")
        print(f"    {d.page_content[:80]}...")

q = "Differentiate between weak AI and strong AI"
show("Only question papers", store.similarity_search(q, k=3, filter={"source_type": "question_paper"}))
show("Only notes", store.similarity_search(q, k=3, filter={"source_type": "notes"}))
show("Only the 2022 paper", store.similarity_search("machine learning", k=3, filter={"year": 2022}))
show("Textbook and lab manual", store.similarity_search("linear regression", k=4, filter={"source_type": "textbook"}))