# -*- coding: utf-8 -*-
"""
Socle d'outils JARVIS : décorateur @outil + auto-découverte.

Chaque outil est un fichier unique dans tools/, décoré avec @outil(...).
Aucun câblage manuel dans main2.py : déposer le fichier suffit.

Contrat d'un outil (identique à celui des resoudre_* historiques) :
    fonction(texte: str) -> str | None
    Renvoie une réponse si elle sait traiter le texte, sinon None/"".

MODES
-----
    "sync"     (défaut) fonction normale, rapide, appelée directement
    "async"    coroutine, attendue avec await
    "bloquant" fonction normale mais qui fait de l'I/O lente (réseau) :
               déportée dans un executor pour ne pas geler la boucle.
               main2.py faisait déjà ça pour jarvis_web et email_hub —
               l'oublier gèlerait JARVIS pendant l'appel.

PRIORITÉ
--------
Obligatoire et explicite : la chaîne de résolution est ordonnée (math avant
traduction, etc.), un tri alphabétique changerait le comportement. Barème
aligné sur l'ordre historique de main2.py, espacé de 10 :

     10  commandes locales (reste main2)   70  globe            <- migré
     20  infos système     <- migré        80  extras locaux (reste main2)
     30  math (reste main2 : eval)         90  extras avancées  <- migré
     40  français          <- migré       100  outils           <- migré
     50  conversion        <- migré       110  web              <- migré
     60  traduction        <- migré       120  mail (reste main2)

Les trous correspondent aux résolveurs encore dans main2.py. On appelle donc
le registre par tranches (depuis/jusqua), de part et d'autre, pour conserver
l'ordre exact.

CAPACITÉS RUNTIME
-----------------
main2.py publie déjà les siennes dans `builtins` (parler, get_user_name,
send_globe_command, CONNECTED_CLIENTS...). Les outils réutilisent ce
mécanisme existant plutôt que d'en introduire un second.
"""

import asyncio
import importlib
import pkgutil
import time

# [(priorite, nom, fonction)] — trié après chargement
_REGISTRE = []

MODES = ("sync", "async", "bloquant")


def sans_accents(texte):
    """
    Minuscules sans accents, pour comparer un motif a ce que dit l'utilisateur.

    POURQUOI C'EST ICI ET PAS DANS CHAQUE OUTIL
    infos_systeme comparait « memoire vive utilisee » (tape sans accents, ou
    transcrit sans accents par la reconnaissance vocale) au motif accentue
    « mémoire vive ». Aucune correspondance : la question partait au modele,
    qui mettait 6 secondes a repondre qu'il n'avait pas acces a la memoire —
    alors que l'outil local savait repondre en 2 millisecondes.

    On ne normalise PAS le texte au niveau de resoudre_async : les outils
    existants portent des motifs accentues, qui cesseraient tous de
    correspondre d'un coup. Chaque outil normalise les deux cotes avec
    `contient()`.
    """
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                   if unicodedata.category(c) != "Mn")


def contient(texte, motifs):
    """Vrai si l'un des motifs apparait, accents et casse ignores des DEUX cotes."""
    t = sans_accents(texte)
    return any(sans_accents(m) in t for m in motifs)

# Observateur optionnel : prévenu chaque fois qu'un outil répond ou échoue.
# main2.py y branche la diffusion WebSocket, pour que le HUD affiche ce que
# JARVIS a réellement FAIT et pas seulement ce qu'il a répondu. Posé ici et
# nulle part ailleurs : les deux chemins de résolution passent par ce module,
# un crochet par appelant se serait désynchronisé au premier ajout d'outil.
_observateur = None


def definir_observateur(fonction):
    """
    Enregistre le rappel prévenu à chaque outil déclenché.

    Signature attendue : fonction(nom, priorite, mode, ok, ms, detail).
        ok=True  -> l'outil a répondu ; detail vide
        ok=False -> l'outil a levé ; detail = l'exception
        ms       -> durée d'exécution, en millisecondes

    On ne transmet PAS la réponse de l'outil : elle est déjà affichée dans
    la conversation, et la recopier ferait transiter une seconde fois des
    contenus sensibles (mail_manager renvoie du texte d'e-mail). Le nom de
    l'outil et sa durée suffisent à savoir ce que JARVIS a fait.

    Passer None le débranche. Un observateur qui plante est ignoré : la
    télémétrie ne doit jamais casser la résolution.
    """
    global _observateur
    _observateur = fonction


