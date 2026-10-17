// ── Route de capture : /api/capture ──────────────────────────────────────
//
// Le navigateur renvoie ici l'image qu'il vient de prendre, en reponse a une
// demande que JARVIS a emise (evenement SSE 'capture-demandee').
//
// POURQUOI CE DETOUR
// JARVIS ne capture pas lui-meme. Il envoie {action:'request_screen_capture'}
// ou {type:'request_camera_capture'} et attend une image base64 sous 15
// secondes. La capture se fait donc dans la page, avec getDisplayMedia ou
// getUserMedia — seul endroit ou ces API existent. Le navigateur ne parlant
// pas WebSocket dans ce projet, il passe par cette route.
//
// SECURITE : la route ne fait que RELAYER une reponse a une demande deja
// initiee par JARVIS. Elle ne peut rien declencher. Un identifiant inconnu
// est simplement ignore cote JARVIS, dont le dictionnaire de futures en
// attente sert de garde.

import { Router } from 'express';
import { repondreCapture } from '../gateway.js';

const router = Router();

// Une image d'ecran en base64 depasse largement la limite JSON par defaut.
// La limite reste bornee : au-dela, c'est une anomalie, pas une capture.
router.post('/capture', (req, res) => {
  const { genre, id, data, erreur } = req.body || {};
  if (!['ecran', 'camera', 'etat_webcam'].includes(genre)) {
    return res.status(400).json({ error: 'genre inconnu : ' + genre });
  }
  if (genre !== 'etat_webcam' && !id) {
    return res.status(400).json({ error: 'identifiant de demande manquant' });
  }
  const ok = repondreCapture(genre, id, data, erreur);
  if (!ok) return res.status(502).json({ error: 'JARVIS injoignable' });
  res.json({ ok: true, genre, id: id || null, taille: (data || '').length });
});

export default router;
