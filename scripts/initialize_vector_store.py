import hashlib
from pathlib import Path

import chromadb

from src.data_loader import load_books
from src.openai_client import get_openai_client


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Local Chroma database folder.
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"

COLLECTION_NAME = "books"
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50


# Build the text that will be indexed in ChromaDB.
def build_book_document(book: dict[str, str]) -> str:
    return (
        f"Title: {book['title']}\n"
        f"Author: {book['author']}\n"
        f"Description: {book['description']}"
    )


# Using a hash keeps the same ID every time we rebuild the collection.
def build_book_id(book: dict[str, str]) -> str:
    source = f"{book['title']}|{book['author']}".casefold()
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


# Split the library into smaller batches.
def split_into_batches(
    items: list[dict[str, str]],
    batch_size: int,
) -> list[list[dict[str, str]]]:
    return [
        items[index:index + batch_size]
        for index in range(0, len(items), batch_size)
    ]


# Create embeddings for a batch of books.
def create_embeddings(
    documents: list[str],
) -> list[list[float]]:
    client = get_openai_client()

    # Sending multiple documents in one request is faster.
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=documents,
    )

    # Keep the returned order unchanged.
    return [item.embedding for item in response.data]


# Create or update the local vector store.
def initialize_vector_store() -> None:
    books = load_books()

    chroma_client = chromadb.PersistentClient(
        path=str(CHROMA_DB_PATH),
    )

    # Create the collection if it doesn't exist yet.
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
    )

    batches = split_into_batches(books, BATCH_SIZE)

    print(f"Found {len(books)} books.")
    print(f"Processing {len(batches)} batches.")

    for batch_number, batch in enumerate(batches, start=1):

        # Convert every book into searchable text.
        documents = [
            build_book_document(book)
            for book in batch
        ]

        # Build stable IDs for every document.
        ids = [
            build_book_id(book)
            for book in batch
        ]

        # Store useful information together with every vector.
        metadatas = [
            {
                "title": book["title"],
                "author": book["author"],
            }
            for book in batch
        ]

        print(
            f"Creating embeddings for batch "
            f"{batch_number}/{len(batches)}..."
        )

        embeddings = create_embeddings(documents)

        # Update existing books instead of creating duplicates.
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    print(
        f"Vector store initialized successfully with "
        f"{collection.count()} books."
    )


if __name__ == "__main__":
    try:
        initialize_vector_store()

    except Exception as error:
        print(f"Vector store initialization failed: {error}")