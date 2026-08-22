"""Custom scenarios routes."""
from flask import Blueprint, request, jsonify, current_app
from app.models import CustomScenario, db
from app.services.auth_service import get_auth_service

bp = Blueprint('scenarios', __name__, url_prefix='/api')


def get_user_id_from_token(request_obj):
    """Extract user ID from Authorization header."""
    auth_header = request_obj.headers.get('Authorization')
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None

    access_token = parts[1]
    auth_service = get_auth_service()
    user = auth_service.get_user(access_token)

    return user.get('id') if user else None


@bp.route('/scenarios', methods=['GET'])
def get_custom_scenarios():
    """Get all custom scenarios for the authenticated user."""
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Get optional filter for scenario type
    scenario_type = request.args.get('type')

    query = CustomScenario.query.filter_by(user_id=user_id)
    if scenario_type:
        query = query.filter_by(scenario_type=scenario_type)

    scenarios = query.order_by(CustomScenario.created_at.desc()).all()

    return jsonify({
        'success': True,
        'scenarios': [s.to_dict() for s in scenarios]
    })


@bp.route('/scenarios', methods=['POST'])
def create_custom_scenario():
    """Create a new custom scenario."""
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400

    # Validate required fields
    title = data.get('title', '').strip()
    topic = data.get('topic', '').strip()
    scenario_type = data.get('scenario_type', 'practice')

    if not title:
        return jsonify({
            'success': False,
            'error': 'Title is required'
        }), 400

    if not topic:
        return jsonify({
            'success': False,
            'error': 'Topic is required'
        }), 400

    if scenario_type not in ['practice', 'behavioral']:
        return jsonify({
            'success': False,
            'error': 'Invalid scenario type'
        }), 400

    # Set default speech type based on scenario type
    speech_type = data.get('speech_type', '').strip()
    if not speech_type:
        speech_type = 'Behavioral Interview Response' if scenario_type == 'behavioral' else 'Custom Practice'

    # Create the scenario
    scenario = CustomScenario(
        user_id=user_id,
        scenario_type=scenario_type,
        title=title,
        description=None,
        topic=topic,
        speech_type=speech_type
    )

    db.session.add(scenario)
    db.session.commit()

    return jsonify({
        'success': True,
        'scenario': scenario.to_dict()
    }), 201


@bp.route('/scenarios/<int:scenario_id>', methods=['DELETE'])
def delete_custom_scenario(scenario_id):
    """Delete a custom scenario."""
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    scenario = CustomScenario.query.filter_by(id=scenario_id, user_id=user_id).first()

    if not scenario:
        return jsonify({
            'success': False,
            'error': 'Scenario not found'
        }), 404

    db.session.delete(scenario)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Scenario deleted'
    })


@bp.route('/scenarios/<int:scenario_id>', methods=['PUT'])
def update_custom_scenario(scenario_id):
    """Update a custom scenario."""
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    scenario = CustomScenario.query.filter_by(id=scenario_id, user_id=user_id).first()

    if not scenario:
        return jsonify({
            'success': False,
            'error': 'Scenario not found'
        }), 404

    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400

    # Update fields if provided
    if 'title' in data:
        scenario.title = data['title'].strip()
    if 'description' in data:
        scenario.description = data['description'].strip() or None
    if 'topic' in data:
        scenario.topic = data['topic'].strip()
    if 'speech_type' in data:
        scenario.speech_type = data['speech_type'].strip()

    db.session.commit()

    return jsonify({
        'success': True,
        'scenario': scenario.to_dict()
    })


__all__ = ['bp']
