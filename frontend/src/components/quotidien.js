// ── Quotidien : meteo, courses, notes, messagerie (lot 5) ────────────────
//
// meteo      NOUVEAU panneau. Jusqu'ici la meteo n'etait que POUSSEE par
//            JARVIS (action weather_panel) sur demande vocale. Un handler
//            get_meteo a ete ajoute cote main2.py pour la rendre
//            interrogeable, avec asyncio.to_thread — sans quoi le geocodage
//            et l'appel open-meteo gelaient la boucle async.
// courses    get_shopping_list / update_shopping_list -> shopping_list {items}
// notes      get_obsidian_notes / read / save / delete
//            Le vault actuel est PLAT : obsidian_helper.creer_ou_modifier_note
//            applique os.path.basename() au titre, tout chemin est ecrase.
//            Le vault structure "memoire partagee" demande est donc un
//            chantier a part (voir rapport), pas une extension de ce panneau.
// messagerie simple ouverture de http://<hote>:8090, exactement ce que
//            faisait le bouton de l'ancien frontend (mail_server.py).

import { showNotification } from './notifications.js';
import { appelerJarvis } from './appel-jarvis.js';

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Delegue a appel-jarvis.js : copie unique, et c'est la qu'est gere le
// refus 428 (niveau d'autorisation depasse -> demande d'accord -> rejeu).
const appeler = appelerJarvis;

// ── Meteo ────────────────────────────────────────────────────────────────

const ICONES_METEO = {
  0: '☀', 1: '☀', 2: '⛅', 3: '☁', 45: '≡', 48: '≡',
  51: '⋯', 53: '⋯', 55: '⋯', 61: '☂', 63: '☂', 65: '☂',
  71: '❄', 73: '❄', 75: '❄', 80: '☂', 81: '☂', 82: '☂',
  95: '⚡', 96: '⚡', 99: '⚡',
};

function initMeteo(zone) {
  zone.innerHTML = `
    <div class="sec-barre">
      <input class="rg-input" id="me-ville" type="text" placeholder="VILLE (vide = par defaut)" />
      <button class="btn sec-btn" id="me-charger">RELEVER</button>
    </div>
    <div class="sec-etat" id="me-etat">—</div>
    <div id="me-carte"></div>`;

  const etat = zone.querySelector('#me-etat');
  const carte = zone.querySelector('#me-carte');

  async function charger() {
    const ville = zone.querySelector('#me-ville').value.trim();
    etat.textContent = 'RELEVE EN COURS...';
    etat.className = 'sec-etat';
    carte.innerHTML = '';
    try {
      const r = await appeler('get_meteo', ville ? { ville } : {});
      const m = r.data;
      if (!m) {
        // get_meteo_structuree renvoie None en cas d'echec : on le dit,
        // on n'affiche pas une carte vide qui ferait croire a un succes.
        etat.textContent = 'RELEVE IMPOSSIBLE (ville inconnue ou service indisponible)';
        etat.className = 'sec-etat erreur';
        return;
      }
      // get_meteo_structuree retombe SILENCIEUSEMENT sur la ville par
      // defaut quand le geocodage echoue. On le dit plutot que de laisser
      // croire que la ville demandee a ete prise en compte.
      const demandee = ville.toLowerCase();
      const obtenue = String(m.ville || '').toLowerCase();
      if (demandee && obtenue && !obtenue.includes(demandee) && !demandee.includes(obtenue)) {
        etat.textContent = `${m.ville} — ville "${ville}" introuvable, repli sur la ville par defaut`;
        etat.className = 'sec-etat erreur';
      } else {
        etat.textContent = m.ville || '';
      }
      carte.innerHTML = `
        <div class="me-carte">
          <div class="me-icone">${ICONES_METEO[m.code] || '·'}</div>
          <div class="me-principal">
            <div class="me-temp">${ech(m.temperature)}°</div>
            <div class="me-desc">${ech(m.description)}</div>
          </div>
          <div class="me-detail">
            <div><span>RESSENTI</span><b>${ech(m.ressenti)}°</b></div>
            <div><span>HUMIDITE</span><b>${ech(m.humidite)}%</b></div>
            <div><span>VENT</span><b>${ech(m.vent)} km/h</b></div>
          </div>
        </div>`;
    } catch (e) {
      etat.textContent = `ECHEC : ${e.message}`;
      etat.className = 'sec-etat erreur';
    }
  }

  zone.querySelector('#me-charger').addEventListener('click', charger);
  zone.querySelector('#me-ville').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') charger();
  });
  charger();
}

// ── Courses ──────────────────────────────────────────────────────────────

function initCourses(zone) {
  zone.innerHTML = `
    <div class="sec-barre">
      <input class="rg-input" id="co-ajout" type="text" placeholder="AJOUTER UN ARTICLE..." />
      <button class="btn sec-btn" id="co-ajouter">AJOUTER</button>
    </div>
    <div class="sec-etat" id="co-etat">—</div>
    <div id="co-liste"></div>`;

  const etat = zone.querySelector('#co-etat');
  const liste = zone.querySelector('#co-liste');
  let articles = [];

  function dessiner() {
    etat.textContent = `${articles.length} ARTICLE(S)`;
    liste.innerHTML = articles.length
      ? articles.map((a, i) => `
          <div class="co-ligne">
            <span class="co-nom">${ech(typeof a === 'string' ? a : (a.nom || a.item || JSON.stringify(a)))}</span>
            <button class="ha-btn co-suppr" data-i="${i}">RETIRER</button>
          </div>`).join('')
      : '<div class="rg-note">LISTE VIDE</div>';
    liste.querySelectorAll('.co-suppr').forEach((b) => {
      b.addEventListener('click', () => retirer(Number(b.dataset.i)));
    });
  }

  async function envoyer(nouveaux) {
    // update_shopping_list rediffuse shopping_list a tous les clients :
    // on prend la liste que JARVIS confirme, pas celle qu'on a devinee.
    const r = await appeler('update_shopping_list', { items: nouveaux });
    articles = r.items || nouveaux;
    dessiner();
  }

  async function retirer(i) {
    const nom = typeof articles[i] === 'string' ? articles[i] : (articles[i]?.nom || 'cet article');
    if (!window.confirm(`Retirer "${nom}" de la liste de courses ?`)) return;
    const copie = articles.slice();
    copie.splice(i, 1);
    try { await envoyer(copie); } catch (e) { showNotification(`COURSES : ${e.message}`); }
  }

  async function ajouter() {
    const champ = zone.querySelector('#co-ajout');
    const v = champ.value.trim();
    if (!v) return;
    try { await envoyer(articles.concat([v])); champ.value = ''; }
    catch (e) { showNotification(`COURSES : ${e.message}`); }
  }

  zone.querySelector('#co-ajouter').addEventListener('click', ajouter);
  zone.querySelector('#co-ajout').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') ajouter();
  });

  (async () => {
    try {
      const r = await appeler('get_shopping_list');
      articles = r.items || [];
      dessiner();
    } catch (e) {
      etat.textContent = `ECHEC : ${e.message}`;
      etat.className = 'sec-etat erreur';
    }
  })();
}

