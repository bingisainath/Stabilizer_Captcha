"""Flask routes and API endpoints."""

import secrets
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template, session, redirect, url_for, current_app

from .verification import (
    generate_smooth_parameter_schedule,
    generate_force_jolts,
    analyze_behavior_pattern
)

main_bp = Blueprint('main', __name__)

active_sessions = {}


def cleanup_expired_sessions():
    now = datetime.now()
    timeout = timedelta(seconds=current_app.config['SESSION_TIMEOUT'])
    
    expired = [
        token for token, data in active_sessions.items() 
        if now - data.get('created', now) > timeout
    ]
    
    for token in expired:
        del active_sessions[token]
        current_app.logger.debug(f"Cleaned up expired session: {token[:8]}...")


@main_bp.route('/')
def index():
    session.clear()
    return render_template('login.html')


@main_bp.route('/captcha')
def captcha():
    max_attempts = current_app.config['MAX_ATTEMPTS']
    
    if session.get('attempts', 0) >= max_attempts:
        current_app.logger.warning("User exceeded max attempts, redirecting to failed page")
        return redirect(url_for('main.failed_page'))
    
    return render_template('captcha.html')


@main_bp.route('/success')
def success_page():
    if not session.get('verified', False):
        current_app.logger.warning("Unauthorized access attempt to success page")
        return redirect(url_for('main.index'))
    
    return render_template('success.html')


@main_bp.route('/failed')
def failed_page():
    return render_template('failed.html')


@main_bp.route('/init_stabilizer', methods=['GET'])
def init_stabilizer():
    cleanup_expired_sessions()
    
    if 'attempts' not in session:
        session['attempts'] = 0
    
    max_attempts = current_app.config['MAX_ATTEMPTS']
    current_attempts = session.get('attempts', 0)
    
    if current_attempts >= max_attempts:
        current_app.logger.warning("Max attempts exceeded")
        return jsonify({
            'success': False,
            'error': 'MAX_ATTEMPTS_EXCEEDED',
            'redirect': '/failed'
        })
    
    frame_count = current_app.config['FRAME_COUNT']
    
    gravity = generate_smooth_parameter_schedule(0.10, 0.25, frame_count, 10)
    length = generate_smooth_parameter_schedule(120.0, 100.0, frame_count, 8)
    jolts = generate_force_jolts(frame_count)
    
    token = secrets.token_urlsafe(32)
    
    active_sessions[token] = {
        'gravity': gravity,
        'length': length,
        'force_jolts': jolts,
        'created': datetime.now()
    }
    
    current_app.logger.info(f"Session initialized: {token[:8]}... | Attempts left: {max_attempts - current_attempts}")
    
    return jsonify({
        'success': True,
        'session_token': token,
        'attempts_left': max_attempts - current_attempts,
        'schedule': {
            'gravity': gravity,
            'length': length,
            'force_jolts': jolts
        }
    })


@main_bp.route('/verify_stability', methods=['POST'])
def verify_stability():
    """
    Verify CAPTCHA completion and analyze behavior patterns.
    
    Expected JSON payload:
        {
            "session_token": str,
            "angle_history": list[float],
            "cart_history": list[float]
        }
    
    Returns:
        JSON response with verification result
    """
    data = request.get_json()
    
    if 'attempts' not in session:
        session['attempts'] = 0
    
    if not data or 'session_token' not in data:
        current_app.logger.error("Invalid verification request: missing data")
        return jsonify({'success': False, 'verified': False}), 400
    
    token = data['session_token']
    angle_history = data.get('angle_history', [])
    cart_history = data.get('cart_history', [])
    
    if token not in active_sessions:
        current_app.logger.warning(f"Invalid or expired session token: {token[:8]}...")
        return jsonify({
            'success': False,
            'verified': False,
            'message': 'Session Expired'
        }), 403
    
    del active_sessions[token]
    
    if not cart_history:
        cart_history = [0] * len(angle_history)
    
    ai_pct, human_pct, details = analyze_behavior_pattern(angle_history, cart_history)
    
    current_app.logger.info("="*50)
    current_app.logger.info(f"VERIFICATION ATTEMPT - Session: {token[:8]}...")
    current_app.logger.info(f"PROBABILITY :: Human: {human_pct}% | Bot: {ai_pct}%")
    current_app.logger.info(f"METRICS     :: Lag: {details.get('estimated_lag')}f | "
                           f"Roughness: {details.get('input_roughness')} | "
                           f"Speed: {details.get('avg_speed')}")
    current_app.logger.info(f"FLAGS       :: {details.get('reasons')}")
    current_app.logger.info("="*50)
    
    metrics = {
        'ai': round(ai_pct, 1),
        'human': round(human_pct, 1)
    }
    
    def fail(msg):
        session['attempts'] += 1
        max_attempts = current_app.config['MAX_ATTEMPTS']
        left = max_attempts - session['attempts']
        
        current_app.logger.warning(f"FAILED: {msg} (Attempts left: {left})")
        
        response = {
            'success': True,
            'verified': False,
            'attempts_left': left,
            'message': msg,
            'metrics': metrics
        }
        
        if left <= 0:
            response['redirect'] = '/failed'
        
        return jsonify(response)
    
    frame_threshold = current_app.config['PASS_FRAME_THRESHOLD']
    if len(angle_history) < frame_threshold:
        duration_sec = len(angle_history) / 60
        return fail(f'Failed: Lasted {duration_sec:.1f}s / 5.0s')
    
    if len(angle_history) > 0 and abs(angle_history[-1]) > 1.4:
        return fail('Failed: Reactor crashed at the finish line.')
    
    if ai_pct >= human_pct:
        return fail('Try again (Likely Bot)')
    
    session['verified'] = True
    
    import math
    max_angle = max(abs(a) for a in angle_history) if angle_history else 0
    
    current_app.logger.info("SUCCESS: User verified as Human.")
    
    return jsonify({
        'success': True,
        'verified': True,
        'redirect': '/success',
        'metrics': metrics,
        'stats': {
            'duration': len(angle_history) / 60,
            'max_deviation': math.degrees(max_angle),
            'stability_score': min(100, int(100 * (1 - max_angle / 1.2)))
        }
    })