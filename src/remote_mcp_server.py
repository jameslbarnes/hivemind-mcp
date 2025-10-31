#!/usr/bin/env python3
"""
Remote MCP Server for Hivemind (Custom Connector)

This serves the MCP protocol over HTTP with SSE for use as a Claude custom connector.
Can be tested locally with http://localhost:8080 or deployed remotely.

Features:
- Serves MCP tools over HTTP/SSE
- CORS-enabled for remote access
- OAuth support (optional)
- Works with Claude Pro/Max/Team/Enterprise custom connectors
"""

import asyncio
import json
import logging
import secrets
import sys
from typing import Any, Optional
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import httpx

# MCP imports
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport

# Hivemind imports
from src.space_manager import SpaceManager
from src.policy_engine import PolicyEngine
from src.models import RawConversationTurn, SpaceType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
CORS(app)  # Enable CORS for remote access

# Initialize managers
space_manager = SpaceManager()
policy_engine = PolicyEngine(space_manager)

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
            description="Log a conversation turn. Saves locally and routes through policy engines to appropriate spaces.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "What the user said"
                    },
                    "assistant_message": {
                        "type": "string",
                        "description": "Claude's response"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID (for multi-user support)"
                    }
                },
                "required": ["user_message", "assistant_message"]
            }
        ),
        Tool(
            name="create_space",
            description="Create a new space for sharing context with specific people or groups.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for this space"
                    },
                    "space_type": {
                        "type": "string",
                        "enum": ["1:1", "group", "public"],
                        "description": "Type of space"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID creating the space"
                    },
                    "policy_template": {
                        "type": "string",
                        "description": "Optional policy template (couples, team, public)"
                    }
                },
                "required": ["name", "space_type", "user_id"]
            }
        ),
        Tool(
            name="list_spaces",
            description="See all your spaces and their status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID"
                    }
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="join_space",
            description="Join a space using an invite code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invite_code": {
                        "type": "string",
                        "description": "The invite code"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID joining the space"
                    }
                },
                "required": ["invite_code", "user_id"]
            }
        ),
        Tool(
            name="read_space",
            description="Read recent content from a space to get context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {
                        "type": "string",
                        "description": "Which space to read from"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID"
                    },
                    "limit": {
                        "type": "number",
                        "description": "How many recent items to read",
                        "default": 5
                    }
                },
                "required": ["space_id", "user_id"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle MCP tool calls."""
    try:
        if name == "log_conversation_turn":
            return await handle_log_conversation(arguments)
        elif name == "create_space":
            return await handle_create_space(arguments)
        elif name == "list_spaces":
            return await handle_list_spaces(arguments)
        elif name == "join_space":
            return await handle_join_space(arguments)
        elif name == "read_space":
            return await handle_read_space(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_log_conversation(args: dict) -> list[TextContent]:
    """Handle log_conversation_turn tool."""
    user_message = args["user_message"]
    assistant_message = args["assistant_message"]
    user_id = args.get("user_id", "default_user")

    # Ensure user exists
    if user_id not in space_manager.users:
        space_manager.create_user(user_id, f"{user_id}@example.com")

    # Create conversation turn
    turn = RawConversationTurn(
        user_id=user_id,
        user_message=user_message,
        assistant_message=assistant_message
    )

    # Route through policy engine
    results = await policy_engine.route_conversation(turn, user_id)

    # Format response
    response_lines = ["Logged and processed for your spaces:\n"]

    for result in results:
        space = space_manager.get_space(result.space_id)
        if result.action == "shared":
            response_lines.append(f"✓ {space.name}")
            if result.filtered_content:
                response_lines.append(f'  "{result.filtered_content[:100]}..."')
        elif result.action == "approval_needed":
            response_lines.append(f"⏸ {space.name} (needs approval)")
            response_lines.append(f"  {result.reason}")
        elif result.action == "skipped":
            response_lines.append(f"⊘ {space.name}")
            response_lines.append(f"  {result.reason}")

    return [TextContent(type="text", text="\n".join(response_lines))]


async def handle_create_space(args: dict) -> list[TextContent]:
    """Handle create_space tool."""
    name = args["name"]
    space_type = SpaceType(args["space_type"])
    user_id = args["user_id"]
    policy_template = args.get("policy_template")

    # Ensure user exists
    if user_id not in space_manager.users:
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


async def handle_list_spaces(args: dict) -> list[TextContent]:
    """Handle list_spaces tool."""
    user_id = args["user_id"]

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


async def handle_join_space(args: dict) -> list[TextContent]:
    """Handle join_space tool."""
    invite_code = args["invite_code"].strip().upper()
    user_id = args["user_id"]

    # Ensure user exists
    if user_id not in space_manager.users:
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


async def handle_read_space(args: dict) -> list[TextContent]:
    """Handle read_space tool."""
    space_id = args["space_id"]
    user_id = args["user_id"]
    limit = args.get("limit", 5)

    space = space_manager.get_space(space_id)

    if not space:
        return [TextContent(type="text", text=f"Space not found: {space_id}")]

    # Check if user is member
    is_member = any(m.user_id == user_id for m in space.members)
    if not is_member:
        return [TextContent(type="text", text=f"You are not a member of space: {space.name}")]

    # TODO: Actually retrieve conversations from the space
    # For now, return a placeholder
    response = f"""Recent context from "{space.name}":

(No conversations yet - this space is newly created)

Start logging conversations with log_conversation_turn to populate this space!"""

    return [TextContent(type="text", text=response)]


# ============================================================================
# Flask Routes for SSE Transport
# ============================================================================

@app.route('/', methods=['GET', 'POST'])
def root():
    """Root endpoint - redirect to MCP info."""
    if request.method == 'POST':
        # Claude might POST here for MCP connection
        return jsonify({
            "name": "Hivemind Remote MCP",
            "version": "0.2.0",
            "mcp_endpoint": "/mcp/sse"
        })
    return jsonify({
        "name": "Hivemind Remote MCP",
        "version": "0.2.0",
        "mcp_endpoint": "/mcp/sse",
        "health": "/health"
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "hivemind-remote-mcp"})


@app.route('/mcp/sse', methods=['GET', 'POST'])
def mcp_sse():
    """
    Main MCP endpoint using SSE transport.
    This is what Claude's custom connector will connect to.
    """
    if request.method == 'GET':
        # Return info about the server
        return jsonify({
            "name": "Hivemind Remote MCP",
            "version": "0.2.0",
            "description": "Multi-space collective intelligence with policy-driven sharing",
            "transport": "sse",
            "endpoint": "/mcp/sse"
        })

    # POST request - handle MCP connection
    # For now, return a simple response
    # Full MCP SSE implementation would require more complex setup
    return jsonify({"status": "mcp_ready", "message": "MCP server is running"})



@app.route('/mcp/messages', methods=['GET'])
def mcp_messages():
    """SSE stream endpoint for MCP messages."""
    def generate():
        # This will be handled by the SseServerTransport
        yield 'data: {"type": "connected"}\n\n'

    return Response(generate(), mimetype='text/event-stream')


# ============================================================================
# OAuth Support & Well-Known Endpoints
# ============================================================================

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
    base_url = request.host_url.rstrip('/')
    return jsonify({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "service_documentation": f"{base_url}"
    })


@app.route('/register', methods=['POST'])
def register_client():
    """OAuth 2.0 Dynamic Client Registration."""
    # Accept any client registration for now
    client_data = request.get_json() or {}
    return jsonify({
        "client_id": "hivemind_client_" + secrets.token_hex(8),
        "client_secret": "hivemind_secret_" + secrets.token_hex(16),
        "client_id_issued_at": int(datetime.now().timestamp()),
        "redirect_uris": client_data.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_basic"
    })


@app.route('/oauth/authorize', methods=['GET'])
def oauth_authorize():
    """OAuth authorization endpoint."""
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')

    # Generate auth code
    auth_code = "demo_auth_code_" + secrets.token_hex(16)

    return f"""
    <html>
    <body>
    <h1>Authorize Hivemind Access</h1>
    <p>Application requesting access to your Hivemind spaces.</p>
    <form action="{redirect_uri}" method="get">
        <input type="hidden" name="code" value="{auth_code}">
        <input type="hidden" name="state" value="{state}">
        <button type="submit">Authorize</button>
    </form>
    </body>
    </html>
    """


@app.route('/oauth/token', methods=['POST'])
def oauth_token():
    """OAuth token endpoint."""
    # Accept any token request for now
    return jsonify({
        "access_token": "hivemind_token_" + secrets.token_hex(32),
        "token_type": "Bearer",
        "expires_in": 3600
    })


# ============================================================================
# Main
# ============================================================================

def main():
    print("\n" + "="*70)
    print("HIVEMIND REMOTE MCP SERVER (Custom Connector)")
    print("="*70)
    print("\nStarting server...")
    print(f"Local URL: http://localhost:8080/mcp/sse")
    print(f"Health check: http://localhost:8080/health")
    print("\nTo use as custom connector:")
    print("1. Start this server")
    print("2. In Claude, go to Settings > Connectors")
    print("3. Click 'Add custom connector'")
    print("4. Enter: http://localhost:8080/mcp/sse")
    print("5. Click 'Add'")
    print("\nFor remote deployment:")
    print("- Deploy to a server with public URL")
    print("- Use HTTPS (required for production)")
    print("- Update URL in connector settings")
    print("\nPress Ctrl+C to stop")
    print("="*70 + "\n")

    app.run(host='0.0.0.0', port=8080, debug=True)


if __name__ == '__main__':
    main()
