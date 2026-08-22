"""Analytics routes for user performance tracking."""
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from app.models import Recording, db
from app.services.auth_service import get_auth_service
import psycopg2
import os
import sys
import hashlib
import json

bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

# Simple in-memory cache with TTL
_analytics_cache = {}
CACHE_TTL_SECONDS = 60  # Cache for 60 seconds


def get_cache_key(user_id, endpoint, params):
    """Generate a cache key from user_id, endpoint, and params."""
    param_str = json.dumps(params, sort_keys=True)
    key = f"{user_id}:{endpoint}:{param_str}"
    return hashlib.md5(key.encode()).hexdigest()


def get_cached(cache_key):
    """Get cached value if not expired."""
    if cache_key in _analytics_cache:
        cached_data, cached_time = _analytics_cache[cache_key]
        if datetime.utcnow() - cached_time < timedelta(seconds=CACHE_TTL_SECONDS):
            return cached_data
        else:
            del _analytics_cache[cache_key]
    return None


def set_cached(cache_key, data):
    """Set cache value with current timestamp."""
    _analytics_cache[cache_key] = (data, datetime.utcnow())


def invalidate_user_cache(user_id):
    """Invalidate all cache entries for a user."""
    keys_to_delete = [k for k in _analytics_cache.keys() if k.startswith(user_id[:8])]
    for k in keys_to_delete:
        del _analytics_cache[k]


def get_db_connection():
    """Get a raw psycopg2 database connection."""
    # Use the exact same approach as evaluation.py which works in production
    db_url = os.getenv('DATABASE_URL')

    if not db_url:
        # Fallback: try Flask config
        print(f"[ANALYTICS] DATABASE_URL not in env, trying Flask config...", file=sys.stderr, flush=True)
        db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI')

    if not db_url:
        print(f"[ANALYTICS] No database URL found!", file=sys.stderr, flush=True)
        return None

    print(f"[ANALYTICS] Connecting with URL: {db_url[:50]}...", file=sys.stderr, flush=True)

    conn = psycopg2.connect(db_url)
    conn.set_session(autocommit=True)
    return conn


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