// ── Notes Obsidian (vault plat existant) ─────────────────────────────────

function initNotes(zone) {
  zone.innerHTML = `
    <div class="sec-barre">
      <input class="rg-input" id="no-titre" type="text" placeholder="TITRE DE LA NOTE" />
      <button class="btn sec-btn" id="no-nouvelle">NOUVELLE</button>
      <button class="btn sec-btn" id="no-enregistrer">ENREGISTRER</button>
      <button class="btn sec-btn la-danger" id="no-supprimer">SUPPRIMER</button>
    </div>
    <div class="sec-etat" id="no-etat">—</div>
    <div class="no-corps">
      <div id="no-liste" class="no-liste"></div>
      <textarea id="no-contenu" class="no-editeur" spellcheck="false"
                placeholder="CONTENU MARKDOWN..."></textarea>
    </div>`;

  const etat = zone.querySelector('#no-etat');
  const champTitre = zone.querySelector('#no-titre');
  const editeur = zone.querySelector('#no-contenu');
  let notes = [];

  function dessiner() {
    etat.textContent = `${notes.length} NOTE(S)`;
    const l = zone.querySelector('#no-liste');
    l.innerHTML = notes.length
      ? notes.map((n) => {
          const titre = typeof n === 'string' ? n : (n.titre || n.name || String(n));
          return `<div class="no-item" data-titre="${ech(titre)}">${ech(titre)}</div>`;
        }).join('')
      : '<div class="rg-note">AUCUNE NOTE</div>';
    l.querySelectorAll('.no-item').forEach((el) => {
      el.addEventListener('click', () => ouvrir(el.dataset.titre));
    });
  }

  async function rafraichir(liste) {
    notes = liste || (await appeler('get_obsidian_notes')).notes || [];
    dessiner();
  }

  async function ouvrir(titre) {
    champTitre.value = titre;
    etat.textContent = `LECTURE DE ${titre}...`;
    try {
      const r = await appeler('read_obsidian_note', { titre });
      editeur.value = r.content ?? r.contenu ?? '';
      etat.textContent = titre;
    } catch (e) {
      etat.textContent = `ECHEC : ${e.message}`;
      etat.className = 'sec-etat erreur';
    }
  }

  zone.querySelector('#no-nouvelle').addEventListener('click', () => {
    champTitre.value = ''; editeur.value = ''; etat.textContent = 'NOUVELLE NOTE';
  });

  zone.querySelector('#no-enregistrer').addEventListener('click', async () => {
    const titre = champTitre.value.trim();
    if (!titre) { showNotification('TITRE REQUIS'); return; }
    try {
      const r = await appeler('save_obsidian_note', { titre, content: editeur.value });
      await rafraichir(r.notes);
      etat.textContent = `ENREGISTRE : ${titre}`;
      showNotification('NOTE ENREGISTREE');
    } catch (e) { showNotification(`NOTE : ${e.message}`); }
  });

  zone.querySelector('#no-supprimer').addEventListener('click', async () => {
    const titre = champTitre.value.trim();
    if (!titre) return;
    // Suppression de fichier : irreversible, confirmation obligatoire.
    if (!window.confirm(`Supprimer definitivement la note "${titre}" ?\n\nAction irreversible.`)) return;
    try {
      const r = await appeler('delete_obsidian_note', { titre });
      await rafraichir(r.notes);
      champTitre.value = ''; editeur.value = '';
      etat.textContent = 'NOTE SUPPRIMEE';
      showNotification('NOTE SUPPRIMEE');
    } catch (e) { showNotification(`NOTE : ${e.message}`); }
  });

  rafraichir().catch((e) => {
    etat.textContent = `ECHEC : ${e.message}`;
    etat.className = 'sec-etat erreur';
  });
}

// ── Messagerie ───────────────────────────────────────────────────────────

