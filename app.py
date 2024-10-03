"""
Document generatie voor verslagen dagbesteding
"""

from datetime import datetime
import os
import json
import logging
import requests
from flask import Flask, render_template, request, send_from_directory, flash
from docx import Document

# Flask setup
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flashing messages

# Setup logging
logging.basicConfig(filename="ollama_logs.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# NOTE: ollama must be running for this to work
MODEL = "llama3.1"


def chat(messages):
    """Send a chat message to the Ollama API and stream the response."""
    try:
        r = requests.post("http://ollama.heldeninict.nl/api/chat",
                          json={"model": MODEL, "messages": messages,
                                "stream": True, "temperature": 0.4}, timeout=10)
        r.raise_for_status()
        logging.info("Request to Ollama was successful.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to connect to Ollama: {e}") # pylint: disable=logging-fstring-interpolation
        return None

    output = ""
    for line in r.iter_lines():
        body = json.loads(line)
        if "error" in body:
            logging.error(f"Error in Ollama response: {body['error']}") # pylint: disable=logging-fstring-interpolation
            return None
        if body.get("done") is False:
            message = body.get("message", "")
            content = message.get("content", "")
            output += content

        if body.get("done", False):
            message["content"] = output
            return message

    logging.warning("No content received from Ollama.")
    return None


def save_to_docx(content, output_dir="documents"):
    """Save the generated content to a .docx file with a timestamped filename."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"ollama_output_{current_time}.docx"
    file_path = os.path.join(output_dir, filename)

    doc = Document()
    doc.add_paragraph(content)
    doc.save(file_path)

    logging.info(f"Document saved as: {file_path}") # pylint: disable=logging-fstring-interpolation
    return file_path


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the form and handle document generation requests."""
    if request.method == 'POST':
        user_input = request.form['input_text']
        if not user_input:
            flash("Please provide input for the report.", "error")
            return render_template('index.html')

        text = "Schrijf een verslag voor dagbesteding in tegenwoordige tijd. Houd het feitelijk en maak het niet te lang. Geef het een opmaak met kopjes.\n"  # pylint: disable=line-too-long
        messages = [{"role": "user", "content": text + user_input}]

        # Call the Ollama API
        message = chat(messages)

        if message:
            # Save the document and provide download link
            file_path = save_to_docx(message['content'])
            return render_template('index.html', success=True, filename=os.path.basename(file_path))
        else:
            flash("Failed to generate the report.", "error")

    return render_template('index.html')


@app.route('/documents/<filename>')
def download_file(filename):
    """Serve the generated document for download."""
    return send_from_directory('documents', filename)


if __name__ == '__main__':
    app.run(debug=True)


# was er wel/niet
# heeft aan doelen gewerkt?
# was in goede bui of niet?
# bijzonderheden?

# nee komt er uberhaupt niet in

# het gaat over Pietje. Pietje was vandaag op tijd aanwezig. Hij heeft met meerdere mensen samengewerkt. Dat ging goed, waarmee hij stappen heeft gemaakt ten opzichte van zijn leerdoelen. hij ging wel wat eerder naar huis, waar hij nog verder aan moet werken. Hij ging goed om met andere aanwezigen. Samen hebben ze aan een project gewerkt in de programmeertaal Python. Er waren geen bijzonderheden. # pylint: disable=line-too-long

# curl http://127.0.0.1:11434/api/generate -d '{"model": "llama3.1", "messages": [{"role": "user", "content": "write five short prompts for a dnd adventure."}], "stream": false}' # pylint: disable=line-too-long
# curl http://ollama.heldeninict.nl/api/chat -d "{\"model\": \"llama3.1\", \"messages\": [{\"role\": \"user\", \"content\": \"write five short prompts for a dnd adventure.\"}], \"stream\": false}" -H "Content-Type: application/json" # pylint: disable=line-too-long
