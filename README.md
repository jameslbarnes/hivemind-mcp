# Hivemind MCP

**Asynchronous group mind for trusted networks**

Transform para-social LLM conversations into pro-social human connections. Share anonymized insights from your Claude conversations with your team, find others who can help, and maintain ambient awareness of what your people are learning and thinking about.

## Architecture

```
User's Machine                    TEE (dstack)                 Storage
─────────────                    ─────────────                ─────────

MCP Server                        Privacy Prompt              Firestore
  ├─ log_conversation_turn() ──→   ├─ Extract insight          insights/
  ├─ read_hivemind()          ←────┤ ├─ Anonymize PII           ├─ insight1
  └─ query_hivemind()         ←────┘ ├─ Check sensitivity       ├─ insight2
                                     └─ Write if approved ────→  └─ ...
```

## Core Principles

1. **Privacy by Default**: Raw conversations never leave your machine or the TEE
2. **Trusted Execution**: Privacy prompt runs in verified TEE (dstack)
3. **Human Connection**: Insights include attribution and contact info (with consent)
4. **Trust Networks**: Designed for groups who already know each other

## Components

- **MCP Server** (`src/mcp_server.py`): Thin client, three tools (log/read/query)
- **TEE API** (`src/tee_api.py`): Privacy prompt, runs in dstack TEE
- **Firestore Client** (`src/firestore_client.py`): Manages insights storage
- **Web Feed** (`web/`): Public feed showing what the group is exploring

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure Firestore
cp config/firestore.example.json config/firestore.json
# Edit with your credentials

# Run MCP server locally
python src/mcp_server.py

# Deploy TEE API to dstack
dstack run tee_api
```

## Usage

Once configured with Claude:

```
User: "What's the team exploring today?"

Claude: [calls read_hivemind()]

• Alex is diving into MEV strategies
  "Been thinking about block building optimizations..."
  [Open to discussing]

• Sarah discovered a Rust debugging technique
  "Using cargo-expand to understand macro expansions..."
  [Happy to share examples]

• Someone is learning distributed consensus
  "Raft makes more sense when you think of it as..."
  [Available for questions]
```

## First Users

Built for the Flashbots team - technical depth with human warmth.

## Future: Private Trust Networks

Prototype uses single public feed. Future: separate feeds per trust network (team, cohort, friends).

## BCI Connection

This is a prototype for brain-computer interface collective intelligence. The TEE is the neural firewall, the privacy prompt is the policy for what thoughts to share.
