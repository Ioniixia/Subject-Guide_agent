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
        {
            "path": "data/unit1_intro_ai.pptx",
            "source_type": "notes",
            "subject": "AIML",
            "chapter": "Unit 1 - Introduction to AI",
        },
        {
            "path": "data/unit2_ai_frameworks.pptx",
            "source_type": "notes",
            "subject": "AIML",
            "chapter": "Unit 2 - AI Technologies and Frameworks",
        },
        {
            "path": "data/unit3_ml_basics.pptx",
            "source_type": "notes",
            "subject": "AIML",
            "chapter": "Unit 3 - Machine Learning Basics",
        },
    ]
    build_index(file_configs)