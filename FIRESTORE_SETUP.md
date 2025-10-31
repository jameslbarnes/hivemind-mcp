# Firestore Setup Guide

This guide walks you through setting up Firestore for persistent storage in Hivemind.

## Why Firestore?

- ✅ **Persistent storage** - Data survives server restarts
- ✅ **Shared state** - Web app and MCP server access the same data
- ✅ **Production-ready** - Scalable and reliable
- ✅ **No more auth loss** - OAuth credentials persist across restarts

## Quick Setup (5 minutes)

### Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or select an existing project
3. Follow the setup wizard (you can disable Google Analytics if you don't need it)

### Step 2: Enable Firestore

1. In your Firebase project, go to **Build → Firestore Database**
2. Click **Create database**
3. Choose **Start in production mode** (we'll set up rules later)
4. Select a location (choose one close to you)
5. Click **Enable**

### Step 3: Generate Service Account Credentials

1. In Firebase Console, go to **Project Settings** (gear icon)
2. Go to the **Service accounts** tab
3. Click **Generate new private key**
4. Save the JSON file as `firebase-credentials.json` in your `hivemind-mcp` directory

**⚠️ Important:** Add this file to `.gitignore`! Never commit credentials to git.

### Step 4: Set Environment Variable

Add this line to your terminal or `.env` file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/hivemind-mcp/firebase-credentials.json"
```

**Windows (PowerShell):**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\james\scribe\hivemind-mcp\firebase-credentials.json"
```

**Windows (CMD):**
```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\james\scribe\hivemind-mcp\firebase-credentials.json
```

### Step 5: Start the Servers

That's it! Both servers will now use Firestore automatically:

```bash
python web_app.py
```

```bash
python src/remote_mcp_server_fixed.py
```

You should see: `✅ Firestore backend initialized`

## Data Structure

Firestore will create these collections automatically:

```
firestore/
  ├── users/              # User accounts with OAuth credentials
  ├── spaces/             # Spaces with policies
  └── conversations/      # Conversation history
```

## Firestore Security Rules

Set these up in Firebase Console → Firestore Database → Rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow authenticated service accounts (your servers)
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

## Troubleshooting

### "Firestore initialization failed"

**Solution**: The system will automatically fall back to in-memory storage. Check:
1. Is `GOOGLE_APPLICATION_CREDENTIALS` set correctly?
2. Does the credentials file exist at that path?
3. Is the file valid JSON?

### "Permission denied"

**Solution**: Update your Firestore security rules (see above)

### Want to disable Firestore temporarily?

Start servers with in-memory mode:

```python
# In web_app.py or remote_mcp_server_fixed.py
space_manager = SpaceManager(use_firestore=False)
```

## Viewing Your Data

1. Go to Firebase Console → Firestore Database
2. Browse collections: `users`, `spaces`, `conversations`
3. You can manually edit, add, or delete data here

## Next Steps

- Set up Firestore indexes for better query performance
- Configure backup schedules in Firebase Console
- Set up monitoring and alerts
- Consider upgrading to Blaze (pay-as-you-go) plan for production

## Support

- [Firestore Documentation](https://firebase.google.com/docs/firestore)
- [Python Admin SDK](https://firebase.google.com/docs/admin/setup)
