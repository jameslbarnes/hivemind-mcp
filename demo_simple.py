#!/usr/bin/env python3
"""
Simple demo of hivemind multi-space system (no fancy formatting).
Run: python demo_simple.py
"""

from src.space_manager import SpaceManager
from src.models import SpaceType


def demo_couples():
    """Demo: Creating a couples space."""
    print("\n" + "="*70)
    print("DEMO 1: COUPLES RELATIONSHIP SPACE")
    print("="*70)

    manager = SpaceManager()

    print("\n[Step 1] Andrew creates an account...")
    andrew = manager.create_user("Andrew Miller", "andrew@example.com")
    print(f"  Created user: {andrew.display_name} ({andrew.user_id})")

    print("\n[Step 2] Andrew creates a relationship space...")
    space = manager.create_space(
        creator_user_id=andrew.user_id,
        name="Andrew & Jamila",
        space_type=SpaceType.ONE_ON_ONE,
        description="Shared relationship context",
        policy_template="couples"
    )
    print(f"  Created space: {space.name}")
    print(f"  Space ID: {space.space_id}")
    print(f"  Invite code: {space.invite_code}")
    print(f"  Members: {len(space.members)}")

    print("\n[Step 3] Viewing the policy...")
    print(f"  Includes: {', '.join(space.policy.inclusion_criteria[:3])}")
    print(f"  Excludes: {', '.join(space.policy.exclusion_criteria[:3])}")
    print(f"  Remove names: {space.policy.transformation_rules.remove_names}")
    print(f"  Preserve emotion: {space.policy.transformation_rules.preserve_emotional_tone}")

    print("\n[Step 4] Jamila joins with invite code...")
    jamila = manager.create_user("Jamila", "jamila@example.com")
    success = manager.join_space(space.space_id, jamila.user_id, space.invite_code)
    print(f"  Join result: {'SUCCESS' if success else 'FAILED'}")

    space = manager.get_space(space.space_id)
    print(f"  Space now has {len(space.members)} members:")
    for member in space.members:
        user = manager.get_user(member.user_id)
        print(f"    - {user.display_name} ({member.role})")

    print("\n[Step 5] Both can see the space...")
    andrew_spaces = manager.list_user_spaces(andrew.user_id)
    jamila_spaces = manager.list_user_spaces(jamila.user_id)
    print(f"  Andrew's spaces: {len(andrew_spaces)}")
    print(f"  Jamila's spaces: {len(jamila_spaces)}")

    print("\n[What this enables]")
    print("  - Andrew can share emotional state without details")
    print("  - Jamila sees when Andrew needs support")
    print("  - Work details stay private")
    print("  - Relationship topics are preserved")


def demo_hacker_house():
    """Demo: Creating a group space."""
    print("\n" + "="*70)
    print("DEMO 2: HACKER HOUSE GROUP SPACE")
    print("="*70)

    manager = SpaceManager()

    print("\n[Step 1] Andrew creates a hacker house space...")
    andrew = manager.create_user("Andrew Miller", "andrew@example.com")

    pirate_ship = manager.create_space(
        creator_user_id=andrew.user_id,
        name="Pirate Ship",
        space_type=SpaceType.GROUP,
        description="NYC hacker house - Jan 2025",
        policy_template="team"
    )
    print(f"  Created space: {pirate_ship.name}")
    print(f"  Invite code: {pirate_ship.invite_code}")

    print("\n[Step 2] Other hackers join the space...")
    for name in ["Novel", "Alexis", "Ron", "Eugene"]:
        user = manager.create_user(name)
        success = manager.join_space(
            pirate_ship.space_id,
            user.user_id,
            pirate_ship.invite_code
        )
        print(f"  {name}: {'JOINED' if success else 'FAILED'}")

    print("\n[Step 3] Final space state...")
    space = manager.get_space(pirate_ship.space_id)
    print(f"  Members: {len(space.members)}")
    for member in space.members:
        user = manager.get_user(member.user_id)
        print(f"    - {user.display_name} ({member.role})")

    print("\n[What this enables]")
    print("  - Share what you're working on")
    print("  - Find collaboration opportunities")
    print("  - Ask for help when blocked")
    print("  - Ambient awareness of team activity")


