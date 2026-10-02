# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Piloter le PC et le navigateur sans passer par le modele
=====================================================================
Onglets, pages, videos, sites, recherches, fenetres, verrouillage, applis
ouvertes, gros consommateurs, carte graphique, presse-papiers.

POURQUOI CE FICHIER EXISTE
Banc d'essai du 24/09/2026 : 70 demandes PC / navigateur envoyees au vrai
traiter_reponse_ia, actions interceptees. 33 partaient au modele, qui ne
peut RIEN faire sur le PC ; « ouvre youtube » repondait « pas dans ma
liste » ; « mets youtube en plein ecran » lancait une video au hasard ;
« ferme cette fenetre », « onglet suivant », « recharge la page »,
« verrouille le pc » n'aboutissaient nulle part. Un tiers des vraies
demandes de l'utilisateur a JARVIS concernent son PC.

ORDRE
Priorite 5 : AVANT resoudre_commandes_locales (10), qui finit par un filet
« ouvre X inconnu -> je ne connais pas X » et par une recherche YouTube sur
tout ce qui contient « youtube » + « mets ». D'ou des motifs STRICTS ici :
chaque action exige son mot de contexte (onglet, page, video, fenetre,
pc...). Ce qui ne correspond a rien renvoie None en quelques microsecondes.

