#!/usr/bin/env python3
"""
Demo: Policy Engine in Action
Shows how conversations are routed through policies to different spaces.

Run: python demo_policy_engine.py
"""

import asyncio
from src.space_manager import SpaceManager
from src.policy_engine import PolicyEngine
from src.models import RawConversationTurn, SpaceType


async def demo_couples_routing():
    """Demo: Routing conversations to a couples space."""
    print("\n" + "="*70)
    print("DEMO 1: COUPLES SPACE ROUTING")
    print("="*70)

    manager = SpaceManager()
    engine = PolicyEngine(manager)

    # Setup
    andrew = manager.create_user("Andrew")
    couples_space = manager.create_space(
        andrew.user_id,
        "Andrew & Jamila",
        SpaceType.ONE_ON_ONE,
        policy_template="couples"
    )

    print(f"\nSetup: Andrew created couples space (ID: {couples_space.space_id})")
    print(f"Policy includes: {', '.join(couples_space.policy.inclusion_criteria[:3])}")
    print(f"Policy excludes: {', '.join(couples_space.policy.exclusion_criteria[:3])}")

    # Test different conversation types
    conversations = [
        {
            "desc": "Emotional state (work stress)",
            "user": "I'm feeling stressed about work deadlines lately",
            "assistant": "That sounds challenging. Work stress can be difficult.",
            "expected": "SHARED (emotional state relevant to relationship)"
        },
        {
            "desc": "Weekend planning",
            "user": "What should we do this weekend together?",
            "assistant": "Maybe something relaxing?",
            "expected": "SHARED (relationship planning)"
        },
        {
            "desc": "Technical work details",
            "user": "Help me debug this Python code",
            "assistant": "Sure, let's look at it",
            "expected": "SKIPPED (technical details not relationship-relevant)"
        },
        {
            "desc": "Relationship conflict",
            "user": "I'm really frustrated about our household responsibilities",
            "assistant": "That's an important topic to discuss",
            "expected": "MAY NEED APPROVAL (high sensitivity)"
        }
    ]

    for i, conv in enumerate(conversations, 1):
        print(f"\n{'-'*70}")
        print(f"Conversation {i}: {conv['desc']}")
        print(f"User: \"{conv['user']}\"")
        print(f"Expected: {conv['expected']}")

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message=conv['user'],
            assistant_message=conv['assistant']
        )

        results = await engine.route_conversation(turn, andrew.user_id)
        result = results[0]

        print(f"\nActual result: {result.action.upper()}")
        print(f"Reason: {result.reason}")

        if result.action == "shared" and result.document:
            print(f"Content to share: \"{result.document.content[:100]}...\"")
            print(f"Confidence: {result.document.confidence_score}")
            print(f"Sensitivity: {result.document.sensitivity_score}")

        elif result.action == "approval_needed" and result.approval:
            print(f"Proposed content: \"{result.approval.proposed_content[:100]}...\"")
            print(f"Approval reason: {result.approval.reason_for_approval}")


async def demo_multi_space_routing():
    """Demo: Same conversation routes to different spaces differently."""
    print("\n" + "="*70)
    print("DEMO 2: MULTI-SPACE ROUTING")
    print("="*70)

    manager = SpaceManager()
    engine = PolicyEngine(manager)

    # Setup
    andrew = manager.create_user("Andrew")

    couples_space = manager.create_space(
        andrew.user_id, "Couples", SpaceType.ONE_ON_ONE, policy_template="couples"
    )

    team_space = manager.create_space(
        andrew.user_id, "Team", SpaceType.GROUP, policy_template="team"
    )

    public_space = manager.create_space(
        andrew.user_id, "Public Feed", SpaceType.PUBLIC, policy_template="public"
    )

    print(f"\nSetup: Andrew has 3 spaces:")
    print(f"  1. Couples (1:1, relationship context)")
    print(f"  2. Team (Group, work collaboration)")
    print(f"  3. Public Feed (Public, insights sharing)")

    # Same conversation processed for all spaces
    print(f"\n{'-'*70}")
    print("Conversation: Work stress affecting relationships")
    print("User: \"I'm feeling stressed about work which is affecting my relationships\"")

    turn = RawConversationTurn(
        user_id=andrew.user_id,
        user_message="I'm feeling stressed about work which is affecting my relationships",
        assistant_message="That's a common challenge. Work-life balance is important."
    )

    results = await engine.route_conversation(turn, andrew.user_id)

    print(f"\n{'-'*70}")
    print("Routing Results:")

    for result in results:
        space = manager.get_space(result.space_id)
        print(f"\n  [{space.name}] ({space.space_type.value})")
        print(f"    Action: {result.action.upper()}")
        print(f"    Reason: {result.reason}")

        if result.action == "shared" and result.document:
            print(f"    Filtered content: \"{result.document.content[:80]}...\"")
            print(f"    Topics: {result.document.filtered_topics}")