function initMessagerie(zone) {
  // L'ancien bouton ouvrait simplement http://<hote>:8090 dans un onglet.
  // Courrier trie par categorie, avec brouillon de reponse.
  //
  // Remplace le simple bouton qui ouvrait mail_server.py sur le port 8090 :
  // ce panneau lit vraiment la boite, la range, et propose une reponse.
  //
  // AUCUN ENVOI. JARVIS ne sait pas envoyer d'e-mail aujourd'hui, et le jour
  // ou il saura, l'envoi sera un message distinct en niveau 7, valide
  // explicitement. Ici le brouillon est AFFICHE, rien de plus : ce panneau
  // ne peut rien expedier a un tiers, meme par erreur.
  const LIBELLES = {
    a_repondre: 'A REPONDRE', important: 'IMPORTANT',
    notification: 'NOTIFICATIONS', publicite: 'PUBLICITE', autre: 'AUTRE',
  };

  zone.innerHTML = `
    <div class="sec-barre">
      <button class="btn sec-btn" id="ms-relever">RELEVER LE COURRIER</button>
      <button class="btn sec-btn" id="ms-ouvrir">APPLICATION COMPLETE</button>
    </div>
    <div class="sec-etat" id="ms-etat">non releve</div>
    <div id="ms-liste"></div>`;

  const etat = zone.querySelector('#ms-etat');
  const liste = zone.querySelector('#ms-liste');
  const hote = location.hostname || 'localhost';
  zone.querySelector('#ms-ouvrir').addEventListener('click', () => {
    window.open(`http://${hote}:8090`, '_blank', 'noopener');
  });

  function rendre(groupes, comptes) {
    liste.innerHTML = Object.entries(groupes).map(([cat, msgs]) => `
      <div class="ms-cat">
        <div class="ms-cat-titre ms-${ech(cat)}">${ech(LIBELLES[cat] || cat)} (${msgs.length})</div>
        ${msgs.map((m, i) => `
          <div class="ms-mail" data-compte="${ech(m.compte)}" data-id="${ech(m.id)}">
            <div class="ms-ligne">
              <span class="ms-de">${ech((m.de || '').slice(0, 40))}</span>
              <span class="ms-src">${ech(m.source || '')}</span>
            </div>
            <div class="ms-sujet">${ech(m.sujet || '')}</div>
            <div class="ms-raison">${ech(m.raison || '')}</div>
            ${cat === 'a_repondre' || cat === 'important'
              ? `<button class="btn ms-btn" data-action="brouillon">PROPOSER UNE REPONSE</button>` : ''}
            <div class="ms-brouillon" hidden></div>
          </div>`).join('')}
      </div>`).join('')
      || '<div class="rg-note">Aucun message.</div>';

    liste.querySelectorAll('[data-action="brouillon"]').forEach((b) => {
      b.addEventListener('click', async () => {
        const bloc = b.closest('.ms-mail');
        const sortie = bloc.querySelector('.ms-brouillon');
        sortie.hidden = false;
        sortie.textContent = 'REDACTION EN COURS...';
        try {
          const r = await appelerJarvis('proposer_reponse_mail', {
            compte: bloc.dataset.compte, id: bloc.dataset.id, consigne: '' });
          if (!r.ok) {
            sortie.innerHTML = `<div class="sec-etat erreur">${ech(r.erreur || 'echec')}</div>`;
            return;
          }
          // Le brouillon est EDITABLE : on n'envoie pas un texte que
          // l'utilisateur n'a pas pu corriger.
          sortie.innerHTML = `
            <textarea class="ms-brouillon-texte" rows="8">${ech(r.brouillon)}</textarea>
            <div class="ms-envoi-barre">
              <button class="btn ms-btn" data-action="envoyer">ENVOYER</button>
              <span class="ms-avert">Relis avant d'envoyer : un message parti
              ne se rattrape pas.</span>
            </div>
            <div class="ms-resultat"></div>`;

          sortie.querySelector('[data-action="envoyer"]').addEventListener('click', async () => {
            const corps = sortie.querySelector('textarea').value.trim();
            const res = sortie.querySelector('.ms-resultat');
            if (!corps) { res.textContent = 'Corps vide.'; return; }
            const de = bloc.querySelector('.ms-de').textContent;
            const sujet = 'Re: ' + bloc.querySelector('.ms-sujet').textContent;
            // L'accord porte sur le contenu REEL, pas sur une intention.
            const apercu = corps.length > 400 ? corps.slice(0, 400) + '\n[...]' : corps;
            const ok = window.confirm(
              'ENVOYER CE MESSAGE ?\n\n'
              + `Compte : ${bloc.dataset.compte}\n`
              + `A : ${de}\n`
              + `Objet : ${sujet}\n\n`
              + apercu
              + '\n\nUn e-mail envoye ne peut pas etre rappele.');
            if (!ok) { res.textContent = 'Envoi annule.'; return; }
            res.textContent = 'ENVOI EN COURS...';
            try {
              const e = await appelerJarvis('envoyer_mail', {
                compte: bloc.dataset.compte, destinataire: de, sujet, corps,
                repondre_a_id: bloc.dataset.id, confirme: true });
              res.innerHTML = e.ok
                ? `<span class="ms-ok">ENVOYE a ${ech(e.a)}</span>`
                : `<span class="sec-etat erreur">${ech(e.erreur || e.message || 'echec')}</span>`;
            } catch (err) {
              res.innerHTML = `<span class="sec-etat erreur">${ech(err.message)}</span>`;
            }
          });
        } catch (e) {
          sortie.innerHTML = `<div class="sec-etat erreur">${ech(e.message)}</div>`;
        }
      });
    });
  }

  zone.querySelector('#ms-relever').addEventListener('click', async () => {
    etat.textContent = 'RELEVE ET CLASSEMENT EN COURS (IMAP x3 + modele)...';
    etat.className = 'sec-etat';
    try {
      const r = await appelerJarvis('get_courrier', { limite: 10 });
      const pannes = (r.comptes || []).filter((c) => !c.ok);
      etat.textContent = `${r.total || 0} message(s)`
        + (pannes.length ? ` — ${pannes.length} compte(s) en echec : `
            + pannes.map((c) => `${c.name} (${c.error || 'inconnu'})`).join(', ') : '');
      etat.className = `sec-etat ${pannes.length ? 'erreur' : 'ok'}`;
      rendre(r.groupes || {}, r.comptes || []);
    } catch (e) {
      etat.textContent = e.message;
      etat.className = 'sec-etat erreur';
    }
  });
}

// ── Scolaire (Pronote via Home Assistant) ─────────────────────────────────
//
// Lecture pure (get_agenda_scolaire) + un bouton pour ecrire dans l'agenda
// Google dedie (agenda_scolaire_sync). Les deux reutilisent EXACTEMENT les
// fonctions verifiees par _test_agenda_scolaire.py cote JARVIS ; ce panneau
// ne fait qu'afficher ce qu'elles renvoient.
//
// Devoirs, evaluations, notes, plan de revision genere : PAS ICI. Aucune de
// ces donnees n'est cablee cote Pronote/HA aujourd'hui (voir le plan de ce
// lot) — les afficher inventerait un contenu au lieu de dire l'absence,
// exactement l'erreur deja commise deux fois cette session avec Pronote.

function memeJourParis(isoDebut, aujourdHui) {
  // Comparaison sur la date locale Europe/Paris, pas UTC : un cours a
  // 23h30 ne doit pas basculer sur le mauvais jour pour un fuseau plus a
  // l'ouest. `isoDebut` est deja un horaire local Pronote (voir
  // agenda_scolaire.normaliser), donc une comparaison de chaine sur les
  // 10 premiers caracteres suffit sans reinterpreter le fuseau.
  return String(isoDebut || '').slice(0, 10) === aujourdHui;
}

function heureLocale(iso) {
  const m = /T(\d{2}):(\d{2})/.exec(String(iso || ''));
  return m ? `${m[1]}h${m[2]}` : '—';
}

// ── Panneau scolaire : le visuel de la maquette « Panneau Scolaire JARVIS » ──
//
// Mise en page reprise de design/Main.dc.html (artefact) : coins en
// equerre, lignes de scan, cartes a lisere colore par matiere, barres de
// charge, bloc date des evaluations. Couleurs et police suivent le HUD
// (--accent-rgb / --accent-primary, TheGoodMonolith) : le cyan #00e5ff et
// le Courier de la maquette juraient avec le reste de JARVIS et ignoraient
// le theme choisi (24/09/2026).
//
// AGRANDIR : le cadre part dans un <dialog> modal (couche superieure) qui
// couvre presque tout l'ecran, les trois vues cote a cote. Il faut sortir
// du .data-panel : son backdrop-filter piege les position:fixed.
//
// Les donnees, elles, sont les VRAIES : Pronote via Home Assistant. Une
// source muette affiche son absence et sa raison — jamais un contenu
// plausible invente (panne du 03/09/2026).

const SC_COULEURS = {
  'MATHS': 'var(--accent-primary)', 'MATHEMATIQUES': 'var(--accent-primary)',
  'PHYSIQUE-CHIMIE': '#7df4ff',
  'SVT': '#5ee9b5', 'SCIENCES VIE & TERRE': '#5ee9b5',
  'ANGLAIS': '#ff8a1a', 'ANGLAIS LV1': '#ff8a1a',
  'HISTOIRE-GEO': '#b98cff', 'HISTOIRE-GEOGRAPHIE': '#b98cff',
  'FRANCAIS': '#ffd166',
  'ESPAGNOL LV2': '#ff6ec7', 'EDUCATION MUSICALE': '#9ad0ff',
  'ARTS PLASTIQUES': '#ffa8d2', 'TECHNOLOGIE': '#8affc1',
  'EMI': '#c0f0ff', 'ED.PHYSIQUE&SPORT.': '#ff5f6d',
};
const SC_ROUGE = '#ff2e4d';
const SC_ORANGE = '#ff8a1a';

function scCouleur(matiere) {
  return SC_COULEURS[String(matiere || '').toUpperCase().trim()] || 'var(--accent-primary)';
}