LECTURE SEPAREE DE L'EXECUTION
interpreter(texte) est pur (aucun effet) : _test_pc_controle.py y fait
passer des centaines de phrases sans toucher au PC. executer() agit.
"""

import os
import re
import shutil
import subprocess
import time
import urllib.parse
import webbrowser

from . import outil, sans_accents
from config import nom_utilisateur

NAVIGATEURS = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe")

SITES = {
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "google": "https://www.google.com", "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.fr", "twitch": "https://www.twitch.tv",
    "instagram": "https://www.instagram.com", "insta": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com", "twitter": "https://x.com", "x": "https://x.com",
    "facebook": "https://www.facebook.com", "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com", "github": "https://github.com",
    "google maps": "https://maps.google.com", "maps": "https://maps.google.com",
    "google drive": "https://drive.google.com", "drive": "https://drive.google.com",
    "wikipedia": "https://fr.wikipedia.org", "wikipedie": "https://fr.wikipedia.org",
    "deepl": "https://www.deepl.com/translator", "google traduction": "https://translate.google.com",
    "leboncoin": "https://www.leboncoin.fr", "disney plus": "https://www.disneyplus.com",
    "disney+": "https://www.disneyplus.com", "prime video": "https://www.primevideo.com",
    "linkedin": "https://www.linkedin.com", "pinterest": "https://www.pinterest.com",
    "messenger": "https://www.messenger.com", "home assistant": os.getenv("HA_URL", "").strip() or "http://homeassistant.local:8123",
    "whatsapp web": "https://web.whatsapp.com", "google agenda": "https://calendar.google.com",
    "google docs": "https://docs.google.com", "canva": "https://www.canva.com",
    "roblox": "https://www.roblox.com", "vinted": "https://www.vinted.fr",
}
# Carte OSINT locale (God's Eye View + ShadowBroker), lancee par JARVIS au demarrage.
# « œ » n'a pas de decomposition Unicode : sans_accents() le laisse tel quel.
_GODSEYE = os.getenv("GODSEYE_URL", "http://localhost:4173/")
SITES.update({nom: _GODSEYE for nom in (
    "god's eye", "gods eye", "god eye", "god's eye view", "gods eye view",
    "oeil de dieu", "œil de dieu", "shadowbroker", "shadow broker",
    "carte osint", "osint")})
MOTEURS = {
    "google": "https://www.google.com/search?q=%s",
    "amazon": "https://www.amazon.fr/s?k=%s",
    "wikipedia": "https://fr.wikipedia.org/w/index.php?search=%s",
    "wikipedie": "https://fr.wikipedia.org/w/index.php?search=%s",
    "images": "https://www.google.com/search?tbm=isch&q=%s",
    "google images": "https://www.google.com/search?tbm=isch&q=%s",
    "maps": "https://www.google.com/maps/search/%s",
    "google maps": "https://www.google.com/maps/search/%s",
}

_POLI = re.compile(r"\b(jarvis|stp|s'il te plait|s'il vous plait|svp|merci|please)\b")
_ART = r"(?:le |la |les |l'|un |une |mon |ma |mes |ce |cet |cette )?"
_OUVRE = r"(?:ouvre|ouvrir|va sur|vas sur|aller sur|lance|affiche|mets|met|montre)(?:[- ]moi)?"
_DOMAINE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|fr|net|org|io|dev|tv|gg|app|ai|co|be|ch|eu|me))\b")


def normaliser(texte):
    t = sans_accents(texte).replace("’", "'").replace("-", " ")
    t = _POLI.sub(" ", t)
    t = re.sub(r"[?!,;:«»\"]|\.(?!\w)", " ", t)  # garde le point de « leboncoin.fr »
    return " ".join(t.split())


def interpreter(texte):
    """(action, argument) ou None. Pur : ne touche a rien."""
    t = normaliser(texte)
    if not t or len(t) > 120:
        return None

    # ── Onglets ───────────────────────────────────────────────────────────
    if "onglet" in t:
        m = re.search(r"(?:nouvel|nouveau|un) onglet(?: (?:sur|avec|pour) (.+))?$", t)
        if m and re.search(r"\b(ouvre|ouvrir|nouvel|nouveau|cree|lance)\b", t):
            return ("onglet_nouveau", _url_de(m.group(1)) if m.group(1) else None)
        if re.search(r"\b(rouvre|reouvre|restaure)\b", t):
            return ("onglet_rouvrir", None)
        if re.search(r"\b(ferme|fermer|supprime|vire)\b", t):
            return ("onglet_fermer", None)
        if re.search(r"\b(precedent|d'avant|de gauche|retour)\b", t):
            return ("onglet_precedent", None)
        if re.search(r"\b(suivant|prochain|d'apres|de droite|change|passe)\b", t):
            return ("onglet_suivant", None)

    # ── Page web (exige « page » sauf verbes sans ambiguite) ─────────────
    if re.search(r"\b(recharge|actualise|rafraichis|refresh)\b", t) and not re.search(r"\b(meteo|mail|agenda|capteur|batterie|telephone|portable|manette|voiture|casque|montre)\b", t):
        return ("page_recharger", None)
    if "page" in t:
        if re.search(r"page (precedente|d'avant)|(reviens|retourne|retour|recule)\b.*\b(arriere|page)", t):
            return ("page_retour", None)
        if re.search(r"page suivante|(avance|va)\b.*\bpage suivante", t):
            return ("page_avant", None)
        if re.search(r"\b(tout en bas|en bas de la page|fin de la page)\b", t):
            return ("defiler", "fin")
        if re.search(r"\b(tout en haut|en haut de la page|debut de la page)\b", t):
            return ("defiler", "debut")
    if re.search(r"\b(defile|defiler|scroll|scrolle|descends|descend|remonte|monte)\b", t) and \
            re.search(r"\b(page|bas|haut|site|article)\b", t) and not re.search(r"\b(son|volume|volet|store|chauffage|lumiere)\b", t):
        return ("defiler", "haut" if re.search(r"\b(haut|remonte|monte)\b", t) else "bas")

    # ── Video / plein ecran / zoom ────────────────────────────────────────
    if "plein ecran" in t and not re.search(r"\b(camera|webcam|cam|fenetre)\b", t):
        return ("plein_ecran", "quitter" if re.search(r"\b(quitte|sors|enleve|arrete)\b", t) else None)
    if re.search(r"\b(video|youtube)\b", t) and re.search(r"\b(pause|reprends|relance|play|lecture|remets)\b", t):
        return ("video_pause", None)
    if re.search(r"\b(zoome|zoom avant|agrandis la page|grossis)\b", t):
        return ("zoom", "+")
    if re.search(r"\b(dezoome|zoom arriere|retrecis la page)\b", t):
        return ("zoom", "-")

    # ── Recherche sur un moteur ───────────────────────────────────────────
    m = re.match(r"(?:cherche|recherche|trouve|tape)(?: moi)? (.+?) (?:sur|dans) (google images|google maps|google|amazon|wikipedia|wikipedie|maps|images)$", t) \
        or re.match(r"(?:cherche|recherche|trouve)(?: moi)? (?:sur|dans) (google images|google maps|google|amazon|wikipedia|wikipedie|maps) (.+)$", t)
    if m:
        a, b = m.groups()
        requete, moteur = (a, b) if b in MOTEURS else (b, a)
        return ("recherche", (moteur, requete))
    m = re.match(r"(?:google|googlise|recherche google) (.+)$", t)
    if m:
        return ("recherche", ("google", m.group(1)))

    # ── Sites connus / domaines ───────────────────────────────────────────
    m = re.match(r"%s %s(?:site (?:de |d')?)?(.+)$" % (_OUVRE, _ART), t)
    if m:
        cible = m.group(1).strip()
        cible = re.sub(r"^(?:site (?:de |d')?|page (?:de |d')?)", "", cible).strip()
        if cible in SITES:
            return ("site", (SITES[cible], cible))
        d = _DOMAINE.fullmatch(cible)
        if d:
            return ("site", ("https://" + d.group(1), d.group(1)))

    # ── Fenetres ──────────────────────────────────────────────────────────
    if re.search(r"\b(montre|affiche|va sur|retourne sur) le bureau\b|\b(reduis|minimise|cache) (tout|toutes les fenetres)\b", t):
        return ("bureau", None)
    if "fenetre" in t and not re.search(r"\b(salon|cuisine|chambre|salle|garage|veranda|verranda|sejour|toit|velux|maison|dehors)\b", t):
        if re.search(r"\b(change|passe a la|fenetre suivante|autre fenetre|bascule)\b", t):
            return ("fenetre_suivante", None)
        if re.search(r"\b(ferme|fermer|quitte)\b", t) and re.search(r"\b(cette|la|ma) fenetre\b|fenetre (active|actuelle|ouverte)", t):
            return ("fenetre_fermer", None)
        if re.search(r"\b(agrandis|maximise|plein ecran|en grand)\b", t):
            return ("fenetre_agrandir", None)
        if re.search(r"\b(reduis|minimise|cache)\b", t):
            return ("fenetre_reduire", None)

    # ── Verrouillage / annulation d'extinction ────────────────────────────
    if re.search(r"\bverrouille\b", t) and re.search(r"\b(pc|ordi|ordinateur|session|ecran|windows)\b", t):
        return ("verrouiller", None)
    if re.search(r"\b(annule|annuler|stoppe|arrete) (l'|la |le )?(extinction|arret|redemarrage|veille)\b|\bn'eteins pas\b", t):
        return ("annuler_extinction", None)

    # ── Etat du PC ────────────────────────────────────────────────────────
    if re.search(r"\b(applis?|applications?|logiciels?|programmes?)\b.*\bouvert|\bqu'est ce qui (est|tourne) ouvert\b|\bqu'est ce qui est ouvert\b", t):
        return ("apps_ouvertes", None)
    if not re.search(r"\b(electricite|energie|watts?|kwh|eau|gaz|chauffage|maison|essence|batterie)\b", t) and re.search(r"\b(consomme|bouffe|utilise|prend|mange)\b.*\b(le plus|toute|trop)\b|\bpourquoi (mon pc|l'ordi|le pc|mon ordi)\b.*\b(rame|lag|lent|ralenti)\b|\b(rame|lag|lent)\b.*\b(mon pc|l'ordi|le pc)\b", t):
        return ("gros_consommateurs", None)
    if re.search(r"\b(carte graphique|gpu|nvidia|rtx)\b", t) and \
            re.search(r"\b(chauffe|temperature|temp|degres|chaud|utilisation|charge|combien|occupe|memoire|etat|va|quelle|quoi|modele)\b", t):
        return ("gpu", None)

    # ── Clavier : taper un texte, appuyer sur une touche ──────────────────
    # « tape » seul (pas « ecris » : « ecris une fonction python » est une
    # demande de code). « tape X sur google » est deja pris plus haut.
    m = re.match(r"(?:appuie|appuies|tape|presse) (?:sur )?(?:la touche )?(entree|echap|echappe|espace|tab|tabulation|retour arriere|supprime|suppr)$", t)
    if m:
        return ("touche", m.group(1))
    if t in ("valide", "valide ca", "envoie", "entree"):
        return ("touche", "entree")
    if re.match(r"(?:tape|ecris au clavier|ecris dans la fenetre|saisis) ", t):
        # Le texte a taper est pris dans la phrase d'ORIGINE (accents, majuscules).
        m = re.search(r"\b(?:tape|[ée]cris au clavier|[ée]cris dans la fen[êe]tre|saisis)\s+(.+?)\s*$", texte, re.I)
        if m:
            a_taper = re.sub(r"[\s,]+(?:stp|s'il te pla[iî]t|svp)\s*[.!]?$", "", m.group(1), flags=re.I).strip()
            if a_taper:
                return ("taper", a_taper)

    # ── Vocal Discord (le bot vient dans le salon ou se trouve l'utilisateur)
    if re.search(r"\b(quitte|deconnecte toi|sors)\b.*\b(vocal|appel|call)\b", t):
        return ("discord_quitter", None)
    if re.search(r"\b(rejoin[st]?|viens|connecte toi)\b.*\b(vocal|appel|call)|\brejoin[st]? moi (?:sur|en) discord\b|\bviens (?:en|sur) discord\b", t):
        return ("discord_rejoindre", None)

    # ── Presse-papiers (lecture seule ; traduire/corriger = presse_papiers.py)
    if re.search(r"presse ?papiers?|j'ai copie", t) and not re.search(r"\b(traduis|corrige|resume|reformule|ameliore|copie ca|colle)\b", t):
        if re.search(r"\b(lis|lire|c'est quoi|qu'est ce qu|qu'y a|contenu|montre|dis moi|quoi|y a quoi)\b", t) or "j'ai copie" in t:
            return ("presse_papier_lire", None)

    return None


def _url_de(cible):
    cible = (cible or "").strip()
    if cible in SITES:
        return SITES[cible]
    d = _DOMAINE.fullmatch(cible)
    if d:
        return "https://" + d.group(1)
    return MOTEURS["google"] % urllib.parse.quote_plus(cible) if cible else None


# Intentions qui, demandees depuis Discord ou le telephone, attendent un
# « oui » (main2.traiter_reponse_ia) : a distance, personne ne voit la
# fenetre qui recoit la frappe, et le presse-papiers peut contenir un mot de
# passe. Valeur : ce que JARVIS annonce avant de demander.
A_CONFIRMER_A_DISTANCE = {
    "taper": "taper ce texte dans la fenêtre active du PC",
    "touche": "appuyer sur cette touche dans la fenêtre active du PC",
    "presse_papier_lire": "vous envoyer le contenu du presse-papiers du PC",
}


# ═════════════════════════════════════════════════════════════════════════
# Execution
# ═════════════════════════════════════════════════════════════════════════

def _pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = False
    return pyautogui


def _est_masquee(h):
    """Fenetres UWP suspendues : « visibles » pour Windows mais invisibles a l'ecran."""
    try:
        import ctypes
        val = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(val), ctypes.sizeof(val))
        return val.value != 0
    except Exception:
        return False


