"""Helper to strip markdown fences from Claude's JSON responses"""

import json

def parse_json_response(response_text: str) -> dict:
    """
    Parse JSON from Claude's response, stripping markdown code fences if present.

    Claude sometimes wraps JSON in ```json...``` markdown fences.
    This function handles that gracefully.
    """
    cleaned = response_text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]  # Remove ```json
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]  # Remove ```

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]  # Remove trailing ```

    cleaned = cleaned.strip()

    # Parse as JSON
    return json.loads(cleaned)
