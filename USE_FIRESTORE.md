# Connecting Web App and MCP Server with Firestore

## The Problem

Currently:
- Web app (port 5000) has its own in-memory `SpaceManager`
- MCP server (port 8080) has its own in-memory `SpaceManager`
- They don't share data!

## The Solution: Firestore

Use `FirestoreSpaceManager` instead of `SpaceManager` in both servers. They'll read/write to the same Firestore database.

## Setup Steps

### 1. Get Firestore Ready

1. Go to https://console.cloud.google.com
2. Create a project (e.g., "hivemind-prod")
3. Enable Firestore:
   - Navigation menu → Firestore Database
   - Click "Create Database"
   - Choose location (e.g., us-central1)
   - Start in "Production mode"
4. Create service account:
   - IAM & Admin → Service Accounts
   - "Create Service Account"
   - Name: "hivemind-server"
   - Role: "Cloud Datastore User"
   - Click "Create Key" → JSON
   - Download the JSON file to a safe location

### 2. Set Environment Variables

**Windows (PowerShell)**:
```powershell
$env:FIRESTORE_PROJECT="your-project-id"
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account-key.json"
```

**Windows (CMD)**:
```cmd
set FIRESTORE_PROJECT=your-project-id
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account-key.json
```

**Linux/Mac**:
```bash
export FIRESTORE_PROJECT="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### 3. Update Servers to Use Firestore

Edit both files to import and use `FirestoreSpaceManager`:

**In `src/remote_mcp_server_fixed.py`**:
```python
# Change this line:
from src.space_manager import SpaceManager

# To this:
from src.firestore_manager import FirestoreSpaceManager as SpaceManager
```

**In `web_app.py`**:
```python
# Change this line:
from src.space_manager import SpaceManager

# To this:
from src.firestore_manager import FirestoreSpaceManager as SpaceManager
```

### 4. Restart Both Servers

```bash
# Kill and restart
python src/remote_mcp_server_fixed.py
python web_app.py
```

### 5. Test It

1. **In web app** (http://localhost:5000):
   - Log in as "james"
   - Create a space called "Test Space"
   - Note the invite code

2. **In Claude Desktop**:
   - Run: "List my spaces"
   - You should see "Test Space"!

## Alternative: Quick Test Without Firestore

If you don't want to set up Firestore yet, use the same user_id in both:

1. **Web app**: Log in as `james`
2. **MCP tools**: When Claude calls tools, it uses `user_id: "james"`

But note: They still won't see each other's data until you enable Firestore.

## User ID Mapping

Once Firestore is enabled:
- Web app user "james" → Firestore user document
- MCP calls with `user_id: "james"` → Same Firestore user document
- Both see the same spaces, members, conversations!

## Checking It Works

After setup, verify both servers are connected:

```bash
# Check Firestore in web console
https://console.cloud.google.com/firestore/data

# You should see collections:
# - users
# - spaces
# - filtered_documents
# - pending_approvals
```

## Troubleshooting

**"FIRESTORE_PROJECT environment variable must be set"**
- Set the environment variable before starting servers

**"Could not automatically determine credentials"**
- Set GOOGLE_APPLICATION_CREDENTIALS to your JSON key file path
- Make sure the path is absolute and file exists

**"Permission denied"**
- Make sure service account has "Cloud Datastore User" role
- Check IAM permissions in Google Cloud Console

## For Production

Once working:
- Deploy to a server with Firestore credentials
- Use environment variables (don't commit keys!)
- Consider using Cloud Run or similar for auto-scaling
