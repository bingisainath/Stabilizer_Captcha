import random
import math
import os
import logging
import secrets
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, session, redirect, url_for

try:
    import numpy as np
except ImportError:
    np = None

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, '../logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

active_sessions = {}
SESSION_TIMEOUT = 600

# CONFIGURATION
FRAME_COUNT = 300 # Target is 5 seconds (60fps * 5)
# UPDATED: Minimum frames required to PASS. 
# We allow a small buffer (e.g., 20 frames) for lag/network drop, 
# but they must essentially complete the full duration.
PASS_FRAME_THRESHOLD = FRAME_COUNT - 20 

PERFECT_ANGLE_THRESHOLD = 0.001
MAX_PERFECT_FRAMES = 30
MAX_ATTEMPTS = 3 

def cleanup_expired_sessions():
    now = datetime.now()
    expired = [token for token, data in active_sessions.items() 
               if now - data.get('created', now) > timedelta(seconds=SESSION_TIMEOUT)]
    for token in expired:
        del active_sessions[token]

def lerp(start, end, t):
    return start + (end - start) * t

def generate_smooth_parameter_schedule(min_val, max_val, frame_count, num_keyframes=5):
    keyframe_positions = sorted([0] + random.sample(range(1, frame_count - 1), num_keyframes - 2) + [frame_count - 1])
    keyframe_values = [random.uniform(min_val, max_val) for _ in range(num_keyframes)]
    schedule = []
    keyframe_idx = 0
    for frame in range(frame_count):
        while keyframe_idx < len(keyframe_positions) - 1 and frame >= keyframe_positions[keyframe_idx + 1]:
            keyframe_idx += 1
        if keyframe_idx >= len(keyframe_positions) - 1:
            schedule.append(keyframe_values[-1])
        else:
            start_frame, end_frame = keyframe_positions[keyframe_idx], keyframe_positions[keyframe_idx + 1]
            t = (frame - start_frame) / (end_frame - start_frame) if end_frame != start_frame else 0
            schedule.append(lerp(keyframe_values[keyframe_idx], keyframe_values[keyframe_idx + 1], t))
    return schedule

def generate_force_jolts(frame_count):
    jolts = [0.0] * frame_count
    jolt_interval = random.randint(70, 100)
    for i in range(0, frame_count, jolt_interval):
        jolt_frame = i + random.randint(0, min(20, frame_count - i - 1))
        if jolt_frame < frame_count:
            jolts[jolt_frame] = random.uniform(-0.004, 0.004)
            for decay in range(1, 5):
                if jolt_frame + decay < frame_count:
                    jolts[jolt_frame + decay] = jolts[jolt_frame] * (0.5 ** decay)
    return jolts

def calculate_bot_probability(angle_history):
    """
    Analyzes movement to determine likelihood of being a bot.
    Returns (ai_percent, human_percent)
    """
    if not angle_history or len(angle_history) < 10:
        return 0, 100

    # 1. Reflex Ratio (High = Bot)
    immediate_corrections = 0
    significant_frames = 0
    for i in range(1, len(angle_history) - 1):
        if abs(angle_history[i]) > 0.02:
            significant_frames += 1
            is_correcting = (angle_history[i] > 0 and angle_history[i+1] < angle_history[i]) or \
                            (angle_history[i] < 0 and angle_history[i+1] > angle_history[i])
            if is_correcting:
                immediate_corrections += 1
    
    reflex_ratio = immediate_corrections / significant_frames if significant_frames > 0 else 0

    # 2. Variance (Extremely Low = Bot)
    diffs = [abs(angle_history[i] - angle_history[i-1]) for i in range(1, len(angle_history))]
    mean_diff = sum(diffs)/len(diffs) if diffs else 0
    variance = sum((x - mean_diff)**2 for x in diffs) / len(diffs) if diffs else 0
    
    # Scoring Logic
    ai_score = 0
    
    # Reflex check
    if reflex_ratio > 0.95: ai_score += 90
    elif reflex_ratio > 0.85: ai_score += 60
    elif reflex_ratio > 0.70: ai_score += 30
    
    # Variance check (Dead stillness or perfect linear movement)
    if variance < 1e-9: ai_score += 100
    elif variance < 1e-7: ai_score += 50
    
    # Perfection check
    perfect_frames = sum(1 for a in angle_history if abs(a) < 0.001)
    if perfect_frames > 40: ai_score += 80

    # Cap and calculate
    ai_final = min(100, max(0, ai_score))
    human_final = 100 - ai_final
    
    return ai_final, human_final

