"""
Policy Engine - Routes conversations through policies to appropriate spaces.

Phase 1: Simple rule-based routing with mock LLM.
Phase 2: Real Claude API integration.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from src.models import (
    RawConversationTurn, Space, FilteredDocument, PendingApproval,
    AttributionLevel, User
)
from src.space_manager import SpaceManager


class RouteResult:
    """Result of routing a conversation to a space."""

    def __init__(
        self,
        space_id: str,
        action: str,  # "shared", "skipped", "approval_needed"
        document: Optional[FilteredDocument] = None,
        approval: Optional[PendingApproval] = None,
        reason: Optional[str] = None
    ):
        self.space_id = space_id
        self.action = action
        self.document = document
        self.approval = approval
        self.reason = reason

    def __repr__(self):
        return f"RouteResult(space_id={self.space_id}, action={self.action})"


class PolicyEngine:
    """Routes conversations through space policies."""

    def __init__(self, space_manager: SpaceManager, llm_client=None):
        """
        Initialize policy engine.

        Args:
            space_manager: SpaceManager instance
            llm_client: Optional LLM client (for real Claude API). If None, uses mock.
        """
        self.manager = space_manager
        self.llm_client = llm_client
        self.use_mock = llm_client is None

    async def route_conversation(
        self,
        turn: RawConversationTurn,
        user_id: str
    ) -> List[RouteResult]:
        """
        Route a conversation turn to appropriate spaces.

        Args:
            turn: The conversation turn to route
            user_id: User who had the conversation

        Returns:
            List of RouteResult for each space
        """
        results = []

        # Get user's spaces
        spaces = self.manager.list_user_spaces(user_id)

        # Get user info for attribution
        user = self.manager.get_user(user_id)
        if not user:
            return []

        # Process each space
        for space in spaces:
            result = await self._process_space(turn, space, user)
            results.append(result)

        return results

    async def _process_space(
        self,
        turn: RawConversationTurn,
        space: Space,
        user: User
    ) -> RouteResult:
        """Process a conversation turn for a specific space."""

        policy = space.policy

        # Single-pass LLM evaluation (the prompt IS the contract)
        result = await self._evaluate_content_single_pass(turn, policy)

        if not result['is_relevant']:
            return RouteResult(
                space_id=space.space_id,
                action="skipped",
                reason=result['relevance_reason']
            )

        filtered_content = result['transformed_content']
        topics = result['topics']
        confidence = result['confidence_score']
        sensitivity = result['sensitivity_score']

        # Check if approval needed
        needs_approval, approval_reason = self._check_approval_needed(
            confidence, sensitivity, policy
        )

        if needs_approval:
            approval = PendingApproval(
                user_id=user.user_id,
                space_id=space.space_id,
                source_turn_id=turn.turn_id,
                proposed_content=filtered_content,
                reason_for_approval=approval_reason,
                confidence_score=confidence,
                sensitivity_score=sensitivity,
                expires_at=datetime.now() + timedelta(days=7)
            )

            return RouteResult(
                space_id=space.space_id,
                action="approval_needed",
                approval=approval,
                reason=approval_reason
            )

        # Step 4: Create filtered document
        doc = FilteredDocument(
            space_id=space.space_id,
            source_turn_id=turn.turn_id,
            author_user_id=user.user_id,
            content=filtered_content,
            original_topics=turn.topics,
            filtered_topics=topics,
            attribution_level=policy.attribution_level,
            display_name=user.display_name if policy.attribution_level == AttributionLevel.FULL else None,
            contact_method=user.contact_method if policy.attribution_level == AttributionLevel.FULL else None,
            contact_preference=user.consent_config.contact_preference if policy.attribution_level == AttributionLevel.FULL else None,
            confidence_score=confidence,
            sensitivity_score=sensitivity
        )

        return RouteResult(
            space_id=space.space_id,
            action="shared",
            document=doc,
            reason="Content filtered and approved"
        )

    async def _check_relevance(self, turn: RawConversationTurn, policy) -> tuple[bool, str]:
        """Check if conversation is relevant to this space's policy."""

        if self.use_mock:
            return self._mock_check_relevance(turn, policy)

        # TODO: Implement with real Claude API
        # Use policy.relevance_prompt with Claude
        raise NotImplementedError("Real Claude API not implemented yet")

    def _mock_check_relevance(self, turn: RawConversationTurn, policy) -> tuple[bool, str]:
        """Mock relevance check using simple keyword matching."""

        combined_text = f"{turn.user_message} {turn.assistant_message}".lower()

        # Keyword mappings for mock matching
        keyword_map = {
            "emotional_state": ["feeling", "feel", "emotion", "stress", "happy", "sad", "angry", "worried", "excited"],
            "relationship_topic": ["relationship", "partner", "spouse", "together", "couple", "love"],
            "shared_planning": ["plan", "planning", "weekend", "together", "schedule"],
            "support_needed": ["help", "support", "need", "struggling", "difficult"],
            "work_progress": ["working", "progress", "project", "completed", "building"],
            "blockers": ["blocked", "stuck", "problem", "issue", "challenge"],
            "help_needed": ["help", "need help", "stuck", "not sure"],
            "collaboration_opportunity": ["collaborate", "work together", "team up"],
            "technical_insight": ["learned", "discovery", "realized", "insight", "found"],
            "career_advice": ["career", "job", "work", "professional"],
            "learning_discovery": ["learn", "learning", "discovered", "found out"],
            "creative_breakthrough": ["creative", "idea", "breakthrough", "inspiration"],
        }

        # Check inclusion criteria with expanded keywords
        matches_inclusion = False
        matched_criterion = None
        for criterion in policy.inclusion_criteria:
            # Check if criterion has keyword mapping
            if criterion in keyword_map:
                keywords = keyword_map[criterion]
            else:
                keywords = criterion.replace("_", " ").split()

            if any(kw in combined_text for kw in keywords):
                matches_inclusion = True
                matched_criterion = criterion
                break

        # Check exclusion criteria (must be more specific to avoid false positives)
        exclusion_map = {
            "work_details": ["debug", "debugging", "algorithm", "implementation", "code review", "technical spec", "python code"],
            "third_party_conversations": ["john said", "she told me", "they said"],
            "financial_specifics": ["$", "dollar", "money", "salary", "payment", "financial"],
            "proprietary_details": ["confidential", "proprietary", "secret", "internal"],
            "personal_relationships": ["relationship issues", "dating", "girlfriend", "boyfriend", "personal life"],
        }

        matches_exclusion = False
        for criterion in policy.exclusion_criteria:
            if criterion in exclusion_map:
                keywords = exclusion_map[criterion]
            else:
                keywords = criterion.replace("_", " ").split()

            # Need to match specific phrases, not just presence
            if any(kw in combined_text for kw in keywords):
                matches_exclusion = True
                break

        # Check trigger keywords
        matches_trigger = False
        for keyword in policy.trigger_keywords:
            if keyword.lower() in combined_text:
                matches_trigger = True
                break

        # Check trigger entities
        for entity in policy.trigger_entities:
            if entity.lower() in combined_text:
                matches_trigger = True
                break

        is_relevant = (matches_inclusion or matches_trigger) and not matches_exclusion

        reason = f"Matches criterion: {matched_criterion}" if is_relevant and matched_criterion else "Does not match policy criteria"

        return is_relevant, reason

    async def _filter_and_transform(
        self,
        turn: RawConversationTurn,
        policy
    ) -> tuple[str, List[str], float, float]:
        """
        Filter and transform content according to policy (used only for mock mode).

        Returns:
            (filtered_content, topics, confidence, sensitivity)
        """
        # Only used in mock mode - LLM mode uses _evaluate_content_single_pass directly
        return self._mock_filter_and_transform(turn, policy)

    async def _evaluate_content_single_pass(
        self,
        turn: RawConversationTurn,
        policy
    ) -> Dict[str, Any]:
        """
        Use Claude API to evaluate and transform content in a single pass.

        Returns:
            Dict with keys: is_relevant, relevance_reason, transformed_content, topics,
            confidence_score, sensitivity_score
        """
        import json

        # Build comprehensive evaluation prompt
        rules = policy.transformation_rules

        transformation_instructions = []
        if rules.remove_names:
            transformation_instructions.append("- Remove or replace all person names with generic placeholders like [Person] or [Friend]")
        if rules.remove_locations:
            transformation_instructions.append("- Remove or generalize specific locations (use [Location] or general descriptions like 'a city')")
        if rules.remove_organizations:
            transformation_instructions.append("- Remove or replace organization names with [Organization] or generic descriptions")
        if rules.generalize_situations:
            transformation_instructions.append(f"- Generalize specific situations to preserve privacy (detail level: {rules.detail_level})")
        if rules.preserve_emotional_tone:
            transformation_instructions.append("- IMPORTANT: Preserve the emotional tone and sentiment of the original message")

        # Add custom prompt if specified
        if rules.custom_prompt:
            transformation_instructions.append(f"- Custom transformation: {rules.custom_prompt}")

        transformation_text = "\n".join(transformation_instructions) if transformation_instructions else "- Preserve the content as-is"

        system_prompt = f"""You are a privacy-preserving content filter for a collaborative space.

Your task is to evaluate a conversation and determine:
1. Whether it's relevant to this space's policy
2. How to transform it to respect privacy while preserving value
3. What topics it covers
4. Confidence and sensitivity scores

SPACE POLICY:
<inclusion_criteria>
{', '.join(policy.inclusion_criteria)}
</inclusion_criteria>

<exclusion_criteria>
{', '.join(policy.exclusion_criteria)}
</exclusion_criteria>

<trigger_keywords>
{', '.join(policy.trigger_keywords) if policy.trigger_keywords else 'None'}
</trigger_keywords>

<trigger_entities>
{', '.join(policy.trigger_entities) if policy.trigger_entities else 'None'}
</trigger_entities>

TRANSFORMATION RULES:
{transformation_text}

Detail level: {rules.detail_level}

RESPONSE FORMAT:
Respond with the following XML structure. Do not include any other text before or after the XML.

<evaluation>
    <is_relevant>true or false</is_relevant>
    <relevance_reason>brief explanation</relevance_reason>
    <transformed_content>the filtered/transformed message</transformed_content>
    <topics>
        <topic>topic1</topic>
        <topic>topic2</topic>
    </topics>
    <confidence_score>0.0-1.0</confidence_score>
    <sensitivity_score>0.0-1.0</sensitivity_score>
</evaluation>

SCORING GUIDANCE:
- confidence_score: How confident you are that this content matches the policy (1.0 = perfect match)
- sensitivity_score: How sensitive/private the content is (1.0 = highly sensitive, requires careful handling)"""

        conversation_text = f"User: {turn.user_message}\n\nAssistant: {turn.assistant_message}"

        try:
            message = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": f"Evaluate this conversation:\n\n{conversation_text}"
                }]
            )

            # Parse XML response
            response_text = message.content[0].text.strip()

            # Extract XML if there's extra text
            import xml.etree.ElementTree as ET

            # Try to find <evaluation> tag in case there's extra text
            if '<evaluation>' in response_text:
                start = response_text.find('<evaluation>')
                end = response_text.find('</evaluation>') + len('</evaluation>')
                response_text = response_text[start:end]

            root = ET.fromstring(response_text)

            # Extract values with safe defaults
            is_relevant_text = root.findtext('is_relevant', 'false').strip().lower()
            is_relevant = is_relevant_text in ('true', '1', 'yes')

            relevance_reason = root.findtext('relevance_reason', 'No reason provided').strip()
            transformed_content = root.findtext('transformed_content', turn.user_message).strip()

            # Extract topics
            topics = []
            topics_elem = root.find('topics')
            if topics_elem is not None:
                topics = [topic.text.strip() for topic in topics_elem.findall('topic') if topic.text]

            # Extract scores with safe conversion
            try:
                confidence_score = float(root.findtext('confidence_score', '0.5'))
            except (ValueError, TypeError):
                confidence_score = 0.5

            try:
                sensitivity_score = float(root.findtext('sensitivity_score', '0.5'))
            except (ValueError, TypeError):
                sensitivity_score = 0.5

            return {
                'is_relevant': is_relevant,
                'relevance_reason': relevance_reason,
                'transformed_content': transformed_content,
                'topics': topics,
                'confidence_score': confidence_score,
                'sensitivity_score': sensitivity_score
            }

        except ET.ParseError as e:
            # Fallback: mark as not relevant
            print(f"LLM response was not valid XML: {e}")
            print(f"Response text: {response_text[:500]}")  # Log first 500 chars for debugging
            return {
                'is_relevant': False,
                'relevance_reason': f'XML parsing error: {str(e)}',
                'transformed_content': turn.user_message,
                'topics': [],
                'confidence_score': 0.0,
                'sensitivity_score': 0.5
            }
        except Exception as e:
            # Fallback on any error
            print(f"Error in LLM evaluation: {e}")
            import traceback
            traceback.print_exc()
            return {
                'is_relevant': False,
                'relevance_reason': f'Evaluation error: {str(e)}',
                'transformed_content': turn.user_message,
                'topics': [],
                'confidence_score': 0.0,
                'sensitivity_score': 0.5
            }

    def _mock_filter_and_transform(
        self,
        turn: RawConversationTurn,
        policy
    ) -> tuple[str, List[str], float, float]:
        """Mock filtering using simple rules."""

        content = turn.user_message
        rules = policy.transformation_rules

        # Apply transformations
        if rules.remove_names:
            # Simple name removal (would use NER in real version)
            common_names = ["andrew", "jamila", "novel", "alexis", "ron", "eugene"]
            for name in common_names:
                content = content.replace(name.capitalize(), "[Person]")
                content = content.replace(name.lower(), "[person]")

        if rules.remove_organizations:
            # Simple org removal
            orgs = ["flashbots", "anthropic", "openai", "google"]
            for org in orgs:
                content = content.replace(org.capitalize(), "[Organization]")
                content = content.replace(org.lower(), "[organization]")

        if rules.generalize_situations:
            # Add generalizing phrase
            if rules.detail_level == "low":
                content = f"General context: {content[:100]}..."
            elif rules.detail_level == "medium":
                content = f"{content[:200]}"

        # Extract topics (simple keyword extraction)
        topics = []
        for criterion in policy.inclusion_criteria:
            if criterion.replace("_", " ") in turn.user_message.lower():
                topics.append(criterion)

        # Mock confidence and sensitivity
        confidence = 0.8
        sensitivity = 0.3

        # Increase sensitivity for certain keywords
        sensitive_keywords = ["stress", "conflict", "problem", "worried", "angry"]
        for kw in sensitive_keywords:
            if kw in turn.user_message.lower():
                sensitivity = 0.6
                break

        return content, topics, confidence, sensitivity

    def _check_approval_needed(
        self,
        confidence: float,
        sensitivity: float,
        policy
    ) -> tuple[bool, str]:
        """Check if content needs manual approval."""

        # Check threshold
        if confidence < policy.auto_approve_threshold:
            return True, f"Confidence {confidence} below threshold {policy.auto_approve_threshold}"

        # Check sensitivity against approval rules
        for rule in policy.require_approval_if:
            if "sensitivity" in rule.lower():
                # Parse "sensitivity > 0.6"
                try:
                    parts = rule.split()
                    if len(parts) >= 3 and parts[0].lower() == "sensitivity":
                        operator = parts[1]
                        threshold = float(parts[2])

                        if operator == ">" and sensitivity > threshold:
                            return True, f"Sensitivity {sensitivity} > {threshold}"
                        elif operator == ">=" and sensitivity >= threshold:
                            return True, f"Sensitivity {sensitivity} >= {threshold}"
                except:
                    pass

        # Check high sensitivity topics
        # (Would check against conversation content in real version)

        return False, "Auto-approved"


class MockLLMClient:
    """Mock LLM client for testing."""

    async def analyze_relevance(self, conversation: str, policy_prompt: str) -> Dict[str, Any]:
        """Mock relevance analysis."""
        return {
            "relevant": True,
            "confidence": 0.8,
            "reason": "Mock analysis"
        }

    async def filter_content(self, conversation: str, transformation_rules: Dict) -> Dict[str, Any]:
        """Mock content filtering."""
        return {
            "filtered_content": "Mock filtered content",
            "topics": ["mock_topic"],
            "confidence": 0.8,
            "sensitivity": 0.3
        }
