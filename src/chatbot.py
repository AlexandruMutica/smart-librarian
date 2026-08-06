import json
from typing import Any

from src.openai_client import get_openai_client
from src.retriever import retrieve_books
from src.tools import get_summary_by_title

from src.moderation import moderate_message

CHAT_MODEL = "gpt-4.1-mini"

RETRIEVED_CANDIDATE_COUNT = 6
CONTEXT_BOOK_COUNT = 3

SYSTEM_PROMPT = """
You are Smart Librarian, a conversational assistant that recommends books.

Use only the books provided in the current retrieved context.
Choose one main recommendation that best matches the user's request.
Never invent titles, authors or summaries.
Use the exact title found in the retrieved context.
Do not recommend a title that the conversation says was already recommended.
After choosing a book, call get_summary_by_title using that exact title.

The final answer must contain:
1. The recommended title and author.
2. A short explanation of why the book matches the request.
3. The full summary returned by the tool.

Use the conversation history to understand follow-up messages such as:
"another one", "something darker", "mai dă-mi una" or "tot așa".

Answer in the same language as the user.
"""

TOOLS = [
    {
        "type": "function",
        "name": "get_summary_by_title",
        "description": (
            "Returns the full local summary for an exact book title. "
            "The title must be copied exactly from the retrieved context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": (
                        "The exact title of the recommended book."
                    ),
                }
            },
            "required": ["title"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]

FOLLOW_UP_PHRASES = (
    "another",
    "another one",
    "something else",
    "one more",
    "mai da-mi",
    "mai dă-mi",
    "inca una",
    "încă una",
    "alta",
    "altul",
    "tot asa",
    "tot așa",
)


# Formatting the retrieved books for the model.
def build_retrieved_context(
    books: list[dict[str, Any]],
) -> str:
    context_parts: list[str] = []

    for position, book in enumerate(books, start=1):
        context_parts.append(
            "\n".join(
                [
                    f"Book {position}",
                    f"Title: {book['title']}",
                    f"Author: {book['author']}",
                    f"Content: {book['document']}",
                ]
            )
        )

    return "\n\n".join(context_parts)


# Reading the arguments received from a function call.
def get_tool_arguments(tool_call: Any) -> dict[str, Any]:
    try:
        arguments = json.loads(tool_call.arguments)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The tool arguments were not valid JSON."
        ) from error

    if not isinstance(arguments, dict):
        raise ValueError(
            "The tool arguments must contain a JSON object."
        )

    return arguments


# Running the local function selected by the model.
def execute_tool_call(tool_call: Any) -> tuple[str, str | None]:
    if tool_call.name != "get_summary_by_title":
        return f"Unknown tool: {tool_call.name}", None

    arguments = get_tool_arguments(tool_call)
    title = arguments.get("title", "")

    if not isinstance(title, str):
        return "The title provided to the tool was invalid.", None

    summary = get_summary_by_title(title)

    return summary, title.strip() or None


class SmartLibrarianChat:
    def __init__(self) -> None:
        self.client = get_openai_client()
        self.previous_response_id: str | None = None
        self.last_user_request: str | None = None
        self.recommended_titles: set[str] = set()

    # Starting a new conversation without restarting the application.
    def reset(self) -> None:
        self.previous_response_id = None
        self.last_user_request = None
        self.recommended_titles.clear()

    # Adding the previous request only when the new message looks like a follow-up.
    def build_retrieval_query(self, user_message: str) -> str:
        normalized_message = user_message.casefold()
        word_count = len(user_message.split())

        is_follow_up = (
            word_count <= 6
            or any(
                phrase in normalized_message
                for phrase in FOLLOW_UP_PHRASES
            )
        )

        if not is_follow_up or self.last_user_request is None:
            return user_message

        return (
            f"Previous book request: {self.last_user_request}\n"
            f"Current follow-up request: {user_message}"
        )

    # Keeping already recommended titles out of the next context.
    def select_new_books(
        self,
        books: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        available_books = [
            book
            for book in books
            if book["title"].casefold() not in self.recommended_titles
        ]

        if not available_books:
            available_books = books

        return available_books[:CONTEXT_BOOK_COUNT]

    def chat(self, user_message: str) -> str:
        if not isinstance(user_message, str):
            raise TypeError("The user message must be a string.")

        cleaned_message = user_message.strip()

        if not cleaned_message:
            return (
                "Please enter a question or describe "
                "what kind of book you want."
            )

        moderation_response = moderate_message(cleaned_message)

        if moderation_response is not None:
            return moderation_response

        retrieval_query = self.build_retrieval_query(
            cleaned_message
        )

        retrieved_candidates = retrieve_books(
            query=retrieval_query,
            result_count=RETRIEVED_CANDIDATE_COUNT,
        )

        if not retrieved_candidates:
            return (
                "I could not find a relevant book "
                "in the local library."
            )

        retrieved_books = self.select_new_books(
            retrieved_candidates
        )

        retrieved_context = build_retrieved_context(
            retrieved_books
        )

        already_recommended = (
            ", ".join(sorted(self.recommended_titles))
            if self.recommended_titles
            else "None"
        )

        user_input = (
            f"Current user request:\n{cleaned_message}\n\n"
            f"Books already recommended in this conversation:\n"
            f"{already_recommended}\n\n"
            f"Retrieved books for the current request:\n"
            f"{retrieved_context}"
        )

        request_arguments: dict[str, Any] = {
            "model": CHAT_MODEL,
            "instructions": SYSTEM_PROMPT,
            "input": user_input,
            "tools": TOOLS,
            "tool_choice": "auto",
        }

        # Continuing from the last response gives the model conversation memory.
        if self.previous_response_id is not None:
            request_arguments["previous_response_id"] = (
                self.previous_response_id
            )

        first_response = self.client.responses.create(
            **request_arguments
        )

        tool_outputs: list[dict[str, str]] = []

        for output_item in first_response.output:
            if output_item.type != "function_call":
                continue

            tool_result, selected_title = execute_tool_call(
                output_item
            )

            if selected_title:
                self.recommended_titles.add(
                    selected_title.casefold()
                )

            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": output_item.call_id,
                    "output": tool_result,
                }
            )

        self.last_user_request = retrieval_query

        if not tool_outputs:
            self.previous_response_id = first_response.id

            if first_response.output_text:
                return first_response.output_text

            return (
                "The model did not select a book "
                "from the retrieved results."
            )

        final_response = self.client.responses.create(
            model=CHAT_MODEL,
            instructions=SYSTEM_PROMPT,
            previous_response_id=first_response.id,
            input=tool_outputs,
            tools=TOOLS,
        )

        self.previous_response_id = final_response.id

        if not final_response.output_text:
            return (
                "The final recommendation could not be generated."
            )

        return final_response.output_text


if __name__ == "__main__":
    try:
        librarian = SmartLibrarianChat()

        first_answer = librarian.chat(
            "Vreau o carte despre magie și aventură."
        )
        print(first_answer)

        second_answer = librarian.chat(
            "Mai dă-mi una tot așa."
        )
        print(f"\n{second_answer}")

    except Exception as error:
        print(f"Chatbot failed: {error}")