"""
Data models for multi-space hivemind system.
"""

from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class ContactPreference(str, Enum):
    """How open user is to being contacted."""
    JUST_SHARING = "just_sharing"
    OPEN_TO_QUESTIONS = "open_to_questions"
    HAPPY_TO_HELP = "happy_to_help"


class AttributionLevel(str, Enum):
    """Level of attribution for shared content."""
    FULL = "full"  # Name + contact info
    PSEUDONYM = "pseudonym"  # Consistent ID, no contact
    ANONYMOUS = "anonymous"  # No attribution


class SpaceType(str, Enum):
    """Type of space."""
    ONE_ON_ONE = "1:1"
    GROUP = "group"
    PUBLIC = "public"


class ConsentConfig(BaseModel):
    """User consent configuration."""
    enabled: bool = False
    contact_preference: ContactPreference = ContactPreference.JUST_SHARING
    default_attribution: AttributionLevel = AttributionLevel.FULL
    setup_complete: bool = False


class OAuthCredentials(BaseModel):
    """OAuth credentials for MCP connector access."""
    client_id: str = Field(default_factory=lambda: f"scribe_{uuid.uuid4().hex}")
    client_secret: str = Field(default_factory=lambda: uuid.uuid4().hex + uuid.uuid4().hex)
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None


class User(BaseModel):
    """User profile."""
    user_id: str = Field(default_factory=lambda: f"usr_{uuid.uuid4().hex[:8]}")
    display_name: str
    contact_method: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    consent_config: ConsentConfig = Field(default_factory=ConsentConfig)
    spaces: List[str] = Field(default_factory=list)  # space_ids
    oauth_credentials: Optional[OAuthCredentials] = None  # For MCP connector access

    def to_dict(self) -> dict:
        """Convert to dict for Firestore."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        if self.oauth_credentials and self.oauth_credentials.created_at:
            data['oauth_credentials']['created_at'] = self.oauth_credentials.created_at.isoformat()
        if self.oauth_credentials and self.oauth_credentials.last_used:
            data['oauth_credentials']['last_used'] = self.oauth_credentials.last_used.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Load from Firestore dict."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('oauth_credentials'):
            if isinstance(data['oauth_credentials'].get('created_at'), str):
                data['oauth_credentials']['created_at'] = datetime.fromisoformat(data['oauth_credentials']['created_at'])
            if data['oauth_credentials'].get('last_used') and isinstance(data['oauth_credentials']['last_used'], str):
                data['oauth_credentials']['last_used'] = datetime.fromisoformat(data['oauth_credentials']['last_used'])
        return cls(**data)


class TransformationRules(BaseModel):
    """Rules for transforming content."""
    remove_names: bool = True
    remove_locations: bool = True
    remove_organizations: bool = True
    remove_financial_details: bool = True
    generalize_situations: bool = True
    preserve_emotional_tone: bool = True
    detail_level: Literal["high", "medium", "low"] = "medium"
    custom_prompt: Optional[str] = None


class Policy(BaseModel):
    """Policy for a space defining what/how to share."""
    policy_id: str = Field(default_factory=lambda: f"pol_{uuid.uuid4().hex[:8]}")
    space_id: str
    version: int = 1

    # Write rules (what gets shared)
    relevance_prompt: str
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)

    # Transformation rules
    transformation_rules: TransformationRules = Field(default_factory=TransformationRules)
    attribution_level: AttributionLevel = AttributionLevel.FULL

    # Read rules (when to inject context)
    trigger_keywords: List[str] = Field(default_factory=list)
    trigger_entities: List[str] = Field(default_factory=list)
    context_window: int = 10

    # Approval rules
    auto_approve_threshold: float = 0.7
    require_approval_if: List[str] = Field(default_factory=list)
    high_sensitivity_topics: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dict for Firestore."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Policy':
        """Load from Firestore dict."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class SpaceMember(BaseModel):
    """Member of a space."""
    user_id: str
    joined_at: datetime = Field(default_factory=datetime.now)
    role: Literal["owner", "admin", "member"] = "member"
    custom_policy_overrides: Optional[Dict[str, Any]] = None


class SpaceSettings(BaseModel):
    """Settings for a space."""
    visibility: Literal["private", "unlisted", "public"] = "private"
    allow_member_invites: bool = False
    require_approval: bool = True
    max_members: Optional[int] = None


