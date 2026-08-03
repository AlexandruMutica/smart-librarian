import json
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CSV_FILE = PROJECT_ROOT / "good_reads.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "books.json"

import pandas as pd
import requests
from dotenv import load_dotenv

# We define the import settings
MAX_REQUESTS_PER_RUN = 900
MIN_TITLE_SIMILARITY = 0.80
REQUEST_DELAY_SECONDS = 1
REQUEST_TIMEOUT_SECONDS = 30

# We load the environment variables from the .env file
load_dotenv()

API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GOOGLE_BOOKS_API_KEY was not found in the .env file."
    )


# We create the output directory if it does not exist
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_saved_books():
    # We return an empty list if the output file does not exist yet
    if not OUTPUT_FILE.exists():
        return []

    try:
        with OUTPUT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        print(
            "Warning: books.json could not be read. "
            "We start with an empty list."
        )
        return []


def save_books(books):
    # We write to a temporary file first to reduce corruption risk
    temporary_file = OUTPUT_FILE.with_suffix(".json.tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(
            books,
            file,
            ensure_ascii=False,
            indent=2
        )

    temporary_file.replace(OUTPUT_FILE)


def clean_title(value):
    # We convert the value to text
    value = str(value)

    # We remove the first parenthesis and everything after it
    value = re.sub(r"\s*\(.*$", "", value)

    # We replace multiple spaces with a single space
    value = re.sub(r"\s+", " ", value).strip()

    return value


def clean_author(value):
    # We convert the value to text
    value = str(value)

    # We replace multiple spaces with a single space
    value = re.sub(r"\s+", " ", value).strip()

    return value


def normalize_text(value):
    # We convert the value to lowercase text
    value = str(value).casefold()

    # We normalize accented characters
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )

    # We remove the first parenthesis and everything after it
    value = re.sub(r"\s*\(.*$", "", value)

    # We remove punctuation
    value = re.sub(r"[^\w\s]", "", value)

    # We normalize whitespace
    value = re.sub(r"\s+", " ", value).strip()

    return value


def calculate_similarity(first_value, second_value):
    # We calculate a similarity score between 0 and 1
    return SequenceMatcher(
        None,
        normalize_text(first_value),
        normalize_text(second_value)
    ).ratio()


def authors_match(searched_author, result_authors):
    # We normalize the author from the CSV
    expected_author = normalize_text(searched_author)

    # We compare it with every author returned by the API
    for result_author in result_authors:
        normalized_result_author = normalize_text(result_author)

        if (
            expected_author == normalized_result_author
            or expected_author in normalized_result_author
            or normalized_result_author in expected_author
        ):
            return True

    return False


def find_best_book(items, searched_title, searched_author):
    best_item = None
    best_title_similarity = -1
    best_final_score = -1
    best_author_match = False

    # We compare every result returned by the API
    for item in items:
        volume_info = item.get("volumeInfo", {})

        result_title = volume_info.get("title", "")
        result_authors = volume_info.get("authors", [])

        if not result_title:
            continue

        title_similarity = calculate_similarity(
            searched_title,
            result_title
        )

        author_match = authors_match(
            searched_author,
            result_authors
        )

        # We strongly prefer results with a matching author
        author_bonus = 0.25 if author_match else 0
        final_score = title_similarity + author_bonus

        if final_score > best_final_score:
            best_item = item
            best_title_similarity = title_similarity
            best_final_score = final_score
            best_author_match = author_match

    return (
        best_item,
        best_title_similarity,
        best_author_match
    )


def request_book(session, title, author):
    url = "https://www.googleapis.com/books/v1/volumes"

    params = {
        "q": f'intitle:"{title}" inauthor:"{author}"',
        "key": API_KEY,
        "orderBy": "relevance",
        "printType": "books"
    }

    # We send one request for the current book
    response = session.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS
    )

    response.raise_for_status()

    return response.json()


def create_book_key(title, author):
    # We create a normalized key used to avoid duplicate saved books
    return (
        normalize_text(title),
        normalize_text(author)
    )


