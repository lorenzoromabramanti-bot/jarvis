# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Presence dans la zone de notification
===================================================
JARVIS continue de tourner quand on ferme le HUD. Une icone pres de l'horloge
permet de le rouvrir, et surtout de le QUITTER.

LA REGLE QUI COMPTE
Fermer le HUD ne doit se transformer en masquage QUE si cette icone tourne
vraiment. Sinon on obtient un programme sans fenetre et sans moyen de
l'arreter autrement que par le gestionnaire de taches. `demarrer()` renvoie
donc (actif, raison), et l'appelant ne change le comportement de fermeture
que si actif vaut True. Un echec ici est sans consequence : le HUD garde son
comportement d'avant.

DEMARRAGE AVEC WINDOWS
Une entree dans HKCU\\...\\Run — cle utilisateur, pas machine : pas
d'elevation, pas de service, et l'utilisateur peut la retirer lui-meme depuis
le Gestionnaire des taches. Volontairement OPTIONNEL et decoche par defaut :
un assistant qui s'installe au demarrage sans le demander est une nuisance.

L'ICONE
jarvis.ico est reference par main2.py mais absent du dossier. On en dessine
une plutot que de tomber sur l'icone generique : un anneau cyan, comme
l'orbe.
"""

import os
import sys
import threading

NOM_REGISTRE = "JARVIS"
CLE_DEMARRAGE = r"Software\Microsoft\Windows\CurrentVersion\Run"

_icone = None
_fil = None


# ── Icone ────────────────────────────────────────────────────────────────

def _image():
    """L'icone du projet si elle existe, sinon un anneau cyan dessine."""
    from PIL import Image, ImageDraw
    ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis.ico")
    if os.path.exists(ico):
        try:
            return Image.open(ico)
        except Exception:
            pass
    taille = 64
    img = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, taille - 5, taille - 5], outline=(53, 231, 224, 255), width=5)
    d.ellipse([20, 20, taille - 21, taille - 21], fill=(53, 231, 224, 255))
    return img


# ── Demarrage avec Windows ───────────────────────────────────────────────

def _commande_demarrage():
    """De quoi relancer JARVIS. pythonw evite la console qui clignote."""
    racine = os.path.dirname(os.path.abspath(__file__))
    pyw = os.path.join(racine, "venv", "Scripts", "pythonw.exe")
    py = pyw if os.path.exists(pyw) else os.path.join(racine, "venv", "Scripts", "python.exe")
    return '"%s" "%s"' % (py, os.path.join(racine, "main2.py"))


def demarrage_automatique():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_DEMARRAGE) as k:
            valeur, _ = winreg.QueryValueEx(k, NOM_REGISTRE)
            return bool(valeur)
    except Exception:
        return False


def definir_demarrage_automatique(actif):
    """Renvoie (ok, message). Ne leve pas : c'est un confort, pas un socle."""
    if sys.platform != "win32":
        return False, "seulement sous Windows"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_DEMARRAGE, 0,
                            winreg.KEY_SET_VALUE) as k:
            if actif:
                winreg.SetValueEx(k, NOM_REGISTRE, 0, winreg.REG_SZ,
                                  _commande_demarrage())
                return True, "JARVIS demarrera avec Windows"
            try:
                winreg.DeleteValue(k, NOM_REGISTRE)
            except FileNotFoundError:
                pass
            return True, "JARVIS ne demarrera plus avec Windows"
    except Exception as e:
        return False, "registre inaccessible : %r" % (e,)


# ── Icone de notification ────────────────────────────────────────────────

def demarrer(ouvrir_hud, ouvrir_barre, quitter):
    """
    Affiche l'icone. Renvoie (actif, raison).

    `quitter` est la SEULE sortie volontaire de JARVIS une fois que la
    fermeture du HUD ne quitte plus. L'appelant ne doit changer ce
    comportement que si cette fonction a renvoye True.
    """
    global _icone, _fil
    if _icone is not None:
        return True, "deja active"
    try:
        import pystray
    except ImportError:
        return False, "pystray absent (pip install pystray)"

    def _basculer_demarrage(icon, item):
        ok, message = definir_demarrage_automatique(not demarrage_automatique())
        print("[FOND] %s" % message)

    menu = pystray.Menu(
        pystray.MenuItem("Ouvrir le HUD", lambda i, it: ouvrir_hud(), default=True),
        pystray.MenuItem("Barre rapide  (Ctrl+Alt+J)", lambda i, it: ouvrir_barre()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Demarrer avec Windows", _basculer_demarrage,
                         checked=lambda item: demarrage_automatique()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter JARVIS", lambda i, it: quitter()),
    )

    try:
        _icone = pystray.Icon("jarvis", _image(), "J.A.R.V.I.S", menu)
    except Exception as e:
        return False, "icone impossible : %r" % (e,)

    # pystray tient sa propre boucle de messages ; elle ne peut pas partager
    # celle de pywebview.
    _fil = threading.Thread(target=_icone.run, daemon=True, name="zone-notification")
    _fil.start()

    # Attendre la confirmation d'affichage : renvoyer True sans que l'icone
    # soit visible ferait perdre le seul moyen de quitter.
    for _ in range(50):
        if getattr(_icone, "visible", False):
            return True, "icone affichee"
        threading.Event().wait(0.1)
    return False, "icone non confirmee apres 5 s"


def arreter():
    global _icone
    if _icone is not None:
        try:
            _icone.stop()
        except Exception:
            pass
        _icone = None


def notifier(titre, message):
    """Bulle d'information. Sans effet si le systeme n'en gere pas."""
    if _icone is None:
        return False
    try:
        if _icone.HAS_NOTIFICATION:
            _icone.notify(message, titre)
            return True
    except Exception:
        pass
    return False


if __name__ == "__main__":
    import time
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    fini = threading.Event()
    ok, raison = demarrer(
        ouvrir_hud=lambda: print("  -> ouvrir le HUD"),
        ouvrir_barre=lambda: print("  -> ouvrir la barre"),
        quitter=lambda: (print("  -> quitter"), fini.set()),
    )
    print("  icone : %s (%s)" % (ok, raison))
    print("  demarrage automatique actif : %s" % demarrage_automatique())
    if ok:
        notifier("JARVIS", "Essai de la zone de notification.")
        fini.wait(20)
    arreter()