_TITRES_IGNORES = ("program manager", "microsoft text input application", "windows input experience",
                   "experience d'entree windows", "barre des taches")
# Superpositions et morceaux du shell : visibles pour Windows, jamais ce que l'utilisateur regarde.
_EXE_IGNORES = ("textinputhost.exe", "nvidia overlay.exe", "nvidia share.exe", "shellexperiencehost.exe",
                "searchhost.exe", "startmenuexperiencehost.exe", "lockapp.exe", "gamebar.exe")
_NOMS_VUS = {}  # exe en minuscules -> nom d'origine (« Notepad »)


def fenetres():
    """Fenetres visibles, de la plus recente a la plus ancienne : [(hwnd, titre, exe)]."""
    import psutil
    import win32con
    import win32gui
    import win32process
    moi = os.getpid()
    out = []

    def rappel(h, _):
        if not win32gui.IsWindowVisible(h) or _est_masquee(h):
            return True
        titre = win32gui.GetWindowText(h).strip()
        if not titre or normaliser(titre) in _TITRES_IGNORES:
            return True
        # Fenetres-outils, non activables (overlays) ou minuscules : jamais une cible.
        # Un bandeau « toujours au-dessus » de quelques pixels d'un jeu passait
        # devant la vraie fenetre active dans l'ordre d'EnumWindows.
        ex = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
        if ex & 0x80 or ex & 0x08000000:
            return True
        g, hh, d, b = win32gui.GetWindowRect(h)
        if not win32gui.IsIconic(h) and (d - g < 200 or b - hh < 100):
            return True
        try:
            pid = win32process.GetWindowThreadProcessId(h)[1]
            nom = psutil.Process(pid).name()
            exe = nom.lower()
            _NOMS_VUS[exe] = nom[:-4] if exe.endswith(".exe") else nom
        except Exception:
            pid, exe = 0, ""
        if exe in _EXE_IGNORES:
            return True
        # JARVIS lui-meme (HUD, navigateur securise) n'est jamais une cible
        if pid == moi or "j.a.r.v.i.s" in titre.lower() or "jarvis" in titre.lower():
            return True
        out.append((h, titre, exe))
        return True

    win32gui.EnumWindows(rappel, None)
    return out


