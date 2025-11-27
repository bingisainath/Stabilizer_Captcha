"""
RL ATTACKER FOR REACTOR CAPTCHA
Compatible with:
- app.py (Flask backend)
- login.html
- captcha.html
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
# Q-LEARNING AGENT
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
# REACTOR CAPTCHA ATTACKER
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
    # Play Episode
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
            timed_out = elapsed >= 5.5
            success = elapsed >= 5.0 and not crash
            done = crash or timed_out

            reward = self.calculate_reward(next_state_raw, done, success)
            episode_reward += reward

            next_state = self.agent.discretize_state(next_state_raw["angle"], next_state_raw["velocity"])

            if train:
                self.agent.update(state, action, reward, next_state)

            if done:
                return episode_reward, success

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
    # ATTACK MODE WITH 3 RETRIES
    # -------------------------------------------

    def attack(self, load_pretrained=True):
        print("\n⚔️ STARTING ATTACK MODE")

        if load_pretrained:
            if not self.agent.load():
                print("⚠️ No Q-table found → training first")
                self.train()
                return self.attack(load_pretrained=True)

        self.agent.epsilon = 0

        self.setup()
        wait = WebDriverWait(self.driver, 10)

        MAX_ATTEMPTS = 3

        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"\n===== ATTEMPT {attempt} / {MAX_ATTEMPTS} =====")

            reward, success = self.run_episode(train=False)
            print(f"Attempt result: reward={reward:.1f}, success={success}")

            if success:
                print("Stabilized successfully → clicking VERIFY…")

                try:
                    verify_btn = wait.until(EC.element_to_be_clickable((By.ID, "verifyBtn")))
                    verify_btn.click()
                except:
                    self.driver.execute_script("document.getElementById('verifyBtn').click()")

                time.sleep(1.5)

                result = wait.until(EC.visibility_of_element_located((By.ID, "resultTitle"))).text.strip()
                print("Verification result:", result)

                if "HUMAN VERIFIED" in result.upper():
                    print("🎉 SUCCESS! SYSTEM DEFEATED.")
                    self.driver.quit()
                    return True

            # Failure → click TRY AGAIN
            print("❌ Failed. Clicking TRY AGAIN…")

            try:
                retry_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".retry-btn")))
                retry_btn.click()
                print("🔄 TRY AGAIN clicked.")
            except:
                print("⚠️ Retry button missing → reloading page")
                self.driver.execute_script("location.reload()")

            # Reset
            self.previous_angle = 0
            self.current_mouse_x = None
            time.sleep(1.5)

        print("❌ All attempts failed.")
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

    success = bot.attack(load_pretrained=True)
    sys.exit(0 if success else 1)
