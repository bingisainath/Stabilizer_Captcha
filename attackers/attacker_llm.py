"""
LLM Vision Attacker - Updated for Auth & New HTML
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

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMVisionAttacker:
    def __init__(self, url="http://localhost:3000", api_key=None, headless=False):
        self.url = url
        self.driver = None
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.headless = headless
        
        if not self.api_key: raise ValueError("OPENAI_API_KEY required")
        if not OPENAI_AVAILABLE: raise ImportError("openai package not installed")
        
        self.client = OpenAI(api_key=self.api_key)
        self.decision_history = []
        
    def setup(self):
        options = webdriver.ChromeOptions()
        if self.headless: options.add_argument('--headless=new')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1000,900') # Slightly larger for centering
        options.add_argument('--no-sandbox')
        options.add_argument('--log-level=3')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        
        # AUTOMATED LOGIN
        try:
            logger.info("Attempting login...")
            WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.ID, "email"))).send_keys("ai_vision@bot.com")
            self.driver.find_element(By.ID, "password").send_keys("gpt4_vision")
            self.driver.find_element(By.ID, "loginBtn").click()
            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, "gameCanvas")))
            time.sleep(1)
        except Exception:
            logger.info("Login skipped (maybe already logged in)")
    
    def capture_screenshot(self):
        try:
            # Locate canvas element specifically to crop correctly
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            screenshot = self.driver.get_screenshot_as_png()
            image = Image.open(BytesIO(screenshot))
            
            # Calculate exact canvas position
            location = canvas.location
            size = canvas.size
            pixel_ratio = self.driver.execute_script("return window.devicePixelRatio")
            
            left = location['x'] * pixel_ratio
            top = location['y'] * pixel_ratio
            right = left + (size['width'] * pixel_ratio)
            bottom = top + (size['height'] * pixel_ratio)
            
            cropped = image.crop((left, top, right, bottom))
            
            buffered = BytesIO()
            cropped.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None
    
    def get_game_state(self):
        try:
            angle_text = self.driver.find_element(By.ID, "angleDisplay").text
            angle = float(angle_text.replace("°", ""))
            time_val = float(self.driver.find_element(By.ID, "timeDisplay").text.replace("s", ""))
            return {'angle': angle, 'time': time_val}
        except: return None
    
    def ask_gpt4_vision(self, screenshot_b64, game_state, previous_decisions):
        context = ""
        if previous_decisions:
            recent = previous_decisions[-3:]
            context = "Recent: " + ", ".join([f"Ang={d['angle']}->Act={d['action']}" for d in recent])
        
        prompt = f"""Inverted Pendulum Game. Keep the red pole UPRIGHT.
State: Angle {game_state['angle']:.1f}° (0 is perfect), Time {game_state['time']:.1f}s.
{context}

Goal: Move cart LEFT or RIGHT to balance pole.
Output JSON only: {{ "movement_pixels": <int -80 to 80>, "reasoning": "str" }}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                    ]
                }],
                max_tokens=100
            )
            import json
            txt = response.choices[0].message.content.strip()
            if "```" in txt: txt = txt.split("```json")[-1].split("```")[0]
            return json.loads(txt.strip())
        except:
            return {"movement_pixels": game_state['angle'] * 3, "reasoning": "Fallback"}

    def move_mouse(self, x_pos):
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            width = canvas.size['width']
            x_pos = max(0, min(width, x_pos))
            ActionChains(self.driver).move_to_element_with_offset(canvas, x_pos - width/2, 0).perform()
        except: pass

    def attack(self):
        self.setup()
        try:
            canvas = self.driver.find_element(By.ID, "gameCanvas")
            canvas.click() # Start game
            
            cart_pos = 300
            start = time.time()
            
            while time.time() - start < 6:
                state = self.get_game_state()
                if not state: break
                
                # Sample every 10 frames (GPT is slow)
                img = self.capture_screenshot()
                decision = self.ask_gpt4_vision(img, state, self.decision_history)
                
                move = decision.get('movement_pixels', 0)
                cart_pos += move
                self.move_mouse(cart_pos)
                self.decision_history.append({'angle': state['angle'], 'action': move})
                
                logger.info(f"GPT Action: {move}px | Angle: {state['angle']}°")
            
            time.sleep(1)
            # Verification
            verify = self.driver.find_element(By.ID, "verifyBtn")
            if verify.is_displayed():
                verify.click()
                time.sleep(2)
                res = self.driver.find_element(By.ID, "resultTitle").text
                if "VERIFIED" in res:
                    logger.info("✓ PASSED")
                    return True
            logger.warning("✗ FAILED")
            return False
            
        except Exception as e:
            logger.error(e)
            return False
        finally:
            if self.driver: self.driver.quit()

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    LLMVisionAttacker(url=url).attack()