# --- ROUTES ---

@app.route('/')
def index():
    session.clear()
    return render_template('login.html')

@app.route('/captcha')
def captcha():
    if session.get('attempts', 0) >= MAX_ATTEMPTS:
        return redirect(url_for('failed_page'))
    return render_template('captcha.html')

@app.route('/success')
def success_page():
    if not session.get('verified', False):
        return redirect(url_for('index'))
    return render_template('success.html')

@app.route('/failed')
def failed_page():
    return render_template('failed.html')

@app.route('/init_stabilizer', methods=['GET'])
def init_stabilizer():
    cleanup_expired_sessions()
    
    if 'attempts' not in session:
        session['attempts'] = 0

    current_attempts = session.get('attempts', 0)
    if current_attempts >= MAX_ATTEMPTS:
        return jsonify({'success': False, 'error': 'MAX_ATTEMPTS_EXCEEDED', 'redirect': '/failed'})

    gravity = generate_smooth_parameter_schedule(0.10, 0.25, FRAME_COUNT, 10)
    length = generate_smooth_parameter_schedule(120.0, 100.0, FRAME_COUNT, 8)
    jolts = generate_force_jolts(FRAME_COUNT)
    token = secrets.token_urlsafe(32)
    
    active_sessions[token] = {'gravity': gravity, 'length': length, 'force_jolts': jolts, 'created': datetime.now()}
    
    return jsonify({
        'success': True,
        'session_token': token,
        'attempts_left': MAX_ATTEMPTS - current_attempts,
        'schedule': {'gravity': gravity, 'length': length, 'force_jolts': jolts}
    })

@app.route('/verify_stability', methods=['POST'])
def verify_stability():
    data = request.get_json()
    if 'attempts' not in session: session['attempts'] = 0
    
    if not data or 'session_token' not in data:
        return jsonify({'success': False, 'verified': False}), 400

    token = data['session_token']
    history = data.get('angle_history', [])
    
    if token not in active_sessions:
        return jsonify({'success': False, 'verified': False, 'message': 'Session Expired'}), 403
    del active_sessions[token]

    # Calculate Metrics regardless of outcome
    ai_pct, human_pct = calculate_bot_probability(history)
    metrics = {'ai': round(ai_pct, 1), 'human': round(human_pct, 1)}

    # Helper for failures
    def fail(msg):
        session['attempts'] += 1
        left = MAX_ATTEMPTS - session['attempts']
        response = {
            'success': True, 
            'verified': False, 
            'attempts_left': left,
            'message': msg,
            'metrics': metrics
        }
        if left <= 0: response['redirect'] = '/failed'
        return jsonify(response)

    # --- UPDATED VALIDATION CHECKS ---
    
    # 1. Survival Check: Must last the FULL duration (minus small buffer)
    if len(history) < PASS_FRAME_THRESHOLD:
        duration_sec = len(history) / 60
        return fail(f'Failed: Lasted {duration_sec:.1f}s / 5.0s')

    # 2. Crash Check: Ensure the final angle wasn't a crash
    # Even if history is long enough, if the last angle is huge, it's a fail
    if len(history) > 0 and abs(history[-1]) > 1.4: # 1.4 is approx failure angle
         return fail('Failed: Reactor crashed at the finish line.')

    # 3. Bot Check
    if ai_pct > 80: 
        return fail('Anomaly: Non-biological movement detected.')

    # Success Case
    session['verified'] = True
    sign_changes = sum(1 for i in range(1, len(history)) if history[i] * history[i-1] < 0)
    max_angle = max(abs(a) for a in history) if history else 0
    
    return jsonify({
        'success': True,
        'verified': True,
        'redirect': '/success',
        'metrics': metrics,
        'stats': {
            'duration': len(history) / 60,
            'max_deviation': math.degrees(max_angle),
            'stability_score': min(100, int(100 * (1 - max_angle / 1.2)))
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)