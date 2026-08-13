let stream: MediaStream | null = null;

export async function enableScreenCapture(): Promise<boolean> {
  if (stream) return true;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 1 },
      audio: false,
    });
    stream.getVideoTracks()[0].addEventListener("ended", () => {
      stream = null;
      console.warn("[VISION] Partage d'écran arrêté par l'utilisateur");
    });
    console.log("[VISION] Capture d'écran activée");
    return true;
  } catch (e) {
    console.error("[VISION] Refusé:", e);
    return false;
  }
}

export async function captureFrame(): Promise<string | null> {
  if (!stream) {
    console.warn("[VISION] Pas de stream — clique sur 'Activer la vision'");
    return null;
  }

  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;

    video.onloadedmetadata = async () => {
      try {
        await video.play();

        const maxW = 1280;
        const ratio = video.videoWidth > maxW ? maxW / video.videoWidth : 1;
        const w = Math.round(video.videoWidth * ratio);
        const h = Math.round(video.videoHeight * ratio);

        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, w, h);
          resolve(canvas.toDataURL("image/jpeg", 0.8).split(",")[1]);
        } else {
          resolve(null);
        }
      } catch (e) {
        console.error("Erreur lecture video:", e);
        resolve(null);
      } finally {
        video.pause();
        video.srcObject = null;
      }
    };

    // Timeout de sécurité si la vidéo ne se charge pas
    setTimeout(() => {
      resolve(null);
    }, 5000);
  });
}

export function injectVisionButton() {
  let btn = document.getElementById("vision-button") as HTMLButtonElement | null;
  const isStatic = !!btn;
  if (!btn) {
    btn = document.createElement("button");
    btn.id = "vision-button";
    btn.textContent = "👁️ ACTIVER LA VISION";
    document.body.appendChild(btn);
  }
  
  btn.onclick = async () => {
    const ok = await enableScreenCapture();
    if (isStatic) {
      btn.innerHTML = ok ? '<span class="btn-icon">👁️</span> VISION ACTIVE' : '<span class="btn-icon">❌</span> VISION REFUSÉE';
    } else {
      btn.textContent = ok ? "👁️ VISION ACTIVE" : "❌ VISION REFUSÉE";
    }
    if (ok) {
      btn.classList.add("active");
      btn.classList.remove("error");
    } else {
      btn.classList.add("error");
      btn.classList.remove("active");
    }
  };
}
