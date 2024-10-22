"""
Document generatie voor verslagen dagbesteding
"""

from datetime import datetime
import os
import json
import logging
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory
import requests
from docx import Document


# Flask setup
app = Flask(__name__)
# Load secret key from environment variable or fall back to a default value
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# Setup logging
logging.basicConfig(filename="ollama_logs.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Updated Ollama Model
MODEL = "llama3.1"


def chat(messages, temperature):
    """Send a chat message to the Ollama API and stream the response with specified temperature."""
    try:
        # Log the payload to ensure temperature and other parameters are being sent correctly
        logging.info(f"Sending request to Ollama with model: {MODEL}, temperature: {temperature}, messages: {messages}")  # pylint: disable=logging-fstring-interpolation, disable=line-too-long

        # Attempt to connect to the Ollama API with a timeout of 10 seconds
        r = requests.post("http://ollama.heldeninict.nl/api/chat",
                          json={"model": MODEL, "messages": messages, "stream": True, "temperature": temperature}, timeout=10)  # pylint: disable=line-too-long
        r.raise_for_status()  # Ensure the request was successful
        logging.info(f"Request to Ollama with temperature {temperature} was successful.")  # pylint: disable=logging-fstring-interpolation
    except requests.Timeout:
        # Log and flash an error message for timeout issues
        logging.error(f"Timeout error when connecting to Ollama API for temperature {temperature}")  # pylint: disable=logging-fstring-interpolation
        flash(f"Timeout error. Please try again later.","error")  # pylint: disable=f-string-without-interpolation
        return None
    except requests.RequestException as e:
        # Log and flash an error message for general request failures
        logging.error(f"Failed to connect to Ollama: {e}")  # pylint: disable=logging-fstring-interpolation
        flash(f"Failed to generate report. Please contact support.","error")  # pylint: disable=f-string-without-interpolation
        return None

    output = ""
    try:
        # Process streamed lines from the Ollama API response
        for line in r.iter_lines():
            body = json.loads(line)
            if "error" in body:
                # Log errors from the API response
                logging.error(f"Error in Ollama response: {body['error']}")  # pylint: disable=logging-fstring-interpolation
                flash(f"Error in response from the API: {body['error']}", "error")  # pylint: disable=logging-fstring-interpolation
                return None
            if body.get("done") is False:
                # Accumulate message content
                message = body.get("message", "")
                content = message.get("content", "")
                output += content

            if body.get("done", False):
                # Finalize the output and return it
                message["content"] = output
                return message

    except json.JSONDecodeError as e:
        # Handle and log JSON decoding errors
        logging.error(f"Error decoding JSON from Ollama response: {e}")  # pylint: disable=logging-fstring-interpolation
        flash(f"Error decoding API response. Please try again later.","error")  # pylint: disable=f-string-without-interpolation
        return None

    # Log in case no content is received
    logging.warning("No content received from Ollama.")
    flash("No content received. Please try again.",
          "error")  # pylint: disable=f-string-without-interpolation
    return None


def save_to_docx(content, output_dir="documents"):
    """Save the selected content to a .docx file with a timestamped filename."""
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Generate a unique filename with the current timestamp
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"ollama_output_{current_time}.docx"
    file_path = os.path.join(output_dir, filename)

    # Create a new document and add the content
    doc = Document()
    doc.add_paragraph(content)
    doc.save(file_path)  # Save the file

    logging.info(f"Document saved as: {file_path}")  # pylint: disable=logging-fstring-interpolation
    return file_path  # Return the file path for later use


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the form and handle document generation requests."""
    generated_versions = {}  # Dictionary to hold versions for different temperatures

    if request.method == 'POST':
        # Get the input text and client name from the form
        user_input = request.form['input_text']
        # Extract selected client name
        client_name = request.form['client_name']

        if not user_input:
            # Notify the user if no input is provided
            flash("Please provide input for the report.", "error")
            return render_template('index.html')

        # Update the prompt with the client's name
        text = f"Schrijf een verslag voor dagbesteding in tegenwoordige tijd. Houd het feitelijk, maak het niet te lang en geef het een opmaak met kopjes. Voeg geen tekst toe die niet in het verslag zelf thuishoort.\nHet verslag gaat over {client_name}. "  # pylint: disable=line-too-long
        messages = [{"role": "user", "content": text + user_input}]

        # Generate three versions with different temperature settings
        for temp in [0.1, 0.4, 0.7]:
            message = chat(messages, temperature=temp)
            if message:
                # Store the generated content for each temperature
                generated_versions[temp] = message['content']
            else:
                flash(f"Failed to generate report at temperature {temp}.", "error")

        if generated_versions:
            # Notify the user if reports were generated successfully
            flash("Reports generated successfully.", "success")

    # Render the template with the generated versions (if any)
    return render_template('index.html', generated_versions=generated_versions)


@app.route('/save_docx/<temperature>', methods=['POST'])
def save_docx(temperature):
    """Save the selected version as a .docx file."""
    # Retrieve the content for the selected temperature
    content = request.form.get(
        f'content_{temperature}')  # pylint: disable=logging-fstring-interpolation
    if not content:
        # Notify the user if no content is available to save
        flash("No content to save.", "error")
        return redirect(url_for('index'))

    # Save the selected content to a docx file
    file_path = save_to_docx(content)
    if file_path:
        # Notify the user that the document was saved successfully
        flash(f"Report saved successfully. Download it <a href='/documents/{os.path.basename(file_path)}'>here</a>.", "success")  # pylint: disable=line-too-long
    else:
        flash("Failed to save the document.", "error")

    # Redirect to the main page
    return redirect(url_for('index'))


@app.route('/documents/<filename>')
def download_file(filename):
    """Serve the generated document for download."""
    return send_from_directory('documents', filename)


if __name__ == '__main__':
    # Run the Flask app in debug mode (for development purposes)
    app.run(debug=True)
