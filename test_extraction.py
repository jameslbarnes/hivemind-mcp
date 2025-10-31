#!/usr/bin/env python3
"""
Quick test to see Claude's response
"""

import os
import json
from dotenv import load_dotenv
import anthropic

load_dotenv()

claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PRIVACY_PROMPT = """You are a privacy-preserving insight extractor for Hivemind.

CRITICAL: You MUST respond with ONLY valid JSON. No explanatory text before or after.

Extract valuable insights from conversations while protecting privacy.

Look for insights in ANY domain: technical, career, life, creative, personal growth.
Key question: "Would this help someone else in the group?"

PRIVACY RULES (STRICT):
- Remove: names, companies, health diagnoses, financial details, locations
- Preserve: general context, emotional tone, expertise demonstrated

You MUST return ONLY this exact JSON structure (no other text):
{
  "shareable": true or false,
  "insight": "2-4 sentence anonymized insight",
  "category": "technical/career/life/creative/learning/other",
  "subcategory": "specific area",
  "confidence": 0.0-1.0,
  "sensitivity": 0.0-1.0,
  "tags": ["keyword1", "keyword2"],
  "expertise_areas": ["area1", "area2"],
  "reason": "why shareable or not"
}

Share if: confidence > 0.6, sensitivity < 0.6, generalizable, no third-party PII.
When in doubt, protect privacy."""

user_msg = "I'm struggling with async Python bugs. They're really hard to debug."
assistant_msg = "One helpful technique is to add print statements with timestamps to visualize the execution order. You can use datetime.now() to see exactly when each coroutine runs. This helps identify race conditions."

conversation = f"User: {user_msg}\n\nAssistant: {assistant_msg}"

print("Calling Claude...")
print()

message = claude_client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=PRIVACY_PROMPT,
    messages=[{
        "role": "user",
        "content": f"Analyze this conversation and extract any shareable insights:\n\n{conversation}"
    }]
)

response_text = message.content[0].text

print("=" * 60)
print("CLAUDE'S RAW RESPONSE:")
print("=" * 60)
print(response_text)
print("=" * 60)
print()

try:
    result = json.loads(response_text)
    print("✓ Successfully parsed as JSON!")
    print()
    print(json.dumps(result, indent=2))
except json.JSONDecodeError as e:
    print(f"✗ JSON Parse Error: {e}")
    print(f"Response starts with: {response_text[:100]}")
