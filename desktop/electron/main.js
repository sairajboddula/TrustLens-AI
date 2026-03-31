"use strict";
/**
 * KYC Platform - Electron Main Process
 *
 * Responsibilities:
 *   1. Spawn the Python FastAPI backend as a child process.
 *   2. Poll /health until the backend is ready.
 *   3. Show a splash screen while loading.
 *   4. Open the main BrowserWindow loading the frontend.
 *   5. Kill the backend process on app quit.
 *   6. Handle errors gracefully with user-facing dialogs.
 */

const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BACKEND_PORT = 8000;
const BACKEND_HOST = "127.0.0.1";
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const HEALTH_URL = `${BACKEND_URL}/health`;
const FRONTEND_URL = `${BACKEND_URL}`;

/** Maximum time (ms) to wait for the backend to become healthy. */
const BACKEND_STARTUP_TIMEOUT_MS = 30_000;
/** Interval (ms) between health-check polls. */
const HEALTH_POLL_INTERVAL_MS = 500;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/** @type {import("child_process").ChildProcess | null} */
let backendProcess = null;

/** @type {BrowserWindow | null} */
let mainWindow = null;

/** @type {BrowserWindow | null} */
let splashWindow = null;

// ---------------------------------------------------------------------------
// Path helpers
// ---------------------------------------------------------------------------

/**
 * Return the resources root, which differs between development and packaged builds.
 *   - Dev:     <repo-root>
 *   - Packaged: path.join(process.resourcesPath)
 */
function getResourcesPath() {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  // Development: two levels up from desktop/electron/
  return path.resolve(__dirname, "..", "..");
}

/** Locate the Python interpreter bundled with or alongside the app. */
function getPythonExecutable() {
  const isWindows = process.platform === "win32";
  const candidates = [];

  if (app.isPackaged) {
    // Look for a python binary bundled next to the executable
    const appDir = path.dirname(app.getPath("exe"));
    candidates.push(
      path.join(appDir, "python", isWindows ? "python.exe" : "python3"),
      path.join(appDir, isWindows ? "python.exe" : "python3")
    );
  }

  // Fall back to system Python
  candidates.push(isWindows ? "python" : "python3");

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return isWindows ? "python" : "python3";
}

/** Return the absolute path to the backend main.py. */
function getBackendEntryPoint() {
  return path.join(getResourcesPath(), "backend", "main.py");
}

// ---------------------------------------------------------------------------
// Backend process management
// ---------------------------------------------------------------------------

