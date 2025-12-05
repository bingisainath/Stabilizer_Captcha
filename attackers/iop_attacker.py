"""
Interoperability Code to Attack Group 22 & 23
This Python script automates the solving of visual-semantic CAPTCHAs

Authors: Sai Ruthwik Thummurugoti (thummurs), Sainath Bingi (bingis) and Aniket Mishra (mishraa1)
"""
import time, io, re, os
from PIL import Image
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EDGE_DRIVER_PATH = os.environ.get("EDGE_DRIVER_PATH")
CAPTCHA_URL = "http://localhost:8080/"
MAX_RETRIES = 5  


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.5-pro")

def setup_driver():
    options = Options()
    options.use_chromium = True
    service = Service(executable_path=EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
    driver.maximize_window()
    return driver

def capture_screenshot(driver):
    """Capture full page screenshot as PIL Image."""
    png = driver.get_screenshot_as_png()
    return Image.open(io.BytesIO(png))

def semantic_validator(answer_text, driver):
    """Check Gemini output against CAPTCHA rules before submission."""
    token_word = driver.find_element(By.ID, "tokenText").text.strip()
    print(f"[Validator] Token word from page: '{token_word}'")
    print(f"[Validator] Answer length: {len(answer_text)} characters")

    if len(answer_text) < 25:
        print("[Validator] FAIL: Answer too short.")
        return False
    if token_word and token_word.lower() not in answer_text.lower():
        print(f"[Validator] FAIL: Token word '{token_word}' missing.")
        return False
    print("[Validator] PASS: Answer includes token and meets checks.")
    return True

def run_textbox_captcha(driver):
    print("Running textbox CAPTCHA...")

    screenshot = capture_screenshot(driver)
    prompt_text = driver.find_element(By.CSS_SELECTOR, "div.prompt").text.strip()
    print(f"[Prompt] Extracted prompt text: {prompt_text}")

    token_word = driver.find_element(By.ID, "tokenText").text.strip()

    gemini_prompt = (
        f"You are solving a visual CAPTCHA. The page prompt is:\n\n{prompt_text}\n\n"
        f"IMPORTANT:\n"
        f"- You MUST include the token word: {token_word}\n"
        "- Write a natural, human-like paragraph (>=25 characters) connecting Image A and B.\n"
        "- End your response ONLY with this format:\n"
        "ANSWER: <your paragraph>\n"
        "Do not output anything else."
    )
    try:
        response = model.generate_content([screenshot, gemini_prompt])
        response_text = response.text.strip()
    except Exception as e:
        print(f"[Gemini failed: {e}]")
        return False

    print(f"[Gemini] Full response:\n{response_text}\n")

    match = re.search(r"answer:\s*(.+)", response_text, re.IGNORECASE)
    if match:
        answer_text = match.group(1).strip()
    else:
        print("[Gemini] Did not follow format; using full response.")
        answer_text = response_text.strip()

    print(f"[Gemini] Parsed answer: {answer_text}")

    if not semantic_validator(answer_text, driver):
        return False

    try:
        editor = driver.find_element(By.ID, "editor")
        driver.execute_script("arguments[0].innerText = '';", editor)
        editor.send_keys(answer_text)
        driver.find_element(By.ID, "submitBtn").click()
        print("[Submit] Answer typed and submitted.")


        try:
            ov_title = driver.find_element(By.ID, "ovTitle").text
            ov_msg = driver.find_element(By.ID, "ovMsg").text
            print(f"[Overlay] Title: {ov_title}, Message: {ov_msg}")
        except Exception:
            print("[Overlay] No feedback overlay detected.")

        return True
    except Exception as e:
        print(f"[Submit failed: {e}]")
        return False

def click_retry_if_popup(driver):
    """Check if overlay popup is visible and click Retry if present."""
    try:
        overlay = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.ID, "overlay"))
        )
        retry_btn = overlay.find_element(By.ID, "retryBtn")
        if retry_btn.is_displayed():
            print("[Retry] Popup detected, clicking...")
            try:
                retry_btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", retry_btn)

            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located((By.ID, "overlay"))
            )
            time.sleep(2)
            return True
    except TimeoutException:
        return False
    except Exception as e:
        print(f"[Retry] Popup handling failed: {e}")
        return False
    return False

def main():
    driver = setup_driver()
    try:
        driver.get(CAPTCHA_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "editor"))
        )
        print("CAPTCHA page loaded.")

        round_num = 1
        while round_num <= MAX_RETRIES:
            print(f"\nROUND {round_num}")
            run_textbox_captcha(driver)
            time.sleep(3)

            if click_retry_if_popup(driver):
                round_num += 1
                continue
            else:
                print("No retry popup visible, ending loop.")
                break

        time.sleep(5)
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()