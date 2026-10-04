from load_and_chunk import load_and_chunk
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def build_index(pdf_path, save_path="faiss_index"):
    # Load and chunk the PDF
    chunks = load_and_chunk(pdf_path)

    # Set up the embedding model (free, runs locally)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Build the FAISS index from chunks
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # Save it to disk
    vectorstore.save_local(save_path)
    print(f"Index saved to {save_path}")

    return vectorstore

if __name__ == "__main__":
    pdf_path = "data/dbms_sample_notes.pdf"
    build_index(pdf_path)