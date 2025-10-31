# Quick Start - Explore What We've Built

## 🎯 What's Working Right Now

You have a **fully functional multi-space system** with:
- User management
- Space creation (1:1, group, public)
- Invite code system
- Policy templates (couples, team, public feed)
- 32 passing tests

## 🚀 Try It Out

### Option 1: Run Automated Demos

See all the features in action:

```bash
cd hivemind-mcp
python demo_simple.py
```

This shows:
1. **Couples scenario** - Andrew & Jamila create a relationship space
2. **Hacker house** - Group space for pirate ship crew
3. **Multiple spaces** - One user in different spaces
4. **Policy comparison** - See how different templates work

### Option 2: Interactive Python Session

Play with the API directly:

```bash
cd hivemind-mcp
python
```

```python
from src.space_manager import SpaceManager
from src.models import SpaceType

# Create a manager
manager = SpaceManager()

# Create users
andrew = manager.create_user("Andrew", "andrew@example.com")
jamila = manager.create_user("Jamila", "jamila@example.com")

# Create a 1:1 space with couples policy
space = manager.create_space(
    creator_user_id=andrew.user_id,
    name="Andrew & Jamila",
    space_type=SpaceType.ONE_ON_ONE,
    policy_template="couples"
)

print(f"Invite code: {space.invite_code}")
print(f"Policy includes: {space.policy.inclusion_criteria}")

# Jamila joins
success = manager.join_space(space.space_id, jamila.user_id, space.invite_code)
print(f"Jamila joined: {success}")

# List spaces
andrews_spaces = manager.list_user_spaces(andrew.user_id)
print(f"Andrew has {len(andrews_spaces)} space(s)")
```

### Option 3: Run Tests

See all the functionality tested:

```bash
cd hivemind-mcp
python -m pytest tests/ -v
```

This runs 32 tests covering:
- User creation
- Space creation (all types)
- Invite codes
- Joining/leaving spaces
- Policy templates
- Real scenarios

## 📋 What Each Component Does

### 1. SpaceManager (`src/space_manager.py`)

The main API for managing spaces:

```python
manager = SpaceManager()

# User operations
user = manager.create_user(name, email)
user = manager.get_user(user_id)

# Space operations
space = manager.create_space(creator, name, type, template)
space = manager.get_space(space_id)
space = manager.get_space_by_invite_code(code)
spaces = manager.list_user_spaces(user_id)

# Membership
success = manager.join_space(space_id, user_id, invite_code)
success = manager.leave_space(space_id, user_id)
members = manager.get_space_members(space_id)
```

### 2. Policy Templates (`src/models.py`)

Three pre-configured policies:

**Couples Policy** (`policy_template="couples"`):
- ✅ Shares: emotional_state, relationship_topic, support_needed
- ❌ Excludes: work_details, third_party_conversations
- 🔧 Transforms: Removes names, preserves emotion
- 🎯 Use case: 1:1 relationships

**Team Policy** (`policy_template="team"`):
- ✅ Shares: work_progress, blockers, help_needed
- ❌ Excludes: proprietary_details, personal_relationships
- 🔧 Transforms: Keeps names/orgs, high detail
- 🎯 Use case: Work teams, hacker houses

**Public Feed** (`policy_template="public"`):
- ✅ Shares: technical_insight, career_advice, learning
- ❌ Excludes: personal_details, names, companies
- 🔧 Transforms: Heavy anonymization, low detail
- 🎯 Use case: Public broadcasting

### 3. Data Models

All the core types are in `src/models.py`:

- `User` - User profile + consent
- `Space` - Container for shared content
- `Policy` - Rules for what/how to share
- `SpaceMember` - User's role in a space
- `RawConversationTurn` - Original conversation
- `FilteredDocument` - Processed content for sharing

## 🔍 Inspect a Space

Want to see what's inside a space?

