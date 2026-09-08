# Preload Unsafe Patterns Analysis

## Scope

- **Preload:** `/home/jao/VSCode/transcribe-assistant/electron/src/preload/index.ts`
- **Main:** `/home/jao/VSCode/transcribe-assistant/electron/src/main/index.ts`

Context: `contextIsolation: true` (preload runs in isolated renderer context)

---

## Finding 1 — `mainWindow` referenced in preload context

**File:** `electron/src/preload/index.ts`
**Line:** 47
**Severity:** HIGH — Runtime failure

```typescript
insertTextAtCursor(text: string) {
  mainWindow?.webContents.send('insert-text', text);
},
```

**Status:** BROKEN

**Problem:** `mainWindow` is a main-process variable (declared at `main/index.ts:37`). The preload script executes in a renderer process context with `contextIsolation: true`, meaning it has no access to `mainWindow`. At runtime this will throw: `ReferenceError: mainWindow is not defined`.

**Fix:** Replace direct `mainWindow` access with an IPC call that the main process handles:

```typescript
// preload
insertTextAtCursor(text: string) {
  ipcRenderer.invoke('insert-text-at-cursor', text);
},
```

```typescript
// main — add handler
ipcMain.handle('insert-text-at-cursor', (_event, text: string) => {
  mainWindow?.webContents.send('insert-text', text);
});
```

---

## Finding 2 — `insertTextAtCursor` exposed via contextBridge without fallback

**File:** `electron/src/preload/index.ts`
**Lines:** 14, 46-48
**Severity:** MEDIUM — API design issue

The `ElectronAPI` interface exposes `insertTextAtCursor` as a void function with no error signaling. If the underlying IPC call fails or the window is unavailable, the caller gets no feedback. The optional chaining (`mainWindow?.`) silently swallows the failure.

---

## Main Process Analysis — No issues found

The main process (`main/index.ts`) correctly uses `mainWindow` and other main-process variables within its own scope:

| Line | Pattern | Status |
|------|---------|--------|
| 37   | `let mainWindow: BrowserWindow \| null = null` | OK (local scope) |
| 53   | `mainWindow?.webContents.send('rms-update', ...)` | OK (inside `startAudioEngine`, called from main context) |
| 57   | `mainWindow?.webContents.send('audio-status', ...)` | OK (same) |
| 113  | `mainWindow` used in `open-file-dialog` handler | OK (ipcMain handler runs in main process) |
| 136  | `mainWindow = new BrowserWindow(...)` | OK (main process assignment) |

`server` and `audioEngine` subprocess variables are similarly scoped correctly — they are used only in main-process functions (`startServer`, `stopServer`, `startAudioEngine`, `stopAudioEngine`) and IPC handlers that run in the main process.

---

## Summary

| Finding | File | Line | Severity | Status |
|---------|------|------|----------|--------|
| `mainWindow` referenced in preload | preload/index.ts | 47 | HIGH | BROKEN |
| `insertTextAtCursor` silent failure | preload/index.ts | 47 | MEDIUM | Design flaw |

**Total broken patterns:** 1
**Total design issues:** 1
