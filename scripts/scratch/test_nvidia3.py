import asyncio
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
os.environ["NVIDIA_MODEL"] = "nvidia/llama-3.1-nemotron-70b-instruct"

from backend.agents.default_agent import invoke

async def main():
    try:
        response = await invoke("Hello, who are you? Please use the calculator to compute 2+2.")
        print("Response:", response)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
