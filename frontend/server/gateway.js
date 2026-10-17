// ── Adaptateur JARVIS ────────────────────────────────────────────────────
// Remplace la couche Gateway OpenClaw (ws://127.0.0.1:18789, protocole
// {type:'req'|'res'|'event'} avec authentification Ed25519 par appareil) par
// une connexion directe au WebSocket que main2.py emet deja sur :8765.
//
// L'original est conserve tel quel dans gateway-openclaw-original.js.
//
// POURQUOI CE SENS DE MIGRATION : le navigateur ne parle jamais WebSocket
// dans ce projet — il consomme du SSE (/api/events) et poste en REST
// (/api/chat). Le WebSocket est purement cote serveur. Remplacer ce seul
// fichier laisse donc intacts sse.js, chat.js, l'orbe et tous les panneaux,
// et supprime au passage toute la machinerie d'auth Ed25519 qu'OpenClaw
// exige et que JARVIS n'a pas. L'alternative (navigateur -> :8765 direct)
// coutait plus cher et faisait perdre les panneaux SSE.
//
// PROTOCOLE JARVIS (main2.py) — cle "action", pas "type" :
//   sortant  {action:'set_state', state:'idle'|'thinking'|'speaking'|'searching'}
//            {action:'jarvis_text', text:'...'}
//            {action:'user_speech', text:'...'}
//   entrant  {type:'user_input', text:'...'}
//            {type:'stop_audio'} {type:'get_agent_models'} ...

import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import WebSocket from 'ws';
import { broadcastEvent } from './sse.js';

// Le WebSocket de JARVIS est authentifie : premier message {token}, sous 10s,
// reponse auth_ok / auth_failed (comparaison a temps constant cote Python).
// On lit le jeton depuis le .env de JARVIS plutot que de le recopier ici :
// une seule source pour le secret, rien a resynchroniser, rien a fuiter.
const CHEMIN_ENV_JARVIS = process.env.JARVIS_ENV_PATH
  || fileURLToPath(new URL('../../.env', import.meta.url));   // frontend/server -> dossier de JARVIS

