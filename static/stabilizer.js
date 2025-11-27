/**
 * REACTOR STABILIZER - Physics Engine & Logic
 */

// ==================== CONFIGURATION ====================
const CONFIG = {
  canvasWidth: 600,
  canvasHeight: 400,
  cartWidth: 80,
  cartHeight: 20,
  failAngle: 1.4, 
  successFrames: 300, 
  fps: 60,
  dampingFactor: 0.985, 
  cartForceMultiplier: 0.15,
  poleColor: "#ff3333",
  poleSuccessColor: "#00ff41",
  cartColor: "#555555",
  pivotColor: "#ffcc00",
  groundColor: "#222222",
};

// ==================== GAME STATE ====================
let state = {
  initialized: false,
  running: false,
  gameOver: false,
  success: false,
  sessionToken: null,
  schedule: null,
  poleAngle: 0.05,
  angularVelocity: 0,
  cartX: CONFIG.canvasWidth / 2,
  cartVelocity: 0,
  prevCartX: CONFIG.canvasWidth / 2,
  mouseX: CONFIG.canvasWidth / 2,
  mouseInCanvas: false,
  frameCount: 0,
  angleHistory: [],
  currentGravity: 0.5,
  currentLength: 100,
  currentJolt: 0,
};

// ==================== DOM ELEMENTS ====================
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const timeDisplay = document.getElementById("timeDisplay");
const angleDisplay = document.getElementById("angleDisplay");
const attemptsDisplay = document.getElementById("attemptsDisplay");
const clickPrompt = document.getElementById("clickPrompt");
const verifyBtn = document.getElementById("verifyBtn");
const retryBtn = document.getElementById("retryBtn");

// ==================== INITIALIZATION ====================
async function initGame() {
  try {
    statusEl.className = "loading";
    statusEl.textContent = "LOADING CHAOS PARAMETERS...";

    const response = await fetch("/init_stabilizer");
    const data = await response.json();

    // CHECK FOR LOCKOUT
    if (data.error === 'MAX_ATTEMPTS_EXCEEDED' && data.redirect) {
        window.location.href = data.redirect;
        return;
    }

    if (!data.success) {
      throw new Error("Failed to initialize");
    }

    // UPDATE UI WITH ATTEMPTS LEFT
    if (attemptsDisplay && data.attempts_left !== undefined) {
        attemptsDisplay.textContent = "Attempts Left: " + data.attempts_left;
        if(data.attempts_left <= 1) attemptsDisplay.style.color = "#ff3333";
    }

    state.sessionToken = data.session_token;
    state.schedule = data.schedule;
    state.initialized = true;

    statusEl.className = "ready";
    statusEl.textContent = "REACTOR READY // AWAITING OPERATOR";
    clickPrompt.style.display = "block";

    // Hide retry button on fresh init
    if(retryBtn) retryBtn.classList.remove("visible");

    requestAnimationFrame(gameLoop);
  } catch (error) {
    console.error("Initialization error:", error);
    statusEl.className = "failed";
    statusEl.textContent = "SYSTEM ERROR";
  }
}

// ==================== PHYSICS ENGINE ====================
function updatePhysics() {
  if (!state.running || state.gameOver) return;

  const frame = Math.min(state.frameCount, state.schedule.gravity.length - 1);
  state.currentGravity = state.schedule.gravity[frame];
  state.currentLength = state.schedule.length[frame];
  state.currentJolt = state.schedule.force_jolts[frame];

  const cartAcceleration = state.cartX - state.prevCartX;
  state.prevCartX = state.cartX;

  const gravityTorque = (state.currentGravity / state.currentLength) * Math.sin(state.poleAngle);
  const inertialTorque = ((-CONFIG.cartForceMultiplier * cartAcceleration) / state.currentLength) * Math.cos(state.poleAngle);
  const angularAcceleration = gravityTorque + inertialTorque + state.currentJolt;

  state.angularVelocity += angularAcceleration;
  state.angularVelocity *= CONFIG.dampingFactor;
  state.poleAngle += state.angularVelocity;

  state.angleHistory.push(state.poleAngle);
  state.frameCount++;

  if (Math.abs(state.poleAngle) > CONFIG.failAngle) {
    endGame(false);
  } else if (state.frameCount >= CONFIG.successFrames) {
    endGame(true);
  }
}

