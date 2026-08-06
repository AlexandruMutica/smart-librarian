from src.chatbot import SmartLibrarianChat


EXIT_COMMANDS = {
    "exit",
    "quit",
    "stop",
}

RESET_COMMANDS = {
    "reset",
    "new",
}


# Starting the command-line interface.
def run_chatbot() -> None:
    librarian = SmartLibrarianChat()

    print("Smart Librarian")
    print("Describe what kind of book you are looking for.")
    print("Type 'reset' to start a new conversation.")
    print("Type 'exit' to close the application.\n")

    while True:
        try:
            user_message = input("You: ").strip()
            normalized_message = user_message.casefold()

            if normalized_message in EXIT_COMMANDS:
                print("\nSmart Librarian: Goodbye!")
                break

            if normalized_message in RESET_COMMANDS:
                librarian.reset()
                print(
                    "\nSmart Librarian: "
                    "A new conversation has been started.\n"
                )
                continue

            if not user_message:
                print(
                    "\nSmart Librarian: "
                    "Please enter a question "
                    "or a book preference.\n"
                )
                continue

            print(
                "\nSmart Librarian is looking for a book..."
            )

            answer = librarian.chat(user_message)

            print(f"\nSmart Librarian:\n{answer}\n")

        except KeyboardInterrupt:
            print("\n\nSmart Librarian: Goodbye!")
            break

        except EOFError:
            print("\n\nSmart Librarian: Goodbye!")
            break

        except Exception as error:
            print(
                "\nSmart Librarian: "
                "Something went wrong while "
                "processing your request."
            )
            print(f"Error: {error}\n")


if __name__ == "__main__":
    run_chatbot()