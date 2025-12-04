import random
import math


def lerp(start, end, t):
    """Linear interpolation between start and end."""
    return start + (end - start) * t


def generate_smooth_parameter_schedule(min_val, max_val, frame_count, num_keyframes=5):
    """
    Generate a smooth parameter schedule using keyframe interpolation.
    
    Args:
        min_val: Minimum parameter value
        max_val: Maximum parameter value
        frame_count: Total number of frames
        num_keyframes: Number of keyframes for interpolation
    
    Returns:
        List of parameter values for each frame
    """
    keyframe_positions = sorted([0] + 
                                random.sample(range(1, frame_count - 1), num_keyframes - 2) + 
                                [frame_count - 1])
    
    keyframe_values = [random.uniform(min_val, max_val) for _ in range(num_keyframes)]
    
    schedule = []
    keyframe_idx = 0
    
    for frame in range(frame_count):
        while keyframe_idx < len(keyframe_positions) - 1 and frame >= keyframe_positions[keyframe_idx + 1]:
            keyframe_idx += 1
        
        if keyframe_idx >= len(keyframe_positions) - 1:
            schedule.append(keyframe_values[-1])
        else:
            start_frame = keyframe_positions[keyframe_idx]
            end_frame = keyframe_positions[keyframe_idx + 1]
            
            t = (frame - start_frame) / (end_frame - start_frame) if end_frame != start_frame else 0
            
            value = lerp(keyframe_values[keyframe_idx], keyframe_values[keyframe_idx + 1], t)
            schedule.append(value)
    
    return schedule


def generate_force_jolts(frame_count):
    """
    Generate random force jolts throughout the simulation.
    
    Args:
        frame_count: Total number of frames
    
    Returns:
        List of force jolt values for each frame
    """
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
    """
    Analyze user behavior to detect bot patterns.
    
    Uses cart velocity vs angle correlation (reaction time) and input entropy
    to distinguish between human and AI behavior.
    
    Args:
        angle_history: List of pole angles over time
        cart_history: List of cart positions over time
    
    Returns:
        Tuple of (ai_probability, human_probability, details_dict)
    """
    if not angle_history or len(angle_history) < 20 or not cart_history:
        return 0, 100, {"error": "insufficient_data"}
    
    cart_velocity = [
        cart_history[i] - cart_history[i-1] 
        for i in range(1, len(cart_history))
    ]
    
    cart_accel = [
        cart_velocity[i] - cart_velocity[i-1] 
        for i in range(1, len(cart_velocity))
    ]
    
    input_roughness = sum(abs(a) for a in cart_accel) / len(cart_accel) if cart_accel else 0
    
    best_correlation = -1
    estimated_lag = 0
    
    def normalize(data):
        """Normalize data to zero mean and unit variance."""
        mean = sum(data) / len(data)
        std = (sum((x - mean) ** 2 for x in data) / len(data)) ** 0.5
        if std == 0:
            return [0] * len(data)
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
    avg_speed = total_distance / len(cart_velocity)
    
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