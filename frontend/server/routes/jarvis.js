// ── Route generique JARVIS : /api/jarvis/:type ──
//
// Relaie un message vers JARVIS via le passe-plat borne de gateway.js.
// Seuls les types declares dans MESSAGES_AUTORISES passent ; tout le reste
// est refuse cote adaptateur (403 ici). Sert de socle a la migration des
// panneaux de l'ancien frontend (lots 1 a 8).

import { Router } from 'express';
import { gwRequest } from '../gateway.js';

const router = Router();

router.post('/jarvis/:type', async (req, res) => {
  const type = req.params.type;
  try {
    const r = await gwRequest('jarvis.send', { type, ...(req.body || {}) });
    res.json(r);
  } catch (err) {
    const msg = err.message || 'gateway error';
    // Niveau d'autorisation depasse -> 428 Precondition Required, avec de
    // quoi construire la demande d'accord. Distinct du 403 : ce n'est pas
    // interdit, c'est en attente d'un feu vert. Le navigateur rejoue le
    // meme appel avec { confirme: true } une fois l'utilisateur d'accord.
    if (err.confirmationRequise) {
      return res.status(428).json({
        error: msg, confirmationRequise: true,
        niveau: err.niveau, type: err.typeMessage,
      });
    }
    // Message refuse par la liste blanche -> 403, pas 502 : ce n'est pas une
    // panne, c'est un refus deliberé.
    const code = (msg.startsWith('message non autorise')
                  || msg.startsWith('service domotique non autorise')) ? 403 : 502;
    res.status(code).json({ error: msg });
  }
});

export default router;
