# ⚛️ Reactor Stabilizer CAPTCHA

## 📋 Overview

This project implements a novel "Embodied Cognition" CAPTCHA verification system. Unlike standard CAPTCHAs that test knowledge (e.g., "select the traffic lights"), this system verifies humanity by testing motor control agency and reaction latency.

The enclosed demonstration proves the system's security by launching three distinct automated attacks against the CAPTCHA, showcasing how specific defense mechanisms defeat different types of bots (Mathematical, Reinforcement Learning, and Generative AI).

## 💻 System Requirements

To execute this demo successfully, the following must be installed on your testing machine:

1. **Python 3.9+** (Required)
2. **Google Chrome** (Required for the Selenium-based attackers)
3. **Terminal/Shell** (Bash or Zsh)

## ⚙️ Setup & Configuration

### 1. Configure Environment Variables

A `.env.example` file is provided in the root directory. You must create a `.env` file to store the necessary API keys.

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and paste your Google Gemini API Key:
   ```
   GEMINI_API_KEY=your_actual_api_key_here
   SECRET_KEY=any_random_string
   ```

> **Note:** If you skip adding the `GEMINI_API_KEY`, the automation script will gracefully skip the AI Vision portion of the demo.

### 2. Make Script Executable

Ensure the automation script has permission to run:

```bash
chmod +x auto.sh
```

## 🚀 Execution Instructions

A single shell script, `auto.sh`, automates the entire process. This script handles the virtual environment creation, dependency installation, server management, and attacker execution.

To run the full demonstration:

```bash
./auto.sh
```

### What happens when you run this script?

The script performs the following actions automatically:

1. **Bootstraps Environment:** Checks for Python 3.11, creates a `.venv`, and installs dependencies.
2. **Starts Server:** Launches the Flask backend application in the background (Port 3000).
3. **Runs Attacks:** Sequentially launches three different bot scripts against the live server.
4. **Cleanup:** Automatically shuts down the server and processes when finished.

## 🧪 Demo Walkthrough & Expected Results

The script will guide you through three attack scenarios. Here is what you should look for:

### Phase 1: The Mechanical Bot (PID Controller)

**What it is:** A scripted bot using mathematical formulas to calculate perfect balance.

**Behavior:** The cursor will move smoothly, and the pole will remain perfectly upright for 5 seconds.

**Defense Mechanism:** "The Reflex Trap"

**Expected Result:** ❌ VERIFICATION FAILED. The server detects that the reaction time is "superhuman" (0-frame lag) and rejects the session despite perfect performance.

---

### Phase 2: The Learned Bot (Reinforcement Learning)

**What it is:** A Q-Learning AI agent trained on the standard game physics.

**Behavior:** The bot will likely crash the pole within 1-2 seconds.

**Defense Mechanism:** "Dynamic Chaos"

**Expected Result:** ❌ CRASH. The server randomizes gravity and pole length for every session. The AI's pre-trained memory (`q_table.pkl`) does not match the current physics, causing it to fail.

---

### Phase 3: The Vision AI (Google Gemini)

**What it is:** A Multimodal LLM that "sees" the game screen and instructs the mouse.

**Behavior:** The cursor will move jerkily, and the pole will oscillate wildly before falling.

**Defense Mechanism:** "The OODA Loop Latency"

**Expected Result:** ❌ CRASH. The processing time (Image Capture → API Upload → Inference → Action) introduces a >200ms delay. In an unstable system like an inverted pendulum, this lag makes stabilization impossible.

## ❓ Troubleshooting

- **"Python not found":** Ensure `python3` points to Python 3.11. If your python executable is named differently (e.g., `python3.11`), you may need to edit line 23 of `auto.sh`.

- **"Chromedriver error":** Ensure Google Chrome is installed. Selenium usually manages the driver automatically, but a very old version of Chrome may cause issues.

- **"Gemini Skipped":** If the script says "SKIPPING: GEMINI_API_KEY not set", please verify your `.env` file exists and contains the key.

## 📝 License

[Add your license information here]

## 👤 Author

**Student:** [Your Name]  
**Course:** [Course Name]