def _prevenir(nom, priorite, mode, ok, debut, detail=""):
    if _observateur is None:
        return
    try:
        _observateur(nom, priorite, mode, ok,
                     int((time.monotonic() - debut) * 1000), str(detail)[:200])
    except Exception as e:
        print("[TOOLS] observateur a echoue : %r" % (e,))


def outil(nom, priorite=500, description="", mode="sync"):
    """Enregistre la fonction décorée comme outil JARVIS."""
    if mode not in MODES:
        raise ValueError("mode inconnu %r (attendu : %s)" % (mode, ", ".join(MODES)))

    def decorateur(fonction):
        _REGISTRE.append((priorite, nom, fonction))
        fonction._outil_nom = nom
        fonction._outil_priorite = priorite
        fonction._outil_description = description
        fonction._outil_mode = mode
        return fonction
    return decorateur


def charger_outils():
    """
    Importe tous les modules tools/*.py et renvoie (noms_charges, echecs).

    Un module qui plante à l'import est ignoré et signalé, jamais fatal :
    un outil cassé ne doit pas empêcher JARVIS de démarrer (même logique
    que les drapeaux _XXX_OK historiques).
    """
    echecs = []
    for _, nom_module, _ in pkgutil.iter_modules(__path__):
        if nom_module.startswith("_"):
            continue
        try:
            importlib.import_module("%s.%s" % (__name__, nom_module))
        except Exception as e:
            echecs.append((nom_module, repr(e)))
    _REGISTRE.sort(key=lambda x: (x[0], x[1]))
    return [nom for _, nom, _ in _REGISTRE], echecs


def _tranche(depuis, jusqua):
    """Outils dont la priorité tombe dans [depuis, jusqua], bornes incluses."""
    for priorite, nom, fonction in _REGISTRE:
        if depuis is not None and priorite < depuis:
            continue
        if jusqua is not None and priorite > jusqua:
            break
        yield priorite, nom, fonction


async def resoudre_async(texte, depuis=None, jusqua=None):
    """
    Chaîne complète, par priorité croissante. Premier non-vide gagne.
    Gère les trois modes. Un outil qui lève est sauté, jamais fatal.
    """
    for _priorite, nom, fonction in _tranche(depuis, jusqua):
        _debut = time.monotonic()
        try:
            mode = getattr(fonction, "_outil_mode", "sync")
            if mode == "async":
                reponse = await fonction(texte)
            elif mode == "bloquant":
                boucle = asyncio.get_event_loop()
                reponse = await boucle.run_in_executor(None, fonction, texte)
            else:
                reponse = fonction(texte)
        except Exception as e:
            print("[TOOLS] outil '%s' a echoue : %r" % (nom, e))
            _prevenir(nom, _priorite, mode, False, _debut, e)
            continue
        if reponse:
            _prevenir(nom, _priorite, mode, True, _debut)
            return reponse
    return None


def resoudre(texte, depuis=None, jusqua=None):
    """
    Variante synchrone, pour les contextes sans boucle d'événements.
    Refuse explicitement une tranche contenant un outil async ou bloquant
    plutôt que de le sauter en silence.
    """
    for _priorite, nom, fonction in _tranche(depuis, jusqua):
        mode = getattr(fonction, "_outil_mode", "sync")
        if mode != "sync":
            raise RuntimeError(
                "outil '%s' est en mode '%s' : utiliser resoudre_async()" % (nom, mode))
        _debut = time.monotonic()
        try:
            reponse = fonction(texte)
        except Exception as e:
            print("[TOOLS] outil '%s' a echoue : %r" % (nom, e))
            _prevenir(nom, _priorite, mode, False, _debut, e)
            continue
        if reponse:
            _prevenir(nom, _priorite, mode, True, _debut)
            return reponse
    return None


def lister_outils():
    """Inventaire des outils chargés — utile pour le debug et le HUD."""
    return [
        {"nom": n, "priorite": p, "mode": getattr(f, "_outil_mode", "sync"),
         "description": getattr(f, "_outil_description", "")}
        for p, n, f in _REGISTRE
    ]
