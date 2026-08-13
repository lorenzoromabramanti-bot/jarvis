// ════════════════════════════════════════════════════════════════════
//  JARVIS OS APP STORE
// ════════════════════════════════════════════════════════════════════

interface OsApp {
  name: string;
  icon: string;
  desc: string;
  pkg: string;
  cat: string;
  size?: string;
  script?: string; // custom bash script instead of apt install
}

const OS_APPS: OsApp[] = [
  // Bureautique
  { name: "LibreOffice",     icon: "📄", desc: "Suite bureautique complète (Writer, Calc, Impress)", pkg: "libreoffice",            cat: "bureautique", size: "~350 Mo" },
  { name: "Thunderbird",     icon: "📧", desc: "Client mail et agenda Mozilla",                      pkg: "thunderbird",            cat: "bureautique", size: "~80 Mo"  },
  { name: "Calibre",         icon: "📚", desc: "Gestionnaire de bibliothèque eBooks",               pkg: "calibre",                cat: "bureautique", size: "~150 Mo" },
  { name: "Okular",          icon: "📰", desc: "Visionneuse PDF universelle (KDE)",                  pkg: "okular",                 cat: "bureautique", size: "~30 Mo"  },
  { name: "Evince",          icon: "📃", desc: "Lecteur PDF léger (GNOME)",                          pkg: "evince",                 cat: "bureautique", size: "~10 Mo"  },
  { name: "GnuCash",         icon: "💰", desc: "Logiciel de comptabilité personnelle",              pkg: "gnucash",                cat: "bureautique", size: "~80 Mo"  },
  { name: "Xournalpp",       icon: "✏️", desc: "Prise de notes manuscrites & PDF annotator",        pkg: "xournalpp",              cat: "bureautique", size: "~20 Mo"  },
  // Medias
  { name: "VLC",             icon: "🎬", desc: "Lecteur multimédia universel",                      pkg: "vlc",                    cat: "media",       size: "~50 Mo"  },
  { name: "GIMP",            icon: "🎨", desc: "Éditeur d'images avancé",                           pkg: "gimp",                   cat: "media",       size: "~200 Mo" },
  { name: "Inkscape",        icon: "🖊️", desc: "Éditeur graphique vectoriel SVG",                   pkg: "inkscape",               cat: "media",       size: "~100 Mo" },
  { name: "Audacity",        icon: "🎵", desc: "Éditeur audio multipiste",                          pkg: "audacity",               cat: "media",       size: "~30 Mo"  },
  { name: "Kdenlive",        icon: "🎞️", desc: "Éditeur vidéo non-linéaire",                        pkg: "kdenlive",               cat: "media",       size: "~200 Mo" },
  { name: "OBS Studio",      icon: "📹", desc: "Enregistrement et streaming live",                  pkg: "obs-studio",             cat: "media",       size: "~80 Mo"  },
  { name: "Shotcut",         icon: "✂️", desc: "Éditeur vidéo simple et puissant",                  pkg: "shotcut",                cat: "media",       size: "~100 Mo" },
  { name: "Krita",           icon: "🖌️", desc: "Peinture numérique professionnelle",                pkg: "krita",                  cat: "media",       size: "~150 Mo" },
  { name: "Blender",         icon: "🧊", desc: "Modélisation 3D, animation, rendu",                 pkg: "blender",                cat: "media",       size: "~300 Mo" },
  { name: "HandBrake",       icon: "📼", desc: "Convertisseur vidéo open-source",                   pkg: "handbrake",              cat: "media",       size: "~50 Mo"  },
  { name: "Rhythmbox",       icon: "🎶", desc: "Lecteur et organisateur de musique",                pkg: "rhythmbox",              cat: "media",       size: "~20 Mo"  },
  // Internet
  { name: "Firefox",         icon: "🦊", desc: "Navigateur web rapide et sécurisé",                pkg: "firefox",                cat: "internet",    size: "~80 Mo"  },
  { name: "Chromium",        icon: "🌐", desc: "Navigateur open-source Google",                    pkg: "chromium-browser",       cat: "internet",    size: "~100 Mo" },
  { name: "Brave",           icon: "🦁", desc: "Navigateur respectueux de la vie privée (anti-pub)", pkg: "brave-browser",         cat: "internet",    size: "~100 Mo",
    script: "apt-get install -y curl && curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg && echo 'deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg arch=amd64] https://brave-browser-apt-release.s3.brave.com/ stable main' | tee /etc/apt/sources.list.d/brave-browser-release.list && apt-get update && apt-get install -y brave-browser && sed -i 's/^Exec=/Exec=env --no-sandbox /' /usr/share/applications/brave-browser.desktop" },
  { name: "qBittorrent",     icon: "⬇️", desc: "Client BitTorrent avancé",                         pkg: "qbittorrent",            cat: "internet",    size: "~20 Mo"  },
  { name: "Transmission",    icon: "📡", desc: "Client BitTorrent léger",                          pkg: "transmission-gtk",       cat: "internet",    size: "~10 Mo"  },
  { name: "FileZilla",       icon: "📤", desc: "Client FTP/SFTP",                                  pkg: "filezilla",              cat: "internet",    size: "~20 Mo"  },
  { name: "Telegram",        icon: "✈️", desc: "Messagerie Telegram Desktop",                       pkg: "telegram-desktop",       cat: "internet",    size: "~60 Mo"  },
  { name: "Discord",         icon: "🎙️", desc: "Chat, voix et communautés gaming",                 pkg: "discord",                cat: "internet",    size: "~80 Mo"  },
  { name: "Zoom",            icon: "📷", desc: "Visioconférence Zoom",                              pkg: "zoom",                   cat: "internet",    size: "~100 Mo" },
  { name: "Remmina",         icon: "🖥️", desc: "Bureau à distance (RDP, VNC, SSH)",               pkg: "remmina",                cat: "internet",    size: "~20 Mo"  },
  { name: "Wireshark",       icon: "🦈", desc: "Analyseur de paquets réseau",                      pkg: "wireshark",              cat: "internet",    size: "~50 Mo"  },
  // Developpement
  { name: "VS Code",         icon: "💻", desc: "Éditeur de code Microsoft",                        pkg: "code",                   cat: "developpement", size: "~300 Mo" },
  { name: "Git",             icon: "🔀", desc: "Gestionnaire de versions",                         pkg: "git",                    cat: "developpement", size: "~5 Mo"   },
  { name: "Python 3 + pip",  icon: "🐍", desc: "Langage Python + pip",                             pkg: "python3 python3-pip",    cat: "developpement", size: "~30 Mo"  },
  { name: "Node.js + npm",   icon: "🟩", desc: "Runtime JavaScript",                               pkg: "nodejs npm",             cat: "developpement", size: "~50 Mo"  },
  { name: "Docker CLI",      icon: "🐳", desc: "Outil Docker en ligne de commande",                pkg: "docker.io",              cat: "developpement", size: "~80 Mo"  },
  { name: "DBeaver",         icon: "🗄️", desc: "Outil universel de base de données",              pkg: "dbeaver-ce",             cat: "developpement", size: "~200 Mo" },
  { name: "MySQL Workbench", icon: "🐬", desc: "Interface graphique MySQL",                        pkg: "mysql-workbench",        cat: "developpement", size: "~100 Mo" },
  { name: "Geany",           icon: "📝", desc: "Éditeur de texte / IDE léger",                     pkg: "geany",                  cat: "developpement", size: "~10 Mo"  },
  { name: "Meld",            icon: "🔍", desc: "Outil de comparaison de fichiers",                 pkg: "meld",                   cat: "developpement", size: "~10 Mo"  },
  // Outils
  { name: "7-Zip",           icon: "🗜️", desc: "Archiveur fichiers multi-formats",                 pkg: "p7zip-full",             cat: "outils",      size: "~5 Mo"   },
  { name: "Htop",            icon: "📊", desc: "Moniteur de processus interactif",                 pkg: "htop",                   cat: "outils",      size: "~1 Mo"   },
  { name: "Timeshift",       icon: "⏱️", desc: "Sauvegarde et restauration système",               pkg: "timeshift",              cat: "outils",      size: "~10 Mo"  },
  { name: "KeePassXC",       icon: "🔐", desc: "Gestionnaire de mots de passe",                   pkg: "keepassxc",              cat: "outils",      size: "~30 Mo"  },
  { name: "Gparted",         icon: "💾", desc: "Gestionnaire de partitions de disque",             pkg: "gparted",                cat: "outils",      size: "~10 Mo"  },
  { name: "Bleachbit",       icon: "🧹", desc: "Nettoyeur système (comme CCleaner)",               pkg: "bleachbit",              cat: "outils",      size: "~10 Mo"  },
  { name: "Flameshot",       icon: "📸", desc: "Capture d'écran avancée",                          pkg: "flameshot",              cat: "outils",      size: "~5 Mo"   },
  { name: "Stacer",          icon: "⚡", desc: "Optimiseur et moniteur système Linux",              pkg: "stacer",                 cat: "outils",      size: "~50 Mo"  },
  { name: "Gufw",            icon: "🔥", desc: "Interface graphique pare-feu UFW",                 pkg: "gufw",                   cat: "outils",      size: "~5 Mo"   },
  { name: "ClamAV",          icon: "🛡️", desc: "Antivirus open-source + interface graphique",      pkg: "clamav clamtk",          cat: "outils",      size: "~20 Mo"  },
  { name: "Nmap",            icon: "🔭", desc: "Scanner réseau et sécurité",                       pkg: "nmap",                   cat: "outils",      size: "~5 Mo"   },
  { name: "VirtualBox",      icon: "📦", desc: "Virtualisation de systèmes d'exploitation",        pkg: "virtualbox",             cat: "outils",      size: "~200 Mo" },
  { name: "Neofetch",        icon: "🖥️", desc: "Affiche les infos système en beauté",              pkg: "neofetch",               cat: "outils",      size: "~1 Mo"   },
  // Jeux
  { name: "Steam",           icon: "🎮", desc: "Plateforme de jeux Steam",                         pkg: "steam",                  cat: "jeux",        size: "~100 Mo" },
  { name: "Lutris",          icon: "🕹️", desc: "Gestionnaire de jeux (Wine, GOG, Epic...)",        pkg: "lutris",                 cat: "jeux",        size: "~50 Mo"  },
  { name: "Supertux",        icon: "🐧", desc: "Jeu de plateformes (comme Mario Bros)",            pkg: "supertux",               cat: "jeux",        size: "~40 Mo"  },
  { name: "SuperTuxKart",    icon: "🏎️", desc: "Jeu de kart open-source fun",                     pkg: "supertuxkart",           cat: "jeux",        size: "~250 Mo" },
  { name: "0 A.D.",          icon: "⚔️", desc: "Jeu de stratégie temps réel historique",           pkg: "0ad",                    cat: "jeux",        size: "~800 Mo" },
  { name: "OpenArena",       icon: "🔫", desc: "FPS multijoueur open-source",                      pkg: "openarena",              cat: "jeux",        size: "~300 Mo" },
  { name: "Minetest",        icon: "⛏️", desc: "Jeu de type Minecraft open-source",               pkg: "minetest",               cat: "jeux",        size: "~50 Mo"  },
  { name: "Xonotic",         icon: "💥", desc: "FPS arène rapide open-source",                     pkg: "xonotic",                cat: "jeux",        size: "~1 Go"   },
];

