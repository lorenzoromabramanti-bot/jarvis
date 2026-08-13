# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Assistant de configuration
========================================
Ce qu'on voit au premier lancement : ce que JARVIS peut faire, ce qu'on active,
et ce qu'il lui faut pour que ça marche.

DEUX MODES, UN SEUL CATALOGUE
La différence n'est pas deux listes : c'est le niveau d'exposition. Le mode
simple masque trois capacités et verrouille les garde-fous ; le mode avancé
montre tout. Les deux lisent `catalogue.CAPACITES`, donc une capacité ajoutée
apparaît des deux côtés sans rien recâbler.

CE QUI N'EST JAMAIS ENVOYÉ À LA PAGE
Les valeurs des clés. La page reçoit « GEMINI_API_KEY : renseignée » ou
« absente », jamais le contenu. Une interface qui affiche un secret finit par
le montrer dans une capture d'écran.

ON N'ÉCRASE PAS UNE CONFIGURATION EXISTANTE
Un champ laissé vide garde la valeur déjà en place. Sans ça, relancer
l'assistant pour changer une seule option effacerait tout le reste — et
c'est exactement ce qu'on fait après une mise à jour.

    venv\\Scripts\\python.exe installeur.py
"""

import io
import os
import re
import sys

import config

RACINE = config.RACINE
PAGE = os.path.join(RACINE, "installeur", "page.html")


# ── Lecture / écriture du .env ───────────────────────────────────────────

def _fichier_env(racine=None):
    """Le chemin du .env. Parametrable pour que ce code soit testable ailleurs
    que sur l'installation reelle — RACINE est fige a l'import."""
    import pathlib
    return pathlib.Path(racine or RACINE) / ".env"


def _lire_env(racine=None):
    """{clé: valeur} du .env. Reste en mémoire, ne sort jamais d'ici."""
    chemin = _fichier_env(racine)
    valeurs = {}
    if not chemin.exists():
        return valeurs
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.rstrip("\n")
        if not ligne.strip() or ligne.lstrip().startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def _ecrire_env(nouvelles, racine=None):
    """
    Fusionne dans .env, sans rien perdre.

    Les lignes existantes sont modifiées sur place — commentaires, ordre et
    clés inconnues sont conservés. Un fichier réécrit de zéro perdrait tout
    ce que l'utilisateur y a mis à la main.
    """
    chemin = _fichier_env(racine)
    lignes = (io.open(chemin, encoding="utf-8", errors="replace").read().splitlines()
              if chemin.exists() else [])
    restantes = dict(nouvelles)
    sortie = []
    for ligne in lignes:
        m = re.match(r"^(\s*)([A-Z0-9_]+)(\s*)=(.*)$", ligne)
        if m and m.group(2) in restantes:
            cle = m.group(2)
            sortie.append("%s%s=%s" % (m.group(1), cle, restantes.pop(cle)))
        else:
            sortie.append(ligne)
    if restantes:
        sortie.append("")
        sortie.append("# Ajouté par l'assistant de configuration")
        for cle, valeur in restantes.items():
            sortie.append("%s=%s" % (cle, valeur))

    tmp = str(chemin) + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write("\n".join(sortie) + "\n")
    os.replace(tmp, chemin)
    return len(nouvelles)


def _jeton_aleatoire(n=48):
    import secrets
    return secrets.token_urlsafe(n)[:n]


# ── L'API vue par la page ────────────────────────────────────────────────

