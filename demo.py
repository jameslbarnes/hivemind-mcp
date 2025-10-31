#!/usr/bin/env python3
"""
Interactive demo of hivemind multi-space system.
Run: python demo.py
"""

import json
from src.space_manager import SpaceManager
from src.models import SpaceType


class HivemindDemo:
    """Interactive demo of space management."""

    def __init__(self):
        self.manager = SpaceManager()
        self.current_user_id = None

    def print_header(self, text):
        """Print a section header."""
        print("\n" + "=" * 70)
        print(f"  {text}")
        print("=" * 70)

    def print_space(self, space):
        """Pretty print a space."""
        print(f"\n📦 Space: {space.name}")
        print(f"   ID: {space.space_id}")
        print(f"   Type: {space.space_type.value}")
        print(f"   Invite Code: {space.invite_code}")
        print(f"   Created by: {space.created_by}")
        print(f"   Members: {len(space.members)}")

        for member in space.members:
            user = self.manager.get_user(member.user_id)
            role_emoji = "👑" if member.role == "owner" else "👤"
            print(f"      {role_emoji} {user.display_name if user else member.user_id} ({member.role})")

        print(f"\n   📋 Policy Settings:")
        print(f"      - Include: {', '.join(space.policy.inclusion_criteria[:3])}...")
        print(f"      - Exclude: {', '.join(space.policy.exclusion_criteria[:3])}...")
        print(f"      - Auto-approve threshold: {space.policy.auto_approve_threshold}")
        print(f"      - Remove names: {space.policy.transformation_rules.remove_names}")
        print(f"      - Preserve emotion: {space.policy.transformation_rules.preserve_emotional_tone}")

    def print_user(self, user):
        """Pretty print a user."""
        print(f"\n👤 User: {user.display_name}")
        print(f"   ID: {user.user_id}")
        print(f"   Contact: {user.contact_method or 'Not set'}")
        print(f"   Spaces: {len(user.spaces)}")

    def demo_couples_scenario(self):
        """Demo: Creating a couples space."""
        self.print_header("Demo 1: Couples Relationship Space")

        print("\n1️⃣  Andrew creates an account...")
        andrew = self.manager.create_user("Andrew Miller", "andrew@example.com")
        self.print_user(andrew)

        print("\n2️⃣  Andrew creates a relationship space with Jamila...")
        space = self.manager.create_space(
            creator_user_id=andrew.user_id,
            name="Andrew & Jamila",
            space_type=SpaceType.ONE_ON_ONE,
            description="Shared relationship context",
            policy_template="couples"
        )
        self.print_space(space)

        print("\n3️⃣  Jamila creates an account and joins using invite code...")
        jamila = self.manager.create_user("Jamila", "jamila@example.com")
        success = self.manager.join_space(space.space_id, jamila.user_id, space.invite_code)

        if success:
            print(f"   ✅ Jamila successfully joined!")
            self.print_space(self.manager.get_space(space.space_id))
        else:
            print(f"   ❌ Failed to join")

        print("\n4️⃣  Both users can see the space...")
        andrew_spaces = self.manager.list_user_spaces(andrew.user_id)
        jamila_spaces = self.manager.list_user_spaces(jamila.user_id)

        print(f"   Andrew's spaces: {len(andrew_spaces)}")
        print(f"   Jamila's spaces: {len(jamila_spaces)}")

        print("\n✨ What this enables:")
        print("   • Andrew can share emotional state without details")
        print("   • Jamila sees when Andrew needs support")
        print("   • Work details stay private")
        print("   • Relationship topics are preserved")

        return andrew, jamila, space

    def demo_hacker_house_scenario(self):
        """Demo: Creating a group space."""
        self.print_header("Demo 2: Hacker House Group Space")

        print("\n1️⃣  Andrew creates a hacker house space...")
        andrew = self.manager.create_user("Andrew Miller", "andrew@example.com")

        pirate_ship = self.manager.create_space(
            creator_user_id=andrew.user_id,
            name="Pirate Ship",
            space_type=SpaceType.GROUP,
            description="NYC hacker house - Jan 2025",
            policy_template="team"
        )
        self.print_space(pirate_ship)

        print("\n2️⃣  Other hackers join the space...")
        for name in ["Novel", "Alexis", "Ron", "Eugene"]:
            user = self.manager.create_user(name)
            success = self.manager.join_space(
                pirate_ship.space_id,
                user.user_id,
                pirate_ship.invite_code
            )
            print(f"   {'✅' if success else '❌'} {name} joined")

        print("\n3️⃣  Final space state...")
        updated_space = self.manager.get_space(pirate_ship.space_id)
        self.print_space(updated_space)

        print("\n✨ What this enables:")
        print("   • Share what you're working on")
        print("   • Find collaboration opportunities")
        print("   • Ask for help when blocked")
        print("   • Ambient awareness of team activity")

        return pirate_ship

    def demo_multiple_spaces(self):
        """Demo: User in multiple spaces."""
        self.print_header("Demo 3: User in Multiple Spaces")

        print("\n1️⃣  Andrew creates account...")
        andrew = self.manager.create_user("Andrew Miller", "andrew@example.com")

        print("\n2️⃣  Creating multiple spaces...")

        # Couples space
        couples_space = self.manager.create_space(
            andrew.user_id,
            "Andrew & Jamila",
            SpaceType.ONE_ON_ONE,
            policy_template="couples"
        )
        print(f"   ✅ Created couples space: {couples_space.invite_code}")

        # Team space
        team_space = self.manager.create_space(
            andrew.user_id,
            "Flashbots Team",
            SpaceType.GROUP,
            policy_template="team"
        )
        print(f"   ✅ Created team space: {team_space.invite_code}")

        # Public space
        public_space = self.manager.create_space(
            andrew.user_id,
            "Public Insights",
            SpaceType.PUBLIC,
            policy_template="public"
        )
        print(f"   ✅ Created public space: {public_space.invite_code}")

        print("\n3️⃣  Andrew's spaces:")
        for space in self.manager.list_user_spaces(andrew.user_id):
            print(f"   • {space.name} ({space.space_type.value})")

        print("\n✨ What this enables:")
        print("   • Same conversation routes to different spaces")
        print("   • Each space has different privacy rules")
        print("   • Personal → Couples → Team → Public")
        print("   • Automatic filtering based on context")

    def demo_policy_comparison(self):
        """Demo: Compare different policy templates."""
        self.print_header("Demo 4: Policy Template Comparison")

        andrew = self.manager.create_user("Andrew", "andrew@example.com")

        templates = [
            ("couples", "1:1 Relationship"),
            ("team", "Team/Group"),
            ("public", "Public Feed")
        ]

        for template_name, description in templates:
            print(f"\n{'='*70}")
            print(f"📋 {description.upper()} POLICY ({template_name})")
            print('='*70)

            space = self.manager.create_space(
                andrew.user_id,
                f"Test {description}",
                SpaceType.GROUP,
                policy_template=template_name
            )

            policy = space.policy

            print(f"\n✅ INCLUDES (what gets shared):")
            for criterion in policy.inclusion_criteria:
                print(f"   • {criterion}")

            print(f"\n❌ EXCLUDES (what's filtered out):")
            for criterion in policy.exclusion_criteria:
                print(f"   • {criterion}")

            print(f"\n🔧 TRANSFORMATIONS:")
            rules = policy.transformation_rules
            print(f"   • Remove names: {rules.remove_names}")
            print(f"   • Remove locations: {rules.remove_locations}")
            print(f"   • Remove organizations: {rules.remove_organizations}")
            print(f"   • Generalize situations: {rules.generalize_situations}")
            print(f"   • Preserve emotional tone: {rules.preserve_emotional_tone}")
            print(f"   • Detail level: {rules.detail_level}")

            print(f"\n🔒 APPROVAL:")
            print(f"   • Auto-approve threshold: {policy.auto_approve_threshold}")
            print(f"   • Requires approval if: {', '.join(policy.require_approval_if) or 'None'}")

    def interactive_mode(self):
        """Interactive CLI mode."""
        self.print_header("🤖 Hivemind Space Manager - Interactive Mode")

        print("\nCommands:")
        print("  1 - Demo: Couples scenario")
        print("  2 - Demo: Hacker house scenario")
        print("  3 - Demo: Multiple spaces")
        print("  4 - Demo: Policy comparison")
        print("  u - Create user")
        print("  s - Create space")
        print("  j - Join space")
        print("  l - List spaces")
        print("  v - View space details")
        print("  q - Quit")

        while True:
            print("\n" + "-" * 70)
            cmd = input("Command: ").strip().lower()

            if cmd == 'q':
                print("\n👋 Goodbye!")
                break

            elif cmd == '1':
                self.demo_couples_scenario()

            elif cmd == '2':
                self.demo_hacker_house_scenario()

            elif cmd == '3':
                self.demo_multiple_spaces()

            elif cmd == '4':
                self.demo_policy_comparison()

            elif cmd == 'u':
                name = input("Name: ").strip()
                email = input("Email (optional): ").strip() or None
                user = self.manager.create_user(name, email)
                self.print_user(user)
                self.current_user_id = user.user_id
                print(f"\n✅ Created user! (Now current user)")

            elif cmd == 's':
                if not self.current_user_id:
                    print("❌ Create a user first (u)")
                    continue

                name = input("Space name: ").strip()
                space_type = input("Type (1:1/group/public): ").strip().lower()

                if space_type == "1:1":
                    st = SpaceType.ONE_ON_ONE
                elif space_type == "group":
                    st = SpaceType.GROUP
                elif space_type == "public":
                    st = SpaceType.PUBLIC
                else:
                    print("❌ Invalid type")
                    continue

                template = input("Policy template (couples/team/public/none): ").strip() or None

                space = self.manager.create_space(
                    self.current_user_id,
                    name,
                    st,
                    policy_template=template
                )
                self.print_space(space)

            elif cmd == 'j':
                if not self.current_user_id:
                    print("❌ Create a user first (u)")
                    continue

                invite_code = input("Invite code: ").strip().upper()
                space = self.manager.get_space_by_invite_code(invite_code)

                if not space:
                    print(f"❌ Invalid invite code")
                    continue

                success = self.manager.join_space(
                    space.space_id,
                    self.current_user_id,
                    invite_code
                )

                if success:
                    print(f"✅ Joined {space.name}!")
                else:
                    print(f"❌ Failed to join (already member or space full)")

            elif cmd == 'l':
                if not self.current_user_id:
                    print("❌ Create a user first (u)")
                    continue

                spaces = self.manager.list_user_spaces(self.current_user_id)
                if not spaces:
                    print("No spaces yet")
                else:
                    print(f"\nYour {len(spaces)} space(s):")
                    for space in spaces:
                        print(f"\n  • {space.name} ({space.space_type.value})")
                        print(f"    ID: {space.space_id}")
                        print(f"    Invite: {space.invite_code}")
                        print(f"    Members: {len(space.members)}")

            elif cmd == 'v':
                space_id = input("Space ID: ").strip()
                space = self.manager.get_space(space_id)
                if space:
                    self.print_space(space)
                else:
                    print("❌ Space not found")

            else:
                print("❌ Unknown command")


def main():
    """Run the demo."""
    demo = HivemindDemo()

    # Quick automated demo mode
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "auto":
            print("\n>>> Running automated demos...\n")
            demo.demo_couples_scenario()
            input("\n[Press Enter to continue to next demo...]")
            demo.demo_hacker_house_scenario()
            input("\n[Press Enter to continue to next demo...]")
            demo.demo_multiple_spaces()
            input("\n[Press Enter to continue to next demo...]")
            demo.demo_policy_comparison()
            print("\n✨ All demos complete!")
            return

    # Interactive mode
    demo.interactive_mode()


if __name__ == "__main__":
    main()
