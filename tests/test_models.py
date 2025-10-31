"""
Tests for data models.
Run with: python -m pytest tests/test_models.py -v
"""

import pytest
from datetime import datetime
from src.models import (
    User, Space, SpaceType, SpaceMember, Policy,
    ConsentConfig, ContactPreference, AttributionLevel,
    RawConversationTurn, FilteredDocument,
    create_couples_policy, create_public_feed_policy, create_team_policy
)


class TestUser:
    """Test User model."""

    def test_create_user(self):
        """Test creating a user."""
        user = User(display_name="Test User", contact_method="test@example.com")

        assert user.user_id.startswith("usr_")
        assert user.display_name == "Test User"
        assert user.contact_method == "test@example.com"
        assert isinstance(user.created_at, datetime)
        assert user.spaces == []

    def test_user_to_dict(self):
        """Test converting user to dict."""
        user = User(display_name="Test User")
        data = user.to_dict()

        assert isinstance(data, dict)
        assert data['display_name'] == "Test User"
        assert isinstance(data['created_at'], str)

    def test_user_from_dict(self):
        """Test loading user from dict."""
        data = {
            'user_id': 'usr_test123',
            'display_name': 'Test User',
            'contact_method': 'test@example.com',
            'created_at': '2025-01-15T10:00:00',
            'consent_config': {
                'enabled': True,
                'contact_preference': 'open_to_questions',
                'default_attribution': 'full',
                'setup_complete': True
            },
            'spaces': []
        }

        user = User.from_dict(data)
        assert user.user_id == 'usr_test123'
        assert user.display_name == 'Test User'
        assert isinstance(user.created_at, datetime)


class TestPolicy:
    """Test Policy model."""

    def test_create_couples_policy(self):
        """Test couples policy template."""
        policy = create_couples_policy("spc_test")

        assert policy.space_id == "spc_test"
        assert "emotional_state" in policy.inclusion_criteria
        assert "work_details" in policy.exclusion_criteria
        assert policy.transformation_rules.preserve_emotional_tone is True
        assert "partner" in policy.trigger_keywords

    def test_create_public_feed_policy(self):
        """Test public feed policy template."""
        policy = create_public_feed_policy("spc_public")

        assert policy.space_id == "spc_public"
        assert "technical_insight" in policy.inclusion_criteria
        assert "personal_details" in policy.exclusion_criteria
        assert policy.transformation_rules.remove_names is True
        assert policy.auto_approve_threshold == 0.8

    def test_create_team_policy(self):
        """Test team policy template."""
        policy = create_team_policy("spc_team")

        assert policy.space_id == "spc_team"
        assert "work_progress" in policy.inclusion_criteria
        assert "proprietary_details" in policy.exclusion_criteria
        assert policy.transformation_rules.remove_names is False  # Keep team names
        assert "team" in policy.trigger_keywords

    def test_policy_serialization(self):
        """Test policy to/from dict."""
        policy = create_couples_policy("spc_test")
        data = policy.to_dict()

        assert isinstance(data, dict)
        assert isinstance(data['created_at'], str)

        loaded = Policy.from_dict(data)
        assert loaded.space_id == policy.space_id
        assert loaded.inclusion_criteria == policy.inclusion_criteria


class TestSpace:
    """Test Space model."""

    def test_create_space(self):
        """Test creating a space."""
        policy = create_couples_policy("spc_test")
        space = Space(
            space_type=SpaceType.ONE_ON_ONE,
            name="Test Space",
            policy=policy,
            created_by="usr_test"
        )

        assert space.space_id.startswith("spc_")
        assert space.space_type == SpaceType.ONE_ON_ONE
        assert space.name == "Test Space"
        assert len(space.invite_code) == 8
        assert space.members == []

    def test_space_membership(self):
        """Test space membership methods."""
        policy = create_couples_policy("spc_test")
        space = Space(
            space_type=SpaceType.GROUP,
            name="Test Group",
            policy=policy,
            created_by="usr_owner"
        )

        # Add members
        member1 = SpaceMember(user_id="usr_1", role="owner")
        member2 = SpaceMember(user_id="usr_2", role="member")
        space.members = [member1, member2]

        # Test is_member
        assert space.is_member("usr_1") is True
        assert space.is_member("usr_2") is True
        assert space.is_member("usr_3") is False

        # Test get_member
        m = space.get_member("usr_1")
        assert m is not None
        assert m.role == "owner"

    def test_space_serialization(self):
        """Test space to/from dict."""
        policy = create_public_feed_policy("spc_test")
        space = Space(
            space_type=SpaceType.PUBLIC,
            name="Public Feed",
            policy=policy,
            created_by="usr_test"
        )

        data = space.to_dict()
        assert isinstance(data, dict)
        assert isinstance(data['created_at'], str)

        loaded = Space.from_dict(data)
        assert loaded.space_id == space.space_id
        assert loaded.name == space.name


class TestConversationTurn:
    """Test conversation turn models."""

    def test_create_raw_turn(self):
        """Test creating raw conversation turn."""
        turn = RawConversationTurn(
            user_id="usr_test",
            user_message="I'm feeling stressed",
            assistant_message="I understand that's difficult"
        )

        assert turn.turn_id.startswith("turn_")
        assert turn.user_id == "usr_test"
        assert isinstance(turn.timestamp, datetime)
        assert turn.topics == []

    def test_turn_with_metadata(self):
        """Test turn with metadata."""
        turn = RawConversationTurn(
            user_id="usr_test",
            user_message="Working on TEE paper with Jamila",
            assistant_message="That sounds interesting",
            topics=["work", "TEE", "collaboration"],
            entities=["Jamila"]
        )

        assert "TEE" in turn.topics
        assert "Jamila" in turn.entities

    def test_turn_serialization(self):
        """Test turn to/from dict."""
        turn = RawConversationTurn(
            user_id="usr_test",
            user_message="Test message",
            assistant_message="Test response"
        )

        data = turn.to_dict()
        assert isinstance(data, dict)
        assert isinstance(data['timestamp'], str)

        loaded = RawConversationTurn.from_dict(data)
        assert loaded.turn_id == turn.turn_id
        assert loaded.user_message == turn.user_message


class TestFilteredDocument:
    """Test filtered document model."""

    def test_create_filtered_doc(self):
        """Test creating filtered document."""
        doc = FilteredDocument(
            space_id="spc_test",
            source_turn_id="turn_123",
            author_user_id="usr_test",
            content="Feeling stressed about work",
            original_topics=["work", "stress", "deadline"],
            filtered_topics=["work", "stress"],
            attribution_level=AttributionLevel.FULL,
            display_name="Test User",
            confidence_score=0.85,
            sensitivity_score=0.3
        )

        assert doc.doc_id.startswith("doc_")
        assert doc.space_id == "spc_test"
        assert doc.confidence_score == 0.85
        assert doc.approved is True

    def test_filtered_doc_serialization(self):
        """Test document to/from dict."""
        doc = FilteredDocument(
            space_id="spc_test",
            source_turn_id="turn_123",
            author_user_id="usr_test",
            content="Test content",
            attribution_level=AttributionLevel.ANONYMOUS,
            confidence_score=0.9,
            sensitivity_score=0.2
        )

        data = doc.to_dict()
        assert isinstance(data, dict)
        assert isinstance(data['created_at'], str)

        loaded = FilteredDocument.from_dict(data)
        assert loaded.doc_id == doc.doc_id
        assert loaded.content == doc.content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