// ==================== INPUT HANDLING ====================
function setupInputHandlers() {
  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    state.mouseX = e.clientX - rect.left;
    state.mouseInCanvas = true;
  });

  canvas.addEventListener("mouseleave", () => {
    state.mouseInCanvas = false;
  });

  canvas.addEventListener("click", () => {
    if (state.mouseX === 0 && state.prevCartX === 0) return;
    if (state.initialized && !state.running && !state.gameOver) {
      startGame();
    }
  });

  // verifyBtn is only used for manual success verification
  if(verifyBtn) verifyBtn.addEventListener("click", verifyHuman);
}

function startGame() {
  state.cartX = state.mouseX;
  state.prevCartX = state.mouseX;
  state.poleAngle = 0.05 * (Math.random() > 0.5 ? 1 : -1);
  state.angularVelocity = 0;
  state.frameCount = 0;
  state.angleHistory = [];
  state.running = true;
  state.gameOver = false;
  state.success = false;

  clickPrompt.style.display = "none";
  statusEl.className = "active";
  statusEl.textContent = "STABILIZATION IN PROGRESS...";
  
  if(retryBtn) retryBtn.classList.remove("visible");
}

// ==================== GAME FLOW ====================
function endGame(success) {
  state.running = false;
  state.gameOver = true;
  state.success = success;

  if (success) {
    // Success Case: User clicks button to confirm
    statusEl.className = "success";
    statusEl.textContent = "STABILIZED // VERIFICATION REQUIRED";
    verifyBtn.classList.add("visible");
  } else {
    // Failure Case: AUTOMATICALLY REPORT FAILURE TO SERVER
    statusEl.className = "failed";
    statusEl.textContent = "CRITICAL FAILURE // SYNCING WITH SERVER...";
    
    // Call verifyHuman immediately to register the failure and decrement attempts
    verifyHuman(); 
  }
}

async function verifyHuman() {
  if(verifyBtn) verifyBtn.classList.remove("visible");
  
  // If this was a success run, show analyzing. If failure, we are just syncing.
  if (state.success) {
      statusEl.textContent = "ANALYZING BIOMETRIC SIGNATURE...";
  }

  try {
    const response = await fetch("/verify_stability", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_token: state.sessionToken,
        angle_history: state.angleHistory,
      }),
    });

    const data = await response.json();

    // 1. PRINT METRICS TO CONSOLE
    if (data.metrics) {
        console.group("%c 🧬 VERIFICATION METRICS ", "background: #222; color: #00ffff; font-size: 14px");
        console.log(`%c Human Probability: ${data.metrics.human}% `, "color: #00ff41; font-weight: bold;");
        console.log(`%c AI Probability:    ${data.metrics.ai}% `, "color: #ff3333; font-weight: bold;");
        console.groupEnd();
    }

    // 2. REAL-TIME ATTEMPTS UPDATE
    // This will now update immediately after the pole drops
    if (data.attempts_left !== undefined) {
        if (attemptsDisplay) {
            attemptsDisplay.textContent = "Attempts Left: " + data.attempts_left;
            if (data.attempts_left <= 1) attemptsDisplay.style.color = "#ff3333";
        }
    }

    if (data.verified) {
      // SUCCESS REDIRECT
      window.location.href = data.redirect || "/success";
    } else {
      // FAILURE REDIRECT (LOCKOUT)
      if (data.redirect) {
          window.location.href = data.redirect;
          return;
      }

      // SHOW RESULT OVERLAY
      if (typeof window.showResult === "function") {
        const msg = `${data.message}`; // Stats usually null on failure
        window.showResult(data.verified, msg, data.stats);
      }
      
      statusEl.className = "failed";
      statusEl.textContent = "VERIFICATION FAILED // REACTOR UNSTABLE";
      retryBtn.classList.add("visible");
    }
  } catch (error) {
    console.error("Verification error:", error);
    statusEl.className = "failed";
    statusEl.textContent = "NETWORK ERROR";
    retryBtn.classList.add("visible");
  }
}

async function resetGame() {
  state.initialized = false;
  state.running = false;
  state.gameOver = false;
  state.success = false;
  state.frameCount = 0;
  state.angleHistory = [];
  state.poleAngle = 0.05;
  state.angularVelocity = 0;
  state.cartX = CONFIG.canvasWidth / 2;
  state.prevCartX = CONFIG.canvasWidth / 2;

  verifyBtn.classList.remove("visible");
  retryBtn.classList.remove("visible");
  
  // Close result overlay
  const overlay = document.getElementById("resultOverlay");
  if(overlay) overlay.style.display = "none";

  await initGame();
}