// Track install states

export const osAppStates: Record<string, "idle" | "installing" | "installed" | "error"> = {};
export let currentOsFilter = "all";

function renderAppStoreGrid(filter: string, search: string) {
  const grid = document.getElementById("os-appstore-grid") as HTMLDivElement | null;
  if (!grid) return;
  grid.innerHTML = "";
  const lSearch = search.toLowerCase();
  const filtered = OS_APPS.filter(app =>
    (filter === "all" || app.cat === filter) &&
    (search === "" || app.name.toLowerCase().includes(lSearch) || app.pkg.toLowerCase().includes(lSearch) || app.desc.toLowerCase().includes(lSearch))
  );
  if (filtered.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:rgba(0,229,255,0.4);padding:40px;font-family:'Orbitron',monospace;font-size:13px;">Aucune application trouvée.</div>`;
    return;
  }
  filtered.forEach(app => {
    const state = osAppStates[app.pkg] || "idle";
    const card = document.createElement("div");
    card.className = "os-app-card";
    let btnClass = "os-app-install-btn";
    let btnLabel = "⬇️ Installer";
    let btnDisabled = "";
    if (state === "installed") { btnClass += " installed"; btnLabel = "✅ Installé"; }
    else if (state === "installing") { btnClass += " installing"; btnLabel = "⏳ En cours..."; btnDisabled = "disabled"; }
    else if (state === "error") { btnClass += ""; btnLabel = "❌ Réessayer"; }
    card.innerHTML = `
      <div class="os-app-card-top">
        <div class="os-app-card-icon">${app.icon}</div>
        <div>
          <div class="os-app-card-name">${app.name}</div>
        </div>
      </div>
      <div class="os-app-card-desc">${app.desc}</div>
      <div class="os-app-card-footer">
        <span class="os-app-size">${app.size || ""}</span>
        <button class="${btnClass}" data-pkg="${app.pkg}" ${btnDisabled}>${btnLabel}</button>
      </div>
    `;
    const btn = card.querySelector<HTMLButtonElement>(".os-app-install-btn")!;
    btn.addEventListener("click", () => startInstallOsApp(app));
    grid.appendChild(card);
  });
}

