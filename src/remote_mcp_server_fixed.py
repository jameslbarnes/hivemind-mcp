#!/usr/bin/env python3
"""
Remote MCP Server for Hivemind (Custom Connector) - FIXED

Properly implements MCP protocol over SSE for Claude custom connectors.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import requests
import secrets
import sys
from typing import Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Sequence

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import anthropic

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource, Prompt

# Hivemind imports
from src.space_manager import SpaceManager
from src.models import (
    RawConversationTurn, SpaceType, ConversationSummaryEntry, ConversationThread
)

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("=" * 70)
logger.info("HIVEMIND MCP SERVER STARTING")
logger.info("=" * 70)

# Initialize Flask
app = Flask(__name__)
CORS(app)  # Enable CORS for remote access

# Get configured user ID from environment (for MCP connections)
CONFIGURED_USER_ID = os.getenv("SCRIBE_USER_ID", "usr_6acf10ca")
logger.info(f"MCP server configured for user: {CONFIGURED_USER_ID}")

# Initialize managers with Firestore
# On Railway, credentials come from GOOGLE_APPLICATION_CREDENTIALS_JSON env var
# Locally, we can use a file path
FIREBASE_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") or r"C:\Users\james\Downloads\hivemind-476519-d174ae36378a.json"

if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    logger.info("Using GOOGLE_APPLICATION_CREDENTIALS_JSON from environment")
else:
    logger.info(f"Using local credentials file: {FIREBASE_CREDS}")

logger.info("Initializing SpaceManager with Firestore...")
try:
    space_manager = SpaceManager(use_firestore=True, credentials_path=FIREBASE_CREDS)
    logger.info("SpaceManager initialized successfully!")
except Exception as e:
    logger.error(f"FAILED to initialize SpaceManager: {e}")
    logger.exception("Full traceback:")
    raise

# Cleanup expired tokens on startup
try:
    deleted_count = space_manager.cleanup_expired_tokens()
    logger.info(f"Startup: Cleaned up {deleted_count} expired tokens")
except Exception as e:
    logger.warning(f"Failed to cleanup expired tokens: {e}")

# MCP Server instance
mcp_server = Server("hivemind-remote")


# ============================================================================
# MCP Tool Handlers
# ============================================================================

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="log_conversation_turn",
            description="Log a conversation to Scribe. Scribe creates structured summaries to build a knowledge graph. Call this after substantive exchanges with insights, decisions, or context worth preserving.",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_summary": {
                        "type": "string",
                        "description": "REQUIRED: A 1-3 sentence summary of THIS specific exchange - what the user asked/said and how you (Claude) responded. Include key points, user intent, and your actions."
                    },
                    "related_context_summary": {
                        "type": "string",
                        "description": "REQUIRED: BEFORE writing anything, search through your message history from PREVIOUS discussions to find related topics, themes, or patterns. Look for connections to earlier exchanges. Summarize any relevant context (e.g., 'This continues our earlier discussion about X' or 'Related to previous conversation about Y' or 'No related previous context found'). This helps build connections across conversations."
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User identifier (defaults to authenticated user)"
                    }
                },
                "required": ["conversation_summary", "related_context_summary"]
            }
        ),
        Tool(
            name="create_space",
            description="Scribe organizes shared context into 'spaces' - containers for different audiences the user wants to share with. A space represents a relationship or group where filtered conversation content flows based on privacy policies. Create a new space when the user wants to start sharing context with someone specific or a group. Space types: '1:1' creates an intimate bilateral space (for partners, close friends, or one-on-one relationships where both people share filtered context with each other), 'group' creates a multi-person collaborative space (for teams, communities, or friend groups working/thinking together), 'public' creates an anonymous broadcasting channel (for sharing curated insights with the world without attribution). Each space has its own privacy policy that determines what types of conversation content get filtered and shared there. The tool returns an invite code that the user can share with others to give them access to the space. Example use: User says 'I want to share relationship context with my partner Jamie' → create a 1:1 space named 'Jamie & [User]' with policy template 'couples'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "A descriptive name for this space (e.g., 'Work Team', 'Family Updates', 'Andrew & Sarah')"
                    },
                    "space_type": {
                        "type": "string",
                        "enum": ["1:1", "group", "public"],
                        "description": "Type of space: '1:1' for one other person, 'group' for teams/communities, 'public' for anonymous public sharing"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User creating the space (defaults to 'default_user')",
                        "default": "default_user"
                    },
                    "policy_template": {
                        "type": "string",
                        "description": "Pre-configured privacy policy: 'couples' for relationship context, 'team' for work collaboration, 'public' for anonymous insights"
                    }
                },
                "required": ["name", "space_type"]
            }
        ),
        Tool(
            name="list_spaces",
            description="In Scribe, users can be members of multiple spaces - each representing a different audience or relationship where they share filtered conversation context. Use this tool to show the user all their spaces, including space names (e.g., 'Work Team', 'Sarah & Alex'), space types (1:1, group, or public), how many members are in each space, and the invite codes they can share to add others. Call this when the user wants to see what spaces they have access to, needs an invite code to share with someone, wants to understand their current sharing contexts, or asks questions like 'what spaces do I have?', 'show me my groups', 'who am I sharing with?', or 'how do I invite someone?'. This provides orientation in their Scribe network.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier (defaults to 'default_user')",
                        "default": "default_user"
                    }
                }
            }
        ),
        Tool(
            name="join_space",
            description="Scribe spaces use invite codes to control membership - when someone creates a space, they receive a code to share with intended members. Use this tool when the user has received an invite code from someone else and wants to join their space. An invite code looks like 'REL-X7K9P' or similar format. Joining a space connects the user to that collaborative context - they'll start receiving filtered content that other members have shared there, and their own future conversations will be routed to that space based on its privacy policy. The tool shows the space's name, type, and privacy policy before completing the join so the user understands what they're agreeing to share. Call this when the user says something like 'I have an invite code', 'someone sent me REL-X7K9P', 'join code ABC123', or asks 'how do I join a space?'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invite_code": {
                        "type": "string",
                        "description": "The invite code provided by an existing space member (format: XXX-XXXXX, e.g., 'REL-X7K9P')"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User joining the space (defaults to 'default_user')",
                        "default": "default_user"
                    }
                },
                "required": ["invite_code"]
            }
        ),
        Tool(
            name="read_space",
            description="Scribe spaces accumulate filtered conversation content from all members - creating a shared context about what people in that space are thinking, feeling, working on, or experiencing. Use this tool to retrieve recent content from a specific space to give you (Claude) important context when helping the user. For example, before giving relationship advice, read the user's 1:1 partner space to understand what emotional context has been shared recently. Before discussing work, read their team space to see what projects are active. Reading a space helps you provide advice that's informed by the broader context of that relationship or group. Call this when: the user mentions someone they have a space with and you need context about that relationship, you're discussing a topic (work, relationships, projects) where space context would improve your advice, the user asks 'what has [person] shared recently?', or you notice the conversation would benefit from understanding what's happening in one of their spaces. Specify a limit parameter to control how much history to retrieve (default 5, use higher for more context).",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {
                        "type": "string",
                        "description": "The unique identifier of the space to read from (get this from list_spaces)"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User reading the space (defaults to 'default_user')",
                        "default": "default_user"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of recent entries to retrieve (default: 5, higher for more history)",
                        "default": 5
                    }
                },
                "required": ["space_id"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict, user_id: str = None) -> Sequence[TextContent]:
    """Handle MCP tool calls."""
    logger.info(f"call_tool - name: {name}, arguments: {arguments}")
    try:
        if name == "log_conversation_turn":
            return await handle_log_conversation(arguments, user_id)
        elif name == "create_space":
            return await handle_create_space(arguments, user_id)
        elif name == "list_spaces":
            return await handle_list_spaces(arguments, user_id)
        elif name == "join_space":
            return await handle_join_space(arguments, user_id)
        elif name == "read_space":
            return await handle_read_space(arguments, user_id)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_log_conversation(args: dict, auth_user_id: str = None) -> Sequence[TextContent]:
    """Handle log_conversation_turn tool with simplified structure."""
    user_id = args.get("user_id") or auth_user_id or CONFIGURED_USER_ID

    logger.info(f"handle_log_conversation - using user_id: {user_id}")
    logger.info(f"handle_log_conversation - received args: {args}")

    # Ensure user exists
    if not space_manager.get_user(user_id):
        space_manager.create_user(user_id, f"{user_id}@example.com")

    # Validate required parameters
    if "conversation_summary" not in args or not args["conversation_summary"]:
        return [TextContent(
            type="text",
            text="Error: 'conversation_summary' is required. Please provide a 1-3 sentence summary of the conversation exchange."
        )]

    if "related_context_summary" not in args or not args["related_context_summary"]:
        return [TextContent(
            type="text",
            text="Error: 'related_context_summary' is required. Please search your message history for related context, or use 'No related previous context found' if none exists."
        )]

    # Extract summaries from new simplified parameters
    conversation_summary = args["conversation_summary"]
    related_context = args["related_context_summary"]

    # Create key points from related context if available
    key_points = []
    if related_context and related_context.lower() != "no related previous context found":
        key_points.append(f"Related context: {related_context}")

    # Create summary entry
    entry = ConversationSummaryEntry(
        summary=conversation_summary,
        key_points=key_points,
        user_intent=conversation_summary,  # Use full summary as user intent
        assistant_action=conversation_summary,  # Use full summary as assistant action
        topics=[],  # No longer using topics parameter
        emotional_tone=None,
        related_entry_ids=[]
    )

    # No threading for now - Claude can't provide thread_id
    thread_id = None

    # Save entry
    space_manager.save_conversation_entry(entry, user_id)

    # Create legacy RawConversationTurn for webhook compatibility
    turn = RawConversationTurn(
        user_id=user_id,
        user_message=f"Conversation summary: {conversation_summary}",
        assistant_message=f"Related context: {related_context}"
    )

    # Call Flask webhook to trigger routing (async)
    try:
        webhook_url = "http://localhost:5000/api/webhook/conversation"
        payload = {
            'turn_id': turn.turn_id,
            'user_id': user_id,
            'user_message': conversation_summary,
            'assistant_message': related_context
        }
        requests.post(webhook_url, json=payload, timeout=1)
    except Exception as e:
        logger.warning(f"Failed to call webhook: {e}")

    response_parts = [f"✓ Conversation summary logged!"]
    response_parts.append(f"Entry ID: {entry.entry_id}")
    response_parts.append("\nThis summary will be routed through your space policies.")
    response_parts.append("Dashboard: http://localhost:5000/dashboard")

    return [TextContent(type="text", text="\n".join(response_parts))]


async def handle_create_space(args: dict, auth_user_id: str = None) -> Sequence[TextContent]:
    """Handle create_space tool."""
    name = args["name"]
    space_type = SpaceType(args["space_type"])
    user_id = args.get("user_id") or auth_user_id or CONFIGURED_USER_ID
    policy_template = args.get("policy_template")

    # Ensure user exists
    if not space_manager.get_user(user_id):
        space_manager.create_user(user_id, f"{user_id}@example.com")

    space = space_manager.create_space(
        user_id, name, space_type, policy_template=policy_template
    )

    response = f"""Created space "{name}" ({space_type.value})
