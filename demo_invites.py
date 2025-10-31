#!/usr/bin/env python3
"""
Demo: Invite Code System
Shows how invites work currently and what's missing.

Run: python demo_invites.py
"""

from src.space_manager import SpaceManager
from src.models import SpaceType


def demo_basic_invite():
    """Show basic invite flow."""
    print("\n" + "="*70)
    print("DEMO 1: BASIC INVITE CODE FLOW")
    print("="*70)

    manager = SpaceManager()

    # Andrew creates space
    print("\n[Step 1] Andrew creates a couples space...")
    andrew = manager.create_user("Andrew Miller", "andrew@example.com")
    space = manager.create_space(
        andrew.user_id,
        "Andrew & Jamila",
        SpaceType.ONE_ON_ONE,
        policy_template="couples"
    )

    print(f"  Space created: {space.name}")
    print(f"  Space ID: {space.space_id}")
    print(f"  Invite code: {space.invite_code}")
    print(f"\n  Andrew now needs to send '{space.invite_code}' to Jamila")
    print(f"  (via Signal, email, etc. - not automated)")

    # Jamila joins
    print("\n[Step 2] Jamila receives the code and joins...")
    jamila = manager.create_user("Jamila", "jamila@example.com")

    success = manager.join_space(space.space_id, jamila.user_id, space.invite_code)

    if success:
        print(f"  [OK] Jamila successfully joined using code '{space.invite_code}'")
        print(f"  Space now has {len(space.members)} members")

    # What's missing
    print("\n[What's Missing]")
    print("  [X] No notification that Jamila joined")
    print("  [X] No way for Jamila to see pending invites")
    print("  [X] No way to browse Andrew's spaces before joining")
    print("  [X] No invite expiration or usage limits")
    print("  [X] No way to revoke invite codes")


def demo_group_invite():
    """Show group invite flow."""
    print("\n" + "="*70)
    print("DEMO 2: GROUP INVITE FLOW")
    print("="*70)

    manager = SpaceManager()

    # Andrew creates hacker house
    print("\n[Step 1] Andrew creates a hacker house space...")
    andrew = manager.create_user("Andrew")
    team = manager.create_space(
        andrew.user_id,
        "Pirate Ship",
        SpaceType.GROUP,
        policy_template="team"
    )

    print(f"  Space: {team.name}")
    print(f"  Invite code: {team.invite_code}")
    print(f"\n  Andrew shares code in Signal group chat")

    # Multiple people join
    print("\n[Step 2] Multiple people join with the same code...")
    members = ["Novel", "Alexis", "Ron", "Eugene"]

    for name in members:
        user = manager.create_user(name)
        manager.join_space(team.space_id, user.user_id, team.invite_code)
        print(f"  [OK] {name} joined")

    print(f"\n  Total members: {len(team.members)}")

    # What's missing
    print("\n[What's Missing]")
    print("  [X] No member roles (admin, moderator, member)")
    print("  [X] Can't remove members")
    print("  [X] Can't see who's in the space before joining")
    print("  [X] No member approval workflow")
    print("  [X] Same code used by everyone (can't track who invited whom)")


def demo_multiple_spaces():
    """Show user with multiple spaces."""
    print("\n" + "="*70)
    print("DEMO 3: USER WITH MULTIPLE SPACES")
    print("="*70)

    manager = SpaceManager()

    andrew = manager.create_user("Andrew")

    # Create multiple spaces
    print("\n[Step 1] Andrew creates multiple spaces...")

    couples = manager.create_space(
        andrew.user_id, "Andrew & Jamila",
        SpaceType.ONE_ON_ONE, policy_template="couples"
    )
    print(f"  1. {couples.name} (code: {couples.invite_code})")

    team = manager.create_space(
        andrew.user_id, "Pirate Ship",
        SpaceType.GROUP, policy_template="team"
    )
    print(f"  2. {team.name} (code: {team.invite_code})")

    public = manager.create_space(
        andrew.user_id, "Public Feed",
        SpaceType.PUBLIC, policy_template="public"
    )
    print(f"  3. {public.name} (code: {public.invite_code})")

    # List spaces
    print("\n[Step 2] Andrew's spaces...")
    spaces = manager.list_user_spaces(andrew.user_id)

    for space in spaces:
        print(f"  - {space.name} ({space.space_type.value})")
        print(f"    Members: {len(space.members)}")
        print(f"    Invite: {space.invite_code}")

    # What's missing
    print("\n[What's Missing]")
    print("  [X] No way to organize/categorize spaces")
    print("  [X] No space search/filter")
    print("  [X] No space metadata (description, tags, etc.)")
    print("  [X] No space settings (archive, mute, etc.)")
    print("  [X] No way to see which spaces are active")


