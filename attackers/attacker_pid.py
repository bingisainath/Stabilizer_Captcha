"""PID Controller Mathematical Attacker"""

import time
import math
import logging
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PIDController:
    """Proportional-Integral-Derivative controller for inverted pendulum."""
    
    def __init__(self, kp=80, ki=0.02, kd=35):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.previous_error = 0.0
        self.integral = 0.0

    def update(self, error, dt=1/60):
        if error * self.previous_error < 0:
            self.integral = 0.0

        p_term = self.kp * error
        self.integral += error * dt
        self.integral = max(-2.0, min(2.0, self.integral))
        i_term = self.ki * self.integral
        derivative = (error - self.previous_error) / dt if dt > 0 else 0.0
        d_term = self.kd * derivative
        self.previous_error = error

        return p_term + i_term + d_term


class PIDAttacker:
    """PID controller-based CAPTCHA attacker."""
    
    def __init__(self, url, headless=False):
        self.url = url
        self.headless = headless
        self.driver = None
        self.pid = PIDController()
        self.current_mouse_x = None

    def setup(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1100,900")

        if self.headless:
            options.add_argument("--headless=new")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

        try:
            logger.info("Filling login form...")

            email = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email.send_keys("bot@pid.sys")

            self.driver.find_element(By.ID, "password").send_keys("access_code_123")
            self.driver.find_element(By.ID, "loginBtn").click()

            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.ID, "gameCanvas"))
            )
            logger.info("Login successful → CAPTCHA page loaded")

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

        return True

    def start_game(self):
        try:
            try:
                engage = WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located((By.ID, "clickPrompt"))
                )
                self.driver.execute_script("arguments[0].style.display='none';", engage)
                time.sleep(0.2)
            except:
                pass

            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click()
            time.sleep(0.3)
            return True

        except Exception as e:
            logger.error(f"start_game failed: {e}")
            return False

    def get_state(self):
        try:
            angle_text = self.driver.find_element(By.ID, "angleDisplay").text
            angle_deg = float(angle_text.replace("°", ""))

            time_text = self.driver.find_element(By.ID, "timeDisplay").text
            elapsed = float(time_text.replace("s", ""))

            return {
                "angle": math.radians(angle_deg),
                "angle_deg": angle_deg,
                "time": elapsed
            }
        except:
            return None

    def move_mouse(self, target_x, smoothing=0.5):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            width = canvas.size["width"]

            if self.current_mouse_x is None:
                self.current_mouse_x = width / 2

            smooth_x = self.current_mouse_x + (target_x - self.current_mouse_x) * smoothing
            smooth_x = max(0, min(width, smooth_x))

            ActionChains(self.driver).move_to_element_with_offset(
                canvas,
                smooth_x - width / 2,
                0
            ).perform()

            self.current_mouse_x = smooth_x

        except:
            pass

    def verify(self):
        logger.info("Clicking VERIFY COMPLETION button...")

        try:
            verify_btn = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.ID, "verifyBtn"))
            )
            self.driver.execute_script("arguments[0].click();", verify_btn)
            logger.info("VERIFY button clicked successfully")

            result = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "resultTitle"))
            ).text

            logger.info(f"Verification result: {result}")

            if "HUMAN VERIFIED" in result.upper():
                logger.info("✓ CAPTCHA CRACKED! Waiting for redirect...")
                
                time.sleep(2)
                
                if "/captcha" in self.driver.current_url:
                    logger.info("No automatic redirect, forcing navigation...")
                    self.driver.get(self.url + "/success")
                    time.sleep(1)
                
                if "/success" in self.driver.current_url:
                    logger.info("✓ SUCCESS PAGE REACHED!")
                    return True
                else:
                    logger.warning(f"Unexpected URL: {self.driver.current_url}")
                    return False
            else:
                logger.info("✗ Verification failed")
                return False

        except Exception as e:
            logger.error(f"Verification failed with error: {e}")
            return False

    def check_redirect(self):
        url = self.driver.current_url
        
        if "/success" in url:
            return "SUCCESS"
        elif "/failed" in url:
            return "FAILED"
        else:
            return "CONTINUE"

    def run_pid_loop(self):
        canvas = self.driver.find_element(By.ID, "gameCanvas")
        width = canvas.size["width"]
        center_x = width / 2
        self.current_mouse_x = center_x

        start_time = time.time()
        last_loop = start_time

        MAX_OUTPUT = 150
        DANGER_ZONE = math.radians(25)

        while True:
            state = self.get_state()
            if not state:
                break

            now = time.time()
            dt = now - last_loop
            last_loop = now

            elapsed = now - start_time
            
            if elapsed > 5.5:
                logger.info(f"Stabilization complete after {elapsed:.2f}s")
                break

            angle = state["angle"]
            angle_deg = state["angle_deg"]

            if abs(angle) > DANGER_ZONE:
                control = -MAX_OUTPUT if angle > 0 else MAX_OUTPUT
            else:
                control = self.pid.update(angle, dt if dt > 0 else 1/60)
                control = max(-MAX_OUTPUT, min(MAX_OUTPUT, control))

            target = center_x + control
            target = max(30, min(width - 30, target))

            self.move_mouse(target)

            if int(elapsed * 10) % 10 == 0:
                logger.info(
                    f"[t={elapsed:.1f}s] [ANGLE={angle_deg:+6.2f}°] "
                    f"[PID={control:+6.2f}] [CART={self.current_mouse_x:.1f}]"
                )

            time.sleep(1/60)

        time.sleep(0.5)

    def attack(self):
        logger.info("PID CAPTCHA ATTACKER - STARTING")

        if not self.setup():
            logger.error("Setup failed")
            return False

        attempt = 1

        while attempt <= 3:
            logger.info(f"\nATTEMPT {attempt}/3")

            if not self.start_game():
                logger.error("Could not start game")
                return False

            self.run_pid_loop()

            verified = self.verify()
            
            if verified:
                status = self.check_redirect()
                
                if status == "SUCCESS":
                    logger.info("✓ ATTACK SUCCESSFUL - CAPTCHA DEFEATED!")
                    time.sleep(3)
                    return True

            status = self.check_redirect()
            if status == "FAILED":
                logger.info("Maximum attempts exceeded → FAILED PAGE")
                return False

            logger.info("Retrying with new CAPTCHA challenge...")
            self.driver.get(self.url + "/captcha")
            time.sleep(1.5)
            attempt += 1

        logger.info("All 3 attempts exhausted - Attack failed")
        return False

    def cleanup(self):
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    
    attacker = PIDAttacker(url=url, headless=False)
    try:
        success = attacker.attack()
        exit(0 if success else 1)
    finally:
        attacker.cleanup()