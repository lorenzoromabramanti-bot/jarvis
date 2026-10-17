// ── SSE 廣播管理 ──

const sseClients = new Set();
const voiceChatHandlers = new Set();

export function addClient(res) { sseClients.add(res); }
export function removeClient(res) { sseClients.delete(res); }
export function clientCount() { return sseClients.size; }
export function addVoiceHandler(h) { voiceChatHandlers.add(h); }
export function removeVoiceHandler(h) { voiceChatHandlers.delete(h); }

// 提取文字內容
function extractText(payload) {
  if (!payload.message?.content) return '';
  const content = payload.message.content;
  if (Array.isArray(content)) return content.filter(c => c.type === 'text').map(c => c.text).join('');
  return typeof content === 'string' ? content : '';
}

export function broadcastChat(payload) {
  const text = extractText(payload);
  const event = {
    runId: payload.runId,
    state: payload.state,
    text,
    role: payload.message?.role || '',
    done: payload.state === 'final' || payload.state === 'aborted',
  };
  if (payload.message?.model) event.model = payload.message.model;
  if (payload.message?.provider) event.provider = payload.message.provider;
  if (payload.message?.usage) event.usage = payload.message.usage;

  const data = JSON.stringify(event);
  for (const res of sseClients) res.write(`data: ${data}\n\n`);
  for (const handler of voiceChatHandlers) { try { handler(payload); } catch {} }
}

export function broadcastSystem(data) {
  const msg = JSON.stringify({ type: 'system', ...data });
  for (const res of sseClients) res.write(`data: ${msg}\n\n`);
}

export function broadcastEvent(type, extra = {}) {
  // extra : optionnel, retro-compatible avec les appels existants qui ne
  // passent qu'un type (connected, agent-state:*).
  const msg = JSON.stringify({ type, ...extra });
  for (const res of sseClients) res.write(`data: ${msg}\n\n`);
}

// ── Battement de coeur ────────────────────────────────────────────────────
// Sans ca, une connexion SSE peut mourir en silence : le navigateur garde
// readyState=OPEN (socket tenue ouverte par le proxy vite) alors que plus
// rien n'arrive. Constate en vrai apres un redemarrage du backend : 0 message
// en 7s alors que le serveur diffusait toutes les 3s. Un battement regulier
// donne au client de quoi detecter l'absence.
export const INTERVALLE_BATTEMENT_MS = 10000;

let timerBattement = null;

export function demarrerBattement() {
  if (timerBattement) return;
  timerBattement = setInterval(() => {
    const msg = JSON.stringify({ type: 'heartbeat', ts: Date.now() });
    for (const res of sseClients) {
      // Commentaire SSE (ligne ':') en plus : traverse les proxies qui
      // bufferisent, et ne remonte pas comme message au client.
      try { res.write(`: ping\n\ndata: ${msg}\n\n`); } catch { removeClient(res); }
    }
  }, INTERVALLE_BATTEMENT_MS);
  if (timerBattement.unref) timerBattement.unref();
}

export function arreterBattement() {
  if (timerBattement) { clearInterval(timerBattement); timerBattement = null; }
}
