#!/usr/bin/env python3
"""
Hivemind MCP Server v2 - Production Multi-Space Server

Complete MCP server with all tools for multi-space hivemind:
- Space management (create, join, list)
- Conversation logging with policy routing
- Approval workflow
- Context injection from spaces
- Public feed discovery
"""

import os
import sys
import json
import asyncio
from typing import Any, Optional, List
from pathlib import Path

# MCP SDK imports
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Hivemind imports
from src.firestore_manager import FirestoreSpaceManager
from src.policy_engine import PolicyEngine
from src.models import RawConversationTurn, SpaceType

# Configuration
CONFIG_DIR = Path.home() / ".config" / "hivemind"
USER_CONFIG_FILE = CONFIG_DIR / "user.json"


class HivemindServerV2:
    """Production Hivemind MCP Server."""

    def __init__(self):
        self.server = Server("hivemind-v2")

        # Initialize managers
        try:
            self.space_manager = FirestoreSpaceManager()
            self.policy_engine = PolicyEngine(self.space_manager)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("Please set FIRESTORE_PROJECT environment variable", file=sys.stderr)
            sys.exit(1)

        # Load user configuration
        self.user_config = self.load_user_config()

        # Ensure directories exist
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def load_user_config(self) -> dict:
        """Load user configuration (user_id, etc.)"""
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
                # ============================================================
                # Setup & User Management
                # ============================================================
                Tool(
                    name="setup_hivemind",
                    description=(
                        "Set up your Hivemind account. Creates your user profile and configures the system. "
                        "Run this first before using other tools."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "display_name": {
                                "type": "string",
                                "description": "Your name (e.g., 'Andrew Miller')"
                            },
                            "contact_method": {
                                "type": "string",
                                "description": "Optional contact info (email, Signal, etc.)"
                            }
                        },
                        "required": ["display_name"]
                    }
                ),

                # ============================================================
                # Space Management
                # ============================================================
                Tool(
                    name="create_space",
                    description=(
                        "Create a new space for sharing conversations with specific people. "
                        "Returns an invite code that you can share with others to join."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the space (e.g., 'Andrew & Jamila', 'Pirate Ship')"
                            },
                            "space_type": {
                                "type": "string",
                                "enum": ["1:1", "group", "public"],
                                "description": "Type: '1:1' (max 2 people), 'group' (unlimited), 'public' (discoverable)"
                            },
                            "policy_template": {
                                "type": "string",
                                "enum": ["couples", "team", "public"],
                                "description": "Policy template: 'couples' (share emotions), 'team' (share work), 'public' (share insights)"
                            }
                        },
                        "required": ["name", "space_type", "policy_template"]
                    }
                ),
                Tool(
                    name="join_space",
                    description=(
                        "Join a space using an invite code. "
                        "After joining, conversations will automatically route to this space based on the policy."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "invite_code": {
                                "type": "string",
                                "description": "8-character invite code (e.g., 'F7D6F71B')"
                            }
                        },
                        "required": ["invite_code"]
                    }
                ),
                Tool(
                    name="list_my_spaces",
                    description=(
                        "List all spaces you're a member of. "
                        "Shows space names, types, member counts, and invite codes."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),

                # ============================================================
                # Conversation Logging (with routing!)
                # ============================================================
                Tool(
                    name="log_conversation",
                    description=(
                        "Log a conversation turn and route it through your space policies. "
                        "Automatically shares relevant content to appropriate spaces based on policies. "
                        "High-sensitivity content may be queued for your approval."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_message": {
                                "type": "string",
                                "description": "What the user said"
                            },
                            "assistant_message": {
                                "type": "string",
                                "description": "What Claude said in response"
                            },
                            "topics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional topics/keywords for better routing"
                            }
                        },
                        "required": ["user_message", "assistant_message"]
                    }
                ),

                # ============================================================
                # Reading from Spaces (Context Injection!)
                # ============================================================
                Tool(
                    name="read_space",
                    description=(
                        "Read recent content from a specific space. "
                        "Use this to get context about what's been shared. "
                        "Great for reminding yourself what you've discussed before."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "space_id": {
                                "type": "string",
                                "description": "Space ID (use list_my_spaces to get IDs)"
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of items to retrieve (default: 10)"
                            }
                        },
                        "required": ["space_id"]
                    }
                ),
                Tool(
                    name="browse_public_feed",
                    description=(
                        "Browse recent insights from all public spaces. "
                        "Discover what others are learning and sharing publicly."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "number",
                                "description": "Number of items to retrieve (default: 10)"
                            }
                        }
                    }
                ),

                # ============================================================
                # Approval Workflow (THE CONSENT LAYER!)
                # ============================================================
                Tool(
                    name="view_pending_approvals",
                    description=(
                        "View content waiting for your approval before sharing. "
                        "Shows high-sensitivity items that need your review. "
                        "Use the web app (http://localhost:5000/approvals) to approve/reject."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            try:
                # Check if user is set up (except for setup_hivemind)
                if name != "setup_hivemind" and not self.user_config.get("user_id"):
                    return [TextContent(
                        type="text",
                        text=(
                            "Hivemind not set up yet. Please run:\n\n"
                            "setup_hivemind(display_name='Your Name', contact_method='your@email.com')\n\n"
                            "This creates your user profile."
                        )
                    )]

                user_id = self.user_config.get("user_id")

                # ========================================================
                # Setup
                # ========================================================
                if name == "setup_hivemind":
                    display_name = arguments.get("display_name", "")
                    contact_method = arguments.get("contact_method")

                    # Create user
                    user = self.space_manager.create_user(display_name, contact_method)

                    # Save config
                    self.save_user_config({
                        "user_id": user.user_id,
                        "display_name": display_name,
                        "contact_method": contact_method,
                        "setup_complete": True
                    })

                    return [TextContent(
                        type="text",
                        text=(
                            f"✓ Hivemind set up successfully!\n\n"
                            f"User ID: {user.user_id}\n"
                            f"Name: {display_name}\n\n"
                            f"You can now create spaces and share conversations.\n\n"
                            f"Try: create_space(name='My First Space', space_type='1:1', policy_template='couples')"
                        )
                    )]

                # ========================================================
                # Space Management
                # ========================================================
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
                            f"Space ID: {space.space_id}\n"
                            f"Type: {space.space_type.value}\n"
                            f"Invite Code: {space.invite_code}\n\n"
                            f"Share this invite code with others to let them join.\n"
                            f"They can join by running:\n"
                            f"join_space(invite_code='{space.invite_code}')\n\n"
                            f"View this space at: http://localhost:5000/spaces/{space.space_id}"
                        )
                    )]

                elif name == "join_space":
                    invite_code = arguments.get("invite_code", "").strip().upper()

                    # Find space by invite code
                    # Note: This is inefficient. In production, use an invite_codes collection
                    all_spaces = self.space_manager.spaces_col.stream()
                    target_space = None

                    for space_doc in all_spaces:
                        space_data = space_doc.to_dict()
                        if space_data.get("invite_code") == invite_code:
                            target_space = space_data
                            break

                    if not target_space:
                        return [TextContent(
                            type="text",
                            text=f"✗ Invalid invite code: {invite_code}\n\nPlease check the code and try again."
                        )]

                    space_id = target_space["space_id"]
                    success = self.space_manager.join_space(space_id, user_id, invite_code)

                    if success:
                        return [TextContent(
                            type="text",
                            text=(
                                f"✓ Successfully joined '{target_space['name']}'!\n\n"
                                f"Conversations will now route to this space based on the policy.\n"
                                f"View space at: http://localhost:5000/spaces/{space_id}"
                            )
                        )]
                    else:
                        return [TextContent(
                            type="text",
                            text=f"✗ Failed to join space. You may already be a member, or the space is full."
                        )]

                elif name == "list_my_spaces":
                    spaces = self.space_manager.list_user_spaces(user_id)

                    if not spaces:
                        return [TextContent(
                            type="text",
                            text=(
                                "You haven't joined any spaces yet.\n\n"
                                "Create one with: create_space(...)\n"
                                "Or join with: join_space(invite_code='...')"
                            )
                        )]

                    output = f"Your Spaces ({len(spaces)}):\n\n"

                    for i, space in enumerate(spaces, 1):
                        output += f"{i}. {space.name}\n"
                        output += f"   ID: {space.space_id}\n"
                        output += f"   Type: {space.space_type.value}\n"
                        output += f"   Members: {len(space.members)}\n"
                        output += f"   Invite Code: {space.invite_code}\n"
                        output += f"   Policy: {space.policy.policy_id.split('_')[0]}\n\n"

                    output += "\nUse read_space(space_id='...') to see content from a space."

                    return [TextContent(type="text", text=output)]

                # ========================================================
                # Conversation Logging (WITH ROUTING!)
                # ========================================================
                elif name == "log_conversation":
                    user_msg = arguments.get("user_message", "")
                    assistant_msg = arguments.get("assistant_message", "")
                    topics = arguments.get("topics", [])

                    # Create conversation turn
                    turn = RawConversationTurn(
                        user_id=user_id,
                        user_message=user_msg,
                        assistant_message=assistant_msg,
                        topics=topics
                    )

                    # Save raw conversation
                    self.space_manager.save_raw_conversation(turn)

                    # Route through policy engine
                    results = await self.policy_engine.route_conversation(turn, user_id)

                    # Process results
                    shared_to = []
                    skipped = []
                    needs_approval = []

                    for result in results:
                        space = self.space_manager.get_space(result.space_id)

                        if result.action == "shared" and result.document:
                            # Save filtered document
                            self.space_manager.save_filtered_document(result.document)
                            shared_to.append(space.name)

                        elif result.action == "skipped":
                            skipped.append(f"{space.name} ({result.reason})")

                        elif result.action == "approval_needed" and result.approval:
                            # Save to approval queue
                            self.space_manager.save_pending_approval(result.approval)
                            needs_approval.append(space.name)

                    # Format response
                    output = "✓ Conversation logged\n\n"

                    if shared_to:
                        output += f"Shared to: {', '.join(shared_to)}\n"

                    if needs_approval:
                        output += f"\n⚠ Needs approval for: {', '.join(needs_approval)}\n"
                        output += "Review at: http://localhost:5000/approvals\n"

                    if skipped:
                        output += f"\nSkipped: {len(skipped)} spaces (not relevant)\n"

                    return [TextContent(type="text", text=output)]

                # ========================================================
                # Reading from Spaces
                # ========================================================
                elif name == "read_space":
                    space_id = arguments.get("space_id", "")
                    limit = arguments.get("limit", 10)

                    space = self.space_manager.get_space(space_id)
                    if not space:
                        return [TextContent(type="text", text=f"✗ Space not found: {space_id}")]

                    # Check if user is a member
                    if not any(m.user_id == user_id for m in space.members):
                        return [TextContent(type="text", text=f"✗ You are not a member of '{space.name}'")]

                    # Get documents
                    docs = self.space_manager.get_space_documents(space_id, limit=limit)

                    if not docs:
                        return [TextContent(
                            type="text",
                            text=f"No content in '{space.name}' yet. Start sharing conversations!"
                        )]

                    output = f"Recent content from '{space.name}':\n\n"

                    for i, doc in enumerate(docs, 1):
                        output += f"{i}. {doc.content[:200]}{'...' if len(doc.content) > 200 else ''}\n"
                        output += f"   Topics: {', '.join(doc.filtered_topics[:3])}\n"
                        output += f"   {doc.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"

                    return [TextContent(type="text", text=output)]

                elif name == "browse_public_feed":
                    limit = arguments.get("limit", 10)

                    docs = self.space_manager.search_public_documents("", limit=limit)

                    if not docs:
                        return [TextContent(
                            type="text",
                            text="No public content yet. Be the first to share to a public space!"
                        )]

                    output = f"Recent public insights ({len(docs)}):\n\n"

                    for i, doc in enumerate(docs, 1):
                        output += f"{i}. {doc.content[:200]}{'...' if len(doc.content) > 200 else ''}\n"

                        if doc.display_name:
                            output += f"   By: {doc.display_name}\n"

                        if doc.contact_method and doc.contact_preference != "just_sharing":
                            output += f"   Contact: {doc.contact_method}\n"

                        output += f"   Topics: {', '.join(doc.filtered_topics[:3])}\n\n"

                    return [TextContent(type="text", text=output)]

                # ========================================================
                # Approval Workflow
                # ========================================================
                elif name == "view_pending_approvals":
                    approvals = self.space_manager.get_pending_approvals(user_id)

                    if not approvals:
                        return [TextContent(
                            type="text",
                            text="No pending approvals. All conversations have been automatically shared or skipped based on your policies."
                        )]

                    output = f"Pending Approvals ({len(approvals)}):\n\n"

                    for i, approval in enumerate(approvals, 1):
                        space = self.space_manager.get_space(approval.space_id)

                        output += f"{i}. For: {space.name if space else 'Unknown'}\n"
                        output += f"   Content: {approval.proposed_content[:100]}...\n"
                        output += f"   Reason: {approval.reason_for_approval}\n"
                        output += f"   Sensitivity: {approval.sensitivity_score:.0%}\n"
                        output += f"   Confidence: {approval.confidence_score:.0%}\n\n"

                    output += "\nReview and approve/reject at: http://localhost:5000/approvals"

                    return [TextContent(type="text", text=output)]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                import traceback
                traceback.print_exc()
                return [TextContent(
                    type="text",
                    text=f"Error: {str(e)}\n\nPlease check the logs for details."
                )]


async def main():
    """Run the MCP server"""
    server = HivemindServerV2()
    server.setup_handlers()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream,
            write_stream,
            server.server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
