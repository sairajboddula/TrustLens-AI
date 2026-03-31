"use strict";
/**
 * KYC Platform - Electron Preload Script
 *
 * Runs in a privileged context (Node.js available) but exposes only a
 * narrow, explicitly-defined API surface to the renderer via contextBridge.
 *
 * The renderer process accesses this API via `window.kyc.*`.
 */

const { contextBridge, ipcRenderer } = require("electron");

// ---------------------------------------------------------------------------
// Exposed API
// ---------------------------------------------------------------------------

contextBridge.exposeInMainWorld("kyc", {
  /**
   * Return the Electron application version string.
   * @returns {Promise<string>}
   */
  getVersion: () => ipcRenderer.invoke("app:get-version"),

  /**
   * Return the URL of the running FastAPI backend.
   * @returns {Promise<string>}  e.g. "http://127.0.0.1:8000"
   */
  getBackendUrl: () => ipcRenderer.invoke("app:get-backend-url"),

  /**
   * Open a URL in the system default browser (not in Electron).
   * Only http:// and https:// URLs are forwarded; others are silently dropped.
   * @param {string} url
   * @returns {Promise<void>}
   */
  openExternal: (url) => ipcRenderer.invoke("app:open-external", url),

  /**
   * Restart the backend subprocess.
   * Useful from an admin / diagnostics panel.
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  restartBackend: () => ipcRenderer.invoke("app:restart-backend"),
});

// ---------------------------------------------------------------------------
// Platform information (synchronous, no IPC needed)
// ---------------------------------------------------------------------------

contextBridge.exposeInMainWorld("platform", {
  /** Operating system platform: 'win32' | 'darwin' | 'linux' */
  os: process.platform,

  /** true when running inside a packaged Electron app */
  isPackaged: !!(process.env.ELECTRON_NO_ASAR === undefined && require("electron").app?.isPackaged),
});
