// ── Orbe de verre (JARVIS 1.5) ───────────────────────────────────────────
//
// Même branchement que le HUD actuel, rien de nouveau côté serveur :
//   - /api/events (SSE) : états de JARVIS (« agent-state:… »), réponses
//     ({ text, done, role }), panneaux demandés (« open-panel »), événements
//     (« jarvis-event », dont ha_state_changed) ;
//   - POST /api/chat { message } : une question tapée ;
//   - appelerJarvis(type) : météo, Pronote, Home Assistant (liste blanche de
//     gateway.js, niveaux d'autorisation compris).
//
// Les données externes passent toujours par textContent, jamais innerHTML.

import { appelerJarvis } from '../components/appel-jarvis.js';

const $ = (id) => document.getElementById(id);
const racine = document.documentElement;

// ── Thème : automatique (clair de 7 h à 20 h), clair ou sombre ─────────────
const THEMES = ['auto', 'clair', 'sombre'];
const NOMS_THEME = { auto: 'automatique', clair: 'clair', sombre: 'sombre' };
const lire = (cle) => { try { return localStorage.getItem(cle); } catch { return null; } };
const ecrire = (cle, val) => { try { localStorage.setItem(cle, val); } catch { /* navigation privée */ } };
let choixTheme = THEMES.includes(lire('verre-theme')) ? lire('verre-theme') : 'auto';

function appliquerTheme() {
  const h = new Date().getHours();
  racine.dataset.theme = choixTheme === 'auto' ? (h >= 7 && h < 20 ? 'clair' : 'sombre') : choixTheme;
  $('theme').setAttribute('aria-label', `Thème : ${NOMS_THEME[choixTheme]}`);
  $('theme').title = `Thème : ${NOMS_THEME[choixTheme]}`;
}
$('theme').addEventListener('click', () => {
  choixTheme = THEMES[(THEMES.indexOf(choixTheme) + 1) % THEMES.length];
  ecrire('verre-theme', choixTheme);
  appliquerTheme();
});

// ── Heure ─────────────────────────────────────────────────────────────────
function horloge() {
  const d = new Date();
  $('heure').textContent = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  $('date').textContent = d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
  appliquerTheme();
}
horloge();
setInterval(horloge, 15000);

// ── État de JARVIS : l'île et l'orbe ──────────────────────────────────────
const TEXTES_ETAT = {
  idle: 'Jarvis t\'écoute', listening: 'Jarvis t\'écoute', thinking: 'Jarvis réfléchit…',
  responding: 'Jarvis parle', hors: 'Connexion à Jarvis…', ecoute: 'Parle, je t\'écoute…',
};
function etat(e) {
  const connu = TEXTES_ETAT[e] ? e : 'idle';
  racine.dataset.etat = connu;
  $('ile-texte').textContent = TEXTES_ETAT[connu];
}

// ── Onde vocale : 31 points, plus hauts au milieu ; le CSS les anime selon l'état ──
$('onde').append(...Array.from({ length: 31 }, (_, i) => {
  const point = document.createElement('i');
  point.style.setProperty('--i', String(i));
  point.style.setProperty('--haut', (2 + 8 * Math.exp(-(((i - 15) / 8) ** 2))).toFixed(1));
  return point;
}));

// ── Conversation ──────────────────────────────────────────────────────────
const SUJET_ECOLE = /devoir|[ée]valuation|contr[ôo]le|pronote|r[ée]vis|interro|moyenne|\bnotes?\b/i;
let derniereQuestion = '';

function repondre(texte) {
  $('reponse').textContent = texte;
  $('reponse').classList.toggle('long', texte.length > 140);
  const sujet = `${derniereQuestion} ${texte}`;
  if (SUJET_ECOLE.test(sujet)) montrerPronote();
  cartesPour(sujet);
}

// La phrase de l'utilisateur (dite ou tapée) s'affiche au-dessus de l'orbe ; la carte arrive avant la réponse.
function phraseUtilisateur(texte) {
  derniereQuestion = texte;
  $('question').textContent = `« ${texte} »`;
  if (SUJET_ECOLE.test(texte)) montrerPronote();
  cartesPour(texte);
}

