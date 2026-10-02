# -*- coding: utf-8 -*-
"""Adaptateur : expose jarvis_web.resoudre_web dans le registre.

Le module reste ou il est, on n'y touche pas. Ce fichier ne fait que
l'enregistrer dans la chaine, avec la meme priorite qu'avant.
mode=bloquant : main2.py deportait deja cet appel dans un executor
(run_in_executor) parce qu'il fait du reseau. Le laisser en sync
gelerait la boucle d'evenements pendant la requete.
"""

import jarvis_web

from . import outil


@outil(nom="web_change", priorite=110, mode="bloquant", description="Taux de change reels (appels reseau)")
def web_change(texte):
    return jarvis_web.resoudre_web(texte)
