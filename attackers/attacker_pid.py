"""
PID Controller Attacker - FIXED VERSION
- Properly handles verification and redirect flow
- Ensures navigation to success page after cracking CAPTCHA
"""

import time
import math
import logging
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


# =============================================================
#  PID CONTROLLER  (UNCHANGED)
# =============================================================
class PIDController:
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


# =============================================================
#  PID ATTACKER CLASS WITH FIXED VERIFICATION FLOW
# =============================================================
class PIDAttacker:
    def __init__(self):
        self.url = "http://localhost:3000"
        self.headless = False
        self.driver = None
        self.pid = PIDController()
        self.current_mouse_x = None

    # ----------------------------------------------------------
    # LOGIN PAGE HANDLING
    # ----------------------------------------------------------
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

            # Wait for captcha page
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.ID, "gameCanvas"))
            )
            logger.info("Login successful → CAPTCHA page loaded")

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

        return True

    # ----------------------------------------------------------
    # START GAME (Remove overlay + click canvas)
    # ----------------------------------------------------------
    def start_game(self):
        try:
            # Remove "CLICK TO ENGAGE" overlay if present
            try:
                engage = WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located((By.ID, "clickPrompt"))
                )
                self.driver.execute_script("arguments[0].style.display='none';", engage)
                time.sleep(0.2)
            except:
                pass

            # Click canvas to start
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click()
            time.sleep(0.3)
            return True

        except Exception as e:
            logger.error(f"start_game failed: {e}")
            return False

    # ----------------------------------------------------------
    # READ GAME STATE
    # ----------------------------------------------------------
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

    # ----------------------------------------------------------
    # MOVE MOUSE
    # ----------------------------------------------------------
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

    # ----------------------------------------------------------
    # VERIFY AND HANDLE REDIRECT (FIXED)
    # ----------------------------------------------------------
    def verify(self):
        logger.info("Clicking VERIFY COMPLETION button...")

        try:
            # Wait for and click verify button
            verify_btn = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.ID, "verifyBtn"))
            )
            self.driver.execute_script("arguments[0].click();", verify_btn)
            logger.info("VERIFY button clicked successfully")

            # Wait for result overlay to appear
            result = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "resultTitle"))
            ).text

            logger.info(f"Verification result: {result}")

            # Check if verification succeeded
            if "HUMAN VERIFIED" in result.upper():
                logger.info("✓ CAPTCHA CRACKED! Waiting for redirect...")
                
                # FIXED: Force navigation to success page
                # Wait a moment for any automatic redirect, then force it
                time.sleep(2)
                
                # Check if we're still on captcha page
                if "/captcha" in self.driver.current_url:
                    logger.info("No automatic redirect detected, forcing navigation...")
                    self.driver.get(self.url + "/success")
                    time.sleep(1)
                
                # Verify we reached success page
                if "/success" in self.driver.current_url:
                    logger.info("🎉 SUCCESS PAGE REACHED!")
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

    # ----------------------------------------------------------
    # CHECK CURRENT PAGE STATUS
    # ----------------------------------------------------------
    def check_redirect(self):
        url = self.driver.current_url
        
        if "/success" in url:
            return "SUCCESS"
        elif "/failed" in url:
            return "FAILED"
        else:
            return "CONTINUE"

    # ----------------------------------------------------------
    # PID CONTROL LOOP
    # ----------------------------------------------------------
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
            
            # Run for at least 5.5 seconds to ensure passing threshold
            if elapsed > 5.5:
                logger.info(f"Stabilization complete after {elapsed:.2f}s")
                break

            angle = state["angle"]
            angle_deg = state["angle_deg"]

            # Emergency control for large deviations
            if abs(angle) > DANGER_ZONE:
                control = -MAX_OUTPUT if angle > 0 else MAX_OUTPUT
            else:
                control = self.pid.update(angle, dt if dt > 0 else 1/60)
                control = max(-MAX_OUTPUT, min(MAX_OUTPUT, control))

            target = center_x + control
            target = max(30, min(width - 30, target))

            self.move_mouse(target)

            # Log progress
            if int(elapsed * 10) % 10 == 0:  # Log every second
                logger.info(
                    f"[t={elapsed:.1f}s] [ANGLE={angle_deg:+6.2f}°] "
                    f"[PID={control:+6.2f}] [CART={self.current_mouse_x:.1f}]"
                )

            time.sleep(1/60)

        time.sleep(0.5)

    # ----------------------------------------------------------
    # MAIN ATTACK LOOP WITH 3 ATTEMPTS
    # ----------------------------------------------------------
    def attack(self):
        logger.info("=" * 60)
        logger.info("PID CAPTCHA ATTACKER - STARTING")
        logger.info("=" * 60)

        if not self.setup():
            logger.error("Setup failed")
            return False

        attempt = 1

        while attempt <= 3:
            logger.info(f"\n{'='*20} ATTEMPT {attempt}/3 {'='*20}")

            if not self.start_game():
                logger.error("Could not start game")
                return False

            # Run PID stabilization
            self.run_pid_loop()

            # Attempt verification
            verified = self.verify()
            
            if verified:
                status = self.check_redirect()
                
                if status == "SUCCESS":
                    logger.info("=" * 60)
                    logger.info("🎉 ATTACK SUCCESSFUL - CAPTCHA DEFEATED!")
                    logger.info("=" * 60)
                    time.sleep(3)  # Keep browser open to see success
                    return True

            # Check if we hit max attempts
            status = self.check_redirect()
            if status == "FAILED":
                logger.info("Maximum attempts exceeded → FAILED PAGE")
                return False

            # Retry with new CAPTCHA
            logger.info("Retrying with new CAPTCHA challenge...")
            self.driver.get(self.url + "/captcha")
            time.sleep(1.5)
            attempt += 1

        logger.info("=" * 60)
        logger.info("All 3 attempts exhausted - Attack failed")
        logger.info("=" * 60)
        return False

    def cleanup(self):
        if self.driver:
            self.driver.quit()


# =============================================================
# RUN
# =============================================================
if __name__ == "__main__":
    attacker = PIDAttacker()
    try:
        success = attacker.attack()
        exit(0 if success else 1)
    finally:
        attacker.cleanup()