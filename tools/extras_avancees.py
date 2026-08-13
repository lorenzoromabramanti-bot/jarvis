# -*- coding: utf-8 -*-
"""Adaptateur : expose jarvis_extras.resoudre_extras_avancees dans le registre.

Le module reste ou il est, on n'y touche pas. Ce fichier ne fait que
l'enregistrer dans la chaine, avec la meme priorite qu'avant."""

import jarvis_extras

from . import outil


@outil(nom="extras_avancees", priorite=90, mode="sync", description="Commandes avancees (calculs, conversions, texte, dates)")
def extras_avancees(texte):
    return jarvis_extras.resoudre_extras_avancees(texte)