async def demo_filtering_and_transformation():
    """Demo: How content is filtered and transformed."""
    print("\n" + "="*70)
    print("DEMO 3: CONTENT FILTERING & TRANSFORMATION")
    print("="*70)

    manager = SpaceManager()
    engine = PolicyEngine(manager)

    andrew = manager.create_user("Andrew")
    couples_space = manager.create_space(
        andrew.user_id, "Andrew & Jamila", SpaceType.ONE_ON_ONE, policy_template="couples"
    )

    print("\nPolicy Transformations:")
    print(f"  Remove names: {couples_space.policy.transformation_rules.remove_names}")
    print(f"  Preserve emotional tone: {couples_space.policy.transformation_rules.preserve_emotional_tone}")
    print(f"  Generalize situations: {couples_space.policy.transformation_rules.generalize_situations}")

    # Conversation with names
    original = "I talked to Jamila about feeling stressed. She suggested we spend time together."

    print(f"\n{'-'*70}")
    print("Original message:")
    print(f"  \"{original}\"")

    turn = RawConversationTurn(
        user_id=andrew.user_id,
        user_message=original,
        assistant_message="That sounds like a good conversation."
    )

    results = await engine.route_conversation(turn, andrew.user_id)
    result = results[0]

    if result.action == "shared" and result.document:
        print(f"\nFiltered/Transformed:")
        print(f"  \"{result.document.content}\"")
        print(f"\nTransformations applied:")
        print(f"  - Name 'Jamila' filtered out")
        print(f"  - Emotional context preserved")


async def demo_approval_workflow():
    """Demo: High sensitivity content requiring approval."""
    print("\n" + "="*70)
    print("DEMO 4: APPROVAL WORKFLOW")
    print("="*70)

    manager = SpaceManager()
    engine = PolicyEngine(manager)

    andrew = manager.create_user("Andrew")
    couples_space = manager.create_space(
        andrew.user_id, "Andrew & Jamila", SpaceType.ONE_ON_ONE, policy_template="couples"
    )

    print(f"\nApproval settings:")
    print(f"  Auto-approve threshold: {couples_space.policy.auto_approve_threshold}")
    print(f"  Requires approval if: {couples_space.policy.require_approval_if}")

    # High sensitivity conversation
    print(f"\n{'-'*70}")
    print("High Sensitivity Conversation:")
    print("User: \"I'm really angry about our argument last night\"")

    turn = RawConversationTurn(
        user_id=andrew.user_id,
        user_message="I'm really angry about our argument last night",
        assistant_message="That sounds like a difficult situation."
    )

    results = await engine.route_conversation(turn, andrew.user_id)
    result = results[0]

    print(f"\nResult: {result.action.upper()}")

    if result.action == "approval_needed" and result.approval:
        print(f"\nApproval Queue Entry:")
        print(f"  Proposed content: \"{result.approval.proposed_content}\"")
        print(f"  Reason: {result.approval.reason_for_approval}")
        print(f"  Confidence: {result.approval.confidence_score}")
        print(f"  Sensitivity: {result.approval.sensitivity_score}")
        print(f"\n  User would review and decide:")
        print(f"    [Approve] - Share as-is")
        print(f"    [Modify] - Edit before sharing")
        print(f"    [Reject] - Don't share")


async def main():
    """Run all demos."""
    print("\n>>> Policy Engine Demo\n")

    await demo_couples_routing()
    input("\n[Press Enter to continue to next demo...]")

    await demo_multi_space_routing()
    input("\n[Press Enter to continue to next demo...]")

    await demo_filtering_and_transformation()
    input("\n[Press Enter to continue to next demo...]")

    await demo_approval_workflow()

    print("\n" + "="*70)
    print("ALL DEMOS COMPLETE!")
    print("="*70)
    print("\nKey Takeaways:")
    print("  1. Conversations automatically route to relevant spaces")
    print("  2. Each space has different filtering rules")
    print("  3. Content is transformed based on policy")
    print("  4. High sensitivity content requires approval")
    print("  5. All routing is transparent and verifiable")
    print("\nNext: Integrate with MCP server for Claude Code!")


if __name__ == "__main__":
    asyncio.run(main())
