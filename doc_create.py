from docx import Document  # Importing the python-docx library
from datetime import datetime  # Importing datetime module


content = "blablablablabla"

def main(content):
    # Get the current date and time
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Create the filename with date and time
    filename = f"ollama_output_{current_time}.docx"

    doc = Document()  # Create a new Document
    doc.add_paragraph(content)  # Add the response content as a paragraph
    doc.save(filename)  # Save the document with the filename

    print(f"Document saved as: {filename}")


if __name__ == "__main__":
    main(content)
