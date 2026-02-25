import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.1-8b-instant"


def chat(system_message: str, message_history: list) -> str:
    messages = [{"role": "system", "content": system_message}]
    messages.extend(message_history)

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=256,
    )

    return response.choices[0].message.content
