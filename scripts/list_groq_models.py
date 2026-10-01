"""List available Groq models for this API key."""
import os
from groq import Groq

os.environ.setdefault("GROQ_API_KEY", "")
client = Groq()
models = sorted([m.id for m in client.models.list().data])
print("Available Groq models:")
for m in models:
    print(f"  {m}")
