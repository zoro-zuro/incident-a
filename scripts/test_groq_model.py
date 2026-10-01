"""Quick test of Groq decision provider with the available model."""
import os
import sys

os.environ["GROQ_API_KEY"] = ""
os.environ["GROQ_MODEL"] = "openai/gpt-oss-120b"
os.environ["DECISION_PROVIDER"] = "groq"

sys.path.insert(0, ".")

from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

print("Testing openai/gpt-oss-120b with json_object response format...")
try:
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are an SRE decision engine. Output JSON only."},
            {"role": "user", "content": 'Analyze: high error rate on checkout-service after deployment v2.4.1. Return JSON: {"recommended_action": "rollback", "confidence": 0.95, "hypothesis": "deployment caused the issue", "root_cause": "db pool exhaustion"}'},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        timeout=30.0,
    )
    content = resp.choices[0].message.content
    print(f"SUCCESS! Response:\n{content}")
except Exception as e:
    print(f"FAILED: {e}")
    print("\nTrying without json_object format...")
    try:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are an SRE decision engine. Output JSON only."},
                {"role": "user", "content": 'Analyze: high error rate on checkout-service after deployment v2.4.1. Return JSON: {"recommended_action": "rollback", "confidence": 0.95, "hypothesis": "deployment caused the issue", "root_cause": "db pool exhaustion"}'},
            ],
            temperature=0.1,
            timeout=30.0,
        )
        content = resp.choices[0].message.content
        print(f"SUCCESS without json_object format:\n{content}")
    except Exception as e2:
        print(f"ALSO FAILED: {e2}")
