import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_openai_client() -> OpenAI:
    #Creating and return the OpenAI client.
    api_key = os.getenv("OPENAI_API_KEY")

    #Stop early if the API key is missing.
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found in the environment."
        )

    return OpenAI(api_key=api_key)


if __name__ == "__main__":
    try:
        #We only check if the client can be created.
        client = get_openai_client()
        print("OpenAI client was created successfully.")

    except ValueError as error:
        print(f"Error: {error}")