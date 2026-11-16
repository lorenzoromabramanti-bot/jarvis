# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Barre rapide et raccourci global
==============================================
Ctrl+Alt+J depuis n'importe quelle application fait apparaitre une barre au
centre de l'ecran. On tape, on lit la reponse, Echap referme.

POURQUOI UN RACCOURCI ET PAS UNE FENETRE DE PLUS
Le HUD est une fenetre qu'on va chercher. Une barre invoquee au clavier
arrive sous les doigts, la ou on travaille deja. C'est la difference entre
« ouvrir l'assistant » et « demander quelque chose ».

PAS DE NOUVELLE DEPENDANCE
Le paquet `keyboard` installe un hook clavier global — il voit TOUTES les
frappes, y compris les mots de passe, et reclame souvent l'elevation.
RegisterHotKey de l'API Windows fait exactement ce qu'il faut et rien de
plus : le systeme ne previent QUE pour la combinaison enregistree. Il est
dans ctypes, donc rien a installer.

    MOD_NOREPEAT evite que maintenir la touche declenche en rafale.

LA FENETRE EST CREEE CACHEE AU DEMARRAGE
La creer a la premiere pression couterait une seconde de chargement a chaque
fois — precisement ce qu'une barre rapide ne doit pas coder. Elle existe des
le lancement, masquee ; l'afficher est instantane.

CE MODULE NE FAIT RIEN SANS FENETRE
Sur un systeme sans pywebview ou hors Windows, `demarrer()` renvoie une
raison lisible au lieu d'echouer en vol. Le reste de JARVIS continue.
"""

import ctypes
import os
import sys
import threading
import time

# Combinaison : Ctrl + Alt + J. J comme JARVIS, et libre sous Windows —
# Alt+Espace ouvre le menu systeme, Ctrl+Espace est pris par les IME.
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
VK_J = 0x4A
ID_RACCOURCI = 0xB19E

HAUTEUR_COMPACTE = 104         # ligne de saisie (60) + puces (44) : = COMPACTE dans barre.html
HAUTEUR_MAX = 520
LARGEUR = 720

# pywebview impose min_size=(200, 100) par defaut. Sans ce reglage, la barre
# refermee gardait 100 px de haut pour 62 px de contenu : une bande noire
# sous le champ, a chaque ouverture. Le minimum doit etre SOUS la hauteur
# compacte, sinon c'est lui qui decide.
TAILLE_MINIMALE = (300, 50)

# Un panneau VIDE s'est affiche (16/11/2026, capture de l'utilisateur) : la fenetre avait la bonne taille, la page ne
# peignait rien. Cause exacte inconnue (serveur de l'interface demarre apres JARVIS, rendu WebView2 perdu apres un jeu
# plein ecran ou une longue veille…). Ouvrir repasse donc par le chemin du premier affichage, qui peint toujours : la
# page est rechargee, CACHEE, si elle ne repond pas ou si la barre est restee fermee plus de RECHARGE_APRES secondes.
RECHARGE_APRES = 120          # secondes fermee avant de recharger la page a l'ouverture
ATTENTE_PAGE = 3.0            # secondes au plus pour qu'une page rechargee reponde
PAS_ATTENTE = 0.15
JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "barre_rapide.log")
# Plutot qu'un panneau vide : une phrase, dans les couleurs de la barre.
PAGE_ABSENTE = ("<body style='margin:0;height:100vh;display:grid;place-items:center;background:#0B0D12;color:#CFD6E4;"
                "font:15px Segoe UI,system-ui,sans-serif'>L'interface de JARVIS ne répond pas. "
                "Réessaie dans un instant.</body>")

_fenetre = None
_visible = False
_fil = None
_url_page = ""
_rechargements = 0
_fermee_a = 0.0               # time.monotonic() de la derniere fermeture (ou de la creation)


def _noter(texte):
    """Une ligne horodatee dans barre_rapide.log : sous pythonw, print() ne va nulle part."""
    try:
        if os.path.exists(JOURNAL) and os.path.getsize(JOURNAL) > 200000:
            os.replace(JOURNAL, JOURNAL + ".1")
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), texte))
    except Exception:
        pass


class Api:
    """Expose a la page le strict minimum : se cacher, se redimensionner."""

    def cacher(self):
        masquer()
        return True

    def redimensionner(self, hauteur):
        try:
            h = max(HAUTEUR_COMPACTE, min(int(hauteur), HAUTEUR_MAX))
            _fenetre.resize(LARGEUR, h)
        except Exception:
            pass
        return True


def _geometrie():
    """Centree horizontalement, au tiers superieur — la hauteur des yeux.

    En pixels LOGIQUES : pywebview remultiplie x/y par l'echelle de
    l'ecran avant de les passer a WinForms. Le calcul se faisait avant
    sur les pixels PHYSIQUES (screeninfo) — sur cet ecran 4K a 225 %,
    (4096-720)/2 = 1688, remultiplie par 2,25 = 3798, soit une barre
    posee a 3798 px sur un bureau qui n'en fait que 1820 de large :
    entierement hors champ. Mesure confirmee avant/apres correction.
    """
    try:
        import config
        larg, haut = config.ecran_logique()
    except Exception:
        larg, haut = 1920, 1080
    return (larg - LARGEUR) // 2, int(haut * 0.26)


def creer(url_base):
    """Cree la fenetre, masquee. A appeler une seule fois, avant webview.start()."""
    global _fenetre, _url_page, _fermee_a
    if _fenetre is not None:
        return _fenetre
    import webview
    x, y = _geometrie()
    _url_page = "%s/barre.html" % url_base.rstrip("/")
    _fermee_a = time.monotonic()
    _fenetre = webview.create_window(
        title="JARVIS",
        url=_url_page,
        width=LARGEUR, height=HAUTEUR_COMPACTE, x=x, y=y,
        frameless=True, easy_drag=False, on_top=True,
        resizable=False, hidden=True, min_size=TAILLE_MINIMALE,
        # shadow (vrai par defaut) : ombre et coins arrondis dessines par
        # Windows. Fond = theme sombre de l'Orbe de verre.
        shadow=True, background_color="#0B0D12",
        js_api=Api(),
    )
    return _fenetre


def _page_prete(delai=1.0):
    """Vrai si barre.html tourne dans la fenetre ET que son JavaScript repond. Un evaluate_js qui ne rend pas la main
    (rendu mort) compte comme faux : sans ce delai, le raccourci resterait bloque jusqu'a 20 s."""
    resultat = []

    def sonder():
        try:
            resultat.append(_fenetre.evaluate_js("typeof window.reinitialiser") == "function")
        except Exception:
            resultat.append(False)

    fil = threading.Thread(target=sonder, daemon=True, name="sonde-barre")
    fil.start()
    fil.join(delai)
    return bool(resultat and resultat[0])


