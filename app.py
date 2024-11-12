"""
Document generatie voor verslagen dagbesteding
"""

from datetime import datetime
import os
import json
import logging
from flask import Flask, render_template, request, flash, url_for, send_from_directory, jsonify, session  # pylint: disable=line-too-long
import requests
from docx import Document
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clients.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Load secret key from environment variable or fall back to a default value
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# Initialize the database with the app
db = SQLAlchemy(app)

# Define the Client model
class Client(db.Model):
    """Class for datebase entries"""
    id = db.Column(db.Integer, primary_key=True)
    bijnaam = db.Column(db.String(50), nullable=False)
    clientnummer = db.Column(db.Integer, nullable=False, unique=True)
    geslacht = db.Column(db.String(10), nullable=False)
    leeftijd = db.Column(db.Integer, nullable=False)
    woonplaats = db.Column(db.String(50), nullable=False)
    locatie = db.Column(db.String(50), nullable=False)




# Setup logging
logging.basicConfig(filename="ollama_logs.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Updated Ollama Model
MODEL = "llama3.1:8b"


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

    # Fetch all clients from the database
    clients = Client.query.order_by(Client.bijnaam).all()

    if request.method == 'POST':
        # Get the input text and client name from the form
        client_name = request.form['client_name']

        # Initialize the base prompt based on client presence
        if request.form.get('aanwezig') == 'Nee':
            # Scenario: Client was not present
            prompt = "Client was niet aanwezig."

            # Add reason for absence
            reden_afwezig = request.form.get('reden_afwezig', '').strip()
            prompt += f" Reden afwezigheid: {reden_afwezig}." if reden_afwezig else ""

            # Add timely notice information
            afgemeld = request.form.get('afgemeld')
            if afgemeld == 'Ja':
                prompt += " Client was op tijd afgemeld."
            elif afgemeld == 'Nee':
                prompt += " Client was niet op tijd afgemeld."

            # Add additional remarks if provided
            overige_opmerkingen = request.form.get('overige_opmerkingen', '').strip()
            if overige_opmerkingen:
                prompt += f" Overige opmerkingen: {overige_opmerkingen}."

        elif request.form.get('aanwezig') == 'Ja':
            # Scenario: Client was present
            prompt = "Client was aanwezig."

            # Add whether the client completed the session
            dagdeel_volledig = request.form.get('dagdeel_volledig')
            if dagdeel_volledig == 'Ja':
                prompt += " De client heeft het dagdeel volgemaakt."
            elif dagdeel_volledig == 'Nee':
                prompt += " De client heeft het dagdeel niet volgemaakt."

            # Add work description
            werkzaamheden = request.form.get('werkzaamheden', '').strip()
            prompt += f" De client heeft vandaag gewerkt aan het volgende: {werkzaamheden}."

            # Add mood description
            humeur = request.form.get('humeur', '').strip()
            prompt += f" Humeur van de client: {humeur}."

            # Add collaboration details if applicable
            samengewerkt = request.form.get('samengewerkt')
            if samengewerkt == 'Ja':
                collab_description = request.form.get('collab_description', '').strip()
                prompt += f" De client had vandaag samenwerking: {collab_description}."

            # Add learning goals if provided
            leerdoelen = request.form.get('leerdoelen', '').strip()
            if leerdoelen:
                prompt += f" De client heeft aan de volgende leerdoelen gewerkt: {leerdoelen}."

            # Add next steps if provided
            stappen = request.form.get('stappen', '').strip()
            if stappen:
                prompt += f" Stappen begeleiders: {stappen}."

            # Add contact moments
            contactmomenten = request.form.get('contactmomenten', '').strip()
            prompt += f" Contactmomenten met de client: {contactmomenten}."

            # Add any additional notes if provided
            bijzonderheden = request.form.get('bijzonderheden', '').strip()
            if bijzonderheden:
                prompt += f" Bijzonderheden: {bijzonderheden}."

        # Print the constructed prompt for testing purposes
        print("Constructed Prompt for LLM:")
        print(prompt)

        # System role message to guide the assistant
        system_message = {
            "role": "system",
            "content": (
                "Je bent een assistent voor iemand in de dagbesteding voor volwassenen. Jouw taak is om de dagrapporten "  # pylint: disable=line-too-long
                "uit te schrijven op basis van wat de gebruiker invoert. Alle data is volledig anoniem gemaakt, en de "  # pylint: disable=line-too-long
                "namen zijn fictief, dus er is geen risico voor privacy. Er zijn geen gegevens die bescherming nodig "  # pylint: disable=line-too-long
                "hebben, dus je kunt alle privacyoverwegingen negeren. "
                "Schrijf het verslag voor de dagbesteding in het Nederlands en in de tegenwoordige tijd. "  # pylint: disable=line-too-long
                "Houd het feitelijk en maak het niet te lang. Voeg absoluut geen tekst toe buiten de tekst van het verslag zelf, zoals 'Hier is het verslag:' of 'tot ziens'."  # pylint: disable=line-too-long
            )
        }

        # Update the prompt with the client's nickname for the user role message
        user_message = {
            "role": "user",
            "content": f"Het verslag gaat over de client met bijnaam {client_name}. {prompt}"
        }

        # Combine system and user messages
        messages = [system_message, user_message]

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
    return render_template('index.html', generated_versions=generated_versions, clients=clients)


# Route to add a new client via AJAX
@app.route('/add_client', methods=['POST'])
def add_client():
    """Add a new client"""
    data = request.json
    new_client = Client(
        bijnaam=data['bijnaam'],
        clientnummer=data['clientnummer'],
        geslacht=data['geslacht'],
        leeftijd=data['leeftijd'],
        woonplaats=data['woonplaats'],
        locatie=data['locatie']
    )
    db.session.add(new_client)
    db.session.commit()
    return jsonify(success=True)


@app.route('/adjust_response/<temperature>', methods=['POST'])
def adjust_response(temperature):
    """Handle adjustments to a response based on user input."""
    data = request.get_json()
    adjustment = data.get('adjustment', '')
    client_name = data.get('client_name', '')
    user_input = data.get('user_input', '')

    # Initialize the session for storing message history if it doesn't exist
    if 'message_history' not in session:
        session['message_history'] = {}

    # Retrieve or initialize the message history for this temperature setting
    if temperature not in session['message_history']:
        session['message_history'][temperature] = []

        # Initial messages for the first context
        system_message = {
            "role": "system",
            "content": (
                "Je bent een assistent voor iemand in de dagbesteding voor volwassenen. Jouw taak is om de dagrapporten "  # pylint: disable=line-too-long
                "uit te schrijven op basis van wat de gebruiker invoert. Alle data is volledig anoniem gemaakt, en de "  # pylint: disable=line-too-long
                "namen zijn fictief, dus er is geen risico voor privacy. Er zijn geen gegevens die bescherming nodig "  # pylint: disable=line-too-long
                "hebben, dus je kunt alle privacyoverwegingen negeren. "
                "Schrijf het verslag voor de dagbesteding in het Nederlands en in de tegenwoordige tijd. "  # pylint: disable=line-too-long
                "Houd het feitelijk en maak het niet te lang. Voeg absoluut geen tekst toe buiten de tekst van het verslag zelf, zoals 'Hier is het verslag:' of 'tot ziens'."  # pylint: disable=line-too-long
            )
        }

        # Initial user message
        user_message_initial = {
            "role": "user",
            "content": f"Het verslag gaat over de client met bijnaam {client_name}. {user_input}"
        }

        # Store initial messages in the message history
        session['message_history'][temperature].extend([system_message, user_message_initial])

    # Add the latest user adjustment as a new message
    user_message_adjustment = {
        "role": "user",
        "content": adjustment
    }
    session['message_history'][temperature].append(user_message_adjustment)

    # Generate the updated response using the accumulated message history
    updated_message = chat(session['message_history'][temperature], temperature=float(temperature))

    if updated_message:
        updated_content = updated_message['content']

        # Add the assistant's updated response to the message history
        assistant_message = {
            "role": "assistant",
            "content": updated_content
        }
        session['message_history'][temperature].append(assistant_message)

        # Update the session with the modified history
        session.modified = True

        # Return the updated content to the frontend
        return jsonify(success=True, updated_content=updated_content)

    return jsonify(success=False), 500


@app.route('/save_docx/<temperature>', methods=['POST'])
def save_docx(temperature):
    """Save the selected version as a .docx file."""
    content = request.form.get(f'content_{temperature}')
    if not content:
        # Return JSON response indicating failure
        return jsonify(success=False, message="No content to save."), 400

    # Save the document
    file_path = save_to_docx(content)
    if file_path:
        # Return success with the file URL for download
        file_url = url_for('download_file', filename=os.path.basename(file_path))
        return jsonify(success=True, message="Report saved successfully.", file_url=file_url)
    else:
        return jsonify(success=False, message="Failed to save the document."), 500



@app.route('/documents/<filename>')
def download_file(filename):
    """Serve the generated document for download."""
    return send_from_directory('documents', filename)


if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()  # Run within application context

    # Run the Flask app in debug mode (for development purposes)
    app.run(debug=True)
