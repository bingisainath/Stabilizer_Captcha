"""
Production Reactor Stabilizer CAPTCHA
"""

import random
import math
import os
import logging
import secrets
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template
from functools import wraps

try:
    import numpy as np
except ImportError:
    np = None

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, '../logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'captcha.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Active sessions with expiry
active_sessions = {}
SESSION_TIMEOUT = 600  # 10 minutes

# Configuration
FRAME_COUNT = 300
MIN_SURVIVAL_FRAMES = 150
PERFECT_ANGLE_THRESHOLD = 0.001
MAX_PERFECT_FRAMES = 30


def cleanup_expired_sessions():
    """Remove expired sessions"""
    now = datetime.now()
    expired = [token for token, data in active_sessions.items() 
               if now - data.get('created', now) > timedelta(seconds=SESSION_TIMEOUT)]
    for token in expired:
        del active_sessions[token]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")


def lerp(start: float, end: float, t: float) -> float:
    return start + (end - start) * t


def generate_smooth_parameter_schedule(min_val: float, max_val: float, 
                                      frame_count: int, num_keyframes: int = 5) -> list:
    keyframe_positions = sorted([0] + random.sample(range(1, frame_count - 1), 
                                                     num_keyframes - 2) + [frame_count - 1])
    keyframe_values = [random.uniform(min_val, max_val) for _ in range(num_keyframes)]
    
    schedule = []
    keyframe_idx = 0
    
    for frame in range(frame_count):
        while keyframe_idx < len(keyframe_positions) - 1 and \
              frame >= keyframe_positions[keyframe_idx + 1]:
            keyframe_idx += 1
        
        if keyframe_idx >= len(keyframe_positions) - 1:
            schedule.append(keyframe_values[-1])
        else:
            start_frame = keyframe_positions[keyframe_idx]
            end_frame = keyframe_positions[keyframe_idx + 1]
            t = (frame - start_frame) / (end_frame - start_frame) if end_frame != start_frame else 0
            
            start_val = keyframe_values[keyframe_idx]
            end_val = keyframe_values[keyframe_idx + 1]
            schedule.append(lerp(start_val, end_val, t))
    
    return schedule


def generate_force_jolts(frame_count: int) -> list:
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
    if len(values) == 0:
        return 0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)


def calculate_mean(values):
    return sum(values) / len(values) if len(values) > 0 else 0


@app.route('/')
def index():
    return render_template('login.html')


@app.route('/captcha')
def captcha():
    return render_template('captcha.html')


@app.route('/init_stabilizer', methods=['GET'])
def init_stabilizer():
    try:
        cleanup_expired_sessions()
        
        gravity_schedule = generate_smooth_parameter_schedule(0.10, 0.25, FRAME_COUNT, 10)
        length_schedule = generate_smooth_parameter_schedule(120.0, 100.0, FRAME_COUNT, 8)
        force_jolts = generate_force_jolts(FRAME_COUNT)
        
        session_token = secrets.token_urlsafe(32)
        
        active_sessions[session_token] = {
            'gravity': gravity_schedule,
            'length': length_schedule,
            'force_jolts': force_jolts,
            'created': datetime.now()
        }
        
        logger.info(f"Session created: {session_token[:8]}...")
        
        return jsonify({
            'success': True,
            'session_token': session_token,
            'frame_count': FRAME_COUNT,
            'target_fps': 60,
            'schedule': {
                'gravity': gravity_schedule,
                'length': length_schedule,
                'force_jolts': force_jolts
            },
            'config': {
                'canvas_width': 600,
                'canvas_height': 400,
                'cart_width': 60,
                'cart_height': 20,
                'fail_angle': 1.4,
                'success_frames': FRAME_COUNT
            }
        })
    except Exception as e:
        logger.error(f"Error initializing: {e}")
        return jsonify({'success': False, 'error': 'Initialization failed'}), 500


