import asyncio
import httpx
from redguard.datasets.loader import load_all_datasets

async def main():
    entries = load_all_datasets(validate=False)
    prompts = [e["prompt"] for e in entries if "prompt" in e]
    print(f"Total prompts: {len(prompts)}")
    
    mismatches = 0
    async with httpx.AsyncClient() as client:
        for prompt in prompts:
            resp = await client.post("https://api.mohitchdev.me/agent/classify", json={"prompt": prompt}, timeout=10)
            if resp.status_code == 200:
                v = resp.json().get("verdict", "")
                if v != "ADVERSARIAL":
                    print(f"NOT ADVERSARIAL: {v} - {prompt}")
                    mismatches += 1
            else:
                print("API ERROR")
    print(f"Total non-adversarial: {mismatches}")

asyncio.run(main())
