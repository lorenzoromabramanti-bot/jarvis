// ── Media : images et IPTV (lot 6) ───────────────────────────────────────
//
// images  JARVIS POUSSE {type:'show_images', query, images[]} apres une
//         recherche vocale. Il n'existe aucun message pour LES DEMANDER :
//         ce panneau est donc un recepteur, pas un declencheur. Il garde
//         les dernieres series recues au lieu de les perdre au changement
//         d'onglet, ce que l'ancien frontend ne faisait pas.
//
// iptv    iptv_parse_url {url} -> iptv_playlist {channels[{name,url,logo,group}]}
//                              ou iptv_direct_stream si l'URL est un flux
//         iptv_open {url,name} -> iptv_stream_ready
//         La lecture se fait dans une balise <video> native. Les flux HLS
//         (.m3u8) ne sont lisibles nativement que par Safari : ailleurs il
//         faudrait hls.js, une dependance que je n'ajoute pas sans accord.
//         Le panneau le DIT au lieu d'afficher un lecteur muet.

import { showNotification } from './notifications.js';
import { appelerJarvis } from './appel-jarvis.js';

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Delegue a appel-jarvis.js : copie unique, et c'est la qu'est gere le
// refus 428 (niveau d'autorisation depasse -> demande d'accord -> rejeu).
const appeler = appelerJarvis;

// ── Images ───────────────────────────────────────────────────────────────

function initImages(zone) {
  zone.innerHTML = `
    <div class="rg-note">Images poussees par JARVIS apres une recherche
      vocale ("montre-moi des images de ..."). Ce panneau les recoit ; il
      n'existe pas de message pour les demander depuis l'interface.</div>
    <div class="sec-etat" id="im-etat">EN ATTENTE</div>
    <div id="im-series"></div>`;

  const etat = zone.querySelector('#im-etat');
  const series = zone.querySelector('#im-series');
  const recues = [];

  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    if (ev.type !== 'show_images') return;
    recues.unshift({ query: ev.query || '', images: ev.images || [], t: new Date() });
    if (recues.length > 5) recues.pop();
    dessiner();
    showNotification(`IMAGES : ${ev.query || ''}`);
  });

  function dessiner() {
    etat.textContent = `${recues.length} RECHERCHE(S) RECUE(S)`;
    series.innerHTML = recues.map((s) => `
      <div class="im-serie">
        <div class="im-titre">${ech(s.query)} <span class="im-heure">${
          s.t.toLocaleTimeString()}</span></div>
        <div class="im-grille">${s.images.map((u) =>
          `<a href="${ech(u)}" target="_blank" rel="noopener noreferrer">
             <img src="${ech(u)}" alt="${ech(s.query)}" loading="lazy" />
           </a>`).join('')}</div>
      </div>`).join('');
  }
}

// ── IPTV ─────────────────────────────────────────────────────────────────