Invite code: {space.invite_code}

Policy: {policy_template or 'default'}
Space ID: {space.space_id}

Share the invite code with others to join!"""

    return [TextContent(type="text", text=response)]


async def handle_list_spaces(args: dict, auth_user_id: str = None) -> Sequence[TextContent]:
    """Handle list_spaces tool."""
    user_id = args.get("user_id") or auth_user_id or CONFIGURED_USER_ID

    spaces = space_manager.list_user_spaces(user_id)

    if not spaces:
        return [TextContent(type="text", text="You don't have any spaces yet. Create one with create_space!")]

    response_lines = ["Your Spaces:\n"]
    for i, space in enumerate(spaces, 1):
        member_count = len(space.members)
        response_lines.append(f"{i}. {space.name} ({space.space_type.value})")
        response_lines.append(f"   Members: {member_count}")
        response_lines.append(f"   Invite code: {space.invite_code}")
        response_lines.append(f"   Space ID: {space.space_id}\n")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def handle_join_space(args: dict, auth_user_id: str = None) -> Sequence[TextContent]:
    """Handle join_space tool."""
    invite_code = args["invite_code"].strip().upper()
    user_id = args.get("user_id") or auth_user_id or CONFIGURED_USER_ID

    # Ensure user exists
    if not space_manager.get_user(user_id):
        space_manager.create_user(user_id, f"{user_id}@example.com")

    # Find space by invite code
    space = None
    for s in space_manager.spaces.values():
        if s.invite_code == invite_code:
            space = s
            break

    if not space:
        return [TextContent(type="text", text=f"Invalid invite code: {invite_code}")]

    success = space_manager.join_space(space.space_id, user_id, invite_code)

    if success:
        response = f"""Successfully joined "{space.name}"!

