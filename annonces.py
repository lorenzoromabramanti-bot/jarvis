# -*- coding: utf-8 -*-
"""Pendant un quiz du Mode Professeur, les annonces de fond attendent la fin du quiz.

Un avion de God's Eye View ou le résumé du courrier tombait au milieu d'une question (test du 07/11).
parler() passe chaque texte ici : une annonce de fond (pas une réponse à l'utilisateur, pas urgente) est
gardée pendant le quiz, puis dite après la première phrase prononcée une fois le quiz fini.
"""
MAX_EN_ATTENTE = 5   # au-delà, les plus anciennes tombent : un avion d'il y a vingt minutes n'apprend plus rien

_attente = []


def filtrer(texte, en_reponse, urgent, quiz_actif):
    """Le texte à dire maintenant (avec les annonces gardées derrière), ou None s'il faut le garder."""
    if quiz_actif and not en_reponse and not urgent:
        _attente.append(texte)
        del _attente[:-MAX_EN_ATTENTE]
        return None
    if _attente and not quiz_actif:
        texte = "\n".join([texte] + _attente)
        _attente.clear()
    return texte


def en_attente():
    return list(_attente)
