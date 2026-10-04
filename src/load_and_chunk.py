from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_and_chunk(pdf_path):
    # Load the PDF
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    chunks = splitter.split_documents(documents)

    return chunks

if __name__ == "__main__":
    pdf_path = "data/dbms_sample_notes.pdf"
    chunks = load_and_chunk(pdf_path)

    print(f"Total chunks created: {len(chunks)}")
    print("\n--- First chunk preview ---")
    print(chunks[0].page_content)
    print("\n--- Second chunk preview ---")
    print(chunks[1].page_content)