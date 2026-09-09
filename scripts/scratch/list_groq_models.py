import os
import httpx

api_key = os.getenv("GROQ_API_KEY")
if api_key:
    r = httpx.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    if r.status_code == 200:
        models = [m['id'] for m in r.json().get('data', [])]
        print("Groq Models:", models)
    else:
        print("Error fetching models:", r.status_code)
else:
    print("GROQ_API_KEY not set")
