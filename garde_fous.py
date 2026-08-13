# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Garde-fous
========================
Ce que JARVIS s'interdit de faire, et ce qu'il faut pour lever une interdiction.

DEUX PROTECTIONS
  domaines_sensibles   Sur une banque, un site d'impôts ou de santé, JARVIS
                       peut REGARDER mais pas AGIR : pas de frappe au clavier,
                       pas de clic, pas de formulaire. Il n'a aucune raison de
                       valider un virement, et une erreur y coûte cher.
  action_irreversible  Supprimer, désinstaller, envoyer : confirmation exigée.

POURQUOI UN SEUL PASSAGE OBLIGÉ
main2.py ouvre des pages à quinze endroits différents. Poser un contrôle à
chacun garantissait qu'on en oublie un — et un garde-fou contourné à un seul
endroit ne protège de rien. `ouvrir_url()` remplace webbrowser.open : une
définition, quinze sites couverts.

DÉSACTIVATION
En mode simple : impossible, quoi qu'on demande. Ce n'est pas un réglage
caché, c'est un refus. Quelqu'un qui veut vraiment passer outre doit éditer
un fichier à la main — ce qui filtre naturellement le public visé.

En mode avancé : possible, mais il faut RETAPER une phrase exacte. Une case à
cocher se coche par réflexe ; recopier « je desactive la protection des
domaines sensibles » demande de lire ce qu'on fait.

    venv\\Scripts\\python.exe garde_fous.py
