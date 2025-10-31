from src.json_helper import parse_json_response

# The actual response from Claude (with markdown fences)
test_response = """```json
{
  "shareable": true,
  "insight": "Test",
  "category": "technical"
}
```"""

result = parse_json_response(test_response)
print("[OK] Parsed successfully!")
print("Result:", result)