function appendOsLog(msg: string) {
  const log = document.getElementById("os-appstore-log") as HTMLDivElement | null;
  if (!log) return;
  log.style.display = "block";
  log.textContent += msg + "\n";
  log.scrollTop = log.scrollHeight;
}

function startInstallOsApp(app: OsApp) {
  if (osAppStates[app.pkg] === "installing") return;
  osAppStates[app.pkg] = "installing";
  renderAppStoreGrid(currentOsFilter, (document.getElementById("os-appstore-search") as HTMLInputElement)?.value || "");
  appendOsLog(`▶ Installation de ${app.name}...`);
  // Send via WebSocket
  const wsRef = (window as unknown as Record<string, WebSocket>)._jarvisWs;
  if (wsRef && wsRef.readyState === WebSocket.OPEN) {
    const payload: Record<string, string> = { type: "jarvis_os_install_app", pkg: app.pkg, name: app.name };
    if (app.script) payload.script = app.script; // custom bash script (e.g. Brave repo setup)
    wsRef.send(JSON.stringify(payload));
  } else {
    appendOsLog("❌ WebSocket non connecté. Relancez JARVIS.");
    osAppStates[app.pkg] = "error";
    renderAppStoreGrid(currentOsFilter, "");
  }
}

export function handleOsAppInstallProgress(data: Record<string, unknown>) {
  const pkg = data.pkg as string;
  const log = data.log as string;
  const done = data.done as boolean;
  const success = data.success as boolean;
  if (log) appendOsLog(log);
  if (done) {
    osAppStates[pkg] = success ? "installed" : "error";
    const search = (document.getElementById("os-appstore-search") as HTMLInputElement)?.value || "";
    renderAppStoreGrid(currentOsFilter, search);
    appendOsLog(success ? `✅ ${pkg} installé !` : `❌ Erreur installation ${pkg}`);
  }
}

