import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")
api_key = os.getenv("NVIDIA_API_KEY", "")

resp = requests.get(
    "https://integrate.api.nvidia.com/v1/models",
    headers={"Authorization": f"Bearer {api_key}"}
)

if resp.status_code == 200:
    data = resp.json()
    models = [m["id"] for m in data.get("data", [])]
    print(f"Total available NVIDIA models: {len(models)}")
    for m in models:
        if "nemotron" in m.lower() or "llama" in m.lower() or "deepseek" in m.lower():
            print(" -", m)
else:
    print("Error listing models:", resp.status_code, resp.text)
