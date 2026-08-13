import requests
import json
import random
import builtins
from google.genai import types

def obtenir_ville_par_ip():
    """Détecte la ville de l'utilisateur par son IP en utilisant une API publique gratuite."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=4)
        if r.status_code == 200:
            data = r.json()
            city = data.get("city")
            country = data.get("country_name")
            if city:
                print(f"[RESTAURANT] Géolocalisation IP : {city}, {country}")
                return f"{city}, {country}"
    except Exception as e:
        print(f"[RESTAURANT] Erreur géolocalisation IP : {e}")
    return "Paris, France"

def rechercher_restaurants_proches(location, lat=None, lng=None, exclure=None):
    """Recherche des restaurants à proximité (SerpAPI en priorité, Gemini en fallback)."""
    import os
    import json
    import random
    import requests
    import google.genai as genai
    from dotenv import load_dotenv
    
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    
    target_loc = location if location else "Amilly"
    
    # 1. Tentative SerpAPI (ultra-rapide et fiable)
    serp_key = os.getenv("SERPAPI_API_KEY")
    if serp_key and serp_key != "VOTRE_CLE_ICI":
        try:
            print(f"[RESTAURANT] Recherche SerpAPI pour la ville : {target_loc}")
            params = {
                "engine": "google",
                "q": f"restaurants à {target_loc}",
                "api_key": serp_key,
                "hl": "fr",
                "gl": "fr"
            }
            r = requests.get("https://serpapi.com/search.json", params=params, timeout=8)
            data = r.json()
            places = data.get("local_results", {}).get("places", [])
            if places:
                results = []
                for p in places:
                    nom = p.get("title", "")
                    if exclure and nom in exclure:
                        continue
                    
                    cuisine = p.get("type", "Restaurant")
                    adresse = p.get("address", target_loc)
                    note = p.get("rating", 4.2)
                    horaires = p.get("hours", "Inconnu")
                    desc = p.get("description", "Adresse gourmande locale.")
                    
                    coords = "Inconnu"
                    if "gps_coordinates" in p:
                        coords = f"{p['gps_coordinates']['latitude']}, {p['gps_coordinates']['longitude']}"
                        
                    results.append({
                        "nom": nom,
                        "cuisine": cuisine,
                        "adresse": adresse,
                        "note": note,
                        "telephone": "Inconnu",
                        "site_web": "Inconnu",
                        "horaires": horaires,
                        "coordonnees": coords,
                        "details_speciaux": desc,
                        "distance_estimee": "À proximité",
                        "angle_radar": random.randint(0, 360),
                        "distance_radar": random.randint(20, 85)
                    })
                if results:
                    print(f"[RESTAURANT] {len(results)} restaurants trouvés via SerpAPI.")
                    return results[:6]
        except Exception as e:
            print(f"[RESTAURANT] Échec SerpAPI : {e}")

    # 2. Fallback Gemini (sans coordonnes GPS dans le prompt)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            local_client = genai.Client(api_key=api_key)
            model_name = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
            
            print(f"[RESTAURANT] Fallback Gemini pour la ville : {target_loc}")
            prompt = (
                f"Fais une recherche sur Google pour trouver de bons restaurants (ou adresses gourmandes) à proximité de '{target_loc}'. "
                f"Donne-moi une liste de 6 restaurants réels. "
                f"Pour chaque restaurant, tu devez fournir les informations exactes au format JSON suivant. "
                f"Renvoie uniquement un tableau JSON contenant des objets avec ces clés :\n"
                f"- 'nom': Nom du restaurant\n"
                f"- 'cuisine': Type de cuisine (ex: 'Italien', 'Bistrot', 'Gastronomique')\n"
                f"- 'adresse': Adresse physique simplifiée\n"
                f"- 'note': Note sur 5 (nombre décimal ou entier, ex: 4.5)\n"
                f"- 'telephone': Numéro de téléphone du restaurant (ex: '01 30 22 45 67' ou 'Inconnu')\n"
                f"- 'site_web': URL de son site internet ou lien Google Maps (ex: 'https://...' ou 'Inconnu')\n"
                f"- 'horaires': Horaires d'ouverture simplifiés (ex: '12:00-14:30, 19:00-22:30' ou 'Inconnu')\n"
                f"- 'coordonnees': Coordonnées GPS sous format 'latitude, longitude' (ex: '48.8566, 2.3522' ou 'Inconnu')\n"
                f"- 'details_speciaux': Une phrase de description de sa spécialité ou plat phare (ex: 'Spécialiste de la fondue savoyarde au feu de bois' ou 'Inconnu')\n"
                f"- 'distance_estimee': Distance estimée depuis '{target_loc}' (ex: '350m', '1.2km')\n"
                f"- 'angle_radar': Un angle de positionnement aléatoire ou réaliste entre 0 et 360 (pour affichage sur écran radar)\n"
                f"- 'distance_radar': Un rayon de positionnement sur le radar entre 20 et 90 (pour l'affichage sur écran radar)\n\n"
                f"Important : Renvoie uniquement le JSON brut. Pas de texte explicatif avant ou après, pas de balise ```json, juste le tableau JSON."
            )
            if exclure and isinstance(exclure, list) and len(exclure) > 0:
                prompt += f"\nImportant : N'affiche PAS ces restaurants (exclus-les absolument de la recherche car ils ont déjà été affichés) : {', '.join(exclure)}."

            print(f"[RESTAURANT] Envoi de la requête Gemini (Modèle: {model_name})...")
            import time
            t_start = time.time()
            response = local_client.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    system_instruction="Tu es un assistant expert en gastronomie locale. Tu dois renvoyer uniquement du JSON pur."
                )
            )
            print(f"[RESTAURANT] Réponse Gemini reçue en {time.time() - t_start:.2f} secondes.")
            text = response.text.strip()
            
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
                
            restaurants = json.loads(text)
            if isinstance(restaurants, list) and len(restaurants) > 0:
                print(f"[RESTAURANT] {len(restaurants)} restaurants trouvés via Gemini Search.")
                return restaurants
        except Exception as e:
            print(f"[RESTAURANT] Erreur recherche Gemini restaurants : {e}")
            import traceback
            traceback.print_exc()

    return obtenir_mock_restaurants(target_loc, exclure=exclure)

def obtenir_mock_restaurants(location, exclure=None):
    """Retourne une liste de restaurants factices (fallback sécurisé)."""
    print(f"[RESTAURANT] Utilisation du fallback mock de restaurants pour : {location}")
    nom_loc = location.split(",")[0].strip()
    
    mock_data = [
        {
            "nom": f"Le Bistrot de {nom_loc}",
            "cuisine": "Cuisine Traditionnelle",
            "adresse": f"12 Rue de la République, {nom_loc}",
            "note": 4.6,
            "telephone": "01 34 56 78 90",
            "site_web": "https://www.bistrot-local-test.fr",
            "horaires": "12:00-14:30, 19:00-22:30",
            "coordonnees": "48.8566, 2.3522",
            "details_speciaux": "Célèbre pour sa cuisine de terroir et sa tarte tatin maison.",
            "distance_estimee": "250m",
            "angle_radar": 45,
            "distance_radar": 35
        },
        {
            "nom": "L'Atelier des Saveurs",
            "cuisine": "Gastronomique",
            "adresse": f"45 Avenue des Champs, {nom_loc}",
            "note": 4.8,
            "telephone": "01 23 45 67 89",
            "site_web": "https://www.atelier-saveurs-test.fr",
            "horaires": "19:00-23:00",
            "coordonnees": "48.8738, 2.2950",
            "details_speciaux": "Menu dégustation raffiné avec accords mets & vins d'exception.",
            "distance_estimee": "680m",
            "angle_radar": 120,
            "distance_radar": 60
        },
        {
            "nom": "Bella Italia",
            "cuisine": "Italien",
            "adresse": f"8 Rue du Théâtre, {nom_loc}",
            "note": 4.3,
            "telephone": "01 45 67 89 01",
            "site_web": "https://www.bella-italia-test.it",
            "horaires": "12:00-14:00, 19:00-22:00",
            "coordonnees": "48.8650, 2.3200",
            "details_speciaux": "Pizzas cuites au feu de bois et pâtes fraîches faites maison.",
            "distance_estimee": "400m",
            "angle_radar": 290,
            "distance_radar": 45
        },
        {
            "nom": "Le Phare Gourmand",
            "cuisine": "Poissons & Fruits de mer",
            "adresse": f"2 Place de la Marine, {nom_loc}",
            "note": 4.5,
            "telephone": "01 56 78 90 12",
            "site_web": "https://www.phare-gourmand-test.com",
            "horaires": "12:00-14:30, 19:00-22:30",
            "coordonnees": "48.8400, 2.3700",
            "details_speciaux": "Plateaux de fruits de mer frais livrés chaque matin.",
            "distance_estimee": "1.1km",
            "angle_radar": 180,
            "distance_radar": 85
        },
        {
            "nom": "Le Wok d'Or",
            "cuisine": "Asiatique",
            "adresse": f"67 Boulevard Carnot, {nom_loc}",
            "note": 4.2,
            "telephone": "01 67 89 01 23",
            "site_web": "https://www.wok-dor-test.cn",
            "horaires": "11:30-14:30, 18:30-22:30",
            "coordonnees": "48.8800, 2.3100",
            "details_speciaux": "Buffet asiatique à volonté et grillades à la plancha.",
            "distance_estimee": "820m",
            "angle_radar": 30,
            "distance_radar": 70
        },
        {
            "nom": "Chez l'Oncle Sam",
            "cuisine": "Burgers & Grill",
            "adresse": f"19 Rue de Verdun, {nom_loc}",
            "note": 4.4,
            "telephone": "01 78 90 12 34",
            "site_web": "https://www.unclesam-grill-test.us",
            "horaires": "11:30-23:00 (non-stop)",
            "coordonnees": "48.8300, 2.3400",
            "details_speciaux": "Burgers américains gourmets de boeuf d'origine locale.",
            "distance_estimee": "510m",
            "angle_radar": 230,
            "distance_radar": 50
        }
    ]
    if exclure and isinstance(exclure, list):
        filtered_mock = [r for r in mock_data if r["nom"] not in exclure]
        if len(filtered_mock) < 4:
            for i in range(6):
                var_r = dict(mock_data[i])
                var_r["nom"] = var_r["nom"] + f" ({random.choice(['Le Relais', 'L\'Annexe', 'Le Coin', 'Chez l\'Hôte'])})"
                var_r["note"] = round(min(5.0, var_r["note"] + random.uniform(-0.3, 0.2)), 1)
                var_r["angle_radar"] = (var_r["angle_radar"] + 90) % 360
                if var_r["nom"] not in exclure:
                    filtered_mock.append(var_r)
        return filtered_mock[:6]
    return mock_data
