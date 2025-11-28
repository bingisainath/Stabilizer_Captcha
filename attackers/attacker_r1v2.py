"""
RL ATTACKER FOR REACTOR CAPTCHA - COMPLETE FIX
- Returns immediately at 5.0s success
- Handles redirect to success page
- Properly detects and handles /failed page lockout
"""

import time
import math
import pickle
import os
import sys
from collections import defaultdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ======================================================
# Q-LEARNING AGENT (UNCHANGED)
# ======================================================

class QLearningAgent:
    def __init__(self, learning_rate=0.2, discount=0.9, epsilon=0.2):
        self.lr = learning_rate
        self.gamma = discount
        self.epsilon = epsilon

        self.q_table = defaultdict(lambda: defaultdict(float))
        self.actions = [-40, -20, 0, 20, 40]

    def discretize_state(self, angle, angular_velocity):
        import numpy as np

        angle_bins = np.linspace(-1.4, 1.4, 10)
        vel_bins = np.linspace(-0.6, 0.6, 6)

        angle_idx = int(np.digitize(angle, angle_bins))
        vel_idx = int(np.digitize(angular_velocity, vel_bins))

        return (angle_idx, vel_idx)

    def get_action(self, state, explore=True):
        import numpy as np

        if explore and np.random.random() < self.epsilon:
            return np.random.choice(self.actions)

        q_values = [self.q_table[state][a] for a in self.actions]
        max_q = max(q_values)
        best_actions = [a for a, q in zip(self.actions, q_values) if q == max_q]

        return int(np.random.choice(best_actions))

    def update(self, state, action, reward, next_state):
        max_next = max(self.q_table[next_state][a] for a in self.actions)
        current = self.q_table[state][action]

        new_q = current + self.lr * (reward + self.gamma * max_next - current)
        self.q_table[state][action] = new_q

    def save(self, filename="q_table.pkl"):
        with open(filename, "wb") as f:
            pickle.dump(dict(self.q_table), f)

    def load(self, filename="q_table.pkl"):
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                data = pickle.load(f)
            self.q_table = defaultdict(lambda: defaultdict(float), data)
            return True
        return False


# ======================================================
# REACTOR CAPTCHA ATTACKER (COMPLETE FIX)
# ======================================================