def _premier_plan(h):
    import win32api
    import win32con
    import win32gui
    import win32process
    if win32gui.IsIconic(h):
        win32gui.ShowWindow(h, win32con.SW_RESTORE)
    if win32gui.GetForegroundWindow() == h:
        return True
    # Windows refuse SetForegroundWindow a un processus qui n'a pas la main.
    # On emprunte la file d'entree de la fenetre active (AttachThreadInput)
    # plutot que l'astuce « appuyer sur Alt » : dans Opera, Alt ouvre le menu,
    # qui avalait le raccourci suivant (test reel du 24/09 : 1 sur 6).
    moi = win32api.GetCurrentThreadId()
    lui = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
    try:
        if lui and lui != moi:
            win32process.AttachThreadInput(moi, lui, True)
        win32gui.BringWindowToTop(h)
        win32gui.SetForegroundWindow(h)
    except Exception:
        pass
    finally:
        if lui and lui != moi:
            try:
                win32process.AttachThreadInput(moi, lui, False)
            except Exception:
                pass
    time.sleep(0.3)
    return win32gui.GetForegroundWindow() == h


def _navigateur():
    for h, titre, exe in fenetres():
        if exe in NAVIGATEURS:
            return h, titre
    return None, None


_TOUCHES = {
    "onglet_nouveau": ("ctrl", "t"), "onglet_fermer": ("ctrl", "w"), "onglet_suivant": ("ctrl", "pagedown"),
    "onglet_precedent": ("ctrl", "pageup"), "onglet_rouvrir": ("ctrl", "shift", "t"),
    "page_recharger": ("f5",), "page_retour": ("alt", "left"), "page_avant": ("alt", "right"),
}
_DIT = {
    "onglet_nouveau": "Nouvel onglet ouvert", "onglet_fermer": "Onglet fermé",
    "onglet_suivant": "Onglet suivant", "onglet_precedent": "Onglet précédent",
    "onglet_rouvrir": "J'ai rouvert le dernier onglet fermé", "page_recharger": "Page rechargée",
    "page_retour": "Retour à la page précédente", "page_avant": "Page suivante",
}


