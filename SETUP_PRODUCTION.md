# Production Setup Guide

## Overview

This guide sets up the full production Hivemind system with:
- Firestore for persistent storage
- MCP server for Claude Code integration
- Web app for consent/approval UI
- End-to-end workflow

## Prerequisites

1. **Google Cloud Account**
   - Create project at https://console.cloud.google.com
   - Enable Firestore API
   - Create service account with Firestore permissions

2. **Python 3.10+**

3. **Claude Code** (latest version)

## Step 1: Google Cloud Setup

### 1.1 Create Project

```bash
# Install gcloud CLI
# Visit: https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login

# Create project
gcloud projects create hivemind-prod-XXXXX
gcloud config set project hivemind-prod-XXXXX

# Enable Firestore
gcloud services enable firestore.googleapis.com
```

### 1.2 Create Firestore Database

```bash
# Go to console
open https://console.cloud.google.com/firestore

# Or via CLI:
gcloud firestore databases create --location=us-central1
```

### 1.3 Create Service Account

```bash
# Create service account
gcloud iam service-accounts create hivemind-server \\
    --display-name="Hivemind MCP Server"

# Grant Firestore permissions
gcloud projects add-iam-policy-binding hivemind-prod-XXXXX \\
    --member="serviceAccount:hivemind-server@hivemind-prod-XXXXX.iam.gserviceaccount.com" \\
    --role="roles/datastore.user"

# Download key
gcloud iam service-accounts keys create ~/hivemind-key.json \\
    --iam-account=hivemind-server@hivemind-prod-XXXXX.iam.gserviceaccount.com
```

## Step 2: Install Dependencies

```bash
cd hivemind-mcp

# Install all dependencies
pip install -r requirements.txt

# Specifically:
pip install google-cloud-firestore flask mcp
```

## Step 3: Configure Environment

### 3.1 Create `.env` file

```bash
cp .env.example .env
```

Edit `.env`:
```env
FIRESTORE_PROJECT=hivemind-prod-XXXXX
GOOGLE_APPLICATION_CREDENTIALS=/Users/you/hivemind-key.json
```

### 3.2 Load Environment

```bash
# Option A: Use python-dotenv (recommended)
pip install python-dotenv

# Option B: Export manually
export FIRESTORE_PROJECT=hivemind-prod-XXXXX
export GOOGLE_APPLICATION_CREDENTIALS=/Users/you/hivemind-key.json
```

## Step 4: Test Firestore Connection

```bash
python test_firestore.py
```

Expected output:
```
✓ Firestore connection successful!
✓ Created test user
✓ Created test space
✓ All systems operational
```

## Step 5: Configure Claude Code

### 5.1 Find Config File

**Windows:**
```
C:\\Users\\YOUR_USERNAME\\AppData\\Roaming\\Claude\\claude_desktop_config.json
```

**Mac:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 5.2 Add Hivemind MCP Server

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "python",
      "args": [
        "C:\\\\Users\\\\james\\\\scribe\\\\hivemind-mcp\\\\src\\\\mcp_server_v2.py"
      ],
      "env": {
        "FIRESTORE_PROJECT": "hivemind-prod-XXXXX",
        "GOOGLE_APPLICATION_CREDENTIALS": "C:\\\\Users\\\\you\\\\hivemind-key.json"
      }
    }
  }
}
```

**Mac/Linux example:**
```json
{
  "mcpServers": {
    "hivemind": {
      "command": "python3",
      "args": [
        "/Users/james/scribe/hivemind-mcp/src/mcp_server_v2.py"
      ],
      "env": {
        "FIRESTORE_PROJECT": "hivemind-prod-XXXXX",
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/you/hivemind-key.json"
      }
    }
  }
}
```

### 5.3 Restart Claude Code

1. Quit Claude Code completely
2. Restart it
3. Open developer tools (if available) to see MCP connection logs

## Step 6: Test MCP Integration

In Claude Code, try:

```
Can you set up my Hivemind account?
Name: Andrew Miller
Email: andrew@example.com
```

Claude should call the `setup_hivemind` tool.

Then:
```
Create a couples space called "Andrew & Jamila"
```

Claude should call `create_space` and give you an invite code.

## Step 7: Start Web App

```bash
cd hivemind-mcp
python web_app.py
```

Visit: http://localhost:5000

## Step 8: Test End-to-End Workflow

### Full Scenario:

1. **In Claude Code:**
   ```
   Create a couples space called "Andrew & Jamila"
   ```
   - Claude creates space
   - Returns invite code (e.g., `F7D6F71B`)

2. **In Web App:**
   - Login as "Jamila"
   - Join space with invite code
   - See Andrew's space in your list

3. **In Claude Code:**
   ```
   I'm feeling stressed about work deadlines lately.
   It's affecting my sleep.
   ```
   - Claude logs conversation
   - Routes through policy engine
   - Shares to couples space (emotional state)
   - May queue for approval if sensitive

4. **In Web App:**
   - Check http://localhost:5000/approvals
   - See pending approval (if flagged)
   - Review filtered content
   - Approve/reject

5. **In Claude Code:**
   ```
   What did I mention last time about being stressed?
   ```
   - Claude calls `read_space`
   - Gets context from couples space
   - References previous conversation

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Claude Code    │     │   Web Browser   │
│                 │     │  (port 5000)    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  MCP Server v2  │     │   Flask App     │
│  (stdio)        │     │   (HTTP)        │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ FirestoreSpaceManager │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Google Firestore     │
         │  (Cloud Database)     │
         └───────────────────────┘
```

