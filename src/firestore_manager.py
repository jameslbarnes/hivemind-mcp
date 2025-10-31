"""
Firestore-backed SpaceManager for production use.
Both web app and MCP server will use this.
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from src.models import (
    User, Space, Policy, SpaceMember, RawConversationTurn,
    FilteredDocument, PendingApproval, SpaceType
)


class FirestoreSpaceManager:
    """SpaceManager with Firestore persistence."""

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Firestore client.

        Args:
            project_id: Google Cloud project ID. If None, uses FIRESTORE_PROJECT env var.
        """
        self.project_id = project_id or os.getenv("FIRESTORE_PROJECT")

        if not self.project_id:
            raise ValueError("FIRESTORE_PROJECT environment variable must be set")

        self.db = firestore.Client(project=self.project_id)

        # Collections
        self.users_col = self.db.collection("users")
        self.spaces_col = self.db.collection("spaces")
        self.documents_col = self.db.collection("filtered_documents")
        self.approvals_col = self.db.collection("pending_approvals")
        self.conversations_col = self.db.collection("raw_conversations")

    # ========================================================================
    # User Management
    # ========================================================================

    def create_user(self, display_name: str, contact_method: Optional[str] = None) -> User:
        """Create a new user."""
        user = User(display_name=display_name, contact_method=contact_method)

        # Save to Firestore
        self.users_col.document(user.user_id).set(user.to_dict())

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        doc = self.users_col.document(user_id).get()

        if not doc.exists:
            return None

        return User.from_dict(doc.to_dict())

    def update_user(self, user: User):
        """Update user in Firestore."""
        self.users_col.document(user.user_id).set(user.to_dict())

    # ========================================================================
    # Space Management
    # ========================================================================

    def create_space(
        self,
        creator_user_id: str,
        name: str,
        space_type: SpaceType,
        policy_template: Optional[str] = None
    ) -> Space:
        """Create a new space."""
        from src.models import create_couples_policy, create_team_policy, create_public_feed_policy

        # Create space
        space = Space(
            name=name,
            space_type=space_type,
            created_by=creator_user_id,
            members=[SpaceMember(user_id=creator_user_id, role="owner")]
        )

        # Set policy from template
        if policy_template == "couples":
            space.policy = create_couples_policy(space.space_id)
        elif policy_template == "team":
            space.policy = create_team_policy(space.space_id)
        elif policy_template == "public":
            space.policy = create_public_feed_policy(space.space_id)
        else:
            # Default policy
            space.policy = Policy(space_id=space.space_id, relevance_prompt="Is this relevant?")

        # Save to Firestore
        self.spaces_col.document(space.space_id).set(space.to_dict())

        # Update user's spaces list
        user = self.get_user(creator_user_id)
        if user:
            user.spaces.append(space.space_id)
            self.update_user(user)

        return space

    def get_space(self, space_id: str) -> Optional[Space]:
        """Get space by ID."""
        doc = self.spaces_col.document(space_id).get()

        if not doc.exists:
            return None

        return Space.from_dict(doc.to_dict())

    def list_user_spaces(self, user_id: str) -> List[Space]:
        """List all spaces a user is a member of."""
        # Query spaces where user is a member
        query = self.spaces_col.where(
            filter=FieldFilter("members", "array_contains", {"user_id": user_id})
        )

        spaces = []
        for doc in query.stream():
            space = Space.from_dict(doc.to_dict())
            spaces.append(space)

        return spaces

    def join_space(self, space_id: str, user_id: str, invite_code: str) -> bool:
        """Join a space with invite code."""
        space = self.get_space(space_id)
        if not space:
            return False

        # Verify invite code
        if space.invite_code != invite_code:
            return False

        # Check if already a member
        if any(m.user_id == user_id for m in space.members):
            return False

        # Check member limits
        if space.space_type == SpaceType.ONE_ON_ONE and len(space.members) >= 2:
            return False

        # Add member
        space.members.append(SpaceMember(user_id=user_id))

        # Update Firestore
        self.spaces_col.document(space_id).set(space.to_dict())

        # Update user's spaces list
        user = self.get_user(user_id)
        if user:
            user.spaces.append(space_id)
            self.update_user(user)

        return True

    def leave_space(self, space_id: str, user_id: str) -> bool:
        """Leave a space."""
        space = self.get_space(space_id)
        if not space:
            return False

        # Remove member
        space.members = [m for m in space.members if m.user_id != user_id]

        # Update Firestore
        self.spaces_col.document(space_id).set(space.to_dict())

        # Update user's spaces list
        user = self.get_user(user_id)
        if user:
            user.spaces = [s for s in user.spaces if s != space_id]
            self.update_user(user)

        return True

    def get_space_members(self, space_id: str) -> List[User]:
        """Get all members of a space."""
        space = self.get_space(space_id)
        if not space:
            return []

        members = []
        for member in space.members:
            user = self.get_user(member.user_id)
            if user:
                members.append(user)

        return members

    # ========================================================================
    # Conversation & Document Storage
    # ========================================================================

    def save_raw_conversation(self, turn: RawConversationTurn):
        """Save raw conversation turn."""
        self.conversations_col.document(turn.turn_id).set(turn.to_dict())

    def save_filtered_document(self, doc: FilteredDocument):
        """Save filtered document to a space."""
        self.documents_col.document(doc.document_id).set(doc.to_dict())

    def get_space_documents(
        self,
        space_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[FilteredDocument]:
        """Get filtered documents for a space."""
        query = (
            self.documents_col
            .where(filter=FieldFilter("space_id", "==", space_id))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .offset(offset)
        )

        docs = []
        for doc in query.stream():
            docs.append(FilteredDocument.from_dict(doc.to_dict()))

        return docs

    # ========================================================================
    # Approval Queue
    # ========================================================================

    def save_pending_approval(self, approval: PendingApproval):
        """Save pending approval."""
        self.approvals_col.document(approval.approval_id).set(approval.to_dict())

    def get_pending_approvals(self, user_id: str) -> List[PendingApproval]:
        """Get pending approvals for a user."""
        query = (
            self.approvals_col
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("status", "==", "pending"))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
        )

        approvals = []
        for doc in query.stream():
            approvals.append(PendingApproval.from_dict(doc.to_dict()))

        return approvals

    def update_approval_status(
        self,
        approval_id: str,
        status: str,
        edited_content: Optional[str] = None
    ) -> bool:
        """Update approval status (approved/rejected)."""
        doc_ref = self.approvals_col.document(approval_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        approval = PendingApproval.from_dict(doc.to_dict())
        approval.status = status

        if edited_content:
            approval.proposed_content = edited_content

        doc_ref.set(approval.to_dict())

        return True

    # ========================================================================
    # Search & Discovery
    # ========================================================================

    def search_public_documents(
        self,
        query: str,
        limit: int = 10
    ) -> List[FilteredDocument]:
        """Search public space documents."""
        # Get all public spaces
        public_spaces = []
        query_spaces = self.spaces_col.where(
            filter=FieldFilter("space_type", "==", "public")
        )

        for doc in query_spaces.stream():
            space = Space.from_dict(doc.to_dict())
            public_spaces.append(space.space_id)

        if not public_spaces:
            return []

        # Search documents in public spaces
        # Note: Full-text search requires external indexing (Algolia, Elasticsearch, etc.)
        # For now, we'll just return recent public documents
        results = []
        for space_id in public_spaces:
            docs = self.get_space_documents(space_id, limit=limit)
            results.extend(docs)

        # Sort by date and limit
        results.sort(key=lambda d: d.created_at, reverse=True)
        return results[:limit]
