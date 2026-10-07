from load_and_chunk import load_and_chunk_multiple
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def build_index(file_configs, save_path="faiss_index"):
    chunks = load_and_chunk_multiple(file_configs)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(save_path)
    print(f"Index saved to {save_path} ({len(chunks)} chunks)")

    return vectorstore

if __name__ == "__main__":
    file_configs = [
        {"path": "data/dbms_sample_notes.pdf", "source_type": "notes"},
    ]
    build_index(file_configs)