```python
from src.space_manager import SpaceManager
from src.models import SpaceType

manager = SpaceManager()
andrew = manager.create_user("Andrew")
space = manager.create_space(
    andrew.user_id,
    "Test Space",
    SpaceType.ONE_ON_ONE,
    policy_template="couples"
)

# Look at the space
print(f"Space ID: {space.space_id}")
print(f"Invite: {space.invite_code}")
print(f"Type: {space.space_type}")
print(f"Members: {len(space.members)}")

# Look at the policy
policy = space.policy
print(f"\nPolicy includes:")
for item in policy.inclusion_criteria:
    print(f"  + {item}")

print(f"\nPolicy excludes:")
for item in policy.exclusion_criteria:
    print(f"  - {item}")

print(f"\nTransformations:")
print(f"  Remove names: {policy.transformation_rules.remove_names}")
print(f"  Preserve emotion: {policy.transformation_rules.preserve_emotional_tone}")
print(f"  Detail level: {policy.transformation_rules.detail_level}")

# Look at approval settings
print(f"\nApproval:")
print(f"  Auto-approve threshold: {policy.auto_approve_threshold}")
print(f"  Requires approval if: {policy.require_approval_if}")
```

## 📊 Understanding Policy Templates

Run the policy comparison demo:

```bash
python demo_simple.py quick
```

Or manually compare them:

```python
from src.models import create_couples_policy, create_public_feed_policy, create_team_policy

couples = create_couples_policy("test")
public = create_public_feed_policy("test")
team = create_team_policy("test")

print("Couples includes:", couples.inclusion_criteria)
print("Public includes:", public.inclusion_criteria)
print("Team includes:", team.inclusion_criteria)
```

## 🎨 Example Scenarios

### Scenario 1: Create a Relationship Space

```python
manager = SpaceManager()

# Andrew sets up
andrew = manager.create_user("Andrew Miller", "andrew@example.com")
space = manager.create_space(
    andrew.user_id,
    "Andrew & Jamila",
    SpaceType.ONE_ON_ONE,
    policy_template="couples"
)

invite_code = space.invite_code

# Jamila joins
jamila = manager.create_user("Jamila", "jamila@example.com")
manager.join_space(space.space_id, jamila.user_id, invite_code)

# Both see the space
print(manager.list_user_spaces(andrew.user_id))
print(manager.list_user_spaces(jamila.user_id))
```

### Scenario 2: Create a Hacker House Group

```python
manager = SpaceManager()

# Create space
andrew = manager.create_user("Andrew")
pirate_ship = manager.create_space(
    andrew.user_id,
    "Pirate Ship",
    SpaceType.GROUP,
    policy_template="team"
)

# Everyone joins
for name in ["Novel", "Alexis", "Ron", "Eugene"]:
    user = manager.create_user(name)
    manager.join_space(pirate_ship.space_id, user.user_id, pirate_ship.invite_code)

# Check members
print(f"Members: {len(pirate_ship.members)}")
```

### Scenario 3: One Person, Multiple Spaces

```python
manager = SpaceManager()
andrew = manager.create_user("Andrew")

# Create different spaces
couples = manager.create_space(andrew.user_id, "Andrew & Jamila", SpaceType.ONE_ON_ONE, policy_template="couples")
team = manager.create_space(andrew.user_id, "Work Team", SpaceType.GROUP, policy_template="team")
public = manager.create_space(andrew.user_id, "Public Feed", SpaceType.PUBLIC, policy_template="public")

# List all
spaces = manager.list_user_spaces(andrew.user_id)
for space in spaces:
    print(f"{space.name}: {space.space_type.value}")
```

## ⚡ Quick Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_models.py -v
python -m pytest tests/test_space_manager.py -v

# Run demos
python demo_simple.py           # All demos with pauses
python demo_simple.py quick     # Just couples demo

# Interactive Python
python
>>> from src.space_manager import SpaceManager
>>> manager = SpaceManager()
>>> # ... play around
```

## 📖 What's Next?

What we have now:
- ✅ User management
- ✅ Space creation and joining
- ✅ Policy templates
- ✅ Full test coverage

What's coming next:
- 🚧 **Policy Engine** - Actually process conversations through policies
- 🚧 **MCP Tools** - Integrate with Claude Code
- 🚧 **Firestore** - Persistent storage
- 🚧 **Approval Queue** - Review sensitive content before sharing

## 🐛 Troubleshooting

**Import errors?**
```bash
cd hivemind-mcp
python -m pip install pydantic pytest
```

**Tests failing?**
```bash
# Make sure you're in the right directory
cd hivemind-mcp
python -m pytest tests/ -v
```

**Want to reset everything?**
Just restart Python - everything is in-memory for now!

---

**Ready to explore?** Start with `python demo_simple.py quick` to see it in action!
