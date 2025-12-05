"""
A sophisticated script that uses Google's Gemini API to "see" the game screen and make decisions. It tests the "Latency Gap" defense, as the time taken to process the image usually causes the bot to crash.
Authors: Aniket Mishra (mishraa1)
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

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
import json


logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("Gemini-Attacker")


class LLMVisionAttacker:
    def __init__(self, url="http://127.0.0.1:3000", api_key=None, headless=False):
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

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash") 

        self.decision_history = []

    def setup(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1000,900")
        options.add_argument("--no-sandbox")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)

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

    def capture_screenshot(self):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(BytesIO(screenshot))

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

            return buf.getvalue()

        except Exception as e:
            logger.error(f"Screenshot Error: {e}")
            return None

    def get_game_state(self):
        try:
            angle = float(self.driver.find_element(By.ID, "angleDisplay").text.replace("°", ""))
            t = float(self.driver.find_element(By.ID, "timeDisplay").text.replace("s", ""))
            return {"angle": angle, "time": t}
        except:
            return None

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
                safety_settings={'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                                 'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                                 'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                                 'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'}
            )

            text_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(text_response)

        except Exception as e:
            logger.error(f"Gemini Vision Error: {e}")
            return {"movement_pixels": int(state['angle'] * 2.5), "reasoning": "Fallback"}

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

    def attack(self, max_attempts=3):
        self.setup()
        if not self.driver:
            logger.error("Driver not initialized. Aborting.")
            return False

        try:
            for i in range(max_attempts):
                logger.info(f"--- LAUNCHING ATTACK ATTEMPT {i + 1} of {max_attempts} ---")
                
                success = self._run_single_attempt()

                if success:
                    logger.info(" ATTACK SUCCESSFUL. CAPTCHA DEFEATED. (UNEXPECTED)")
                    return True

                if i == max_attempts - 1:
                    logger.warning("Final attempt failed.")
                    break 
                

                logger.info("Attempt failed. Clicking 'TRY AGAIN'...")
                try:
                    retry_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='TRY AGAIN']"))
                    )
                    retry_btn.click()
                    
                    WebDriverWait(self.driver, 5).until(
                        EC.invisibility_of_element_located((By.ID, "resultOverlay"))
                    )
                    WebDriverWait(self.driver, 5).until(
                        EC.text_to_be_present_in_element((By.ID, "status"), "REACTOR READY")
                    )
                    logger.info("Game reset. Preparing for next attempt.")
                    
                except Exception as e:
                    logger.error(f"Could not click retry button. Checking for redirect... Error: {e}")
                    if "/failed" in self.driver.current_url:
                        logger.error("Max attempts reached early. Aborting loop.")
                        break
            
            logger.error("All attack attempts failed. (EXPECTED RESULT)")
            
            if "/failed" in self.driver.current_url:
                logger.info("On /failed page. Clicking 'RETURN TO LOGIN'...")
                try:
                    return_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='RETURN TO LOGIN']"))
                    )
                    return_btn.click()
                    
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.ID, "loginBtn"))
                    )
                    logger.info("Successfully returned to login page.")
                    
                except Exception as e:
                    logger.error(f"Could not click 'RETURN TO LOGIN' button: {e}")
            
            return False
            
        finally:
            logger.info("Attack sequence finished. Quitting driver in 3 seconds...")
            time.sleep(3)
            if self.driver:
                self.driver.quit()


    def _run_single_attempt(self):
        try:
            canvas = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.ID, "gameCanvas"))
            )
            ActionChains(self.driver).move_to_element(canvas).perform()
            time.sleep(0.1)
            canvas.click()
            logger.info("Game started. Engaging OODA control loop...")
            
            cart_x = 300 
            start = time.time()
            self.decision_history = [] 

            while time.time() - start < 6.0: 
                state = self.get_game_state()
                if not state:
                    logger.warning("Could not get game state, skipping frame.")
                    time.sleep(0.1)
                    continue

                logger.info(f"OODA: Observe... (t={state['time']:.1f}s)")
                img_bytes = self.capture_screenshot()
                if not img_bytes:
                    logger.warning("Could not capture screenshot, skipping frame.")
                    time.sleep(0.1)
                    continue
                
                logger.info("OODA: Orient & Decide... (Calling Gemini API)")
                decision = self.ask_gemini_vision(img_bytes, state, self.decision_history)
                
                move = int(decision.get("movement_pixels", 0))
                reason = decision.get("reasoning", "No reasoning.")
                cart_x += move
                

                logger.info("OODA: Act! (Moving mouse)")
                self.move_mouse(cart_x)
                
                self.decision_history.append({"angle": state["angle"], "action": move})
                logger.info(f"==> [t={state['time']:.1f}s] Angle: {state['angle']:>5.1f}° | Gemini: {move:>3}px | Reason: {reason}")


                try:
                    if self.driver.find_element(By.ID, "resultOverlay").is_displayed():
                        logger.warning("Game failure detected mid-loop. Breaking.")
                        break
                except:
                    pass 

            logger.info("Control loop finished. Waiting for final verification...")
            time.sleep(1) 


            try:
                if self.driver.find_element(By.ID, "resultOverlay").is_displayed():
                    logger.info("Failure case: Result overlay is already visible.")
                else:
                    logger.info("Success case: Clicking 'verifyBtn'...")
                    verify_btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.ID, "verifyBtn"))
                    )
                    verify_btn.click()
            
            except Exception:
                logger.warning("Could not find result overlay or verify button. Waiting...")
        
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.ID, "resultOverlay"))
                )
                
                res = self.driver.find_element(By.ID, "resultTitle").text
                
                if "VERIFIED" in res or "SUCCESS" in res:
                    logger.info(f"✓ PASSED: {res}")
                    return True 
                else:
                    logger.warning(f"✗ FAILED: {res}")
                    return False 
                    
            except Exception as e:
                logger.error(f"Could not determine final result: {e}")
                return False 
            
        except Exception as e:
            logger.error(f"An error occurred during the attack attempt: {e}")
            return False 


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
    

    attacker = LLMVisionAttacker(url=url, headless=False)
    attacker.attack(max_attempts=3)