@bp.route('/overview', methods=['GET'])
def get_analytics_overview():
    """
    Get analytics overview for the authenticated user.

    Returns summary statistics across all recordings.
    """
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Check cache first
    params = dict(request.args)
    cache_key = get_cache_key(user_id, 'overview', params)
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    # Use raw SQL to get recordings (bypasses SQLAlchemy connection issues)
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()

        # First, check how many total recordings exist for this user
        cur.execute("SELECT COUNT(*) FROM recordings WHERE user_id = %s", (user_id,))
        total_count = cur.fetchone()[0]

        # Check how many have scores
        cur.execute("SELECT COUNT(*) FROM recordings WHERE user_id = %s AND score_overall IS NOT NULL", (user_id,))
        scored_count = cur.fetchone()[0]

        print(f"[ANALYTICS] user={user_id[:8]}... total_recordings={total_count}, with_scores={scored_count}", file=sys.stderr, flush=True)

        cur.execute("""
            SELECT id, score_overall, score_content, score_organization,
                   score_delivery, score_language, duration, recording_mode,
                   language, created_at
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL
            ORDER BY created_at ASC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ANALYTICS ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    if not rows:
        return jsonify({
            'success': True,
            'data': {
                'total_recordings': 0,
                'total_practice_time': 0,
                'average_score': None,
                'highest_score': None,
                'lowest_score': None,
                'score_trend': None,
                'category_averages': {
                    'content': None,
                    'organization': None,
                    'delivery': None,
                    'language': None
                },
                'mode_breakdown': {
                    'standard': 0,
                    'behavioral': 0,
                    'improvement': 0
                },
                'language_breakdown': {},
                'recent_improvement': None
            }
        })

    # Column indices: 0=id, 1=score_overall, 2=score_content, 3=score_organization,
    # 4=score_delivery, 5=score_language, 6=duration, 7=recording_mode, 8=language, 9=created_at

    # Calculate statistics
    scores = [r[1] for r in rows if r[1] is not None]
    total_duration = sum(r[6] or 0 for r in rows)

    # Category averages
    content_scores = [r[2] for r in rows if r[2] is not None]
    org_scores = [r[3] for r in rows if r[3] is not None]
    delivery_scores = [r[4] for r in rows if r[4] is not None]
    lang_scores = [r[5] for r in rows if r[5] is not None]

    # Mode breakdown
    mode_counts = {'standard': 0, 'behavioral': 0, 'improvement': 0}
    for r in rows:
        mode = r[7] or 'standard'
        if mode in mode_counts:
            mode_counts[mode] += 1

    # Language breakdown
    lang_counts = {}
    for r in rows:
        lang = r[8] or 'en'
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    # Score trend (compare last 5 to previous 5) - rows already sorted by created_at ASC
    if len(rows) >= 10:
        recent_5 = [r[1] for r in rows[-5:] if r[1]]
        previous_5 = [r[1] for r in rows[-10:-5] if r[1]]
        if recent_5 and previous_5:
            score_trend = sum(recent_5) / len(recent_5) - sum(previous_5) / len(previous_5)
        else:
            score_trend = None
    elif len(rows) >= 2:
        # Simple comparison of last vs first
        first_score = rows[0][1]
        last_score = rows[-1][1]
        score_trend = last_score - first_score if first_score and last_score else None
    else:
        score_trend = None

    response_data = {
        'success': True,
        'data': {
            'total_recordings': len(rows),
            'total_duration': round(total_duration, 1),  # in seconds (frontend divides by 60)
            'average_score': round(sum(scores) / len(scores), 1) if scores else None,
            'highest_score': max(scores) if scores else None,
            'lowest_score': min(scores) if scores else None,
            'score_trend': round(score_trend, 1) if score_trend is not None else None,
            'avg_content': round(sum(content_scores) / len(content_scores), 1) if content_scores else None,
            'avg_organization': round(sum(org_scores) / len(org_scores), 1) if org_scores else None,
            'avg_delivery': round(sum(delivery_scores) / len(delivery_scores), 1) if delivery_scores else None,
            'avg_language': round(sum(lang_scores) / len(lang_scores), 1) if lang_scores else None,
            'mode_distribution': mode_counts,
            'language_breakdown': lang_counts,
            'recent_improvement': score_trend
        }
    }
    set_cached(cache_key, response_data)
    return jsonify(response_data)


@bp.route('/scores', methods=['GET'])
def get_score_history():
    """
    Get score history for charts.

    Query params:
    - period: 'day', 'week', 'month', 'all' (default: 'all')
    - mode: 'all', 'standard', 'behavioral', 'improvement' (default: 'all')
    - language: language code or 'all' (default: 'all')
    """
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Check cache first
    params = dict(request.args)
    cache_key = get_cache_key(user_id, 'scores', params)
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    period = request.args.get('period', 'all')
    mode = request.args.get('mode', 'all')
    language = request.args.get('language', 'all')

    # Use raw SQL
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()

        # Build SQL with optional filters
        sql = """
            SELECT id, score_overall, score_content, score_organization,
                   score_delivery, score_language, topic, recording_mode,
                   language, duration, created_at
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL
        """
        params = [user_id]

        # Apply period filter
        now = datetime.utcnow()
        if period == 'day':
            sql += " AND created_at >= %s"
            params.append(now - timedelta(days=1))
        elif period == 'week':
            sql += " AND created_at >= %s"
            params.append(now - timedelta(weeks=1))
        elif period == 'month':
            sql += " AND created_at >= %s"
            params.append(now - timedelta(days=30))

        # Apply mode filter
        if mode != 'all':
            sql += " AND recording_mode = %s"
            params.append(mode)

        # Apply language filter
        if language != 'all':
            sql += " AND language = %s"
            params.append(language)

        sql += " ORDER BY created_at ASC"

        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ANALYTICS ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    # Format data for charts
    # Columns: 0=id, 1=score_overall, 2=score_content, 3=score_organization,
    # 4=score_delivery, 5=score_language, 6=topic, 7=recording_mode, 8=language, 9=duration, 10=created_at
    score_data = []
    for r in rows:
        topic = r[6]
        score_data.append({
            'id': r[0],
            'date': r[10].isoformat() if r[10] else None,
            'timestamp': int(r[10].timestamp() * 1000) if r[10] else 0,
            'score_overall': r[1],
            'score_content': r[2],
            'score_organization': r[3],
            'score_delivery': r[4],
            'score_language': r[5],
            'topic': topic[:50] + '...' if topic and len(topic) > 50 else topic,
            'mode': r[7],
            'language': r[8],
            'duration': r[9]
        })

    response_data = {
        'success': True,
        'data': {
            'scores': score_data,
            'count': len(score_data)
        }
    }
    set_cached(cache_key, response_data)
    return jsonify(response_data)


@bp.route('/trends', methods=['GET'])
def get_trends():
    """
    Get aggregated trends data.

    Query params:
    - period: 'week', 'month', '3months', 'year' (default: 'month')
    - group_by: 'day', 'week' (default: 'day')
    """
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Check cache first
    cache_params = dict(request.args)
    cache_key = get_cache_key(user_id, 'trends', cache_params)
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    period = request.args.get('period', 'month')
    group_by = request.args.get('group_by', 'day')

    # Determine date range
    now = datetime.utcnow()
    if period == 'week':
        start_date = now - timedelta(weeks=1)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == '3months':
        start_date = now - timedelta(days=90)
    elif period == 'year':
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)

    # Use raw SQL
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, score_overall, score_content, score_organization,
                   score_delivery, score_language, duration, created_at
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL AND created_at >= %s
            ORDER BY created_at ASC
        """, (user_id, start_date))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ANALYTICS ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    # Column indices: 0=id, 1=score_overall, 2=score_content, 3=score_organization,
    # 4=score_delivery, 5=score_language, 6=duration, 7=created_at

    # Group by day or week
    trends = {}
    for r in rows:
        created_at = r[7]
        if group_by == 'week':
            key = created_at.strftime('%Y-W%U')
        else:
            key = created_at.strftime('%Y-%m-%d')

        if key not in trends:
            trends[key] = {
                'date': key,
                'scores': [],
                'content_scores': [],
                'org_scores': [],
                'delivery_scores': [],
                'lang_scores': [],
                'count': 0,
                'total_duration': 0
            }

        if r[1]:
            trends[key]['scores'].append(r[1])
        if r[2]:
            trends[key]['content_scores'].append(r[2])
        if r[3]:
            trends[key]['org_scores'].append(r[3])
        if r[4]:
            trends[key]['delivery_scores'].append(r[4])
        if r[5]:
            trends[key]['lang_scores'].append(r[5])
        trends[key]['count'] += 1
        trends[key]['total_duration'] += r[6] or 0

    # Calculate averages
    trend_data = []
    for key, data in sorted(trends.items()):
        trend_data.append({
            'date': data['date'],
            'avg_score': round(sum(data['scores']) / len(data['scores']), 1) if data['scores'] else None,
            'avg_content': round(sum(data['content_scores']) / len(data['content_scores']), 1) if data['content_scores'] else None,
            'avg_organization': round(sum(data['org_scores']) / len(data['org_scores']), 1) if data['org_scores'] else None,
            'avg_delivery': round(sum(data['delivery_scores']) / len(data['delivery_scores']), 1) if data['delivery_scores'] else None,
            'avg_language': round(sum(data['lang_scores']) / len(data['lang_scores']), 1) if data['lang_scores'] else None,
            'recording_count': data['count'],
            'practice_time': round(data['total_duration'] / 60, 1)  # minutes
        })

    response_data = {
        'success': True,
        'data': {
            'data': trend_data,  # nested so frontend unwrapper works correctly
            'period': period,
            'group_by': group_by
        }
    }
    set_cached(cache_key, response_data)
    return jsonify(response_data)


