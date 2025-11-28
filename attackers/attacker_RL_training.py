"""
RL ATTACKER (Q-Learning) - Updated for Auth System
--------------------------------------------------
This bot learns to balance the reactor by trial and error.
It includes auto-login capabilities and state persistence.
"""

import time
import math
import numpy as np
import pickle
import os
import sys
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# PART 1: THE BRAIN (Q-Learning Agent)
# ==========================================

class QLearningAgent:
    """The brain that makes decisions based on the game state."""
    
    def __init__(self, learning_rate=0.2, discount=0.9, epsilon=0.2):
        self.lr = learning_rate
        self.gamma = discount
        self.epsilon = epsilon
        
        # Q-table: stores the value of taking an Action in a specific State
        self.q_table = defaultdict(lambda: defaultdict(float))
        
        # Actions: Move mouse by X pixels relative to current position
        # Increased force slightly for the new physics engine
        self.actions = [-40, -20, 0, 20, 40] 
        
    def discretize_state(self, angle, angular_velocity):
        """Reduces the infinite game states into manageable 'bins'."""
        # Angle bins (radians)
        angle_bins = np.linspace(-1.4, 1.4, 10)
        angle_idx = np.digitize(angle, angle_bins)
        
        # Velocity bins
        velocity_bins = np.linspace(-0.6, 0.6, 6)
        velocity_idx = np.digitize(angular_velocity, velocity_bins)
        
        return (angle_idx, velocity_idx)
    
    def get_action(self, state, explore=True):
        """Decide what to do: Explore (random) or Exploit (best known)."""
        if explore and np.random.random() < self.epsilon:
            return np.random.choice(self.actions)
        
        # Find action with highest Q-value for this state
        q_values = [self.q_table[state][a] for a in self.actions]
        max_q = max(q_values)
        
        # Pick randomly among the best actions (if ties exist)
        best_actions = [a for a, q in zip(self.actions, q_values) if q == max_q]
        return np.random.choice(best_actions)
    
    def update(self, state, action, reward, next_state):
        """Learn from the result of an action."""
        current_q = self.q_table[state][action]
        max_next_q = max([self.q_table[next_state][a] for a in self.actions])
        
        # Bellman Equation
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state][action] = new_q
    
    def save(self, filename="q_table.pkl"):
        with open(filename, 'wb') as f:
            pickle.dump(dict(self.q_table), f)
    
    def load(self, filename="q_table.pkl"):
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                self.q_table = defaultdict(lambda: defaultdict(float), pickle.load(f))
            return True
        return False

# ==========================================
# PART 2: THE BODY (Selenium Controller)
# ==========================================