$('saisie').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const champ = $('message');
  const texte = champ.value.trim();
  if (!texte) { champ.focus(); return; }
  champ.value = '';
  phraseUtilisateur(texte);
  etat('thinking');
  try {
    const r = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: texte }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  } catch (e) {
    $('reponse').textContent = `Je n'ai pas pu envoyer ta question (${e.message}).`;
    etat('idle');
  }
});

// ── Flux en direct ────────────────────────────────────────────────────────
function connecter() {
  const flux = new EventSource('/api/events');
  flux.onopen = () => etat('idle');
  flux.onerror = () => etat('hors');          // EventSource se reconnecte tout seul
  flux.onmessage = (message) => {
    let d;
    try { d = JSON.parse(message.data); } catch { return; }
    if (d.type === 'connected') { etat('idle'); return; }
    if (d.type === 'heartbeat' || d.type === 'system') return;
    if (typeof d.type === 'string' && d.type.startsWith('agent-state:')) {
      const e = d.type.slice('agent-state:'.length);
      // Le micro de JARVIS repasse par « idle » entre deux bouts de son : ça ne doit pas effacer « Parle… »
      if (e === 'idle' && racine.dataset.etat === 'ecoute') return;
      etat(e);
      return;
    }
    if (d.type === 'open-panel') {
      if (/scolaire|quotidien|pronote/i.test(`${d.panel || ''} ${d.sub || ''}`)) montrerPronote();
      return;
    }
    if (d.type === 'jarvis-event') {
      if (d.evenement?.type === 'ha_state_changed' && d.evenement.state) majEntite(d.evenement.state);
      return;
    }
    if (typeof d.text === 'string' && d.text) {
      if (d.role === 'user') phraseUtilisateur(d.text); else repondre(d.text);
    }
  };
}
connecter();

// ── Micro ─────────────────────────────────────────────────────────────────
// Sur le PC, l'oreille de JARVIS écoute déjà la pièce : le bouton lui dit « la prochaine phrase est pour
// toi » (ecoute_directe), sans le mot d'éveil. Sur un téléphone, cette oreille ne t'entend pas : on
// prend la dictée du navigateur (Safari, Chrome) et la phrase part comme si elle était tapée.
const Dictee = window.SpeechRecognition || window.webkitSpeechRecognition;
const surLePC = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
let minuteurEcoute = null;

async function micro() {
  if (surLePC || !Dictee) {
    try {
      const r = await appelerJarvis('ecoute_directe');
      if (r.muted) { $('reponse').textContent = 'Mon micro est coupé : réactive-le pour me parler.'; return; }
      etat('ecoute');
      clearTimeout(minuteurEcoute);
      minuteurEcoute = setTimeout(() => { if (racine.dataset.etat === 'ecoute') etat('idle'); }, 30000);
    } catch (e) {
      $('reponse').textContent = `Je n'arrive pas à t'écouter (${e.message}).`;
    }
    return;
  }
  const dictee = new Dictee();
  dictee.lang = 'fr-FR';
  dictee.interimResults = true;
  racine.dataset.micro = 'actif';
  etat('ecoute');
  dictee.onresult = (ev) => {
    $('message').value = [...ev.results].map((res) => res[0].transcript).join('');
    if (ev.results[ev.results.length - 1].isFinal) $('saisie').requestSubmit();
  };
  dictee.onerror = (ev) => { $('reponse').textContent = `Micro indisponible (${ev.error}).`; };
  dictee.onend = () => {
    delete racine.dataset.micro;
    if (racine.dataset.etat === 'ecoute') etat('idle');
  };
  dictee.start();
}
$('micro').addEventListener('click', micro);

// ── Météo ─────────────────────────────────────────────────────────────────
let donneesMeteo = null;   // la dernière météo reçue : en-tête et carte lisent la même
let dateMeteo = 0;

async function meteo() {
  try {
    const r = await appelerJarvis('get_meteo');
    const m = r.data ?? r;
    if (!m || m.temperature == null) throw new Error('vide');
    donneesMeteo = m;
    dateMeteo = Date.now();
    $('temp').textContent = `${m.temperature}°`;
    $('ciel').textContent = m.description || '';
    dessinerMeteo();
  } catch {
    $('temp').textContent = '--°';
    $('ciel').textContent = 'météo indisponible';
    dessinerMeteo();
  }
}
meteo();
setInterval(meteo, 15 * 60 * 1000);