@bp.route('/comparison', methods=['GET'])
def get_category_comparison():
    """
    Get category score comparison over time.

    Returns data for radar/spider charts comparing category performance.
    """
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Check cache first
    cache_params = dict(request.args)
    cache_key = get_cache_key(user_id, 'comparison', cache_params)
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    # Use raw SQL
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, score_content, score_organization, score_delivery, score_language, created_at
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL
            ORDER BY created_at ASC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ANALYTICS ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    # Column indices: 0=id, 1=score_content, 2=score_organization, 3=score_delivery, 4=score_language, 5=created_at

    if len(rows) < 2:
        return jsonify({
            'success': True,
            'data': {
                'current': None,
                'previous': None,
                'all_time': None
            }
        })

    # Calculate all-time averages
    all_content = [r[1] for r in rows if r[1]]
    all_org = [r[2] for r in rows if r[2]]
    all_delivery = [r[3] for r in rows if r[3]]
    all_lang = [r[4] for r in rows if r[4]]

    all_time = {
        'content': round(sum(all_content) / len(all_content), 1) if all_content else None,
        'organization': round(sum(all_org) / len(all_org), 1) if all_org else None,
        'delivery': round(sum(all_delivery) / len(all_delivery), 1) if all_delivery else None,
        'language': round(sum(all_lang) / len(all_lang), 1) if all_lang else None
    }

    # Split into halves for comparison
    mid = len(rows) // 2
    first_half = rows[:mid]
    second_half = rows[mid:]

    def calc_averages(recs):
        content = [r[1] for r in recs if r[1]]
        org = [r[2] for r in recs if r[2]]
        delivery = [r[3] for r in recs if r[3]]
        lang = [r[4] for r in recs if r[4]]
        return {
            'content': round(sum(content) / len(content), 1) if content else None,
            'organization': round(sum(org) / len(org), 1) if org else None,
            'delivery': round(sum(delivery) / len(delivery), 1) if delivery else None,
            'language': round(sum(lang) / len(lang), 1) if lang else None
        }

    # Return flat structure with avg_ prefix for frontend compatibility
    response_data = {
        'success': True,
        'data': {
            'avg_content': all_time['content'],
            'avg_organization': all_time['organization'],
            'avg_delivery': all_time['delivery'],
            'avg_language': all_time['language'],
            'current': calc_averages(second_half),
            'previous': calc_averages(first_half),
            'all_time': all_time
        }
    }
    set_cached(cache_key, response_data)
    return jsonify(response_data)