def _dans_navigateur(action, arg):
    moi = nom_utilisateur()
    if action == "onglet_nouveau" and arg:
        webbrowser.open(arg, new=2)
        return f"J'ouvre un nouvel onglet, {moi}."
    h, titre = _navigateur()
    if not h:
        if action == "onglet_nouveau":
            webbrowser.open("about:blank", new=2)
            return f"J'ouvre le navigateur, {moi}."
        return f"Aucun navigateur n'est ouvert, {moi}."
    if not _premier_plan(h):
        return f"Je n'arrive pas à mettre le navigateur au premier plan, {moi}. Cliquez dessus puis redemandez."
    pg = _pyautogui()
    youtube = "youtube" in titre.lower()
    if action in _TOUCHES:
        pg.hotkey(*_TOUCHES[action])
        return f"{_DIT[action]}, {moi}."
    if action == "defiler":
        pg.press({"bas": "pagedown", "haut": "pageup", "fin": "end", "debut": "home"}[arg])
        return f"C'est fait, {moi}."
    if action == "plein_ecran":
        if youtube:
            pg.press("f")
        else:
            pg.press("esc" if arg == "quitter" else "f11")
        return f"{'Plein écran quitté' if arg == 'quitter' else 'Plein écran'}, {moi}."
    if action == "video_pause":
        pg.press("k" if youtube else "space")
        return f"C'est fait, {moi}."
    if action == "zoom":
        pg.hotkey("ctrl", "+" if arg == "+" else "-")
        return f"Zoom {'avant' if arg == '+' else 'arrière'}, {moi}."
    return None


