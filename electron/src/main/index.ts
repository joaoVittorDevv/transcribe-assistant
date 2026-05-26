import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { spawn, type ChildProcess } from 'child_process';
import path from 'path';
import * as url from 'url';
import fs from 'fs';

declare const MAIN_WINDOW_VITE_DEV_SERVER_URL: string;
declare const MAIN_WINDOW_VITE_NAME: string;

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------------------
// Server subprocess
// ---------------------------------------------------------------------------
let server: ChildProcess | null = null;

function startServer(): void {
  server = spawn('uv', ['run', 'python', '-m', 'app.server'], {
    cwd: path.resolve(__dirname, '../../../..'),
    stdio: 'pipe',
    detached: false,
  });
  server.stdout?.on('data', (data: Buffer) => process.stdout.write(`[sse-server] ${data}`));
  server.stderr?.on('data', (data: Buffer) => process.stderr.write(`[sse-server:err] ${data}`));
  server.on('error', (err: Error) => console.error('[sse-server] Failed to start:', err.message));
}

function stopServer(): void {
  if (server) { server.kill('SIGTERM'); server = null; }
}

// ---------------------------------------------------------------------------
// Audio engine subprocess
// ---------------------------------------------------------------------------
let audioEngine: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;
// Bug 1b fix: queue pending commands while engine is restarting
let engineRestarting = false;
const pendingCommands: Array<{ cmd: { action: string; mode?: string }; resolve: (result: boolean) => void }> = [];

function startAudioEngine(): void {
  if (audioEngine) return;
  engineRestarting = false;
  audioEngine = spawn('uv', ['run', 'python', 'app/audio_engine.py'], {
    cwd: path.resolve(__dirname, '../../../..'),
    stdio: ['pipe', 'pipe', 'pipe'],
    detached: false,
  });

  audioEngine.stdout?.on('data', (data: Buffer) => {
    const lines = data.toString().split('\n').filter(Boolean);
    for (const line of lines) {
      try {
        const msg = JSON.parse(line);
        if (msg.type === 'rms') {
          mainWindow?.webContents.send('rms-update', msg.value);
        }
        if (msg.type === 'status') {
          // Forward status events to renderer (includes wav_path on stop)
          mainWindow?.webContents.send('audio-status', msg);
        }
        if (msg.type === 'ready') {
          // Bug 1b fix: engine is ready, drain pending command queue
          console.log('[audio-engine] ready');
          while (pendingCommands.length > 0) {
            const pending = pendingCommands.shift()!;
            try {
              audioEngine?.stdin?.write(JSON.stringify(pending.cmd) + '\n');
              pending.resolve(true);
            } catch (err) {
              console.error('[audio-engine] failed to send queued command:', err);
              pending.resolve(false);
            }
          }
        }
      } catch {
        // ignore malformed lines
      }
    }
  });

  audioEngine.stderr?.on('data', (data: Buffer) => {
    process.stderr.write(`[audio-engine:err] ${data}`);
  });

  audioEngine.on('error', (err: Error) => {
    console.error('[audio-engine] error:', err.message);
  });

  audioEngine.on('exit', (code) => {
    console.log('[audio-engine] exited with code', code);
    audioEngine = null;
    engineRestarting = true;
    if (mainWindow && !mainWindow.isDestroyed()) {
      // Restart after 500ms if window still open
      setTimeout(() => {
        if (mainWindow && !mainWindow.isDestroyed()) startAudioEngine();
      }, 500);
    }
  });
}

function stopAudioEngine(): void {
  if (!audioEngine) return;
  try {
    audioEngine.stdin?.write(JSON.stringify({ action: 'stop' }) + '\n');
    audioEngine.stdin?.end();
  } catch { /* ignore */ }
  setTimeout(() => {
    if (audioEngine && !audioEngine.killed) {
      audioEngine.kill('SIGTERM');
    }
    audioEngine = null;
  }, 2000);
}

// ---------------------------------------------------------------------------
// IPC handlers
// ---------------------------------------------------------------------------
function setupIpcHandlers(): void {
  ipcMain.handle('audio-command', async (_event, cmd: { action: string; mode?: string }) => {
    // Bug 1b fix: queue command if engine is dead or restarting
    if (!audioEngine || !audioEngine.stdin) {
      if (engineRestarting) {
        console.log('[audio-engine] queuing command while restarting:', cmd.action);
        return new Promise<boolean>((resolve) => {
          pendingCommands.push({ cmd, resolve });
        });
      }
      console.error('[audio-engine] engine not running, cannot send command:', cmd.action);
      return false;
    }
    try {
      audioEngine.stdin.write(JSON.stringify(cmd) + '\n');
      return true;
    } catch (err) {
      console.error('[audio-engine] stdin write error:', err);
      return false;
    }
  });

  ipcMain.handle('open-file-dialog', async (_event, accept: string[]) => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: [{ name: 'Audio', extensions: accept }],
    });
    return result.canceled ? null : result.filePaths[0];
  });

  ipcMain.handle('open-directory-dialog', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    });
    return result.canceled ? null : result.filePaths[0];
  });

  ipcMain.handle('read-file', async (_event, filePath: string) => {
    try {
      const data = fs.readFileSync(filePath);
      return data;
    } catch (err) {
      console.error('[read-file] error:', err);
      return null;
    }
  });

  // Use ipcMain.on (fire-and-forget) instead of handle to reduce latency
  // for text insertion. No response needed — just forward to renderer.
  ipcMain.on('insert-text-at-cursor', (_event, payload: { text: string; tabId?: string }) => {
    mainWindow?.webContents.send('insert-text', payload);
  });

  // Reset insertion point — signals editor to re-capture cursor on next chunk
  ipcMain.on('reset-insertion-point', () => {
    mainWindow?.webContents.send('reset-insertion-point');
  });

  ipcMain.handle('delete-file', async (_event, filePath: string) => {
    try {
      fs.unlinkSync(filePath);
      return true;
    } catch (err) {
      console.error('[delete-file] error:', err);
      return false;
    }
  });
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------
function createWindow(): void {
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'assets/icon.png')
    : path.resolve(__dirname, '../../../../assets/assist_transcribe_1x1.png');

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#121B26',
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    titleBarStyle: 'hiddenInset',
    frame: true,
  });

  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, `../../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`));
  }

  mainWindow.on('closed', () => {
    stopAudioEngine();
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(() => {
  startServer();
  setupIpcHandlers();
  createWindow();
  startAudioEngine();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  stopAudioEngine();
  stopServer();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  stopAudioEngine();
  stopServer();
});