// ── Pronote : apparaît quand on parle d'école, repart tout seul ────────────
const JOURS = ['DIM.', 'LUN.', 'MAR.', 'MER.', 'JEU.', 'VEN.', 'SAM.'];
let minuteurPanneau = null;
let chargePronote = 0;

function enDate(texte) {
  const d = new Date(String(texte || '').slice(0, 10) + 'T12:00:00');
  return Number.isNaN(d.getTime()) ? null : d;
}

function ligne(date, matiere, detail) {
  const li = document.createElement('li');
  const jour = document.createElement('div');
  jour.className = 'jour';
  const nomJour = document.createElement('span');
  const numero = document.createElement('b');
  nomJour.textContent = date ? JOURS[date.getDay()] : '—';
  numero.textContent = date ? String(date.getDate()) : '';
  jour.append(nomJour, numero);
  const texte = document.createElement('div');
  const m = document.createElement('div');
  const det = document.createElement('div');
  m.className = 'matiere';
  det.className = 'detail';
  m.textContent = matiere || 'Matière';
  det.textContent = detail || '';
  texte.append(m, det);
  li.append(jour, texte);
  return li;
}

async function montrerPronote() {
  const panneau = $('panneau-pronote');
  panneau.hidden = false;
  clearTimeout(minuteurPanneau);
  minuteurPanneau = setTimeout(() => { panneau.hidden = true; }, 90000);
  if (Date.now() - chargePronote < 5 * 60 * 1000) return;   // relu au plus toutes les 5 minutes
  const liste = $('pronote-liste');
  liste.replaceChildren(Object.assign(document.createElement('li'), { textContent: 'Lecture de Pronote…' }));
  try {
    const r = await appelerJarvis('get_devoirs_notes');
    const aujourdhui = new Date();
    aujourdhui.setHours(0, 0, 0, 0);
    const avenir = (x) => { const d = enDate(x.date); return d && d >= aujourdhui; };
    // Les contrôles d'abord : chez Pronote, ils arrivent souvent comme des devoirs (« Contrôle bilan… »),
    // la réponse vocale (tools/devoirs_vocal.py) les met déjà en tête de la même façon.
    const estEval = (x) => /contr[ôo]le|[ée]valuation|\binterro|\bds\b/i.test(`${x.nom || ''} ${x.description || ''}`);
    const parDate = (a, b) => (enDate(a.date) - enDate(b.date));
    const evals = (r.evaluations || []).filter(avenir)
      .map((e) => ({ date: e.date, matiere: e.matiere, texte: e.nom || e.description || 'Évaluation', eval: true }));
    const devoirs = (r.devoirs || []).filter((d) => !d.fait && avenir(d))
      .map((d) => ({ date: d.date, matiere: d.matiere, texte: d.description || 'Devoir', eval: estEval(d) }));
    const tout = [...evals, ...devoirs]
      .sort((a, b) => (Number(b.eval) - Number(a.eval)) || parDate(a, b))
      .slice(0, 4)
      .map((x) => ligne(enDate(x.date), x.matiere, x.texte));
    if (tout.length) {
      liste.replaceChildren(...tout);
    } else {
      const vide = (r.raisons || []).join(' · ') || 'Rien de prévu dans Pronote.';
      liste.replaceChildren(Object.assign(document.createElement('li'), { textContent: vide }));
    }
    chargePronote = Date.now();
  } catch (e) {
    liste.replaceChildren(Object.assign(document.createElement('li'), { textContent: `Pronote indisponible : ${e.message}` }));
  }
}
$('fermer-pronote').addEventListener('click', () => { $('panneau-pronote').hidden = true; });
$('reviser').addEventListener('click', () => {
  $('message').value = 'Fais-moi réviser';
  $('saisie').requestSubmit();
});

// ── Maison : lumières, volets, chauffage, alarme (lecture seule) ───────────
let entites = [];
const nomEntite = (e) => e.attributes?.friendly_name || e.entity_id;
const disponible = (e) => e && e.state !== 'unavailable' && e.state !== 'unknown';