Space type: {space.space_type.value}
Members: {len(space.members)}
Space ID: {space.space_id}

You'll now receive context from this space and your conversations will be routed here based on the space's policy."""
        return [TextContent(type="text", text=response)]
    else:
        return [TextContent(type="text", text="Failed to join space (already a member or space is full)")]


async def handle_read_space(args: dict, auth_user_id: str = None) -> Sequence[TextContent]:
    """Handle read_space tool."""
    space_id = args["space_id"]
    user_id = args.get("user_id") or auth_user_id or CONFIGURED_USER_ID
    limit = args.get("limit", 5)

    space = space_manager.get_space(space_id)

    if not space:
        return [TextContent(type="text", text=f"Space not found: {space_id}")]

    # Check if user is member
    is_member = any(m.user_id == user_id for m in space.members)
    if not is_member:
        return [TextContent(type="text", text=f"You are not a member of space: {space.name}")]

    response = f"""Recent context from "{space.name}":

(No conversations yet - this space is newly created)

Start logging conversations with log_conversation_turn to populate this space!"""

    return [TextContent(type="text", text=response)]


# ============================================================================
# SSE Message Handling
# ============================================================================

class SSEConnection:
    """Manages an SSE connection with MCP protocol."""

    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.initialized = False
        self.user_id = None

    async def handle_message(self, message: dict) -> dict:
        """Handle incoming MCP JSON-RPC message."""
        method = message.get("method")
        msg_id = message.get("id")

        try:
            if method == "initialize":
                self.initialized = True
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "hivemind-remote",
                            "version": "0.2.0"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }

            elif method == "tools/list":
                tools = await list_tools()
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                            for tool in tools
                        ]
                    }
                }

            elif method == "tools/call":
                params = message.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                result = await call_tool(tool_name, arguments, self.user_id)

                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": item.text}
                            for item in result
                        ]
                    }
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }


# ============================================================================
# Flask Routes
# ============================================================================

@app.route('/', methods=['GET', 'POST'])
def root():
    """Root endpoint."""
    return jsonify({
        "name": "Hivemind Remote MCP",
        "version": "0.2.0",
        "mcp_endpoint": "/mcp/sse"
    })


# Store authorization codes temporarily (in production, use Redis or database)
auth_codes = {}

# Store PKCE code verifiers (client_id -> code_verifier)
pkce_verifiers = {}


@app.route('/oauth/authorize', methods=['GET'])
def oauth_authorize():
    """
    OAuth authorization endpoint.
    Claude Desktop redirects here to start the OAuth flow.
    """
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')
    code_challenge = request.args.get('code_challenge')
    code_challenge_method = request.args.get('code_challenge_method')

    if not all([client_id, redirect_uri, state]):
        return jsonify({'error': 'missing_parameters'}), 400

    # Verify client_id exists
    user = space_manager.get_user_by_client_id(client_id)
    if not user:
        return jsonify({'error': 'invalid_client_id'}), 401

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)

    # Store auth code with associated data
    auth_codes[auth_code] = {
        'client_id': client_id,
        'user_id': user.user_id,
        'redirect_uri': redirect_uri,
        'code_challenge': code_challenge,
        'code_challenge_method': code_challenge_method,
        'created_at': datetime.now()
    }

    # Redirect back to Claude with authorization code
    callback_url = f"{redirect_uri}?code={auth_code}&state={state}"

    # Return redirect response
    from flask import redirect as flask_redirect
    return flask_redirect(callback_url)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "hivemind-remote-mcp"})


@app.route('/mcp/sse', methods=['GET', 'POST', 'OPTIONS'])
def mcp_sse():
    """
    Main MCP endpoint using SSE transport.
    Implements proper MCP JSON-RPC protocol over Server-Sent Events.
    """
    if request.method == 'OPTIONS':
        # Handle CORS preflight
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method == 'GET':
        # Return info about the server
        return jsonify({
            "name": "Hivemind Remote MCP",
            "version": "0.2.0",
            "transport": "sse",
            "protocol": "mcp",
            "description": "Multi-space collective intelligence with policy-driven sharing"
        })

    # POST request - handle MCP messages via SSE
    # ENFORCE AUTHENTICATION - Per MCP spec, must return 401 if no valid token
    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        # No authorization header - return 401 with WWW-Authenticate
        logger.warning("MCP request without Authorization header - returning 401")
        response = Response(
            json.dumps({"error": "unauthorized", "message": "Bearer token required"}),
            status=401,
            mimetype='application/json'
        )
        response.headers['WWW-Authenticate'] = 'Bearer realm="MCP Server"'
        return response

    # Extract and validate token
    token = auth_header[7:]

    # Look up user from token (checks Firestore or in-memory storage)
    auth_user_id = space_manager.get_user_from_token(token)

    if not auth_user_id:
        logger.warning(f"MCP request with invalid or expired token - returning 401")
        response = Response(
            json.dumps({"error": "invalid_token", "message": "Token is invalid or expired"}),
            status=401,
            mimetype='application/json'
        )
        response.headers['WWW-Authenticate'] = 'Bearer realm="MCP Server", error="invalid_token"'
        return response

    logger.info(f"MCP endpoint - authenticated user_id: {auth_user_id}")

    async def generate():
        """Generator for SSE stream."""
        connection = SSEConnection()
        connection.user_id = auth_user_id  # Store user_id in connection

        try:
            # Get the request body (MCP message)
            data = request.get_json()
            logger.info(f"Raw MCP request data: {data}")

            if data:
                # Handle the message
                response_msg = await connection.handle_message(data)

                # Send response as SSE event
                yield f"data: {json.dumps(response_msg)}\n\n"
            else:
                # No data, send connection established
                yield f"data: {json.dumps({'type': 'connected'})}\n\n"

        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            error_msg = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Stream error: {str(e)}"
                }
            }
            yield f"data: {json.dumps(error_msg)}\n\n"

    # Run async generator
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def sync_generate():
        """Sync wrapper for async generator."""
        for item in loop.run_until_complete(generate_all()):
            yield item

    async def generate_all():
        """Collect all generated items."""
        items = []
        async for item in generate():
            items.append(item)
        return items

    # Actually, let's simplify - just handle the message and return JSON
    try:
        data = request.get_json()
        connection = SSEConnection()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response_msg = loop.run_until_complete(connection.handle_message(data))
        loop.close()

        return Response(
            f"data: {json.dumps(response_msg)}\n\n",
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
    except Exception as e:
        logger.error(f"Error in MCP endpoint: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# OAuth endpoints (same as before)
@app.route('/.well-known/oauth-protected-resource', methods=['GET'])
def oauth_protected_resource():
    """OAuth 2.0 Protected Resource metadata."""
    return jsonify({
        "resource": request.host_url,
        "authorization_servers": [request.host_url]
    })


@app.route('/.well-known/oauth-authorization-server', methods=['GET'])
def oauth_authorization_server():
    """OAuth 2.0 Authorization Server metadata."""
    # Determine the correct scheme (HTTPS for ngrok, HTTP for localhost)
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    host = request.headers.get('X-Forwarded-Host', request.host)
    base_url = f"{scheme}://{host}"

    return jsonify({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"]
    })


@app.route('/register', methods=['POST'])
def register_client():
    """OAuth 2.0 Dynamic Client Registration."""
    client_data = request.get_json() or {}
    return jsonify({
        "client_id": "hivemind_client_" + secrets.token_hex(8),
        "client_secret": "hivemind_secret_" + secrets.token_hex(16),
        "client_id_issued_at": int(datetime.now().timestamp()),
        "redirect_uris": client_data.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "response_types": ["code"]
    })


@app.route('/oauth/token', methods=['POST'])
def oauth_token():
    """OAuth token endpoint - handles both authorization_code and client_credentials grants."""
    grant_type = request.form.get('grant_type')

    if grant_type == 'authorization_code':
        # Authorization code flow (for custom connectors)
        code = request.form.get('code')
        redirect_uri = request.form.get('redirect_uri')
        client_id = request.form.get('client_id')
        code_verifier = request.form.get('code_verifier')

        if not all([code, redirect_uri, client_id]):
            return jsonify({'error': 'missing_parameters'}), 400

        # Verify auth code
        auth_data = auth_codes.get(code)
        if not auth_data:
            return jsonify({'error': 'invalid_code'}), 401

        # Verify client_id and redirect_uri match
        if auth_data['client_id'] != client_id or auth_data['redirect_uri'] != redirect_uri:
            return jsonify({'error': 'invalid_grant'}), 401

        # Verify PKCE if code_challenge was provided
        if auth_data.get('code_challenge'):
            if not code_verifier:
                return jsonify({'error': 'code_verifier_required'}), 400

            # Verify code_challenge matches code_verifier
            verifier_hash = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip('=')

            if verifier_hash != auth_data['code_challenge']:
                return jsonify({'error': 'invalid_code_verifier'}), 401

        # Get user's OAuth credentials
        user = space_manager.get_user_by_client_id(client_id)
        if not user or not user.oauth_credentials:
            return jsonify({'error': 'invalid_client'}), 401

        # Delete used auth code
        del auth_codes[code]

        # Generate access token
        access_token = f"{user.user_id}:{secrets.token_hex(32)}"

        # Store token with expiration (1 hour)
        expires_in_seconds = 3600
        expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        space_manager.save_token(access_token, user.user_id, expires_at)

        logger.info(f"Generated and stored access token for user {user.user_id}, expires at {expires_at}")

        return jsonify({
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': expires_in_seconds
        })

    else:
        # Client credentials flow (legacy/direct auth)
        auth_header = request.headers.get('Authorization', '')

        client_id = None
        client_secret = None

        if auth_header.startswith('Basic '):
            # Decode Basic Auth
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                client_id, client_secret = decoded.split(':', 1)
            except Exception as e:
                logger.warning(f"Failed to decode Basic Auth: {e}")
        else:
            # Try form-encoded
            client_id = request.form.get('client_id')
            client_secret = request.form.get('client_secret')

        if not client_id or not client_secret:
            return jsonify({"error": "invalid_client"}), 401

        # Validate credentials
        user = space_manager.validate_oauth_credentials(client_id, client_secret)

        if not user:
            return jsonify({"error": "invalid_client"}), 401

        # Generate access token (JWT-like but simple for now)
        access_token = f"{user.user_id}:{secrets.token_hex(32)}"

        # Store token with expiration (1 hour)
        expires_in_seconds = 3600
        expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        space_manager.save_token(access_token, user.user_id, expires_at)

        logger.info(f"Generated and stored access token for user {user.user_id}, expires at {expires_at}")

        return jsonify({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in_seconds
        })


def get_user_from_request() -> Optional[str]:
    """Extract user ID from OAuth token in request."""
    auth_header = request.headers.get('Authorization', '')

    logger.info(f"=== GET_USER_FROM_REQUEST ===")
    logger.info(f"Authorization header: {auth_header[:50] if auth_header else 'None'}...")
    logger.info(f"Has active_tokens: {hasattr(app, 'active_tokens')}")
    if hasattr(app, 'active_tokens'):
        logger.info(f"Active tokens count: {len(app.active_tokens)}")
        logger.info(f"Active token keys (first 20 chars): {[t[:20] for t in list(app.active_tokens.keys())[:3]]}")
    logger.info(f"============================")

    if not auth_header.startswith('Bearer '):
        logger.info(f"No Bearer token, returning CONFIGURED_USER_ID: {CONFIGURED_USER_ID}")
        return CONFIGURED_USER_ID  # Fallback to configured user

    token = auth_header[7:]  # Remove 'Bearer ' prefix
    logger.info(f"Looking up token (first 20 chars): {token[:20]}")

    # Look up user from token
    if hasattr(app, 'active_tokens'):
        user_id = app.active_tokens.get(token)
        if user_id:
            logger.info(f"Found user_id from token: {user_id}")
            return user_id

    logger.info(f"Token not found in active_tokens, returning CONFIGURED_USER_ID: {CONFIGURED_USER_ID}")
    return CONFIGURED_USER_ID  # Fallback


# ============================================================================
# Main
# ============================================================================

def main():
    print("\n" + "="*70)
    print("HIVEMIND REMOTE MCP SERVER (Custom Connector) - FIXED")
    print("="*70)
    print("\nStarting server with proper MCP protocol support...")
    print(f"Local URL: http://localhost:8080/mcp/sse")
    print(f"Health check: http://localhost:8080/health")
    print("\nTo use as custom connector:")
    print("1. Make sure this server is running")
    print("2. Make sure ngrok is running: ngrok http 8080")
    print("3. In Claude Desktop, Settings > Connectors > Add custom connector")
    print("4. Enter your ngrok URL: https://YOUR-NGROK-URL.ngrok-free.app/mcp/sse")
    print("5. Click 'Add'")
    print("\n" + "="*70 + "\n")

    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)


if __name__ == '__main__':
    main()
