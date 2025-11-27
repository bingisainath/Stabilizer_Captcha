"""
LLM Vision Attacker - Gemini Vision Version
Author: Your Name
"""

import time
import base64
import os
import logging
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image

# -------------------------- LOAD .ENV --------------------------
from dotenv import load_dotenv
load_dotenv()  # <-- loads GEMINI_API_KEY from .env
# ---------------------------------------------------------------

# ------------------- GEMINI IMPORT ----------------------------
import google.generativeai as genai
# --------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Gemini-Attacker")


class LLMVisionAttacker:
    def __init__(self, url="http://localhost:3000", api_key=None, headless=False):
        self.url = url
        self.driver = None
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.headless = headless

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY missing.\n"
                "Fix: Create .env file:\n"
                "GEMINI_API_KEY=YOUR_KEY_HERE"
            )

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash-vision")

        self.decision_history = []

    # ----------------------- SELENIUM SETUP -----------------------
    def setup(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1000,900")
        options.add_argument("--no-sandbox")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

        # Auto Login
        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.ID, "email"))
            ).send_keys("ai_vision@bot.com")

            self.driver.find_element(By.ID, "password").send_keys("gpt4_vision")
            self.driver.find_element(By.ID, "loginBtn").click()

            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "gameCanvas"))
            )
            time.sleep(1)

        except Exception:
            logger.info("Login skipped")

    # ----------------------- CAPTURE SCREENSHOT -----------------------
    def capture_screenshot(self):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(BytesIO(screenshot))

            # Crop exactly around canvas
            loc = canvas.location
            size = canvas.size
            dpr = self.driver.execute_script("return window.devicePixelRatio")

            left = loc['x'] * dpr
            top = loc['y'] * dpr
            right = left + size['width'] * dpr
            bottom = top + size['height'] * dpr

            cropped = img.crop((left, top, right, bottom))
            buf = BytesIO()
            cropped.save(buf, format="PNG")

            return base64.b64encode(buf.getvalue()).decode()

        except Exception as e:
            logger.error(f"Screenshot Error: {e}")
            return None

    # ----------------------- GAME STATE READ -----------------------
    def get_game_state(self):
        try:
            angle = float(self.driver.find_element(By.ID, "angleDisplay").text.replace("°", ""))
            t = float(self.driver.find_element(By.ID, "timeDisplay").text.replace("s", ""))
            return {"angle": angle, "time": t}
        except:
            return None

    # ----------------------- GEMINI DECISION -----------------------
    def ask_gemini_vision(self, screenshot_b64, state, history):
        context = ""
        if history:
            last = history[-3:]
            context = "Recent: " + ", ".join([f"A={h['angle']}→M={h['action']}" for h in last])

        prompt = f"""
You are controlling an inverted pendulum (balancing pole game).

Current State:
- Angle: {state['angle']:.1f}°
- Time: {state['time']:.1f}s

Goal:
Output JSON ONLY → format exactly like this:

{{
  "movement_pixels": -80 to +80,
  "reasoning": "short reasoning text"
}}

Do NOT output anything outside JSON.
{context}
"""

        try:
            response = self.model.generate_content(
                contents=[
                    prompt,
                    {"mime_type": "image/png",
                     "data": base64.b64decode(screenshot_b64)}
                ],
                generation_config={"response_mime_type": "application/json"}
            )

            import json
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Gemini Vision Error: {e}")
            return {"movement_pixels": state['angle'] * 2.5, "reasoning": "Fallback"}

    # ----------------------- MOVE MOUSE -----------------------
    def move_mouse(self, new_pos):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            width = canvas.size["width"]
            new_pos = max(0, min(width, new_pos))

            ActionChains(self.driver).move_to_element_with_offset(
                canvas, new_pos - width/2, 0
            ).perform()
        except:
            pass

    # ----------------------- MAIN LOOP -----------------------
    def attack(self):
        self.setup()

        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click()

            cart_x = 300
            start = time.time()

            while time.time() - start < 6:
                state = self.get_game_state()
                if not state:
                    break

                img = self.capture_screenshot()
                decision = self.ask_gemini_vision(img, state, self.decision_history)

                move = int(decision.get("movement_pixels", 0))
                cart_x += move

                self.move_mouse(cart_x)

                self.decision_history.append({
                    "angle": state["angle"],
                    "action": move
                })

                logger.info(f"[Gemini] Move: {move}px | Angle={state['angle']}°")

            # Verification
            time.sleep(1)
            self.driver.find_element(By.ID, "verifyBtn").click()
            time.sleep(1)

            result = self.driver.find_element(By.ID, "resultTitle").text
            if "VERIFIED" in result:
                logger.info("🎉 CAPTCHA PASSED")
                return True

            logger.info("❌ CAPTCHA FAILED")
            return False

        except Exception as e:
            logger.error(f"Attack Error: {e}")
            return False

        finally:
            if self.driver:
                self.driver.quit()


# ----------------------- MAIN ENTRY -----------------------
if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    LLMVisionAttacker(url=url).attack()
