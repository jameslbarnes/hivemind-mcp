#!/usr/bin/env python3
"""
Hivemind MCP Server

Thin client that provides three tools:
1. log_conversation_turn - Save locally and forward to TEE for privacy filtering
2. read_hivemind - Browse recent insights from the group
3. query_hivemind - Search for specific topics or people
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import asyncio
import httpx

# MCP SDK imports
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Configuration
CONFIG_DIR = Path.home() / ".config" / "hivemind"
LOCAL_LOG_DIR = Path.home() / ".local" / "share" / "hivemind" / "conversations"
CONSENT_FILE = CONFIG_DIR / "consent.json"

# TEE API endpoint (will be configured)
TEE_API_URL = os.getenv("HIVEMIND_TEE_API", "http://localhost:8000")

# Firestore (direct read access for now, write only through TEE)
FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "")


class HivemindServer:
    def __init__(self):
        self.server = Server("hivemind-mcp")
        self.consent_config = self.load_consent()
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Ensure directories exist
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def load_consent(self) -> dict:
        """Load user consent configuration"""
        if not CONSENT_FILE.exists():
            return {
                "enabled": False,
                "display_name": None,
                "contact_method": None,
                "contact_preference": "just_sharing",
                "setup_complete": False
            }

        with open(CONSENT_FILE) as f:
            return json.load(f)

    def save_consent(self, config: dict):
        """Save consent configuration"""
        with open(CONSENT_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        self.consent_config = config

    def save_local_log(self, user_msg: str, assistant_msg: str) -> str:
        """Save conversation turn locally (always)"""
        timestamp = datetime.now().isoformat()
        log_file = LOCAL_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

        log_entry = {
            "timestamp": timestamp,
            "user": user_msg,
            "assistant": assistant_msg
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        return timestamp

    async def forward_to_tee(self, user_msg: str, assistant_msg: str, timestamp: str) -> Optional[dict]:
        """Forward conversation to TEE API for privacy filtering"""
        if not self.consent_config.get("enabled"):
            return None

        try:
            response = await self.http_client.post(
                f"{TEE_API_URL}/extract_insight",
                json={
                    "user_message": user_msg,
                    "assistant_message": assistant_msg,
                    "timestamp": timestamp,
                    "user_config": {
                        "display_name": self.consent_config.get("display_name"),
                        "contact_method": self.consent_config.get("contact_method"),
                        "contact_preference": self.consent_config.get("contact_preference")
                    }
                }
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"TEE API error: {response.status_code}", file=sys.stderr)
                return None

        except Exception as e:
            print(f"Error forwarding to TEE: {e}", file=sys.stderr)
            return None

    async def read_from_firestore(self, limit: int = 10, category: Optional[str] = None) -> list[dict]:
        """Read recent insights from Firestore (via TEE API for now)"""
        try:
            params = {"limit": limit}
            if category:
                params["category"] = category

            response = await self.http_client.get(
                f"{TEE_API_URL}/read_insights",
                params=params
            )

            if response.status_code == 200:
                return response.json().get("insights", [])
            else:
                return []

        except Exception as e:
            print(f"Error reading from Firestore: {e}", file=sys.stderr)
            return []

    async def query_firestore(self, query: str, limit: int = 10) -> list[dict]:
        """Search Firestore for relevant insights"""
        try:
            response = await self.http_client.post(
                f"{TEE_API_URL}/query_insights",
                json={"query": query, "limit": limit}
            )

            if response.status_code == 200:
                return response.json().get("insights", [])
            else:
                return []

        except Exception as e:
            print(f"Error querying Firestore: {e}", file=sys.stderr)
            return []

    def setup_handlers(self):
        """Register MCP tool handlers"""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="log_conversation_turn",
                    description=(
                        "Log a conversation turn. Saves locally (always) and optionally "
                        "shares anonymized insights with your group (if opted in). "
                        "Use this to contribute to the collective knowledge."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_message": {
                                "type": "string",
                                "description": "The user's message in the conversation"
                            },
                            "assistant_message": {
                                "type": "string",
                                "description": "Claude's response"
                            }
                        },
                        "required": ["user_message", "assistant_message"]
                    }
                ),
                Tool(
                    name="read_hivemind",
                    description=(
                        "See what your group has been exploring recently. "
                        "Returns recent insights with attribution and contact info. "
                        "Like checking in on an asynchronous group chat."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "number",
                                "description": "Number of insights to return (default: 10)"
                            },
                            "category": {
                                "type": "string",
                                "description": "Filter by category (optional)"
                            }
                        }
                    }
                ),
                Tool(
                    name="query_hivemind",
                    description=(
                        "Search for specific topics or find people who can help. "
                        "Returns relevant insights with contact info for reaching out."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What to search for (topic, problem, or area of interest)"
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of results to return (default: 10)"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            if name == "log_conversation_turn":
                user_msg = arguments.get("user_message", "")
                assistant_msg = arguments.get("assistant_message", "")

                # Always save locally
                timestamp = self.save_local_log(user_msg, assistant_msg)

                # Check if first time - offer consent
                if not self.consent_config.get("setup_complete"):
                    return [TextContent(
                        type="text",
                        text=(
                            "Hivemind is not yet configured.\n\n"
                            "This tool can share anonymized insights from your conversations "
                            "with your trusted group. Your team can see what you're learning, "
                            "and you can connect with others who can help.\n\n"
                            "To set up, run: hivemind init\n\n"
                            "For now, conversation saved locally only."
                        )
                    )]

                # Forward to TEE if opted in
                result = await self.forward_to_tee(user_msg, assistant_msg, timestamp)

                if result and result.get("shared"):
                    return [TextContent(
                        type="text",
                        text=f"Logged locally and shared insight to the group:\n\"{result.get('insight_preview', '')}\""
                    )]
                else:
                    return [TextContent(
                        type="text",
                        text="Logged locally. No shareable insight extracted (too sensitive or low value)."
                    )]

            elif name == "read_hivemind":
                limit = arguments.get("limit", 10)
                category = arguments.get("category")

                insights = await self.read_from_firestore(limit, category)

                if not insights:
                    return [TextContent(
                        type="text",
                        text="No recent insights in the hivemind yet. Be the first to share!"
                    )]

                # Format insights for display
                formatted = "Recent insights from your group:\n\n"
                for i, insight in enumerate(insights, 1):
                    formatted += f"{i}. [{insight.get('category', 'general')}]\n"
                    formatted += f"   {insight.get('insight', '')}\n"

                    if insight.get('display_name'):
                        formatted += f"   By: {insight['display_name']}"
                        if insight.get('contact_preference') != 'just_sharing':
                            formatted += f" ({insight.get('contact_preference', 'open to questions')})"
                        formatted += "\n"

                        if insight.get('contact_method') and insight.get('contact_preference') != 'just_sharing':
                            formatted += f"   Contact: {insight['contact_method']}\n"

                    formatted += "\n"

                return [TextContent(type="text", text=formatted)]

            elif name == "query_hivemind":
                query = arguments.get("query", "")
                limit = arguments.get("limit", 10)

                insights = await self.query_firestore(query, limit)

                if not insights:
                    return [TextContent(
                        type="text",
                        text=f"No insights found for '{query}'. Try a different search or be the first to share about this topic!"
                    )]

                # Format search results
                formatted = f"Found {len(insights)} insights about '{query}':\n\n"
                for i, insight in enumerate(insights, 1):
                    formatted += f"{i}. {insight.get('insight', '')}\n"

                    if insight.get('display_name'):
                        formatted += f"   By: {insight['display_name']}"
                        if insight.get('contact_preference') != 'just_sharing':
                            formatted += f" - {insight.get('contact_preference', 'open to questions')}"
                        formatted += "\n"

                        if insight.get('contact_method') and insight.get('contact_preference') != 'just_sharing':
                            formatted += f"   Reach out: {insight['contact_method']}\n"

                    formatted += "\n"

                return [TextContent(type="text", text=formatted)]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server"""
    server = HivemindServer()
    server.setup_handlers()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream,
            write_stream,
            server.server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
