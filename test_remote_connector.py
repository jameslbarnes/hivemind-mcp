#!/usr/bin/env python3
"""
Test script for remote MCP connector.

This helps verify the server works before adding to Claude as a custom connector.
"""

import httpx
import asyncio


async def test_health():
    """Test health endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/health")
        print(f"Health check: {response.status_code}")
        print(f"Response: {response.json()}\n")


async def test_mcp_info():
    """Test MCP info endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/mcp/sse")
        print(f"MCP Info: {response.status_code}")
        print(f"Response: {response.json()}\n")


async def main():
    print("="*70)
    print("Testing Hivemind Remote MCP Connector")
    print("="*70 + "\n")

    print("Make sure the server is running:")
    print("  python src/remote_mcp_server.py\n")

    try:
        await test_health()
        await test_mcp_info()

        print("✓ Server is responding!")
        print("\nNext steps:")
        print("1. Keep the server running")
        print("2. In Claude, go to Settings > Connectors")
        print("3. Click 'Add custom connector'")
        print("4. Enter URL: http://localhost:8080/mcp/sse")
        print("5. Click 'Add'")
        print("\n" + "="*70)

    except httpx.ConnectError:
        print("✗ Server is not running!")
        print("\nStart it with:")
        print("  python src/remote_mcp_server.py")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == '__main__':
    asyncio.run(main())
