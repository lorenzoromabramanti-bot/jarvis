// ── Vision : capture d'ecran et webcam a la demande de JARVIS ────────────
//
// JARVIS ne capture pas lui-meme. Il envoie une demande et attend une image
// base64 sous 15 secondes. La capture se fait ICI, seul endroit ou
// getDisplayMedia et getUserMedia existent.
//
// Depuis que le HUD a remplace l'ancien frontend, plus personne ne repondait
// a ces demandes : « regarde mon ecran » restait sans effet, et JARVIS
// tombait en timeout sans dire pourquoi. Ce fichier rebranche la vision.
//
// CONSENTEMENT
// Une capture d'ecran ouvre un selecteur systeme : c'est Windows qui demande,
// et l'utilisateur choisit ce qu'il partage. On ne peut pas — et on ne veut
// pas — contourner ca. Si l'utilisateur refuse, on renvoie l'erreur a JARVIS
// plutot que de le laisser attendre : un refus explicite vaut mieux qu'un
// silence de quinze secondes.
//
// Le flux d'ecran est ARRETE immediatement apres la capture. Laisser un
// partage d'ecran actif en arriere-plan serait inacceptable.

import { showNotification } from './notifications.js';

const QUALITE = 0.75;          // JPEG : au-dela, l'image gonfle sans gagner
const LARGEUR_MAX = 1600;      // suffisant pour qu'un modele lise un ecran

let webcamActive = false;

async function envoyer(genre, id, data, erreur) {
  try {
    await fetch('/api/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre, id, data, erreur }),
    });
  } catch (e) {
    console.error('[CAPTURE] renvoi impossible :', e);
  }
}

/** Une frame de flux -> JPEG base64, redimensionnee. */
function versImage(video) {
  const ratio = Math.min(1, LARGEUR_MAX / (video.videoWidth || LARGEUR_MAX));
  const c = document.createElement('canvas');
  c.width = Math.round((video.videoWidth || LARGEUR_MAX) * ratio);
  c.height = Math.round((video.videoHeight || 900) * ratio);
  c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
  // JARVIS attend la chaine base64 NUE, sans le prefixe data:.
  return c.toDataURL('image/jpeg', QUALITE).split(',')[1];
}

/** Attend qu'une frame soit reellement disponible, pas seulement le flux. */
function premiereFrame(flux) {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.srcObject = flux;
    video.muted = true;
    video.playsInline = true;
    const echec = setTimeout(() => reject(new Error('aucune image en 8s')), 8000);
    video.onloadedmetadata = async () => {
      try {
        await video.play();
        // Une frame de decalage : la premiere est souvent noire.
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        clearTimeout(echec);
        resolve(versImage(video));
      } catch (e) { clearTimeout(echec); reject(e); }
    };
    video.onerror = () => { clearTimeout(echec); reject(new Error('lecture du flux impossible')); };
  });
}

async function capturerEcran(id) {
  let flux = null;
  try {
    flux = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 1 }, audio: false });
    const image = await premiereFrame(flux);
    await envoyer('ecran', id, image);
    showNotification('ECRAN TRANSMIS A JARVIS');
  } catch (e) {
    // NotAllowedError = l'utilisateur a ferme le selecteur. Ce n'est pas une
    // panne, mais JARVIS doit le savoir tout de suite.
    const motif = e.name === 'NotAllowedError'
      ? 'partage refuse par l\'utilisateur' : (e.message || String(e));
    await envoyer('ecran', id, null, motif);
    showNotification('CAPTURE ECRAN : ' + motif.toUpperCase());
  } finally {
    // Toujours, meme en cas d'erreur : jamais de partage d'ecran orphelin.
    if (flux) flux.getTracks().forEach((t) => t.stop());
  }
}

async function capturerCamera(id) {
  let flux = null;
  try {
    flux = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 } }, audio: false });
    webcamActive = true;
    await envoyer('etat_webcam', null, true);
    const image = await premiereFrame(flux);
    await envoyer('camera', id, image);
    showNotification('IMAGE CAMERA TRANSMISE');
  } catch (e) {
    const motif = e.name === 'NotAllowedError'
      ? 'acces camera refuse' : (e.message || String(e));
    await envoyer('camera', id, null, motif);
    showNotification('CAPTURE CAMERA : ' + motif.toUpperCase());
  } finally {
    if (flux) flux.getTracks().forEach((t) => t.stop());
    if (webcamActive) {
      webcamActive = false;
      await envoyer('etat_webcam', null, false);
    }
  }
}

export function initCapture() {
  window.addEventListener('capture-demandee', (e) => {
    const { genre, id } = e.detail || {};
    if (genre === 'ecran') capturerEcran(id);
    else if (genre === 'camera') capturerCamera(id);
  });
}
