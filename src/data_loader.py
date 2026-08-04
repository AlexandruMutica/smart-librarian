import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOOKS_FILE_PATH = PROJECT_ROOT / "data" / "books.json"

REQUIRED_FIELDS = {
    "title",
    "author",
    "description",
}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def validate_book(book: Any, index: int) -> dict[str, str]:

    #Validate one book and return its cleaned values.
    #We expect every item from the JSON file to be an object.
    if not isinstance(book, dict):
        raise ValueError(
            f"Book at index {index} must be a JSON object."
        )

    #checking that every required field is available.
    missing_fields = REQUIRED_FIELDS - book.keys()

    if missing_fields:
        missing_fields_text = ", ".join(sorted(missing_fields))

        raise ValueError(
            f"Book at index {index} is missing the following fields: "
            f"{missing_fields_text}."
        )

    cleaned_book: dict[str, str] = {}

    #We clean and validate each value before using it.
    for field in REQUIRED_FIELDS:
        value = book[field]

        if not isinstance(value, str):
            raise ValueError(
                f"Field '{field}' from book at index {index} "
                "must be a string."
            )

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError(
                f"Field '{field}' from book at index {index} "
                "cannot be empty."
            )

        cleaned_book[field] = cleaned_value

    return cleaned_book


def remove_duplicate_books(
    books: list[dict[str, str]],
) -> list[dict[str, str]]:

    #Remove duplicate books based on title and author
    unique_books: list[dict[str, str]] = []
    seen_books: set[tuple[str, str]] = set()

    for book in books:
        #We normalize the title and author before comparing them
        book_key = (
            normalize_text(book["title"]),
            normalize_text(book["author"]),
        )

        #Keeping only the first occurrence of every book.
        if book_key in seen_books:
            continue

        seen_books.add(book_key)
        unique_books.append(book)

    return unique_books


def load_books(
    file_path: Path | str = BOOKS_FILE_PATH,
) -> list[dict[str, str]]:

    #Load, validate and return the books from a JSON file

    path = Path(file_path)

    #We check the path before trying to open the file
    if not path.exists():
        raise FileNotFoundError(
            f"Books file was not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"The provided path is not a file: {path}"
        )

    try:
        # UTF-8 because book descriptions may contain special characters.
        with path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"The books file contains invalid JSON: {error}"
        ) from error

    except OSError as error:
        raise OSError(
            f"The books file could not be read: {error}"
        ) from error

    if not isinstance(raw_data, list):
        raise ValueError(
            "The books JSON file must contain a list."
        )

    validated_books: list[dict[str, str]] = []

    #Validate every book before adding it to the final list.
    for index, raw_book in enumerate(raw_data):
        validated_book = validate_book(raw_book, index)
        validated_books.append(validated_book)

    #We remove repeated entries before returning the library.
    unique_books = remove_duplicate_books(validated_books)

    return unique_books


def build_books_by_title(
    books: list[dict[str, str]],
) -> dict[str, dict[str, str]]:

    #Build a lookup dictionary using normalized book titles.
    books_by_title: dict[str, dict[str, str]] = {}

    for book in books:
        normalized_title = normalize_text(book["title"])
        books_by_title[normalized_title] = book

    return books_by_title


def get_book_by_title(
    title: str,
    books: list[dict[str, str]],
) -> dict[str, str] | None:

    #Return a book that matches the given title
    if not isinstance(title, str):
        raise TypeError("The title must be a string.")

    #We normalize the received title before searching for it.
    normalized_title = normalize_text(title)

    if not normalized_title:
        return None

    #building a lookup dictionary for a direct title search.
    books_by_title = build_books_by_title(books)

    return books_by_title.get(normalized_title)


if __name__ == "__main__":
    try:
        loaded_books = load_books()

        print(f"Loaded {len(loaded_books)} valid books.")

        first_book = loaded_books[0]

        print("\nFirst book:")
        print(f"Title: {first_book['title']}")
        print(f"Author: {first_book['author']}")
        print(f"Description: {first_book['description'][:200]}...")

    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Error: {error}")