function puce(texte, { avecInter = false, presse = null, auClic = null } = {}) {
  const el = document.createElement(auClic ? 'button' : 'div');
  el.className = 'puce' + (avecInter ? ' avec-inter' : '');
  if (auClic) { el.type = 'button'; el.addEventListener('click', auClic); }
  if (presse !== null) el.setAttribute('aria-pressed', String(presse));
  const t = document.createElement('span');
  t.textContent = texte;
  el.append(t);
  if (avecInter) {
    const inter = document.createElement('span');
    inter.className = 'inter';
    inter.setAttribute('aria-hidden', 'true');
    el.append(inter);
  }
  return el;
}

async function service(domain, serviceHa, entity_id) {
  try {
    await appelerJarvis('ha_call_service', { domain, service: serviceHa, entity_id });
  } catch (e) {
    $('reponse').textContent = `La maison n'a pas répondu (${e.message}).`;
  }
}

function dessinerMaison() {
  const zone = $('maison');
  const lumieres = entites.filter((e) => e.entity_id.startsWith('light.') && disponible(e))
    .sort((a, b) => Number(/salon/i.test(nomEntite(b))) - Number(/salon/i.test(nomEntite(a)))).slice(0, 2);
  const volets = entites.filter((e) => e.entity_id.startsWith('cover.') && disponible(e)).slice(0, 1);
  const chauffage = entites.find((e) => e.entity_id.startsWith('climate.') && disponible(e));
  const alarme = entites.find((e) => e.entity_id.startsWith('alarm_control_panel.') && disponible(e));
  const puces = [];
  for (const l of lumieres) {
    const allume = l.state === 'on';
    puces.push(puce(nomEntite(l), {
      avecInter: true, presse: allume,
      auClic: () => { l.state = allume ? 'off' : 'on'; dessinerMaison(); service('light', 'toggle', l.entity_id); },
    }));
  }
  // Lecture seule : gateway.js ne laisse passer aucun service « cover », un clic ne ferait qu'une erreur.
  for (const v of volets) puces.push(puce(`${nomEntite(v)} : ${v.state === 'open' ? 'ouverts' : 'fermés'}`));
  if (chauffage) {
    const t = chauffage.attributes?.current_temperature ?? chauffage.attributes?.temperature;
    puces.push(puce(`Chauffage ${t != null ? `${t} °C` : chauffage.state}`));
  }
  if (alarme) puces.push(puce(`Alarme ${alarme.state === 'disarmed' ? 'coupée' : 'activée'}`));
  zone.replaceChildren(...puces);
}

function majEntite(nouvelle) {
  const i = entites.findIndex((e) => e.entity_id === nouvelle.entity_id);
  if (i >= 0) { entites[i] = nouvelle; dessinerMaison(); dessinerMusique(); dessinerAppareils(); }
}

let dateEtats = 0;
async function maison() {
  dateEtats = Date.now();
  try {
    const r = await appelerJarvis('ha_get_states');
    entites = r.states || [];
    dessinerMaison();
    dessinerMusique();
    dessinerAppareils();
  } catch {
    $('maison').replaceChildren();                // pas de maison : rien à montrer
  }
}
maison();

// ── Cartes façon Opal : météo, musique, appareils ─────────────────────────
// Elles apparaissent quand on en parle (la phrase de l'utilisateur ou la réponse de JARVIS), comme le
// panneau Pronote, et repartent seules au bout de 90 s. Côté serveur, seule la météo détaillée (heures,
// pluie, mini/maxi) est nouvelle ; la musique et les appareils lisent Home Assistant.
const SUJETS = {
  meteo: /m[ée]t[ée]o|quel temps|pleu(?:t|voir)|pluie|temp[ée]rature|parapluie|il fait (?:chaud|froid|beau)|soleil|neige|orage/i,
  musique: /musique|chanson|morceau|spotify|deezer|playlist|lecteur|ce qui joue|qui chante/i,
  appareils: /appareils?|ordinateurs?|\btv\b|t[ée]l[ée](?![a-zà-ÿ])|ampli|connect[ée]s?(?![a-zà-ÿ])/i,
};
const CARTES = {
  meteo: { id: 'carte-meteo', charger: chargerMeteo },
  musique: { id: 'carte-musique', charger: chargerMusique },
  appareils: { id: 'carte-appareils', charger: chargerAppareils },
};
const minuteursCartes = {};