class Space(BaseModel):
    """A space for sharing content with specific people/groups."""
    space_id: str = Field(default_factory=lambda: f"spc_{uuid.uuid4().hex[:8]}")
    space_type: SpaceType
    name: str
    description: Optional[str] = None
    members: List[SpaceMember] = Field(default_factory=list)
    policy: Policy
    created_by: str  # user_id
    created_at: datetime = Field(default_factory=datetime.now)
    invite_code: str = Field(default_factory=lambda: f"{uuid.uuid4().hex[:8].upper()}")
    settings: SpaceSettings = Field(default_factory=SpaceSettings)

    def to_dict(self) -> dict:
        """Convert to dict for Firestore."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        for member in data['members']:
            member['joined_at'] = member['joined_at'].isoformat() if isinstance(member['joined_at'], datetime) else member['joined_at']
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Space':
        """Load from Firestore dict."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        for member in data.get('members', []):
            if isinstance(member.get('joined_at'), str):
                member['joined_at'] = datetime.fromisoformat(member['joined_at'])
        return cls(**data)

    def is_member(self, user_id: str) -> bool:
        """Check if user is a member."""
        return any(m.user_id == user_id for m in self.members)

    def get_member(self, user_id: str) -> Optional[SpaceMember]:
        """Get member by user_id."""
        for m in self.members:
            if m.user_id == user_id:
                return m
        return None


