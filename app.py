"""
This is the main Flask backend server. It handles user sessions, serves the web pages, and implements the core security logic. It generates the random "chaos schedules" (physics parameters) and contains the verify_stability endpoint that analyzes user behavior (reaction time, input roughness) to distinguish humans from bots.
Authors: Jai Mangesh Nagle (jnagle)
"""

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, '../logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

active_sessions = {}
SESSION_TIMEOUT = 600

FRAME_COUNT = 300 
PASS_FRAME_THRESHOLD = FRAME_COUNT - 20 
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


def analyze_behavior_pattern(angle_history, cart_history):
    if not angle_history or len(angle_history) < 20 or not cart_history:
        return 0, 100, {"error": "insufficient_data"}

    cart_velocity = [cart_history[i] - cart_history[i-1] for i in range(1, len(cart_history))]

    cart_accel = [cart_velocity[i] - cart_velocity[i-1] for i in range(1, len(cart_velocity))]


    input_roughness = sum(abs(a) for a in cart_accel) / len(cart_accel) if cart_accel else 0

    best_correlation = -1
    estimated_lag = 0
    
    def normalize(data):
        mean = sum(data) / len(data)
        std = (sum((x - mean) ** 2 for x in data) / len(data)) ** 0.5
        if std == 0: return [0] * len(data)
        return [(x - mean) / std for x in data]

    sample_size = min(len(angle_history), len(cart_velocity)) - 10
    if sample_size > 50:
        angle_sample = normalize(angle_history[10:10+sample_size])
        vel_sample = normalize(cart_velocity[10:10+sample_size])

        for lag in range(0, 25):
            dot_product = 0
            count = 0
            for i in range(len(angle_sample) - lag):
                dot_product += angle_sample[i] * vel_sample[i + lag]
                count += 1
            
            corr = dot_product / count if count > 0 else 0
            
            if corr > best_correlation:
                best_correlation = corr
                estimated_lag = lag

    total_distance = sum(abs(v) for v in cart_velocity)
    
    bot_score = 0
    reasons = []

    if input_roughness < 0.4:
        bot_score += 60
        reasons.append(f"Mechanical Smoothness (Roughness: {input_roughness:.2f})")
    elif input_roughness > 1.2:
        bot_score += 30
        reasons.append("Excessive Input Noise / Artificial Jitter")

    if estimated_lag > 5:
        bot_score += 50
        reasons.append(f"High Latency Response (Lag: {estimated_lag}f)")
    elif estimated_lag < 1:
        bot_score += 50
        reasons.append(f"Predictive/Instant Reaction (Lag: {estimated_lag}f)")

    avg_speed = total_distance / len(cart_velocity)
    
    if avg_speed < 0.2:
        bot_score += 40
        reasons.append(f"Unnatural Efficiency (Speed: {avg_speed:.2f})")
    elif avg_speed > 1.5:
        bot_score += 40
        reasons.append(f"Erratic/High Speed (Speed: {avg_speed:.2f})")
        
    final_ai_prob = min(100, max(0, bot_score))
    final_human_prob = 100 - final_ai_prob

    details = {
        "input_roughness": round(input_roughness, 3),
        "estimated_lag": estimated_lag,
        "avg_speed": round(avg_speed, 3),
        "reasons": reasons
    }

    return final_ai_prob, final_human_prob, details


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
    angle_history = data.get('angle_history', [])
    cart_history = data.get('cart_history', []) 
    
    if token not in active_sessions:
        return jsonify({'success': False, 'verified': False, 'message': 'Session Expired'}), 403
    del active_sessions[token]

    if not cart_history:
        cart_history = [0] * len(angle_history)
    
    ai_pct, human_pct, details = analyze_behavior_pattern(angle_history, cart_history)
    
    logger.info("="*50)
    logger.info(f"VERIFICATION ATTEMPT - Session: {token[:8]}...")
    logger.info(f"PROBABILITY :: Human: {human_pct}% | Bot: {ai_pct}%")
    logger.info(f"METRICS     :: Lag: {details.get('estimated_lag')}f | Roughness: {details.get('input_roughness')} | Speed: {details.get('avg_speed')}")
    logger.info(f"FLAGS       :: {details.get('reasons')}")
    logger.info("="*50)

    metrics = {'ai': round(ai_pct, 1), 'human': round(human_pct, 1)}

    def fail(msg):
        session['attempts'] += 1
        left = MAX_ATTEMPTS - session['attempts']
        
        logger.warning(f"FAILED: {msg} (Attempts left: {left})")
        
        response = {
            'success': True, 
            'verified': False, 
            'attempts_left': left,
            'message': msg,
            'metrics': metrics
        }
        if left <= 0: response['redirect'] = '/failed'
        return jsonify(response)

    if len(angle_history) < PASS_FRAME_THRESHOLD:
        duration_sec = len(angle_history) / 60
        return fail(f'Failed: Lasted {duration_sec:.1f}s / 5.0s')

    if len(angle_history) > 0 and abs(angle_history[-1]) > 1.4:
         return fail('Failed: Reactor crashed at the finish line.')

    if ai_pct >= human_pct: 
        return fail('Try again (Likely Bot)')

    session['verified'] = True
    max_angle = max(abs(a) for a in angle_history) if angle_history else 0
    
    logger.info("SUCCESS: User verified as Human.")

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)