function montrerCarte(nom) {
  const carte = $(CARTES[nom].id);
  carte.hidden = false;
  clearTimeout(minuteursCartes[nom]);
  minuteursCartes[nom] = setTimeout(() => { carte.hidden = true; }, 90000);
  CARTES[nom].charger();
}

function cartesPour(texte) {
  for (const nom of Object.keys(SUJETS)) if (SUJETS[nom].test(texte)) montrerCarte(nom);
}

for (const bouton of document.querySelectorAll('[data-ferme]')) {
  bouton.addEventListener('click', () => { $(bouton.dataset.ferme).hidden = true; });
}

async function rafraichirEtats() { if (Date.now() - dateEtats > 5000) await maison(); }   // 5 s : une réponse en morceaux ne relit pas Home Assistant à chaque morceau

// Météo : la courbe des prochaines heures, l'heure en cours et le maximum repérés.
function chargerMeteo() { if (Date.now() - dateMeteo > 10 * 60 * 1000) meteo(); }

const SVG_NS = 'http://www.w3.org/2000/svg';
function noeud(nom, attributs, texte) {
  const n = document.createElementNS(SVG_NS, nom);
  for (const [cle, val] of Object.entries(attributs)) n.setAttribute(cle, val);
  if (texte !== undefined) n.textContent = texte;
  return n;
}

function dessinerCourbe(heures) {
  const svg = $('meteo-courbe');
  svg.toggleAttribute('hidden', heures.length < 2);          // un SVG n'a pas de propriété « hidden »
  if (heures.length < 2) return;
  const LARGE = 280, MARGE = 14, HAUT = 28, BAS = 62;             // viewBox 280 × 96 ; la courbe vit entre y = 28 et 62
  const temps = heures.map((p) => p.t);
  const mini = Math.min(...temps);
  const maxi = Math.max(...temps);
  const x = (i) => MARGE + (i * (LARGE - 2 * MARGE)) / (heures.length - 1);
  const y = (t) => (maxi === mini ? (HAUT + BAS) / 2 : BAS - ((t - mini) * (BAS - HAUT)) / (maxi - mini));
  const pts = heures.map((p, i) => [x(i), y(p.t)]);
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i += 1) {
    const [x0, y0] = pts[i - 1];
    const [x1, y1] = pts[i];
    const milieu = (x0 + x1) / 2;
    d += ` C${milieu} ${y0} ${milieu} ${y1} ${x1} ${y1}`;
  }
  const dernier = pts[pts.length - 1][0];
  const noeuds = [
    noeud('path', { class: 'aire', d: `${d} L${dernier} ${BAS + 8} L${pts[0][0]} ${BAS + 8} Z` }),
    noeud('path', { class: 'ligne', d }),
  ];
  for (const i of new Set([0, temps.indexOf(maxi)])) {
    noeuds.push(noeud('circle', { class: 'repere', cx: pts[i][0], cy: pts[i][1], r: 4 }));
    noeuds.push(noeud('text', { class: 'valeur', x: pts[i][0], y: pts[i][1] - 10 }, `${heures[i].t}°`));
  }
  heures.forEach((p, i) => { if (i % 2 === 0) noeuds.push(noeud('text', { x: x(i), y: 90 }, `${p.h} h`)); });
  svg.replaceChildren(...noeuds);
}

function dessinerMeteo() {
  const m = donneesMeteo;
  if (!m) {
    $('meteo-ville').textContent = 'Météo indisponible';
    $('meteo-temp').textContent = '--°';
    $('meteo-ciel').textContent = '';
    dessinerCourbe([]);
    return;
  }
  const ciel = m.description ? m.description[0].toUpperCase() + m.description.slice(1) : '';
  $('meteo-ville').textContent = m.ville || 'Météo';
  $('meteo-temp').textContent = `${m.temperature}°`;
  $('meteo-ciel').textContent = m.ressenti != null ? `${ciel} · ressenti ${m.ressenti}°` : ciel;
  $('meteo-vent').textContent = m.vent != null ? `${m.vent} km/h` : '--';
  $('meteo-pluie').textContent = m.pluie != null ? `${m.pluie} %` : '--';
  $('meteo-minmax').textContent = m.mini != null ? `${m.mini}° – ${m.maxi}°` : '--';
  dessinerCourbe(m.heures || []);
}

