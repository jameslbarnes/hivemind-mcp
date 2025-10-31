#!/usr/bin/env python3
"""
Test script to verify local Hivemind setup
"""

import asyncio
import httpx
from datetime import datetime

TEE_API_URL = "http://localhost:8000"


async def test_health():
    """Test API health check"""
    print("Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{TEE_API_URL}/health")
        if response.status_code == 200:
            print("[OK] Health check passed")
            return True
        else:
            print(f"[FAIL] Health check failed: {response.status_code}")
            return False


async def test_prompt_hash():
    """Verify privacy prompt"""
    print("\nChecking privacy prompt...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{TEE_API_URL}/prompt_hash")
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Prompt hash: {data['prompt_hash'][:16]}...")
            return True
        else:
            print(f"[FAIL] Failed to get prompt hash")
            return False


async def test_extract_insight():
    """Test insight extraction"""
    print("\nTesting insight extraction...")

    test_conversation = {
        "user_message": "I'm struggling with async Python bugs. They're really hard to debug.",
        "assistant_message": "One helpful technique is to add print statements with timestamps to visualize the execution order. You can use datetime.now() to see exactly when each coroutine runs. This helps identify race conditions.",
        "timestamp": datetime.now().isoformat(),
        "user_config": {
            "display_name": "TestUser",
            "contact_method": "test@example.com",
            "contact_preference": "open_to_questions"
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{TEE_API_URL}/extract_insight",
            json=test_conversation
        )

        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Extraction completed")
            print(f"  Shared: {result['shared']}")
            if result['shared']:
                print(f"  Preview: {result.get('insight_preview', '')}")
            else:
                print(f"  Reason: {result.get('reason', '')}")
            return True
        else:
            print(f"[FAIL] Extraction failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False


async def test_read_insights():
    """Test reading insights"""
    print("\nTesting read insights...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{TEE_API_URL}/read_insights?limit=5")

        if response.status_code == 200:
            data = response.json()
            insights = data.get("insights", [])
            print(f"[OK] Read {len(insights)} insights")

            if insights:
                print("\nRecent insights:")
                for i, insight in enumerate(insights[:3], 1):
                    print(f"  {i}. [{insight.get('category', 'unknown')}] {insight.get('insight', '')[:80]}...")
            else:
                print("  (No insights yet - try extracting one first)")

            return True
        else:
            print(f"[FAIL] Read failed: {response.status_code}")
            return False


async def test_query():
    """Test querying insights"""
    print("\nTesting query insights...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TEE_API_URL}/query_insights",
            json={"query": "python debugging", "limit": 5}
        )

        if response.status_code == 200:
            data = response.json()
            insights = data.get("insights", [])
            print(f"[OK] Found {len(insights)} insights matching 'python debugging'")
            return True
        else:
            print(f"[FAIL] Query failed: {response.status_code}")
            return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Hivemind Local Test Suite")
    print("=" * 60)
    print()
    print("Make sure TEE API is running: python src/tee_api.py")
    print()

    results = []

    results.append(await test_health())
    results.append(await test_prompt_hash())
    results.append(await test_extract_insight())
    results.append(await test_read_insights())
    results.append(await test_query())

    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n[OK] All tests passed! Your local setup is working.")
        print("\nNext steps:")
        print("1. Configure Claude Desktop to use the MCP server")
        print("2. Test with real conversations")
        print("3. Build the web feed interface")
    else:
        print("\n[FAIL] Some tests failed. Check the errors above.")
        print("\nCommon issues:")
        print("- Make sure TEE API is running: python src/tee_api.py")
        print("- Check environment variables are set (.env file)")
        print("- Verify Firestore credentials are valid")


if __name__ == "__main__":
    asyncio.run(main())