export function initOsAppStore() {
  const btn = document.getElementById("os-toolbar-appstore") as HTMLButtonElement | null;
  const panel = document.getElementById("os-appstore-panel") as HTMLDivElement | null;
  const closeBtn = document.getElementById("os-appstore-close-btn") as HTMLButtonElement | null;
  const searchInput = document.getElementById("os-appstore-search") as HTMLInputElement | null;
  const customInstallBtn = document.getElementById("os-appstore-custom-install") as HTMLButtonElement | null;

  if (!btn || !panel) {
    console.error("[AppStore] Elements not found, btn:", btn, "panel:", panel);
    return;
  }

  // Open / Close
  btn.addEventListener("click", () => {
    const isHidden = panel.classList.contains("hidden");
    if (isHidden) {
      panel.classList.remove("hidden");
      panel.classList.add("visible");
      renderAppStoreGrid(currentOsFilter, "");
    } else {
      panel.classList.add("hidden");
      panel.classList.remove("visible");
    }
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      panel.classList.add("hidden");
      panel.classList.remove("visible");
    });
  }

  // Search
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      renderAppStoreGrid(currentOsFilter, searchInput.value);
    });
  }

  // Category tabs
  document.querySelectorAll<HTMLButtonElement>(".os-appstore-cat").forEach(catBtn => {
    catBtn.addEventListener("click", () => {
      document.querySelectorAll(".os-appstore-cat").forEach(b => b.classList.remove("active"));
      catBtn.classList.add("active");
      currentOsFilter = catBtn.dataset.cat || "all";
      renderAppStoreGrid(currentOsFilter, searchInput?.value || "");
    });
  });

  // Custom install
  if (customInstallBtn) {
    customInstallBtn.addEventListener("click", () => {
      const pkg = prompt("📦 Nom du paquet apt à installer :\n(exemple: gimp, vlc, firefox...)");
      if (pkg && pkg.trim()) {
        const customApp: OsApp = { name: pkg.trim(), icon: "📦", desc: "Installation personnalisée", pkg: pkg.trim(), cat: "all" };
        startInstallOsApp(customApp);
      }
    });
  }

  // Drag header
  const header = document.getElementById("os-appstore-header") as HTMLDivElement | null;
  if (header && panel) {
    let dragging = false, ox = 0, oy = 0;
    header.addEventListener("mousedown", (e) => {
      dragging = true;
      const r = panel.getBoundingClientRect();
      ox = e.clientX - r.left; oy = e.clientY - r.top;
    });
    document.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      panel.style.left = (e.clientX - ox) + "px";
      panel.style.top = (e.clientY - oy) + "px";
      panel.style.transform = "none";
    });
    document.addEventListener("mouseup", () => { dragging = false; });
  }

  console.log("[AppStore] Initialized ✅");
}