def _recharger():
    """Recharge barre.html (fenetre cachee). Vrai si la page repond au bout de ATTENTE_PAGE secondes au plus.

    L'adresse change a chaque fois (?r=N) : mesure du 16/11, un load_url() vers l'adresse DEJA affichee ne redevient
    jamais « pret » pour pywebview (evaluate_js attend 6 s sans reponse), alors qu'une adresse differente repond en 0,01 s."""
    global _rechargements
    _rechargements += 1
    try:
        _fenetre.load_url("%s?r=%d" % (_url_page, _rechargements))
    except Exception as e:
        _noter("rechargement impossible : %r" % (e,))
        return False
    fin = time.monotonic() + ATTENTE_PAGE
    while time.monotonic() < fin:
        time.sleep(PAS_ATTENTE)
        if _page_prete(0.5):
            return True
    return False


def afficher():
    global _visible
    if _fenetre is None:
        return
    try:
        # Redimensionner a la taille actuelle ne produit aucun evenement : le +1 px oblige WebView2 a recalculer ses
        # limites, sans quoi la page peut rester sur une surface perimee.
        _fenetre.resize(LARGEUR, HAUTEUR_COMPACTE + 1)
        _fenetre.resize(LARGEUR, HAUTEUR_COMPACTE)
        x, y = _geometrie()
        _fenetre.move(x, y)
        pret = True
        ferme_depuis = time.monotonic() - _fermee_a
        if (not _visible and ferme_depuis > RECHARGE_APRES) or not _page_prete():
            t0 = time.monotonic()
            pret = _recharger()
            _noter("page rechargee (fermee depuis %d s) : %s en %.1f s"
                   % (ferme_depuis, "ok" if pret else "SANS REPONSE", time.monotonic() - t0))
        _fenetre.show()
        if pret:
            # Vider le champ et y remettre le curseur : rouvrir la barre sur la
            # question precedente obligerait a l'effacer avant chaque usage.
            _fenetre.evaluate_js("window.reinitialiser && window.reinitialiser()")
        else:
            _fenetre.load_html(PAGE_ABSENTE)      # une phrase plutot qu'un panneau vide ; la prochaine ouverture reessaie
        _visible = True
    except Exception as e:
        _noter("affichage impossible : %r" % (e,))


def masquer():
    global _visible, _fermee_a
    if _fenetre is None:
        return
    try:
        _fenetre.hide()
        _visible = False
        _fermee_a = time.monotonic()
    except Exception:
        pass


def basculer():
    (masquer if _visible else afficher)()


def _boucle_raccourci():
    """
    Fil dedie : RegisterHotKey lie le raccourci au FIL qui l'enregistre, et
    les messages arrivent dans la file de CE fil. L'enregistrer depuis le fil
    principal bloquerait la boucle de pywebview.
    """
    u32 = ctypes.windll.user32
    if not u32.RegisterHotKey(None, ID_RACCOURCI,
                              MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_J):
        # Deja pris par une autre application : le dire, ne pas faire semblant.
        print("[BARRE] Ctrl+Alt+J refuse par Windows (deja utilise ailleurs).")
        return
    print("[BARRE] Ctrl+Alt+J actif.")

    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_uint),
                    ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long)]

    msg = MSG()
    WM_HOTKEY = 0x0312
    try:
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == ID_RACCOURCI:
                basculer()
    finally:
        u32.UnregisterHotKey(None, ID_RACCOURCI)


def demarrer():
    """Lance l'ecoute du raccourci. Renvoie (actif, raison)."""
    global _fil
    if sys.platform != "win32":
        return False, "raccourci global non implemente hors Windows"
    if _fenetre is None:
        return False, "barre non creee"
    if _fil is not None:
        return True, "deja actif"
    _fil = threading.Thread(target=_boucle_raccourci, daemon=True,
                            name="raccourci-barre")
    _fil.start()
    return True, "Ctrl+Alt+J"


if __name__ == "__main__":
    # Essai isole : la barre seule, sans le reste de JARVIS.
    import webview
    creer("http://localhost:8001")
    ok, raison = None, None

    def _apres_demarrage():
        global ok, raison
        ok, raison = demarrer()
        print("  raccourci : %s (%s)" % (ok, raison))
        afficher()

    webview.start(_apres_demarrage, private_mode=False)
