import asyncio
from llm_service import generate_response

async def test():
    print("Testing generate_response...")
    try:
        r = await generate_response("What is the capital of India?")
        print(f"Result: {r}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