def main():
    # We verify that the CSV file exists
    if not CSV_FILE.exists():
        raise FileNotFoundError(
            f"The CSV file was not found: {CSV_FILE.resolve()}"
        )

    # We read the source CSV file
    books_dataframe = pd.read_csv(
        CSV_FILE,
        encoding="cp1252"
    )

    required_columns = {"bookTitle", "authorName"}

    missing_columns = required_columns.difference(
        books_dataframe.columns
    )

    if missing_columns:
        raise KeyError(
            f"Missing CSV columns: {sorted(missing_columns)}"
        )

    # We load books saved during previous runs
    saved_books = load_saved_books()

    # We create a set of already saved books to avoid duplicates
    saved_book_keys = {
        create_book_key(
            book.get("title", ""),
            book.get("author", "")
        )
        for book in saved_books
    }

    requests_made = 0
    books_saved_this_run = 0
    books_skipped_this_run = 0

    # We reuse the same HTTP connection for all requests
    with requests.Session() as session:
        for _, row in books_dataframe.iterrows():
            if requests_made >= MAX_REQUESTS_PER_RUN:
                print(
                    f"Stopped after {MAX_REQUESTS_PER_RUN} API requests."
                )
                break

            title = clean_title(row["bookTitle"])
            author = clean_author(row["authorName"])

            if not title or not author:
                print("Skipped a row with a missing title or author.")
                books_skipped_this_run += 1
                continue

            print(
                f"[{requests_made + 1}/{MAX_REQUESTS_PER_RUN}] "
                f"Searching: {title} by {author}"
            )

            try:
                # We count every API request, including failed requests
                requests_made += 1

                response_data = request_book(
                    session,
                    title,
                    author
                )

                items = response_data.get("items", [])

                if not items:
                    print("  Skipped: no API results were found.")
                    books_skipped_this_run += 1
                    continue

                (
                    best_item,
                    title_similarity,
                    author_matched
                ) = find_best_book(
                    items,
                    title,
                    author
                )

                if best_item is None:
                    print("  Skipped: no valid result was found.")
                    books_skipped_this_run += 1
                    continue

                if title_similarity < MIN_TITLE_SIMILARITY:
                    print(
                        f"  Skipped: title similarity was too low "
                        f"({title_similarity:.2f})."
                    )
                    books_skipped_this_run += 1
                    continue

                if not author_matched:
                    print("  Skipped: the author did not match.")
                    books_skipped_this_run += 1
                    continue

                volume_info = best_item.get("volumeInfo", {})

                result_title = volume_info.get("title")
                result_authors = volume_info.get("authors", [])
                description = volume_info.get("description")

                if not result_title:
                    print("  Skipped: the result did not contain a title.")
                    books_skipped_this_run += 1
                    continue

                if not result_authors:
                    print("  Skipped: the result did not contain an author.")
                    books_skipped_this_run += 1
                    continue

                if not description:
                    print("  Skipped: the result did not contain a description.")
                    books_skipped_this_run += 1
                    continue

                result_author = ", ".join(result_authors)

                result_key = create_book_key(
                    result_title,
                    result_author
                )

                if result_key in saved_book_keys:
                    print("  Skipped: this book is already saved.")
                    books_skipped_this_run += 1
                    continue

                book_record = {
                    "title": result_title,
                    "author": result_author,
                    "description": description
                }

                saved_books.append(book_record)
                saved_book_keys.add(result_key)

                save_books(saved_books)

                books_saved_this_run += 1

                print(
                    f"  Saved: {result_title} by {result_author} "
                    f"(similarity: {title_similarity:.2f})"
                )

            except requests.HTTPError as error:
                status_code = (
                    error.response.status_code
                    if error.response is not None
                    else "unknown"
                )

                print(
                    f"  HTTP error for '{title}': "
                    f"{status_code} - {error}"
                )

                if status_code == 429:
                    print("Google Books quota was exhausted.")
                    break

                books_skipped_this_run += 1

            except requests.Timeout:
                print(f"  Request timed out for '{title}'.")
                books_skipped_this_run += 1

            except requests.RequestException as error:
                print(f"  Network error for '{title}': {error}")
                books_skipped_this_run += 1

            except Exception as error:
                print(f"  Unexpected error for '{title}': {error}")
                books_skipped_this_run += 1

            finally:
                # We wait after every request, successful or failed
                time.sleep(REQUEST_DELAY_SECONDS)

    print()
    print("Import finished.")
    print(f"API requests made: {requests_made}")
    print(f"Books saved during this run: {books_saved_this_run}")
    print(f"Books skipped during this run: {books_skipped_this_run}")
    print(f"Total books currently saved: {len(saved_books)}")
    print(f"Output file: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()