def demo_multiple_spaces():
    """Demo: User in multiple spaces."""
    print("\n" + "="*70)
    print("DEMO 3: USER IN MULTIPLE SPACES")
    print("="*70)

    manager = SpaceManager()

    print("\n[Step 1] Andrew creates account...")
    andrew = manager.create_user("Andrew Miller", "andrew@example.com")

    print("\n[Step 2] Creating multiple spaces...")

    couples_space = manager.create_space(
        andrew.user_id, "Andrew & Jamila", SpaceType.ONE_ON_ONE, policy_template="couples"
    )
    print(f"  Created couples space: {couples_space.invite_code}")

    team_space = manager.create_space(
        andrew.user_id, "Flashbots Team", SpaceType.GROUP, policy_template="team"
    )
    print(f"  Created team space: {team_space.invite_code}")

    public_space = manager.create_space(
        andrew.user_id, "Public Insights", SpaceType.PUBLIC, policy_template="public"
    )
    print(f"  Created public space: {public_space.invite_code}")

    print("\n[Step 3] Andrew's spaces:")
    for space in manager.list_user_spaces(andrew.user_id):
        print(f"  - {space.name} ({space.space_type.value})")

    print("\n[What this enables]")
    print("  - Same conversation routes to different spaces")
    print("  - Each space has different privacy rules")
    print("  - Personal -> Couples -> Team -> Public")
    print("  - Automatic filtering based on context")


def demo_policy_comparison():
    """Demo: Compare different policy templates."""
    print("\n" + "="*70)
    print("DEMO 4: POLICY TEMPLATE COMPARISON")
    print("="*70)

    manager = SpaceManager()
    andrew = manager.create_user("Andrew", "andrew@example.com")

    templates = [
        ("couples", "1:1 Relationship"),
        ("team", "Team/Group"),
        ("public", "Public Feed")
    ]

    for template_name, description in templates:
        print(f"\n{'-'*70}")
        print(f"POLICY: {description.upper()} ({template_name})")
        print('-'*70)

        space = manager.create_space(
            andrew.user_id,
            f"Test {description}",
            SpaceType.GROUP,
            policy_template=template_name
        )

        policy = space.policy

        print(f"\nINCLUDES (what gets shared):")
        for criterion in policy.inclusion_criteria:
            print(f"  + {criterion}")

        print(f"\nEXCLUDES (what's filtered out):")
        for criterion in policy.exclusion_criteria:
            print(f"  - {criterion}")

        print(f"\nTRANSFORMATIONS:")
        rules = policy.transformation_rules
        print(f"  Remove names: {rules.remove_names}")
        print(f"  Remove locations: {rules.remove_locations}")
        print(f"  Remove organizations: {rules.remove_organizations}")
        print(f"  Generalize situations: {rules.generalize_situations}")
        print(f"  Preserve emotional tone: {rules.preserve_emotional_tone}")
        print(f"  Detail level: {rules.detail_level}")

        print(f"\nAPPROVAL:")
        print(f"  Auto-approve threshold: {policy.auto_approve_threshold}")
        print(f"  Requires approval if: {', '.join(policy.require_approval_if) or 'None'}")


def main():
    """Run all demos."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        print("\n>>> Running quick demo...\n")
        demo_couples()
    else:
        print("\n>>> Running all demos...\n")
        demo_couples()
        input("\n[Press Enter to continue...]")

        demo_hacker_house()
        input("\n[Press Enter to continue...]")

        demo_multiple_spaces()
        input("\n[Press Enter to continue...]")

        demo_policy_comparison()

        print("\n" + "="*70)
        print("ALL DEMOS COMPLETE!")
        print("="*70)
        print("\nNext: Run tests with 'python -m pytest tests/ -v'")
        print("Or try interactive mode: 'python demo.py'")


if __name__ == "__main__":
    main()
