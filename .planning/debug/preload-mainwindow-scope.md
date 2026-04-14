---
status: resolved
trigger: "mainWindow is undefined in preload/index.ts when insertTextAtCursor is called"
created: 2026-04-14T00:00:00Z
updated: 2026-04-14T00:00:00Z
---

## Current Focus

hypothesis: mainWindow is not in scope in preload context
test: Code analysis of preload vs main process scopes
expecting: Confirm mainWindow is a main-process-only variable
next_action: Write findings

## Symptoms

expected: insertTextAtCursor in preload sends 'insert-text' to renderer
actual: mainWindow is undefined in preload, call silently fails
errors: None thrown (optional chaining masks the issue)
reproduction: Call window.electronAPI.insertTextAtCursor('text') from renderer
started: When insertTextAtCursor was added to preload API

## Evidence

- timestamp: 2026-04-14
  checked: preload/index.ts lines 46-48
  found: `mainWindow?.webContents.send('insert-text', text)` references `mainWindow` which is not declared in preload file
  implication: mainWindow is undefined at runtime

- timestamp: 2026-04-14
  checked: main/index.ts line 37
  found: `let mainWindow: BrowserWindow | null = null;` is declared in main process only
  implication: Preload cannot access this variable

- timestamp: 2026-04-14
  checked: main/index.ts webPreferences
  found: `contextIsolation: true, nodeIntegration: false` (line 145)
  implication: Preload has no access to main process scope

- timestamp: 2026-04-14
  checked: preload/index.ts contextBridge setup
  found: Only `electronAPI` object is exposed via contextBridge.exposeInMainWorld
  implication: Renderer gets electronAPI, not main process variables

## Resolution

root_cause: The preload script runs in an isolated renderer context and has no access to `mainWindow` (a main-process variable). Line 47 in preload calls `mainWindow?.webContents.send()` but `mainWindow` is undefined, so the optional chaining silently skips the call.

fix: Use IPC to communicate from preload to main process:
1. Preload: `ipcRenderer.send('insert-text-at-cursor', text)` instead of `mainWindow?.webContents.send()`
2. Main process: Add handler `ipcMain.on('insert-text-at-cursor', (_event, text) => mainWindow?.webContents.send('insert-text', text))`

verification: After implementing IPC handler in main and updating preload, insertTextAtCursor will route through main process to renderer correctly.

files_changed: []
---