def _fenetre(action):
    import win32con
    import win32gui
    moi = nom_utilisateur()
    pg = _pyautogui()
    if action == "bureau":
        pg.hotkey("win", "d")
        return f"Voici le bureau, {moi}."
    if action == "fenetre_suivante":
        pg.hotkey("alt", "tab")
        return f"Fenêtre suivante, {moi}."
    # Une fenetre reduite n'est jamais « cette fenetre » : on ne ferme pas le jeu
    # laisse dans la barre des taches.
    liste = [f for f in fenetres() if not win32gui.IsIconic(f[0])]
    if not liste:
        return f"Je ne vois aucune fenêtre ouverte, {moi}."
    # La fenetre active si ce n'est pas JARVIS (absent de la liste), sinon celle
    # juste en dessous dans l'ordre d'affichage.
    active = win32gui.GetForegroundWindow()
    h, titre, _exe = next((f for f in liste if f[0] == active), liste[0])
    court = titre if len(titre) <= 50 else titre[:47] + "..."
    if action == "fenetre_fermer":
        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
        return f"Je ferme « {court} », {moi}."
    if action == "fenetre_agrandir":
        win32gui.ShowWindow(h, win32con.SW_MAXIMIZE)
        return f"« {court} » est agrandie, {moi}."
    if action == "fenetre_reduire":
        win32gui.ShowWindow(h, win32con.SW_MINIMIZE)
        return f"« {court} » est réduite, {moi}."
    return None


_NOMS_APPS = {"chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "code.exe": "VS Code",
              "discord.exe": "Discord", "spotify.exe": "Spotify", "explorer.exe": "Explorateur de fichiers",
              "steam.exe": "Steam", "windowsterminal.exe": "Terminal", "claude.exe": "Claude",
              "notepad.exe": "Bloc-notes", "obs64.exe": "OBS", "whatsapp.exe": "WhatsApp"}


def _nom_app(exe):
    return _NOMS_APPS.get(exe) or _NOMS_VUS.get(exe) or (exe[:-4] if exe.endswith(".exe") else (exe or "?"))


def _apps_ouvertes():
    compte = {}
    for _h, _titre, exe in fenetres():
        nom = _nom_app(exe)
        compte[nom] = compte.get(nom, 0) + 1
    if not compte:
        return f"Aucune application n'est ouverte à l'écran, {nom_utilisateur()}."
    parts = [f"{n} ({c} fenêtres)" if c > 1 else n for n, c in sorted(compte.items(), key=lambda x: -x[1])]
    return f"Ouvert en ce moment : {', '.join(parts)}."


