# Local Setup Guide

Get Hivemind running on your machine for testing.

## Prerequisites

- Python 3.11+
- Anthropic API key
- Google Cloud Firestore project

## Step 1: Install Dependencies

```bash
cd hivemind-mcp
pip install -r requirements.txt
```

## Step 2: Set Up Firestore

1. Create a Firestore project in Google Cloud Console
2. Create a service account with Firestore access
3. Download the credentials JSON file
4. Create a collection called `insights` (it will auto-create when first insight is added)

## Step 3: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your values
# - Add your ANTHROPIC_API_KEY
# - Add your FIRESTORE_PROJECT id
# - Add path to your credentials JSON
```

## Step 4: Initialize Consent

```bash
python hivemind_cli.py init
```

Follow the prompts to set up your sharing preferences.

## Step 5: Start the TEE API (locally)

In one terminal:

```bash
# Load environment variables
source .env  # or: export $(cat .env | xargs) on Windows

# Run the TEE API
python src/tee_api.py
```

This starts the API on `http://localhost:8000`

## Step 6: Test the API

In another terminal:

```bash
# Test health check
curl http://localhost:8000/health

# Test prompt hash (verify the privacy prompt)
curl http://localhost:8000/prompt_hash
```

## Step 7: Configure Claude Desktop

Add to your Claude Desktop MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "python",
      "args": ["/full/path/to/hivemind-mcp/src/mcp_server.py"],
      "env": {
        "HIVEMIND_TEE_API": "http://localhost:8000"
      }
    }
  }
}
```

## Step 8: Test with Claude

1. Restart Claude Desktop
2. Start a conversation
3. Try: "What's the hivemind talking about?"
4. Or manually log a turn (Claude will offer this if MCP server is detected)

## Troubleshooting

**MCP server not showing up:**
- Check Claude Desktop logs
- Verify python path is correct
- Make sure src/mcp_server.py is executable

**TEE API errors:**
- Check environment variables are loaded
- Verify Firestore credentials are valid
- Check ANTHROPIC_API_KEY is set

**No insights appearing:**
- Run `python hivemind_cli.py config` to verify sharing is enabled
- Check TEE API logs for extraction errors
- Try lowering confidence threshold in privacy prompt

## Next Steps

Once working locally:
1. Deploy TEE API to dstack
2. Update MCP server to point to remote TEE API
3. Share the web feed URL with your team
