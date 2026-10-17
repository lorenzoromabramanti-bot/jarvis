// ── Model Routes : /api/models (liste + selection du modele JARVIS) ──

import { Router } from 'express';
import { gwRequest } from '../gateway.js';

const router = Router();

// Liste des modeles disponibles + celui actuellement prefere.
router.get('/models', async (req, res) => {
  try {
    const r = await gwRequest('models.list');
    res.json(r);
  } catch (err) {
    res.status(502).json({ error: err.message || 'gateway error' });
  }
});

// Change le modele prefere. JARVIS ne renvoie pas d'accuse pour cette
// action (sauvegarde config silencieuse) : on relit la liste juste apres
// pour renvoyer un etat a jour au client.
router.post('/models', async (req, res) => {
  const { model } = req.body || {};
  if (!model) return res.status(400).json({ error: 'model required' });
  try {
    await gwRequest('models.set', { model });
    const r = await gwRequest('models.list');
    res.json(r);
  } catch (err) {
    res.status(502).json({ error: err.message || 'gateway error' });
  }
});

export default router;
