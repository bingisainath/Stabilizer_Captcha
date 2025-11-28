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
import json
# --------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
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
        # Using the standard stable vision model. 
        # Replace with "gemini-1.5-flash-latest" if you prefer.
        self.model = genai.GenerativeModel("gemini-2.5-flash") 

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

            # Return raw bytes for the Gemini API
            return buf.getvalue()

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
    def ask_gemini_vision(self, screenshot_bytes, state, history):
        context = ""
        if history:
            last = history[-3:]
            context = "Recent: " + ", ".join([f"A={h['angle']}→M={h['action']}" for h in last])

        prompt = f"""
You are controlling an inverted pendulum (balancing pole game).
Current State: Angle: {state['angle']:.1f}°, Time: {state['time']:.1f}s
Goal: Output JSON ONLY → {{ "movement_pixels": -80 to +80, "reasoning": "short text" }}
Do NOT output anything outside the JSON.
{context}
"""

        try:
            image_part = {"mime_type": "image/png", "data": screenshot_bytes}
            response = self.model.generate_content(
                contents=[prompt, image_part],
                # gemini-pro-vision does not support JSON response_mime_type
                # generation_config={"response_mime_type": "application/json"},
                safety_settings={'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                                 'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                                 'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                                 'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'}
            )

            # Manually parse the JSON from the text response
            text_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(text_response)

        except Exception as e:
            logger.error(f"Gemini Vision Error: {e}")
            return {"movement_pixels": int(state['angle'] * 2.5), "reasoning": "Fallback"}

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

    # ----------------------- MAIN LOOP (HANDLES 3 ATTEMPTS) -----------------------
    def attack(self, max_attempts=3):
        """
        Main attack function that handles setup, the attempt loop, and retry logic.
        """
        self.setup()
        if not self.driver:
            logger.error("Driver not initialized. Aborting.")
            return False

        try:
            for i in range(max_attempts):
                logger.info(f"--- LAUNCHING ATTACK ATTEMPT {i + 1} of {max_attempts} ---")
                
                # Run one full attempt
                success = self._run_single_attempt() # This will return True/False

                if success:
                    # If we passed, log it and exit the function
                    logger.info("🎉 ATTACK SUCCESSFUL. CAPTCHA DEFEATED. (UNEXPECTED)")
                    return True

                # --- Handle Failure ---
                # Check if we are on the final attempt
                if i == max_attempts - 1:
                    # This was the last attempt, loop will break
                    logger.warning("Final attempt failed.")
                    break 
                
                # --- Handle Retry Logic (if not last attempt) ---
                logger.info("Attempt failed. Clicking 'TRY AGAIN'...")
                try:
                    # This clicks the "TRY AGAIN" button in the *result overlay*
                    retry_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='TRY AGAIN']"))
                    )
                    retry_btn.click()
                    
                    # Wait for the overlay to disappear and game to reset
                    WebDriverWait(self.driver, 5).until(
                        EC.invisibility_of_element_located((By.ID, "resultOverlay"))
                    )
                    # Wait for the "Ready" status to ensure new physics are loaded
                    WebDriverWait(self.driver, 5).until(
                        EC.text_to_be_present_in_element((By.ID, "status"), "REACTOR READY")
                    )
                    logger.info("Game reset. Preparing for next attempt.")
                    
                except Exception as e:
                    # This might fail if we were redirected to /failed early
                    logger.error(f"Could not click retry button. Checking for redirect... Error: {e}")
                    if "/failed" in self.driver.current_url:
                        logger.error("Max attempts reached early. Aborting loop.")
                        break # Exit loop
            
            # --- END OF LOOP ---
            # If we are here, all attempts have failed
            logger.error("All attack attempts failed. (EXPECTED RESULT)")
            
            # Check if we are on the /failed page
            if "/failed" in self.driver.current_url:
                logger.info("On /failed page. Clicking 'RETURN TO LOGIN'...")
                try:
                    # Find the button by its text and click it
                    return_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='RETURN TO LOGIN']"))
                    )
                    return_btn.click()
                    
                    # Wait for the login page to load (look for loginBtn)
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.ID, "loginBtn"))
                    )
                    logger.info("Successfully returned to login page.")
                    
                except Exception as e:
                    logger.error(f"Could not click 'RETURN TO LOGIN' button: {e}")
            
            return False # Return False as the attack failed
            
        finally:
            logger.info("Attack sequence finished. Quitting driver in 3 seconds...")
            time.sleep(3) # Keep browser open for 3s to see final action
            if self.driver:
                self.driver.quit()


    # ----------------------- SINGLE ATTEMPT LOGIC -----------------------
    def _run_single_attempt(self):
        """
        Runs one full attempt of the game, from click to verification.
        Returns True on success, False on failure.
        """
        try:
            # Find and click the canvas to start the game
            canvas = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.ID, "gameCanvas"))
            )
            # A small move to get the mouse in position before click
            ActionChains(self.driver).move_to_element(canvas).perform()
            time.sleep(0.1)
            canvas.click() # Starts the game
            logger.info("Game started. Engaging OODA control loop...")
            
            cart_x = 300 # Start at the center
            start = time.time()
            self.decision_history = [] # Clear history for this attempt

            while time.time() - start < 6.0: # Run for 6 seconds
                state = self.get_game_state()
                if not state:
                    logger.warning("Could not get game state, skipping frame.")
                    time.sleep(0.1)
                    continue

                # --- OODA LOOP ---
                # 1. Observe
                logger.info(f"OODA: Observe... (t={state['time']:.1f}s)")
                img_bytes = self.capture_screenshot()
                if not img_bytes:
                    logger.warning("Could not capture screenshot, skipping frame.")
                    time.sleep(0.1)
                    continue
                
                # 2. Orient & 3. Decide (This is the slow part)
                logger.info("OODA: Orient & Decide... (Calling Gemini API)")
                decision = self.ask_gemini_vision(img_bytes, state, self.decision_history)
                
                # Parse the AI's decision
                move = int(decision.get("movement_pixels", 0))
                reason = decision.get("reasoning", "No reasoning.")
                cart_x += move
                
                # 4. Act
                logger.info("OODA: Act! (Moving mouse)")
                self.move_mouse(cart_x)
                
                self.decision_history.append({"angle": state["angle"], "action": move})
                logger.info(f"==> [t={state['time']:.1f}s] Angle: {state['angle']:>5.1f}° | Gemini: {move:>3}px | Reason: {reason}")

                # --- FAIL-FAST CHECK ---
                # Check if the "resultOverlay" has appeared, which means we failed.
                try:
                    if self.driver.find_element(By.ID, "resultOverlay").is_displayed():
                        logger.warning("Game failure detected mid-loop. Breaking.")
                        break
                except:
                    pass # Overlay not visible, continue

            logger.info("Control loop finished. Waiting for final verification...")
            time.sleep(1) # Give JS time to process

            # --- ROBUST VERIFICATION LOGIC ---
            try:
                # Check for Case 1 (Failure) first
                if self.driver.find_element(By.ID, "resultOverlay").is_displayed():
                    logger.info("Failure case: Result overlay is already visible.")
                else:
                    # Case 2 (Success)
                    logger.info("Success case: Clicking 'verifyBtn'...")
                    verify_btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.ID, "verifyBtn"))
                    )
                    verify_btn.click()
            
            except Exception:
                # This can happen if the page is slow
                logger.warning("Could not find result overlay or verify button. Waiting...")
            
            # --- Final check for the result text ---
            # In both success or failure, the resultOverlay will appear. Wait for it.
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.ID, "resultOverlay"))
                )
                
                res = self.driver.find_element(By.ID, "resultTitle").text
                
                if "VERIFIED" in res or "SUCCESS" in res:
                    logger.info(f"✓ PASSED: {res}")
                    return True # Success
                else:
                    logger.warning(f"✗ FAILED: {res}")
                    return False # Failure
                    
            except Exception as e:
                logger.error(f"Could not determine final result: {e}")
                return False # Failure
            
        except Exception as e:
            logger.error(f"An error occurred during the attack attempt: {e}")
            return False # Failure

# ----------------------- MAIN ENTRY -----------------------
if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    
    # Create the attacker and call the new main attack loop
    attacker = LLMVisionAttacker(url=url, headless=False)
    attacker.attack(max_attempts=3)