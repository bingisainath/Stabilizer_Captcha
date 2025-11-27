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

# Configure Logger to print to console immediately
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

active_sessions = {}
SESSION_TIMEOUT = 600

# CONFIGURATION
FRAME_COUNT = 300 
# Strict threshold: Must last ~4.7s of the 5s to pass (allow small network/render lag)
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

def calculate_variance(values):
    if not values: return 0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)

# =========================================================
#  BEHAVIORAL ANALYSIS ENGINE
# =========================================================
def analyze_behavior_pattern(angle_history):
    """
    Advanced heuristic analysis of physics data to determine Bot vs Human.
    Returns: (ai_probability, human_probability, details_dict)
    """
    if not angle_history or len(angle_history) < 10:
        return 0, 100, {"error": "insufficient_data"}

    # --- 1. PRE-CALCULATE DERIVATIVES ---
    # Velocity: Change in angle per frame
    velocity = [angle_history[i] - angle_history[i-1] for i in range(1, len(angle_history))]
    
    # --- 2. CALCULATE METRICS ---

    # A. Total Distance (Effort)
    # Bots hold position efficiently (low distance). Humans constantly micro-correct (high distance).
    total_distance = sum(abs(v) for v in velocity)
    
    # B. Micro-Oscillations (PID Shake)
    # PID controllers often flip velocity direction every frame (zigzag).
    velocity_flips = sum(1 for i in range(1, len(velocity)) if velocity[i] * velocity[i-1] < 0)
    flip_ratio = velocity_flips / len(velocity) if len(velocity) > 0 else 0

    # C. Reaction Latency (The "Biological Delay")
    # Bots react in 1 frame. Humans react in 10-20 frames (approx 200ms).
    correction_lags = []
    frames_since_deviation = 0
    
    for i in range(len(angle_history)):
        val = angle_history[i]
        if abs(val) > 0.01: # Threshold for "needs correction"
            frames_since_deviation += 1
            # If velocity opposes angle, they are correcting
            if i > 0 and (val * velocity[i-1] < 0):
                correction_lags.append(frames_since_deviation)
                frames_since_deviation = 0
        else:
            frames_since_deviation = 0
            
    avg_reaction_frames = sum(correction_lags) / len(correction_lags) if correction_lags else 0

    # D. Uniformity (Variance)
    # Deadbots or static scripts have near-zero variance.
    vel_variance = calculate_variance(velocity)

    # --- 3. SCORING LOGIC (0 = Human, 100 = Bot) ---
    bot_score = 0
    reasons = []

    # Check 1: Superhuman Stability (Variance)
    if vel_variance < 1e-7:
        bot_score += 100
        reasons.append("Zero Variance (Static)")
    elif vel_variance < 1e-5:
        bot_score += 40
        reasons.append("Low Variance (Robotic Precision)")

    # Check 2: The "PID Shake" (Flip Ratio)
    # If direction flips > 60% of frames, it's likely a high-frequency PID controller
    if flip_ratio > 0.60:
        bot_score += 50
        reasons.append(f"High Frequency Oscillation ({flip_ratio:.2f})")
    
    # Check 3: Reaction Time
    # If average reaction is < 3 frames (50ms), it's superhuman.
    if avg_reaction_frames < 3 and avg_reaction_frames > 0:
        bot_score += 60
        reasons.append(f"Instant Reaction ({avg_reaction_frames:.1f} frames)")
    
    # Check 4: Efficiency (Total Distance)
    # If they moved the pole VERY little over 5 seconds, it's suspicious.
    if total_distance < 0.5: # Tuned threshold
        bot_score += 30
        reasons.append("Unnatural Efficiency")

    # Final Clamping
    final_ai_prob = min(100, max(0, bot_score))
    final_human_prob = 100 - final_ai_prob

    details = {
        "total_distance": round(total_distance, 4),
        "avg_velocity": round(sum(abs(v) for v in velocity)/len(velocity) if velocity else 0, 5),
        "velocity_flip_ratio": round(flip_ratio, 2),
        "avg_reaction_frames": round(avg_reaction_frames, 1),
        "variance": f"{vel_variance:.2e}",
        "reasons": reasons
    }

    return final_ai_prob, final_human_prob, details

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

    # --- RUN BEHAVIOR ANALYSIS ---
    ai_pct, human_pct, details = analyze_behavior_pattern(history)
    
    # --- LOGGING ---
    logger.info("="*50)
    logger.info(f"VERIFICATION ATTEMPT - Session: {token[:8]}...")
    logger.info(f"PROBABILITY :: Human: {human_pct}% | Bot: {ai_pct}%")
    logger.info(f"METRICS     :: Dist: {details.get('total_distance')} | Reaction: {details.get('avg_reaction_frames')}f | Flips: {details.get('velocity_flip_ratio')}")
    logger.info(f"FLAGS       :: {details.get('reasons')}")
    logger.info("="*50)

    metrics = {'ai': round(ai_pct, 1), 'human': round(human_pct, 1)}

    # Helper for failures
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

    # 1. Survival Check
    if len(history) < PASS_FRAME_THRESHOLD:
        duration_sec = len(history) / 60
        return fail(f'Failed: Lasted {duration_sec:.1f}s / 5.0s')

    # 2. Crash Check (Final Angle)
    if len(history) > 0 and abs(history[-1]) > 1.4:
         return fail('Failed: Reactor crashed at the finish line.')

    # 3. AI Probability Check
    if ai_pct > 80: 
        return fail('Anomaly: Non-biological movement detected.')

    # Success Case
    session['verified'] = True
    sign_changes = sum(1 for i in range(1, len(history)) if history[i] * history[i-1] < 0)
    max_angle = max(abs(a) for a in history) if history else 0
    
    logger.info("SUCCESS: User verified as Human.")

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