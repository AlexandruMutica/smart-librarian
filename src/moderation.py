import re
import unicodedata


BLOCKED_WORDS = {
    "idiot",
    "idiotule",
    "prost",
    "proasta",
    "prostule",
    "dobitoc",
    "tampit",
    "tampita",
    "fraier",
    "bou",
}


# Removing diacritics so similar spellings are checked consistently.
def remove_diacritics(text: str) -> str:
    normalized_text = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized_text
        if not unicodedata.combining(character)
    )


# Preparing the message for whole-word matching.
def normalize_message(message: str) -> str:
    message_without_diacritics = remove_diacritics(
        message.casefold()
    )

    # Replacing punctuation with spaces avoids partial matches.
    cleaned_message = re.sub(
        r"[^a-z0-9\s]",
        " ",
        message_without_diacritics,
    )

    return " ".join(cleaned_message.split())


# Checking the message before sending it to external services.
def contains_inappropriate_language(message: str) -> bool:
    if not isinstance(message, str):
        raise TypeError("The message must be a string.")

    normalized_message = normalize_message(message)

    if not normalized_message:
        return False

    words = set(normalized_message.split())

    return bool(words.intersection(BLOCKED_WORDS))


# Returning a polite local response for blocked messages.
def moderate_message(message: str) -> str | None:
    if contains_inappropriate_language(message):
        return (
            "Te rog să folosești un limbaj respectuos. "
            "Pot continua să te ajut cu recomandări de cărți."
        )

    return None


if __name__ == "__main__":
    test_messages = [
        "Vreau o carte fantasy.",
        "Ești un idiot.",
        "Recomandă-mi o carte despre prietenie.",
    ]

    for test_message in test_messages:
        moderation_result = moderate_message(test_message)

        print(f"Message: {test_message}")
        print(
            f"Result: {moderation_result or 'Allowed'}\n"
        )