function startBackend() {
  const pythonExe = getPythonExecutable();
  const backendDir = path.join(getResourcesPath(), "backend");
  const entryPoint = getBackendEntryPoint();

  if (!fs.existsSync(entryPoint)) {
    console.error(`[Backend] Entry point not found: ${entryPoint}`);
    return false;
  }

  const env = {
    ...process.env,
    PYTHONPATH: backendDir,
    PORT: String(BACKEND_PORT),
    HOST: BACKEND_HOST,
    DEBUG: "false",
    ENVIRONMENT: "production",
  };

  const args = [
    "-m", "uvicorn",
    "main:app",
    "--host", BACKEND_HOST,
    "--port", String(BACKEND_PORT),
    "--log-level", "warning",
  ];

  console.log(`[Backend] Spawning: ${pythonExe} ${args.join(" ")}`);

  backendProcess = spawn(pythonExe, args, {
    cwd: backendDir,
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  backendProcess.stdout.on("data", (data) => {
    process.stdout.write(`[Backend OUT] ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    process.stderr.write(`[Backend ERR] ${data}`);
  });

  backendProcess.on("error", (err) => {
    console.error(`[Backend] Failed to start: ${err.message}`);
    showErrorDialog(
      "Backend Startup Error",
      `Could not start the KYC backend server.\n\n${err.message}\n\nPlease ensure Python 3.11+ is installed.`
    );
  });

  backendProcess.on("exit", (code, signal) => {
    if (code !== 0 && code !== null) {
      console.warn(`[Backend] Exited with code ${code} (signal: ${signal})`);
    }
    backendProcess = null;
  });

  console.log(`[Backend] Process started (PID ${backendProcess.pid})`);
  return true;
}

function stopBackend() {
  if (!backendProcess) return;

  console.log(`[Backend] Stopping process (PID ${backendProcess.pid})...`);

  try {
    if (process.platform === "win32") {
      // On Windows, SIGTERM is not available; use taskkill to kill the tree
      spawn("taskkill", ["/pid", String(backendProcess.pid), "/T", "/F"], {
        windowsHide: true,
      });
    } else {
      backendProcess.kill("SIGTERM");
    }
  } catch (err) {
    console.error(`[Backend] Error stopping process: ${err}`);
  }

  backendProcess = null;
}

// ---------------------------------------------------------------------------
// Health check polling
// ---------------------------------------------------------------------------

/**
 * Poll the backend /health endpoint until it returns 200 or we time out.
 * @returns {Promise<boolean>}
 */
function waitForBackend() {
  return new Promise((resolve) => {
    const start = Date.now();

    const poll = () => {
      // Check if the backend process died
      if (!backendProcess) {
        console.error("[Health] Backend process is not running.");
        return resolve(false);
      }

      if (Date.now() - start > BACKEND_STARTUP_TIMEOUT_MS) {
        console.error("[Health] Timed out waiting for backend.");
        return resolve(false);
      }

      const req = http.get(HEALTH_URL, { timeout: 2000 }, (res) => {
        if (res.status === 200 || res.statusCode === 200) {
          console.log("[Health] Backend is ready.");
          return resolve(true);
        }
        setTimeout(poll, HEALTH_POLL_INTERVAL_MS);
      });

      req.on("error", () => setTimeout(poll, HEALTH_POLL_INTERVAL_MS));
      req.on("timeout", () => {
        req.destroy();
        setTimeout(poll, HEALTH_POLL_INTERVAL_MS);
      });
    };

    // Small initial delay to let the backend start its event loop
    setTimeout(poll, 1000);
  });
}

// ---------------------------------------------------------------------------
// Window management
// ---------------------------------------------------------------------------

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 320,
    frame: false,
    transparent: false,
    resizable: false,
    center: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load a simple HTML splash from the assets folder if it exists, else create inline
  const splashHtmlPath = path.join(__dirname, "assets", "splash.html");

  if (fs.existsSync(splashHtmlPath)) {
    splashWindow.loadFile(splashHtmlPath);
  } else {
    // Inline splash page
    const splashHtml = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8"/>
          <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
              background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d);
              display: flex; flex-direction: column;
              align-items: center; justify-content: center;
              height: 100vh; font-family: 'Segoe UI', sans-serif; color: white;
            }
            h1 { font-size: 2rem; margin-bottom: 0.5rem; letter-spacing: 2px; }
            p { font-size: 0.9rem; opacity: 0.8; margin-bottom: 1.5rem; }
            .spinner {
              width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3);
              border-top-color: white; border-radius: 50%;
              animation: spin 0.8s linear infinite;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
          </style>
        </head>
        <body>
          <h1>KYC Platform</h1>
          <p>Starting verification engine...</p>
          <div class="spinner"></div>
        </body>
      </html>
    `;
    splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(splashHtml)}`);
  }

  splashWindow.on("closed", () => {
    splashWindow = null;
  });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
    show: false,  // shown after backend is ready
    title: "KYC Platform",
    icon: path.join(__dirname, "assets", "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Open external links in the system browser, not in Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http")) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.once("ready-to-show", () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
    }
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
    app.quit();
  });

  mainWindow.loadURL(FRONTEND_URL);
}

// ---------------------------------------------------------------------------
// Error dialog
// ---------------------------------------------------------------------------

function showErrorDialog(title, message) {
  dialog.showErrorBox(title, message);
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  console.log("[App] Electron ready. Starting KYC Platform...");

  // Show splash while the backend boots
  createSplashWindow();

  // Start the Python backend
  const started = startBackend();
  if (!started) {
    showErrorDialog(
      "Startup Error",
      "Failed to launch the backend process. Please check your Python installation."
    );
    app.quit();
    return;
  }

  // Wait for backend to be healthy
  const ready = await waitForBackend();
  if (!ready) {
    showErrorDialog(
      "Backend Unavailable",
      `The KYC backend server did not start within ${BACKEND_STARTUP_TIMEOUT_MS / 1000} seconds.\n\n` +
        "Please check that:\n" +
        "  • Python 3.11+ is installed\n" +
        "  • All dependencies are installed (pip install -r requirements.txt)\n" +
        "  • Port " + BACKEND_PORT + " is not in use"
    );
    stopBackend();
    app.quit();
    return;
  }

  // Open the main window
  createMainWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  // macOS: re-open the window when the dock icon is clicked
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});

app.on("before-quit", () => {
  console.log("[App] Before quit – stopping backend...");
  stopBackend();
});

app.on("will-quit", () => {
  stopBackend();
});

// ---------------------------------------------------------------------------
// IPC handlers (used by preload.js / renderer)
// ---------------------------------------------------------------------------

ipcMain.handle("app:get-version", () => app.getVersion());

ipcMain.handle("app:get-backend-url", () => BACKEND_URL);

ipcMain.handle("app:open-external", (_event, url) => {
  if (typeof url === "string" && (url.startsWith("https://") || url.startsWith("http://"))) {
    shell.openExternal(url);
  }
});

ipcMain.handle("app:restart-backend", async () => {
  console.log("[IPC] Restarting backend...");
  stopBackend();
  const started = startBackend();
  if (!started) return { success: false, error: "Failed to start backend" };

  const ready = await waitForBackend();
  return { success: ready };
});
