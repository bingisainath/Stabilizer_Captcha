/**
 * REACTOR STABILIZER - Physics Engine
 * Inverted Pendulum simulation with dynamic chaos parameters
 *
 * Physics based on simplified inverted pendulum model:
 * θ'' = (g/L)sin(θ) - (a/L)cos(θ)
 * Where θ is angle, g is gravity, L is length, a is cart acceleration
 */

// ==================== CONFIGURATION ====================
const CONFIG = {
  canvasWidth: 600,
  canvasHeight: 400,
  cartWidth: 80,
  cartHeight: 20,
  failAngle: 1.4, // radians (~80 degrees) - more forgiving
  successFrames: 300, // 5 seconds at 60fps
  fps: 60,

  // Physics constants - TUNED FOR EASIER PLAY
  dampingFactor: 0.985, // More damping = less wild swings (was 0.98)
  cartForceMultiplier: 0.15, // Even stronger cart influence (was 0.08)

  // Visual
  poleColor: "#ff3333",
  poleSuccessColor: "#00ff41",
  cartColor: "#555555",
  pivotColor: "#ffcc00",
  groundColor: "#222222",
};

// ==================== GAME STATE ====================
let state = {
  // Game status
  initialized: false,
  running: false,
  gameOver: false,
  success: false,

  // Session
  sessionToken: null,
  schedule: null,

  // Physics state
  poleAngle: 0.05, // Even smaller initial tilt (was 0.08)
  angularVelocity: 0,
  cartX: CONFIG.canvasWidth / 2,
  cartVelocity: 0,
  prevCartX: CONFIG.canvasWidth / 2,

  // Input
  mouseX: CONFIG.canvasWidth / 2,
  mouseInCanvas: false,

  // Timing
  frameCount: 0,
  angleHistory: [],

  // Current parameters (from schedule)
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
const gravityDisplay = document.getElementById("gravityDisplay");
const lengthDisplay = document.getElementById("lengthDisplay");
const clickPrompt = document.getElementById("clickPrompt");
const verifyBtn = document.getElementById("verifyBtn");
const retryBtn = document.getElementById("retryBtn");
const resultBox = document.getElementById("resultBox");
const resultTitle = document.getElementById("resultTitle");
const resultStats = document.getElementById("resultStats");

// ==================== INITIALIZATION ====================
async function initGame() {
  try {
    statusEl.className = "loading";
    statusEl.textContent = "LOADING CHAOS PARAMETERS...";

    const response = await fetch("/init_stabilizer");
    const data = await response.json();

    if (!data.success) {
      throw new Error("Failed to initialize");
    }

    state.sessionToken = data.session_token;
    state.schedule = data.schedule;
    state.initialized = true;

    statusEl.className = "ready";
    statusEl.textContent = "REACTOR READY // AWAITING OPERATOR";
    clickPrompt.style.display = "block";

    // Start rendering (cart follows mouse before game starts)
    requestAnimationFrame(gameLoop);
  } catch (error) {
    console.error("Initialization error:", error);
    statusEl.className = "failed";
    statusEl.textContent = "SYSTEM ERROR: FAILED TO LOAD PARAMETERS";
  }
}

// ==================== PHYSICS ENGINE ====================
function updatePhysics() {
  if (!state.running || state.gameOver) return;

  // Get current parameters from schedule
  const frame = Math.min(state.frameCount, state.schedule.gravity.length - 1);
  state.currentGravity = state.schedule.gravity[frame];
  state.currentLength = state.schedule.length[frame];
  state.currentJolt = state.schedule.force_jolts[frame];

  // Calculate cart acceleration (how fast the cart position changed)
  const cartAcceleration = state.cartX - state.prevCartX;
  state.prevCartX = state.cartX;

  // Inverted pendulum physics
  // Angular acceleration = gravity term + inertial term from cart movement + random jolt
  const gravityTorque =
    (state.currentGravity / state.currentLength) * Math.sin(state.poleAngle);
  const inertialTorque =
    ((-CONFIG.cartForceMultiplier * cartAcceleration) / state.currentLength) *
    Math.cos(state.poleAngle);

  const angularAcceleration =
    gravityTorque + inertialTorque + state.currentJolt;

  // Update angular velocity and angle
  state.angularVelocity += angularAcceleration;
  state.angularVelocity *= CONFIG.dampingFactor; // Apply damping
  state.poleAngle += state.angularVelocity;

  // Record angle for verification
  state.angleHistory.push(state.poleAngle);
  state.frameCount++;

  // Check win/lose conditions
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

  verifyBtn.addEventListener("click", verifyHuman);
}

function startGame() {
  // CRITICAL: Set cartX to current mouseX to prevent whiplash
  state.cartX = state.mouseX;
  state.prevCartX = state.mouseX;

  // Reset physics state but keep cart position
  // Even smaller initial tilt = easier start (was 0.08, now 0.05)
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
}

// ==================== GAME FLOW ====================
function endGame(success) {
  state.running = false;
  state.gameOver = true;
  state.success = success;

  if (success) {
    statusEl.className = "success";
    statusEl.textContent = "REACTOR STABILIZED // VERIFICATION REQUIRED";
    verifyBtn.classList.add("visible");
  } else {
    statusEl.className = "failed";
    statusEl.textContent = "REACTOR CRITICAL // STABILIZATION FAILED";
    retryBtn.classList.add("visible");
  }
}

async function verifyHuman() {
  verifyBtn.classList.remove("visible");
  statusEl.textContent = "VERIFYING HUMAN SIGNATURE...";

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

    // Call window.showResult if it exists (for new UI)
    if (typeof window.showResult === "function") {
      window.showResult(data.verified, data.message, data.stats);
    } else {
      // Fallback to old UI
      resultBox.classList.add("visible");

      if (data.verified) {
        resultBox.classList.remove("failed");
        resultTitle.textContent = "✓ " + data.message;
        resultTitle.style.color = "#00ff41";

        if (data.stats) {
          resultStats.innerHTML = `
                      Duration: ${data.stats.duration.toFixed(2)}s<br>
                      Max Deviation: ${data.stats.max_deviation.toFixed(1)}°<br>
                      Oscillations: ${data.stats.oscillations}<br>
                      Stability Score: ${data.stats.stability_score}%
                  `;
        }

        statusEl.className = "success";
        statusEl.textContent = "HUMAN IDENTITY CONFIRMED";
      } else {
        resultBox.classList.add("failed");
        resultTitle.textContent = "✗ " + data.message;
        resultTitle.style.color = "#ff3333";
        resultStats.textContent = "";

        statusEl.className = "failed";
        statusEl.textContent = "VERIFICATION FAILED";
        retryBtn.classList.add("visible");
      }
    }
  } catch (error) {
    console.error("Verification error:", error);
    if (typeof window.showResult === "function") {
      window.showResult(false, "Verification error occurred", null);
    } else {
      statusEl.className = "failed";
      statusEl.textContent = "VERIFICATION ERROR";
      retryBtn.classList.add("visible");
    }
  }
}