@bp.route('/top-recordings', methods=['GET'])
def get_top_recordings():
    """Get top and bottom performing recordings."""
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Check cache first
    cache_params = dict(request.args)
    cache_key = get_cache_key(user_id, 'top-recordings', cache_params)
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    limit = request.args.get('limit', 5, type=int)

    # Use raw SQL
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()

        # Top recordings (highest scores)
        cur.execute("""
            SELECT id, topic, score_overall, recording_mode, created_at, duration
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL
            ORDER BY score_overall DESC
            LIMIT %s
        """, (user_id, limit))
        top_rows = cur.fetchall()

        # Bottom recordings (lowest scores)
        cur.execute("""
            SELECT id, topic, score_overall, recording_mode, created_at, duration
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL
            ORDER BY score_overall ASC
            LIMIT %s
        """, (user_id, limit))
        bottom_rows = cur.fetchall()

        # Most recent recordings
        cur.execute("""
            SELECT id, topic, score_overall, recording_mode, created_at, duration
            FROM recordings
            WHERE user_id = %s AND score_overall IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        recent_rows = cur.fetchall()

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ANALYTICS ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    # Column indices: 0=id, 1=topic, 2=score_overall, 3=recording_mode, 4=created_at, 5=duration

    def format_recording(r):
        topic = r[1]
        return {
            'id': r[0],
            'topic': topic[:60] + '...' if topic and len(topic) > 60 else topic,
            'score_overall': r[2],
            'recording_mode': r[3],
            'created_at': r[4].isoformat() if r[4] else None,
            'duration': r[5]
        }

    response_data = {
        'success': True,
        'data': {
            'best': [format_recording(r) for r in top_rows],
            'bottom': [format_recording(r) for r in bottom_rows],
            'recent': [format_recording(r) for r in recent_rows]
        }
    }
    set_cached(cache_key, response_data)
    return jsonify(response_data)


@bp.route('/streaks', methods=['GET'])
def get_practice_streaks():
    """Get practice streak information."""
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Check cache first
    cache_key = get_cache_key(user_id, 'streaks', {})
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)

    # Use raw SQL
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT created_at
            FROM recordings
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ANALYTICS ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    if not rows:
        return jsonify({
            'success': True,
            'data': {
                'current_streak': 0,
                'longest_streak': 0,
                'total_practice_days': 0,
                'last_practice_date': None
            }
        })

    # Get unique practice dates
    practice_dates = set()
    for r in rows:
        if r[0]:
            practice_dates.add(r[0].date())

    sorted_dates = sorted(practice_dates, reverse=True)

    # Calculate current streak
    current_streak = 0
    today = datetime.utcnow().date()

    for i, date in enumerate(sorted_dates):
        expected = today - timedelta(days=i)
        if date == expected or (i == 0 and date == today - timedelta(days=1)):
            current_streak += 1
            if i == 0 and date == today - timedelta(days=1):
                # Adjust for starting from yesterday
                today = date
        else:
            break

    # Calculate longest streak
    longest_streak = 1
    current_run = 1
    sorted_dates_asc = sorted(practice_dates)

    for i in range(1, len(sorted_dates_asc)):
        if (sorted_dates_asc[i] - sorted_dates_asc[i-1]).days == 1:
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            current_run = 1

    response_data = {
        'success': True,
        'data': {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'total_practice_days': len(practice_dates),
            'last_practice_date': sorted_dates[0].isoformat() if sorted_dates else None
        }
    }
    set_cached(cache_key, response_data)
    return jsonify(response_data)


@bp.route('/backfill-scores', methods=['POST'])
def backfill_scores():
    """
    Backfill scores for existing recordings that don't have extracted scores.
    Admin/utility endpoint.
    """
    user_id = get_user_id_from_token(request)

    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Authentication required'
        }), 401

    # Use raw SQL to get and update recordings
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()

        # Get recordings without scores
        cur.execute("""
            SELECT id, feedback, topic, is_repeat, recording_mode
            FROM recordings
            WHERE user_id = %s AND feedback IS NOT NULL AND score_overall IS NULL
        """, (user_id,))
        rows = cur.fetchall()

        updated = 0
        for row in rows:
            rec_id, feedback, topic, is_repeat, rec_mode = row

            # Extract scores from feedback
            scores = Recording.extract_scores_from_feedback(feedback)

            # Determine recording mode if not set
            if not rec_mode:
                if is_repeat:
                    rec_mode = 'improvement'
                elif topic and topic.startswith('BEHAVIORAL:'):
                    rec_mode = 'behavioral'
                else:
                    rec_mode = 'standard'

            # Update the record
            cur.execute("""
                UPDATE recordings
                SET score_overall = %s, score_content = %s, score_organization = %s,
                    score_delivery = %s, score_language = %s, recording_mode = %s
                WHERE id = %s
            """, (
                scores['score_overall'], scores['score_content'], scores['score_organization'],
                scores['score_delivery'], scores['score_language'], rec_mode, rec_id
            ))
            updated += 1

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[BACKFILL ERROR] {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({
        'success': True,
        'message': f'Backfilled scores for {updated} recordings'
    })


__all__ = ['bp']
