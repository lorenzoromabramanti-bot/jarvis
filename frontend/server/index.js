// ── JARVIS 後端入口 ──

import express from 'express';
import path from 'path';
import os from 'os';
import { readFile } from 'fs/promises';
import { fileURLToPath } from 'url';

import { initGateway, gwRequest } from './gateway.js';
import { addClient, removeClient, broadcastChat, demarrerBattement, INTERVALLE_BATTEMENT_MS } from './sse.js';
import { initTTS } from './tts.js';
import { startSystemMonitor } from './system-monitor.js';

// Routes
import chatRoutes from './routes/chat.js';
import statusRoutes from './routes/status.js';
import ttsRoutes from './routes/tts-routes.js';
import tasksRoutes from './routes/tasks.js';
import skillsRoutes from './routes/skills.js';
import memoryRoutes from './routes/memory.js';
import scheduleRoutes from './routes/schedule.js';
import voiceRoutes from './routes/voice.js';
import modelsRoutes from './routes/models.js';
import jarvisRoutes from './routes/jarvis.js';
import captureRoutes from './routes/capture.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
// .env de l'interface : facultatif (le jeton de JARVIS est lu dans le .env de JARVIS par gateway.js)
try { process.loadEnvFile(path.join(ROOT, '.env')); } catch { /* absent ou Node trop ancien */ }

// ── 讀取設定 ──
let config;
try {
  config = JSON.parse(await readFile(path.join(ROOT, 'config.local.json'), 'utf-8'));
} catch {
  config = JSON.parse(await readFile(path.join(ROOT, 'config.json'), 'utf-8'));
}

const GATEWAY_URL = process.env.GATEWAY_URL || config.server.gatewayUrl;
const GATEWAY_TOKEN = process.env.GATEWAY_TOKEN;
const PORT = process.env.PORT || config.server.port;
const SERVE_STATIC = process.env.SERVE_STATIC !== 'false';
const SESSION_KEY = config.agent.sessionKey;
const OC_CONFIG = path.join(os.homedir(), '.openclaw', 'openclaw.json');

// ── Express ──
const app = express();
// 12 Mo : une capture d'ecran en base64 depasse largement les 100 ko par
// defaut d'express.json(). Sans cette limite, la vision de JARVIS
// echouerait en 413 sans message comprehensible. Borne quand meme :
// au-dela, c'est une anomalie et non une capture.
app.use(express.json({ limit: '12mb' }));

// 共享 sessionKey 供路由使用
app.locals.sessionKey = SESSION_KEY;

// ── SSE ──
app.get('/api/events', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache',
    Connection: 'keep-alive', 'Access-Control-Allow-Origin': '*',
  });
  // Annonce l'intervalle de battement : le client calibre son chien de garde
  // dessus plutot que de coder une valeur en dur des deux cotes.
  res.write(`data: {"type":"connected","heartbeatMs":${INTERVALLE_BATTEMENT_MS}}\n\n`);
  addClient(res);
  demarrerBattement();
  req.on('close', () => removeClient(res));
});

// ── 掛載路由 ──
app.use('/api', captureRoutes);
app.use('/api', chatRoutes);
app.use('/api', statusRoutes(config, OC_CONFIG));
app.use('/api', ttsRoutes);
app.use('/api', tasksRoutes);
app.use('/api', skillsRoutes);
app.use('/api', memoryRoutes);
app.use('/api', scheduleRoutes);
app.use('/api', voiceRoutes);
app.use('/api', modelsRoutes);
app.use('/api', jarvisRoutes);

// ── 靜態檔案 ──
if (SERVE_STATIC) {
  const distPath = path.join(ROOT, 'dist');
  app.use(express.static(distPath));
  app.get('/{*splat}', (req, res) => res.sendFile(path.join(distPath, 'index.html')));
}

// ── 初始化 ──
initTTS(config.tts);
initGateway({ url: GATEWAY_URL, token: GATEWAY_TOKEN, sessionKey: SESSION_KEY, onChat: broadcastChat });
startSystemMonitor();

app.listen(PORT, () => {
  console.log(`[JARVIS] API server on http://localhost:${PORT}`);
  if (SERVE_STATIC) console.log(`[JARVIS] Serving static files from dist/`);
});
