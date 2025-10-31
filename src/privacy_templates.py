"""
Privacy contract templates for different space types.
These are pre-written transformation instructions that users can start with.
"""

PRIVACY_TEMPLATES = {
    "emotional_only": {
        "name": "Emotional State Only",
        "description": "Perfect for couples/partners. Share how you're feeling, nothing else.",
        "prompt": """- ONLY share the emotional state (stressed, excited, worried, happy, overwhelmed, etc.)
- Remove ALL specific details: names, places, companies, projects, events
- Remove all context about what caused the emotion
- Preserve the intensity of the emotion (very stressed vs slightly stressed)
- Keep it to 1-2 sentences maximum

Example transformation:
Input: "I'm feeling really stressed about the big presentation at work tomorrow for the Johnson account"
Output: "Feeling quite stressed about an upcoming work obligation"
""",
        "inclusion_criteria": ["emotional_state", "feelings", "mood"],
        "exclusion_criteria": ["work_details", "financial_specifics", "third_party_conversations"]
    },

    "patterns_and_insights": {
        "name": "Patterns & Insights Only",
        "description": "For learning communities. Share what you learned, not what you did.",
        "prompt": """- Extract the general pattern, insight, or learning
- Remove all specific context: people, companies, projects, technologies
- Generalize the situation to make it universally applicable
- Focus on the "why" and "what I learned", not the "what" or "who"
- Make it useful for others facing similar situations

Example transformation:
Input: "I realized while debugging the payment system that testing edge cases early saves so much time"
Output: "Testing edge cases early in development prevents costly debugging later"
""",
        "inclusion_criteria": ["learning_discovery", "technical_insight", "creative_breakthrough"],
        "exclusion_criteria": ["proprietary_details", "work_details", "personal_relationships"]
    },

    "support_requests": {
        "name": "Support Requests",
        "description": "For support groups. Share struggles and needs while protecting privacy.",
        "prompt": """- Share the type of challenge or struggle in general terms
- Remove identifying details: names, locations, specific organizations
- Preserve the emotional weight and urgency
- Keep enough context for others to offer relevant support
- Focus on feelings and needs, not specifics

Example transformation:
Input: "I'm struggling with my manager at Acme Corp constantly micromanaging my project work"
Output: "Dealing with micromanagement at work, feeling frustrated and needing strategies to handle it"
""",
        "inclusion_criteria": ["support_needed", "emotional_state", "help_needed"],
        "exclusion_criteria": ["third_party_conversations", "financial_specifics"]
    },

    "team_blockers": {
        "name": "Team Blockers & Progress",
        "description": "For work teams. Share what you're working on and what's blocking you.",
        "prompt": """- Share high-level progress and blockers
- Remove implementation details and proprietary information
- Keep project names generic (e.g., "the authentication project" not "Project Phoenix")
- Focus on categories of work, not specific code or algorithms
- Preserve what you need help with

Example transformation:
Input: "Made good progress on the OAuth integration for the mobile app, but stuck on handling refresh tokens in the edge case where the user's session expires mid-request"
Output: "Making progress on authentication work, currently blocked on handling session edge cases"
""",
        "inclusion_criteria": ["work_progress", "blockers", "help_needed"],
        "exclusion_criteria": ["proprietary_details", "financial_specifics"]
    },

    "context_with_privacy": {
        "name": "Full Context (Private Names)",
        "description": "For close friends. Keep context but anonymize people and organizations.",
        "prompt": """- Keep the full story and context
- Replace all names with generic placeholders: [Friend], [Colleague], [Partner], etc.
- Replace company names with [Company], [Organization], etc.
- Replace specific locations with general regions
- Preserve everything else: emotions, events, details

Example transformation:
Input: "Had lunch with Sarah from Google and she mentioned their new AI project is facing challenges"
Output: "Had lunch with [Friend] from [Tech Company] and she mentioned their new AI project is facing challenges"
""",
        "inclusion_criteria": ["relationship_topic", "shared_planning", "emotional_state"],
        "exclusion_criteria": []
    },

    "minimal_filter": {
        "name": "Minimal Filtering",
        "description": "For trusted circles. Only remove highly sensitive information.",
        "prompt": """- Keep most details intact
- Only remove: financial specifics (salaries, prices), proprietary trade secrets, medical details
- Preserve names, context, stories
- This is for spaces with high trust

Example transformation:
Input: "I got a raise to $150k and I'm excited to finally afford that vacation"
Output: "I got a raise and I'm excited to finally afford that vacation"
""",
        "inclusion_criteria": ["general"],
        "exclusion_criteria": ["financial_specifics", "proprietary_details"]
    },

    "custom": {
        "name": "Custom (Start from Scratch)",
        "description": "Write your own transformation instructions from scratch.",
        "prompt": "",
        "inclusion_criteria": ["general"],
        "exclusion_criteria": []
    }
}


def get_template(template_id: str) -> dict:
    """Get a privacy template by ID."""
    return PRIVACY_TEMPLATES.get(template_id, PRIVACY_TEMPLATES["custom"])


def get_all_templates() -> dict:
    """Get all available templates."""
    return PRIVACY_TEMPLATES
