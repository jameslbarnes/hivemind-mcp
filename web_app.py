#!/usr/bin/env python3
"""
Hivemind Web App - Flask interface for space management and approvals.

This provides a web UI for:
- Creating and joining spaces with invite codes
- Viewing pending invites
- Approving/rejecting conversation disclosures (CONSENT LAYER)
- Browsing space feeds
- Managing members and policies

Run: python web_app.py
Then visit: http://localhost:5000
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta
from functools import wraps
import asyncio
import secrets

from src.space_manager import SpaceManager
from src.policy_engine import PolicyEngine
from src.models import RawConversationTurn, SpaceType, ConversationHistory, RoutingMetadata
from src.privacy_templates import get_all_templates, get_template

# Initialize Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Initialize managers with Firestore
FIREBASE_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") or r"C:\Users\james\Downloads\hivemind-476519-d174ae36378a.json"

print("=" * 70)
print("HIVEMIND WEB APP STARTING")
print("=" * 70)

if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    print("Using GOOGLE_APPLICATION_CREDENTIALS_JSON from environment")
else:
    print(f"Using local credentials file: {FIREBASE_CREDS}")

print("Initializing SpaceManager with Firestore...")
try:
    space_manager = SpaceManager(use_firestore=True, credentials_path=FIREBASE_CREDS)
    print("SpaceManager initialized successfully!")
except Exception as e:
    print(f"FAILED to initialize SpaceManager: {e}")
    import traceback
    traceback.print_exc()
    raise

# Initialize PolicyEngine with Anthropic client for LLM-based routing
import anthropic
import os
llm_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) if os.getenv("ANTHROPIC_API_KEY") else None
policy_engine = PolicyEngine(space_manager, llm_client=llm_client)

# Store pending approvals (would be in Firestore later)
pending_approvals = {}

# Store notifications (would be in Firestore later)
notifications = {}

# Store raw conversation turns (would be in Firestore later)
raw_conversations = {}


# ============================================================================
# Authentication & Session Management
# ============================================================================

def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get current logged-in user."""
    if 'user_id' in session:
        return space_manager.get_user(session['user_id'])
    return None


# ============================================================================
# Routes: Authentication
# ============================================================================

