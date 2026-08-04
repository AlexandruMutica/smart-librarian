import json
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CSV_FILE = PROJECT_ROOT / "good_reads.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "books.json"

GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"

# We define the import settings
MAX_REQUESTS_PER_RUN = 900
MIN_TITLE_SIMILARITY = 0.80
REQUEST_DELAY_SECONDS = 1
REQUEST_TIMEOUT_SECONDS = 30

# We define the retry settings
MAX_RETRIES = 5
RETRY_BASE_DELAY_SECONDS = 2
RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504
}

# We load the environment variables from the project .env file
load_dotenv(PROJECT_ROOT / ".env")

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

    # We return an empty list if the output file is empty
    if OUTPUT_FILE.stat().st_size == 0:
        return []

    try:
        with OUTPUT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        print(
            "Warning: books.json does not contain a JSON list. "
            "We start with an empty list."
        )
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


def calculate_retry_delay(retry_number):
    # We progressively increase the waiting time after each failed attempt
    return RETRY_BASE_DELAY_SECONDS * (2 ** retry_number)


def request_book(
    session,
    title,
    author,
    available_requests
):
    params = {
        "q": f'intitle:"{title}" inauthor:"{author}"',
        "key": API_KEY,
        "orderBy": "relevance",
        "printType": "books"
    }

    requests_used = 0

    for attempt in range(MAX_RETRIES):
        if requests_used >= available_requests:
            print(
                "  We cannot retry because the request limit "
                "for this run was reached."
            )
            return None, requests_used, True

        try:
            # We count every HTTP request, including retry attempts
            requests_used += 1

            response = session.get(
                GOOGLE_BOOKS_API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS
            )

        except requests.Timeout:
            if (
                attempt == MAX_RETRIES - 1
                or requests_used >= available_requests
            ):
                print(
                    f"  Request timed out for '{title}' after "
                    f"{requests_used} attempt(s)."
                )
                return None, requests_used, False

            retry_delay = calculate_retry_delay(attempt)

            print(
                f"  Request timed out for '{title}'. "
                f"We retry in {retry_delay} seconds."
            )

            time.sleep(retry_delay)
            continue

        except requests.RequestException as error:
            print(f"  Network error for '{title}': {error}")
            return None, requests_used, False

        if response.status_code in RETRYABLE_STATUS_CODES:
            if (
                attempt == MAX_RETRIES - 1
                or requests_used >= available_requests
            ):
                print(
                    f"  HTTP {response.status_code} for '{title}' "
                    f"after {requests_used} attempt(s)."
                )

                # We stop the run when the API quota remains unavailable
                should_stop = response.status_code == 429

                return None, requests_used, should_stop

            retry_delay = calculate_retry_delay(attempt)

            print(
                f"  HTTP {response.status_code} for '{title}'. "
                f"We retry in {retry_delay} seconds."
            )

            time.sleep(retry_delay)
            continue

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            print(
                f"  HTTP error for '{title}': "
                f"{response.status_code} - {error}"
            )
            return None, requests_used, False

        try:
            return response.json(), requests_used, False
        except ValueError:
            print(
                f"  Google Books returned invalid JSON for '{title}'."
            )
            return None, requests_used, False

    return None, requests_used, False


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

    required_columns = {
        "bookTitle",
        "authorName"
    }

    missing_columns = required_columns.difference(
        books_dataframe.columns
    )

    if missing_columns:
        raise KeyError(
            f"Missing CSV columns: {sorted(missing_columns)}"
        )

    # We load the books saved during previous runs
    saved_books = load_saved_books()

    # We keep the saved titles in a set so we can check them quickly
    saved_titles = {
        normalize_text(book.get("title", ""))
        for book in saved_books
        if book.get("title")
    }

    requests_made = 0
    books_saved_this_run = 0
    books_skipped_this_run = 0

    # We reuse the same HTTP connection for all requests
    with requests.Session() as session:
        for _, row in books_dataframe.iterrows():
            title = clean_title(row["bookTitle"])
            author = clean_author(row["authorName"])

            if not title or not author:
                print("Skipped a row with a missing title or author.")
                books_skipped_this_run += 1
                continue

            normalized_title = normalize_text(title)

            # We skip the API request when the title is already in books.json
            if normalized_title in saved_titles:
                print(
                    f"Skipped: '{title}' is already saved."
                )
                books_skipped_this_run += 1
                continue

            if requests_made >= MAX_REQUESTS_PER_RUN:
                print(
                    f"Stopped after {MAX_REQUESTS_PER_RUN} API requests."
                )
                break

            print(
                f"[{requests_made + 1}/{MAX_REQUESTS_PER_RUN}] "
                f"Searching: {title} by {author}"
            )

            available_requests = (
                MAX_REQUESTS_PER_RUN - requests_made
            )

            response_data, requests_used, should_stop = request_book(
                session=session,
                title=title,
                author=author,
                available_requests=available_requests
            )

            requests_made += requests_used

            if response_data is None:
                books_skipped_this_run += 1

                if should_stop:
                    print(
                        "The import was stopped because the API "
                        "request limit is currently unavailable."
                    )
                    break

                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            try:
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
                    print(
                        "  Skipped: the result did not contain a title."
                    )
                    books_skipped_this_run += 1
                    continue

                if not result_authors:
                    print(
                        "  Skipped: the result did not contain an author."
                    )
                    books_skipped_this_run += 1
                    continue

                if not description:
                    print(
                        "  Skipped: the result did not contain "
                        "a description."
                    )
                    books_skipped_this_run += 1
                    continue

                result_author = ", ".join(result_authors)
                normalized_result_title = normalize_text(result_title)

                # We verify the returned title before saving it
                if normalized_result_title in saved_titles:
                    print(
                        "  Skipped: the returned title is already saved."
                    )
                    books_skipped_this_run += 1
                    continue

                book_record = {
                    "title": result_title,
                    "author": result_author,
                    "description": description
                }

                saved_books.append(book_record)

                # We remember both forms during the current run
                saved_titles.add(normalized_title)
                saved_titles.add(normalized_result_title)

                # We save after every successful result
                save_books(saved_books)

                books_saved_this_run += 1

                print(
                    f"  Saved: {result_title} by {result_author} "
                    f"(similarity: {title_similarity:.2f})"
                )

            except Exception as error:
                print(f"  Unexpected error for '{title}': {error}")
                books_skipped_this_run += 1

            finally:
                # We wait after processing every API response
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