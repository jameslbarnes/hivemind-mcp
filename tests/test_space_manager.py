"""
Tests for Space Manager.
Run with: python -m pytest tests/test_space_manager.py -v
"""

import pytest
from src.space_manager import SpaceManager
from src.models import SpaceType


class TestSpaceManager:
    """Test SpaceManager functionality."""

    @pytest.fixture
    def manager(self):
        """Create a fresh space manager for each test."""
        return SpaceManager()

    @pytest.fixture
    def user1(self, manager):
        """Create test user 1."""
        return manager.create_user("Andrew Miller", "andrew@example.com")

    @pytest.fixture
    def user2(self, manager):
        """Create test user 2."""
        return manager.create_user("Jamila", "jamila@example.com")

    def test_create_user(self, manager):
        """Test creating a user."""
        user = manager.create_user("Test User", "test@example.com")

        assert user.user_id.startswith("usr_")
        assert user.display_name == "Test User"
        assert user.contact_method == "test@example.com"

        # User should be retrievable
        retrieved = manager.get_user(user.user_id)
        assert retrieved is not None
        assert retrieved.user_id == user.user_id

    def test_create_1on1_space(self, manager, user1):
        """Test creating a 1:1 space."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Andrew & Jamila",
            space_type=SpaceType.ONE_ON_ONE,
            policy_template="couples"
        )

        assert space.space_id.startswith("spc_")
        assert space.name == "Andrew & Jamila"
        assert space.space_type == SpaceType.ONE_ON_ONE
        assert space.created_by == user1.user_id

        # Creator should be a member with owner role
        assert len(space.members) == 1
        assert space.members[0].user_id == user1.user_id
        assert space.members[0].role == "owner"

        # 1:1 space should have max 2 members
        assert space.settings.max_members == 2

        # Check policy
        assert "emotional_state" in space.policy.inclusion_criteria

    def test_create_group_space(self, manager, user1):
        """Test creating a group space."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Pirate Ship",
            space_type=SpaceType.GROUP,
            description="NYC hacker house",
            policy_template="team"
        )

        assert space.space_type == SpaceType.GROUP
        assert space.description == "NYC hacker house"
        assert space.settings.max_members is None  # No limit for groups

    def test_create_public_space(self, manager, user1):
        """Test creating a public space."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Public Feed",
            space_type=SpaceType.PUBLIC,
            policy_template="public"
        )

        assert space.space_type == SpaceType.PUBLIC
        assert space.settings.visibility == "public"
        assert space.settings.allow_member_invites is True
        assert space.settings.require_approval is False

    def test_invite_code_generation(self, manager, user1):
        """Test that invite codes are generated and work."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        # Invite code should exist and be uppercase
        assert len(space.invite_code) == 8
        assert space.invite_code.isupper()

        # Should be able to find space by invite code
        found = manager.get_space_by_invite_code(space.invite_code)
        assert found is not None
        assert found.space_id == space.space_id

    def test_join_space_with_invite_code(self, manager, user1, user2):
        """Test joining a space with invite code."""
        # User1 creates space
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        # User2 joins with invite code
        success = manager.join_space(
            space_id=space.space_id,
            user_id=user2.user_id,
            invite_code=space.invite_code
        )

        assert success is True
        assert len(space.members) == 2
        assert space.is_member(user2.user_id)

        # User2 should have space in their spaces list
        user2_obj = manager.get_user(user2.user_id)
        assert space.space_id in user2_obj.spaces

    def test_join_space_wrong_invite_code(self, manager, user1, user2):
        """Test that wrong invite code fails."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        success = manager.join_space(
            space_id=space.space_id,
            user_id=user2.user_id,
            invite_code="WRONGCODE"
        )

        assert success is False
        assert len(space.members) == 1

    def test_join_space_max_members(self, manager, user1, user2):
        """Test that max members limit is enforced."""
        # Create 1:1 space (max 2 members)
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="1:1 Space",
            space_type=SpaceType.ONE_ON_ONE
        )

        # User2 joins successfully
        success1 = manager.join_space(
            space_id=space.space_id,
            user_id=user2.user_id,
            invite_code=space.invite_code
        )
        assert success1 is True
        assert len(space.members) == 2

        # User3 tries to join but should fail
        user3 = manager.create_user("User3")
        success2 = manager.join_space(
            space_id=space.space_id,
            user_id=user3.user_id,
            invite_code=space.invite_code
        )
        assert success2 is False
        assert len(space.members) == 2

    def test_cant_join_twice(self, manager, user1, user2):
        """Test that user can't join same space twice."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        # Join once
        success1 = manager.join_space(
            space_id=space.space_id,
            user_id=user2.user_id,
            invite_code=space.invite_code
        )
        assert success1 is True

        # Try to join again
        success2 = manager.join_space(
            space_id=space.space_id,
            user_id=user2.user_id,
            invite_code=space.invite_code
        )
        assert success2 is False
        assert len(space.members) == 2

    def test_list_user_spaces(self, manager, user1):
        """Test listing user's spaces."""
        # Create multiple spaces
        space1 = manager.create_space(
            creator_user_id=user1.user_id,
            name="Space 1",
            space_type=SpaceType.PUBLIC
        )

        space2 = manager.create_space(
            creator_user_id=user1.user_id,
            name="Space 2",
            space_type=SpaceType.GROUP
        )

        # List user's spaces
        spaces = manager.list_user_spaces(user1.user_id)
        assert len(spaces) == 2
        space_ids = [s.space_id for s in spaces]
        assert space1.space_id in space_ids
        assert space2.space_id in space_ids

    def test_leave_space(self, manager, user1, user2):
        """Test leaving a space."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        manager.join_space(
            space_id=space.space_id,
            user_id=user2.user_id,
            invite_code=space.invite_code
        )

        assert len(space.members) == 2

        # User2 leaves
        success = manager.leave_space(space.space_id, user2.user_id)
        assert success is True
        assert len(space.members) == 1
        assert not space.is_member(user2.user_id)

        # User2 should not have space in their list
        user2_obj = manager.get_user(user2.user_id)
        assert space.space_id not in user2_obj.spaces

    def test_leave_empty_space_deletes_it(self, manager, user1):
        """Test that leaving empty private space deletes it."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        space_id = space.space_id
        invite_code = space.invite_code

        # Owner leaves
        manager.leave_space(space_id, user1.user_id)

        # Space should be deleted
        assert manager.get_space(space_id) is None
        assert manager.get_space_by_invite_code(invite_code) is None

    def test_get_space_members(self, manager, user1, user2):
        """Test getting all members of a space as User objects."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        manager.join_space(space.space_id, user2.user_id, space.invite_code)

        members = manager.get_space_members(space.space_id)
        assert len(members) == 2

        member_names = [m.display_name for m in members]
        assert "Andrew Miller" in member_names
        assert "Jamila" in member_names

    def test_update_policy(self, manager, user1):
        """Test updating a space's policy."""
        space = manager.create_space(
            creator_user_id=user1.user_id,
            name="Test Space",
            space_type=SpaceType.GROUP
        )

        original_version = space.policy.version

        # Update policy
        new_policy = space.policy.model_copy()
        new_policy.inclusion_criteria.append("new_criterion")

        success = manager.update_policy(space.space_id, new_policy)
        assert success is True

        # Check policy was updated
        updated_space = manager.get_space(space.space_id)
        assert updated_space.policy.version == original_version + 1
        assert "new_criterion" in updated_space.policy.inclusion_criteria


