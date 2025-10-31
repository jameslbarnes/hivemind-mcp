"""
Space Manager - handles space CRUD operations.
Uses Firestore for persistent storage when available, falls back to in-memory.
"""

from typing import List, Optional, Dict
from datetime import datetime
import uuid
from src.models import (
    Space, SpaceType, SpaceMember, User, Policy, OAuthCredentials,
    ConversationHistory, RoutingMetadata, ConversationSummaryEntry, ConversationThread,
    create_couples_policy, create_public_feed_policy, create_team_policy,
    TransformationRules
)
from src.privacy_templates import get_template


class SpaceManager:
    """Manages spaces with optional Firestore backend."""

    def __init__(self, use_firestore: bool = True, credentials_path: Optional[str] = None):
        """
        Initialize SpaceManager.

        Args:
            use_firestore: If True, use Firestore backend. If False, use in-memory.
            credentials_path: Path to Firebase credentials (optional).
        """
        self.use_firestore = use_firestore
        self.backend = None

        # Try to initialize Firestore
        if use_firestore:
            try:
                from src.firestore_backend import FirestoreBackend
                self.backend = FirestoreBackend(credentials_path)
                print("Firestore backend initialized successfully")
            except Exception as e:
                print(f"Firestore initialization failed: {e}")
                print("Falling back to in-memory storage")
                self.use_firestore = False

        # In-memory storage (fallback or when Firestore disabled)
        if not self.use_firestore:
            self.spaces: Dict[str, Space] = {}
            self.users: Dict[str, User] = {}
            self.invite_codes: Dict[str, str] = {}  # invite_code -> space_id
            self.conversation_history: Dict[str, List[ConversationHistory]] = {}  # user_id -> [history]
            self.active_tokens: Dict[str, Dict] = {}  # token -> {user_id, expires_at}
            self.conversation_entries: Dict[str, ConversationSummaryEntry] = {}  # entry_id -> entry
            self.conversation_threads: Dict[str, ConversationThread] = {}  # thread_id -> thread
            self.user_entries: Dict[str, List[str]] = {}  # user_id -> [entry_ids]
            self.user_threads: Dict[str, List[str]] = {}  # user_id -> [thread_ids]

    def create_user(self, display_name: str, contact_method: Optional[str] = None) -> User:
        """Create a new user."""
        user = User(display_name=display_name, contact_method=contact_method)

        if self.use_firestore:
            self.backend.save_user(user)
        else:
            self.users[user.user_id] = user

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        if self.use_firestore:
            return self.backend.get_user(user_id)
        else:
            return self.users.get(user_id)

    def get_all_users(self) -> List[User]:
        """Get all users."""
        if self.use_firestore:
            return self.backend.get_all_users()
        else:
            return list(self.users.values())

    def save_user(self, user: User) -> None:
        """Save or update a user."""
        if self.use_firestore:
            self.backend.save_user(user)
        else:
            self.users[user.user_id] = user

    def generate_oauth_credentials(self, user_id: str) -> Optional[OAuthCredentials]:
        """Generate OAuth credentials for a user's MCP connector access."""
        user = self.get_user(user_id)
        if not user:
            return None

        # Generate new credentials
        credentials = OAuthCredentials()
        user.oauth_credentials = credentials

        # Save updated user
        self.save_user(user)

        return credentials

    def get_user_by_client_id(self, client_id: str) -> Optional[User]:
        """Find user by OAuth client ID."""
        if self.use_firestore:
            return self.backend.get_user_by_client_id(client_id)
        else:
            for user in self.users.values():
                if user.oauth_credentials and user.oauth_credentials.client_id == client_id:
                    return user
            return None

    def validate_oauth_credentials(self, client_id: str, client_secret: str) -> Optional[User]:
        """Validate OAuth credentials and return the associated user."""
        user = self.get_user_by_client_id(client_id)
        if not user or not user.oauth_credentials:
            return None

        if user.oauth_credentials.client_secret == client_secret:
            # Update last_used timestamp
            user.oauth_credentials.last_used = datetime.now()
            self.save_user(user)

            return user

        return None

    def create_space(
        self,
        creator_user_id: str,
        name: str,
        space_type: SpaceType,
        description: Optional[str] = None,
        policy_template: Optional[str] = None
    ) -> Space:
        """
        Create a new space.

        Args:
            creator_user_id: User creating the space
            name: Space name
            space_type: Type of space (1:1, group, public)
            description: Optional description
            policy_template: Optional privacy template ID (emotional_only, patterns_and_insights, etc.)

        Returns:
            Created Space object
        """
        # Generate unique space ID (works with both Firestore and in-memory)
        space_id = f"spc_{uuid.uuid4().hex[:12]}"

        # Get privacy template (defaults to custom if not found)
        template = get_template(policy_template) if policy_template else get_template("custom")

        # Create policy from template
        policy = Policy(
            space_id=space_id,
            relevance_prompt="Evaluate if this conversation is relevant to the space's policy.",
            inclusion_criteria=template["inclusion_criteria"],
            exclusion_criteria=template["exclusion_criteria"],
            transformation_rules=TransformationRules(
                custom_prompt=template["prompt"],
                remove_names=True,
                remove_locations=True,
                remove_organizations=True,
                preserve_emotional_tone=True,
                generalize_situations=True,
                detail_level="medium"
            )
        )

        # Create space
        space = Space(
            space_id=space_id,
            space_type=space_type,
            name=name,
            description=description,
            policy=policy,
            created_by=creator_user_id
        )

        # Add creator as owner
        creator_member = SpaceMember(
            user_id=creator_user_id,
            role="owner"
        )
        space.members.append(creator_member)

        # Set appropriate settings based on space type
        if space_type == SpaceType.ONE_ON_ONE:
            space.settings.max_members = 2
            space.settings.visibility = "private"
        elif space_type == SpaceType.PUBLIC:
            space.settings.visibility = "public"
            space.settings.allow_member_invites = True
            space.settings.require_approval = False

        # Store space
        if self.use_firestore:
            self.backend.save_space(space)
        else:
            self.spaces[space.space_id] = space
            self.invite_codes[space.invite_code] = space.space_id

        # Add to user's spaces
        user = self.get_user(creator_user_id)
        if user:
            user.spaces.append(space.space_id)
            self.save_user(user)

        return space

    def get_space(self, space_id: str) -> Optional[Space]:
        """Get space by ID."""
        if self.use_firestore:
            return self.backend.get_space(space_id)
        else:
            return self.spaces.get(space_id)

    def get_space_by_invite_code(self, invite_code: str) -> Optional[Space]:
        """Get space by invite code."""
        if self.use_firestore:
            return self.backend.get_space_by_invite_code(invite_code)
        else:
            space_id = self.invite_codes.get(invite_code)
            if space_id:
                return self.get_space(space_id)
            return None

    def join_space(
        self,
        space_id: str,
        user_id: str,
        invite_code: Optional[str] = None
    ) -> bool:
        """
        Join a space.

        Args:
            space_id: Space to join
            user_id: User joining
            invite_code: Optional invite code for verification

        Returns:
            True if joined successfully
        """
        space = self.get_space(space_id)
        if not space:
            return False

        # Verify invite code if required
        if invite_code and space.invite_code != invite_code:
            return False

        # Check if already a member
        if space.is_member(user_id):
            return False

        # Check max members
        if space.settings.max_members and len(space.members) >= space.settings.max_members:
            return False

        # Add member
        member = SpaceMember(user_id=user_id, role="member")
        space.members.append(member)

        # Save updated space
        if self.use_firestore:
            self.backend.save_space(space)
        else:
            self.spaces[space_id] = space

        # Add to user's spaces
        user = self.get_user(user_id)
        if user:
            user.spaces.append(space_id)
            self.save_user(user)

        return True

    def list_user_spaces(self, user_id: str) -> List[Space]:
        """Get all spaces a user is a member of."""
        if self.use_firestore:
            return self.backend.get_user_spaces(user_id)
        else:
            return [
                space for space in self.spaces.values()
                if space.is_member(user_id)
            ]

    def leave_space(self, space_id: str, user_id: str) -> bool:
        """
        Leave a space.

        Args:
            space_id: Space to leave
            user_id: User leaving

        Returns:
            True if left successfully
        """
        space = self.get_space(space_id)
        if not space:
            return False

        # Find and remove member
        space.members = [m for m in space.members if m.user_id != user_id]

        # Remove from user's spaces
        user = self.get_user(user_id)
        if user:
            user.spaces = [s for s in user.spaces if s != space_id]

        # If space is empty and not public, delete it
        if len(space.members) == 0 and space.space_type != SpaceType.PUBLIC:
            del self.spaces[space_id]
            del self.invite_codes[space.invite_code]

        return True

    def get_space_members(self, space_id: str) -> List[User]:
        """Get all members of a space as User objects."""
        space = self.get_space(space_id)
        if not space:
            return []

        members = []
        for member in space.members:
            user = self.get_user(member.user_id)
            if user:
                members.append(user)
        return members

    def update_policy(self, space_id: str, policy: Policy) -> bool:
        """Update a space's policy."""
        space = self.get_space(space_id)
        if not space:
            return False

        policy.space_id = space_id
        policy.updated_at = datetime.now()
        policy.version += 1
        space.policy = policy
        return True

    def add_conversation_history(self, history: ConversationHistory) -> None:
        """Add a conversation to user's history."""
        if self.use_firestore:
            self.backend.save_conversation(history)
        else:
            if history.user_id not in self.conversation_history:
                self.conversation_history[history.user_id] = []
            self.conversation_history[history.user_id].append(history)

    def get_conversation_history(self, user_id: str, limit: int = 50) -> List[ConversationHistory]:
        """Get conversation history for a user."""
        if self.use_firestore:
            return self.backend.get_user_conversations(user_id, limit)
        else:
            history = self.conversation_history.get(user_id, [])
            # Return most recent first
            return sorted(history, key=lambda h: h.timestamp, reverse=True)[:limit]

    def save_token(self, access_token: str, user_id: str, expires_at: datetime) -> None:
        """Save an OAuth access token."""
        if self.use_firestore:
            self.backend.save_token(access_token, user_id, expires_at)
        else:
            self.active_tokens[access_token] = {
                'user_id': user_id,
                'expires_at': expires_at,
                'created_at': datetime.now()
            }

    def get_user_from_token(self, access_token: str) -> Optional[str]:
        """
        Get user_id from an access token.
        Returns None if token is invalid or expired.
        """
        if self.use_firestore:
            return self.backend.get_user_from_token(access_token)
        else:
            token_data = self.active_tokens.get(access_token)
            if not token_data:
                return None

            # Check if token is expired
            expires_at = token_data.get('expires_at')
            if expires_at and expires_at < datetime.now():
                # Token expired, delete it
                self.delete_token(access_token)
                return None

            return token_data.get('user_id')

    def delete_token(self, access_token: str) -> None:
        """Delete an access token."""
        if self.use_firestore:
            self.backend.delete_token(access_token)
        else:
            if access_token in self.active_tokens:
                del self.active_tokens[access_token]

    def cleanup_expired_tokens(self) -> int:
        """Remove all expired tokens. Returns number of tokens deleted."""
        if self.use_firestore:
            return self.backend.cleanup_expired_tokens()
        else:
            now = datetime.now()
            expired = [
                token for token, data in self.active_tokens.items()
                if data.get('expires_at') and data['expires_at'] < now
            ]
            for token in expired:
                del self.active_tokens[token]
            return len(expired)

    def save_conversation_entry(self, entry: ConversationSummaryEntry, user_id: str) -> None:
        """Save a conversation summary entry."""
        if self.use_firestore:
            self.backend.save_conversation_entry(entry, user_id)
        else:
            self.conversation_entries[entry.entry_id] = entry
            if user_id not in self.user_entries:
                self.user_entries[user_id] = []
            self.user_entries[user_id].append(entry.entry_id)

    def get_conversation_entry(self, entry_id: str) -> Optional[ConversationSummaryEntry]:
        """Get a conversation entry by ID."""
        if self.use_firestore:
            return self.backend.get_conversation_entry(entry_id)
        else:
            return self.conversation_entries.get(entry_id)

    def get_user_entries(self, user_id: str, limit: int = 50) -> List[ConversationSummaryEntry]:
        """Get conversation entries for a user."""
        if self.use_firestore:
            return self.backend.get_user_entries(user_id, limit)
        else:
            entry_ids = self.user_entries.get(user_id, [])
            entries = [self.conversation_entries[eid] for eid in entry_ids if eid in self.conversation_entries]
            # Return most recent first
            return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def save_thread(self, thread: ConversationThread) -> None:
        """Save a conversation thread."""
        if self.use_firestore:
            self.backend.save_thread(thread)
        else:
            self.conversation_threads[thread.thread_id] = thread
            if thread.user_id not in self.user_threads:
                self.user_threads[thread.user_id] = []
            if thread.thread_id not in self.user_threads[thread.user_id]:
                self.user_threads[thread.user_id].append(thread.thread_id)

    def get_thread(self, thread_id: str) -> Optional[ConversationThread]:
        """Get a conversation thread by ID."""
        if self.use_firestore:
            return self.backend.get_thread(thread_id)
        else:
            return self.conversation_threads.get(thread_id)

    def get_user_threads(self, user_id: str, active_only: bool = True) -> List[ConversationThread]:
        """Get conversation threads for a user."""
        if self.use_firestore:
            return self.backend.get_user_threads(user_id, active_only)
        else:
            thread_ids = self.user_threads.get(user_id, [])
            threads = [self.conversation_threads[tid] for tid in thread_ids if tid in self.conversation_threads]
            if active_only:
                threads = [t for t in threads if t.is_active]
            # Return most recent first
            return sorted(threads, key=lambda t: t.last_updated, reverse=True)
