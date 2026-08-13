"""
youtube_api.py — Module YouTube pour JARVIS
==============================================
Toutes les fonctionnalités avancées via l'API YouTube Data v3.
La recherche simple (chercher_youtube) reste dans main2.py et n'est PAS touchée.

Fonctions disponibles :
  - yt_infos_video(video_id_ou_url)   → titre, vues, likes, durée, chaîne
  - yt_chercher_multi(recherche, n=5) → N premiers résultats (titre + url)
  - yt_trending(categorie, pays)      → top 5 vidéos tendance
  - yt_infos_chaine(nom_chaine)       → abonnés, nb vidéos, description
  - yt_resumer_video(url_ou_id)       → sous-titres → résumé IA
  - yt_dernieres_videos(nom_chaine)   → 3 dernières vidéos publiées
"""

import os
import re
import requests
from dotenv import load_dotenv
from config import nom_utilisateur

# ---------------------------------------------------------------------------
# Chargement de la clé API (indépendant du main2.py)
# ---------------------------------------------------------------------------
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Réutilise le validateur global de Jarvis s'il est disponible, sinon fallback local
try:
    import builtins as _b
    _cle_valide = _b._cle_valide  # type: ignore
except AttributeError:
    _PLACEHOLDERS = frozenset({"VOTRE_CLE_ICI", "Votre ID", "votre_id", "VOTRE_TOKEN_ICI", ""})
    def _cle_valide(key):
        return bool(key) and str(key).strip() not in _PLACEHOLDERS

_BASE_URL = "https://www.googleapis.com/youtube/v3"
_TIMEOUT  = 7  # secondes


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------

def _extraire_video_id(url_ou_id: str) -> str:
    """Extrait le video ID depuis une URL YouTube ou retourne l'ID directement."""
    patterns = [
        r"(?:v=|youtu\.be/|/embed/|/v/)([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url_ou_id)
        if m:
            return m.group(1)
    # Si c'est déjà un ID brut (11 chars)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_ou_id.strip()):
        return url_ou_id.strip()
    return ""


def _duree_iso_to_lisible(duree_iso: str) -> str:
    """Convertit PT4M13S en '4 min 13 sec'."""
    m = re.search(r"(\d+)H", duree_iso)
    heures = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)M", duree_iso)
    minutes = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)S", duree_iso)
    secondes = int(m.group(1)) if m else 0
    parties = []
    if heures:
        parties.append(f"{heures}h")
    if minutes:
        parties.append(f"{minutes} min")
    if secondes:
        parties.append(f"{secondes} sec")
    return " ".join(parties) if parties else "durée inconnue"