def _gros_consommateurs():
    import psutil
    procs = list(psutil.process_iter(["name", "memory_info"]))
    for p in procs:
        try:
            p.cpu_percent(None)
        except Exception:
            pass
    time.sleep(0.7)
    ram, cpu = {}, {}
    ncpu = psutil.cpu_count() or 1
    for p in procs:
        try:
            nom = _nom_app((p.info["name"] or "").lower())
            if nom.lower() in ("system idle process", "idle", "system"):
                continue
            ram[nom] = ram.get(nom, 0) + (p.info["memory_info"].rss if p.info["memory_info"] else 0)
            cpu[nom] = cpu.get(nom, 0) + p.cpu_percent(None) / ncpu
        except Exception:
            continue
    top_ram = sorted(ram.items(), key=lambda x: -x[1])[:4]
    top_cpu = [x for x in sorted(cpu.items(), key=lambda x: -x[1])[:3] if x[1] >= 1]
    mem = psutil.virtual_memory()
    txt = "Mémoire (%d %% utilisée) : %s." % (mem.percent, ", ".join("%s %.1f Go" % (n, o / 1024 ** 3) for n, o in top_ram))
    if top_cpu:
        txt += " Processeur : %s." % ", ".join("%s %d %%" % (n, c) for n, c in top_cpu)
    else:
        txt += " Le processeur est presque au repos."
    return txt