class TestSpaceScenarios:
    """Test realistic scenarios."""

    @pytest.fixture
    def manager(self):
        """Create a fresh space manager."""
        return SpaceManager()

    def test_couples_scenario(self, manager):
        """Test complete couples scenario."""
        # Andrew creates account
        andrew = manager.create_user("Andrew", "andrew@example.com")

        # Andrew creates relationship space
        space = manager.create_space(
            creator_user_id=andrew.user_id,
            name="Andrew & Jamila",
            space_type=SpaceType.ONE_ON_ONE,
            policy_template="couples"
        )

        invite_code = space.invite_code

        # Jamila creates account and joins
        jamila = manager.create_user("Jamila", "jamila@example.com")
        success = manager.join_space(space.space_id, jamila.user_id, invite_code)

        assert success is True
        assert len(space.members) == 2

        # Check both can see the space
        andrew_spaces = manager.list_user_spaces(andrew.user_id)
        jamila_spaces = manager.list_user_spaces(jamila.user_id)

        assert len(andrew_spaces) == 1
        assert len(jamila_spaces) == 1
        assert andrew_spaces[0].space_id == jamila_spaces[0].space_id

        # Check policy is appropriate
        assert "emotional_state" in space.policy.inclusion_criteria
        assert "work_details" in space.policy.exclusion_criteria

    def test_hacker_house_scenario(self, manager):
        """Test hacker house group scenario."""
        # Create several users
        andrew = manager.create_user("Andrew")
        novel = manager.create_user("Novel")
        alexis = manager.create_user("Alexis")
        ron = manager.create_user("Ron")

        # Andrew creates pirate ship space
        pirate_ship = manager.create_space(
            creator_user_id=andrew.user_id,
            name="Pirate Ship",
            space_type=SpaceType.GROUP,
            description="NYC hacker house Jan 2025",
            policy_template="team"
        )

        # Everyone joins
        for user in [novel, alexis, ron]:
            manager.join_space(
                pirate_ship.space_id,
                user.user_id,
                pirate_ship.invite_code
            )

        assert len(pirate_ship.members) == 4

        # All users should have the space
        for user in [andrew, novel, alexis, ron]:
            spaces = manager.list_user_spaces(user.user_id)
            assert len(spaces) == 1
            assert spaces[0].name == "Pirate Ship"

    def test_multiple_spaces_per_user(self, manager):
        """Test user being in multiple spaces."""
        andrew = manager.create_user("Andrew")
        jamila = manager.create_user("Jamila")
        novel = manager.create_user("Novel")

        # Andrew creates relationship space with Jamila
        couples_space = manager.create_space(
            creator_user_id=andrew.user_id,
            name="Andrew & Jamila",
            space_type=SpaceType.ONE_ON_ONE,
            policy_template="couples"
        )
        manager.join_space(couples_space.space_id, jamila.user_id, couples_space.invite_code)

        # Andrew creates hacker space with Novel
        hacker_space = manager.create_space(
            creator_user_id=andrew.user_id,
            name="Tech Discussions",
            space_type=SpaceType.GROUP,
            policy_template="team"
        )
        manager.join_space(hacker_space.space_id, novel.user_id, hacker_space.invite_code)

        # Andrew creates public feed
        public_space = manager.create_space(
            creator_user_id=andrew.user_id,
            name="Public Insights",
            space_type=SpaceType.PUBLIC,
            policy_template="public"
        )

        # Andrew should be in 3 spaces
        andrew_spaces = manager.list_user_spaces(andrew.user_id)
        assert len(andrew_spaces) == 3

        # Jamila should only be in 1
        jamila_spaces = manager.list_user_spaces(jamila.user_id)
        assert len(jamila_spaces) == 1

        # Novel should only be in 1
        novel_spaces = manager.list_user_spaces(novel.user_id)
        assert len(novel_spaces) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
