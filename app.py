"""
Document generatie voor verslagen dagbesteding
"""


# Added send_from_directory
from datetime import datetime
import os
import json
import logging
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory
import requests
from docx import Document


# Flask setup
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flashing messages

# Setup logging
logging.basicConfig(filename="ollama_logs.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Updated Ollama Model
MODEL = "llama3.2"


def chat(messages, temperature):
    """Send a chat message to the Ollama API and stream the response with specified temperature."""
    try:
        r = requests.post("http://ollama.heldeninict.nl/api/chat",
                          json={"model": MODEL, "messages": messages,
                                "stream": True, "temperature": temperature}, timeout=10)
        r.raise_for_status()
        logging.info(f"Request to Ollama with temperature {temperature} was successful.")  # pylint: disable=logging-fstring-interpolation
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
    """Save the selected content to a .docx file with a timestamped filename."""
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
    generated_versions = {}  # Dictionary to hold versions for different temperatures

    if request.method == 'POST':
        user_input = request.form['input_text']
        # Extract selected client name
        client_name = request.form['client_name']

        if not user_input:
            flash("Please provide input for the report.", "error")
            return render_template('index.html')

        # Update the prompt with the client's name
        text = f"Schrijf een verslag voor dagbesteding in tegenwoordige tijd. Houd het feitelijk en maak het niet te lang. Geef het een opmaak met kopjes. Het verslag gaat over {client_name}.\n" # pylint: disable=line-too-long
        messages = [{"role": "user", "content": text + user_input}]

        # Generate three versions with different temperature settings
        for temp in [0.1, 0.4, 0.7]:
            message = chat(messages, temperature=temp)
            if message:
                generated_versions[temp] = message['content']
            else:
                flash(f"Failed to generate report at temperature {
                      temp}.", "error")

    return render_template('index.html', generated_versions=generated_versions)



@app.route('/save_docx/<temperature>', methods=['POST'])
def save_docx(temperature):
    """Save the selected version as a .docx file."""
    content = request.form.get(f'content_{temperature}')
    if not content:
        flash("No content to save.", "error")
        return redirect(url_for('index'))

    # Save the selected content to a docx file
    file_path = save_to_docx(content)
    if file_path:
        flash(f"Report saved successfully. Download it <a href='/documents/{
              os.path.basename(file_path)}'>here</a>.", "success")
    else:
        flash("Failed to save the document.", "error")

    return redirect(url_for('index'))


@app.route('/documents/<filename>')
def download_file(filename):
    """Serve the generated document for download."""
    return send_from_directory('documents', filename)


if __name__ == '__main__':
    app.run(debug=True)
