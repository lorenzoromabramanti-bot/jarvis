// ── Composant reutilisable : liste + actions ──────────────────────────────
//
// L'ancien frontend repete le meme motif sur ~10 panneaux : desinstalleur,
// mises a jour Winget, pays VPN, applications detectees, notes Obsidian,
// liste de courses, menaces antivirus. Tous font la meme chose : afficher une
// liste, permettre une selection, declencher une action, montrer une
// progression. Ecrire ce motif 10 fois serait 10 fois la meme dette.
//
// Ce composant le fournit une fois. Les lots 3, 5 et 8 s'appuient dessus.
//
// Usage :
//   const liste = creerListeActions(conteneur, {
//     chargement: async () => [{id, titre, sousTitre, meta}],
//     actions: [{ nom:'DESINSTALLER', danger:true, executer: async (elems)=>{} }],
//     selectionMultiple: true,
//     messageVide: 'AUCUN ELEMENT',
//   });
//   liste.recharger();
//
// GARDE-FOU : une action marquee danger:true exige une confirmation
// explicite avant execution. C'est la regle du projet pour toute action
// irreversible (desinstallation, suppression, mise en quarantaine).

export function creerListeActions(conteneur, options) {
  const {
    chargement,
    actions = [],
    selectionMultiple = false,
    messageVide = 'AUCUN ELEMENT',
    rendu = null,          // (element) => string  : rendu personnalise
  } = options;

  let elements = [];
  const selection = new Set();
  let enCours = false;

  function echapper(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  function afficherEtat(texte, classe = 'la-etat') {
    conteneur.innerHTML = `<div class="${classe}">${echapper(texte)}</div>`;
  }

  function dessiner() {
    if (!elements.length) return afficherEtat(messageVide, 'la-vide');

    const lignes = elements.map((el) => {
      const choisi = selection.has(el.id) ? ' selectionne' : '';
      const corps = rendu ? rendu(el) : `
        <span class="la-titre">${echapper(el.titre)}</span>
        ${el.sousTitre ? `<span class="la-sous">${echapper(el.sousTitre)}</span>` : ''}
        ${el.meta ? `<span class="la-meta">${echapper(el.meta)}</span>` : ''}`;
      return `<div class="la-ligne${choisi}" data-id="${echapper(el.id)}">${corps}</div>`;
    }).join('');

    const boutons = actions.map((a, i) => `
      <button class="btn la-action${a.danger ? ' la-danger' : ''}" data-action="${i}">
        ${echapper(a.nom)}
      </button>`).join('');

    conteneur.innerHTML = `
      <div class="la-liste">${lignes}</div>
      <div class="la-barre">
        <span class="la-compte">${elements.length} ELEMENT${elements.length > 1 ? 'S' : ''}${
          selection.size ? ` · ${selection.size} SELECTIONNE${selection.size > 1 ? 'S' : ''}` : ''
        }</span>
        <div class="la-actions">${boutons}</div>
      </div>
      <div class="la-progression" hidden><div class="la-progression-barre"></div><span class="la-progression-texte"></span></div>`;

    conteneur.querySelectorAll('.la-ligne').forEach((ligne) => {
      ligne.addEventListener('click', () => {
        const id = ligne.dataset.id;
        if (selection.has(id)) selection.delete(id);
        else {
          if (!selectionMultiple) selection.clear();
          selection.add(id);
        }
        dessiner();
      });
    });

    conteneur.querySelectorAll('.la-action').forEach((btn) => {
      btn.addEventListener('click', () => lancerAction(actions[Number(btn.dataset.action)]));
    });
  }

  function progresser(texte, pourcent) {
    const zone = conteneur.querySelector('.la-progression');
    if (!zone) return;
    zone.hidden = false;
    const barre = zone.querySelector('.la-progression-barre');
    const label = zone.querySelector('.la-progression-texte');
    if (label) label.textContent = texte || '';
    if (barre && typeof pourcent === 'number') barre.style.width = `${Math.max(0, Math.min(100, pourcent))}%`;
  }

  async function lancerAction(action) {
    if (!action || enCours) return;
    const choisis = elements.filter((e) => selection.has(e.id));
    if (action.exigeSelection !== false && !choisis.length) {
      progresser('AUCUN ELEMENT SELECTIONNE', 0);
      return;
    }
    // Garde-fou : action irreversible => confirmation explicite
    if (action.danger) {
      const quoi = choisis.length ? choisis.map((e) => e.titre).join(', ') : 'la selection';
      if (!window.confirm(`${action.nom}\n\n${quoi}\n\nAction irreversible. Confirmer ?`)) return;
    }
    enCours = true;
    try {
      await action.executer(choisis, progresser);
      selection.clear();
      await recharger();
    } catch (e) {
      progresser(`ECHEC : ${e.message || e}`, 0);
    } finally {
      enCours = false;
    }
  }

  async function recharger() {
    afficherEtat('CHARGEMENT...');
    try {
      elements = (await chargement()) || [];
      dessiner();
    } catch (e) {
      afficherEtat(`ERREUR : ${e.message || e}`, 'la-erreur');
    }
  }

  return { recharger, progresser, elements: () => elements, selection: () => [...selection] };
}