class RLAttacker:
    def __init__(self, url="http://localhost:3000", train_episodes=20):
        self.url = url
        self.driver = None
        self.agent = QLearningAgent()
        self.train_episodes = train_episodes
        
        # State tracking
        self.previous_angle = 0
        self.current_mouse_x = None
        
    def setup(self):
        """Launches browser and performs Login."""
        print("🚀 Launching Browser...")
        options = webdriver.ChromeOptions()
        # Comment out the next line to watch the training happen!
        # options.add_argument('--headless=new') 
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1000,800')
        options.add_argument('--log-level=3')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        
        # --- LOGIN SEQUENCE ---
        try:
            # Check if we are on the login page by looking for email input
            if len(self.driver.find_elements(By.ID, "email")) > 0:
                print("🔒 Login Page Detected. Authenticating...")
                self.driver.find_element(By.ID, "email").send_keys("rl_agent@bot.com")
                self.driver.find_element(By.ID, "password").send_keys("q_learning_v2")
                self.driver.find_element(By.ID, "loginBtn").click()
                
                # Wait for the game canvas to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "gameCanvas"))
                )
                print("🔓 Login Successful.")
                time.sleep(1) # Allow initialization
            else:
                print("🔓 Already logged in.")
        except Exception as e:
            print(f"⚠️ Login Warning: {e}")

    def get_game_state(self):
        """Reads the Angle and Time from the HTML."""
        try:
            # New HTML uses #angleDisplay and #timeDisplay
            angle_text = self.driver.find_element(By.ID, "angleDisplay").text
            angle_deg = float(angle_text.replace("°", ""))
            angle_rad = math.radians(angle_deg)
            
            time_text = self.driver.find_element(By.ID, "timeDisplay").text
            elapsed_time = float(time_text.replace("s", ""))
            
            # Calculate velocity
            angular_velocity = (angle_rad - self.previous_angle) * 60
            self.previous_angle = angle_rad
            
            return {
                'angle': angle_rad, 
                'velocity': angular_velocity, 
                'time': elapsed_time
            }
        except:
            return None

    def move_mouse_smoothly(self, target_x):
        """Moves the mouse to target_x."""
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            width = canvas.size['width']
            
            if self.current_mouse_x is None:
                self.current_mouse_x = width / 2
                
            # Clamp to canvas bounds
            target_x = max(0, min(width, target_x))
            
            # Use ActionChains to move
            actions = ActionChains(self.driver)
            # Coordinates are relative to center of element
            actions.move_to_element_with_offset(canvas, target_x - width/2, 0)
            actions.perform()
            
            self.current_mouse_x = target_x
        except:
            pass

    def calculate_reward(self, state, done, success):
        """Defines what is 'good' behavior."""
        if success:
            return 200  # JACKPOT
        elif done and not success:
            return -100 # CRASH
        
        # Shaping reward: Closer to 0 angle is better
        angle = abs(state['angle'])
        if angle < 0.1: return 5.0
        if angle < 0.3: return 2.0
        if angle < 0.8: return 0.5
        return -1.0

    def run_episode(self, train=True):
        """Plays one single game."""
        # 1. Reset/Start Game
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click()
        except:
            # If clicked too fast or not ready
            pass

        self.previous_angle = 0
        cart_pos = 300 # Center
        start_time = time.time()
        episode_reward = 0
        steps = 0
        
        while steps < 500: # Max steps safety
            # Get current state
            raw_state = self.get_game_state()
            if not raw_state: break
            
            state = self.agent.discretize_state(raw_state['angle'], raw_state['velocity'])
            
            # Decide action
            action = self.agent.get_action(state, explore=train)
            
            # Execute action
            cart_pos += action
            self.move_mouse_smoothly(cart_pos)
            
            # Wait for physics tick
            time.sleep(1/60) 
            steps += 1
            
            # Observe result
            next_raw = self.get_game_state()
            if not next_raw: break
            
            # Check conditions
            elapsed = time.time() - start_time
            done = elapsed > 5.5 or abs(next_raw['angle']) > 1.4
            success = elapsed > 5.0 and abs(next_raw['angle']) < 1.4
            
            # Calculate reward and Learn
            reward = self.calculate_reward(next_raw, done, success)
            episode_reward += reward
            
            next_state = self.agent.discretize_state(next_raw['angle'], next_raw['velocity'])
            
            if train:
                self.agent.update(state, action, reward, next_state)
            
            if done:
                return episode_reward, success
                
        return episode_reward, False

    def train(self):
        """Main training loop."""
        print(f"\n🎓 Starting Training: {self.train_episodes} Episodes")
        self.setup()
        
        try:
            for i in range(self.train_episodes):
                # Refresh page occasionally to clear physics drift or glitches
                if i > 0: 
                    self.driver.refresh()
                    time.sleep(1) # Wait for reload
                
                reward, success = self.run_episode(train=True)
                
                status = "✓ SUCCESS" if success else "✗ Failed"
                print(f"Ep {i+1:02d}: Reward {reward:.1f} | {status} | Epsilon {self.agent.epsilon:.2f}")
                
                # Decay exploration
                self.agent.epsilon = max(0.01, self.agent.epsilon * 0.95)
                
            print("\n💾 Saving Q-Table...")
            self.agent.save()
            
        finally:
            self.driver.quit()

    def attack(self, load_pretrained=True):
        """Attack mode: No learning, just doing."""
        print("\n⚔️ STARTING ATTACK SEQUENCE")
        
        if load_pretrained:
            if self.agent.load():
                print("📂 Loaded existing Q-table.")
            else:
                print("⚠️ No Q-table found. Training first...")
                self.train()
                return self.attack(load_pretrained=True)
        
        self.setup()
        
        try:
            # Turn off exploration (Pure Exploitation)
            self.agent.epsilon = 0
            print("🤖 Agent ready. Stabilizing...")
            
            reward, success = self.run_episode(train=False)
            
            if success:
                print("✅ Stability Achieved. Attempting Verification...")
                time.sleep(1)
                
                btn = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.ID, "verifyBtn"))
                )
                btn.click()
                
                time.sleep(2)
                result = self.driver.find_element(By.ID, "resultTitle").text
                print(f"\nRESULT: {result}")
                
                if "VERIFIED" in result:
                    print("🎉 SYSTEM DEFEATED: Bot accepted as human.")
                    return True
                else:
                    print("🚫 SYSTEM DEFENSE: Bot detected during verification.")
            else:
                print("❌ FAILED: Could not stabilize reactor.")
                
        except Exception as e:
            print(f"Error during attack: {e}")
        finally:
            self.driver.quit()

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    
    # 1. Create the Attacker
    bot = RLAttacker(train_episodes=100)
    
    # 2. Decide: Train or Attack?
    # By default, we try to load. If fail, we train, then attack.
    
    print("="*50)
    print("      REINFORCEMENT LEARNING ATTACKER v3      ")
    print("="*50)
    
    success = bot.attack(load_pretrained=True)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)