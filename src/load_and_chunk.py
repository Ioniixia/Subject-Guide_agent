import os
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pptx import Presentation


def load_pptx(file_path):
    """Read a PowerPoint file: one Document per slide, with the slide number."""
    prs = Presentation(file_path)
    docs = []
    for number, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
        slide_text = "\n".join(t for t in texts if t.strip())
        if slide_text.strip():
            docs.append(
                Document(
                    page_content=slide_text,
                    metadata={"source": file_path, "slide": number},
                )
            )
    return docs


def load_single_file(file_path, source_type="notes", subject="DBMS", chapter="General"):
    """Load one file (PDF, DOCX or PPTX) and tag it with metadata."""
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        documents = PyPDFLoader(file_path).load()
    elif lower.endswith(".docx"):
        documents = Docx2txtLoader(file_path).load()
    elif lower.endswith(".pptx"):
        documents = load_pptx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    for doc in documents:
        doc.metadata["source_type"] = source_type
        doc.metadata["source_file"] = os.path.basename(file_path)
        doc.metadata["subject"] = subject
        doc.metadata["chapter"] = chapter

    return documents


def load_and_chunk_multiple(file_configs):
    """
    file_configs: list of dicts like
      [{"path": "data/unit1.pptx", "source_type": "notes",
        "subject": "AIML", "chapter": "Intro to ML"}]
    """
    all_documents = []
    for config in file_configs:
        docs = load_single_file(
            config["path"],
            config["source_type"],
            config.get("subject", "DBMS"),
            config.get("chapter", "General"),
        )
        all_documents.extend(docs)

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    return splitter.split_documents(all_documents)


# Keep the old single-file function for backward compatibility
def load_and_chunk(pdf_path):
    return load_and_chunk_multiple([{"path": pdf_path, "source_type": "notes"}])