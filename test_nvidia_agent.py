import asyncio
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from backend.agents.default_agent import invoke

async def main():
    try:
        response = await invoke("Hello, please use the calculator to compute 5 * 7.")
        print("Response:", response)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
