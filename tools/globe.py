# -*- coding: utf-8 -*-
"""Outil JARVIS : commandes du globe 3D (affichage, trajets, geocodage).

Migre depuis main2.py (passe 2, lot B). Corps repris a l'identique.
Les 3 capacites runtime utilisees (parler, send_globe_command, geocode_lieu)
sont fournies par main2 via builtins, comme le reste du socle.
"""

import re

from . import outil
from config import nom_utilisateur


@outil(nom="globe", priorite=70, mode="async",
       description="Globe 3D : affichage de lieux, trajets, distances")
async def resoudre_globe_localement(texte: str):
    """Détecte les commandes de navigation globe et déclenche CesiumJS."""
    import re
    t = texte.lower().strip()

    # ── Mots-clés déclencheurs ───────────────────────────────────────────────
    _mots_globe   = ["affiche la terre", "montre la terre", "montre-moi la terre",
                     "globe terrestre", "affiche le globe", "vue de la terre",
                     "vue spatiale", "vue depuis l'espace", "vue de l'espace",
                     "montre la planète", "affiche la planète",
                     "zoom arrière total", "dézoom total"]

    _mots_ville   = ["affiche", "montre-moi", "montre moi", "survole",
                     "navigue vers", "va vers", "zoome sur",
                     "fais un survol de", "localise", "trouve",
                     "où est", "ou est", "situe", "où se trouve", "ou se trouve"]

    _mots_route   = ["trace un itinéraire", "trace l'itinéraire", "itinéraire de",
                     "route de", "chemin de", "comment aller de",
                     "trace une route de", "trajet de", "trajet depuis"]

    _mots_fermer  = ["ferme la carte", "ferme le globe", "cache la carte",
                     "cache le globe", "ferme la navigation", "quitte le globe",
                     "retour à jarvis", "ferme la vue", "masque la carte"]

    _mots_position = ["ma position", "où suis-je", "ou suis-je",
                      "affiche ma position", "montre ma position",
                      "localise-moi", "localise moi", "où je suis"]

    # ── Fermer ───────────────────────────────────────────────────────────────
    if any(m in t for m in _mots_fermer):
        await send_globe_command(globe_action="hide")
        return f"Navigation fermée. Je reviens à l'interface principale, {nom_utilisateur()}."

    # ── Ma position ──────────────────────────────────────────────────────────
    if any(m in t for m in _mots_position):
        # On délègue la géolocalisation au navigateur (navigator.geolocation)
        # bien plus précis que l'IP — le frontend gère tout
        await send_globe_command(globe_action="my_location")
        await parler(f"Localisation en cours, {nom_utilisateur()}. Le globe affiche votre position en temps réel.")
        return "[Globe] Demande de géolocalisation envoyée au navigateur."

    # ── Globe Terre ───────────────────────────────────────────────────────────
    if any(m in t for m in _mots_globe):
        await send_globe_command(globe_action="show_earth")
        await parler(f"Initialisation du globe terrestre. Vue depuis l'espace activée, {nom_utilisateur()}.")
        return "[Globe] Vue Terre activée."

    # ── Itinéraire de X à Y ──────────────────────────────────────────────────
    if any(m in t for m in _mots_route):
        pattern = r"(?:de|depuis)\s+(.+?)\s+(?:a|vers|jusqu.a|et)\s+(.+?)(?:\s*[?!]?\s*$)" 
        match = re.search(pattern, t)
        if match:
            from_name = match.group(1).strip().title()
            to_name   = match.group(2).strip().title()
            await parler(f"Calcul de l'itinéraire de {from_name} vers {to_name}. Géolocalisation en cours...")
            lat1, lon1, _ = await geocode_lieu(from_name)
            lat2, lon2, _ = await geocode_lieu(to_name)
            if lat1 and lat2:
                await send_globe_command(
                    globe_action="route",
                    from_lat=lat1, from_lon=lon1, from_name=from_name,
                    to_lat=lat2,   to_lon=lon2,   to_name=to_name
                )
                await parler(f"Itinéraire tracé de {from_name} à {to_name}, {nom_utilisateur()}. La route est affichée sur le globe.")
                return f"[Globe] Route {from_name} → {to_name} affichée."
            else:
                return f"Je n'ai pas pu localiser les deux villes, {nom_utilisateur()}. Vérifiez les noms et réessayez."
        return None

    # ── Fly to ville ─────────────────────────────────────────────────────────
    for mot in _mots_ville:
        if mot in t:
            # Extraire ce qui suit le mot déclencheur
            idx = t.find(mot)
            reste = t[idx + len(mot):].strip()
            
            # --- DISTINGUER RECHERCHE GLOBE VS RECHERCHE IMAGE / OBJET / RESTAURANT ---
            # Si le mot déclencheur est générique (affiche, montre, trouve)
            if mot in ["affiche", "montre-moi", "montre moi", "trouve"]:
                # 1. Si la phrase contient explicitement des mots-clés liés aux images ou aux restaurants
                if any(k in t for k in ["image", "photo", "dessin", "illustration", "wallpaper", "fond d'écran", "fond decran", "cliché", "pic", "visuel", "restaurant", "restaurants"]):
                    continue
                # 2. Si le reste commence par un article indéfini/partitif (un, une, des, du, de la, de l'), c'est un objet, pas un lieu
                cleaned_reste = reste.lower()
                if any(cleaned_reste.startswith(art) for art in ["un ", "une ", "des ", "du ", "de la ", "de l'"]):
                    continue
                # 3. Si la phrase contient des mots exclus liés à d'autres fonctionnalités de Jarvis (météo, e-mails, actualités, etc.)
                if any(k in t for k in ["météo", "meteo", "temps", "température", "temperature", "actualité", "actualite", "news", "mail", "message", "calendrier", "agenda", "blague", "citation", "note", "courses", "commande"]):
                    continue
            
            # Nettoyer les articles
            for art in ["la ville de ", "la ville ", "le ", "la ", "l'", "les ", "ma ville ", "mon pays "]:
                if reste.startswith(art):
                    reste = reste[len(art):]
            reste = reste.replace("?", "").replace("!", "").strip()
            if len(reste) >= 2:
                nom_lieu = reste.title()
                
                # --- DOUBLE SÉCURITÉ : GÉOCODAGE AVANT D'ACTIVER LE GLOBE ---
                # On géocode en arrière-plan. Si Nominatim ne trouve pas le lieu, on retourne None
                # pour laisser les autres modules (comme la recherche d'images) ou l'IA traiter la demande.
                lat, lon, display = await geocode_lieu(nom_lieu)
                if lat is None:
                    continue  # Ce n'est pas un lieu valide, continuer ou laisser passer
                
                await parler(f"Recherche de {nom_lieu} en cours... Coordonnées en acquisition.")
                # Altitude selon le type de lieu (ville proche = plus bas)
                altitude = 300000
                await send_globe_command(
                    globe_action="fly_to",
                    lat=lat, lon=lon,
                    target=nom_lieu,
                    altitude=altitude
                )
                await parler(f"Coordonnées acquises. Survol de {nom_lieu} en cours, {nom_utilisateur()}.")
                return f"[Globe] Survol de {nom_lieu} ({lat:.4f}°, {lon:.4f}°)"
            break

    return None
