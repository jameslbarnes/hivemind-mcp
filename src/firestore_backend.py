"""
Firestore Backend for Hivemind - Persistent storage layer.

This module provides a Firestore-backed implementation of the storage layer,
allowing data to persist across server restarts and be shared between
the web app and MCP server.
"""

import os
from typing import Optional, List, Dict
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from src.models import (
    User, Space, ConversationHistory, RoutingMetadata,
    SpaceType, Policy, OAuthCredentials,
    ConversationSummaryEntry, ConversationThread
)


class FirestoreBackend:
    """Firestore backend for persistent storage."""

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Firestore backend.

        Args:
            credentials_path: Path to Firebase credentials JSON file OR JSON string content.
                            If None, uses GOOGLE_APPLICATION_CREDENTIALS env var.
        """
        import json

        # Initialize Firebase Admin (only if not already initialized)
        if not firebase_admin._apps:
            if credentials_path:
                # Check if it's a JSON string (starts with '{') or a file path
                if credentials_path.strip().startswith('{'):
                    # It's JSON content - parse it
                    try:
                        # Try parsing with strict=False to handle control characters
                        cred_dict = json.loads(credentials_path, strict=False)
                    except json.JSONDecodeError as e:
                        # If that fails, try escaping common issues
                        try:
                            # Replace literal newlines with escaped ones
                            cleaned = credentials_path.replace('\n', '\\n').replace('\r', '')
                            cred_dict = json.loads(cleaned, strict=False)
                        except json.JSONDecodeError as e2:
                            raise ValueError(f"Failed to parse credentials JSON: {e}. Make sure the JSON is properly formatted. Error at position {e.pos}: {credentials_path[max(0,e.pos-20):e.pos+20]}")

                    # Fix private_key: Firebase needs properly formatted PEM
                    if 'private_key' in cred_dict:
                        pk = cred_dict['private_key']

                        # Railway may have word-wrapped the JSON, adding spaces/newlines in wrong places
                        # Fix common PEM formatting issues:
                        # 1. Remove any spaces between lines that broke up BEGIN/END markers
                        # 2. Ensure proper PEM format with correct newlines

                        # First, fix broken BEGIN/END markers by removing extra spaces and newlines
                        pk = pk.replace('-----BEGIN PRIVATE\n  KEY-----', '-----BEGIN PRIVATE KEY-----')
                        pk = pk.replace('-----END PRIVATE\n  KEY-----', '-----END PRIVATE KEY-----')
                        pk = pk.replace('-----BEGIN PRIVATE \nKEY-----', '-----BEGIN PRIVATE KEY-----')
                        pk = pk.replace('-----END PRIVATE \nKEY-----', '-----END PRIVATE KEY-----')

                        # Also handle if there are other spacing issues
                        import re
                        # Fix BEGIN marker with any whitespace issues
                        pk = re.sub(r'-----BEGIN\s+PRIVATE\s+KEY-----', '-----BEGIN PRIVATE KEY-----', pk)
                        pk = re.sub(r'-----END\s+PRIVATE\s+KEY-----', '-----END PRIVATE KEY-----', pk)

                        cred_dict['private_key'] = pk

                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                elif os.path.exists(credentials_path):
                    # It's a file path that exists
                    cred = credentials.Certificate(credentials_path)
                    firebase_admin.initialize_app(cred)
                else:
                    raise ValueError(f"credentials_path is neither valid JSON nor an existing file: {credentials_path[:100]}...")
            else:
                # Try to use environment variable
                cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    # Use default application credentials
                    firebase_admin.initialize_app()

        self.db = firestore.client()

        # Collection references
        self.users_col = self.db.collection('users')
        self.spaces_col = self.db.collection('spaces')
        self.conversations_col = self.db.collection('conversations')
        self.tokens_col = self.db.collection('tokens')
        self.entries_col = self.db.collection('conversation_entries')
        self.threads_col = self.db.collection('conversation_threads')

    # ============================================================================
    # User Operations
    # ============================================================================

    def save_user(self, user: User) -> None:
        """Save or update a user."""
        self.users_col.document(user.user_id).set(user.to_dict())

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        doc = self.users_col.document(user_id).get()
        if doc.exists:
            return User.from_dict(doc.to_dict())
        return None

    def get_user_by_client_id(self, client_id: str) -> Optional[User]:
        """Find user by OAuth client ID."""
        query = self.users_col.where(
            filter=FieldFilter('oauth_credentials.client_id', '==', client_id)
        ).limit(1)

        docs = query.get()
        for doc in docs:
            return User.from_dict(doc.to_dict())
        return None

    def get_all_users(self) -> List[User]:
        """Get all users."""
        users = []
        docs = self.users_col.stream()
        for doc in docs:
            users.append(User.from_dict(doc.to_dict()))
        return users

    # ============================================================================
    # Space Operations
    # ============================================================================

    def save_space(self, space: Space) -> None:
        """Save or update a space."""
        self.spaces_col.document(space.space_id).set(space.to_dict())

    def get_space(self, space_id: str) -> Optional[Space]:
        """Get space by ID."""
        doc = self.spaces_col.document(space_id).get()
        if doc.exists:
            data = doc.to_dict()
            # Load policy from nested data
            if 'policy' in data:
                data['policy'] = Policy.from_dict(data['policy'])
            return Space.from_dict(data)
        return None

    def get_space_by_invite_code(self, invite_code: str) -> Optional[Space]:
        """Get space by invite code."""
        query = self.spaces_col.where(
            filter=FieldFilter('invite_code', '==', invite_code)
        ).limit(1)

        docs = query.get()
        for doc in docs:
            data = doc.to_dict()
            if 'policy' in data:
                data['policy'] = Policy.from_dict(data['policy'])
            return Space.from_dict(data)
        return None

    def get_user_spaces(self, user_id: str) -> List[Space]:
        """Get all spaces where user is a member."""
        spaces = []

        # Query for spaces where user is in members array
        # Note: This is simplified - you might need to structure data differently
        # for efficient queries in production
        all_spaces = self.spaces_col.stream()

        for doc in all_spaces:
            data = doc.to_dict()
            if 'policy' in data:
                data['policy'] = Policy.from_dict(data['policy'])
            space = Space.from_dict(data)

            # Check if user is a member
            if any(m.user_id == user_id for m in space.members):
                spaces.append(space)

        return spaces

    def delete_space(self, space_id: str) -> None:
        """Delete a space."""
        self.spaces_col.document(space_id).delete()

    # ============================================================================
    # Conversation History Operations
    # ============================================================================

    def save_conversation(self, conversation: ConversationHistory) -> None:
        """Save a conversation history entry."""
        self.conversations_col.document(conversation.history_id).set(
            conversation.to_dict()
        )

    def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[ConversationHistory]:
        """Get conversation history for a user."""
        query = self.conversations_col.where(
            filter=FieldFilter('user_id', '==', user_id)
        ).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)

        conversations = []
        docs = query.get()
        for doc in docs:
            data = doc.to_dict()
            # Parse routing results
            if 'routing_results' in data:
                data['routing_results'] = [
                    RoutingMetadata(**r) for r in data['routing_results']
                ]
            conversations.append(ConversationHistory.from_dict(data))

        return conversations

    def get_conversation(self, history_id: str) -> Optional[ConversationHistory]:
        """Get a specific conversation by ID."""
        doc = self.conversations_col.document(history_id).get()
        if doc.exists:
            data = doc.to_dict()
            if 'routing_results' in data:
                data['routing_results'] = [
                    RoutingMetadata(**r) for r in data['routing_results']
                ]
            return ConversationHistory.from_dict(data)
        return None

    # ============================================================================
    # Token Operations
    # ============================================================================

    def save_token(self, access_token: str, user_id: str, expires_at: datetime) -> None:
        """
        Save an OAuth access token.

        Args:
            access_token: The token string
            user_id: Associated user ID
            expires_at: Expiration timestamp
        """
        self.tokens_col.document(access_token).set({
            'user_id': user_id,
            'expires_at': expires_at,
            'created_at': datetime.now()
        })

    def get_user_from_token(self, access_token: str) -> Optional[str]:
        """
        Get user_id from an access token.

        Args:
            access_token: The token to look up

        Returns:
            user_id if token is valid and not expired, None otherwise
        """
        doc = self.tokens_col.document(access_token).get()
        if not doc.exists:
            return None

        data = doc.to_dict()

        # Check if token is expired
        expires_at = data.get('expires_at')
        if expires_at:
            # Convert to naive datetime if timezone-aware
            if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            if expires_at < datetime.now():
                # Token expired, delete it
                self.delete_token(access_token)
                return None

        return data.get('user_id')

    def delete_token(self, access_token: str) -> None:
        """Delete an access token."""
        self.tokens_col.document(access_token).delete()

    def cleanup_expired_tokens(self) -> int:
        """
        Remove all expired tokens from storage.

        Returns:
            Number of tokens deleted
        """
        now = datetime.now()
        deleted = 0

        # Iterate through all tokens and check expiration in Python
        for doc in self.tokens_col.stream():
            data = doc.to_dict()
            expires_at = data.get('expires_at')
            if expires_at:
                # Convert to naive datetime if timezone-aware
                if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
                    expires_at = expires_at.replace(tzinfo=None)
                if expires_at < now:
                    doc.reference.delete()
                    deleted += 1

        return deleted

    # ============================================================================
    # Conversation Entry Operations
    # ============================================================================

    def save_conversation_entry(self, entry: ConversationSummaryEntry, user_id: str) -> None:
        """Save a conversation summary entry."""
        self.entries_col.document(entry.entry_id).set(entry.to_dict())

    def get_conversation_entry(self, entry_id: str) -> Optional[ConversationSummaryEntry]:
        """Get a conversation entry by ID."""
        doc = self.entries_col.document(entry_id).get()
        if doc.exists:
            return ConversationSummaryEntry.from_dict(doc.to_dict())
        return None

    def get_user_entries(self, user_id: str, limit: int = 50) -> List[ConversationSummaryEntry]:
        """Get conversation entries for a user."""
        # This requires a user_id field on entries - we'll need to add this
        query = self.entries_col.where(
            filter=FieldFilter('user_id', '==', user_id)
        ).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)

        entries = []
        docs = query.get()
        for doc in docs:
            entries.append(ConversationSummaryEntry.from_dict(doc.to_dict()))

        return entries

    # ============================================================================
    # Conversation Thread Operations
    # ============================================================================

    def save_thread(self, thread: ConversationThread) -> None:
        """Save a conversation thread."""
        self.threads_col.document(thread.thread_id).set(thread.to_dict())

    def get_thread(self, thread_id: str) -> Optional[ConversationThread]:
        """Get a conversation thread by ID."""
        doc = self.threads_col.document(thread_id).get()
        if doc.exists:
            return ConversationThread.from_dict(doc.to_dict())
        return None

    def get_user_threads(self, user_id: str, active_only: bool = True) -> List[ConversationThread]:
        """Get conversation threads for a user."""
        query = self.threads_col.where(
            filter=FieldFilter('user_id', '==', user_id)
        )

        if active_only:
            query = query.where(filter=FieldFilter('is_active', '==', True))

        query = query.order_by('last_updated', direction=firestore.Query.DESCENDING)

        threads = []
        docs = query.get()
        for doc in docs:
            threads.append(ConversationThread.from_dict(doc.to_dict()))

        return threads
