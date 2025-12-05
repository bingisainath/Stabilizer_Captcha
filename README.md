# STEPS TO RUN THE PROJECT

## System Requirements

In order to run this demo successfully, you have to install the following in your testing machine:

- Python 3.9+ (Required)
- Selenium (Prerequisite to the Selenium-based attackers)
- Terminal/Shell (Bash or Zsh)

## Setup & Configuration

### Set up Environment Variables

This is an env.example file that is located in the root. You should find a way of creating a .env file in which you put the required API keys.

Copy the example file:

```bash
cp .env.example .env
```

Paste your Google Gemini API Key:

```bash
open .env
GEMINIAPIKEY=youractualapikeyhere
```

The automation script will automatically avoid the AI part of the demo by skipping the addition of the GEMINIAPIKEY.

### Make Script Executable

Make sure that the automation script is allowed to execute:

```bash
chmod +x auto.sh
```

## Execution Instructions

The whole process is automated by just one shell script which is auto.sh. This script takes care of the creation of the virtual environment, dependency installation, server management, and execution of the attacker.

To execute the entire demonstration:

```bash
./auto.sh
```

### So what is the result of running this script?

The following actions are automatically done in the script:

- **Bootstraps Environment:** Verifies Python 3.9+ and builds .venv and installs dependencies.
- **Starts Server:** Starts Flask backend program in the background (Port 3000).
- **Runs Attacks:** This is a sequence of bot scripts directly launched at the live server.
- **Cleanup:** Closes the server and processes automatically upon its completion.

# Run the Server Manually

Once the virtual environment is enabled, you can run the server manually:

```bash
python app.py
```

The server will start on Port 3000 at localhost.

## Expectation Results and Demo Walkthrough

The script will take you through three scenarios of attacks. The following is what you are to seek:

### Phase 1: The Mechanical Bot (PID Controller)

**What it does:** It is a bot that calculates perfect balance by using mathematical formulas.

**Behavior:** The cursor is going to move smoothly, and the pole will stay upright in its entirety within 5 seconds.

**Defense Mechanism:** "Reflex Trap defense mechanism"

**Anticipated Analysis:** FAILURE to verify. The server realizes that the reaction time is superhuman (0-frame lag) and refuses to allow the session despite the faultlessness.

### Phase 2: The Learned Bot (Reinforcement Learning)

**What it does:** A Q-Learning agent which is trained in the standard game physics.

**Behavior:** It is expected that the pole will be crashed by the bot in 1-2 seconds.

**Defence Mechanism:** Dynamic Chaos.

**Expected Result:** CRASH. Each time the user has a session, the server selects the gravity and pole length. The pre-trained memory of the AI (q_table.pkl) is not compatible with the existing physics and therefore fails.

### Phase 3: The Vision AI (Google Gemini)

**What it does:** Multimodal LLM, which is able to see the screen and command the mouse.

**Behavior:** The cursor will move in a jerky fashion and the pole will swing around and fall down.

**Defense Regularity:** The OODA Loop Latency.

**Expected Result:** CRASH. The processing delay (Image Capture - API Upload - Inference - Action) is a delay of over 200ms. This lag is something that cannot allow this system to stabilize (an inverted pendulum is an unstable system).

## Team & Contributions

This was a partnership project and every team member contributed his or her individual proficiency:

### Individual Contributions

- **Front-End Pyla:** Interface Construction & ShellScripting.
- **Jai Mangesh Nagle:** Raspberry Pi and Back-end Architecture.
- **Sainath Bingi:** Reinforcement Learning Attacker and IOP-Attacker.
- **Sai Ruthwik Thummurugoti:** IOP-Attacker PID Controller Attacker.
- **Aniket Mishra:** LLM Vision Attacker/IOP-Attacker.
