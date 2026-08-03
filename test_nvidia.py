import asyncio
import os
from backend.agents.default_agent import invoke

async def main():
    try:
        response = await invoke("Hello, who are you?")
        print("Response:", response)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env")
    asyncio.run(main())
