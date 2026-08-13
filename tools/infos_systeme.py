# -*- coding: utf-8 -*-
"""Outil JARVIS : heure, date, age, batterie, CPU, RAM, uptime.

Migre depuis main2.py (passe 2, lot A). Corps repris a l'identique a deux
substitutions pres : les globals USER_NAME / USER_AGE deviennent les
accesseurs get_user_name() / get_user_age() que main2 publie dans builtins.
Necessaire car ces deux valeurs changent au runtime (ws_handler les reassigne
en global) : relire jarvis_config.json donnerait une valeur perimee.
"""

from datetime import datetime

try:
    import psutil
except Exception:
    psutil = None

from . import outil, contient
from config import nom_utilisateur


@outil(nom="infos_systeme", priorite=20,
       description="Heure, date, age, batterie, CPU, RAM, uptime")
def resoudre_infos_systeme_localement(texte):
    """Répond aux questions d'heure, date, batterie, CPU/RAM localement sans IA."""
    t = texte.lower().replace("?", "").strip()
    maintenant = datetime.now()

    JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    MOIS_FR  = ["janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    # --- HEURE ---
    if contient(t, ["quelle heure", "il est quelle heure", "l'heure qu'il est",
                             "quelle est l'heure", "tu as l'heure", "donne-moi l'heure",
                             "il est combien", "c'est quoi l'heure", "heure il est"]):
        h, m = maintenant.hour, maintenant.minute
        return f"Il est {h}h{m:02d}, {nom_utilisateur()}."

    # --- DATE COMPLÈTE ---
    if contient(t, ["quelle date", "on est quel jour", "quel jour on est",
                             "quel jour sommes-nous", "la date d'aujourd'hui", "date du jour",
                             "on est le combien", "quel jour est-on", "c'est quoi la date",
                             "la date aujourd'hui"]):
        jour_semaine = JOURS_FR[maintenant.weekday()]
        mois = MOIS_FR[maintenant.month - 1]
        return f"Nous sommes le {jour_semaine} {maintenant.day} {mois} {maintenant.year}, {nom_utilisateur()}."

    # --- JOUR DE LA SEMAINE SEUL ---
    if contient(t, ["quel jour", "c'est quel jour"]) and "date" not in t:
        return f"Nous sommes {JOURS_FR[maintenant.weekday()]}, {nom_utilisateur()}."

    # --- MOIS ---
    if contient(t, ["quel mois", "on est en quel mois", "c'est quel mois"]):
        return f"Nous sommes en {MOIS_FR[maintenant.month - 1]}, {nom_utilisateur()}."

    # --- ANNÉE ---
    if contient(t, ["quelle année", "on est en quelle année", "c'est quelle année"]):
        return f"Nous sommes en {maintenant.year}, {nom_utilisateur()}."

    # --- ÂGE DE L'UTILISATEUR ---
    if contient(t, ["quel âge as-tu", "quel age as-tu",
                             f"quel âge a {get_user_name().lower()}",
                             f"quel age a {get_user_name().lower()}",
                             "quel est mon âge", "j'ai quel âge", "j ai quel age"]):
        if get_user_age():
            return f"Vous avez {get_user_age()} ans, {get_user_name()}."
        attente_age = True
        return f"Je ne connais pas encore votre âge, {get_user_name()}. Quel est-il ?"

    # --- BATTERIE ---
    if contient(t, ["batterie", "autonomie", "niveau de charge", "charge du pc"]):
        if psutil is None:
            return f"Le module psutil n'est pas disponible, {nom_utilisateur()}."
        try:
            bat = psutil.sensors_battery()
            if bat:
                pct = int(bat.percent)
                etat = "en charge" if bat.power_plugged else "sur batterie"
                return f"La batterie est à {pct}%, {etat}, {nom_utilisateur()}."
            return f"Je ne détecte pas de batterie sur cet appareil, {nom_utilisateur()}."
        except Exception:
            return f"Impossible de lire la batterie, {nom_utilisateur()}."

    # --- CPU ---
    # « quel est mon processeur » demande le MODELE, pas la charge. On laisse
    # passer vers tools/machine.py plutot que de repondre a cote.
    if (contient(t, ["cpu", "processeur", "utilisation du processeur", "charge du processeur"])
            and not contient(t, ["quel processeur", "quel est mon processeur",
                                 "modele de processeur", "quel cpu ai-je"])):
        if psutil is None:
            return f"Le module psutil n'est pas disponible, {nom_utilisateur()}."
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            return f"Le processeur tourne à {cpu}% d'utilisation, {nom_utilisateur()}."
        except Exception:
            return f"Impossible de lire le processeur, {nom_utilisateur()}."

    # --- RAM ---
    if contient(t, ["ram", "mémoire ram", "mémoire vive", "utilisation de la mémoire"]):
        if psutil is None:
            return f"Le module psutil n'est pas disponible, {nom_utilisateur()}."
        try:
            mem = psutil.virtual_memory()
            utilise = round(mem.used / (1024**3), 1)
            total   = round(mem.total / (1024**3), 1)
            return f"La RAM est à {mem.percent}% — {utilise} Go utilisés sur {total} Go, {nom_utilisateur()}."
        except Exception:
            return f"Impossible de lire la RAM, {nom_utilisateur()}."

    # --- UPTIME (depuis combien de temps le PC est allumé) ---
    if contient(t, ["allumé depuis", "uptime", "depuis combien de temps le pc",
                             "depuis quand est allumé"]):
        if psutil is None:
            return f"Le module psutil n'est pas disponible, {nom_utilisateur()}."
        try:
            boot = datetime.fromtimestamp(psutil.boot_time())
            delta = maintenant - boot
            heures  = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f"Le PC est allumé depuis {heures}h{minutes:02d}, {nom_utilisateur()}."
        except Exception:
            return None

    return None