// ==================== RENDERING ====================
function render() {
  // Clear
  ctx.fillStyle = "#0d0d0d";
  ctx.fillRect(0, 0, CONFIG.canvasWidth, CONFIG.canvasHeight);

  // Grid
  ctx.strokeStyle = "rgba(0, 255, 65, 0.05)";
  ctx.lineWidth = 1;
  for (let x = 0; x < CONFIG.canvasWidth; x += 30) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, CONFIG.canvasHeight); ctx.stroke(); }
  for (let y = 0; y < CONFIG.canvasHeight; y += 30) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(CONFIG.canvasWidth, y); ctx.stroke(); }

  // Ground
  const groundY = CONFIG.canvasHeight - 50;
  ctx.strokeStyle = CONFIG.groundColor;
  ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(0, groundY); ctx.lineTo(CONFIG.canvasWidth, groundY); ctx.stroke();

  // Cart
  const targetX = Math.max(CONFIG.cartWidth / 2, Math.min(CONFIG.canvasWidth - CONFIG.cartWidth / 2, state.mouseX));
  if (!state.running) { state.cartX = targetX; state.prevCartX = targetX; } else { state.cartX = targetX; }
  const cartY = groundY - CONFIG.cartHeight;

  ctx.fillStyle = CONFIG.cartColor;
  ctx.fillRect(state.cartX - CONFIG.cartWidth / 2, cartY, CONFIG.cartWidth, CONFIG.cartHeight);
  ctx.strokeStyle = "#888"; ctx.lineWidth = 2;
  ctx.strokeRect(state.cartX - CONFIG.cartWidth / 2, cartY, CONFIG.cartWidth, CONFIG.cartHeight);

  // Pole
  const poleLength = state.running ? state.currentLength : 100;
  const pivotX = state.cartX;
  const pivotY = cartY;
  const poleEndX = pivotX + Math.sin(state.poleAngle) * poleLength;
  const poleEndY = pivotY - Math.cos(state.poleAngle) * poleLength;

  const dangerLevel = Math.abs(state.poleAngle) / CONFIG.failAngle;
  let poleColor = state.success ? CONFIG.poleSuccessColor : (dangerLevel > 0.7 ? "#ff3333" : (dangerLevel > 0.4 ? "#ffcc00" : "#00ff41"));
  
  ctx.shadowColor = poleColor; ctx.shadowBlur = 10;
  ctx.strokeStyle = poleColor; ctx.lineWidth = 6; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(pivotX, pivotY); ctx.lineTo(poleEndX, poleEndY); ctx.stroke();
  ctx.shadowBlur = 0;

  // Pivot & Tip
  ctx.fillStyle = CONFIG.pivotColor; ctx.beginPath(); ctx.arc(pivotX, pivotY, 8, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = poleColor; ctx.beginPath(); ctx.arc(poleEndX, poleEndY, 6, 0, Math.PI * 2); ctx.fill();

  // Danger Lines
  if (state.running) {
    ctx.strokeStyle = "rgba(255, 51, 51, 0.3)"; ctx.lineWidth = 2; ctx.setLineDash([5, 5]);
    ctx.beginPath(); ctx.moveTo(pivotX, pivotY); ctx.lineTo(pivotX + Math.sin(-CONFIG.failAngle) * poleLength, pivotY - Math.cos(-CONFIG.failAngle) * poleLength); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pivotX, pivotY); ctx.lineTo(pivotX + Math.sin(CONFIG.failAngle) * poleLength, pivotY - Math.cos(CONFIG.failAngle) * poleLength); ctx.stroke();
    ctx.setLineDash([]);
  }

  updateDisplays();
}

function updateDisplays() {
  const time = state.frameCount / CONFIG.fps;
  timeDisplay.textContent = time.toFixed(2) + "s";
  
  const displayNoise = (Math.random() - 0.5) * 2.0;
  const angleDeg = ((state.poleAngle * 180) / Math.PI);
  angleDisplay.textContent = (angleDeg + displayNoise).toFixed(1) + "°";

  if (state.running) {
    const progress = ((state.frameCount / CONFIG.successFrames) * 100).toFixed(0);
    statusEl.textContent = `STABILIZATION IN PROGRESS... ${progress}%`;
  }
}

// ==================== GAME LOOP ====================
let lastTime = 0;
const frameInterval = 1000 / CONFIG.fps;

function gameLoop(currentTime) {
  requestAnimationFrame(gameLoop);
  const deltaTime = currentTime - lastTime;
  if (deltaTime >= frameInterval) {
    lastTime = currentTime - (deltaTime % frameInterval);
    updatePhysics();
    render();
  }
}

setupInputHandlers();
initGame();