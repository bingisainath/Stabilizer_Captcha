"""
PID Controller Attacker - Updated for Auth & New HTML
"""

import time
import math
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PIDController:
    def __init__(self, kp=120, ki=0.05, kd=60):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.previous_error = 0
        self.integral = 0
        
    def update(self, error, dt=1/60):
        p_term = self.kp * error
        self.integral += error * dt
        self.integral = max(-10, min(10, self.integral))
        i_term = self.ki * self.integral
        derivative = (error - self.previous_error) / dt if dt > 0 else 0
        d_term = self.kd * derivative
        self.previous_error = error
        return p_term + i_term + d_term
    
    def reset(self):
        self.previous_error = 0
        self.integral = 0

class PIDAttacker:
    def __init__(self, url="http://localhost:3000", headless=True):
        self.url = url
        self.driver = None
        self.pid = PIDController(kp=130, ki=0.05, kd=70) # Tuned for new physics
        self.current_mouse_x = None
        self.headless = headless
        
    def setup(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1000,800')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--log-level=3')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        
        # --- AUTOMATED LOGIN ---
        try:
            logger.info("Attempting login...")
            email_input = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_input.send_keys("bot@pid.sys")
            self.driver.find_element(By.ID, "password").send_keys("access_code_123")
            self.driver.find_element(By.ID, "loginBtn").click()
            
            # Wait for game canvas to load
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "gameCanvas"))
            )
            logger.info("Login successful. Game loaded.")
            time.sleep(1) # Let initialization finish
        except Exception as e:
            logger.warning(f"Login skipped or failed (might already be on game page): {e}")

    def get_game_state(self):
        try:
            angle_text = self.driver.find_element(By.ID, "angleDisplay").text
            angle_deg = float(angle_text.replace("°", ""))
            angle_rad = math.radians(angle_deg)
            
            time_text = self.driver.find_element(By.ID, "timeDisplay").text
            elapsed_time = float(time_text.replace("s", ""))
            
            return {'angle': angle_rad, 'angle_deg': angle_deg, 'time': elapsed_time}
        except:
            return None
    
    def move_mouse_smoothly(self, target_x, smoothing=0.4):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas_width = canvas.size['width']
            
            if self.current_mouse_x is None:
                self.current_mouse_x = canvas_width / 2
            
            smooth_x = self.current_mouse_x + (target_x - self.current_mouse_x) * smoothing
            smooth_x = max(0, min(canvas_width, smooth_x))
            
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(canvas, smooth_x - canvas_width/2, 0)
            actions.perform()
            
            self.current_mouse_x = smooth_x
        except:
            pass
    
    def start_game(self):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click()
            time.sleep(0.1)
            return True
        except:
            return False
    
    def attack(self):
        logger.info("PID Controller Attack Started")
        self.setup()
        
        try:
            if not self.start_game():
                logger.error("Failed to start game")
                return False
            
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas_width = canvas.size['width']
            cart_position = canvas_width / 2
            
            start_time = time.time()
            
            while True:
                state = self.get_game_state()
                if state is None:
                    break
                
                elapsed = time.time() - start_time
                if elapsed > 6:
                    break
                
                # PID Logic
                angle_error = state['angle']
                control_output = self.pid.update(angle_error)
                
                # Update position based on PID output
                target_position = cart_position + control_output
                target_position = max(30, min(canvas_width - 30, target_position))
                
                self.move_mouse_smoothly(target_position, smoothing=0.5)
                cart_position = self.current_mouse_x
                
                time.sleep(1/60)
            
            time.sleep(1)
            
            # Verification Step
            try:
                verify_btn = self.driver.find_element(By.ID, "verifyBtn")
                if verify_btn.is_displayed():
                    logger.info("Success - balanced for 5 seconds")
                    verify_btn.click()
                    time.sleep(2)
                    
                    # Updated Result Check for new HTML
                    result_title = self.driver.find_element(By.ID, "resultTitle").text
                    logger.info(f"Result: {result_title}")
                    
                    if "VERIFIED" in result_title:
                        logger.info("✓ PASSED verification")
                        return True
                    else:
                        logger.warning("✗ FAILED verification - detected as bot")
                        return False
                else:
                    logger.warning("Failed to balance")
                    return False
            except Exception as e:
                logger.error(f"Verification error: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Attack error: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    headless = "--no-headless" not in sys.argv
    PIDAttacker(url=url, headless=headless).attack()