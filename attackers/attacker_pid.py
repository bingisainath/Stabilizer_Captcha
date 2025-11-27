"""
PID Controller Attacker - FINAL VERSION (UI FIXED, PID UNTOUCHED)
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
#  PID ATTACKER CLASS WITH UPDATED UI LOGIC
# =============================================================
class PIDAttacker:
    def __init__(self):
        self.url = "http://localhost:3000"
        self.headless = False
        self.driver = None
        self.pid = PIDController()
        self.current_mouse_x = None

    # ----------------------------------------------------------
    # LOGIN PAGE HANDLING (UPDATED)
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

            # JS performs redirect → wait for captcha page
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.ID, "gameCanvas"))
            )
            logger.info("Login successful.")

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

        return True

    # ----------------------------------------------------------
    # CLICK "CLICK TO ENGAGE" + CLICK CANVAS (UPDATED)
    # ----------------------------------------------------------
    def start_game(self):
        try:
            # CLICK TO ENGAGE overlay
            try:
                engage = WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located((By.ID, "clickPrompt"))
                )
                # Remove overlay using JS
                self.driver.execute_script("arguments[0].style.display='none';", engage)
                time.sleep(0.2)
            except:
                pass

            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click()
            time.sleep(0.3)
            return True

        except Exception as e:
            logger.error(f"start_game failed {e}")
            return False

    # ----------------------------------------------------------
    # READ GAME STATE (UNCHANGED)
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
    # MOVE MOUSE (UNCHANGED)
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
    # VERIFY BUTTON AND OVERLAY HANDLING (UPDATED)
    # ----------------------------------------------------------
    def verify(self):
        logger.info("Clicking VERIFY button...")

        try:
            verify_btn = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.ID, "verifyBtn"))
            )
            self.driver.execute_script("arguments[0].click();", verify_btn)

            result = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "resultTitle"))
            ).text

            logger.info(f"Result overlay: {result}")

            return "HUMAN VERIFIED" in result

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    # ----------------------------------------------------------
    # CHECK FOR REDIRECT AFTER VERIFY (UPDATED)
    # ----------------------------------------------------------
    def check_redirect(self):
        url = self.driver.current_url

        if "/success" in url:
            return "SUCCESS"

        if "/failed" in url:
            return "FAILED"

        return "CONTINUE"

    # ----------------------------------------------------------
    # PID LOOP (UNCHANGED)
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
            if elapsed > 6:
                break

            angle = state["angle"]
            angle_deg = state["angle_deg"]

            # emergency control
            if abs(angle) > DANGER_ZONE:
                control = -MAX_OUTPUT if angle > 0 else MAX_OUTPUT
            else:
                control = self.pid.update(angle, dt if dt > 0 else 1/60)
                control = max(-MAX_OUTPUT, min(MAX_OUTPUT, control))

            target = center_x + control
            target = max(30, min(width - 30, target))

            self.move_mouse(target)

            logger.info(
                f"[ANGLE={angle_deg:.2f}°] [PID={control:.2f}] "
                f"[TARGET={target:.2f}] [CART={self.current_mouse_x:.2f}] "
                f"[t={elapsed:.2f}s]"
            )

            time.sleep(1/60)

        time.sleep(1)

    # ----------------------------------------------------------
    # MAIN ATTACK LOOP WITH 3 ATTEMPTS (UPDATED)
    # ----------------------------------------------------------
    def attack(self):
        logger.info("=== PID ATTACK STARTED ===")

        if not self.setup():
            return False

        attempt = 1

        while attempt <= 3:
            logger.info(f"=== Attempt {attempt}/3 ===")

            if not self.start_game():
                logger.error("Could not start game.")
                return False

            # RUN PID LOOP (unchanged)
            self.run_pid_loop()

            verified = self.verify()
            status = self.check_redirect()

            if status == "SUCCESS":
                logger.info("Final Status: VERIFIED")
                return True

            if status == "FAILED":
                logger.info("Attempts exceeded → FAILED PAGE")
                return False

            # Try again
            logger.info("Retrying new CAPTCHA...")
            self.driver.get(self.url + "/captcha")
            attempt += 1

        logger.info("=== All 3 Attempts Failed ===")
        return False


# =============================================================
# RUN
# =============================================================
if __name__ == "__main__":
    PIDAttacker().attack()