function scDuree(minutes) {
  const m = Number(minutes) || 0;
  return m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? String(m % 60).padStart(2, '0') : ''}` : `${m} min`;
}

function initScolaire(zone) {
  const SOUS_VUES = [['jour', 'Ce soir'], ['semaine', 'Semaine'], ['notes', 'Evaluations']];

  const S = {
    cadre: 'position: relative; box-sizing: border-box; max-width: 100%; overflow-x: hidden; overflow-wrap: anywhere; background: rgba(var(--accent-rgb),0.025); border: 1px solid rgba(var(--accent-rgb),0.35); border-radius: 4px; box-shadow: 0 0 40px rgba(var(--accent-rgb),0.12), inset 0 0 60px rgba(var(--accent-rgb),0.03); color: var(--accent-primary); padding: 16px 16px 12px; overflow: hidden;',
    scan: 'position: absolute; inset: 0; pointer-events: none; z-index: 1; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(var(--accent-rgb),0.018) 2px, rgba(var(--accent-rgb),0.018) 4px);',
    coin: 'position: absolute; width: 14px; height: 14px; z-index: 2;',
    entete: 'display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid rgba(var(--accent-rgb),0.2); padding-bottom: 8px; margin-bottom: 12px;',
    surtitre: 'font-size: 9px; letter-spacing: 3px; color: rgba(var(--accent-rgb),0.6);',
    titre: 'font-size: 17px; letter-spacing: 2px; margin-top: 4px;',
    pastille: 'width: 7px; height: 7px; border-radius: 50%; background: var(--accent-primary); box-shadow: 0 0 6px var(--accent-primary);',
    sync: 'font-size: 9px; letter-spacing: 2px; color: rgba(var(--accent-rgb),0.55);',
    section: 'font-size: 9px; letter-spacing: 2px; color: rgba(var(--accent-rgb),0.5); margin-bottom: 7px;',
    discret: 'font-size: 10px; color: rgba(var(--accent-rgb),0.45);',
    vide: 'font-size: 12px; color: rgba(var(--accent-rgb),0.4); font-style: italic; padding: 14px 0;',
    pied: 'display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(var(--accent-rgb),0.2); padding-top: 10px; margin-top: 12px;',
    bouton: 'cursor: pointer; font-size: 10px; letter-spacing: 1px; text-transform: uppercase; padding: 7px 13px; border-radius: 2px; background: rgba(var(--accent-rgb),0.08); border: 1px solid rgba(var(--accent-rgb),0.4); color: var(--accent-primary);',
    carteBloc: 'display: flex; gap: 11px; align-items: flex-start; background: rgba(var(--accent-rgb),0.035); border: 1px solid rgba(var(--accent-rgb),0.14); border-radius: 2px; padding: 10px 12px;',
  };
  const styleOnglet = (actif) => actif
    ? 'cursor: pointer; flex: 1 1 0; text-align: center; white-space: nowrap; background: rgba(var(--accent-rgb),0.14); border: 1px solid var(--accent-primary); color: var(--accent-primary); padding: 6px 4px; font-size: 9px; text-transform: uppercase; letter-spacing: 1px; border-radius: 2px;'
    : 'cursor: pointer; flex: 1 1 0; text-align: center; white-space: nowrap; background: rgba(var(--accent-rgb),0.04); border: 1px solid rgba(var(--accent-rgb),0.18); color: rgba(var(--accent-rgb),0.45); padding: 6px 4px; font-size: 9px; text-transform: uppercase; letter-spacing: 1px; border-radius: 2px;';

  zone.innerHTML = `
    <div style="${S.cadre}" id="sc-cadre">
      <div style="${S.scan}"></div>
      <div style="${S.coin} top: 4px; left: 4px; border-top: 2px solid var(--accent-primary); border-left: 2px solid var(--accent-primary);"></div>
      <div style="${S.coin} top: 4px; right: 4px; border-top: 2px solid var(--accent-primary); border-right: 2px solid var(--accent-primary);"></div>
      <div style="${S.coin} bottom: 4px; left: 4px; border-bottom: 2px solid var(--accent-primary); border-left: 2px solid var(--accent-primary);"></div>
      <div style="${S.coin} bottom: 4px; right: 4px; border-bottom: 2px solid var(--accent-primary); border-right: 2px solid var(--accent-primary);"></div>

      <div style="position: relative; z-index: 3;" id="sc-contenu">
        <div style="${S.entete}">
          <div>
            <div style="${S.surtitre}">SCOLAIRE // PRONOTE</div>
            <div style="${S.titre}" id="sc-eleve">ÉLÈVE</div>
          </div>
          <div style="display: flex; align-items: center; gap: 7px; flex-wrap: wrap; justify-content: flex-end;">
            <div style="${S.pastille}" id="sc-pastille"></div>
            <span style="${S.sync}" id="sc-sync-texte">CONNEXION…</span>
            <button type="button" class="sc-agrandir" id="sc-agrandir" title="Agrandir (Echap pour revenir)">⤢ AGRANDIR</button>
          </div>
        </div>

        <div id="sc-alerte"></div>

        <div style="display: flex; gap: 5px; margin-bottom: 12px;" id="sc-onglets">
          ${SOUS_VUES.map(([id, lib], i) =>
            `<div data-sc="${id}" style="${styleOnglet(i === 0)}">${lib}</div>`).join('')}
        </div>

        <div class="sc-grille">
          <div data-sc-corps="jour" data-titre="Ce soir"></div>
          <div data-sc-corps="semaine" data-titre="Semaine" hidden></div>
          <div data-sc-corps="notes" data-titre="Evaluations" hidden></div>
        </div>

        <div style="${S.pied}">
          <div style="${S.discret}" id="sc-avancement">—</div>
          <div style="${S.bouton}" id="sc-rafraichir">
            <span style="display:inline-flex; align-items:center; gap:7px;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M21 3v5h-5"></path>
                <path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path><path d="M3 21v-5h5"></path>
              </svg> Rafraichir
            </span>
          </div>
        </div>
      </div>
    </div>`;

  const zoneAlerte = zone.querySelector('#sc-alerte');
  const syncTexte = zone.querySelector('#sc-sync-texte');
  const pastille = zone.querySelector('#sc-pastille');
  const avancement = zone.querySelector('#sc-avancement');
  const corps = {};
  for (const [id] of SOUS_VUES) corps[id] = zone.querySelector(`[data-sc-corps="${id}"]`);

  let cours = null;
  let dn = null;
  let plan = null;
  let minuterie = null;
  let faits = {};
  try { faits = JSON.parse(localStorage.getItem('sc-faits') || '{}'); } catch (e) { faits = {}; }

  const dateParis = (dec = 0) => {
    const d = new Date();
    d.setDate(d.getDate() + dec);
    return d.toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' });
  };
  const jourNom = (iso) => new Date(`${iso}T12:00:00`)
    .toLocaleDateString('fr-FR', { weekday: 'short' }).replace('.', '');
  const jourNum = (iso) => String(Number(String(iso).slice(8, 10)));
  const joursRestants = (iso) => {
    if (!iso) return null;
    const c = new Date(`${String(iso).slice(0, 10)}T12:00:00`);
    return Math.round((c - new Date(`${dateParis()}T12:00:00`)) / 86400000);
  };
  const echeance = (iso) => {
    const j = joursRestants(iso);
    if (j === null || Number.isNaN(j)) return '';
    if (j < 0) return `EN RETARD ${-j}J`;
    if (j === 0) return "CE SOIR";
    if (j === 1) return 'DEMAIN';
    return `J-${j}`;
  };
  const rien = (t) => `<div style="${S.vide}">${ech(t)}</div>`;

  function etatSync(texte, alerte) {
    syncTexte.textContent = texte;
    syncTexte.style.color = alerte ? SC_ORANGE : 'rgba(var(--accent-rgb),0.55)';
    pastille.style.background = alerte ? SC_ORANGE : 'var(--accent-primary)';
    pastille.style.boxShadow = `0 0 6px ${alerte ? SC_ORANGE : 'var(--accent-primary)'}`;
  }

  // ── Bandeau PROFESSEUR ABSENT ─────────────────────────────────────────
  const cleIgnore = () => `sc-alerte-ignoree-${dateParis()}`;

  function rendreAlerte() {
    if (!cours || localStorage.getItem(cleIgnore()) === '1') { zoneAlerte.innerHTML = ''; return; }
    const auj = dateParis();
    const annules = cours.filter((c) => memeJourParis(c.debut, auj) && c.annule)
      .sort((a, b) => String(a.debut).localeCompare(String(b.debut)));
    if (!annules.length) { zoneAlerte.innerHTML = ''; return; }

    const texte = annules.map((c) =>
      `${c.matiere} de ${heureLocale(c.debut)} a ${heureLocale(c.fin)}`).join(', ');
    zoneAlerte.innerHTML = `
      <div style="display: flex; gap: 12px; align-items: flex-start; background: rgba(255,138,26,0.09); border: 1px solid rgba(255,138,26,0.45); border-left: 3px solid ${SC_ORANGE}; border-radius: 3px; padding: 11px 13px; margin-bottom: 12px;">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${SC_ORANGE}" stroke-width="1.6" stroke-linecap="round" style="flex-shrink: 0; margin-top: 1px;">
          <path d="M12 9v4"></path><path d="M12 17h.01"></path>
          <path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"></path>
        </svg>
        <div style="flex-grow: 1;">
          <div style="font-size: 10px; letter-spacing: 2px; color: ${SC_ORANGE};">PROFESSEUR ABSENT</div>
          <div style="font-size: 13px; margin-top: 5px; line-height: 1.45; color: var(--text-primary);">${ech(texte)}.</div>
          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;">
            <div id="sc-caler" style="cursor: pointer; white-space: nowrap; font-size: 9px; letter-spacing: 1px; text-transform: uppercase; padding: 6px 12px; border-radius: 2px; background: rgba(255,138,26,0.16); border: 1px solid ${SC_ORANGE}; color: ${SC_ORANGE};">Utiliser ce creneau</div>
            <div id="sc-ignorer" style="cursor: pointer; white-space: nowrap; font-size: 9px; letter-spacing: 1px; text-transform: uppercase; padding: 6px 12px; border-radius: 2px; background: rgba(var(--accent-rgb),0.04); border: 1px solid rgba(var(--accent-rgb),0.18); color: rgba(var(--accent-rgb),0.5);">Ignorer</div>
          </div>
          <div style="font-size: 11px; color: rgba(var(--accent-rgb),0.55); margin-top: 8px;" id="sc-caler-resultat"></div>
        </div>
      </div>`;

    zoneAlerte.querySelector('#sc-ignorer').addEventListener('click', () => {
      localStorage.setItem(cleIgnore(), '1');
      zoneAlerte.innerHTML = '';
    });
    zoneAlerte.querySelector('#sc-caler').addEventListener('click', () => {
      const sortie = zoneAlerte.querySelector('#sc-caler-resultat');
      const jp = plan && (plan.jours || []).find((j) => j.date === dateParis());
      const b = jp && (jp.blocs || [])[0];
      sortie.innerHTML = b
        ? `▸ <span style="color:${scCouleur(b.matiere)};">${ech(b.matiere)}</span> — ${ech(b.titre)} (${scDuree(b.minutes)})`
        : "Rien de prioritaire a caler : le plan n'a rien pour aujourd'hui.";
    });
  }

  // ── CE SOIR ───────────────────────────────────────────────────────────
  function basculerFait(cle) {
    faits[cle] = !faits[cle];
    try { localStorage.setItem('sc-faits', JSON.stringify(faits)); } catch (e) { /* quota */ }
    rendreJour();
    majAvancement();
  }

  function rendreJour() {
    if (!cours) { corps.jour.innerHTML = rien('Lecture en cours…'); return; }
    const auj = dateParis();
    const duJour = cours.filter((c) => memeJourParis(c.debut, auj))
      .sort((a, b) => String(a.debut).localeCompare(String(b.debut)));
    const maintenant = new Date();

    const lignesCours = duJour.length === 0
      ? rien("Aucun cours aujourd'hui.")
      : duJour.map((c) => {
          const passe = new Date(c.fin) < maintenant && !c.annule;
          const enCours = !c.annule && new Date(c.debut) <= maintenant && new Date(c.fin) > maintenant;
          const etat = c.annule ? 'ANNULE' : (enCours ? 'EN COURS' : (passe ? 'FAIT' : ''));
          const etatCouleur = c.annule ? SC_ORANGE : (enCours ? 'var(--accent-primary)' : 'rgba(var(--accent-rgb),0.4)');
          const fond = enCours ? 'background: rgba(var(--accent-rgb),0.07);' : '';
          return `
            <div style="display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; padding: 6px 9px; border-radius: 2px; border: 1px solid rgba(var(--accent-rgb),0.10); ${fond}${passe ? 'opacity:.5;' : ''}">
              <span style="flex: 0 0 auto; font-size: 11px; color: rgba(var(--accent-rgb),0.55);">${heureLocale(c.debut)}–${heureLocale(c.fin)}</span>
              <span style="flex: 1 1 90px; min-width: 0; font-size: 12px; letter-spacing: 1px; color: ${scCouleur(c.matiere)};">${ech(c.matiere)}</span>
              <span style="font-size: 10px; color: rgba(var(--accent-rgb),0.35);">${ech(c.salle || '')}</span>
              <span style="font-size: 10px; color: ${etatCouleur}; letter-spacing: 1px;">${etat}</span>
            </div>`;
        }).join('');

    let soirTotal = '';
    let blocsSoir = rien('Plan non genere.');
    if (plan) {
      const jp = (plan.jours || []).find((j) => j.date === auj);
      const blocs = (jp && jp.blocs) || [];
      soirTotal = jp ? `${scDuree(jp.utilise)} / ${scDuree(jp.minutes)}` : '';
      blocsSoir = blocs.length === 0
        ? rien('Rien de prevu ce soir. Le reste tient dans la semaine.')
        : blocs.map((b, i) => {
            const cle = `${auj}|${b.matiere}|${b.titre}|${i}`;
            const fait = !!faits[cle];
            const accent = b.deborde ? SC_ROUGE : scCouleur(b.matiere);
            const caseStyle = 'cursor: pointer; flex-shrink: 0; width: 17px; height: 17px; border-radius: 2px; display: flex; align-items: center; justify-content: center; margin-top: 2px; '
              + (fait ? 'background: var(--accent-primary); border: 1px solid var(--accent-primary);' : 'border: 1px solid rgba(var(--accent-rgb),0.45);');
            const titreStyle = 'font-size: 13px; margin-top: 3px; line-height: 1.4; '
              + (fait ? 'color: rgba(var(--accent-rgb),0.35); text-decoration: line-through;' : 'color: var(--text-primary);');
            return `
              <div style="${S.carteBloc} border-left: 2px solid ${accent}; margin-bottom: 6px;">
                <div class="sc-case" data-cle="${ech(cle)}" style="${caseStyle}">
                  ${fait ? '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#050508" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>' : ''}
                </div>
                <div style="flex-grow: 1;">
                  <div style="font-size: 9px; letter-spacing: 2px; color: ${accent};">${ech(b.matiere)}</div>
                  <div style="${titreStyle}">${ech(b.titre)}</div>
                  <div style="font-size: 10px; color: rgba(var(--accent-rgb),0.4); margin-top: 4px;">${b.deborde ? 'SURCHARGE — a caler malgre tout' : (b.type === 'revision' ? 'Revision' : 'Devoir')}</div>
                </div>
                <span style="font-size: 11px; color: rgba(var(--accent-rgb),0.5); flex-shrink: 0;">${scDuree(b.minutes)}</span>
              </div>`;
          }).join('');
    }

    corps.jour.innerHTML = `
      <div style="${S.section}">EMPLOI DU TEMPS — ${ech(jourNom(auj).toUpperCase())} ${jourNum(auj)}</div>
      <div style="display: flex; flex-direction: column; gap: 3px; margin-bottom: 14px;">${lignesCours}</div>
      <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 7px;">
        <span style="${S.section} margin-bottom:0;">A FAIRE CE SOIR</span>
        <span style="${S.discret}">${ech(soirTotal)}</span>
      </div>
      ${blocsSoir}`;

    corps.jour.querySelectorAll('.sc-case').forEach((el) => {
      el.addEventListener('click', () => basculerFait(el.dataset.cle));
    });
  }

  // ── SEMAINE ───────────────────────────────────────────────────────────
  function rendreSemaine() {
    if (!cours) { corps.semaine.innerHTML = rien('Lecture en cours…'); return; }
    const jours = [];
    for (let i = 0; i < 7; i += 1) jours.push(dateParis(i));

    const cartes = jours.map((d) => {
      const jp = plan && (plan.jours || []).find((j) => j.date === d);
      const blocs = (jp && jp.blocs) || [];
      const utilise = jp ? jp.utilise : 0;
      const capacite = jp ? jp.minutes : 0;
      const surcharge = jp ? utilise > capacite : false;
      const pct = capacite ? Math.min(100, Math.round((utilise / capacite) * 100)) : 0;

      const duJour = cours.filter((c) => memeJourParis(c.debut, d) && !c.annule);
      const annules = cours.filter((c) => memeJourParis(c.debut, d) && c.annule).length;

      const carteStyle = 'padding: 11px 13px; border-radius: 2px; margin-bottom: 7px; '
        + (surcharge
            ? 'background: rgba(255,46,77,0.06); border: 1px solid rgba(255,46,77,0.4);'
            : 'background: rgba(var(--accent-rgb),0.03); border: 1px solid rgba(var(--accent-rgb),0.13);');

      const listeBlocs = blocs.map((b) => {
        const accent = b.deborde ? SC_ROUGE : scCouleur(b.matiere);
        return `
          <div style="display: flex; flex-wrap: wrap; gap: 3px 9px; align-items: baseline;">
            <span style="width: 4px; height: 4px; border-radius: 50%; background: ${accent}; flex-shrink: 0;"></span>
            <span style="font-size: 9px; letter-spacing: 1px; color: ${accent}; flex: 0 1 auto; min-width: 0;">${ech(b.matiere)}</span>
            <span style="flex: 1 1 100%; min-width: 0; font-size: 11px; line-height: 1.4; ${b.deborde ? `color:${SC_ROUGE};` : 'color: var(--text-secondary);'}">${ech(b.titre)}</span>
            <span style="font-size: 10px; color: rgba(var(--accent-rgb),0.4); flex-shrink: 0;">${scDuree(b.minutes)}</span>
          </div>`;
      }).join('');

      return `
        <div style="${carteStyle}">
          <div style="display: flex; justify-content: space-between; align-items: baseline;">
            <span style="font-size: 11px; letter-spacing: 2px;">${ech(jourNom(d).toUpperCase())} ${jourNum(d)}
              <span style="font-size:9px; color:rgba(var(--accent-rgb),0.4); letter-spacing:1px;">· ${duJour.length} COURS${annules ? ` · ${annules} ANNULE` : ''}</span>
            </span>
            <span style="font-size: 10px; color: ${surcharge ? SC_ROUGE : 'rgba(var(--accent-rgb),0.45)'};">${utilise === 0 ? '—' : `${scDuree(utilise)} / ${scDuree(capacite)}`}</span>
          </div>
          <div style="height: 2px; background: rgba(var(--accent-rgb),0.12); margin: 7px 0 9px; overflow: hidden;">
            <div style="height: 100%; width: ${pct}%; background: ${surcharge ? SC_ROUGE : 'var(--accent-primary)'}; box-shadow: 0 0 6px ${surcharge ? SC_ROUGE : 'var(--accent-primary)'};"></div>
          </div>
          ${blocs.length ? `<div style="display: flex; flex-direction: column; gap: 5px;">${listeBlocs}</div>`
                         : '<div style="font-size: 11px; color: rgba(var(--accent-rgb),0.35); font-style: italic;">Libre.</div>'}
        </div>`;
    }).join('');

    const resume = plan
      ? `${plan.en_surcharge ? `${plan.en_surcharge} EN SURCHARGE` : 'TIENT DANS LA SEMAINE'}${plan.hors_fenetre ? ` · ${plan.hors_fenetre} AU-DELA` : ''}`
      : 'PLAN NON GENERE';
    corps.semaine.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
        <span style="${S.section} margin-bottom:0;">PLAN GENERE — ${ech(resume)}</span>
        <span style="${S.discret}">${plan ? `${plan.minutes_par_soir} min/soir` : ''}</span>
      </div>
      ${cartes}`;
  }

  // ── EVALUATIONS ───────────────────────────────────────────────────────
  function rendreNotes() {
    if (!dn) { corps.notes.innerHTML = rien('Lecture en cours…'); return; }

    const evals = (dn.evaluations || []).slice().sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const notes = dn.notes || [];
    const moyennes = dn.moyennes || [];
    const devoirs = (dn.devoirs || []).filter((d) => !d.fait)
      .sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const incidents = [...(dn.absences || []), ...(dn.retards || []), ...(dn.punitions || [])];

    const carteEval = (e) => {
      const accent = scCouleur(e.matiere);
      const d = String(e.date || '').slice(0, 10);
      return `
        <div style="display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; background: rgba(var(--accent-rgb),0.035); border: 1px solid rgba(var(--accent-rgb),0.14); border-left: 2px solid ${accent}; border-radius: 2px; padding: 11px 13px; margin-bottom: 6px;">
          <div style="text-align: center; width: 52px; flex-shrink: 0;">
            <div style="font-size: 19px; letter-spacing: 1px; color: ${accent};">${ech(jourNum(d))}</div>
            <div style="font-size: 9px; letter-spacing: 2px; color: rgba(var(--accent-rgb),0.45);">${ech(jourNom(d).toUpperCase())}</div>
          </div>
          <div style="flex: 1 1 120px; min-width: 0;">
            <div style="font-size: 9px; letter-spacing: 2px; color: ${accent};">${ech(e.matiere || '?')}</div>
            <div style="font-size: 13px; margin-top: 3px; color: var(--text-primary);">${ech(e.nom || 'Evaluation')}</div>
            <div style="font-size: 10px; color: rgba(var(--accent-rgb),0.42); margin-top: 4px;">${ech(echeance(e.date))}</div>
          </div>
          <div style="text-align: right; flex-shrink: 0;">
            <div style="font-size: 9px; letter-spacing: 1px; color: rgba(var(--accent-rgb),0.4);">COEF</div>
            <div style="font-size: 15px;">${ech(e.coefficient || '—')}</div>
          </div>
        </div>`;
    };

    const ligneNote = (n) => `
      <div style="display: flex; flex-wrap: wrap; gap: 3px 12px; align-items: baseline; padding: 8px 12px; border: 1px solid rgba(var(--accent-rgb),0.1); border-radius: 2px; margin-bottom: 4px;">
        <span style="flex-grow: 1; font-size: 12px; letter-spacing: 1px; color: ${scCouleur(n.matiere)};">${ech(n.matiere || '?')}</span>
        <span style="font-size: 11px; color: rgba(var(--accent-rgb),0.4);">${ech(n.date || '')}</span>
        <span style="font-size: 15px; width: 62px; text-align: right;">${ech(n.note)}${n.bareme ? `<span style="font-size:10px; color:rgba(var(--accent-rgb),0.4);">/${ech(n.bareme)}</span>` : ''}</span>
      </div>`;

    const ligneDevoir = (d) => {
      const retard = joursRestants(d.date) !== null && joursRestants(d.date) < 0;
      const accent = retard ? SC_ROUGE : scCouleur(d.matiere);
      return `
        <div style="display: flex; flex-wrap: wrap; gap: 3px 10px; align-items: baseline; padding: 7px 11px; border: 1px solid rgba(var(--accent-rgb),0.1); border-left: 2px solid ${accent}; border-radius: 2px; margin-bottom: 4px;">
          <span style="font-size: 9px; letter-spacing: 1px; color: ${accent}; flex: 0 1 auto; min-width: 0;">${ech(d.matiere || '?')}</span>
          <span style="flex: 1 1 100%; min-width: 0; font-size: 11px; line-height: 1.4; color: var(--text-secondary);">${ech(d.titre || '')}</span>
          <span style="font-size: 10px; color: ${retard ? SC_ROUGE : 'rgba(var(--accent-rgb),0.45)'}; flex-shrink: 0;">${ech(echeance(d.date))}</span>
        </div>`;
    };

    const ligneMoyenne = (m) => `
      <div style="display: flex; flex-wrap: wrap; gap: 3px 12px; align-items: baseline; padding: 7px 12px; border: 1px solid rgba(var(--accent-rgb),0.1); border-radius: 2px; margin-bottom: 4px;">
        <span style="flex-grow: 1; font-size: 11px; letter-spacing: 1px; color: ${scCouleur(m.matiere)};">${ech(m.matiere || '?')}</span>
        <span style="font-size: 10px; color: rgba(var(--accent-rgb),0.4);">classe ${ech(m.classe || '—')}</span>
        <span style="font-size: 14px; width: 56px; text-align: right;">${ech(m.eleve || '—')}</span>
      </div>`;

    const ligneIncident = (i) => {
      const est = i.justifiee !== undefined ? 'Absence' : (i.minutes !== undefined ? 'Retard' : (i.nature || 'Punition'));
      const ok = i.justifiee === true || i.justifie === true;
      const c = ok ? 'rgba(var(--accent-rgb),0.5)' : SC_ORANGE;
      const detail = [i.debut || i.date, i.heures, i.minutes ? `${i.minutes} min` : '', i.motif, i.donnee_par]
        .filter(Boolean).join(' · ');
      return `
        <div style="display: flex; flex-wrap: wrap; gap: 3px 10px; align-items: baseline; padding: 7px 11px; border: 1px solid rgba(255,138,26,0.25); border-left: 2px solid ${c}; border-radius: 2px; margin-bottom: 4px;">
          <span style="font-size: 10px; letter-spacing: 1px; color: ${c}; flex: 0 0 auto;">${ech(est.toUpperCase())}</span>
          <span style="flex-grow: 1; font-size: 11px; color: var(--text-secondary);">${ech(detail)}</span>
          <span style="font-size: 9px; color: ${c};">${ok ? 'JUSTIFIE' : 'NON JUSTIFIE'}</span>
        </div>`;
    };

    corps.notes.innerHTML = `
      <div style="${S.section}">EVALUATIONS ANNONCEES</div>
      ${evals.length ? evals.map(carteEval).join('') : rien('Aucune evaluation annoncee.')}

      <div style="${S.section} margin-top:14px;">DEVOIRS A RENDRE</div>
      ${devoirs.length ? devoirs.map(ligneDevoir).join('') : rien('Aucun devoir a faire.')}

      <div style="${S.section} margin-top:14px;">DERNIERES NOTES</div>
      ${notes.length ? notes.map(ligneNote).join('') : rien('Aucune note — debut de trimestre.')}
      <div style="font-size: 10px; color: rgba(var(--accent-rgb),0.35); margin-top: 8px; letter-spacing: 1px; font-style: italic;">
        Moyenne generale — ${dn.moyenne ? ech(dn.moyenne) : 'non publiee'}
      </div>

      <div style="${S.section} margin-top:14px;">MOYENNES PAR MATIERE</div>
      ${moyennes.length ? moyennes.map(ligneMoyenne).join('') : rien('Pas encore de moyennes par matiere.')}

      <div style="${S.section} margin-top:14px;">ASSIDUITE</div>
      ${incidents.length ? incidents.map(ligneIncident).join('') : rien('Rien a signaler.')}`;
  }

  function majAvancement() {
    if (!plan) { avancement.textContent = '—'; return; }
    const jp = (plan.jours || []).find((j) => j.date === dateParis());
    const blocs = (jp && jp.blocs) || [];
    const total = blocs.length;
    const cochés = blocs.filter((b, i) => faits[`${dateParis()}|${b.matiere}|${b.titre}|${i}`]).length;
    avancement.textContent = total
      ? `${cochés}/${total} fait${cochés > 1 ? 's' : ''} ce soir`
      : 'Rien a faire ce soir';
  }

  // ── Chargements ───────────────────────────────────────────────────────
  async function charger() {
    etatSync('LECTURE…', false);
    try {
      const r = await appeler('get_agenda_scolaire');
      if (r.erreur) { etatSync(String(r.erreur).toUpperCase().slice(0, 46), true); cours = []; }
      else { cours = r.cours || []; etatSync(`${cours.length} COURS SYNCHRONISES`, false); }
    } catch (e) {
      etatSync(`ECHEC : ${e.message}`.toUpperCase().slice(0, 46), true);
      cours = [];
    }
    rendreAlerte(); rendreJour(); rendreSemaine();
  }

  async function chargerDN() {
    try {
      dn = await appeler('get_devoirs_notes');
      if (dn.raisons && dn.raisons.length) etatSync(String(dn.raisons[0]).toUpperCase().slice(0, 46), true);
    } catch (e) {
      dn = { devoirs: [], evaluations: [], notes: [], moyennes: [], absences: [], retards: [], punitions: [] };
      etatSync(`ECHEC : ${e.message}`.toUpperCase().slice(0, 46), true);
    }
    rendreNotes();
  }

  async function chargerPlan() {
    const minutes = parseInt(localStorage.getItem('sc-pr-minutes') || '75', 10) || 75;
    try {
      const r = await appeler('get_plan_revision', { minutes_par_soir: minutes });
      plan = r.plan;
    } catch (e) { plan = null; }
    rendreJour(); rendreSemaine(); rendreAlerte(); majAvancement();
  }

  zone.querySelectorAll('[data-sc]').forEach((b) => {
    b.addEventListener('click', () => {
      zone.querySelectorAll('[data-sc]').forEach((x) => {
        x.setAttribute('style', styleOnglet(x === b));
      });
      for (const [id] of SOUS_VUES) corps[id].hidden = id !== b.dataset.sc;
    });
  });

  zone.querySelector('#sc-rafraichir').addEventListener('click', () => {
    charger(); chargerDN(); chargerPlan();
  });

  // ── AGRANDIR : le cadre (et ses ecouteurs) part dans un <dialog> modal ──
  // showModal() = couche superieure, Echap et fond cliquable fournis par le
  // navigateur ; a la fermeture le cadre revient a sa place dans le panneau.
  const cadre = zone.querySelector('#sc-cadre');
  const boutonAgrandir = zone.querySelector('#sc-agrandir');
  let dialogue = null;
  boutonAgrandir.addEventListener('click', () => {
    if (dialogue?.open) { dialogue.close(); return; }
    if (!dialogue) {
      dialogue = document.createElement('dialog');
      dialogue.className = 'sc-dialog';
      dialogue.setAttribute('aria-label', 'Scolaire');
      // Clic sur le fond = fermer, gere par le navigateur (WebView2 >= 134) :
      // un glisse commence dans le cadre et relache sur le fond ne ferme pas,
      // ce qu'un test e.target === dialogue fait a tort.
      dialogue.setAttribute('closedby', 'any');
      document.body.appendChild(dialogue);
      dialogue.addEventListener('close', () => {
        zone.appendChild(cadre);
        boutonAgrandir.textContent = '⤢ AGRANDIR';
      });
    }
    dialogue.appendChild(cadre);
    boutonAgrandir.textContent = '⤡ REDUIRE';
    dialogue.showModal();
  });

  if (minuterie) clearInterval(minuterie);
  minuterie = setInterval(() => { if (cours) rendreJour(); }, 60000);

  rendreJour(); rendreSemaine(); rendreNotes();
  charger(); chargerDN(); chargerPlan();
}

