import requests
import json
import os
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types

load_dotenv()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
if SERPAPI_API_KEY == "VOTRE_CLE_ICI":
    SERPAPI_API_KEY = None

def recherche_images_gemini(query, nb_images=6):
    """Recherche des images en demandant à Gemini (avec Google Search Grounding) de renvoyer des URLs d'images."""
    import builtins
    if not hasattr(builtins, "client") or builtins.client is None:
        print("[IMAGE] Gemini client non disponible dans builtins.")
        return []
    
    try:
        print(f"[IMAGE] Recherche Gemini Images (avec Google Search) pour : {query}")
        prompt = (
            f"Effectue une recherche sur internet pour trouver des images de '{query}'. "
            f"Donne-moi une liste de {nb_images} URLs d'images directes ou d'images sources valides (par exemple se terminant par .jpg, .png, .jpeg ou provenant de banques d'images ou d'articles de presse). "
            f"Renvoie uniquement un tableau JSON contenant ces URLs (exemple: [\"https://site.com/image.jpg\", ...]). "
            f"Important: Ne mets aucun texte explicatif avant ou après le JSON, pas de balise ```json, uniquement le tableau JSON brut."
        )
        
        model_name = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        
        response = builtins.client.models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction="Tu es un assistant spécialisé dans la recherche d'images sur internet. Tu dois uniquement renvoyer un tableau JSON d'URLs."
            )
        )
        text = response.text.strip()
        
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            
        urls = json.loads(text)
        if isinstance(urls, list):
            valid_urls = [u for u in urls if isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))]
            print(f"[IMAGE] {len(valid_urls)} image(s) trouvées via Gemini.")
            return valid_urls[:nb_images]
    except Exception as e:
        print(f"[IMAGE] Erreur recherche Gemini Images : {e}")
    return []

def recherche_images_web(query, nb_images=6, engine="serpapi"):
    """Recherche des images sur internet via le moteur spécifié (serpapi, gemini, duckduckgo)."""
    urls = []
    
    # ── Moteur Gemini ────────────────────────────────────────────────────────
    if engine == "gemini":
        urls = recherche_images_gemini(query, nb_images)
        if urls:
            return urls
        print("[IMAGE] Échec ou pas de résultats via Gemini. Essai du fallback...")
        
    # ── Moteur SerpAPI ───────────────────────────────────────────────────────
    elif engine == "serpapi":
        if _cle_valide(SERPAPI_API_KEY):
            try:
                print(f"[IMAGE] Recherche SerpAPI Images pour : {query}")
                params = {
                    "engine": "google_images",
                    "q": query,
                    "api_key": SERPAPI_API_KEY,
                    "hl": "fr",
                    "gl": "fr",
                    "num": nb_images,
                }
                r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
                data = r.json()
                images_results = data.get("images_results", [])
                for img in images_results[:nb_images]:
                    src = img.get("original") or img.get("thumbnail")
                    if src:
                        urls.append(src)
                if urls:
                    print(f"[IMAGE] {len(urls)} image(s) trouvées via SerpAPI.")
                    return urls
            except Exception as e:
                print(f"[IMAGE] Erreur SerpAPI Images : {e}")
        else:
            print("[IMAGE] Clé SerpAPI non valide/configurée.")
            
    # ── Moteur DuckDuckGo (ou fallback global) ────────────────────────────────
    try:
        print(f"[IMAGE] Recherche DuckDuckGo Images pour : {query}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(
            "https://duckduckgo.com/",
            params={"q": query, "iax": "images", "ia": "images"},
            headers=headers, timeout=8
        )
        import re as _re
        vqd_match = _re.search(r'vqd=([\d-]+)', r.text)
        if vqd_match:
            vqd = vqd_match.group(1)
            r2 = requests.get(
                "https://duckduckgo.com/i.js",
                params={"l": "fr-fr", "o": "json", "q": query, "vqd": vqd, "f": ",,,,,", "p": "1"},
                headers=headers, timeout=8
            )
            data2 = r2.json()
            for item in data2.get("results", [])[:nb_images]:
                img_url = item.get("image")
                if img_url:
                    urls.append(img_url)
            if urls:
                print(f"[IMAGE] {len(urls)} image(s) trouvées via DuckDuckGo.")
                return urls
    except Exception as e:
        print(f"[IMAGE] Erreur DuckDuckGo Images : {e}")

    print(f"[IMAGE] Aucune image trouvée pour : {query}")
    return []


def recherche_web_serpapi(query):
    """Effectue une recherche sur Google via SerpAPI."""
    if not _cle_valide(SERPAPI_API_KEY):
        return None
    
    try:
        print(f"[WEB] Recherche SerpAPI pour : {query}")
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "hl": "fr",
            "gl": "fr"
        }
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        data = r.json()
        
        # Extraction des actualités si présentes
        if "news_results" in data:
            news = data["news_results"][:3]
            reponse = f"Voici les dernières actualités pour {query} :\n"
            for n in news:
                source = n.get("source", "Source inconnue")
                titre = n.get("title", "")
                reponse += f"- {titre} (via {source})\n"
            return reponse
            
        # Extraction des résultats organiques sinon
        if "organic_results" in data:
            results = data["organic_results"][:3]
            reponse = f"Voici ce que j'ai trouvé sur le web pour {query} :\n"
            for r in results:
                titre = r.get("title", "")
                snippet = r.get("snippet", "")
                reponse += f"- {titre} : {snippet}\n"
            return reponse
            
        return f"Je n'ai rien trouvé de pertinent sur le web pour : {query}."
    except Exception as e:
        print(f"[WEB] Erreur SerpAPI : {e}")
        return "Une erreur est survenue lors de la recherche sur internet."

THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

def get_resultats_football(equipe=None, ligue=None):
    try:
        if equipe:
            print(f"[SPORT] Recherche pour l'equipe : {equipe}")
            r = requests.get(f"{THESPORTSDB_BASE}/searchteams.php", params={"t": equipe}, timeout=5)
            data = r.json()
            teams = data.get("teams")
            if not teams:
                return f"Je n'ai pas trouvé l'équipe {equipe}."
            
            team_id   = teams[0]["idTeam"]
            team_name = teams[0]["strTeam"]
            
            # On cherche les derniers ET les prochains matchs
            res_last = requests.get(f"{THESPORTSDB_BASE}/eventslast.php", params={"id": team_id}, timeout=5).json()
            res_next = requests.get(f"{THESPORTSDB_BASE}/eventsnext.php", params={"id": team_id}, timeout=5).json()
            
            matchs_passes = res_last.get("results", [])
            matchs_futurs = res_next.get("events", [])
            
            reponse = f"Concernant le {team_name} : "
            
            if matchs_futurs:
                m = matchs_futurs[0]
                date_m = m.get("dateEvent", "date inconnue")
                heure_m = m.get("strTime", "")
                reponse += f"Le prochain match aura lieu le {date_m} à {heure_m} contre {m.get('strOpponent')}. "
            
            if matchs_passes:
                m = matchs_passes[0]
                reponse += f"Leur dernier résultat était {m.get('intHomeScore')} à {m.get('intAwayScore')} contre {m.get('strOpponent')}."
            
            if not matchs_futurs and not matchs_passes:
                return f"Je n'ai pas d'informations récentes ou futures pour {team_name}."
                
            return reponse
        else:
            nom_ligue = ligue or "Ligue 1"
            ligue_ids = {
                "ligue 1": "4334", "premier league": "4328", "liga": "4335",
                "bundesliga": "4331", "serie a": "4332",
                "champions league": "4480", "ligue des champions": "4480",
            }
            ligue_id = ligue_ids.get(nom_ligue.lower(), "4334")
            r = requests.get(f"{THESPORTSDB_BASE}/eventspastleague.php", params={"id": ligue_id}, timeout=5)
            data   = r.json()
            matchs = data.get("events", [])
            if not matchs:
                return f"Aucun resultat trouve pour {nom_ligue}."
            reponse = f"Derniers resultats {nom_ligue} : "
            lignes  = []
            for m in matchs[-6:]:
                home    = m.get("strHomeTeam", "?")
                away    = m.get("strAwayTeam", "?")
                score_h = m.get("intHomeScore", "?")
                score_a = m.get("intAwayScore", "?")
                date    = m.get("dateEvent", "?")
                lignes.append(f"{home} {score_h}-{score_a} {away} ({date})")
            return reponse + " | ".join(lignes)
    except Exception as e:
        print(f"[SPORT] Erreur football : {e}")
        return f"Impossible de recuperer les resultats football : {e}"

def get_classement_football(ligue=None):
    try:
        nom_ligue = ligue or "Ligue 1"
        ligue_ids = {
            "ligue 1": "4334", "premier league": "4328", "liga": "4335",
            "bundesliga": "4331", "serie a": "4332",
            "champions league": "4480", "ligue des champions": "4480",
        }
        ligue_id = ligue_ids.get(nom_ligue.lower(), "4334")
        r = requests.get(f"{THESPORTSDB_BASE}/lookuptable.php", params={"l": ligue_id, "s": "2024-2025"}, timeout=8)
        data    = r.json()
        tableau = data.get("table", [])
        if not tableau:
            return f"Classement {nom_ligue} non disponible pour le moment."
        reponse = f"Classement {nom_ligue} : "
        lignes  = []
        for eq in tableau[:10]:
            pos   = eq.get("intRank", "?")
            nom   = eq.get("strTeam", "?")
            pts   = eq.get("intPoints", "?")
            joues = eq.get("intPlayed", "?")
            lignes.append(f"{pos}. {nom} - {pts}pts ({joues}J)")
        return reponse + " | ".join(lignes)
    except Exception as e:
        print(f"[SPORT] Erreur classement : {e}")
        return f"Impossible de recuperer le classement : {e}"

def get_resultats_sport_gemini(question_sport):
    try:
        response = client.models.generate_content(
            model   = CHOSEN_MODEL,
            contents= [types.Content(role="user", parts=[types.Part(text=
                f"Donne-moi les derniers resultats et actualites sportives en 2026 "
                f"pour : {question_sport}. "
                f"Sois precis, donne les scores et dates. Reponds en francais."
            )])],
            config  = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction=(
                    "Tu es un expert sportif. Donne des resultats precis et a jour. "
                    "Reponds de facon concise et conversationnelle en francais."
                )
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[SPORT] Erreur Gemini sport : {e}")
        return "Je n arrive pas a recuperer les resultats sportifs pour le moment."

