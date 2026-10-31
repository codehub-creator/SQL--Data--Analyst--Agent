import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client()  # reads GEMINI_API_KEY from the environment
MODEL = os.getenv("GEMINI_MODEL")

print("Using model:", MODEL)

response = client.models.generate_content(
    model=MODEL,
    contents="Reply with exactly: setup works",
)

print(response.text)
print(response.usage_metadata)