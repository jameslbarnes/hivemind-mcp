#!/usr/bin/env python3
"""
Hivemind TEE API - Mock Version (no Firestore required)

Uses in-memory storage for testing without setting up Firestore.
"""

import os
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv
from json_helper import parse_json_response

# Load environment variables from .env
load_dotenv()

app = FastAPI(title="Hivemind TEE API (Mock)")
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Mock in-memory storage
mock_insights = []


class ConversationTurn(BaseModel):
    user_message: str
    assistant_message: str
    timestamp: str
    user_config: dict


class InsightResponse(BaseModel):
    shared: bool
    insight_preview: Optional[str] = None
    reason: Optional[str] = None


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


async def extract_insight_from_conversation(turn: ConversationTurn) -> dict:
    """Run privacy prompt to extract insight"""

    conversation = f"User: {turn.user_message}

Assistant: {turn.assistant_message}"

    try:
        message = claude_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=PRIVACY_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Analyze this conversation and extract any shareable insights:

{conversation}"
            }]
        )

        # Parse JSON response
        response_text = message.content[0].text
        print()
        print("=" * 60)
        print("CLAUDE'S RAW RESPONSE:")
        print(response_text)
        print("=" * 60)
        print()
        
        result = parse_json_response(response_text)
        return result

    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"First 500 chars: {response_text[:500] if len(response_text) > 500 else response_text}")
        return {"shareable": False, "reason": f"JSON parse error: {str(e)}"}
    except Exception as e:
        print(f"Error extracting insight: {e}")
        return {"shareable": False, "reason": f"Error: {str(e)}"}



@app.post("/extract_insight")
async def extract_insight(turn: ConversationTurn) -> InsightResponse:
    """Main endpoint: Extract and store insight in memory"""

    # Run privacy prompt
    result = await extract_insight_from_conversation(turn)

    # If not shareable, return immediately
    if not result.get("shareable"):
        return InsightResponse(
            shared=False,
            reason=result.get("reason", "Not shareable")
        )

    # Store in memory (mock Firestore)
    insight_doc = {
        "insight": result["insight"],
        "category": result.get("category", "other"),
        "subcategory": result.get("subcategory", ""),
        "tags": result.get("tags", []),
        "expertise_areas": result.get("expertise_areas", []),
        "confidence": result.get("confidence", 0.0),
        "sensitivity": result.get("sensitivity", 0.0),
        "timestamp": turn.timestamp,

        # Attribution (with consent)
        "display_name": turn.user_config.get("display_name"),
        "contact_method": turn.user_config.get("contact_method"),
        "contact_preference": turn.user_config.get("contact_preference", "just_sharing"),
    }

    mock_insights.append(insight_doc)

    return InsightResponse(
        shared=True,
        insight_preview=result["insight"][:100] + "..." if len(result["insight"]) > 100 else result["insight"],
        reason=result.get("reason")
    )


@app.get("/read_insights")
async def read_insights(limit: int = 10, category: Optional[str] = None):
    """Read recent insights from memory"""

    insights = mock_insights.copy()

    # Filter by category if provided
    if category:
        insights = [i for i in insights if i.get("category") == category]

    # Sort by timestamp, most recent first
    insights.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Limit results
    insights = insights[:limit]

    return {"insights": insights}


@app.post("/query_insights")
async def query_insights(query_data: dict):
    """Search insights by keywords"""

    query_text = query_data.get("query", "").lower()
    limit = query_data.get("limit", 10)

    keywords = query_text.split()

    results = []
    for insight_doc in mock_insights:
        insight_text = insight_doc.get("insight", "").lower()
        tags = [t.lower() for t in insight_doc.get("tags", [])]

        if any(kw in insight_text or kw in tags for kw in keywords):
            results.append(insight_doc)

            if len(results) >= limit:
                break

    return {"insights": results}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "hivemind-tee-api-mock",
        "insights_count": len(mock_insights)
    }


@app.get("/prompt_hash")
async def get_prompt_hash():
    """Return hash of privacy prompt for verification"""
    import hashlib
    prompt_hash = hashlib.sha256(PRIVACY_PROMPT.encode()).hexdigest()
    return {
        "prompt_hash": prompt_hash,
        "prompt": PRIVACY_PROMPT
    }


if __name__ == "__main__":
    import uvicorn
    print("Starting Hivemind TEE API (Mock Mode - In-Memory Storage)")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
