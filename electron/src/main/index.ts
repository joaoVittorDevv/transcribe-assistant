import { app, BrowserWindow } from 'electron';
import { spawn, type ChildProcess } from 'child_process';
import path from 'path';

declare const MAIN_WINDOW_VITE_DEV_SERVER_URL: string;
declare const MAIN_WINDOW_VITE_NAME: string;

let server: ChildProcess | null = null;

function startServer(): void {
  server = spawn('uv', ['run', 'python', '-m', 'app.server'], {
    // __dirname = electron/.vite/build/main/ → ../../../.. = project root
    cwd: path.resolve(__dirname, '../../../..'),
    stdio: 'pipe',
    detached: false,
  });

  server.stdout?.on('data', (data: Buffer) => {
    process.stdout.write(`[sse-server] ${data.toString()}`);
  });

  server.stderr?.on('data', (data: Buffer) => {
    process.stderr.write(`[sse-server:err] ${data.toString()}`);
  });

  server.on('error', (err: Error) => {
    console.error('[sse-server] Failed to start:', err.message);
  });
}

function stopServer(): void {
  if (server) {
    server.kill('SIGTERM');
    server = null;
    console.log('[sse-server] Stopped');
  }
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#121B26',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    titleBarStyle: 'hiddenInset',
    frame: true,
  });

  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    win.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`));
  }

  win.on('closed', () => {
    stopServer();
  });
}

app.whenReady().then(() => {
  startServer();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
