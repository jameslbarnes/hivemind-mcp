#!/usr/bin/env python3
"""
Hivemind CLI - Setup and management tool
"""

import json
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "hivemind"
CONSENT_FILE = CONFIG_DIR / "consent.json"


def init_consent():
    """Interactive consent setup"""
    print("=" * 60)
    print("Hivemind Setup - Asynchronous Group Mind")
    print("=" * 60)
    print()
    print("This tool shares anonymized insights from your Claude conversations")
    print("with your trusted group. You can see what others are learning and")
    print("connect with people who can help.")
    print()

    enable = input("Enable sharing? [y/N]: ").lower().strip()

    if enable != 'y':
        print("\nSharing disabled. You can enable later with: python hivemind_cli.py init")
        save_consent({
            "enabled": False,
            "setup_complete": True
        })
        return

    print("\n--- Attribution Settings ---")
    print("How should you appear in the feed?")
    print("1. Anonymous (no attribution)")
    print("2. Pseudonym (choose a display name)")
    print("3. Real name")

    choice = input("Choose [1/2/3]: ").strip()

    display_name = None
    if choice == "2":
        display_name = input("Enter pseudonym: ").strip()
    elif choice == "3":
        display_name = input("Enter your name: ").strip()

    contact_method = None
    contact_pref = "just_sharing"

    if display_name:
        print("\n--- Contact Settings ---")
        add_contact = input("Allow people to contact you? [y/N]: ").lower().strip()

        if add_contact == 'y':
            print("How can people reach you?")
            print("Examples: discord:username#1234, email:you@example.com, matrix:@you:server.org")
            contact_method = input("Contact method: ").strip()

            print("\nWhat are you open to?")
            print("1. Questions about my insights")
            print("2. Mentoring/longer conversations")
            print("3. Collaboration opportunities")

            pref_choice = input("Choose [1/2/3]: ").strip()

            contact_pref = {
                "1": "open_to_questions",
                "2": "available_for_mentoring",
                "3": "open_to_collaboration"
            }.get(pref_choice, "open_to_questions")

    config = {
        "enabled": True,
        "setup_complete": True,
        "display_name": display_name,
        "contact_method": contact_method,
        "contact_preference": contact_pref
    }

    save_consent(config)

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"Sharing: Enabled")
    print(f"Display name: {display_name or 'Anonymous'}")
    if contact_method:
        print(f"Contact: {contact_method} ({contact_pref})")
    print("\nYou can change these settings anytime with: python hivemind_cli.py config")


def save_consent(config):
    """Save consent configuration"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONSENT_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def show_config():
    """Display current configuration"""
    if not CONSENT_FILE.exists():
        print("Not configured. Run: python hivemind_cli.py init")
        return

    with open(CONSENT_FILE) as f:
        config = json.load(f)

    print("Current Hivemind Configuration:")
    print(f"  Enabled: {config.get('enabled', False)}")
    print(f"  Display name: {config.get('display_name', 'Anonymous')}")
    print(f"  Contact: {config.get('contact_method', 'None')}")
    print(f"  Preference: {config.get('contact_preference', 'just_sharing')}")


def disable():
    """Disable sharing"""
    if not CONSENT_FILE.exists():
        print("Hivemind not configured.")
        return

    with open(CONSENT_FILE) as f:
        config = json.load(f)

    config['enabled'] = False
    save_consent(config)
    print("Sharing disabled.")


def enable():
    """Enable sharing"""
    if not CONSENT_FILE.exists():
        print("Please run setup first: python hivemind_cli.py init")
        return

    with open(CONSENT_FILE) as f:
        config = json.load(f)

    config['enabled'] = True
    save_consent(config)
    print("Sharing enabled.")


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Hivemind CLI")
        print()
        print("Commands:")
        print("  init      - Set up consent and preferences")
        print("  config    - Show current configuration")
        print("  enable    - Enable sharing")
        print("  disable   - Disable sharing")
        print()
        print("Example: python hivemind_cli.py init")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_consent()
    elif command == "config":
        show_config()
    elif command == "enable":
        enable()
    elif command == "disable":
        disable()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