def demo_invite_failures():
    """Show what happens with wrong invite codes."""
    print("\n" + "="*70)
    print("DEMO 4: INVITE CODE VALIDATION")
    print("="*70)

    manager = SpaceManager()

    andrew = manager.create_user("Andrew")
    space = manager.create_space(
        andrew.user_id, "Test Space",
        SpaceType.ONE_ON_ONE, policy_template="couples"
    )

    jamila = manager.create_user("Jamila")

    # Try wrong code
    print("\n[Test 1] Try joining with wrong code...")
    success = manager.join_space(space.space_id, jamila.user_id, "WRONGCODE")
    print(f"  Result: {'[OK] Joined' if success else '[X] Failed (wrong code)'}")

    # Try correct code
    print("\n[Test 2] Try joining with correct code...")
    success = manager.join_space(space.space_id, jamila.user_id, space.invite_code)
    print(f"  Result: {'[OK] Joined' if success else '[X] Failed'}")

    # Try joining again
    print("\n[Test 3] Try joining same space again...")
    success = manager.join_space(space.space_id, jamila.user_id, space.invite_code)
    print(f"  Result: {'[OK] Joined' if success else '[X] Failed (already a member)'}")

    # Try exceeding member limit
    print("\n[Test 4] Try adding 3rd person to 1:1 space...")
    ron = manager.create_user("Ron")
    success = manager.join_space(space.space_id, ron.user_id, space.invite_code)
    print(f"  Result: {'[OK] Joined' if success else '[X] Failed (max 2 members for 1:1)'}")

    # What's working
    print("\n[What's Working]")
    print("  [OK] Invite code validation")
    print("  [OK] Member limit enforcement")
    print("  [OK] Duplicate member prevention")

    # What's missing
    print("\n[What's Missing]")
    print("  [X] No error messages (just True/False)")
    print("  [X] No invite code expiration")
    print("  [X] No usage limits (one-time codes)")
    print("  [X] No code regeneration")


def main():
    """Run all demos."""
    print("\n>>> Invite Code System Demo\n")

    demo_basic_invite()
    input("\n[Press Enter to continue...]")

    demo_group_invite()
    input("\n[Press Enter to continue...]")

    demo_multiple_spaces()
    input("\n[Press Enter to continue...]")

    demo_invite_failures()

    print("\n" + "="*70)
    print("SUMMARY: CURRENT INVITE SYSTEM")
    print("="*70)

    print("\n[OK] What Works:")
    print("  - 8-character hex invite codes")
    print("  - Code validation on join")
    print("  - Member limit enforcement")
    print("  - Same code for group spaces")
    print("  - Duplicate prevention")

    print("\n[X] What's Missing (from transcript):")
    print("  - Notifications when someone joins")
    print("  - Pending invite management")
    print("  - Invite expiration/revocation")
    print("  - Member roles and permissions")
    print("  - Space discovery before joining")
    print("  - Agent-suggested space creation")
    print("  - Agent-facilitated invitations")

    print("\n[->] Next Steps:")
    print("  1. Add invite notifications and pending management")
    print("  2. Add member roles and removal")
    print("  3. Integrate with MCP for agent-driven invites")
    print("  4. Add space discovery and browsing")


if __name__ == "__main__":
    main()
