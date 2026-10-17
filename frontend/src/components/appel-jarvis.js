// ── Appel unique vers JARVIS, avec demande d'accord ──────────────────────
//
// Les cinq panneaux (domotique, media, quotidien, reglages, securite)
// portaient chacun une copie identique de ce helper. Une seule copie
// desormais : la gestion des niveaux d'autorisation devait etre ajoutee au
// meme endroit pour les cinq, la dupliquer aurait garanti la divergence.
//
// NIVEAUX D'AUTORISATION
// Le serveur (gateway.js) refuse par un 428 tout message dont le niveau
// depasse le plafond d'autonomie, tant qu'il n'arrive pas avec
// { confirme: true }. On demande alors son accord a l'utilisateur et on
// rejoue le meme appel.
//
// Le controle reste cote serveur. Ce fichier ne fait que l'habiller : si on
// le supprimait, les actions sensibles seraient refusees, pas autorisees.

const LIBELLES_NIVEAU = {
  1: 'lecture', 2: 'lecture',
  3: 'ecriture', 4: 'ecriture',
  5: 'commande systeme', 6: 'commande systeme',
  7: 'installation de logiciel', 8: 'installation de logiciel',
  9: 'action irreversible', 10: 'action irreversible',
};

/** Demande d'accord. Remplacable par une vraie carte d'approbation plus tard. */
function demanderAccord({ type, niveau }) {
  const nature = LIBELLES_NIVEAU[niveau] || 'action sensible';
  return window.confirm(
    `AUTORISATION REQUISE\n\n${type}\nNiveau ${niveau} — ${nature}.\n\n`
    + `Cette action depasse le niveau d'autonomie configure.\nAutoriser une fois ?`);
}

/**
 * @param {string} type   message JARVIS (doit etre dans la liste blanche)
 * @param {object} corps  champs du message
 * @throws {Error} refus, erreur reseau, ou accord refuse par l'utilisateur
 */
export async function appelerJarvis(type, corps = {}) {
  const envoyer = (charge) => fetch(`/api/jarvis/${type}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(charge),
  });

  let r = await envoyer(corps);

  if (r.status === 428) {
    const d = await r.json().catch(() => ({}));
    if (!demanderAccord({ type, niveau: d.niveau })) {
      throw new Error('Autorisation refusee');
    }
    r = await envoyer({ ...corps, confirme: true });
  }

  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `HTTP ${r.status}`);
  }
  return r.json();
}