async function resetGame() {
  // Reset state
  state.initialized = false;
  state.running = false;
  state.gameOver = false;
  state.success = false;
  state.frameCount = 0;
  state.angleHistory = [];
  state.poleAngle = 0.05; // Match easier initial tilt
  state.angularVelocity = 0;
  state.cartX = CONFIG.canvasWidth / 2;
  state.prevCartX = CONFIG.canvasWidth / 2;

  // Reset UI
  verifyBtn.classList.remove("visible");
  retryBtn.classList.remove("visible");
  resultBox.classList.remove("visible");

  // Reinitialize
  await initGame();
}

// ==================== RENDERING ====================
function render() {
  // Clear canvas with dark background
  ctx.fillStyle = "#0d0d0d";
  ctx.fillRect(0, 0, CONFIG.canvasWidth, CONFIG.canvasHeight);

  // Draw grid lines for cyberpunk effect
  ctx.strokeStyle = "rgba(0, 255, 65, 0.05)";
  ctx.lineWidth = 1;
  for (let x = 0; x < CONFIG.canvasWidth; x += 30) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, CONFIG.canvasHeight);
    ctx.stroke();
  }
  for (let y = 0; y < CONFIG.canvasHeight; y += 30) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(CONFIG.canvasWidth, y);
    ctx.stroke();
  }

  // Ground line
  const groundY = CONFIG.canvasHeight - 50;
  ctx.strokeStyle = CONFIG.groundColor;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(0, groundY);
  ctx.lineTo(CONFIG.canvasWidth, groundY);
  ctx.stroke();

  // Update cart position to follow mouse (always, even before game starts)
  // Smooth follow for better feel
  const targetX = Math.max(
    CONFIG.cartWidth / 2,
    Math.min(CONFIG.canvasWidth - CONFIG.cartWidth / 2, state.mouseX)
  );
  if (!state.running) {
    state.cartX = targetX;
    state.prevCartX = targetX;
  } else {
    state.cartX = targetX;
  }

  const cartY = groundY - CONFIG.cartHeight;

  // Draw cart (gray box)
  ctx.fillStyle = CONFIG.cartColor;
  ctx.fillRect(
    state.cartX - CONFIG.cartWidth / 2,
    cartY,
    CONFIG.cartWidth,
    CONFIG.cartHeight
  );

  // Cart border
  ctx.strokeStyle = "#888";
  ctx.lineWidth = 2;
  ctx.strokeRect(
    state.cartX - CONFIG.cartWidth / 2,
    cartY,
    CONFIG.cartWidth,
    CONFIG.cartHeight
  );

  // Calculate pole end position
  const poleLength = state.running ? state.currentLength : 100;
  const pivotX = state.cartX;
  const pivotY = cartY;
  const poleEndX = pivotX + Math.sin(state.poleAngle) * poleLength;
  const poleEndY = pivotY - Math.cos(state.poleAngle) * poleLength;

  // Draw pole
  const dangerLevel = Math.abs(state.poleAngle) / CONFIG.failAngle;
  let poleColor;
  if (state.success) {
    poleColor = CONFIG.poleSuccessColor;
  } else if (dangerLevel > 0.7) {
    poleColor = "#ff3333";
  } else if (dangerLevel > 0.4) {
    poleColor = "#ffcc00";
  } else {
    poleColor = "#00ff41";
  }

  // Pole glow effect
  ctx.shadowColor = poleColor;
  ctx.shadowBlur = 10;

  ctx.strokeStyle = poleColor;
  ctx.lineWidth = 6;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(pivotX, pivotY);
  ctx.lineTo(poleEndX, poleEndY);
  ctx.stroke();

  // Reset shadow
  ctx.shadowBlur = 0;

  // Draw pivot point
  ctx.fillStyle = CONFIG.pivotColor;
  ctx.beginPath();
  ctx.arc(pivotX, pivotY, 8, 0, Math.PI * 2);
  ctx.fill();

  // Draw pole tip
  ctx.fillStyle = poleColor;
  ctx.beginPath();
  ctx.arc(poleEndX, poleEndY, 6, 0, Math.PI * 2);
  ctx.fill();

  // Draw danger zone indicators
  if (state.running) {
    ctx.strokeStyle = "rgba(255, 51, 51, 0.3)";
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);

    // Left danger line
    const dangerAngle = CONFIG.failAngle;
    ctx.beginPath();
    ctx.moveTo(pivotX, pivotY);
    ctx.lineTo(
      pivotX + Math.sin(-dangerAngle) * poleLength,
      pivotY - Math.cos(-dangerAngle) * poleLength
    );
    ctx.stroke();

    // Right danger line
    ctx.beginPath();
    ctx.moveTo(pivotX, pivotY);
    ctx.lineTo(
      pivotX + Math.sin(dangerAngle) * poleLength,
      pivotY - Math.cos(dangerAngle) * poleLength
    );
    ctx.stroke();

    ctx.setLineDash([]);
  }

  // Draw custom cursor
  if (state.mouseInCanvas) {
    ctx.strokeStyle = "#ffcc00";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(state.mouseX - 10, groundY + 20);
    ctx.lineTo(state.mouseX + 10, groundY + 20);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(state.mouseX, groundY + 10);
    ctx.lineTo(state.mouseX, groundY + 30);
    ctx.stroke();
  }

  // Draw direction hint arrow when pole is tilting significantly
  if (state.running && Math.abs(state.poleAngle) > 0.15) {
    const hintDirection = state.poleAngle > 0 ? 1 : -1; // Move toward the tilt
    const arrowX = state.cartX + hintDirection * 80;
    const arrowY = groundY + 35;
    const opacity = Math.min(0.6, Math.abs(state.poleAngle) * 2);

    ctx.fillStyle = `rgba(255, 204, 0, ${opacity})`;
    ctx.beginPath();
    if (hintDirection > 0) {
      // Right arrow
      ctx.moveTo(arrowX - 15, arrowY - 8);
      ctx.lineTo(arrowX, arrowY);
      ctx.lineTo(arrowX - 15, arrowY + 8);
    } else {
      // Left arrow
      ctx.moveTo(arrowX + 15, arrowY - 8);
      ctx.lineTo(arrowX, arrowY);
      ctx.lineTo(arrowX + 15, arrowY + 8);
    }
    ctx.fill();
  }

  // Update displays
  updateDisplays();
}