"""

import io
import json
import os
import re
import sys
import unicodedata
from urllib.parse import urlparse

import config

FICHIER = "garde_fous.json"

# ── Les catégories protégées ─────────────────────────────────────────────
# Des MOTIFS, pas une liste de domaines : une liste fermée oublie la banque
# régionale de quelqu'un d'autre, et vieillit mal. On complète par
# `domaines_supplementaires` dans le fichier de réglages.

MOTIFS = {
    "banque": [
        r"\bbanque", r"\bbank\b", r"\bbanking", r"credit-?agricole", r"\bcic\b",
        r"societegenerale", r"\bbnpparibas", r"\blcl\b", r"labanquepostale",
        r"caisse-?depargne", r"\bboursorama", r"\bfortuneo", r"\bhellobank",
        r"\bmonabanq", r"\brevolut", r"\bn26\b", r"\bqonto", r"\bpaypal",
        r"\bwise\.com", r"\blydia", r"\bcoinbase", r"\bbinance", r"\bkraken",
        r"\bbourse", r"\btrading", r"\bcourtier", r"\bassurance-?vie",
    ],
    "impots": [
        r"impots\.gouv", r"\bimpots\b", r"\burssaf", r"\bameli\b",
        r"service-?public\.fr", r"\bcaf\.fr", r"\bpole-?emploi",
        r"francetravail", r"\bmesdroitssociaux", r"\bdgfip",
    ],
    "sante": [
        r"\bdoctolib", r"\bameli\b", r"\bmondossiermedical", r"\bmaiia\b",
        r"\bqare\b", r"\bmedecin", r"\bhopital", r"\bmutuelle",
        r"\bpharmacie", r"\blaboratoire.*analyse", r"\bdossier-?medical",
    ],
}

# Ce que chaque garde-fou empêche, et ce qui arrive si on le retire. Le
# second texte est montré au moment de désactiver : une protection dont on
# ne dit pas la conséquence est une case à cocher de plus.
GARDES = {
    "domaines_sensibles": dict(
        titre="Lecture seule sur les sites sensibles",
        description="Sur une banque, un site d'impôts ou de santé, JARVIS "
                    "peut afficher la page mais ne peut ni cliquer, ni taper, "
                    "ni valider quoi que ce soit.",
        consequence="JARVIS pourrait remplir et valider des formulaires sur "
                    "votre banque, vos impôts ou votre dossier médical. Une "
                    "erreur d'interprétation y coûte de l'argent ou des "
                    "données de santé.",
        phrase="je desactive la protection des sites sensibles",
    ),
    "action_irreversible": dict(
        titre="Confirmation avant l'irréversible",
        description="Supprimer un fichier, désinstaller un logiciel ou "
                    "envoyer un e-mail demande votre accord, avec le détail "
                    "exact de ce qui va se passer.",
        consequence="JARVIS supprimerait, désinstallerait et enverrait sans "
                    "rien demander. Une phrase mal comprise suffirait.",
        phrase="je desactive la confirmation avant action irreversible",
    ),
}

# Natures d'action refusées sur un domaine sensible. Regarder reste permis.
ACTIONS_ECRITURE = {"vision_ecrire", "vision_chercher_sur_site",
                    "vision_navigateur", "clic", "formulaire", "saisie"}


def _sans_accents(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ── État des garde-fous ──────────────────────────────────────────────────

def _chemin():
    return config.chemin_donnees(FICHIER, creer_dossier=True)


def _lire():
    try:
        with io.open(str(_chemin()), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def actifs():
    """Les garde-fous en vigueur. Tous, sauf ceux explicitement désactivés."""
    desactives = set(_lire().get("desactives", []))
    return {c for c in GARDES if c not in desactives}


def est_actif(cle):
    return cle in actifs()


def domaines_supplementaires():
    """Domaines ajoutés à la main, hors des motifs livrés."""
    return [d.lower() for d in _lire().get("domaines_supplementaires", [])]


def desactiver(cle, phrase_tapee, mode=None):
    """
    Désactive un garde-fou. Renvoie (fait, message).

    Deux verrous, et le premier ne se négocie pas : en mode simple, c'est
    non. Le second exige de RETAPER la phrase exacte — une case se coche par
    réflexe, recopier une phrase demande de la lire.
    """
    if cle not in GARDES:
        return False, "garde-fou inconnu : %s" % cle
    if mode is None:
        try:
            import catalogue
            mode = catalogue.mode_installe()
        except Exception:
            mode = "avance"
    if mode == "simple":
        return False, ("En mode simple, cette protection ne peut pas être "
                       "retirée depuis l'interface.")

    attendu = GARDES[cle]["phrase"]
    if _sans_accents(phrase_tapee).strip() != attendu:
        return False, ("Pour retirer cette protection, recopiez exactement :\n"
                       "    %s" % attendu)

    donnees = _lire()
    desactives = set(donnees.get("desactives", []))
    desactives.add(cle)
    donnees["desactives"] = sorted(desactives)
    _ecrire(donnees)
    return True, "« %s » est désactivé." % GARDES[cle]["titre"]


def reactiver(cle):
    donnees = _lire()
    desactives = set(donnees.get("desactives", []))
    if cle not in desactives:
        return False, "ce garde-fou est déjà actif"
    desactives.discard(cle)
    donnees["desactives"] = sorted(desactives)
    _ecrire(donnees)
    return True, "« %s » est de nouveau actif." % GARDES[cle]["titre"]


def _ecrire(donnees):
    chemin = str(_chemin())
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


# ── Domaines sensibles ───────────────────────────────────────────────────

def categorie(url):
    """La catégorie sensible d'une URL, ou None. Compare sur le DOMAINE."""
    if not url:
        return None
    brut = str(url).strip()
    if "//" not in brut:
        brut = "http://" + brut
    try:
        hote = (urlparse(brut).hostname or "").lower()
    except Exception:
        hote = brut.lower()
    if not hote:
        return None
    # Comparer sur l'hôte et non sur l'URL entière : sinon une recherche
    # « comment fermer un compte en banque » serait prise pour une banque.
    for d in domaines_supplementaires():
        if d and d in hote:
            return "ajoute"
    hote_simple = _sans_accents(hote)
    for nom, motifs in MOTIFS.items():
        for m in motifs:
            if re.search(m, hote_simple):
                return nom
    return None


def _titre_fenetre_active():
    """Le titre de la fenêtre au premier plan, ou ''."""
    if not config.EST_WINDOWS:
        return ""
    try:
        import ctypes
        u = ctypes.windll.user32
        h = u.GetForegroundWindow()
        n = u.GetWindowTextLengthW(h)
        if not h or n <= 0:
            return ""
        tampon = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(h, tampon, n + 1)
        return tampon.value or ""
    except Exception:
        return ""


