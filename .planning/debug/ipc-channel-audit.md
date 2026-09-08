# IPC Channel Audit: `insertTextAtCursor`

## Bug Confirmed

**`insertTextAtCursor` in preload uses `mainWindow` which does not exist in preload scope.**

```typescript
// preload/index.ts line 46-48 — BROKEN
insertTextAtCursor(text: string) {
  mainWindow?.webContents.send('insert-text', text);  // mainWindow is undefined in preload!
}
```

`mainWindow` is declared in `main/index.ts` (line 37) as a `BrowserWindow` variable. The preload script runs in a separate renderer process with `contextIsolation: true`. It has no access to `mainWindow`.

---

## How `audioCommand` Works (Correct Pattern)

**Renderer (useTranscriptionState.ts line 114, 121):**
```typescript
api.audioCommand({ action: 'start', mode: currentMode });
api.audioCommand({ action: 'stop' });
```

**Preload (index.ts line 19-21):**
```typescript
audioCommand(cmd) {
  ipcRenderer.invoke('audio-command', cmd);  // invoke = two-way async
}
```

**Main (index.ts line 103-110):**
```typescript
ipcMain.handle('audio-command', (_event, cmd: { action: string; mode?: string }) => {
  if (!audioEngine || !audioEngine.stdin) return;
  audioEngine.stdin.write(JSON.stringify(cmd) + '\n');
});
```

Pattern: **`ipcRenderer.invoke` (renderer) → `ipcMain.handle` (main)**. This is correct. `invoke` returns a Promise and the main process handles it synchronously.

---

## Correct IPC Pattern for `insertTextAtCursor`

The bug requires inverting the direction. We want **renderer → main → renderer** (cross-step):
1. Renderer calls `api.insertTextAtCursor(text)`
2. Preload does `ipcRenderer.invoke('insert-text', text)`
3. Main `ipcMain.handle` receives it and sends `'insert-text'` via `mainWindow.webContents.send`
4. TextEditor listens on `'insert-text'` channel (already set up correctly)

So the fix only needs to change the preload's `insertTextAtCursor` implementation from a `send` (void, no handler) to an `invoke` (Promise, requires handler in main).

---

## Exact Code Changes

### preload/index.ts

**Old (lines 46-48):**
```typescript
insertTextAtCursor(text: string) {
  mainWindow?.webContents.send('insert-text', text);
},
```

**New:**
```typescript
insertTextAtCursor(text: string) {
  ipcRenderer.invoke('insert-text', text);
},
```

### main/index.ts

**Old (in `setupIpcHandlers`, after line 110):**
```typescript
ipcMain.handle('open-file-dialog', async (_event, accept: string[]) => {
```

**Add before the first `handle` call (or after `audio-command` handler):**
```typescript
ipcMain.handle('insert-text', (_event, text: string) => {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.send('insert-text', text);
});
```

### renderer/composables/useTranscriptionState.ts

No changes needed. Already calls `api.insertTextAtCursor(insertText)` correctly.

### renderer/components/editor/TextEditor.vue

No changes needed. Already listens with `api.onInsertText(...)` correctly.

---

## Summary

| | `audioCommand` | `insertTextAtCursor` (broken) | `insertTextAtCursor` (fixed) |
|---|---|---|---|
| Renderer → Preload | `ipcRenderer.invoke` | `ipcRenderer.invoke` | `ipcRenderer.invoke` |
| Main Handler | `ipcMain.handle` | **missing** | `ipcMain.handle` |
| Main → Renderer | N/A (one-way) | `mainWindow.webContents.send` | `mainWindow.webContents.send` |
| Listens on | N/A | `ipcRenderer.on` | `ipcRenderer.on` |

The only missing piece is the `ipcMain.handle('insert-text', ...)` in main. Preload should use `invoke` not `send` because `invoke` creates the matching handler slot in the main process that receives the call and then forwards to the renderer via the existing `send`.