function updateDisplays() {
  const time = state.frameCount / CONFIG.fps;
  timeDisplay.textContent = time.toFixed(2) + "s";

  const angleDeg = ((state.poleAngle * 180) / Math.PI).toFixed(1);
  // Add visual noise to the display so bots can't use it as a perfect sensor
  // The physics engine uses 'state.poleAngle', but the DOM shows a "noisy" version
  const displayNoise = (Math.random() - 0.5) * 2.0; // +/- 1.0 degree jitter
  const noisyAngle = (parseFloat(angleDeg) + displayNoise).toFixed(1);
  angleDisplay.textContent = noisyAngle + "°";

  // Color based on danger
  const dangerLevel = Math.abs(state.poleAngle) / CONFIG.failAngle;
  if (dangerLevel > 0.7) {
    angleDisplay.className = "stat-value danger";
  } else if (dangerLevel > 0.4) {
    angleDisplay.className = "stat-value warning";
  } else {
    angleDisplay.className = "stat-value";
  }

  if (state.running) {
    gravityDisplay.textContent = state.currentGravity.toFixed(2);
    lengthDisplay.textContent = Math.round(state.currentLength) + "px";
  }

  // Progress indicator
  if (state.running && !state.gameOver) {
    const progress = ((state.frameCount / CONFIG.successFrames) * 100).toFixed(
      0
    );
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

// ==================== START ====================
setupInputHandlers();
initGame();
