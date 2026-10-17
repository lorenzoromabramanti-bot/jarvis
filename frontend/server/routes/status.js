// ── Status Routes: /api/config, /api/status, /api/model-status ──

import { Router } from 'express';
import { readFile } from 'fs/promises';
import { isReady, getSessionKey, gwRequest } from '../gateway.js';
import { getMsgCount } from './chat.js';

const router = Router();

export default function statusRoutes(config, ocConfigPath) {
  // 前端設定
  router.get('/config', (req, res) => {
    res.json({ name: config.name, agent: config.agent, theme: config.theme });
  });

  // 健康檢查
  router.get('/status', async (req, res) => {
    let channel = null;
    try {
      const ocConfig = JSON.parse(await readFile(ocConfigPath, 'utf-8'));
      const channels = ocConfig?.channels;
      if (channels) {
        channel = Object.keys(channels).find(k => channels[k]?.enabled !== false) || Object.keys(channels)[0] || null;
      }
    } catch {}
    res.json({ gateway: isReady(), sessionKey: getSessionKey(), channel, msgCount: getMsgCount() });
  });

  // Model Status
  //
  // Version d'origine : interrogeait chat.history et sessions.list, deux
  // methodes du protocole OpenClaw. L'adaptateur JARVIS renvoie pour elles
  // une liste vide et une session sans metadonnees — le panneau affichait
  // donc « — » et 0% en permanence, quoi qu'il arrive dans la conversation.
  //
  // Ce qui est reellement disponible cote JARVIS :
  //   - le modele : oui, via get_available_models -> champ « prefered ».
  //   - les jetons : NON. main2.py ne compte rien (aucun prompt_tokens /
  //     completion_tokens / total_tokens dans tout le fichier). On renvoie
  //     null plutot que 0, pour que le HUD affiche « indisponible » au lieu
  //     d'un compteur faussement a zero.
  router.get('/model-status', async (req, res) => {
    try {
      const { models = [], preferred = '' } = await gwRequest('models.list');
      const actif = preferred || (models[0] && (models[0].name || models[0])) || '';
      res.json({
        model: typeof actif === 'string' ? actif : (actif.name || ''),
        provider: '',
        tokensDisponibles: false,   // JARVIS ne compte pas les jetons
        contextTokens: null,
        totalTokens: null,
        contextWindow: null,
        usage: null,
      });
    } catch (err) {
      res.status(502).json({ error: err.message || 'gateway error' });
    }
  });

  return router;
}
