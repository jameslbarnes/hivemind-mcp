# How to Connect Hivemind to Claude Code

## What You Just Built

You created a space in the **web app** (http://localhost:5000). Now you want to connect it to **Claude Code** so conversations automatically flow through your policies.

## Current Status

✅ **Web App**: Running at http://localhost:5000
✅ **Backend**: SpaceManager + PolicyEngine working
❌ **MCP Server**: Not yet connected to Claude Code

## Option 1: Quick Integration (Update Existing MCP Server)

### Step 1: Find Your MCP Config

Claude Code's MCP servers are configured in:
```
Windows: C:\Users\james\AppData\Roaming\Claude\claude_desktop_config.json
Mac: ~/Library/Application Support/Claude/claude_desktop_config.json
```

### Step 2: Add Hivemind MCP Server

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "python",
      "args": [
        "C:\\Users\\james\\scribe\\hivemind-mcp\\src\\mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

### Step 3: Update the MCP Server

The existing `src/mcp_server.py` needs new tools. Let me create them:

**New Tools Needed:**
1. `create_space` - Create a new space
2. `join_space` - Join with invite code
3. `list_my_spaces` - See your spaces
4. `log_conversation` - Enhanced with routing
5. `view_pending_approvals` - See what needs approval
6. `approve_content` - Approve/reject pending items

### Step 4: Restart Claude Code

After updating config:
1. Quit Claude Code completely
2. Restart it
3. The Hivemind tools will appear

## Option 2: Test with Standalone MCP Server (Faster)

### Step 1: Create Simple Test Server

Let me create a minimal MCP server just for testing:

```bash
cd hivemind-mcp
python test_mcp_server.py
```

### Step 2: Connect to Claude

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "hivemind-test": {
      "command": "python",
      "args": ["C:\\Users\\james\\scribe\\hivemind-mcp\\test_mcp_server.py"]
    }
  }
}
```

## What Happens When Connected

### Workflow:

1. **You talk to Claude**
   ```
   User: "I'm feeling stressed about work"
   ```

2. **Claude calls MCP tool**
   ```python
   log_conversation(
       user_message="I'm feeling stressed about work",
       assistant_message="That sounds difficult..."
   )
   ```

3. **Backend routes through policies**
   ```python
   # PolicyEngine checks all your spaces
   results = route_conversation(turn, user_id)

   # Routes to relevant spaces
   # - Couples space: SHARED (emotional state)
   # - Work space: SKIPPED (personal)
   # - Public feed: APPROVAL_NEEDED (sensitive)
   ```

4. **You see it in web app**
   - Go to http://localhost:5000/approvals
   - See pending approval for public feed
   - Review and approve/reject

5. **Claude gets context next time**
   ```python
   # Claude calls:
   read_space(space_id="couples_space")

   # Returns filtered conversations
   # Claude uses this as context
   ```

## Current Limitation

**Problem**: Right now, the web app and MCP server use **different instances** of SpaceManager (in-memory).

**Solution Options:**

### A. Shared File Storage (Quick Fix)
```python
# Both web app and MCP server read/write to:
# C:\Users\james\scribe\hivemind-mcp\data\spaces.json

import json

class SharedSpaceManager:
    def __init__(self):
        self.data_file = "data/spaces.json"
        self.load()

    def load(self):
        with open(self.data_file) as f:
            data = json.load(f)
            # Load spaces, users, etc.

    def save(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.to_dict(), f)
```

### B. HTTP API (Better)
```python
# Web app exposes API endpoints
# MCP server makes HTTP calls

# In web_app.py:
@app.route('/api/spaces', methods=['GET'])
def api_list_spaces():
    return jsonify(spaces)

# In MCP server:
import httpx

async def create_space(name, space_type):
    response = httpx.post(
        'http://localhost:5000/api/spaces',
        json={'name': name, 'space_type': space_type}
    )
    return response.json()
```

### C. Firestore (Production)
```python
# Both web app and MCP server use Firestore
# Data is always in sync
# No file conflicts
# Real-time updates
```

## Next Steps

### Immediate (Choose One):

**Option A: Quick File-Based Integration** (30 min)
- I'll create shared JSON file storage
- Both web app and MCP server use it
- You can test end-to-end immediately

**Option B: HTTP API Integration** (1 hour)
- I'll add API endpoints to web app
- MCP server calls the API
- More robust, easier to debug

**Option C: Full MCP Server** (2 hours)
- I'll create complete MCP server with all tools
- Integrate with existing infrastructure
- Production-ready

### Which would you like me to build?

## What You'll Be Able to Do

Once connected:

```
You: "Hey Claude, create a couples space for me and Jamila"
Claude: [calls create_space tool]
Claude: "Created space 'You & Jamila'! Invite code: F7D6F71B"

You: "I'm feeling stressed about the deadline"
Claude: [calls log_conversation]
Claude: "I've noted that. Based on your policies, this was shared to your couples space (emotional state) but not to your work space."

You: "What did we talk about last week?"
Claude: [calls read_space("couples")]
Claude: "Last week you mentioned feeling stressed about work..."
```

## Current Architecture

```
┌─────────────────┐
│   Web Browser   │ ← You manage spaces here
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Flask App     │ ← http://localhost:5000
│  (web_app.py)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SpaceManager   │ ← In-memory (Instance #1)
│  PolicyEngine   │
└─────────────────┘


┌─────────────────┐
│  Claude Code    │ ← Not yet connected!
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   MCP Server    │ ← Needs to be created
│  (to be built)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SpaceManager   │ ← In-memory (Instance #2) ⚠️
│  PolicyEngine   │    Different from web app!
└─────────────────┘
```

## Target Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Web Browser   │     │  Claude Code    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   Flask App     │     │   MCP Server    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
           ┌─────────────────┐
           │ Shared Storage  │ ← JSON file or Firestore
           │  (spaces.json)  │
           └─────────────────┘
                     ▼
           ┌─────────────────┐
           │  SpaceManager   │ ← Single source of truth
           │  PolicyEngine   │
           └─────────────────┘
```

## Tell Me What You Want

1. **Quick test** - File-based storage (30 min)
2. **Better integration** - HTTP API (1 hour)
3. **Production ready** - Full MCP + Firestore (2 hours)
4. **Just explore web app** - Keep testing the UI

What would you like to do next?
