"""
Run this script once to process your PDF documents and make them searchable.
Usage: python ingest.py
"""
import os
import re
import shutil
from pathlib import Path
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, Settings, StorageContext, Document
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.anthropic import Anthropic
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb
import anthropic as anthropic_sdk
import google.generativeai as genai
import fitz  # PyMuPDF — handles AcadNusx and other legacy Georgian fonts

load_dotenv()


CACHE_DIR = "./cleaned_cache"


def fix_merged_georgian_words(text: str, api_key: str, cache_key: str = "") -> str:
    """Use Gemini Flash to fix merged Georgian words caused by AcadNusx font encoding.
    Caches results to disk — each PDF is only cleaned once, never again."""

    # Check cache first — if already cleaned, load from disk
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, cache_key + ".txt") if cache_key else ""
    if cache_file and os.path.exists(cache_file):
        print("    Using cached cleaned text.")
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    # Check if text has merged words — long Georgian strings without spaces
    merged = re.findall(r'[\u10D0-\u10FF]{15,}', text)
    if not merged:
        return text  # Text looks fine, skip cleaning

    print("    Fixing merged Georgian words with Gemini Flash...")
    gemini_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Process only chunks that have merged words — skip clean chunks
    chunk_size = 4000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    cleaned_chunks = []

    for chunk in chunks:
        # Skip chunks that don't have merged words
        if not re.findall(r'[\u10D0-\u10FF]{15,}', chunk):
            cleaned_chunks.append(chunk)
            continue

        for attempt in range(3):
            try:
                response = model.generate_content(
                    "შემდეგ ქართულ ტექსტს აქვს პრობლემა — სიტყვები ერთმანეთს აქვს შეერთებული, "
                    "დაკარგული სფასებით (მაგ: 'საშუალოინტენსივობის' სინამდვილეში უნდა იყოს "
                    "'საშუალო ინტენსივობის'). გთხოვ, გაასწორო ტექსტი — დაამატე სფასები სიტყვებს შორის "
                    "სადაც საჭიროა. დააბრუნე მხოლოდ გასწორებული ტექსტი, სხვა კომენტარის გარეშე:\n\n"
                    + chunk
                )
                cleaned_chunks.append(response.text)
                break
            except Exception as e:
                print(f"    Attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    print("    Giving up on this chunk — using original text.")
                    cleaned_chunks.append(chunk)

    result = "".join(cleaned_chunks)

    # Save to cache so we never clean this file again
    if cache_file:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(result)
        print("    Saved to cache.")

    return result

DOCS_FOLDER = "./docs"

# Pattern that marks the start of a new zone section in Georgian zoning documents
# Matches all zone codes: სზ-1, სსზ-1, ტზ-1, პზ-1, გზ-1 etc.
ZONE_PATTERN = re.compile(
    r'(?=[\u10D0-\u10FF]{1,4}-\d+)',
    re.UNICODE
)


def extract_text_from_pdf(pdf_path):
    """Extract full text from a PDF using PyMuPDF (handles AcadNusx Georgian font).
    Uses word-by-word extraction to preserve spaces lost in some AcadNusx PDFs."""
    doc = fitz.open(str(pdf_path))
    full_text = ""
    for page in doc:
        # Extract individual words with their positions, then join with spaces
        words = page.get_text("words")
        if words:
            page_text = " ".join(w[4] for w in words)
        else:
            page_text = page.get_text()
        full_text += page_text + "\n"
    doc.close()
    return full_text


def split_into_zone_sections(text, file_name):
    """
    Split document text by zone sections so each zone (სზ-1, სზ-2 etc.)
    becomes one searchable unit — both ა) and ბ) subsections stay together.
    Small focused documents (under 3000 chars) are kept as one unit — no splitting.
    """
    # Small focused documents (like manually created zone sheets) — keep whole
    if len(text) < 8000:
        return [Document(text=text, metadata={"file_name": file_name})]

    sections = ZONE_PATTERN.split(text)
    documents = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Skip very short fragments (page headers, footers, etc.)
        if len(section) < 100:
            continue
        documents.append(Document(
            text=section,
            metadata={"file_name": file_name}
        ))

    # If no zone pattern found, fall back to one document per page chunk
    if not documents:
        documents.append(Document(
            text=text,
            metadata={"file_name": file_name}
        ))

    return documents


def load_and_split_pdfs(docs_path):
    """Load all PDFs and split them into zone-aware sections."""
    documents = []
    pdf_files = list(Path(docs_path).rglob("*.pdf"))

    api_key = os.getenv("ANTHROPIC_API_KEY")
    for pdf_path in pdf_files:
        print(f"  Reading: {pdf_path.name}")
        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            print(f"  WARNING: No text extracted from {pdf_path.name}")
            continue

        # Fix merged words from AcadNusx font before indexing (cached — only runs once per file)
        cache_key = pdf_path.stem.replace(" ", "_")
        text = fix_merged_georgian_words(text, api_key, cache_key)

        sections = split_into_zone_sections(text, pdf_path.name)
        print(f"  Split into {len(sections)} sections.")
        documents.extend(sections)

    return documents


def ingest_documents(docs_path=DOCS_FOLDER):
    if not os.path.exists(docs_path) or not os.listdir(docs_path):
        print(f"ERROR: No documents found in '{docs_path}' folder.")
        print("Please add PDF files to the 'docs' folder and run again.")
        return None

    print(f"Loading documents from '{docs_path}'...")

    embed_model = HuggingFaceEmbedding(
        model_name="intfloat/multilingual-e5-large"
    )
    Settings.embed_model = embed_model
    Settings.llm = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # No chunking — each zone section is already one document
    Settings.chunk_size = 8192

    documents = load_and_split_pdfs(docs_path)
    if not documents:
        print("ERROR: Could not extract text from any PDF.")
        return None
    print(f"Total sections to index: {len(documents)}")

    # Clear old index
    if os.path.exists("./chroma_db"):
        try:
            shutil.rmtree("./chroma_db")
            print("Cleared old index.")
        except PermissionError:
            print("Warning: Could not delete chroma_db (file locked). Wiping collection instead...")
            _client = chromadb.PersistentClient(path="./chroma_db")
            try:
                _client.delete_collection("georgian_regulations")
                print("Collection wiped.")
            except Exception as e:
                print(f"Could not wipe collection: {e}. Proceeding anyway...")

    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = chroma_client.get_or_create_collection("georgian_regulations")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("Creating search index...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    count = chroma_collection.count()
    print(f"\nDone! {count} sections indexed and ready to search.")
    return index


if __name__ == "__main__":
    ingest_documents()