def _gpu():
    exe = shutil.which("nvidia-smi") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe")
    if not os.path.exists(exe):
        return f"Je n'ai pas d'outil pour lire la carte graphique sur ce PC, {nom_utilisateur()}."
    try:
        sortie = subprocess.run([exe, "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        nom, temp, util, used, total = [x.strip() for x in sortie.splitlines()[0].split(",")]
    except Exception as e:
        return f"Je n'ai pas pu lire la carte graphique, {nom_utilisateur()} ({type(e).__name__})."
    avis = "c'est chaud" if int(temp) >= 80 else "c'est normal" if int(temp) >= 45 else "elle est fraîche"
    return (f"{nom} : {temp} °C ({avis}), utilisée à {util} %, "
            f"{int(used) / 1024:.1f} Go de mémoire vidéo sur {int(total) / 1024:.0f}.")


def _presse_papier():
    try:
        import pyperclip
        contenu = (pyperclip.paste() or "").strip()
    except Exception as e:
        return f"Je n'arrive pas à lire le presse-papiers, {nom_utilisateur()} ({type(e).__name__})."
    if not contenu:
        return f"Le presse-papiers est vide, {nom_utilisateur()}."
    if len(contenu) > 600:
        contenu = contenu[:600] + "…"
    return f"Dans le presse-papiers : {contenu}"


_TOUCHES_NOMMEES = {"entree": "enter", "echap": "esc", "echappe": "esc", "espace": "space", "tab": "tab",
                    "tabulation": "tab", "retour arriere": "backspace", "supprime": "delete", "suppr": "delete"}


def _clavier(action, arg):
    """Ecrit dans la fenetre active (celle sous JARVIS si JARVIS a la main)."""
    import win32gui
    moi = nom_utilisateur()
    liste = [f for f in fenetres() if not win32gui.IsIconic(f[0])]
    if not liste:
        return f"Je ne vois aucune fenêtre où écrire, {moi}."
    active = win32gui.GetForegroundWindow()
    h, titre, _exe = next((f for f in liste if f[0] == active), liste[0])
    if not _premier_plan(h):
        return f"Je n'arrive pas à mettre « {titre[:40]} » au premier plan, {moi}."
    pg = _pyautogui()
    if action == "touche":
        pg.press(_TOUCHES_NOMMEES[arg])
        return f"C'est fait, {moi}."
    # Par le presse-papiers : typewrite() ne sait pas taper les accents.
    import pyperclip
    try:
        avant = pyperclip.paste()
    except Exception:
        avant = None
    pyperclip.copy(arg)
    pg.hotkey("ctrl", "v")
    time.sleep(0.3)
    if avant is not None:
        pyperclip.copy(avant)  # l'utilisateur retrouve ce qu'il avait copie
    return f"J'ai tapé le texte dans « {titre[:40]} », {moi}."


def executer(action, arg):
    moi = nom_utilisateur()
    if action.startswith(("onglet_", "page_")) or action in ("defiler", "plein_ecran", "video_pause", "zoom"):
        return _dans_navigateur(action, arg)
    if action == "site":
        url, nom = arg
        webbrowser.open(url, new=2)
        return f"J'ouvre {nom}, {moi}."
    if action == "recherche":
        moteur, requete = arg
        webbrowser.open(MOTEURS[moteur] % urllib.parse.quote_plus(requete), new=2)
        return f"Je cherche « {requete} » sur {moteur.capitalize()}, {moi}."
    if action in ("bureau", "fenetre_suivante", "fenetre_fermer", "fenetre_agrandir", "fenetre_reduire"):
        return _fenetre(action)
    if action == "verrouiller":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return f"PC verrouillé, {moi}."
    if action == "annuler_extinction":
        r = subprocess.run(["shutdown", "/a"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0:
            return f"Extinction annulée, {moi}."
        return f"Aucun arrêt n'était programmé, {moi}."
    if action == "apps_ouvertes":
        return _apps_ouvertes()
    if action == "gros_consommateurs":
        return _gros_consommateurs()
    if action == "gpu":
        return _gpu()
    if action == "presse_papier_lire":
        return _presse_papier()
    if action in ("taper", "touche"):
        return _clavier(action, arg)
    if action in ("discord_rejoindre", "discord_quitter"):
        import discord_bot
        if action == "discord_rejoindre":
            return discord_bot.rejoindre_vocal_depuis_jarvis()
        return discord_bot.quitter_vocal_depuis_jarvis()
    return None


# « bloquant » : fenetres, psutil (0,7 s d'echantillonnage), nvidia-smi.
# En « sync » ils gèleraient la boucle asyncio de JARVIS.
@outil(nom="pc_controle", priorite=5, mode="bloquant",
       description="Onglets, pages, videos, sites, recherches, fenetres, verrouillage, etat du PC, presse-papiers")
def resoudre_pc(texte):
    intention = interpreter(texte)
    if not intention:
        return None
    return executer(*intention)


# ═════════════════════════════════════════════════════════════════════════
# Lancer une appli par le menu Demarrer (utilise par main2 avant de dire
# « je ne connais pas X »)
# ═════════════════════════════════════════════════════════════════════════

def _raccourcis_menu_demarrer():
    dossiers = [os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
                os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")]
    for d in dossiers:
        for racine, _dirs, fichiers in os.walk(d):
            for f in fichiers:
                if f.lower().endswith((".lnk", ".url")):
                    yield os.path.join(racine, f)


def trouver_dans_menu_demarrer(nom):
    """Chemin du raccourci qui correspond le mieux a `nom`, ou None."""
    cible = normaliser(nom)
    cible = re.sub(r"^(?:l'application |l'appli |le logiciel |le jeu |le |la |les |l'|mon |ma |mes |un |une )", "", cible).strip()
    if len(cible) < 2:
        return None
    meilleur, score_max = None, 0
    for chemin in _raccourcis_menu_demarrer():
        base = normaliser(os.path.splitext(os.path.basename(chemin))[0])
        if re.search(r"\b(desinstall|uninstall|readme|aide|help|documentation|site web|website)\b", base):
            continue
        if base == cible:
            score = 3
        elif re.search(r"\b%s\b" % re.escape(cible), base):
            score = 2
        elif base.startswith(cible) and len(cible) >= 4:
            score = 1
        else:
            continue
        if score > score_max or (score == score_max and meilleur and len(base) < len(normaliser(os.path.basename(meilleur)))):
            meilleur, score_max = chemin, score
    return meilleur


def lancer_depuis_menu_demarrer(nom):
    """(ok, nom_affiche). Lance le raccourci du menu Demarrer correspondant."""
    chemin = trouver_dans_menu_demarrer(nom)
    if not chemin:
        return False, None
    os.startfile(chemin)
    return True, os.path.splitext(os.path.basename(chemin))[0]
