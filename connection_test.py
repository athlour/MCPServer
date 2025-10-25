import requests
import json

# Default Ollama local API endpoint
OLLAMA_URL = "http://localhost:11434/api/generate"

# Choose your model (check with "ollama list" in terminal)
MODEL_NAME = "gpt-oss:120b-cloud"     # or "mistral", "phi", "gemma", etc.

def test_ollama(prompt: str):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False   # get the full response as one JSON object
    }

    print(f"🔹 Sending prompt to Ollama ({MODEL_NAME}) ...\n")
    response = requests.post(OLLAMA_URL, json=payload)

    print(f"🔹 HTTP Status: {response.status_code}\n")
    print("🔹 Raw response text (first 300 chars):\n", response.text[:300], "\n")

    # Try to parse JSON
    try:
        data = response.json()
        print("✅ Parsed JSON:")
        print(json.dumps(data, indent=2))
        if "response" in data:
            print("\n💬 Model said:\n", data["response"])
    except Exception as e:
        print("⚠️ Could not parse JSON:", e)

if __name__ == "__main__":
    test_ollama("Hello from Python! What model are you running?")
