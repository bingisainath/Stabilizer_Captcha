"""
PID Controller Attacker - OPTIMIZED VERSION WITH TELEMETRY
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


# ------------------------------------------------------
# PID Controller
# ------------------------------------------------------
class PIDController:
    def __init__(self, kp=80, ki=0.02, kd=35):
        # Tuned-down gains; stability > aggression
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.previous_error = 0.0
        self.integral = 0.0

    def update(self, error, dt=1/60):
        # Reset integral if we cross zero (prevents "memory" on flip)
        if error * self.previous_error < 0:
            self.integral = 0.0

        # Proportional
        p_term = self.kp * error

        # Integral with anti-windup
        self.integral += error * dt
        self.integral = max(-2.0, min(2.0, self.integral))
        i_term = self.ki * self.integral

        # Derivative
        derivative = (error - self.previous_error) / dt if dt > 0 else 0.0
        d_term = self.kd * derivative

        self.previous_error = error

        return p_term + i_term + d_term


# ------------------------------------------------------
# PID Attacker
# ------------------------------------------------------
class PIDAttacker:
    def __init__(self):
        self.url = "http://localhost:3000"
        self.headless = False
        self.driver = None
        self.pid = PIDController()
        self.current_mouse_x = None

    # --------------------------------------------------
    def setup(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1000,800")

        if self.headless:
            options.add_argument("--headless=new")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

        # LOGIN
        try:
            logger.info("Attempting login...")
            email = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email.send_keys("bot@pid.sys")

            self.driver.find_element(By.ID, "password").send_keys("access_code_123")
            self.driver.find_element(By.ID, "loginBtn").click()

            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "gameCanvas"))
            )

            logger.info("Login successful.")
            time.sleep(1)

        except Exception as e:
            logger.info(f"Login skipped or already in game: {e}")

    # --------------------------------------------------
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

    # --------------------------------------------------
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

    # --------------------------------------------------
    def start_game(self):
        try:
            self.driver.find_element(By.ID, "gameCanvas").click()
            time.sleep(0.2)
            return True
        except:
            return False

    # --------------------------------------------------
    def verify(self):
        logger.info("Attempting verification button click...")

        try:
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.ID, "verifyBtn"))
                )
                button.click()
            except:
                logger.warning("Normal click failed → using JS click fallback.")
                button = self.driver.find_element(By.ID, "verifyBtn")
                self.driver.execute_script("arguments[0].click();", button)

            time.sleep(1)

            result = self.driver.find_element(By.ID, "resultTitle").text
            logger.info(f"Result: {result}")

            # print stabilization time
            try:
                final_time = float(
                    self.driver.find_element(By.ID, "timeDisplay").text.replace("s", "")
                )
                logger.info(f"Final Stabilization Time: {final_time:.2f} seconds")
            except:
                logger.info("Could not read final stabilization time.")

            return "VERIFIED" in result

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    # --------------------------------------------------
    def attack(self):
        logger.info("=== PID ATTACK STARTED ===")
        self.setup()

        try:
            if not self.start_game():
                logger.error("Could not start game.")
                return False

            canvas = self.driver.find_element(By.ID, "gameCanvas")
            width = canvas.size["width"]
            center_x = width / 2
            self.current_mouse_x = center_x

            start_time = time.time()
            last_loop_time = start_time

            # ---- CONTROL PARAMETERS ----
            MAX_OUTPUT = 150.0  # max pixel offset from center
            DANGER_ZONE = math.radians(25)  # > ~25° → emergency control

            # -------- OPTIMIZED PID LOOP --------
            while True:
                state = self.get_state()
                if not state:
                    break

                now = time.time()
                elapsed = now - start_time
                dt = now - last_loop_time
                last_loop_time = now

                if elapsed > 6:
                    break

                angle = state["angle"]
                angle_deg = state["angle_deg"]

                # EMERGENCY: angle too large → strong correction
                if abs(angle) > DANGER_ZONE:
                    control = -MAX_OUTPUT if angle > 0 else MAX_OUTPUT
                    logger.info(
                        f"[EMERGENCY] angle={angle_deg:.2f}°, forcing control={control:.2f}"
                    )
                else:
                    # Normal PID output around 0 (center balance)
                    control = self.pid.update(angle, dt=dt if dt > 0 else 1/60)
                    # Clamp output so we don't slam to edges
                    control = max(-MAX_OUTPUT, min(MAX_OUTPUT, control))

                # Target is center + control offset
                target = center_x + control
                target = max(30, min(width - 30, target))

                self.move_mouse(target)
                cart_x = self.current_mouse_x

                # Telemetry
                logger.info(
                    f"[ANGLE={angle_deg:.2f}°] "
                    f"[PID={control:.2f}] "
                    f"[TARGET={target:.2f}] "
                    f"[CART={cart_x:.2f}] "
                    f"[t={elapsed:.2f}s]"
                )

                time.sleep(1/60)

            time.sleep(1)

            # VERIFY RESULT
            return self.verify()

        finally:
            if self.driver:
                self.driver.quit()


# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
if __name__ == "__main__":
    PIDAttacker().attack()
