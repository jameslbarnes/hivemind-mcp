"""
Tests for Policy Engine.
Run with: python -m pytest tests/test_policy_engine.py -v
"""

import pytest
from datetime import datetime
from src.policy_engine import PolicyEngine, RouteResult
from src.space_manager import SpaceManager
from src.models import RawConversationTurn, SpaceType


class TestPolicyEngine:
    """Test PolicyEngine functionality."""

    @pytest.fixture
    def manager(self):
        """Create space manager."""
        return SpaceManager()

    @pytest.fixture
    def engine(self, manager):
        """Create policy engine with mock LLM."""
        return PolicyEngine(manager, llm_client=None)

    @pytest.fixture
    def andrew(self, manager):
        """Create test user Andrew."""
        return manager.create_user("Andrew", "andrew@example.com")

    @pytest.fixture
    def couples_space(self, manager, andrew):
        """Create couples space."""
        return manager.create_space(
            andrew.user_id,
            "Andrew & Jamila",
            SpaceType.ONE_ON_ONE,
            policy_template="couples"
        )

    @pytest.fixture
    def public_space(self, manager, andrew):
        """Create public space."""
        return manager.create_space(
            andrew.user_id,
            "Public Feed",
            SpaceType.PUBLIC,
            policy_template="public"
        )

    @pytest.mark.asyncio
    async def test_route_to_relevant_space(self, engine, andrew, couples_space):
        """Test routing conversation to relevant space."""

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm feeling stressed about work lately",
            assistant_message="That sounds difficult. Work stress can be challenging.",
            topics=["work", "stress", "emotional_state"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        assert len(results) == 1
        result = results[0]

        assert result.space_id == couples_space.space_id
        assert result.action == "shared"
        assert result.document is not None
        assert "stress" in result.document.content.lower()

    @pytest.mark.asyncio
    async def test_skip_irrelevant_space(self, engine, andrew, couples_space):
        """Test skipping space when content not relevant."""

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="How do I write a sorting algorithm in Python?",
            assistant_message="Here's a quick sort implementation...",
            topics=["programming", "algorithms"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        assert len(results) == 1
        result = results[0]

        assert result.space_id == couples_space.space_id
        assert result.action == "skipped"
        assert "does not match" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_filter_names_from_content(self, engine, andrew, couples_space):
        """Test that names are filtered out."""

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm stressed. Talked to Jamila about relationship stuff.",
            assistant_message="It's good you're communicating.",
            topics=["relationship", "emotional_state"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        result = results[0]
        assert result.action == "shared"
        assert result.document is not None

        # Name should be filtered
        content = result.document.content
        assert "Jamila" not in content or "[Person]" in content

    @pytest.mark.asyncio
    async def test_approval_needed_high_sensitivity(self, engine, andrew, couples_space):
        """Test that high sensitivity content requires approval."""

        # Modify policy to require approval for sensitivity > 0.5
        couples_space.policy.require_approval_if = ["sensitivity > 0.5"]

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm really angry and we had a big conflict about household responsibilities",
            assistant_message="That sounds like a difficult situation.",
            topics=["relationship", "conflict", "emotional_state"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        result = results[0]
        assert result.action == "approval_needed"
        assert result.approval is not None
        assert result.approval.sensitivity_score > 0.5

    @pytest.mark.asyncio
    async def test_route_to_multiple_spaces(self, engine, andrew, couples_space, public_space):
        """Test routing same conversation to multiple spaces."""

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I learned something about emotional intelligence today",
            assistant_message="That's great! Emotional intelligence is very valuable.",
            topics=["learning", "emotional_state"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        # Should route to both spaces
        assert len(results) == 2

        # Find which went where
        couples_result = next(r for r in results if r.space_id == couples_space.space_id)
        public_result = next(r for r in results if r.space_id == public_space.space_id)

        # Couples space: relevant (emotional_state)
        assert couples_result.action == "shared"

        # Public space: might be relevant (learning)
        # (depends on mock logic, but should process)
        assert public_result.action in ["shared", "skipped"]

    @pytest.mark.asyncio
    async def test_attribution_levels(self, engine, andrew, couples_space, public_space):
        """Test different attribution levels for different spaces."""

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm feeling stressed about work",
            assistant_message="That's understandable.",
            topics=["emotional_state", "work"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        for result in results:
            if result.action == "shared" and result.document:
                doc = result.document

                if result.space_id == couples_space.space_id:
                    # Couples space: full attribution
                    assert doc.display_name == "Andrew"
                    assert doc.contact_method == "andrew@example.com"

                elif result.space_id == public_space.space_id:
                    # Public space: full attribution by default
                    # (in real app, might be anonymous)
                    assert doc.attribution_level is not None

    @pytest.mark.asyncio
    async def test_confidence_scoring(self, engine, andrew, couples_space):
        """Test that confidence scores are assigned."""

        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm feeling stressed",
            assistant_message="I understand.",
            topics=["emotional_state"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        result = results[0]
        if result.action == "shared":
            assert result.document.confidence_score > 0
            assert result.document.confidence_score <= 1.0


class TestPolicyEngineScenarios:
    """Test realistic scenarios."""

    @pytest.fixture
    def manager(self):
        return SpaceManager()

    @pytest.fixture
    def engine(self, manager):
        return PolicyEngine(manager, llm_client=None)

    @pytest.mark.asyncio
    async def test_couples_relationship_scenario(self, engine, manager):
        """Test complete couples scenario."""

        # Setup
        andrew = manager.create_user("Andrew", "andrew@example.com")
        couples_space = manager.create_space(
            andrew.user_id,
            "Andrew & Jamila",
            SpaceType.ONE_ON_ONE,
            policy_template="couples"
        )

        # Scenario 1: Emotional state (should share)
        turn1 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I've been feeling stressed about work deadlines",
            assistant_message="Work stress can be challenging. Have you talked about this?",
            topics=["work", "stress", "emotional_state"]
        )

        results1 = await engine.route_conversation(turn1, andrew.user_id)
        assert len(results1) == 1
        assert results1[0].action == "shared"
        # Work details should be filtered but emotion preserved
        content1 = results1[0].document.content
        assert "stress" in content1.lower()

        # Scenario 2: Weekend plans (should share)
        turn2 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="What should I plan for this weekend with my partner?",
            assistant_message="Maybe something relaxing together?",
            topics=["relationship", "planning", "weekend"]
        )

        results2 = await engine.route_conversation(turn2, andrew.user_id)
        assert results2[0].action == "shared"

        # Scenario 3: Work technical details (should skip)
        turn3 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="Help me debug this Python code for my project",
            assistant_message="Sure, let's look at the code...",
            topics=["programming", "work", "technical"]
        )

        results3 = await engine.route_conversation(turn3, andrew.user_id)
        assert results3[0].action == "skipped"

    @pytest.mark.asyncio
    async def test_hacker_house_scenario(self, engine, manager):
        """Test team/group scenario."""

        andrew = manager.create_user("Andrew")
        team_space = manager.create_space(
            andrew.user_id,
            "Pirate Ship",
            SpaceType.GROUP,
            policy_template="team"
        )

        # Scenario 1: Work progress (should share)
        turn1 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm working on the TEE paper, making good progress",
            assistant_message="That's great!",
            topics=["work", "progress"]
        )

        results1 = await engine.route_conversation(turn1, andrew.user_id)
        assert results1[0].action == "shared"

        # Scenario 2: Asking for help (should share)
        turn2 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm blocked on the cryptography section, need help",
            assistant_message="Maybe ask someone with crypto experience?",
            topics=["work", "help", "blocker"]
        )

        results2 = await engine.route_conversation(turn2, andrew.user_id)
        assert results2[0].action == "shared"

        # Scenario 3: Personal relationship (should skip)
        turn3 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="Having some relationship issues lately",
            assistant_message="That can be difficult.",
            topics=["relationship", "personal"]
        )

        results3 = await engine.route_conversation(turn3, andrew.user_id)
        assert results3[0].action == "skipped"

    @pytest.mark.asyncio
    async def test_public_feed_scenario(self, engine, manager):
        """Test public feed scenario."""

        andrew = manager.create_user("Andrew")
        public_space = manager.create_space(
            andrew.user_id,
            "Public Feed",
            SpaceType.PUBLIC,
            policy_template="public"
        )

        # Scenario 1: Technical insight (should share)
        turn1 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I just learned that TEEs enable verifiable privacy",
            assistant_message="Yes, that's a key insight!",
            topics=["learning", "technical", "insight"]
        )

        results1 = await engine.route_conversation(turn1, andrew.user_id)
        assert results1[0].action == "shared"

        # Scenario 2: Personal details (should skip)
        turn2 = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I talked to Jamila about moving to San Francisco",
            assistant_message="That's a big decision.",
            topics=["personal", "relationship"]
        )

        results2 = await engine.route_conversation(turn2, andrew.user_id)
        assert results2[0].action == "skipped"

    @pytest.mark.asyncio
    async def test_multi_space_routing(self, engine, manager):
        """Test routing to multiple spaces with different filters."""

        andrew = manager.create_user("Andrew")

        couples_space = manager.create_space(
            andrew.user_id, "Couples", SpaceType.ONE_ON_ONE, policy_template="couples"
        )
        team_space = manager.create_space(
            andrew.user_id, "Team", SpaceType.GROUP, policy_template="team"
        )
        public_space = manager.create_space(
            andrew.user_id, "Public", SpaceType.PUBLIC, policy_template="public"
        )

        # Conversation about stress affects relationships and work
        turn = RawConversationTurn(
            user_id=andrew.user_id,
            user_message="I'm feeling stressed about work which is affecting my relationships",
            assistant_message="That's a common challenge. Work-life balance is important.",
            topics=["stress", "work", "relationship", "emotional_state"]
        )

        results = await engine.route_conversation(turn, andrew.user_id)

        assert len(results) == 3

        # Couples space: should share (emotional state + relationship)
        couples_result = next(r for r in results if r.space_id == couples_space.space_id)
        assert couples_result.action == "shared"

        # Team space: might share (work stress)
        team_result = next(r for r in results if r.space_id == team_space.space_id)
        # Could be shared, skipped, or need approval depending on stress/work emphasis
        assert team_result.action in ["shared", "skipped", "approval_needed"]

        # Public space: probably skip (too personal)
        public_result = next(r for r in results if r.space_id == public_space.space_id)
        # Likely skipped due to personal nature
        assert public_result.action in ["shared", "skipped"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