def fenetre_active_sensible():
    """
    La fenêtre au premier plan montre-t-elle un site sensible ?

    Le signal est le TITRE, pas l'URL, et c'est délibéré : la vision agit sur
    n'importe quelle fenêtre, pas seulement sur le navigateur intégré. Si la
    banque est ouverte dans Chrome, secure_browser n'en sait rien — mais le
    titre dit « Boursorama — Mon compte ».

    Approximatif par nature : un titre peut ne rien contenir d'identifiable.
    C'est pour ça que ce contrôle S'AJOUTE à celui de l'URL au lieu de le
    remplacer.
    """
    titre = _sans_accents(_titre_fenetre_active())
    if not titre:
        return None
    for d in domaines_supplementaires():
        if d and _sans_accents(d).split(".")[0] in titre:
            return "ajoute"
    for nom, motifs in MOTIFS.items():
        for m in motifs:
            # Les motifs visent des domaines ; dans un titre on cherche le mot.
            mot = m.replace(r"\b", "").replace("-?", "-").replace(r"\.", ".")
            if len(mot) >= 5 and re.search(re.escape(mot).replace(r"\-", "-?"), titre):
                return nom
    return None


def verifier_action_web(url, nature="lecture"):
    """
    (autorise, raison). `nature` : "lecture" ou une action d'écriture.

    Regarder reste toujours permis — l'utilisateur a demandé la page. C'est
    AGIR qui est refusé : cliquer, taper, valider.
    """
    if nature not in ACTIONS_ECRITURE:
        return True, ""
    if not est_actif("domaines_sensibles"):
        return True, ""
    # L'URL fournie ET la fenêtre réellement au premier plan. La seconde
    # attrape le cas courant : la banque ouverte dans un autre navigateur,
    # que l'appelant ne sait pas nommer.
    cat = categorie(url) or fenetre_active_sensible()
    if cat is None:
        return True, ""
    libelles = {"banque": "bancaire", "impots": "administratif",
                "sante": "de santé", "ajoute": "que vous avez protégé"}
    return False, ("Je peux afficher cette page, mais pas agir dessus : "
                   "c'est un site %s. Faites-le vous-même."
                   % libelles.get(cat, "sensible"))


def ouvrir_url(url, nouvelle_fenetre=2):
    """
    Remplace webbrowser.open. Journalise, et laisse passer la lecture.

    Passage obligé : main2 ouvrait des pages à quinze endroits. Un contrôle
    posé à chacun garantissait d'en oublier un, et un garde-fou contourné à
    un seul endroit ne protège de rien.
    """
    import webbrowser
    cat = categorie(url)
    if cat:
        print("[GARDE] ouverture d'un site %s : %s" % (cat, url))
    return webbrowser.open(url, new=nouvelle_fenetre)


def etat(mode=None):
    """
    Pour l'installeur et le panneau de réglages.

    `mode` explicite : pendant l'installation, le mode n'est pas encore
    enregistré. Sans ce paramètre, choisir « simple » dans l'assistant
    laissait afficher « Retirer cette protection… » — un bouton qui aurait
    échoué au clic. Le refus réel tenait, mais proposer une action impossible
    est un mensonge d'interface.
    """
    en_vigueur = actifs()
    if mode is None:
        mode = "avance"
        try:
            import catalogue
            mode = catalogue.mode_installe()
        except Exception:
            pass
    return [{
        "cle": cle,
        "titre": g["titre"],
        "description": g["description"],
        "consequence": g["consequence"],
        "actif": cle in en_vigueur,
        "desactivable": mode != "simple",
        "phrase": g["phrase"] if mode != "simple" else "",
    } for cle, g in GARDES.items()]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print()
    print("=" * 78)
    print("GARDE-FOUS")
    print("=" * 78)
    for g in etat():
        print("  [%s] %-40s %s"
              % ("x" if g["actif"] else " ", g["titre"],
                 "désactivable" if g["desactivable"] else "VERROUILLÉ (mode simple)"))
        print("      %s" % g["description"])
    print()
    print("  Essais de classement :")
    for u in ("https://www.credit-agricole.fr/mon-compte",
              "https://impots.gouv.fr", "https://www.doctolib.fr/rdv",
              "https://fr.wikipedia.org/wiki/Banque",
              "https://www.google.com/search?q=comment+ouvrir+un+compte+en+banque"):
        c = categorie(u)
        print("    %-58s %s" % (u[:58], c or "ordinaire"))
    print()
    print("  Sur une banque :")
    for nature in ("lecture", "vision_ecrire"):
        ok, raison = verifier_action_web("https://www.boursorama.com", nature)
        print("    %-16s %s  %s" % (nature, "autorise" if ok else "REFUSE", raison[:52]))
    print("=" * 78)