class RawConversationTurn(BaseModel):
    """Raw conversation turn (stored locally only)."""
    turn_id: str = Field(default_factory=lambda: f"turn_{uuid.uuid4().hex[:8]}")
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    user_message: str
    assistant_message: str
    conversation_id: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict for JSONL storage."""
        data = self.model_dump()
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'RawConversationTurn':
        """Load from JSONL dict."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class FilteredDocument(BaseModel):
    """Filtered/transformed content shared to a space."""
    doc_id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:8]}")
    space_id: str
    source_turn_id: str
    author_user_id: str
    content: str
    original_topics: List[str] = Field(default_factory=list)
    filtered_topics: List[str] = Field(default_factory=list)
    attribution_level: AttributionLevel
    display_name: Optional[str] = None
    contact_method: Optional[str] = None
    contact_preference: Optional[ContactPreference] = None
    confidence_score: float = 0.0
    sensitivity_score: float = 0.0
    approved: bool = True
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dict for Firestore."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'FilteredDocument':
        """Load from Firestore dict."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class PendingApproval(BaseModel):
    """Content awaiting user approval before sharing."""
    approval_id: str = Field(default_factory=lambda: f"appr_{uuid.uuid4().hex[:8]}")
    user_id: str
    space_id: str
    source_turn_id: str
    proposed_content: str
    reason_for_approval: str
    confidence_score: float
    sensitivity_score: float
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime

    def to_dict(self) -> dict:
        """Convert to dict for Firestore."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'PendingApproval':
        """Load from Firestore dict."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('expires_at'), str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)


class RoutingMetadata(BaseModel):
    """Metadata about how a conversation was routed."""
    space_id: str
    space_name: str
    action: str  # "shared", "skipped", "approval_needed"
    reason: str
    confidence_score: Optional[float] = None
    sensitivity_score: Optional[float] = None
    filtered_content: Optional[str] = None
    original_content: Optional[str] = None


class ConversationHistory(BaseModel):
    """Conversation turn with routing metadata for dashboard display."""
    history_id: str = Field(default_factory=lambda: f"hist_{uuid.uuid4().hex[:8]}")
    user_id: str
    turn_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    user_message: str
    assistant_message: str
    routing_results: List[RoutingMetadata] = Field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        data = self.model_dump()
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ConversationHistory':
        """Load from dict."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class ConversationSummaryEntry(BaseModel):
    """Summary of a single conversation exchange."""
    entry_id: str = Field(default_factory=lambda: f"entry_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.now)
    summary: str  # Concise 1-2 sentence summary of the exchange
    key_points: List[str] = Field(default_factory=list)  # Important takeaways
    user_intent: Optional[str] = None  # What the user was trying to accomplish
    assistant_action: Optional[str] = None  # How the assistant helped
    topics: List[str] = Field(default_factory=list)  # Topics discussed
    emotional_tone: Optional[str] = None  # Overall emotional context
    related_entry_ids: List[str] = Field(default_factory=list)  # Links to related entries

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        data = self.model_dump()
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ConversationSummaryEntry':
        """Load from dict."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class ConversationThread(BaseModel):
    """A thread of related conversations with hierarchical summaries."""
    thread_id: str = Field(default_factory=lambda: f"thread_{uuid.uuid4().hex[:8]}")
    user_id: str
    title: str  # Auto-generated topic/theme
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    thread_summary: str  # High-level summary of the entire thread
    entry_ids: List[str] = Field(default_factory=list)  # IDs of entries in this thread
    tags: List[str] = Field(default_factory=list)  # Topics, entities, themes
    is_active: bool = True  # Whether this thread is currently ongoing
    related_thread_ids: List[str] = Field(default_factory=list)  # Links to related threads

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        data['last_updated'] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ConversationThread':
        """Load from dict."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('last_updated'), str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


# Policy Templates

def create_couples_policy(space_id: str) -> Policy:
    """Create policy template for 1:1 relationship spaces."""
    return Policy(
        space_id=space_id,
        relevance_prompt=(
            "Is this content relevant to my relationship with my partner? "
            "Does it involve emotional state, shared plans, or relationship dynamics?"
        ),
        inclusion_criteria=[
            "emotional_state",
            "relationship_topic",
            "shared_planning",
            "support_needed"
        ],
        exclusion_criteria=[
            "work_details",
            "third_party_conversations",
            "financial_specifics",
            "health_diagnoses"
        ],
        transformation_rules=TransformationRules(
            remove_names=True,
            remove_organizations=True,
            generalize_situations=True,
            preserve_emotional_tone=True,
            detail_level="medium",
            custom_prompt="Preserve emotional context but generalize specific situations."
        ),
        trigger_keywords=["partner", "wife", "husband", "relationship", "weekend", "plans together"],
        auto_approve_threshold=0.7,
        require_approval_if=["sensitivity > 0.6", "mentions_conflict"],
        high_sensitivity_topics=["infidelity", "separation", "major_conflict"]
    )


def create_public_feed_policy(space_id: str) -> Policy:
    """Create policy template for public feed spaces."""
    return Policy(
        space_id=space_id,
        relevance_prompt=(
            "Is this a generalizable insight that could help others? "
            "Technical learning, career wisdom, life lessons, creative breakthroughs?"
        ),
        inclusion_criteria=[
            "technical_insight",
            "career_advice",
            "learning_discovery",
            "creative_breakthrough",
            "useful_pattern"
        ],
        exclusion_criteria=[
            "personal_details",
            "names",
            "companies",
            "locations",
            "financial_info",
            "health_info",
            "relationship_details"
        ],
        transformation_rules=TransformationRules(
            remove_names=True,
            remove_locations=True,
            remove_organizations=True,
            generalize_situations=True,
            preserve_emotional_tone=False,
            detail_level="low",
            custom_prompt="Extract the general principle or insight. Remove all personal context."
        ),
        trigger_keywords=["team", "group", "learning", "exploring"],
        auto_approve_threshold=0.8,
        require_approval_if=["sensitivity > 0.4"]
    )


def create_team_policy(space_id: str) -> Policy:
    """Create policy template for team/group spaces."""
    return Policy(
        space_id=space_id,
        relevance_prompt=(
            "Is this relevant to team coordination or collaboration? "
            "What's being worked on, blockers, opportunities to help?"
        ),
        inclusion_criteria=[
            "work_progress",
            "blockers",
            "help_needed",
            "collaboration_opportunity",
            "learning"
        ],
        exclusion_criteria=[
            "proprietary_details",
            "personal_relationships",
            "health_info",
            "financial_details"
        ],
        transformation_rules=TransformationRules(
            remove_names=False,  # Keep team member names
            remove_organizations=False,  # Keep company context
            generalize_situations=False,
            preserve_emotional_tone=True,
            detail_level="high",
            custom_prompt="Keep technical details, remove sensitive business info."
        ),
        trigger_keywords=["team", "project", "help", "blocker"],
        auto_approve_threshold=0.6,
        require_approval_if=["sensitivity > 0.5", "mentions_proprietary"]
    )
