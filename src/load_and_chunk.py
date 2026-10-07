import os
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_single_file(file_path, source_type="notes"):
    """Load one file (PDF or DOCX) and tag it with a source_type."""
    if file_path.lower().endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    elif file_path.lower().endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    documents = loader.load()

    # Tag each document with metadata: source_type + filename
    for doc in documents:
        doc.metadata["source_type"] = source_type
        doc.metadata["source_file"] = os.path.basename(file_path)

    return documents

def load_and_chunk_multiple(file_configs):
    """
    file_configs: list of dicts like
      [{"path": "data/dbms_notes.pdf", "source_type": "notes"},
       {"path": "data/dbms_paper_2023.pdf", "source_type": "question_paper"}]
    """
    all_documents = []
    for config in file_configs:
        docs = load_single_file(config["path"], config["source_type"])
        all_documents.extend(docs)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    chunks = splitter.split_documents(all_documents)
    return chunks

# Keep the old single-file function for backward compatibility
def load_and_chunk(pdf_path):
    return load_and_chunk_multiple([{"path": pdf_path, "source_type": "notes"}])

if __name__ == "__main__":
    file_configs = [
        {"path": "data/dbms_sample_notes.pdf", "source_type": "notes"},
    ]
    chunks = load_and_chunk_multiple(file_configs)

    print(f"Total chunks created: {len(chunks)}")
    print("\n--- First chunk preview ---")
    print(chunks[0].page_content)
    print(f"Metadata: {chunks[0].metadata}")