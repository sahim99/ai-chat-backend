import os
from groq import AsyncGroq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Securely retrieve API Key
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("Missing GROQ_API_KEY in environment")

# Initialize asynchronous Groq client
client = AsyncGroq(api_key=api_key)

# Define the model to use (Llama 3.1 8B Instant is fast and cost-effective)
MODEL = "llama-3.1-8b-instant"

async def generate_response(prompt: str, system_prompt: str = "You are a helpful assistant."):
    """Generates a response from the LLM using Groq API."""
    try:
        completion = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        return f"Error generating response: {e}"

async def generate_summary(text_content: str):
    """
    Generates a concise summary of the provided text/conversation history.
    
    Args:
        text_content (str): The full text or conversation transcript to summarize.
        
    Returns:
        str: A summary of the content.
    """
    # Specific prompt engineering for summarization
    prompt = f"Summarize the following conversation strictly and concisely:\n\n{text_content}"
    # Reuse the core generation logic with a specialized system prompt
    return await generate_response(prompt, system_prompt="You are an expert summarizer.")
