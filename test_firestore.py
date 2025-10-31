#!/usr/bin/env python3
"""
Test Firestore connection and basic operations.
Run this to verify your setup before using the MCP server.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Testing Firestore Connection...")
print("=" * 70)

# Check environment variables
project_id = os.getenv("FIRESTORE_PROJECT")
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

print(f"\nProject ID: {project_id}")
print(f"Credentials: {credentials_path}")

if not project_id:
    print("\n✗ ERROR: FIRESTORE_PROJECT not set!")
    print("Please create a .env file with:")
    print("  FIRESTORE_PROJECT=your-project-id")
    sys.exit(1)

# Try to import Firestore
try:
    from google.cloud import firestore
    print("\n✓ google-cloud-firestore installed")
except ImportError:
    print("\n✗ ERROR: google-cloud-firestore not installed!")
    print("Run: pip install google-cloud-firestore")
    sys.exit(1)

# Try to connect
try:
    db = firestore.Client(project=project_id)
    print(f"✓ Connected to Firestore project: {project_id}")
except Exception as e:
    print(f"\n✗ ERROR connecting to Firestore:")
    print(f"  {e}")
    print("\nTroubleshooting:")
    print("  1. Verify FIRESTORE_PROJECT is correct")
    print("  2. Check GOOGLE_APPLICATION_CREDENTIALS points to valid key")
    print("  3. Ensure Firestore API is enabled in Google Cloud")
    sys.exit(1)

# Try to list collections
try:
    collections = list(db.collections())
    print(f"✓ Can access collections ({len(collections)} found)")
except Exception as e:
    print(f"\n✗ ERROR accessing collections:")
    print(f"  {e}")
    sys.exit(1)

# Test basic operations
try:
    print("\nTesting basic operations...")

    # Create a test document
    test_ref = db.collection("_test").document("connectivity_test")
    test_ref.set({
        "timestamp": firestore.SERVER_TIMESTAMP,
        "status": "connected",
        "test": True
    })
    print("✓ Can write documents")

    # Read it back
    doc = test_ref.get()
    assert doc.exists
    print("✓ Can read documents")

    # Delete it
    test_ref.delete()
    print("✓ Can delete documents")

except Exception as e:
    print(f"\n✗ ERROR with basic operations:")
    print(f"  {e}")
    sys.exit(1)

# Test FirestoreSpaceManager
try:
    print("\nTesting FirestoreSpaceManager...")

    from src.firestore_manager import FirestoreSpaceManager
    from src.models import SpaceType

    manager = FirestoreSpaceManager(project_id=project_id)
    print("✓ FirestoreSpaceManager initialized")

    # Create a test user
    user = manager.create_user("Test User", "test@example.com")
    print(f"✓ Created test user: {user.user_id}")

    # Create a test space
    space = manager.create_space(
        user.user_id,
        "Test Space",
        SpaceType.GROUP,
        policy_template="team"
    )
    print(f"✓ Created test space: {space.space_id}")
    print(f"  Invite code: {space.invite_code}")

    # Clean up
    manager.spaces_col.document(space.space_id).delete()
    manager.users_col.document(user.user_id).delete()
    print("✓ Cleaned up test data")

except Exception as e:
    print(f"\n✗ ERROR with FirestoreSpaceManager:")
    print(f"  {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ ALL TESTS PASSED!")
print("=" * 70)
print("\nYour Firestore setup is working correctly.")
print("\nNext steps:")
print("  1. Configure Claude Code (see SETUP_PRODUCTION.md)")
print("  2. Start web app: python web_app.py")
print("  3. Test MCP server: Check Claude Code tools")
