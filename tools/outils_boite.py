# -*- coding: utf-8 -*-
"""Adaptateur : expose jarvis_outils.resoudre_outils dans le registre.

Le module reste ou il est, on n'y touche pas. Ce fichier ne fait que
l'enregistrer dans la chaine, avec la meme priorite qu'avant."""

import jarvis_outils

from . import outil


@outil(nom="outils_boite", priorite=100, mode="sync", description="Boite a outils locale (2e vague)")
def outils_boite(texte):
    return jarvis_outils.resoudre_outils(texte)
