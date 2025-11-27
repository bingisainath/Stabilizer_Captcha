# ⚛️ Reactor Stabilizer: Anti-AI CAPTCHA

**The Reactor Stabilizer** is a novel "Embodied Cognition" verification system designed to replace static CAPTCHAs. Instead of testing knowledge (identifying traffic lights), it tests **agency** and **closed-loop motor control**.

The user must balance an unstable reactor core (inverted pendulum) for 5 seconds. The system exploits the "Latency Gap" between biological neural networks (humans) and artificial neural networks (AI) to filter out bots.

---

## 🛡️ Why It Works (The Security Architecture)

This system defeats modern AI agents using three distinct layers of defense:

1.  **The "OODA Loop" Trap (Latency):**
    * **Humans:** Use predictive motor control (cerebellum) with sub-100ms adjustments.
    * **AI (Vision/LLMs):** Must Capture $\to$ Process $\to$ Infer $\to$ Act. This loop takes >200ms, causing "Pilot-Induced Oscillation" and failure.
    * *Result:* GPT-4 Vision and Selenium bots fail due to lag.

2.  **Dynamic Chaos (Anti-RL):**
    * The physics parameters (Gravity, Rod Length, Force Jolts) change randomly every few frames based on a server-generated "Chaos Schedule."
    * *Result:* Reinforcement Learning (Q-Learning) agents fail because they cannot adapt their policy to changing physics in real-time.

3.  **The "Reflex Trap" (Anti-PID):**
    * Mathematical bots (PID Controllers) correct errors instantly (1 frame lag).
    * The backend analyzes the user's reaction time. If the "Reflex Ratio" is superhuman (>90% instant corrections), the session is flagged as a bot.
    * *Result:* Scripted bots balance the rod perfectly but are rejected during verification.

---

## 🚀 Installation & Usage

### 1. Clone the Repository
```bash
git clone [https://github.com/thummurs/reactor-captcha.git](https://github.com/thummurs/reactor-captcha.git)
cd reactor-captcha