// ── Assemblage ───────────────────────────────────────────────────────────

const VUES = [
  ['meteo', 'METEO', initMeteo],
  ['courses', 'COURSES', initCourses],
  ['notes', 'NOTES', initNotes],
  ['messagerie', 'MESSAGERIE', initMessagerie],
  ['scolaire', 'SCOLAIRE', initScolaire],
];

export function initQuotidien() {
  const conteneur = document.getElementById('rtab-daily');
  if (!conteneur) return;

  conteneur.innerHTML = `
    <div class="rg-onglets">
      ${VUES.map(([id, lib], i) =>
        `<button class="rg-onglet${i === 0 ? ' active' : ''}" data-q="${id}">${ech(lib)}</button>`
      ).join('')}
    </div>
    <div class="sec-corps" id="q-corps"></div>`;

  const corps = conteneur.querySelector('#q-corps');
  const montees = new Set();

  function afficher(id) {
    // Le scolaire agrandi est modal, par-dessus tout : si JARVIS bascule
    // vers un autre sous-onglet (open-panel SSE), le fermer, sinon la
    // bascule se fait derriere, invisible.
    if (id !== 'scolaire') document.querySelector('dialog.sc-dialog[open]')?.close();
    if (!montees.has(id)) {
      const zone = document.createElement('div');
      zone.dataset.q = id;
      corps.appendChild(zone);
      montees.add(id);
      const vue = VUES.find((v) => v[0] === id);
      try { vue[2](zone); } catch (e) {
        zone.innerHTML = `<div class="rg-note erreur">${ech(e.message)}</div>`;
      }
    }
    for (const enfant of corps.children) enfant.hidden = enfant.dataset.q !== id;
  }

  function selectionner(id) {
    const btn = conteneur.querySelector(`.rg-onglet[data-q="${id}"]`);
    if (!btn) return;
    conteneur.querySelectorAll('.rg-onglet').forEach((x) => x.classList.remove('active'));
    btn.classList.add('active');
    afficher(id);
  }

  conteneur.querySelectorAll('.rg-onglet').forEach((b) => {
    b.addEventListener('click', () => selectionner(b.dataset.q));
  });

  afficher('meteo');

  // « Montre le panneau scolaire » (voix/texte) : main2.py pousse
  // {action:'open_panel', panel:'daily', sub:'scolaire'}, gateway.js le
  // relaie en SSE sous 'open-panel'. Meme patron de connexion que
  // schedule.js (SSE partagee, montee par chat.js) : on attend qu'elle
  // existe plutot que d'en ouvrir une seconde.
  function ecouterOuverturePanneau() {
    const essayer = () => {
      const source = window.__jarvisSSE;
      if (!source) { setTimeout(essayer, 1000); return; }
      source.addEventListener('message', (e) => {
        try {
          const donnees = JSON.parse(e.data);
          if (donnees.type !== 'open-panel' || donnees.panel !== 'daily') return;
          document.querySelector('.tab-btn-r[data-rtab="daily"]')?.click();
          selectionner(donnees.sub || 'scolaire');
        } catch { /* evenement non JSON ou hors format attendu : ignore */ }
      });
    };
    essayer();
  }
  ecouterOuverturePanneau();
}
