// JARVIS Mail — application de bureau (Electron)
// Charge la messagerie unifiée servie par JARVIS (http://localhost:8090).
const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');

const JARVIS_URL = process.env.JARVIS_MAIL_URL || 'http://localhost:8090';

function createWindow() {
  const win = new BrowserWindow({
    width: 440,
    height: 820,
    minWidth: 360,
    minHeight: 560,
    title: 'JARVIS Mail',
    backgroundColor: '#000000',
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'icon.ico'),
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });

  Menu.setApplicationMenu(null);

  const loadApp = () => win.loadURL(JARVIS_URL);
  loadApp();

  // Si JARVIS n'est pas démarré → page d'attente avec bouton Réessayer
  win.webContents.on('did-fail-load', () => {
    win.loadFile(path.join(__dirname, 'offline.html'));
  });

  // Réessai déclenché depuis offline.html (via hash #retry)
  win.webContents.on('did-navigate-in-page', (_e, url) => {
    if (url.endsWith('#retry')) loadApp();
  });

  // Liens externes → navigateur système
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(JARVIS_URL)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => app.quit());