@app.route('/verify_stability', methods=['POST'])
def verify_stability():
    try:
        data = request.get_json()
        
        # 1. Basic Validation
        if not data or 'angle_history' not in data or 'session_token' not in data:
            logger.warning("Missing required data in verification")
            return jsonify({
                'success': False,
                'verified': False,
                'message': 'SYSTEM ERROR: Missing required data.'
            }), 400
        
        session_token = data['session_token']
        angle_history = data['angle_history']
        
        # 2. Session Validation
        cleanup_expired_sessions()
        
        if session_token not in active_sessions:
            logger.warning(f"Invalid session token: {session_token[:8]}...")
            return jsonify({
                'success': False,
                'verified': False,
                'message': 'SYSTEM ERROR: Invalid or expired session.'
            }), 403
        
        # Consume the token (One-time use)
        del active_sessions[session_token]
        
        # 3. Survival Check (Did they last 5 seconds?)
        if len(angle_history) < MIN_SURVIVAL_FRAMES:
            logger.info(f"Session failed: Too short ({len(angle_history)} frames)")
            return jsonify({
                'success': True,
                'verified': False,
                'message': f'STABILIZATION FAILED: Reactor unstable after {len(angle_history) / 60:.1f} seconds.'
            })
        
        # 4. Variance Check (Anti-Static / Dead Bot)
        # Bots that crash or hold perfectly still have weird variance profiles.
        if len(angle_history) >= 2:
            angle_changes = [abs(angle_history[i] - angle_history[i-1]) 
                           for i in range(1, len(angle_history))]
            
            if np is not None:
                variance = np.var(angle_changes)
                mean_change = np.mean(angle_changes)
            else:
                variance = calculate_variance(angle_changes)
                mean_change = calculate_mean(angle_changes)
            
            if variance < 1e-10 and mean_change < 1e-8:
                logger.info("Session failed: Pattern too uniform")
                return jsonify({
                    'success': True,
                    'verified': False,
                    'message': 'ANOMALY DETECTED: Input pattern too uniform.'
                })
        
        # 5. Perfection Check (Anti-Bot)
        # Humans cannot hold the angle at exactly 0.000 for long periods.
        perfect_count = sum(1 for angle in angle_history if abs(angle) < PERFECT_ANGLE_THRESHOLD)
        if perfect_count > MAX_PERFECT_FRAMES:
            logger.info("Session failed: Too precise")
            return jsonify({
                'success': True,
                'verified': False,
                'message': 'ANOMALY DETECTED: Impossibly precise stabilization detected.'
            })

        # 6. The "Reflex Trap" (Anti-PID Check) - NEW
        # We calculate the "Reflex Ratio".
        # PID bots correct errors frame-by-frame (60Hz micro-corrections).
        # Humans correct in "ballistic bursts" (wait for error -> push -> wait).
        
        immediate_corrections = 0
        significant_frames = 0
        
        # Look at frames where the pole was actually leaning (ignore the stable center)
        for i in range(1, len(angle_history) - 1):
            current_angle = angle_history[i]
            next_angle = angle_history[i+1]
            
            if abs(current_angle) > 0.02: # Only check if there's a real tilt
                significant_frames += 1
                
                # Check if the movement was an IMMEDIATE correction towards zero
                # If Angle > 0 (Right) AND Next < Current (Moving Left) -> Correction
                # If Angle < 0 (Left) AND Next > Current (Moving Right) -> Correction
                is_correcting = (current_angle > 0 and next_angle < current_angle) or \
                                (current_angle < 0 and next_angle > current_angle)
                
                if is_correcting:
                    immediate_corrections += 1

        if significant_frames > 30:
            reflex_ratio = immediate_corrections / significant_frames
            logger.info(f"Reflex Analysis: {reflex_ratio:.3f} (Frames: {significant_frames})")
            
            # PID bots score > 0.95 (they never let it slide). 
            # Humans usually score 0.60 - 0.85 (we let it slide, then catch it).
            if reflex_ratio > 0.92: 
                logger.info(f"Session failed: Superhuman reflexes ({reflex_ratio:.2f})")
                return jsonify({
                    'success': True,
                    'verified': False,
                    'message': 'ANOMALY DETECTED: Reflexes exceed biological limits.'
                })

        # 7. Verification Success
        sign_changes = sum(1 for i in range(1, len(angle_history)) 
                          if angle_history[i] * angle_history[i-1] < 0)
        max_angle = max(abs(a) for a in angle_history) if angle_history else 0
        
        logger.info(f"Session verified: {len(angle_history)} frames, {sign_changes} oscillations")
        
        return jsonify({
            'success': True,
            'verified': True,
            'message': 'REACTOR STABILIZED: Human operator confirmed.',
            'stats': {
                'duration': len(angle_history) / 60,
                'max_deviation': math.degrees(max_angle),
                'oscillations': sign_changes,
                'stability_score': min(100, int(100 * (1 - max_angle / 1.2)))
            }
        })
        
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return jsonify({
            'success': False,
            'verified': False,
            'message': 'SYSTEM ERROR: Verification failed.'
        }), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Reactor Stabilizer on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)