@app.route('/')
def index():
    """Home page."""
    user = get_current_user()
    if user:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email', '')

        # Find or create user
        # In real app, would authenticate properly
        existing_users = [u for u in space_manager.get_all_users() if u.display_name == username]

        if existing_users:
            user = existing_users[0]
        else:
            user = space_manager.create_user(username, email)

        session['user_id'] = user.user_id
        flash(f'Welcome, {user.display_name}!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout."""
    session.pop('user_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


# ============================================================================
# Routes: OAuth / MCP Connector Setup
# ============================================================================

@app.route('/oauth/credentials', methods=['GET', 'POST'])
@login_required
def oauth_credentials():
    """View or generate OAuth credentials for MCP connector."""
    user = get_current_user()

    if request.method == 'POST':
        # Generate new credentials
        credentials = space_manager.generate_oauth_credentials(user.user_id)

        if credentials:
            flash('OAuth credentials generated successfully!', 'success')
            # Refresh user object
            user = get_current_user()
        else:
            flash('Failed to generate credentials', 'error')

    return render_template('oauth_credentials.html', user=user)


@app.route('/oauth/revoke', methods=['POST'])
@login_required
def oauth_revoke():
    """Revoke OAuth credentials."""
    user = get_current_user()

    if user.oauth_credentials:
        user.oauth_credentials = None
        space_manager.save_user(user)
        flash('OAuth credentials revoked', 'info')
    else:
        flash('No credentials to revoke', 'error')

    return redirect(url_for('oauth_credentials'))


# ============================================================================
# Routes: Dashboard
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing all spaces."""
    user = get_current_user()
    spaces = space_manager.list_user_spaces(user.user_id)

    # Get notification count
    user_notifications = notifications.get(user.user_id, [])
    unread_count = len([n for n in user_notifications if not n.get('read', False)])

    # Get pending approval count
    user_approvals = pending_approvals.get(user.user_id, [])
    pending_count = len(user_approvals)

    # Check if user has OAuth credentials
    has_oauth = user.oauth_credentials is not None

    # Get conversation history
    conversation_history = space_manager.get_conversation_history(user.user_id, limit=20)

    app.logger.info(f"=== DASHBOARD ===")
    app.logger.info(f"Logged in user_id: {user.user_id}")
    app.logger.info(f"User display_name: {user.display_name}")
    app.logger.info(f"Found {len(conversation_history)} conversations")
    app.logger.info(f"================")

    return render_template('dashboard.html',
                         user=user,
                         spaces=spaces,
                         unread_count=unread_count,
                         pending_count=pending_count,
                         has_oauth=has_oauth,
                         conversations=conversation_history)


# ============================================================================
# Routes: Space Management
# ============================================================================

@app.route('/spaces/create', methods=['GET', 'POST'])
@login_required
def create_space():
    """Create a new space."""
    user = get_current_user()

    if request.method == 'POST':
        name = request.form.get('name')
        space_type = request.form.get('space_type')
        policy_template = request.form.get('policy_template')

        # Create space
        space = space_manager.create_space(
            user.user_id,
            name,
            SpaceType(space_type),
            policy_template=policy_template
        )

        flash(f'Space "{name}" created! Invite code: {space.invite_code}', 'success')
        return redirect(url_for('view_space', space_id=space.space_id))

    # Get all privacy templates
    templates = get_all_templates()

    return render_template('create_space.html', user=user, templates=templates)


@app.route('/spaces/<space_id>')
@login_required
def view_space(space_id):
    """View a specific space."""
    user = get_current_user()
    space = space_manager.get_space(space_id)

    if not space:
        flash('Space not found', 'error')
        return redirect(url_for('dashboard'))

    # Check if user is member
    is_member = any(m.user_id == user.user_id for m in space.members)

    if not is_member:
        flash('You are not a member of this space', 'error')
        return redirect(url_for('dashboard'))

    # Get members with user info
    members_info = []
    for member in space.members:
        user_obj = space_manager.get_user(member.user_id)
        members_info.append({
            'user': user_obj,
            'role': member.role,
            'joined_at': member.joined_at
        })

    # Get conversations routed to this space
    all_conversations = space_manager.get_conversation_history(user.user_id, limit=100)

    # Filter for conversations that were routed to this space
    conversations = []
    for conv in all_conversations:
        # Check if any routing result is for this space and was shared
        for result in conv.routing_results:
            if result.space_id == space_id and result.action == 'shared':
                conversations.append(conv)
                break  # Only add each conversation once

    app.logger.info(f"Space {space_id} feed: showing {len(conversations)} conversations")

    return render_template('view_space.html',
                         user=user,
                         space=space,
                         members=members_info,
                         conversations=conversations)


@app.route('/spaces/<space_id>/policy/update', methods=['POST'])
@login_required
def update_policy(space_id):
    """Update space policy."""
    user = get_current_user()
    space = space_manager.get_space(space_id)

    if not space or not space.is_member(user.user_id):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403

    try:
        # Get updated policy fields
        custom_prompt = request.json.get('custom_prompt', '')

        # Update the transformation rules custom prompt
        space.policy.transformation_rules.custom_prompt = custom_prompt if custom_prompt else None

        # Save the updated space
        if space_manager.use_firestore:
            space_manager.backend.save_space(space)
        else:
            space_manager.spaces[space_id] = space

        return jsonify({'success': True, 'message': 'Policy updated successfully'})
    except Exception as e:
        app.logger.error(f"Error updating policy: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/spaces/<space_id>/full_prompt')
@login_required
def get_full_prompt(space_id):
    """Get the full system prompt that will be sent to Claude."""
    user = get_current_user()
    space = space_manager.get_space(space_id)

    if not space or not space.is_member(user.user_id):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403

    try:
        # Build the prompt same way the policy engine does
        policy = space.policy
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
Inclusion criteria: {', '.join(policy.inclusion_criteria)}
Exclusion criteria: {', '.join(policy.exclusion_criteria)}
Trigger keywords: {', '.join(policy.trigger_keywords) if policy.trigger_keywords else 'None'}
Trigger entities: {', '.join(policy.trigger_entities) if policy.trigger_entities else 'None'}

TRANSFORMATION RULES:
{transformation_text}

Detail level: {rules.detail_level}

RESPONSE FORMAT (valid JSON):
{{
    "is_relevant": true/false,
    "relevance_reason": "brief explanation",
    "transformed_content": "the filtered/transformed message",
    "topics": ["topic1", "topic2"],
    "confidence_score": 0.0-1.0,
    "sensitivity_score": 0.0-1.0
}}

SCORING GUIDANCE:
- confidence_score: How confident you are that this content matches the policy (1.0 = perfect match)
- sensitivity_score: How sensitive/private the content is (1.0 = highly sensitive, requires careful handling)

Respond ONLY with valid JSON, no other text."""

        return jsonify({'success': True, 'prompt': system_prompt})
    except Exception as e:
        app.logger.error(f"Error getting full prompt: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/spaces/<space_id>/backtest', methods=['POST'])
@login_required
def backtest_policy(space_id):
    """Backtest policy on previous conversations."""
    user = get_current_user()
    space = space_manager.get_space(space_id)

    if not space or not space.is_member(user.user_id):
        return jsonify({'success': False, 'error': 'Not authorized'}), 403

    try:
        # Get all user's conversations
        all_conversations = space_manager.get_conversation_history(user.user_id, limit=50)

        # Convert to RawConversationTurn format and backtest
        results = []
        for conv in all_conversations[:10]:  # Limit to 10 for now
            # Create raw turn from history
            raw_turn = RawConversationTurn(
                turn_id=conv.turn_id,
                user_id=user.user_id,
                timestamp=conv.timestamp,
                user_message=conv.user_message,
                assistant_message=conv.assistant_message
                # topics defaults to empty list
            )

            # Re-evaluate with current policy (run async code in sync context)
            route_results = asyncio.run(policy_engine.route_conversation(raw_turn, user.user_id))

            # Find result for this space
            space_result = None
            for r in route_results:
                if r.space_id == space_id:
                    space_result = r
                    break

            if space_result:
                results.append({
                    'turn_id': conv.turn_id,
                    'timestamp': conv.timestamp.isoformat(),
                    'user_message': conv.user_message[:100] + '...' if len(conv.user_message) > 100 else conv.user_message,
                    'action': space_result.action,
                    'reason': space_result.reason,
                    'transformed_content': space_result.document.content if space_result.document else None,
                    'confidence': space_result.document.confidence_score if space_result.document else None,
                    'sensitivity': space_result.document.sensitivity_score if space_result.document else None
                })

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        app.logger.error(f"Error backtesting policy: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/spaces/join', methods=['GET', 'POST'])
@login_required
def join_space():
    """Join a space with invite code."""
    user = get_current_user()

    if request.method == 'POST':
        invite_code = request.form.get('invite_code').strip().upper()

        # Find space by invite code
        space = None
        for s in space_manager.spaces.values():
            if s.invite_code == invite_code:
                space = s
                break

        if not space:
            flash('Invalid invite code', 'error')
            return render_template('join_space.html', user=user)

        # Try to join
        success = space_manager.join_space(space.space_id, user.user_id, invite_code)

        if success:
            # Notify space creator
            creator = space_manager.get_user(space.created_by)
            add_notification(space.created_by, {
                'type': 'member_joined',
                'message': f'{user.display_name} joined {space.name}',
                'space_id': space.space_id,
                'timestamp': datetime.now()
            })

            flash(f'Successfully joined "{space.name}"!', 'success')
            return redirect(url_for('view_space', space_id=space.space_id))
        else:
            flash('Failed to join space (already a member or space is full)', 'error')

    return render_template('join_space.html', user=user)


# ============================================================================
# Routes: Approvals (CONSENT LAYER)
# ============================================================================

@app.route('/approvals')
@login_required
def view_approvals():
    """View pending approvals - THE KEY CONSENT FEATURE."""
    user = get_current_user()
    user_approvals = pending_approvals.get(user.user_id, [])

    # Enrich approvals with space info
    enriched_approvals = []
    for approval in user_approvals:
        space = space_manager.get_space(approval.space_id)
        enriched_approvals.append({
            'approval': approval,
            'space': space
        })

    return render_template('approvals.html',
                         user=user,
                         approvals=enriched_approvals)


@app.route('/approvals/<approval_id>/approve', methods=['POST'])
@login_required
def approve_disclosure(approval_id):
    """Approve a pending disclosure."""
    user = get_current_user()
    user_approvals = pending_approvals.get(user.user_id, [])

    approval = None
    for a in user_approvals:
        if a.approval_id == approval_id:
            approval = a
            break

    if not approval:
        flash('Approval not found', 'error')
        return redirect(url_for('view_approvals'))

    # Get optional edited content
    edited_content = request.form.get('edited_content', '')

    if edited_content:
        # User edited the content before approving
        final_content = edited_content
    else:
        # Use proposed content as-is
        final_content = approval.proposed_content

    # TODO: Actually share the content to the space
    # For now, just remove from pending
    user_approvals.remove(approval)

    flash(f'Content approved and shared to space', 'success')
    return redirect(url_for('view_approvals'))


@app.route('/approvals/<approval_id>/reject', methods=['POST'])
@login_required
def reject_disclosure(approval_id):
    """Reject a pending disclosure."""
    user = get_current_user()
    user_approvals = pending_approvals.get(user.user_id, [])

    approval = None
    for a in user_approvals:
        if a.approval_id == approval_id:
            approval = a
            break

    if not approval:
        flash('Approval not found', 'error')
        return redirect(url_for('view_approvals'))

    # Remove from pending
    user_approvals.remove(approval)

    flash('Content rejected and not shared', 'info')
    return redirect(url_for('view_approvals'))


# ============================================================================
# Routes: Notifications
# ============================================================================

@app.route('/notifications')
@login_required
def view_notifications():
    """View notifications."""
    user = get_current_user()
    user_notifications = notifications.get(user.user_id, [])

    # Mark all as read
    for notif in user_notifications:
        notif['read'] = True

    return render_template('notifications.html',
                         user=user,
                         notifications=user_notifications)


# ============================================================================
# API Routes (for AJAX/fetch)
# ============================================================================

@app.route('/api/simulate_conversation', methods=['POST'])
@login_required
def simulate_conversation():
    """
    Simulate a conversation turn and route through policies.
    This is like what would happen in the MCP server.
    """
    user = get_current_user()

    data = request.get_json()
    user_message = data.get('user_message')
    assistant_message = data.get('assistant_message', 'I understand.')

    # Create conversation turn
    turn = RawConversationTurn(
        user_id=user.user_id,
        user_message=user_message,
        assistant_message=assistant_message
    )

    # Route through policy engine
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(
        policy_engine.route_conversation(turn, user.user_id)
    )
    loop.close()

    # Process results
    shared_to = []
    approvals_needed = []

    for result in results:
        space = space_manager.get_space(result.space_id)

        if result.action == "shared":
            shared_to.append(space.name)
        elif result.action == "approval_needed":
            approvals_needed.append(space.name)

            # Add to pending approvals
            if user.user_id not in pending_approvals:
                pending_approvals[user.user_id] = []
            pending_approvals[user.user_id].append(result.approval)

    return jsonify({
        'success': True,
        'shared_to': shared_to,
        'approvals_needed': approvals_needed,
        'total_spaces': len(results)
    })


@app.route('/api/webhook/conversation', methods=['POST'])
def webhook_conversation():
    """
    Webhook endpoint for MCP server to trigger conversation routing.
    Called when a new conversation is logged via MCP.
    """
    data = request.get_json()
    turn_id = data.get('turn_id')
    user_id = data.get('user_id')
    user_message = data.get('user_message')
    assistant_message = data.get('assistant_message')

    app.logger.info(f"=== WEBHOOK CALLED ===")
    app.logger.info(f"Received user_id: {user_id}")
    app.logger.info(f"Turn ID: {turn_id}")
    app.logger.info(f"User message: {user_message[:50] if len(user_message) > 50 else user_message}...")
    app.logger.info(f"===================")

    if not all([turn_id, user_id, user_message, assistant_message]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Deduplication: Check if we've seen this exact content very recently (within 5 seconds)
    from datetime import datetime, timedelta
    recent_conversations = space_manager.get_conversation_history(user_id, limit=10)
    cutoff_time = datetime.now() - timedelta(seconds=5)

    for recent_conv in recent_conversations:
        if recent_conv.timestamp > cutoff_time and recent_conv.user_message == user_message:
            app.logger.info(f"Skipping duplicate conversation (same content within 5 seconds)")
            return jsonify({'success': True, 'skipped': True, 'reason': 'duplicate'}), 200

    # Store raw conversation
    turn = RawConversationTurn(
        turn_id=turn_id,
        user_id=user_id,
        user_message=user_message,
        assistant_message=assistant_message
    )
    raw_conversations[turn_id] = turn

    # Route through policy engine
    app.logger.info(f"Starting policy routing for user {user_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(
        policy_engine.route_conversation(turn, user_id)
    )
    loop.close()
    app.logger.info(f"Policy routing complete. Got {len(results)} results")

    # Build routing metadata
    routing_metadata = []
    for result in results:
        app.logger.info(f"  - Space {result.space_id}: {result.action} - {result.reason}")
        space = space_manager.get_space(result.space_id)

        metadata = RoutingMetadata(
            space_id=result.space_id,
            space_name=space.name,
            action=result.action,
            reason=result.reason or "No reason provided"
        )

        if result.document:
            metadata.confidence_score = result.document.confidence_score
            metadata.sensitivity_score = result.document.sensitivity_score
            metadata.filtered_content = result.document.content
            metadata.original_content = user_message

        if result.approval:
            metadata.confidence_score = result.approval.confidence_score
            metadata.sensitivity_score = result.approval.sensitivity_score
            metadata.filtered_content = result.approval.proposed_content
            metadata.original_content = user_message

            # Add to pending approvals
            if user_id not in pending_approvals:
                pending_approvals[user_id] = []
            pending_approvals[user_id].append(result.approval)

        routing_metadata.append(metadata)

    # Save to conversation history
    history = ConversationHistory(
        user_id=user_id,
        turn_id=turn_id,
        timestamp=turn.timestamp,
        user_message=user_message,
        assistant_message=assistant_message,
        routing_results=routing_metadata
    )
    space_manager.add_conversation_history(history)

    return jsonify({
        'success': True,
        'turn_id': turn_id,
        'routed_to': len(results)
    })


# ============================================================================
# Helpers
# ============================================================================

def add_notification(user_id, notification):
    """Add a notification for a user."""
    if user_id not in notifications:
        notifications[user_id] = []
    notification['read'] = False
    notification['id'] = secrets.token_hex(8)
    notifications[user_id].append(notification)


# ============================================================================
# Template Filters
# ============================================================================

@app.template_filter('timeago')
def timeago_filter(dt):
    """Convert datetime to 'time ago' string."""
    if not dt:
        return 'unknown'

    now = datetime.now()
    diff = now - dt

    if diff.total_seconds() < 60:
        return 'just now'
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    else:
        days = int(diff.total_seconds() / 86400)
        return f'{days} day{"s" if days != 1 else ""} ago'


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("HIVEMIND WEB APP")
    print("="*70)
    print("\nStarting Flask server...")
    print("Visit: http://localhost:5000")
    print("\nFeatures:")
    print("  - Create and join spaces with invite codes")
    print("  - View pending invites and notifications")
    print("  - Approve/reject conversation disclosures (CONSENT LAYER)")
    print("  - Browse space feeds and manage members")
    print("\nPress Ctrl+C to stop")
    print("="*70 + "\n")

    app.run(debug=True, port=5000)
