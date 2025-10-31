#!/usr/bin/env python3
"""
Hivemind MCP Server - Local Testing Version
Uses in-memory storage (no Firestore needed) for quick testing.
"""

import sys
import json
import asyncio
from typing import Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# MCP SDK imports
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Hivemind imports - use in-memory version
from src.space_manager import SpaceManager
from src.policy_engine import PolicyEngine
from src.models import RawConversationTurn, SpaceType

# Configuration
CONFIG_DIR = Path.home() / ".config" / "hivemind"
USER_CONFIG_FILE = CONFIG_DIR / "user_local.json"

# Shared storage (simulates persistence across calls)
# In real version, this would be Firestore
_shared_manager = None
_shared_policy_engine = None


def get_managers():
    """Get or create shared managers."""
    global _shared_manager, _shared_policy_engine

    if _shared_manager is None:
        _shared_manager = SpaceManager()
        _shared_policy_engine = PolicyEngine(_shared_manager)

    return _shared_manager, _shared_policy_engine


class HivemindServerLocal:
    """Local testing Hivemind MCP Server."""

    def __init__(self):
        self.server = Server("hivemind-local")

        # Get shared managers
        self.space_manager, self.policy_engine = get_managers()

        # Load user configuration
        self.user_config = self.load_user_config()

        # Ensure directories exist
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def load_user_config(self) -> dict:
        """Load user configuration."""
        if not USER_CONFIG_FILE.exists():
            return {
                "user_id": None,
                "display_name": None,
                "setup_complete": False
            }

        with open(USER_CONFIG_FILE) as f:
            return json.load(f)

    def save_user_config(self, config: dict):
        """Save user configuration."""
        with open(USER_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        self.user_config = config

    def setup_handlers(self):
        """Register MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="setup_hivemind",
                    description="Set up your Hivemind account. Run this first!",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "display_name": {"type": "string", "description": "Your name"},
                            "contact_method": {"type": "string", "description": "Optional email/contact"}
                        },
                        "required": ["display_name"]
                    }
                ),
                Tool(
                    name="create_space",
                    description="Create a new space with policy. Returns invite code.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "space_type": {"type": "string", "enum": ["1:1", "group", "public"]},
                            "policy_template": {"type": "string", "enum": ["couples", "team", "public"]}
                        },
                        "required": ["name", "space_type", "policy_template"]
                    }
                ),
                Tool(
                    name="join_space",
                    description="Join a space using invite code.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "invite_code": {"type": "string", "description": "8-character code"}
                        },
                        "required": ["invite_code"]
                    }
                ),
                Tool(
                    name="list_my_spaces",
                    description="List all spaces you're a member of.",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="log_conversation",
                    description="Log conversation and route through policies. THE KEY TOOL!",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_message": {"type": "string"},
                            "assistant_message": {"type": "string"},
                            "topics": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["user_message", "assistant_message"]
                    }
                ),
                Tool(
                    name="view_pending_approvals",
                    description="See content waiting for approval.",
                    inputSchema={"type": "object", "properties": {}}
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            try:
                # Check setup
                if name != "setup_hivemind" and not self.user_config.get("user_id"):
                    return [TextContent(
                        type="text",
                        text="Please run: setup_hivemind(display_name='Your Name') first!"
                    )]

                user_id = self.user_config.get("user_id")

                if name == "setup_hivemind":
                    display_name = arguments.get("display_name", "")
                    contact_method = arguments.get("contact_method")

                    user = self.space_manager.create_user(display_name, contact_method)

                    self.save_user_config({
                        "user_id": user.user_id,
                        "display_name": display_name,
                        "contact_method": contact_method,
                        "setup_complete": True
                    })

                    return [TextContent(
                        type="text",
                        text=f"✓ Hivemind set up!\n\nUser ID: {user.user_id}\nName: {display_name}\n\nTry: create_space(...)"
                    )]

                elif name == "create_space":
                    space_name = arguments.get("name", "")
                    space_type = arguments.get("space_type", "")
                    policy_template = arguments.get("policy_template", "")

                    space = self.space_manager.create_space(
                        user_id,
                        space_name,
                        SpaceType(space_type),
                        policy_template=policy_template
                    )

                    return [TextContent(
                        type="text",
                        text=(
                            f"✓ Space '{space_name}' created!\n\n"
                            f"Invite Code: {space.invite_code}\n"
                            f"Type: {space.space_type.value}\n\n"
                            f"Share this code to invite others.\n"
                            f"View at: http://localhost:5000/spaces/{space.space_id}"
                        )
                    )]

                elif name == "join_space":
                    invite_code = arguments.get("invite_code", "").strip().upper()

                    # Find space
                    target_space = None
                    for space in self.space_manager.spaces.values():
                        if space.invite_code == invite_code:
                            target_space = space
                            break

                    if not target_space:
                        return [TextContent(type="text", text=f"✗ Invalid invite code: {invite_code}")]

                    success = self.space_manager.join_space(target_space.space_id, user_id, invite_code)

                    if success:
                        return [TextContent(
                            type="text",
                            text=f"✓ Joined '{target_space.name}'!\n\nConversations will now route to this space."
                        )]
                    else:
                        return [TextContent(type="text", text="✗ Failed to join (already member or full)")]

                elif name == "list_my_spaces":
                    spaces = self.space_manager.list_user_spaces(user_id)

                    if not spaces:
                        return [TextContent(type="text", text="No spaces yet. Create one with: create_space(...)")]

                    output = f"Your Spaces ({len(spaces)}):\n\n"
                    for i, space in enumerate(spaces, 1):
                        output += f"{i}. {space.name}\n"
                        output += f"   Type: {space.space_type.value}\n"
                        output += f"   Members: {len(space.members)}\n"
                        output += f"   Invite: {space.invite_code}\n\n"

                    return [TextContent(type="text", text=output)]

                elif name == "log_conversation":
                    user_msg = arguments.get("user_message", "")
                    assistant_msg = arguments.get("assistant_message", "")
                    topics = arguments.get("topics", [])

                    turn = RawConversationTurn(
                        user_id=user_id,
                        user_message=user_msg,
                        assistant_message=assistant_msg,
                        topics=topics
                    )

                    # Route through policies
                    results = await self.policy_engine.route_conversation(turn, user_id)

                    shared_to = []
                    needs_approval = []

                    for result in results:
                        space = self.space_manager.get_space(result.space_id)

                        if result.action == "shared":
                            shared_to.append(space.name)
                        elif result.action == "approval_needed":
                            needs_approval.append(space.name)

                    output = "✓ Conversation logged\n\n"
                    if shared_to:
                        output += f"Shared to: {', '.join(shared_to)}\n"
                    if needs_approval:
                        output += f"\n⚠ Needs approval for: {', '.join(needs_approval)}\n"
                        output += "Review at: http://localhost:5000/approvals\n"

                    return [TextContent(type="text", text=output)]

                elif name == "view_pending_approvals":
                    # In local version, we'd need to store these
                    return [TextContent(
                        type="text",
                        text="No pending approvals (local version).\n\nUse web app for approval workflow."
                    )]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                import traceback
                traceback.print_exc()
                return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server"""
    server = HivemindServerLocal()
    server.setup_handlers()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream,
            write_stream,
            server.server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
