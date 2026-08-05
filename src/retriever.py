from pathlib import Path
from typing import Any

import chromadb

from src.openai_client import get_openai_client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"

COLLECTION_NAME = "books"
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_RESULT_COUNT = 3


# Creating the query embedding with the same model used during indexing.
def create_query_embedding(query: str) -> list[float]:
    client = get_openai_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )

    return response.data[0].embedding


# Opening the existing local collection.
def get_books_collection() -> Any:
    chroma_client = chromadb.PersistentClient(
        path=str(CHROMA_DB_PATH),
    )

    try:
        return chroma_client.get_collection(
            name=COLLECTION_NAME,
        )

    except Exception as error:
        raise RuntimeError(
            "The books collection was not found. "
            "Run the vector store initialization script first."
        ) from error


# Searching for the books that best match the user's request.
def retrieve_books(
    query: str,
    result_count: int = DEFAULT_RESULT_COUNT,
) -> list[dict[str, Any]]:
    if not isinstance(query, str):
        raise TypeError("The query must be a string.")

    cleaned_query = query.strip()

    if not cleaned_query:
        return []

    if result_count < 1:
        raise ValueError("The result count must be greater than zero.")

    collection = get_books_collection()
    query_embedding = create_query_embedding(cleaned_query)

    # Passing the embedding directly keeps OpenAI responsible for embeddings.
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=result_count,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    first_documents = documents[0] or []
    first_metadatas = metadatas[0] or []
    first_distances = distances[0] or []

    retrieved_books: list[dict[str, Any]] = []

    for document, metadata, distance in zip(
        first_documents,
        first_metadatas,
        first_distances,
    ):
        book_metadata = metadata or {}

        retrieved_books.append(
            {
                "title": book_metadata.get(
                    "title",
                    "Unknown title",
                ),
                "author": book_metadata.get(
                    "author",
                    "Unknown author",
                ),
                "document": document or "",
                "distance": distance,
            }
        )

    return retrieved_books


if __name__ == "__main__":
    try:
        test_query = "I want a book about magic and adventure."
        books = retrieve_books(test_query)

        print(f'Query: "{test_query}"')

        if not books:
            print("No books were found.")

        for position, book in enumerate(books, start=1):
            print(f"\nResult {position}")
            print(f"Title: {book['title']}")
            print(f"Author: {book['author']}")
            print(f"Distance: {book['distance']}")
            print(f"Document: {book['document'][:300]}...")

    except (
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(f"Retriever failed: {error}")

    except Exception as error:
        print(f"An unexpected error occurred: {error}")