class Api:
    """Tout ce que la page peut demander. Rien de plus."""

    def __init__(self):
        self.fenetre = None
        self.termine = False

    # -- lecture --------------------------------------------------------
    def donnees(self, mode="simple"):
        import catalogue
        import garde_fous
        presentes = _lire_env()
        reglages = []
        for variables, present, requis, role, source in config.configuration():
            reglages.append({
                "variables": list(variables),
                # PRÉSENCE, jamais la valeur.
                "renseigne": bool(present),
                "requis": bool(requis),
                "role": role,
                "source": source,
            })
        return {
            "version": config.VERSION,
            "systeme": config.SYSTEME,
            "premier": config.premier_demarrage(),
            "capacites": catalogue.catalogue(mode),
            "reglages": reglages,
            "gardes": garde_fous.etat(mode),
            "degradees": [{"nom": n, "manque": m}
                          for n, m in config.fonctionnalites_indisponibles()],
            "a_deja_un_jeton": bool(presentes.get("JARVIS_ACCESS_TOKEN")),
        }

    # -- écriture -------------------------------------------------------
    def enregistrer(self, mode, capacites, reglages, gardes_a_retirer=None):
        """
        Applique la configuration. Renvoie un compte rendu, jamais une valeur.

        Un réglage vide n'efface RIEN : il signifie « garde ce qui est là ».
        """
        import catalogue
        import garde_fous

        a_ecrire = {}
        for cle, valeur in (reglages or {}).items():
            valeur = (valeur or "").strip()
            if not valeur:
                continue                      # vide = inchangé
            if not re.match(r"^[A-Z0-9_]+$", cle):
                continue                      # nom de variable douteux : ignoré
            a_ecrire[cle] = valeur

        # Le jeton d'accès n'a pas à être inventé par l'utilisateur : c'est
        # une chaîne aléatoire, et lui en demander une donne des « jarvis123 ».
        if not _lire_env().get("JARVIS_ACCESS_TOKEN") and "JARVIS_ACCESS_TOKEN" not in a_ecrire:
            a_ecrire["JARVIS_ACCESS_TOKEN"] = _jeton_aleatoire()
            jeton_genere = True
        else:
            jeton_genere = False

        ecrits = _ecrire_env(a_ecrire) if a_ecrire else 0
        retenues, refusees = catalogue.definir_activees(capacites or [], mode=mode)

        gardes_retires, gardes_refuses = [], []
        for cle in (gardes_a_retirer or []):
            g = garde_fous.GARDES.get(cle)
            if not g:
                continue
            fait, message = garde_fous.desactiver(cle, g["phrase"], mode=mode)
            (gardes_retires if fait else gardes_refuses).append(
                cle if fait else "%s : %s" % (cle, message))

        return {
            "ok": True,
            "reglages_ecrits": ecrits,
            "jeton_genere": jeton_genere,
            "capacites": retenues,
            "capacites_refusees": refusees,
            "gardes_retires": gardes_retires,
            "gardes_refuses": gardes_refuses,
        }

    def verifier_cle(self, nom, valeur):
        """Contrôle de forme, pas de validité. On ne teste pas la clé en ligne."""
        valeur = (valeur or "").strip()
        if not valeur:
            return {"ok": True, "message": ""}
        if len(valeur) < 12:
            return {"ok": False, "message": "Cette clé semble trop courte."}
        if valeur.startswith(("http://", "https://")) and not nom.endswith("_URL"):
            return {"ok": False, "message": "C'est une adresse, pas une clé."}
        if " " in valeur:
            return {"ok": False, "message": "Une clé ne contient pas d'espace."}
        return {"ok": True, "message": ""}

    def ouvrir(self, url):
        """Ouvre une page d'aide dans le navigateur du système."""
        import webbrowser
        webbrowser.open(url, new=2)
        return True

    def terminer(self):
        self.termine = True
        try:
            self.fenetre.destroy()
        except Exception:
            pass
        return True


def lancer():
    """Ouvre l'assistant. Renvoie True s'il est allé au bout."""
    try:
        import webview
    except ImportError:
        print("  pywebview n'est pas installé : assistant graphique indisponible.")
        return False
    if not os.path.exists(PAGE):
        print("  page introuvable : %s" % PAGE)
        return False

    api = Api()
    fenetre = webview.create_window(
        title="Configuration de J.A.R.V.I.S",
        url="file:///" + PAGE.replace("\\", "/"),
        width=980, height=720, min_size=(820, 600),
        background_color="#080b10",
        js_api=api,
    )
    api.fenetre = fenetre
    webview.start(private_mode=False)
    return api.termine


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--donnees" in sys.argv:
        import json
        print(json.dumps(Api().donnees("avance"), ensure_ascii=False, indent=2)[:1800])
    else:
        lancer()