// Musique : le premier lecteur Home Assistant qui joue (ou, à défaut, en pause).
$('musique-barres').append(...Array.from({ length: 36 }, (_, i) => {
  const barre = document.createElement('i');
  barre.style.setProperty('--i', String(i));
  return barre;
}));

const lecteurActif = () => entites
  .filter((e) => e.entity_id.startsWith('media_player.') && (e.state === 'playing' || e.state === 'paused'))
  .sort((a, b) => Number(b.state === 'playing') - Number(a.state === 'playing'))[0];

function dessinerMusique() {
  const l = lecteurActif();
  const joue = l?.state === 'playing';
  $('musique-kicker').textContent = l ? `${joue ? 'En lecture' : 'En pause'} · sur ${nomEntite(l)}` : 'Musique';
  $('musique-titre').textContent = l ? (l.attributes?.media_title || 'Titre inconnu') : 'Rien en lecture pour le moment.';
  $('musique-artiste').textContent = l ? (l.attributes?.media_artist || l.attributes?.media_album_name || '') : '';
  $('musique-barres').classList.toggle('joue', joue);
  $('musique-commandes').hidden = !l;
  $('musique-pp').dataset.joue = String(joue);
}

async function chargerMusique() { await rafraichirEtats(); dessinerMusique(); }

function commandeMusique(serviceHa) {
  const l = lecteurActif();
  if (!l) return;
  if (serviceHa === 'media_play_pause') { l.state = l.state === 'playing' ? 'paused' : 'playing'; dessinerMusique(); }
  service('media_player', serviceHa, l.entity_id);
}
$('musique-prec').addEventListener('click', () => commandeMusique('media_previous_track'));
$('musique-pp').addEventListener('click', () => commandeMusique('media_play_pause'));
$('musique-suiv').addEventListener('click', () => commandeMusique('media_next_track'));

// Appareils : les lecteurs, télés et amplis allumés (ni éteints, ni hors ligne), un seul par nom : sur une vraie
// installation, Home Assistant en compte souvent deux par appareil et une trentaine au total.
const ETATS_APPAREIL = {
  playing: 'en lecture', paused: 'en pause', idle: 'en veille', standby: 'en veille',
  on: 'allumé', off: 'éteint', buffering: 'chargement',
};

function dessinerAppareils() {
  const vus = new Set();
  const allumes = entites
    .filter((e) => e.entity_id.startsWith('media_player.') && !['off', 'unavailable', 'unknown'].includes(e.state))
    .sort((a, b) => (Number(b.state === 'playing') - Number(a.state === 'playing'))
      || nomEntite(a).localeCompare(nomEntite(b), 'fr'))
    .filter((e) => !vus.has(nomEntite(e)) && vus.add(nomEntite(e)));
  $('appareils-nombre').textContent = allumes.length ? `${allumes.length} allumé${allumes.length > 1 ? 's' : ''}` : '';
  const lignes = allumes.slice(0, 5).map((e) => {
    const li = document.createElement('li');
    const point = document.createElement('span');
    point.className = `etat-point${e.state === 'playing' || e.state === 'on' ? ' actif' : ''}`;
    const nom = Object.assign(document.createElement('div'), { className: 'matiere', textContent: nomEntite(e) });
    const etatTexte = Object.assign(document.createElement('div'), {
      className: 'detail', textContent: ETATS_APPAREIL[e.state] || e.state,
    });
    const bloc = document.createElement('div');
    bloc.append(nom, etatTexte);
    li.append(point, bloc);
    return li;
  });
  const note = (texte) => Object.assign(document.createElement('li'), { className: 'doux', textContent: texte });
  if (allumes.length > 5) lignes.push(note(`+ ${allumes.length - 5} autres`));
  if (!lignes.length) lignes.push(note('Aucun appareil allumé.'));
  $('appareils-liste').replaceChildren(...lignes);
}

async function chargerAppareils() { await rafraichirEtats(); dessinerAppareils(); }
