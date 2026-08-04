from src.data_loader import (
    build_books_by_title,
    load_books,
    normalize_text,
)

BOOKS = load_books()

#Building the title index once so repeated searches stay fast
BOOKS_BY_TITLE = build_books_by_title(BOOKS)


def get_summary_by_title(title: str) -> str:

    #Return the full summary for an exact book title
    if not isinstance(title, str):
        raise TypeError("The title must be a string.")

    normalized_title = normalize_text(title)

    if not normalized_title:
        return "No title was provided."

    #Looking for the title
    book = BOOKS_BY_TITLE.get(normalized_title)

    if book is None:
        return f'No summary was found for "{title.strip()}".'

    return book["description"]


if __name__ == "__main__":
    #Run a small local check before connecting this function to OpenAI
    test_title = "Pride and Prejudice"
    summary = get_summary_by_title(test_title)

    print(f"Title: {test_title}")
    print(f"Summary: {summary}")