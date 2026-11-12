# -*- coding: utf-8 -*-
"""Faux appels d'outil écrits par le modèle : jamais dits, jamais affichés, jamais exécutés.

Certains modèles (celui du repli, un modèle local) n'écrivent pas {"action": ...} mais un pseudo-XML :

    <dots_function_call>
    invoke name="voir_ecran">
    <parameter name="instruction">regarde l'écran pour voir quelle musique joue</parameter>
    </invoke>
    </dots_function_call>

(la balise « <invoke » est souvent tronquée, l'ouverture parfois doublée). main2.py ne le comprenait pas : le texte
brut était lu à voix haute et affiché dans le HUD, puis recopié dans la mémoire de conversation, où il donnait
l'exemple au modèle (6 fois entre le 07/11 et le 12/11/2026).

Pourquoi on ne l'exécute pas : tous les cas vus étaient « voir_ecran », que JARVIS utilise pour CLIQUER, alors que
le modèle voulait seulement regarder l'écran. L'exécuter aurait déclenché un clic au hasard.

Où c'est appelé (le texte du modèle passe par ces points) : traiter_reponse_ia (retire le faux appel et, s'il n'y
avait que lui, redemande une vraie réponse), parler (dernier filet avant la voix et le HUD),
parole_anticipee.premiere_phrase (rien ne part à la voix avant lui), la mémoire de conversation
(_retenir_echange, memory_manager).
"""
import re

# Début d'un pseudo-appel : une balise d'enveloppe, ou « invoke name="x" » (avec ou sans le « < » de tête).
_DEBUT = re.compile(
    r"<\s*(?:dots_function_call|function_calls?|tool_calls?|antml:function_calls)\b[^>]*>"
    r"|<?\s*invoke\s+name\s*=\s*[\"'][\w.\-]+[\"']\s*>?",
    re.I,
)
_FIN = re.compile(r"</\s*(?:dots_function_call|function_calls?|tool_calls?|antml:function_calls|invoke)\s*>", re.I)
_NOM = re.compile(r"invoke\s+name\s*=\s*[\"']([\w.\-]+)[\"']", re.I)

# Ajoutée à la question quand le modèle n'a écrit QUE un faux appel : on lui redemande une vraie réponse.
NOTE_REPRISE = (
    "\n\n[Note système : ta réponse précédente était un appel d'outil mal écrit, donc ignoré. "
    "Réponds maintenant en une ou deux phrases. N'utilise « voir_ecran » que pour cliquer quelque part, "
    "jamais pour regarder l'écran.]"
)


def extraire(texte):
    """(texte sans le faux appel, noms des outils appelés). Le texte avant et après le faux appel est gardé.

    shortcut : un seul bloc est retiré, du premier début à la dernière fin ; du texte écrit ENTRE deux faux
    appels serait perdu. Jamais vu ; à reprendre si ça arrive.
    """
    if not isinstance(texte, str):
        return texte, []
    debut = _DEBUT.search(texte)
    if debut is None:
        return texte, []
    fin = max((m.end() for m in _FIN.finditer(texte, debut.start())), default=len(texte))
    noms = _NOM.findall(texte[debut.start():fin])
    morceaux = (texte[:debut.start()].strip(), texte[fin:].strip())
    return " ".join(m for m in morceaux if m), noms


def sans_appels(texte):
    """Le texte sans faux appel d'outil (inchangé s'il n'y en a pas, ou si ce n'est pas du texte)."""
    return extraire(texte)[0]


def est_seul(texte):
    """Vrai si la réponse ne contenait QUE un faux appel (rien à dire une fois retiré)."""
    return isinstance(texte, str) and bool(texte.strip()) and not extraire(texte)[0].strip()


def avant_appel(texte):
    """Le texte jusqu'au début d'un faux appel d'outil (tout le texte s'il n'y en a pas)."""
    if not isinstance(texte, str):
        return texte
    debut = _DEBUT.search(texte)
    return texte if debut is None else texte[:debut.start()]
