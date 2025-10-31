# Hivemind Web App

## What This Is

A Flask web application that provides a visual interface for managing spaces, invite codes, and the **consent layer** (approval workflow) for the Hivemind multi-space system.

## Key Features

### 1. Space Management
- Create spaces with different types (1:1, group, public)
- Join spaces using invite codes
- View space members and policies
- Browse conversation feeds

### 2. Invite Code System
- Each space gets an 8-character invite code
- Share codes to invite others
- Simple join workflow
- Member notifications

### 3. Approval Workflow (THE KEY FEATURE!)
- Review content before it's shared
- See filtered/transformed content
- Approve, edit, or reject
- Confidence and sensitivity scores

### 4. Notifications
- Get notified when people join your spaces
- See when content is shared
- Track approval requests

## How to Run

```bash
cd hivemind-mcp
python web_app.py
```

Then visit: **http://localhost:5000**

## Quick Start

1. **Login** - Enter any username (demo mode, no password)
2. **Create a Space** - Choose type and policy template
3. **Get Invite Code** - Share with others
4. **Test Routing** - Use the simulator on dashboard
5. **Approve Content** - Visit the Approvals page

## Architecture

```
web_app.py (Flask routes)
├── templates/
│   ├── base.html (layout)
│   ├── dashboard.html (main page)
│   ├── create_space.html
│   ├── join_space.html
│   ├── view_space.html
│   ├── approvals.html (consent layer!)
│   └── notifications.html
├── static/
│   └── css/
│       └── style.css
└── src/
    ├── space_manager.py (backend logic)
    └── policy_engine.py (routing logic)
```

## Alignment with Transcript

From the transcript, the key quote:

> "you want, like, a really easy consent layer... it could even be in the, you know, an MCP server... can wait for a response back from the server... it like bounces what you just said against all of your policies and says, Hey, I think this might be good to share with this group you want to and then you say, oh, yeah, like, I do or I don't"

This web app implements exactly that:
- Content is processed through policies
- High-sensitivity content goes to approval queue
- User reviews and decides (approve/edit/reject)
- Policies learn from feedback (future enhancement)

## What Works Now

✓ User login (simple demo mode)
✓ Create spaces with policy templates
✓ Join spaces with invite codes
✓ View space details and members
✓ Simulate conversation routing
✓ View pending approvals
✓ Approve/edit/reject content
✓ Notifications when people join

## What's Missing (Future)

- Real authentication
- Firestore persistence (currently in-memory)
- Real-time updates (websockets)
- Member management (remove, roles)
- Invite expiration/revocation
- Public feed discovery
- Meta-agent for policy customization

## Integration with MCP

This web app runs standalone, but it uses the same `SpaceManager` and `PolicyEngine` that the MCP server will use.

**Next step**: Create MCP tools that call the same backend logic, so Claude can:
- Create spaces
- Process conversations through policies
- Send approvals to this web UI
- Read from spaces for context

## Testing

Try this workflow:

1. Login as "Andrew"
2. Create a couples space (get invite code)
3. Logout, login as "Jamila"
4. Join Andrew's space with the code
5. Logout, login as "Andrew" again
6. Use the simulator: "I'm feeling stressed about work"
7. See it route to the couples space
8. If flagged for approval, check Approvals page

## Files Created

- `web_app.py` - Main Flask application (400+ lines)
- `templates/base.html` - Base template with nav
- `templates/index.html` - Landing page
- `templates/login.html` - Login page
- `templates/dashboard.html` - Main dashboard with simulator
- `templates/create_space.html` - Create space form
- `templates/join_space.html` - Join with invite code
- `templates/view_space.html` - Space details and feed
- `templates/approvals.html` - Consent layer UI
- `templates/notifications.html` - Notifications list
- `static/css/style.css` - Complete styling (500+ lines)

## Demo Video Walkthrough

(To be recorded - showing full workflow from space creation to approval)

---

*Built in Session: January 2025*
*Status: Phase 3.5 - Web UI Complete*
*Next: MCP Integration*
