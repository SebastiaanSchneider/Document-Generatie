"""
Document generatie voor verslagen dagbesteding
"""

import argparse
from datetime import datetime  # Importing datetime module
import json
import logging
import os
import requests
from docx import Document  # Importing the python-docx library


# Setup logging
logging.basicConfig(filename="ollama_logs.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# NOTE: ollama must be running for this to work, start the ollama app or run `ollama serve`
MODEL = "llama3.1"


# curl http://127.0.0.1:11434/api/generate -d '{"model": "llama3.1", "messages": [{"role": "user", "content": "write five short prompts for a dnd adventure."}], "stream": false}' # pylint: disable=line-too-long
# curl http://127.0.0.1:11434/api/generate -d "{\"model\": \"llama3.1\", \"messages\": [{\"role\": \"user\", \"content\": \"write five short prompts for a dnd adventure.\"}], \"stream\": false}" -H "Content-Type: application/json" # pylint: disable=line-too-long

def chat(messages, print_to_console=True):
    """Send a chat message to the Ollama API and stream the response."""
    try:
        r = requests.post("http://127.0.0.1:11434/api/generate",
                          json={"model": MODEL, "messages": messages,
                                "stream": True}, stream=True, timeout=10)
        r.raise_for_status()
        logging.info("Request to Ollama was successful.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to connect to Ollama: {e}") # pylint: disable=logging-fstring-interpolation
        print(f"Error: Could not connect to Ollama. {e}")
        return None

    output = ""

    for line in r.iter_lines():
        body = json.loads(line)
        if "error" in body:
            logging.error(f"Error in Ollama response: {body['error']}") # pylint: disable=logging-fstring-interpolation
            print(f"Error in response: {body['error']}")
            return None
        if body.get("done") is False:
            message = body.get("message", "")
            content = message.get("content", "")
            output += content
            if print_to_console:
                print(content, end="", flush=True)

        if body.get("done", False):
            message["content"] = output
            return message

    # Handle case when no message was returned
    logging.warning("No content received from Ollama.")
    print("Warning: No content received.")
    return None


def save_to_docx(content, output_dir="documents"):
    """Save the generated content to a .docx file with a timestamped filename."""
    # Create directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get the current date and time
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"ollama_output_{current_time}.docx"
    file_path = os.path.join(output_dir, filename)

    # Create and save the document
    doc = Document()
    doc.add_paragraph(content)
    doc.save(file_path)

    logging.info(f"Document saved as: {file_path}") # pylint: disable=logging-fstring-interpolation
    print(f"Document saved as: {file_path}")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a report using Ollama and save it as a .docx file.")
    parser.add_argument('-o', '--output_dir', default="documents",
                        help="Directory to save the output .docx file")
    parser.add_argument('-p', '--print', action='store_true',
                        help="Print the output to the console")
    return parser.parse_args()


def main():
    """Main function to interact with the user and generate a report."""
    args = parse_arguments()

    messages = [
        "Schrijf een verslag voor dagbesteding in tegenwoordige tijd. Houd het feitelijk en maak het niet te lang.\n"]  # pylint: disable=line-too-long

    while True:
        user_input = input(
            "Over wie gaat het en wat moet er in het verslag?: ")
        if not user_input:
            print("No input provided. Exiting...")
            logging.info("No user input. Program exited.")
            break

        messages.append({"role": "user", "content": user_input})
        message = chat(messages, print_to_console=args.print)

        if message:
            save_to_docx(message['content'], output_dir=args.output_dir)
        else:
            logging.error("Failed to generate response from Ollama.")
            print("Failed to generate response.")

        # Ask if the user wants to create another report
        retry = input(
            "Do you want to create another report? (yes/no): ").strip().lower()
        if retry != 'yes':
            logging.info("User chose to exit.")
            break


if __name__ == "__main__":
    main()


# het gaat over Pietje. Pietje was vandaag op tijd aanwezig. Hij heeft met meerdere mensen samengewerkt. Dat ging goed, waarmee hij stappen heeft gemaakt ten opzichte van zijn leerdoelen. hij ging wel wat eerder naar huis, waar hij nog verder aan moet werken. Hij ging goed om met andere aanwezigen. Samen hebben ze aan een project gewerkt in de programmeertaal Python. Er waren geen bijzonderheden. # pylint: disable=line-too-long