## Data Flow

### Creating a Space

```
User → Claude Code → MCP Tool → FirestoreManager → Firestore
                                        ↓
                              Returns invite code
                                        ↓
                    User shares code via Signal/email
                                        ↓
                    Other user joins via Web App
                                        ↓
                              Both see space in Firestore
```

### Logging a Conversation

```
User talks to Claude
         ↓
Claude calls log_conversation
         ↓
MCP Server → PolicyEngine → Routes to spaces
         ↓                         ↓
  Firestore ←────────────────────────
    (stores raw + filtered)
         ↓
If needs approval → Approval Queue
         ↓
User sees in Web App → Approves
         ↓
Shared to space
```

## Firestore Collections

```
/users/{user_id}
  - display_name
  - contact_method
  - spaces[]

/spaces/{space_id}
  - name
  - space_type
  - members[]
  - policy
  - invite_code

/filtered_documents/{doc_id}
  - space_id
  - content
  - topics
  - created_at

/pending_approvals/{approval_id}
  - user_id
  - space_id
  - proposed_content
  - status

/raw_conversations/{turn_id}
  - user_id
  - user_message
  - assistant_message
```

## Troubleshooting

### MCP Server Not Connecting

1. Check Claude Code logs
2. Verify paths in `claude_desktop_config.json`
3. Test MCP server manually:
   ```bash
   python src/mcp_server_v2.py
   ```

### Firestore Errors

1. Verify credentials:
   ```bash
   gcloud auth application-default print-access-token
   ```

2. Check permissions:
   ```bash
   gcloud projects get-iam-policy hivemind-prod-XXXXX
   ```

3. Test connection:
   ```python
   from google.cloud import firestore
   db = firestore.Client(project="hivemind-prod-XXXXX")
   print(list(db.collections()))
   ```

### Web App Issues

1. Check if Firestore env vars are set
2. Verify Flask is running: `http://localhost:5000`
3. Check browser console for errors

## Security Considerations

### Production Checklist

- [ ] Use service account with minimal permissions
- [ ] Enable Firestore security rules
- [ ] Add authentication to web app
- [ ] Use HTTPS for web app
- [ ] Rotate service account keys regularly
- [ ] Enable audit logging
- [ ] Set up backup/disaster recovery

### Firestore Security Rules

Create rules in Firebase Console:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can read/write their own user doc
    match /users/{userId} {
      allow read, write: if request.auth.uid == userId;
    }

    // Space access control
    match /spaces/{spaceId} {
      allow read: if resource.data.members[].user_id.hasAny([request.auth.uid]);
      allow write: if request.auth.uid in resource.data.members[].user_id;
    }

    // Documents in spaces user is member of
    match /filtered_documents/{docId} {
      allow read: if exists(/databases/$(database)/documents/spaces/$(resource.data.space_id))
        && get(/databases/$(database)/documents/spaces/$(resource.data.space_id)).data.members[].user_id.hasAny([request.auth.uid]);
    }

    // User's own approvals
    match /pending_approvals/{approvalId} {
      allow read, write: if resource.data.user_id == request.auth.uid;
    }
  }
}
```

## Next Steps

Once everything is working:

1. **Invite Others** - Share invite codes with your group
2. **Customize Policies** - Adjust filtering rules per space
3. **Monitor Usage** - Check Firestore console for activity
4. **Scale Up** - Add more spaces and users
5. **Add Features** - Member roles, space settings, search, etc.

## Support

- Issues: https://github.com/anthropics/hivemind-mcp/issues
- Docs: See `WEB_APP_README.md`, `TRANSCRIPT_REVIEW.md`
- Questions: Check the web app at http://localhost:5000

---

*Last updated: January 2025*
*Status: Production-ready with Firestore integration*