class RLAttacker:
    def __init__(self, url="http://localhost:3000", train_episodes=20, headless=False):
        self.url = url
        self.train_episodes = train_episodes
        self.headless = headless
        self.driver = None
        self.agent = QLearningAgent()

        self.previous_angle = 0.0
        self.current_mouse_x = None

    # -------------------------------------------
    # Browser + Login
    # -------------------------------------------

    def _create_driver(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1200,900")
        options.add_argument("--log-level=3")
        return webdriver.Chrome(options=options)

    def setup(self):
        print("🚀 Launching browser...")
        self.driver = self._create_driver()
        self.driver.get(self.url)

        wait = WebDriverWait(self.driver, 10)

        try:
            email_input = wait.until(EC.presence_of_element_located((By.ID, "email")))
            password_input = self.driver.find_element(By.ID, "password")
            login_btn = self.driver.find_element(By.ID, "loginBtn")

            email_input.send_keys("rl_agent@bot.com")
            password_input.send_keys("q_learning_access")
            login_btn.click()

            wait.until(EC.presence_of_element_located((By.ID, "gameCanvas")))
            print("🔓 Login success, captcha loaded.")

            time.sleep(1)

        except Exception as e:
            print("⚠️ Login error:", e)
            raise

    # -------------------------------------------
    # Check Current Page
    # -------------------------------------------

    def check_page_status(self):
        """Check what page we're on"""
        try:
            current_url = self.driver.current_url
            
            if "/success" in current_url:
                return "SUCCESS"
            elif "/failed" in current_url:
                return "FAILED"
            elif "/captcha" in current_url:
                return "CAPTCHA"
            elif current_url.endswith("/") or "/login" in current_url:
                return "LOGIN"
            else:
                return "UNKNOWN"
        except:
            return "ERROR"

    # -------------------------------------------
    # Game State
    # -------------------------------------------

    def get_game_state(self):
        try:
            angle_deg = float(
                self.driver.find_element(By.ID, "angleDisplay").text.replace("°", "")
            )
            time_val = float(
                self.driver.find_element(By.ID, "timeDisplay").text.replace("s", "")
            )

            angle_rad = math.radians(angle_deg)
            angular_velocity = (angle_rad - self.previous_angle) * 60
            self.previous_angle = angle_rad

            return {
                "angle": angle_rad,
                "velocity": angular_velocity,
                "time": time_val,
            }

        except:
            return None

    # -------------------------------------------
    # Mouse Control
    # -------------------------------------------

    def move_mouse_smoothly(self, target_x):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            width = canvas.size["width"]

            if self.current_mouse_x is None:
                self.current_mouse_x = width / 2

            target_x = max(0, min(width, target_x))

            actions = ActionChains(self.driver)
            offset = target_x - width / 2
            actions.move_to_element_with_offset(canvas, offset, 0).perform()

            self.current_mouse_x = target_x

        except:
            pass

    # -------------------------------------------
    # Reward Function
    # -------------------------------------------

    def calculate_reward(self, state, done, success):
        if success:
            return 200
        if done:
            return -100

        angle = abs(state["angle"])
        if angle < 0.1:
            return 5
        if angle < 0.3:
            return 2
        if angle < 0.8:
            return 0.5
        return -1

    # -------------------------------------------
    # Play Episode - FIXED TO RETURN IMMEDIATELY AT 5s
    # -------------------------------------------

    def run_episode(self, train=True):
        wait = WebDriverWait(self.driver, 10)

        canvas = wait.until(EC.presence_of_element_located((By.ID, "gameCanvas")))

        try:
            ActionChains(self.driver).move_to_element(canvas).click().perform()
        except:
            canvas.click()

        time.sleep(0.2)

        self.previous_angle = 0
        width = canvas.size["width"]
        cart_x = width / 2

        episode_reward = 0
        steps = 0
        timestep = 1 / 60

        while steps < 600:
            raw_state = self.get_game_state()
            if not raw_state:
                break

            state = self.agent.discretize_state(raw_state["angle"], raw_state["velocity"])
            action = self.agent.get_action(state, explore=train)
            cart_x += action

            self.move_mouse_smoothly(cart_x)
            time.sleep(timestep)
            steps += 1

            next_state_raw = self.get_game_state()
            if not next_state_raw:
                break

            angle = next_state_raw["angle"]
            elapsed = next_state_raw["time"]

            crash = abs(angle) > 1.4
            
            # ✅ FIX: Check for success at 5.0s and return IMMEDIATELY
            success = elapsed >= 5.0 and not crash
            
            if success:
                print(f"✓ Success achieved at {elapsed:.2f}s - returning immediately")
                reward = self.calculate_reward(next_state_raw, False, True)
                episode_reward += reward
                return episode_reward, True
            
            # Only continue if not crashed
            if crash:
                reward = self.calculate_reward(next_state_raw, True, False)
                episode_reward += reward
                print(f"✗ Crashed at {elapsed:.2f}s (angle={math.degrees(angle):.1f}°)")
                return episode_reward, False

            reward = self.calculate_reward(next_state_raw, False, False)
            episode_reward += reward

            next_state = self.agent.discretize_state(next_state_raw["angle"], next_state_raw["velocity"])

            if train:
                self.agent.update(state, action, reward, next_state)

        # If we exit the loop without success or crash (timeout)
        print("✗ Episode timeout (10 seconds elapsed)")
        return episode_reward, False

    # -------------------------------------------
    # TRAINING MODE
    # -------------------------------------------

    def train(self):
        print(f"\n🎓 Starting training for {self.train_episodes} episodes…")
        self.setup()

        try:
            for i in range(self.train_episodes):
                if i > 0:
                    self.driver.get(self.url + "/captcha")
                    time.sleep(1)

                reward, success = self.run_episode(train=True)

                print(f"Ep {i+1}: reward={reward:.1f}, success={success}")

                self.agent.epsilon = max(0.01, self.agent.epsilon * 0.95)

            print("💾 Saving Q table…")
            self.agent.save()

        finally:
            self.driver.quit()

    # -------------------------------------------
    # ATTACK MODE WITH PROPER ERROR HANDLING
    # -------------------------------------------

    def attack(self, load_pretrained=True):
        print("\n" + "="*60)
        print("⚔️ STARTING RL ATTACK MODE")
        print("="*60)

        if load_pretrained:
            if not self.agent.load():
                print("⚠️ No Q-table found → training first")
                self.train()
                return self.attack(load_pretrained=True)
            else:
                print("✓ Loaded pre-trained Q-table")

        self.agent.epsilon = 0  # No exploration during attack

        try:
            self.setup()
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False

        wait = WebDriverWait(self.driver, 10)
        MAX_ATTEMPTS = 3

        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"\n{'='*20} ATTEMPT {attempt}/{MAX_ATTEMPTS} {'='*20}")

            # Check if we're locked out before attempting
            page_status = self.check_page_status()
            if page_status == "FAILED":
                print("❌ PROTOCOL LOCKOUT - Reached /failed page")
                print("Maximum verification attempts exceeded")
                time.sleep(2)
                self.driver.quit()
                return False

            # Run stabilization episode
            try:
                reward, success = self.run_episode(train=False)
                print(f"Episode result: reward={reward:.1f}, stabilized={success}")
            except Exception as e:
                print(f"⚠️ Episode error: {e}")
                success = False

            if success:
                print("✓ Stabilization successful → clicking VERIFY...")

                # Small delay to ensure UI is ready
                time.sleep(0.5)

                try:
                    # Click verify button
                    verify_btn = wait.until(
                        EC.element_to_be_clickable((By.ID, "verifyBtn"))
                    )
                    verify_btn.click()
                    print("✓ VERIFY button clicked")
                except Exception as e:
                    # Fallback to JS click
                    print(f"Standard click failed, using JS...")
                    try:
                        self.driver.execute_script(
                            "document.getElementById('verifyBtn').click()"
                        )
                        print("✓ VERIFY button clicked (JS)")
                    except Exception as js_e:
                        print(f"❌ Could not click VERIFY: {js_e}")
                        continue

                time.sleep(1.5)

                # Read verification result
                try:
                    result = wait.until(
                        EC.visibility_of_element_located((By.ID, "resultTitle"))
                    ).text.strip()
                    print(f"Verification result: {result}")

                    if "HUMAN VERIFIED" in result.upper():
                        print("✓ CAPTCHA CRACKED!")
                        
                        # Force navigation to success page
                        time.sleep(2)
                        
                        # Check current page
                        page_status = self.check_page_status()
                        
                        if page_status == "SUCCESS":
                            print("="*60)
                            print("🎉 SUCCESS! Already on success page!")
                            print("="*60)
                            time.sleep(3)
                            self.driver.quit()
                            return True
                        elif page_status == "CAPTCHA":
                            print("Still on captcha page, forcing navigation...")
                            self.driver.get(self.url + "/success")
                            time.sleep(1)
                            
                            if self.check_page_status() == "SUCCESS":
                                print("="*60)
                                print("🎉 SUCCESS! CAPTCHA DEFEATED")
                                print("="*60)
                                time.sleep(3)
                                self.driver.quit()
                                return True
                        else:
                            print(f"⚠️ Unexpected page: {page_status}")
                    else:
                        print(f"✗ Verification failed: {result}")
                    
                except Exception as e:
                    print(f"⚠️ Error reading result: {e}")

            else:
                print("✗ Stabilization failed (crashed or timed out)")

            # Check if we've been redirected to /failed
            page_status = self.check_page_status()
            if page_status == "FAILED":
                print("="*60)
                print("❌ MAXIMUM ATTEMPTS EXCEEDED")
                print("System has redirected to /failed page - Protocol lockout engaged")
                print("="*60)
                time.sleep(3)
                self.driver.quit()
                return False

            # Try to continue with next attempt
            if attempt < MAX_ATTEMPTS:
                print(f"Preparing attempt {attempt + 1}...")
                
                # Look for retry button first
                try:
                    retry_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".retry-btn"))
                    )
                    retry_btn.click()
                    print("🔄 TRY AGAIN button clicked")
                    time.sleep(1.5)
                except:
                    # No retry button, try reloading captcha page
                    print("No retry button found, reloading captcha...")
                    try:
                        self.driver.get(self.url + "/captcha")
                        time.sleep(1.5)
                        
                        # Check if we ended up on /failed instead
                        if self.check_page_status() == "FAILED":
                            print("❌ Redirected to /failed - lockout engaged")
                            time.sleep(2)
                            self.driver.quit()
                            return False
                    except Exception as e:
                        print(f"❌ Cannot reload captcha: {e}")
                        self.driver.quit()
                        return False

                # Reset state for next attempt
                self.previous_angle = 0
                self.current_mouse_x = None

        # All attempts exhausted
        print("="*60)
        print("❌ All 3 attempts exhausted - Attack failed")
        print("="*60)
        time.sleep(2)
        self.driver.quit()
        return False


# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":
    bot = RLAttacker(
        url="http://localhost:3000",
        train_episodes=20,
        headless=False
    )

    try:
        success = bot.attack(load_pretrained=True)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Attack interrupted by user")
        if bot.driver:
            bot.driver.quit()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        if bot.driver:
            bot.driver.quit()
        sys.exit(1)