function lireJeton() {
  if (process.env.JARVIS_ACCESS_TOKEN) return process.env.JARVIS_ACCESS_TOKEN.trim();
  try {
    const lignes = fs.readFileSync(CHEMIN_ENV_JARVIS, 'utf8').split(/\r?\n/);
    for (const ligne of lignes) {
      const m = /^\s*JARVIS_ACCESS_TOKEN\s*=\s*(.*)$/.exec(ligne);
      if (m) return m[1].trim().replace(/^["']|["']$/g, '');
    }
  } catch (e) {
    journal('lecture du .env JARVIS impossible :', e.code || e.message);
  }
  return '';
}

// JARVIS n'a pas de notion de session : valeur de facade pour /api/status.
const SESSION_JARVIS = 'jarvis:main2:8765';

// Plafond d'autonomie : tout message d'un niveau superieur exige une
// confirmation explicite. 6 par defaut — lecture, ecriture et controle
// d'appareils passent seuls ; installation, reglages et suppressions non.
// Reglable sans toucher au code : JARVIS_NIVEAU_AUTONOMIE=10 pour tout
// laisser passer, =0 pour tout faire confirmer.
const NIVEAU_AUTONOMIE = (() => {
  const n = parseInt(process.env.JARVIS_NIVEAU_AUTONOMIE ?? '6', 10);
  return Number.isFinite(n) ? Math.min(10, Math.max(0, n)) : 6;
})();

// ── Liste blanche des messages relayables vers JARVIS ─────────────────────
// Le HUD doit pouvoir piloter ~30 panneaux. Ecrire une methode gwRequest
// dediee pour chacun ne passerait pas a l'echelle ; ouvrir un passe-plat
// generique laisserait le navigateur envoyer n'importe quel des 56 messages
// que ws_handler accepte, dont des actions destructrices (uninstall_program,
// av_threat_action...). Compromis : un passe-plat, mais borne a ce qui est
// explicitement declare ici, avec la reponse attendue quand il y en a une.
//
// reponse: null  => JARVIS n'accuse pas reception (on resout tout de suite)
//
// NIVEAU D'AUTORISATION (champ `niveau`, 1 a 10)
// Echelle reprise de usejarvis (src/roles/authority.ts), adaptee a JARVIS :
//     1-2  lecture seule
//     3-4  ecriture et bascules reversibles
//     5-6  commandes, reseau, controle d'appareils
//     7-8  installation de logiciel
//    9-10  reglages, suppression, irreversible
//
// Au-dela de NIVEAU_AUTONOMIE, le message est REFUSE tant qu'il n'arrive pas
// avec `confirme: true`. Le controle est ici et pas dans le navigateur :
// une page qui « oublie » de demander confirmation doit se faire refuser,
// sinon la garantie ne vaut rien. La confirmation visuelle de
// liste-actions.js reste utile, mais elle n'est plus la seule barriere.
const MESSAGES_AUTORISES = {
  // Lot 1 — bascules simples
  toggle_mic: { niveau: 3, reponse: 'mic_state' },
  toggle_nemotron_asr: { niveau: 3, reponse: 'nemotron_asr_state', champs: ['enabled'], timeout: 60000 },
  clear_cache: { niveau: 3, reponse: 'cache_cleared' },
  toggle_fullscreen: { niveau: 3, reponse: null },   // agit sur la fenetre pywebview
  get_settings: { niveau: 1, reponse: 'settings_data' },

  // Lot 2 — reglages, cles API, modeles par agent
  // update_settings ne renvoie pas d'accuse : main2.py ecrit la config et
  // les cles dans .env, sans reponse. On relit get_settings ensuite.
  update_settings: { niveau: 9, reponse: null, champs: ['settings'] },
  get_agent_models: { niveau: 1, reponse: 'agent_models_info' },
  set_agent_models: { niveau: 9, reponse: 'agent_model_updated', champs: ['models'] },

  // Lot 3 — securite systeme. Actions irreversibles : la confirmation est
  // exigee cote interface (liste-actions), la liste blanche ne fait que
  // borner ce qui peut atteindre JARVIS.
  vpn_get_countries: { niveau: 1, reponse: 'vpn_countries' },
  // 45s : vpn.get_status() lance un subprocess.run(powershell) SYNCHRONE
  // sans timeout, directement dans le handler async de JARVIS. Le demarrage
  // de PowerShell coute deja plusieurs secondes. Meme famille de dette que
  // geocoder_ville (voir memoire projet).
  vpn_get_status: { niveau: 1, reponse: 'vpn_status', timeout: 45000 },
  vpn_connect: { niveau: 5, reponse: 'vpn_connect_result', champs: ['country'], timeout: 60000 },
  vpn_disconnect: { niveau: 5, reponse: 'vpn_disconnect_result', timeout: 30000 },

  get_installed_programs: { niveau: 1, reponse: 'installed_programs', timeout: 60000 },
  // Desinstallation : diffuse uninstall_progress puis uninstall_complete.
  // Pas de reponse unique a attendre -> relais SSE (voir EVENEMENTS_RELAYES).
  uninstall_program: { niveau: 9, reponse: null,
    champs: ['name', 'publisher', 'install_location', 'uninstall_string'] },

  get_winget_upgrades: { niveau: 1, reponse: 'winget_upgrades', timeout: 90000 },
  run_winget_upgrade: { niveau: 7, reponse: null, champs: ['ids', 'all'] },

  av_scan_start: { niveau: 5, reponse: null },
  av_scan_cancel: { niveau: 5, reponse: null },
  av_threat_action: { niveau: 9, reponse: 'av_action_result', champs: ['action', 'threat'],
                      timeout: 30000 },

  // Lot 4 — Home Assistant. ha_call_service est volontairement filtre plus
  // finement que les autres : tel quel, il permettrait d'appeler N'IMPORTE
  // QUEL service de l'installation domotique (y compris des scripts, des
  // automatisations, ou des domaines dangereux comme lock/alarm). La liste
  // blanche par type ne suffit donc pas, voir SERVICES_HA_AUTORISES.
  ha_get_states: { niveau: 1, reponse: 'ha_states', timeout: 20000 },

  // Lot 5 — quotidien
  // get_meteo : ajoute cote main2.py pour ce lot (la meteo n'etait que
  // poussee a la voix). 25s : geocodage + open-meteo, deportes en thread.
  get_meteo: { niveau: 1, reponse: 'meteo_data', champs: ['ville'], timeout: 25000 },
  // Panneau scolaire (Pronote via Home Assistant). Lecture pure -> niveau 1,
  // meme famille que get_meteo. La synchro ECRIT dans Google Agenda ->
  // niveau 3, meme niveau que update_shopping_list juste en dessous.
  get_agenda_scolaire: { niveau: 1, reponse: 'agenda_scolaire_data', timeout: 20000 },
  agenda_scolaire_sync: { niveau: 3, reponse: 'agenda_scolaire_resultat', timeout: 30000 },
  // Devoirs/evaluations/notes : lecture pure, meme famille de niveau.
  get_devoirs_notes: { niveau: 1, reponse: 'devoirs_notes_data', timeout: 20000 },
  // Plan de revision genere : lecture pure, memes capteurs que get_devoirs_notes.
  get_plan_revision: { niveau: 1, reponse: 'plan_revision_data', champs: ['minutes_par_soir'], timeout: 20000 },
  get_shopping_list: { niveau: 1, reponse: 'shopping_list' },
  update_shopping_list: { niveau: 3, reponse: 'shopping_list', champs: ['items'] },
  get_obsidian_notes: { niveau: 1, reponse: 'obsidian_notes' },
  read_obsidian_note: { niveau: 1, reponse: 'obsidian_note_content', champs: ['titre'] },
  save_obsidian_note: { niveau: 3, reponse: 'obsidian_notes', champs: ['titre', 'content'] },
  delete_obsidian_note: { niveau: 9, reponse: 'obsidian_notes', champs: ['titre'] },

  // Lot 6 — media. iptv_parse_url peut repondre iptv_playlist OU
  // iptv_direct_stream selon que l'URL est une playlist ou un flux direct :
  // on attend donc la playlist, et le flux direct est relaye en evenement.
  iptv_parse_url: { niveau: 5, champs: ['url'], timeout: 45000,
    reponse: ['iptv_playlist', 'iptv_playlist_error', 'iptv_direct_stream'] },
  iptv_open: { niveau: 5, reponse: null, champs: ['url', 'name'] },
  iptv_set_audio_track: { niveau: 3, reponse: null, champs: ['track'] },
  ha_call_service: { niveau: 5, reponse: 'ha_service_result', timeout: 20000,
                     champs: ['domain', 'service', 'entity_id', 'service_data'] },

  // Auto-diagnostic et propositions d'amelioration.
  // Lire l'etat de JARVIS et ses propositions ne coute rien (niveau 1).
  // ENVOYER une proposition lance un agent de code qui MODIFIE des fichiers
  // du disque : niveau 10, le plus haut de l'echelle. Au-dessus du plafond
  // d'autonomie quelle que soit sa valeur raisonnable, donc toujours soumis
  // a un accord explicite. Ne jamais baisser ce niveau.
  // Courrier trie. Lecture pure -> niveau 1. Le brouillon de reponse est en
  // niveau 3 : il fait ecrire un modele mais n'envoie RIEN. Le jour ou un
  // envoi reel existera, ce sera un message distinct en niveau 7 (send_email
  // sur l'echelle adoptee) — ne jamais le glisser dans celui-ci.
  // 120s : IMAP sur trois comptes plus un appel de classement au modele.
  get_courrier: { niveau: 1, reponse: 'courrier', champs: ['limite'], timeout: 120000 },
  lire_mail: { niveau: 1, reponse: 'mail_contenu', champs: ['compte', 'id'], timeout: 45000 },
  proposer_reponse_mail: { niveau: 3, reponse: 'brouillon_mail',
                           champs: ['compte', 'id', 'consigne'], timeout: 90000 },
  // ENVOI REEL. Niveau 7 : la seule action irreversible ET adressee a un
  // tiers de tout le projet. Un message parti ne se rattrape pas et engage
  // l'utilisateur aupres de quelqu'un d'autre. Ne JAMAIS abaisser ce niveau,
  // ne jamais le fusionner avec proposer_reponse_mail qui, lui, ne fait
  // qu'ecrire. mail_envoi.envoyer() exige en plus son propre confirme=True.
  envoyer_mail: { niveau: 7, reponse: 'mail_envoye', timeout: 60000,
                  champs: ['compte', 'destinataire', 'sujet', 'corps',
                           'repondre_a_id', 'confirme'] },
  etat_envoi_mail: { niveau: 1, reponse: 'envoi_mail_etat', timeout: 60000 },

  // ── Lot 8 : JARVIS OS, applications, Shadowbroker ────────────────────
  // JARVIS OS est un conteneur Docker nomme 'jarvis_os', servi sur le port
  // 3000. Les niveaux suivent la meme echelle que le reste :
  //   lire l'etat      -> 5, car check_jarvis_os_status DEMARRE le conteneur
  //                       s'il est arrete. Ce n'est donc pas une lecture.
  //   demarrer/arreter -> 5, controle d'un service
  //   installer        -> 7, installation de logiciel
  //   desinstaller     -> 9, irreversible
  check_jarvis_os_status: { niveau: 5, reponse: 'jarvis_os_status_reply', timeout: 60000 },
  jarvis_os_start: { niveau: 5, reponse: null, timeout: 60000 },
  jarvis_os_stop: { niveau: 5, reponse: 'jarvis_os_stopped', timeout: 60000 },
  jarvis_os_restart: { niveau: 5, reponse: null, timeout: 60000 },
  jarvis_os_install: { niveau: 7, reponse: null, champs: ['path'] },
  jarvis_os_install_app: { niveau: 7, reponse: 'jarvis_os_app_install_progress',
                           champs: ['app', 'name'], timeout: 300000 },
  jarvis_os_uninstall: { niveau: 9, reponse: 'jarvis_os_stopped', timeout: 120000 },
  jarvis_os_pick_folder: { niveau: 3, reponse: 'jarvis_os_folder_picked', timeout: 120000 },
  jarvis_os_open_shared: { niveau: 3, reponse: null },

  // Inventaire des applications installees : lecture pure.
  detect_apps: { niveau: 1, reponse: 'detected_apps', timeout: 90000 },

  // Shadowbroker et navigateur ancre. Ouvrir une fenetre est un controle
  // d'application, pas une lecture.
  open_shadowbroker: { niveau: 5, reponse: 'shadowbroker_opened', timeout: 30000 },
  open_browser: { niveau: 5, reponse: null, champs: ['query'] },
  close_browser: { niveau: 3, reponse: null },
  dock_browser: { niveau: 3, reponse: null },
  undock_browser: { niveau: 3, reponse: null },

  // Mode agent : recensement des IA de la machine. Lecture pure -> niveau 1.
  // 60s : le scan parcourt tous les processus et sonde six ports.
  get_agents: { niveau: 1, reponse: 'agents_list', timeout: 60000 },
  get_auto_diagnostic: { niveau: 1, reponse: 'auto_diagnostic', timeout: 45000 },
  get_propositions: { niveau: 1, reponse: 'propositions', timeout: 45000 },
  envoyer_proposition: { niveau: 10, reponse: 'proposition_resultat',
                         champs: ['cle', 'agent', 'confirme'], timeout: 1800000 },
};

// Services Home Assistant que le HUD a le droit d'appeler.
// Repris exactement de ce que l'ancien frontend savait declencher
// (ha_dashboard.ts) : bascules lumiere/interrupteur/vanne et commandes
// aspirateur. Rien de plus. Les domaines sensibles (lock, alarm_control_panel,
// script, automation, cover...) ne sont PAS ouverts : les ajouter serait une
// decision a prendre explicitement, pas un effet de bord de la migration.
const SERVICES_HA_AUTORISES = {
  light: ['turn_on', 'turn_off', 'toggle'],
  switch: ['turn_on', 'turn_off', 'toggle'],
  input_boolean: ['turn_on', 'turn_off', 'toggle'],
  valve: ['open_valve', 'close_valve'],
  fan: ['turn_on', 'turn_off', 'toggle'],
  vacuum: ['start', 'pause', 'stop', 'return_to_base', 'locate'],
  climate: ['set_temperature'],
};

function serviceHaAutorise(domaine, service) {
  const permis = SERVICES_HA_AUTORISES[domaine];
  return Array.isArray(permis) && permis.includes(service);
}

// Evenements pousses par JARVIS pendant une operation longue : relayes tels
// quels au navigateur en SSE. Sans ca, l'interface n'aurait aucune
// progression pendant un scan ou une desinstallation.
const EVENEMENTS_RELAYES = new Set([
  'av_start', 'av_progress', 'av_threat_detected', 'av_complete', 'av_cancel',
  'uninstall_progress', 'uninstall_complete',
  'winget_upgrade_progress',
  'ha_state_changed',   // diffuse par JARVIS a tous les clients apres une action
  'show_images',        // JARVIS pousse des images apres une recherche vocale
  'iptv_playlist_error', 'iptv_stream_ready', 'iptv_direct_stream',
]);

// Index inverse : types de reponse qu'un jarvis.send peut attendre.
const REPONSES_ATTENDUES = new Set(
  Object.values(MESSAGES_AUTORISES).flatMap((d) =>
    Array.isArray(d.reponse) ? d.reponse : [d.reponse]).filter(Boolean)
);

// Correspondance des etats vers ceux que connait l'orbe du HUD.
// 'searching' n'a pas d'equivalent : mappe sur 'thinking', le plus proche
// visuellement (JARVIS travaille, il ne repond pas encore).
const ETATS = {
  idle: 'idle',
  thinking: 'thinking',
  speaking: 'responding',
  searching: 'thinking',
};

let ws = null;
let pret = false;      // vrai seulement apres auth_ok
let authEnvoyee = false;
let onChatEvent = null;
let urlJarvis = null;
let reconnexion = null;
let compteurRun = 0;
let runCourant = null;

function journal(...a) { console.log('[JARVIS-WS]', ...a); }

// Correlation des requetes modele : le protocole de JARVIS n'a pas d'id de
// requete pour get_available_models/get_agent_models, seulement un type de
// reponse. File d'attente FIFO par type de reponse attendu, avec timeout —
// suffisant tant qu'un seul HUD parle a JARVIS a la fois.
const attenteParType = new Map();  // responseType -> [{resolve, reject, timer}]

function attendreReponse(reponses, timeoutMs = 5000) {
  // `reponses` peut etre un type unique ou plusieurs : certains messages
  // repondent par l'un OU l'autre. iptv_parse_url renvoie iptv_playlist,
  // iptv_playlist_error ou iptv_direct_stream selon l'URL — n'attendre que
  // le cas nominal faisait patienter 45s sur une URL invalide.
  const types = Array.isArray(reponses) ? reponses : [reponses];
  return new Promise((resolve, reject) => {
    const entree = { resolve, reject, timer: null, types };
    entree.timer = setTimeout(() => {
      for (const t of types) {
        const f = attenteParType.get(t);
        if (f) { const i = f.indexOf(entree); if (i >= 0) f.splice(i, 1); }
      }
      reject(new Error('JARVIS n a pas repondu (' + types.join(' | ') + ')'));
    }, timeoutMs);
    for (const t of types) {
      const file = attenteParType.get(t) || [];
      file.push(entree);
      attenteParType.set(t, file);
    }
  });
}

function resoudreReponse(responseType, valeur) {
  const file = attenteParType.get(responseType);
  if (!file || !file.length) return false;
  const entree = file.shift();
  clearTimeout(entree.timer);
  // L'entree peut etre inscrite sur plusieurs types : la retirer partout,
  // sinon une reponse ulterieure resoudrait une promesse deja tenue.
  for (const t of (entree.types || [])) {
    if (t === responseType) continue;
    const f = attenteParType.get(t);
    if (f) { const i = f.indexOf(entree); if (i >= 0) f.splice(i, 1); }
  }
  entree.resolve(valeur);
  return true;
}

/** Etat de l'orbe -> navigateur. Passe par broadcastEvent (SSE). */
function pousserEtat(etatJarvis) {
  const etat = ETATS[etatJarvis] || 'idle';
  broadcastEvent('agent-state:' + etat);
  // NE PAS remettre runCourant a null ici. C'etait le cas, et ca cassait le
  // chat : le micro de JARVIS le fait passer par 'idle' en permanence entre
  // deux phrases captees. Un 'idle' parasite survenant entre l'envoi et la
  // reponse effacait le runId, pousserTexte en forgeait un nouveau, et le
  // navigateur rejetait la reponse — il ne garde que le runId qu'il a reçu
  // a l'envoi. Cote utilisateur : « TIMEOUT » au bout de 60 s alors que
  // JARVIS avait bel et bien repondu.
  // Un run se termine quand sa reponse est livree, pas sur un changement
  // d'etat : c'est pousserTexte qui le clot desormais.
}

/** Texte de JARVIS -> navigateur, dans la forme attendue par broadcastChat. */
function pousserTexte(texte) {
  if (!onChatEvent || !texte) return;
  // Pas de run en cours = texte spontane (declenche a la voix, notification).
  // On lui donne son propre identifiant ; le navigateur l'affiche puisqu'il
  // n'attend rien de precis.
  const run = runCourant || ('jarvis-' + (++compteurRun));
  runCourant = null;                    // le run s'acheve avec sa reponse
  onChatEvent({
    runId: run,
    state: 'final',
    message: { role: 'assistant', content: texte },
  });
}

function connecter() {
  if (reconnexion) { clearTimeout(reconnexion); reconnexion = null; }
  journal('connexion a', urlJarvis);
  try {
    ws = new WebSocket(urlJarvis);
  } catch (e) {
    journal('creation impossible :', e.message);
    return planifierReconnexion();
  }

  ws.on('open', () => {
    const jeton = lireJeton();
    if (!jeton) {
      journal('aucun JARVIS_ACCESS_TOKEN trouve — connexion refusee cote JARVIS');
      return;
    }
    authEnvoyee = true;
    ws.send(JSON.stringify({ token: jeton }));   // jamais journalise
    journal('connecte, authentification envoyee');
  });

  ws.on('message', (brut) => {
    let msg;
    try { msg = JSON.parse(brut.toString()); } catch { return; }
    // JARVIS envoie beaucoup d'actions (meteo, vpn, obsidian...) : on ne
    // traite que celles qui concernent la conversation, le reste est ignore
    // sans bruit plutot que mal interprete.
    if (msg.type === 'auth_ok') {
      pret = true;
      journal('authentifie');
      broadcastEvent('connected');
      return;
    }
    if (msg.type === 'auth_failed') {
      pret = false;
      journal('AUTHENTIFICATION REFUSEE — verifier JARVIS_ACCESS_TOKEN dans le .env de JARVIS');
      return;
    }
    // Reponses aux requetes modele (get_available_models / get_agent_models),
    // correlees par type puisque le protocole n'a pas d'id de requete.
    if (msg.type === 'available_models' || msg.type === 'agent_models_info'
        || msg.type === 'agent_model_updated') {
      if (resoudreReponse(msg.type, msg)) return;
    }
    // Reponses des messages passes par jarvis.send (liste blanche).
    // Si personne n'attend, on ne bloque pas : le message continue son chemin.
    if (REPONSES_ATTENDUES.has(msg.type) && resoudreReponse(msg.type, msg)) return;
    // Evenement de securite REEL (antivirus, protection live) : jamais
    // simule, jamais affiche hors de ce declencheur precis.
    if (msg.type === 'av_live_threat_intercepted') {
      broadcastEvent('av-threat', { threat: msg.threat, quarantineFile: msg.quarantine_file });
      return;
    }
    // Outil declenche par le socle tools/ de JARVIS. Relaye tel quel : le
    // navigateur l'affiche dans la conversation, pour qu'on voie ce que
    // JARVIS a FAIT et pas seulement ce qu'il a repondu. Le message ne
    // contient jamais la reponse de l'outil, seulement son nom et sa duree.
    if (msg.type === 'tool_call') {
      broadcastEvent('tool-call', {
        nom: msg.nom, priorite: msg.priorite, mode: msg.mode,
        ok: msg.ok !== false, ms: msg.ms, detail: msg.detail || '',
      });
      return;
    }
    // Progression des operations longues (scan, desinstallation, winget).
    if (EVENEMENTS_RELAYES.has(msg.type)) {
      broadcastEvent('jarvis-event', { evenement: msg });
      return;
    }
    // Demandes de capture. JARVIS ne capture pas lui-meme : il DEMANDE au
    // frontend, qui utilise getDisplayMedia / getUserMedia et lui renvoie une
    // image base64. Tant que personne ne repond, la vision de JARVIS est
    // aveugle — c'etait le cas depuis que le HUD a remplace l'ancien front.
    //
    // Noter l'incoherence du protocole cote JARVIS, reproduite telle quelle
    // plutot que « corrigee » unilateralement : l'ecran arrive en `action`,
    // la camera en `type`.
    if (msg.type === 'request_camera_capture') {
      broadcastEvent('capture-demandee', { genre: 'camera', id: msg.id });
      return;
    }
    switch (msg.action) {
      case 'request_screen_capture':
        broadcastEvent('capture-demandee', { genre: 'ecran', id: msg.id });
        break;
      case 'set_state':
        pousserEtat(msg.state);
        break;
      case 'jarvis_text':
        pousserTexte(msg.text || msg.texte || '');
        break;
      case 'open_panel':
        // Poussee par main2.py sur « montre/ouvre/affiche le panneau
        // scolaire ». Le navigateur ne parle jamais au WebSocket JARVIS en
        // direct (voir l'entete de ce fichier) : ce cas est le seul chemin
        // par lequel JARVIS peut faire basculer un onglet du HUD sans
        // action de souris/clavier.
        broadcastEvent('open-panel', { panel: msg.panel, sub: msg.sub });
        break;
      default:
        break;
    }
  });

  ws.on('close', () => { pret = false; authEnvoyee = false; journal('deconnecte'); planifierReconnexion(); });
  ws.on('error', (e) => { journal('erreur :', e.message); });
}

function planifierReconnexion() {
  if (reconnexion) return;
  reconnexion = setTimeout(() => { reconnexion = null; connecter(); }, 3000);
}

// ── Interface attendue par index.js et les routes (drop-in) ───────────────

export function initGateway({ url, token, sessionKey, onChat }) {
  // token / sessionKey (parametres) : ignores volontairement. Ce sont ceux
  // d'OpenClaw ; JARVIS a sa propre authentification par jeton (lu depuis
  // son .env, voir lireJeton) et pas de notion de sessions. Les garder dans
  // la signature evite de toucher index.js.
  onChatEvent = onChat;
  urlJarvis = url || process.env.JARVIS_WS_URL || 'ws://127.0.0.1:8765';
  connecter();
}

/**
 * Reponse a une demande de capture, ou etat de la webcam.
 *
 * Volontairement ETROITE : trois types autorises, pas un passe-plat. Ce
 * chemin contourne la liste blanche de jarvis.send parce qu'il repond a une
 * demande que JARVIS a lui-meme initiee ; il ne doit donc pas pouvoir servir
 * a autre chose.
 */
export function repondreCapture(genre, id, donnees, erreur) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  let paquet;
  if (genre === 'ecran') {
    paquet = erreur ? { type: 'screen_frame', id, error: String(erreur) }
                    : { type: 'screen_frame', id, data: donnees };
  } else if (genre === 'camera') {
    paquet = erreur ? { type: 'camera_capture_response', id, success: false,
                        error: String(erreur) }
                    : { type: 'camera_capture_response', id, image: donnees };
  } else if (genre === 'etat_webcam') {
    paquet = { type: 'webcam_state', active: !!donnees };
  } else {
    return false;
  }
  ws.send(JSON.stringify(paquet));
  return true;
}

export function isReady() { return pret; }

export function getSessionKey() { return SESSION_JARVIS; }

export function gwRequest(method, params = {}) {
  return new Promise((resolve, reject) => {
    if (!pret || !ws || ws.readyState !== WebSocket.OPEN) {
      return reject(new Error('JARVIS injoignable sur ' + urlJarvis));
    }
    switch (method) {
      case 'chat.send': {
        const texte = params.text || params.message || '';
        runCourant = 'jarvis-' + (++compteurRun);
        ws.send(JSON.stringify({ type: 'user_input', text: texte }));
        // JARVIS ne renvoie pas d'accuse : la reponse arrivera en push via
        // action:jarvis_text. On resout tout de suite avec le runId pour que
        // le client puisse filtrer le flux.
        return resolve({ runId: runCourant, accepted: true });
      }
      case 'chat.abort':
        ws.send(JSON.stringify({ type: 'stop_audio' }));
        return resolve({ aborted: true });
      case 'chat.history':
        // Pas d'historique expose par le WebSocket de JARVIS. Renvoyer une
        // liste vide est correct pour le HUD (il affiche juste rien) ; le
        // brancher sur jarvis_conversations.json serait une etape a part.
        return resolve({ messages: [] });
      case 'sessions.list':
        return resolve({ sessions: [{ key: SESSION_JARVIS, title: 'JARVIS' }] });

      // Selection de modele : les 3 messages reellement geres par main2.py
      // (get_agent_models / get_available_models / set_primary_model),
      // rien d'invente.
      case 'models.list':
        ws.send(JSON.stringify({ type: 'get_available_models' }));
        return attendreReponse('available_models')
          .then((r) => resolve({ models: r.models || [], preferred: r.prefered || '' }))
          .catch(reject);
      case 'models.agents':
        ws.send(JSON.stringify({ type: 'get_agent_models' }));
        return attendreReponse('agent_models_info')
          .then((r) => resolve({ data: r.data || {} }))
          .catch(reject);
      case 'models.set':
        if (!params.model) return reject(new Error('parametre model requis'));
        // JARVIS ne renvoie pas d'accuse pour set_primary_model (verifie
        // dans main2.py : sauvegarde config, pas de websocket.send derriere).
        // On resout tout de suite ; l'appelant relit models.list pour l'etat
        // a jour, comme le fait deja le selecteur TTS du meme HUD.
        ws.send(JSON.stringify({ type: 'set_primary_model', model: params.model }));
        return resolve({ accepted: true, model: params.model });

      // Passe-plat borne : jarvis.send + le type du message JARVIS.
      // Sert de socle a la migration des panneaux de l'ancien frontend.
      case 'jarvis.send': {
        const decl = MESSAGES_AUTORISES[params.type];
        if (!decl) {
          return reject(new Error('message non autorise : ' + params.type));
        }
        // Niveau d'autorisation. Un message sans niveau declare est traite
        // comme maximal : ajouter une entree a la liste blanche sans y
        // reflechir ne doit pas ouvrir une porte en silence.
        const niveau = Number.isFinite(decl.niveau) ? decl.niveau : 10;
        if (niveau > NIVEAU_AUTONOMIE && params.confirme !== true) {
          const e = new Error(
            'confirmation requise : ' + params.type
            + ' (niveau ' + niveau + ' > autonomie ' + NIVEAU_AUTONOMIE + ')');
          e.confirmationRequise = true;
          e.niveau = niveau;
          e.typeMessage = params.type;
          return reject(e);
        }
        // Filtrage fin des appels domotique, en plus de la liste blanche.
        if (params.type === 'ha_call_service'
            && !serviceHaAutorise(params.domain, params.service)) {
          return reject(new Error(
            'service domotique non autorise : ' + params.domain + '.' + params.service));
        }
        const paquet = { type: params.type };
        for (const champ of decl.champs || []) {
          if (params[champ] !== undefined) paquet[champ] = params[champ];
        }
        ws.send(JSON.stringify(paquet));
        if (!decl.reponse) return resolve({ envoye: true, type: params.type });
        return attendreReponse(decl.reponse, decl.timeout || 5000)
          .then(resolve).catch(reject);
      }

      default:
        return reject(new Error('methode non supportee par l adaptateur : ' + method));
    }
  });
}