function initIptv(zone) {
  zone.innerHTML = `
    <div class="sec-barre">
      <input class="rg-input" id="tv-url" type="text"
             placeholder="URL DE PLAYLIST M3U OU FLUX DIRECT" />
      <button class="btn sec-btn" id="tv-charger">CHARGER</button>
    </div>
    <div class="sec-etat" id="tv-etat">—</div>
    <div class="tv-corps">
      <div id="tv-chaines" class="tv-chaines"></div>
      <div class="tv-lecteur">
        <video id="tv-video" controls playsinline></video>
        <div class="sec-etat" id="tv-lecture">AUCUNE LECTURE</div>
      </div>
    </div>`;

  const etat = zone.querySelector('#tv-etat');
  const lecture = zone.querySelector('#tv-lecture');
  const video = zone.querySelector('#tv-video');
  let chaines = [];

  function hlsLisibleNativement() {
    return video.canPlayType('application/vnd.apple.mpegurl') !== '';
  }

  function dessiner() {
    const l = zone.querySelector('#tv-chaines');
    l.innerHTML = chaines.length
      ? chaines.slice(0, 300).map((c, i) => `
          <div class="tv-chaine" data-i="${i}">
            <span class="tv-nom">${ech(c.name || 'sans nom')}</span>
            ${c.group ? `<span class="tv-groupe">${ech(c.group)}</span>` : ''}
          </div>`).join('')
      : '<div class="rg-note">AUCUNE CHAINE</div>';
    l.querySelectorAll('.tv-chaine').forEach((el) => {
      el.addEventListener('click', () => lire(chaines[Number(el.dataset.i)]));
    });
  }

  function lire(c) {
    if (!c || !c.url) return;
    lecture.className = 'sec-etat';
    if (/\.m3u8(\?|$)/i.test(c.url) && !hlsLisibleNativement()) {
      // Honnetete : ne pas afficher un lecteur qui ne jouera rien.
      lecture.textContent = `${c.name} — flux HLS non lisible par ce navigateur `
        + '(hls.js requis, dependance non ajoutee)';
      lecture.className = 'sec-etat erreur';
      return;
    }
    video.src = c.url;
    lecture.textContent = `LECTURE : ${c.name || c.url}`;
    video.play().catch((e) => {
      lecture.textContent = `${c.name} — lecture impossible : ${e.message}`;
      lecture.className = 'sec-etat erreur';
    });
    // On informe JARVIS de ce qui est ouvert, comme le faisait l'ancien front.
    appeler('iptv_open', { url: c.url, name: c.name || '' }).catch(() => {});
  }

  zone.querySelector('#tv-charger').addEventListener('click', async () => {
    const url = zone.querySelector('#tv-url').value.trim();
    if (!url) return;
    etat.textContent = 'ANALYSE DE LA PLAYLIST...';
    etat.className = 'sec-etat';
    try {
      const r = await appeler('iptv_parse_url', { url });
      chaines = r.channels || [];
      etat.textContent = `${chaines.length} CHAINE(S)`
        + (chaines.length > 300 ? ' (300 premieres affichees)' : '');
      dessiner();
    } catch (e) {
      etat.textContent = `ECHEC : ${e.message}`;
      etat.className = 'sec-etat erreur';
    }
  });

  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    if (ev.type === 'iptv_playlist_error') {
      etat.textContent = `ERREUR PLAYLIST : ${ev.error || ''}`;
      etat.className = 'sec-etat erreur';
    } else if (ev.type === 'iptv_direct_stream' && ev.url) {
      // L'URL n'etait pas une playlist mais un flux : on le lit directement.
      lire({ url: ev.url, name: ev.name || 'FLUX DIRECT' });
    }
  });
}

// ── Assemblage ───────────────────────────────────────────────────────────

const VUES = [['images', 'IMAGES', initImages], ['iptv', 'IPTV', initIptv]];

export function initMedia() {
  const conteneur = document.getElementById('rtab-media');
  if (!conteneur) return;

  conteneur.innerHTML = `
    <div class="rg-onglets">
      ${VUES.map(([id, lib], i) =>
        `<button class="rg-onglet${i === 0 ? ' active' : ''}" data-m="${id}">${ech(lib)}</button>`
      ).join('')}
    </div>
    <div class="sec-corps" id="m-corps"></div>`;

  const corps = conteneur.querySelector('#m-corps');
  const montees = new Set();

  function afficher(id) {
    if (!montees.has(id)) {
      const zone = document.createElement('div');
      zone.dataset.m = id;
      corps.appendChild(zone);
      montees.add(id);
      VUES.find((v) => v[0] === id)[2](zone);
    }
    for (const enfant of corps.children) enfant.hidden = enfant.dataset.m !== id;
  }

  conteneur.querySelectorAll('.rg-onglet').forEach((b) => {
    b.addEventListener('click', () => {
      conteneur.querySelectorAll('.rg-onglet').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      afficher(b.dataset.m);
    });
  });

  // Les deux vues sont montees d'emblee : le panneau images doit recevoir
  // ce que JARVIS pousse meme si l'utilisateur ne l'a jamais ouvert.
  afficher('iptv');
  afficher('images');
}
