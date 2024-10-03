import json
import requests

# NOTE: ollama must be running for this to work, start the ollama app or run `ollama serve`
model = "llama3.1"


def chat(messages):
    r = requests.post("http://ollama.heldeninict.nl/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True)
    r.raise_for_status()
    output = ""

    for line in r.iter_lines():
        body = json.loads(line)
        if "error" in body:
            raise Exception(body["error"])
        if body.get("done") is False:
            message = body.get("message", "")
            content = message.get("content", "")
            output += content
            # the response streams one token at a time, print that as we receive it
            print(content, end="", flush=True)

        if body.get("done", False):
            message["content"] = output
            return message


def main():
    messages = ["Schrijf een verslag dagbesteding in tegenwoordige tijd. " +
                "Houd het feitelijk en maak het niet te lang.\n"]

    while True:
        user_input = input("Over wie gaat het en wat moet er in het verslag?: ")
        if not user_input:
            exit()
        print()
        messages.append({"role": "user", "content": user_input})
        message = chat(messages)
        messages.append(message)
        print("\n\n")


if __name__ == "__main__":
    main()

# het gaat over Pietje. Pietje was vandaag op tijd aanwezig. Hij heeft met meerdere mensen samengewerkt. Dat ging goed, waarmee hij stappen heeft gemaakt ten opzichte van zijn leerdoelen. hij ging wel wat eerder naar huis, waar hij nog verder aan moet werken. Hij ging goed om met andere aanwezigen. Samen hebben ze aan een project gewerkt in de programmeertaal Python. Er waren geen bijzonderheden.