def _formater_nombre(n: int) -> str:
    """1234567 → '1,2 million', 8500 → '8 500'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} million{'s' if n >= 2_000_000 else ''}"
    if n >= 1_000:
        return f"{n:,}".replace(",", " ")
    return str(n)


def _chercher_chaine_id(nom_chaine: str) -> tuple[str, str]:
    """Retourne (channel_id, titre_officiel) pour un nom de chaîne."""
    if not _cle_valide(YOUTUBE_API_KEY):
        return "", ""
    try:
        r = requests.get(
            f"{_BASE_URL}/search",
            params={
                "part": "snippet",
                "q": nom_chaine,
                "type": "channel",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        data = r.json()
        if not data.get("items"):
            return "", ""
        item = data["items"][0]
        return item["id"]["channelId"], item["snippet"]["title"]
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# 1. Infos détaillées sur une vidéo
# ---------------------------------------------------------------------------

def yt_infos_video(url_ou_id: str) -> str:
    """
    Retourne les infos d'une vidéo YouTube : titre, chaîne, vues, likes, durée.
    Déclencheurs : 'infos de la vidéo', 'combien de vues', 'c'est quoi cette vidéo'
    """
    if not _cle_valide(YOUTUBE_API_KEY):
        return f"La clé API YouTube n'est pas configurée, {nom_utilisateur()}."

    video_id = _extraire_video_id(url_ou_id)
    if not video_id:
        return f"Je n'ai pas pu extraire l'identifiant de cette vidéo, {nom_utilisateur()}."

    try:
        r = requests.get(
            f"{_BASE_URL}/videos",
            params={
                "part": "snippet,statistics,contentDetails",
                "id": video_id,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        data = r.json()
        if not data.get("items"):
            return "Vidéo introuvable sur YouTube."

        item = data["items"][0]
        snip  = item["snippet"]
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})

        titre   = snip.get("title", "Titre inconnu")
        chaine  = snip.get("channelTitle", "Chaîne inconnue")
        vues    = _formater_nombre(int(stats.get("viewCount", 0)))
        likes   = _formater_nombre(int(stats.get("likeCount", 0))) if "likeCount" in stats else "non public"
        duree   = _duree_iso_to_lisible(details.get("duration", ""))
        date    = snip.get("publishedAt", "")[:10]

        return (
            f"La vidéo « {titre} » de la chaîne {chaine} "
            f"a été publiée le {date}. "
            f"Elle dure {duree}, totalise {vues} vues "
            f"et {likes} likes."
        )
    except Exception as e:
        return f"Erreur lors de la récupération des infos vidéo : {e}"


# ---------------------------------------------------------------------------
# 2. Recherche multi-résultats (5 vidéos)
# ---------------------------------------------------------------------------

def yt_chercher_multi(recherche: str, n: int = 5) -> str:
    """
    Retourne les N premiers résultats YouTube pour une recherche.
    Déclencheurs : 'cherche [X] sur youtube', 'montre-moi des vidéos de [X]'
    """
    if not _cle_valide(YOUTUBE_API_KEY):
        return f"La clé API YouTube n'est pas configurée, {nom_utilisateur()}."

    if not recherche.strip():
        return "Dites-moi ce que je dois rechercher sur YouTube."

    try:
        r = requests.get(
            f"{_BASE_URL}/search",
            params={
                "part": "snippet",
                "q": recherche,
                "type": "video",
                "maxResults": n,
                "relevanceLanguage": "fr",
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if not items:
            return f"Aucun résultat trouvé pour « {recherche} » sur YouTube."

        lignes = [f"Voici les {len(items)} meilleurs résultats pour « {recherche} » :"]
        for i, item in enumerate(items, 1):
            titre   = item["snippet"]["title"]
            chaine  = item["snippet"]["channelTitle"]
            vid_id  = item["id"]["videoId"]
            url     = f"https://www.youtube.com/watch?v={vid_id}"
            lignes.append(f"{i}. {titre} — par {chaine} | {url}")

        return "\n".join(lignes)
    except Exception as e:
        return f"Erreur lors de la recherche YouTube : {e}"


# ---------------------------------------------------------------------------
# 3. Vidéos trending / populaires
# ---------------------------------------------------------------------------

# Mapping catégories texte → ID YouTube
_CATEGORIES_YT = {
    "musique": "10",
    "jeux": "20",
    "jeu": "20",
    "gaming": "20",
    "sport": "17",
    "sports": "17",
    "science": "28",
    "technologie": "28",
    "tech": "28",
    "cinéma": "1",
    "cinema": "1",
    "film": "1",
    "actualité": "25",
    "actualites": "25",
    "info": "25",
    "infos": "25",
    "comédie": "23",
    "comedie": "23",
    "humour": "23",
}

def yt_trending(categorie: str = "", pays: str = "FR") -> str:
    """
    Retourne les 5 vidéos en tendance sur YouTube.
    Déclencheurs : 'les tendances youtube', 'vidéos populaires', 'top youtube'
    """
    if not _cle_valide(YOUTUBE_API_KEY):
        return f"La clé API YouTube n'est pas configurée, {nom_utilisateur()}."

    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": pays.upper(),
        "maxResults": 5,
        "key": YOUTUBE_API_KEY,
    }
    cat_id = _CATEGORIES_YT.get(categorie.lower().strip(), "")
    if cat_id:
        params["videoCategoryId"] = cat_id

    try:
        r = requests.get(f"{_BASE_URL}/videos", params=params, timeout=_TIMEOUT)
        items = r.json().get("items", [])
        if not items:
            return "Impossible de récupérer les tendances YouTube pour le moment."

        cat_label = f" en {categorie}" if categorie else ""
        lignes = [f"Voici le top {len(items)} des vidéos en tendance{cat_label} sur YouTube en ce moment :"]
        for i, item in enumerate(items, 1):
            titre  = item["snippet"]["title"]
            chaine = item["snippet"]["channelTitle"]
            vues   = _formater_nombre(int(item["statistics"].get("viewCount", 0)))
            vid_id = item["id"]
            url    = f"https://www.youtube.com/watch?v={vid_id}"
            lignes.append(f"{i}. {titre} — {chaine} ({vues} vues) | {url}")

        return "\n".join(lignes)
    except Exception as e:
        return f"Erreur lors de la récupération des tendances : {e}"


# ---------------------------------------------------------------------------
# 4. Infos sur une chaîne YouTube
# ---------------------------------------------------------------------------

def yt_infos_chaine(nom_chaine: str) -> str:
    """
    Retourne les infos d'une chaîne : abonnés, nb vidéos, description.
    Déclencheurs : 'combien d'abonnés a [X]', 'infos sur la chaîne [X]'
    """
    if not _cle_valide(YOUTUBE_API_KEY):
        return f"La clé API YouTube n'est pas configurée, {nom_utilisateur()}."

    channel_id, titre_officiel = _chercher_chaine_id(nom_chaine)
    if not channel_id:
        return f"Je n'ai pas trouvé la chaîne « {nom_chaine} » sur YouTube."

    try:
        r = requests.get(
            f"{_BASE_URL}/channels",
            params={
                "part": "snippet,statistics",
                "id": channel_id,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if not items:
            return f"Impossible de récupérer les infos de la chaîne « {nom_chaine} »."

        item  = items[0]
        stats = item.get("statistics", {})
        snip  = item.get("snippet", {})

        abonnes     = _formater_nombre(int(stats.get("subscriberCount", 0))) if stats.get("subscriberCount") else "non public"
        nb_videos   = _formater_nombre(int(stats.get("videoCount", 0)))
        nb_vues     = _formater_nombre(int(stats.get("viewCount", 0)))
        description = snip.get("description", "")[:150].strip()
        if description and not description.endswith("."):
            description += "…"

        reponse = (
            f"La chaîne YouTube « {titre_officiel} » compte {abonnes} abonnés, "
            f"{nb_videos} vidéos et {nb_vues} vues au total."
        )
        if description:
            reponse += f" Description : {description}"
        return reponse
    except Exception as e:
        return f"Erreur lors de la récupération des infos de la chaîne : {e}"


# ---------------------------------------------------------------------------
# 5. Résumé de vidéo via sous-titres (caption)
# ---------------------------------------------------------------------------

def yt_resumer_video(url_ou_id: str) -> str:
    """
    Tente de récupérer les sous-titres d'une vidéo YouTube et les envoie à l'IA.
    Déclencheurs : 'résume-moi cette vidéo', 'de quoi parle cette vidéo'
    Nécessite le package 'youtube_transcript_api' (pip install youtube-transcript-api)
    """
    if not _cle_valide(YOUTUBE_API_KEY):
        return f"La clé API YouTube n'est pas configurée, {nom_utilisateur()}."

    video_id = _extraire_video_id(url_ou_id)
    if not video_id:
        return f"Je n'ai pas pu extraire l'identifiant de cette vidéo, {nom_utilisateur()}."

    # Récupération des métadonnées (titre) via l'API
    titre = "cette vidéo"
    try:
        r = requests.get(
            f"{_BASE_URL}/videos",
            params={"part": "snippet", "id": video_id, "key": YOUTUBE_API_KEY},
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if items:
            titre = items[0]["snippet"]["title"]
    except Exception:
        pass

    # Tentative de récupération des sous-titres
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled  # type: ignore
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Priorité : français, sinon anglais, sinon première dispo
            try:
                transcript = transcript_list.find_transcript(["fr"])
            except NoTranscriptFound:
                try:
                    transcript = transcript_list.find_transcript(["en"])
                except NoTranscriptFound:
                    transcript = transcript_list._manually_created_transcripts and \
                                 list(transcript_list._manually_created_transcripts.values())[0] or \
                                 list(transcript_list._generated_transcripts.values())[0]

            segments = transcript.fetch()
            texte_brut = " ".join(seg["text"] for seg in segments)

            # Limite à ~3000 mots pour ne pas surcharger l'IA
            mots = texte_brut.split()
            if len(mots) > 3000:
                texte_brut = " ".join(mots[:3000]) + "…"

            # Résumé via le module IA de Jarvis (Gemini/Anthropic)
            try:
                import google.genai as genai  # type: ignore
                _gemini_key = os.getenv("GEMINI_API_KEY", "")
                if _cle_valide(_gemini_key):
                    client = genai.Client(api_key=_gemini_key)
                    prompt = (
                        f"Résume en français en 4-5 phrases concises le contenu "
                        f"de la vidéo YouTube intitulée « {titre} » "
                        f"à partir de sa transcription :\n\n{texte_brut}"
                    )
                    resp = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                    )
                    return f"Voici le résumé de « {titre} » : {resp.text.strip()}"
            except Exception:
                pass

            # Fallback : retourne les 500 premiers caractères de la transcription
            extrait = texte_brut[:500].strip()
            return (
                f"Je n'ai pas pu générer un résumé IA pour « {titre} », "
                f"mais voici le début de sa transcription : {extrait}…"
            )

        except (NoTranscriptFound, TranscriptsDisabled):
            return (
                f"La vidéo « {titre} » n'a pas de sous-titres disponibles, "
                f"je ne peux donc pas la résumer."
            )
    except ImportError:
        return (
            "Le module 'youtube-transcript-api' n'est pas installé. "
            "Dites-moi et je l'installerai pour activer cette fonctionnalité."
        )
    except Exception as e:
        return f"Erreur lors de la récupération des sous-titres : {e}"


# ---------------------------------------------------------------------------
# 6. Dernières vidéos d'une chaîne
# ---------------------------------------------------------------------------

def yt_dernieres_videos(nom_chaine: str, n: int = 3) -> str:
    """
    Retourne les N dernières vidéos publiées par une chaîne.
    Déclencheurs : 'dernières vidéos de [X]', 'quoi de neuf sur la chaîne [X]'
    """
    if not _cle_valide(YOUTUBE_API_KEY):
        return f"La clé API YouTube n'est pas configurée, {nom_utilisateur()}."

    channel_id, titre_officiel = _chercher_chaine_id(nom_chaine)
    if not channel_id:
        return f"Je n'ai pas trouvé la chaîne « {nom_chaine} » sur YouTube."

    try:
        r = requests.get(
            f"{_BASE_URL}/search",
            params={
                "part": "snippet",
                "channelId": channel_id,
                "order": "date",
                "type": "video",
                "maxResults": n,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if not items:
            return f"Aucune vidéo récente trouvée pour la chaîne « {titre_officiel} »."

        lignes = [f"Les {len(items)} dernières vidéos de « {titre_officiel} » :"]
        for i, item in enumerate(items, 1):
            titre   = item["snippet"]["title"]
            date    = item["snippet"]["publishedAt"][:10]
            vid_id  = item["id"]["videoId"]
            url     = f"https://www.youtube.com/watch?v={vid_id}"
            lignes.append(f"{i}. [{date}] {titre} | {url}")

        return "\n".join(lignes)
    except Exception as e:
        return f"Erreur lors de la récupération des dernières vidéos : {e}"
