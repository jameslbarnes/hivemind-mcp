#!/usr/bin/env python3
"""
Hivemind TEE API - Complete Implementation

Runs in TEE (dstack). This is the trust anchor.
"""

import os
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import anthropic
from google.cloud import firestore

app = FastAPI(title="Hivemind TEE API")
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
db = firestore.Client()
insights_collection = db.collection("insights")


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

Extract valuable insights from conversations while protecting privacy.

Look for insights in ANY domain: technical, career, life, creative, personal growth.
Key question: "Would this help someone else in the group?"

PRIVACY RULES (STRICT):
- Remove: names, companies, health diagnoses, financial details, locations
- Preserve: general context, emotional tone, expertise demonstrated

Return JSON:
{
  "shareable": true/false,
  "insight": "2-4 sentence anonymized insight",
  "category": "technical/career/life/creative/learning/other",
  "subcategory": "specific area",
  "confidence": 0.0-1.0,
  "sensitivity": 0.0-1.0,
  "tags": ["keywords"],
  "expertise_areas": ["areas"],
  "reason": "why shareable or not"
}

Share if: confidence > 0.6, sensitivity < 0.6, generalizable, no third-party PII.
When in doubt, protect privacy."""


async def extract_insight_from_conversation(turn: ConversationTurn) -> dict:
    """Run privacy prompt to extract insight"""
    
    conversation = f"User: {turn.user_message}\n\nAssistant: {turn.assistant_message}"
    
    try:
        message = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=PRIVACY_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Analyze this conversation and extract any shareable insights:\n\n{conversation}"
            }]
        )
        
        # Parse JSON response
        response_text = message.content[0].text
        result = json.loads(response_text)
        return result
        
    except Exception as e:
        print(f"Error extracting insight: {e}")
        return {"shareable": False, "reason": f"Error: {str(e)}"}


@app.post("/extract_insight")
async def extract_insight(turn: ConversationTurn) -> InsightResponse:
    """
    Main endpoint: Extract and optionally store insight
    This runs in TEE - users trust this code via attestation
    """
    
    # Run privacy prompt
    result = await extract_insight_from_conversation(turn)
    
    # If not shareable, return immediately
    if not result.get("shareable"):
        return InsightResponse(
            shared=False,
            reason=result.get("reason", "Not shareable")
        )
    
    # Write to Firestore (only anonymized insight gets stored)
    try:
        insight_doc = {
            "insight": result["insight"],
            "category": result.get("category", "other"),
            "subcategory": result.get("subcategory", ""),
            "tags": result.get("tags", []),
            "expertise_areas": result.get("expertise_areas", []),
            "confidence": result.get("confidence", 0.0),
            "sensitivity": result.get("sensitivity", 0.0),
            "timestamp": datetime.fromisoformat(turn.timestamp),
            
            # Attribution (with consent)
            "display_name": turn.user_config.get("display_name"),
            "contact_method": turn.user_config.get("contact_method"),
            "contact_preference": turn.user_config.get("contact_preference", "just_sharing"),
        }
        
        doc_ref = insights_collection.add(insight_doc)
        
        return InsightResponse(
            shared=True,
            insight_preview=result["insight"][:100] + "...",
            reason=result.get("reason")
        )
        
    except Exception as e:
        print(f"Error writing to Firestore: {e}")
        return InsightResponse(
            shared=False,
            reason=f"Storage error: {str(e)}"
        )


@app.get("/read_insights")
async def read_insights(limit: int = 10, category: Optional[str] = None):
    """Read recent insights from Firestore"""
    
    try:
        query = insights_collection.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        
        if category:
            query = query.where("category", "==", category)
        
        docs = query.stream()
        insights = []
        
        for doc in docs:
            data = doc.to_dict()
            insights.append(data)
        
        return {"insights": insights}
        
    except Exception as e:
        print(f"Error reading insights: {e}")
        return {"insights": [], "error": str(e)}


@app.post("/query_insights")
async def query_insights(query_data: dict):
    """Search insights by tags/keywords"""
    
    query_text = query_data.get("query", "")
    limit = query_data.get("limit", 10)
    
    # Simple keyword matching for now
    # TODO: Implement vector search for semantic matching
    keywords = query_text.lower().split()
    
    try:
        # Get all recent insights and filter by keywords
        docs = insights_collection.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit * 3).stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict()
            
            # Check if any keyword matches tags or insight text
            insight_text = data.get("insight", "").lower()
            tags = [t.lower() for t in data.get("tags", [])]
            
            if any(kw in insight_text or kw in tags for kw in keywords):
                results.append(data)
                
                if len(results) >= limit:
                    break
        
        return {"insights": results}
        
    except Exception as e:
        print(f"Error querying insights: {e}")
        return {"insights": [], "error": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "hivemind-tee-api"}


@app.get("/prompt_hash")
async def get_prompt_hash():
    """Return hash of privacy prompt for verification"""
    import hashlib
    prompt_hash = hashlib.sha256(PRIVACY_PROMPT.encode()).hexdigest()
    return {
        "prompt_hash": prompt_hash,
        "prompt": PRIVACY_PROMPT  # Users can verify this matches what they expect
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
