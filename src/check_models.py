import os
import sys
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
models = sys.argv[1:] or CANDIDATES

client = genai.Client(http_options=types.HttpOptions(timeout=30000))  # 30s limit

for m in models:
    start = time.time()
    try:
        r = client.models.generate_content(
            model=m, contents="Reply with exactly: setup works"
        )
        print(f"OK     {m:<26} {time.time() - start:5.1f}s  -> {r.text!r}")
    except Exception as e:
        print(f"FAIL   {m:<26} {time.time() - start:5.1f}s  -> {type(e).__name__}: {str(e)[:90]}")