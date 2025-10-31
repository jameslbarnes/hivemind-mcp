# Using Hivemind with Claude Desktop

Claude Desktop uses **stdio transport**, not HTTP remote connectors.

## Setup for Claude Desktop

### Step 1: Find your config file

Windows location:
```
%APPDATA%\Claude\claude_desktop_config.json
```

(Usually: `C:\Users\YOUR_NAME\AppData\Roaming\Claude\claude_desktop_config.json`)

### Step 2: Add Hivemind to the config

Edit `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "python",
      "args": [
        "C:\\Users\\james\\scribe\\hivemind-mcp\\src\\mcp_server.py"
      ],
      "env": {
        "HIVEMIND_TEE_API": "http://localhost:8000"
      }
    }
  }
}
```

**Important**: Update the path to match where your `mcp_server.py` file is located.

### Step 3: Restart Claude Desktop

Close and reopen Claude Desktop completely.

### Step 4: Test it

In a new chat, try:
```
Use the hivemind tools to list my spaces
```

---

## For Claude.ai Web (Different!)

If you want to use **Claude.ai in your browser** (not Claude Desktop), then:

1. Go to https://claude.ai
2. Go to Settings → Connectors
3. Add custom connector
4. Enter: `https://004c19c34d30.ngrok-free.app/mcp/sse`
5. Click Add

---

## Which Should You Use?

### Use Claude Desktop if:
- You want local-only setup
- You prefer the desktop app
- No HTTPS/ngrok needed

### Use Claude.ai Web if:
- You have Pro/Max/Team/Enterprise plan
- You want remote access
- You want to share the server with others

---

## Current Status

You have **both options ready**:
- ✅ stdio server: `src/mcp_server.py` (for Claude Desktop)
- ✅ HTTP server: `https://004c19c34d30.ngrok-free.app` (for Claude.ai web)

Which one do you want to use?
