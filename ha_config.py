# ============================================================
#  ha_config.py — Configuration Home Assistant & Météo
#  Personnalisez CE fichier selon votre installation domotique
#  Ne touchez pas main2.py pour la domotique, tout est ici.
# ============================================================

import os
import json
import requests
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from config import nom_utilisateur

def _charger_user_name():
    # Delegue a config : une seule source pour le prenom.
    return nom_utilisateur()

_USER = _charger_user_name().lower()

def _update_ha_env():
    global HA_URL, HA_TOKEN, HA_HEADERS
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)
    HA_URL    = os.getenv("HA_URL", "").rstrip("/")
    HA_TOKEN  = os.getenv("HA_TOKEN", "")
    HA_HEADERS = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type" : "application/json"
    }

# Initial load
HA_URL = ""
HA_TOKEN = ""
HA_HEADERS = {}
_update_ha_env()

# ═══════════════════════════════════════════════════════════════
#  SECTION 1 — MÉTÉO PAR DÉFAUT
#  Remplacez par votre ville et ses coordonnées GPS.
#  Coordonnées : https://www.latlong.net/
# ═══════════════════════════════════════════════════════════════
VILLE_PAR_DEFAUT = "Amilly"   # ← Votre ville
LAT_PAR_DEFAUT   = 47.9742    # ← Latitude
LON_PAR_DEFAUT   = 2.7708     # ← Longitude

def reload_config_values():
    global VILLE_PAR_DEFAUT, LAT_PAR_DEFAUT, LON_PAR_DEFAUT
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(_p):
            with open(_p, "r", encoding="utf-8") as _f:
                cfg = json.load(_f)
                if "user_city" in cfg and cfg["user_city"]:
                    VILLE_PAR_DEFAUT = cfg["user_city"]
                if "user_lat" in cfg and cfg["user_lat"] is not None:
                    LAT_PAR_DEFAUT = float(cfg["user_lat"])
                if "user_lon" in cfg and cfg["user_lon"] is not None:
                    LON_PAR_DEFAUT = float(cfg["user_lon"])
    except Exception as e:
        print(f"[HA_CONFIG] Erreur reload_config_values : {e}")

reload_config_values()

# ═══════════════════════════════════════════════════════════════
#  SECTION 2 — LUMIÈRES
#  Format : "nom vocal" : "entity_id Home Assistant"
#  Pour trouver un entity_id : HA → Paramètres → Appareils
#    → cliquez sur l'entité → "Informations sur l'entité"
# ═══════════════════════════════════════════════════════════════

# Vide par defaut, et ce n'est pas un oubli.
#
# Ces tables contenaient 48 entites cablees en dur, decrivant le logement
# d'une personne nommee — jusqu'au telephone et a la montre de quelqu'un.
# Verifie le 13/08/2026 contre le Home Assistant en marche : sur ces 48
# entites, ZERO existe parmi les 737 reelles. Elles ne pouvaient rien
# piloter, et « allume le salon » repondait « j'allume le salon » sans
# qu'aucune lampe ne bouge.
#
# Deux raisons de les vider plutot que de les corriger :
#   - elles ne peuvent pas etre justes pour deux logements differents ;
#   - ha_resolution.py interroge le Home Assistant VIVANT et resout les noms
#     parles contre les vrais libelles, ce qu'aucune table figee ne sait faire.
#
# Une correspondance personnelle reste possible : _charger_custom_ha_entities()
# les lit depuis jarvis_config.json, qui n'est pas suivi par git.
PIECES_LUMIERES = {}   # nom parle -> entite light.*

# ═══════════════════════════════════════════════════════════════
#  SECTION 3 — PRISES CONNECTÉES
#  Format : "nom vocal" : "entity_id switch.xxx"
# ═══════════════════════════════════════════════════════════════
PIECES_PRISES = {}   # nom parle -> entite switch.*

# ═══════════════════════════════════════════════════════════════
#  SECTION 4 — CAPTEURS TEMPÉRATURE & DIVERS
#  Format : "nom vocal" : "entity_id sensor.xxx"
#  Vous pouvez ajouter autant de pièces que nécessaire.
# ═══════════════════════════════════════════════════════════════
PIECES_CAPTEURS = {}   # nom parle -> capteur de temperature

# ═══════════════════════════════════════════════════════════════
#  SECTION 5 — CAPTEURS HUMIDITÉ
#  Format : "nom vocal" : "entity_id sensor.xxx"
# ═══════════════════════════════════════════════════════════════
PIECES_HUMIDITE = {}   # nom parle -> capteur d'humidite

# ═══════════════════════════════════════════════════════════════
#  SECTION 6 — TARIFS ÉLECTRICITÉ (€/kWh)
#  Adaptez selon votre contrat EDF / fournisseur
#  p1-p6 = plages tarifaires Linky (heures creuses, pleines, etc.)
# ═══════════════════════════════════════════════════════════════
HA_TARIFS = {
    "p1": 0.1296,
    "p2": 0.1603,
    "p3": 0.1486,
    "p4": 0.1894,
    "p5": 0.1568,
    "p6": 0.7562,
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 7 — SUIVI ÉNERGIE PAR APPAREIL
#  Format : "nom vocal" : "entity_id sensor.xxx_mensuel"
# ═══════════════════════════════════════════════════════════════
APPAREILS_ENERGIE = {}   # nom parle -> capteur de consommation

# ═══════════════════════════════════════════════════════════════
#  SECTION 8 — BATTERIES DES APPAREILS
#  Format : "nom vocal" : "entity_id sensor.xxx_battery_level"
# ═══════════════════════════════════════════════════════════════
APPAREILS_BATTERIE = {}   # nom parle -> capteur de batterie

# ═══════════════════════════════════════════════════════════════
#  SECTION 9 — COULEURS RGB
#  Format : "nom vocal" : [R, G, B]
#  Vous pouvez ajouter vos propres couleurs.
# ═══════════════════════════════════════════════════════════════
COULEURS_MAP = {
    "rouge"     : [255, 0,   0  ],
    "bleu"      : [0,   0,   255],
    "vert"      : [0,   255, 0  ],
    "blanc"     : [255, 255, 255],
    "orange"    : [255, 140, 0  ],
    "violet"    : [148, 0,   211],
    "rose"      : [255, 20,  147],
    "jaune"     : [255, 255, 0  ],
    "cyan"      : [0,   255, 255],
    "magenta"   : [255, 0,   255],
    "turquoise" : [64,  224, 208],
    "or"        : [255, 215, 0  ],
    "argent"    : [192, 192, 192],
    "indigo"    : [75,  0,   130],
    "marron"    : [139, 69,  19 ],
    "citron"    : [255, 250, 0  ],
    "corail"    : [255, 127, 80 ],
    "lavande"   : [230, 230, 250],
}

# ── Codes météo Open-Meteo (ne pas modifier) ─────────────────
CODES_METEO = {
    0:  "degage",
    1:  "principalement clair", 2: "partiellement nuageux", 3: "couvert",
    45: "brouillard", 48: "brouillard givrant",
    51: "bruine legere", 53: "bruine moderee", 55: "bruine dense",
    61: "pluie faible", 63: "pluie moderee", 65: "pluie forte",
    71: "neige faible", 73: "neige moderee", 75: "neige forte",
    80: "averses faibles", 81: "averses moderees", 82: "averses violentes",
    85: "averses de neige", 86: "averses de neige fortes",
    95: "orage", 96: "orage avec grele", 99: "orage violent avec grele",
}

# ════════════════════════════════════════════════════════════════
#  ENTITÉS HOME ASSISTANT PERSONNALISÉES (chargées depuis jarvis_config.json)
#  Rechargé automatiquement à chaque sauvegarde dans les paramètres.
# ════════════════════════════════════════════════════════════════

_HA_CUSTOM_KEYS: dict = {"lumieres": set(), "prises": set(), "capteurs": set()}

def _charger_custom_ha_entities():
    global _HA_CUSTOM_KEYS
    _update_ha_env()
    for k in _HA_CUSTOM_KEYS["lumieres"]:
        PIECES_LUMIERES.pop(k, None)
    for k in _HA_CUSTOM_KEYS["prises"]:
        PIECES_PRISES.pop(k, None)
    for k in _HA_CUSTOM_KEYS["capteurs"]:
        PIECES_CAPTEURS.pop(k, None)
    _HA_CUSTOM_KEYS = {"lumieres": set(), "prises": set(), "capteurs": set()}
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            _cfg = json.load(_f)
        custom = _cfg.get("ha_custom_entities", {})
        for entry in custom.get("lumieres", []):
            nom = entry["nom"].lower().strip()
            PIECES_LUMIERES[nom] = entry["entity_id"]
            _HA_CUSTOM_KEYS["lumieres"].add(nom)
        for entry in custom.get("prises", []):
            nom = entry["nom"].lower().strip()
            PIECES_PRISES[nom] = entry["entity_id"]
            _HA_CUSTOM_KEYS["prises"].add(nom)
        for entry in custom.get("capteurs", []):
            nom = entry["nom"].lower().strip()
            PIECES_CAPTEURS[nom] = entry["entity_id"]
            _HA_CUSTOM_KEYS["capteurs"].add(nom)
    except Exception:
        pass

_charger_custom_ha_entities()

# ════════════════════════════════════════════════════════════════
#  FONCTIONS API HOME ASSISTANT
#  Ne modifiez pas ces fonctions — elles appellent l'API HA.
# ════════════════════════════════════════════════════════════════

# Entités inexistantes déjà rencontrées, pour ne pas re-interroger HA à
# chaque tentative ni répéter le même avertissement en boucle.
_ENTITES_FANTOMES = set()


def ha_entite_existe(entity_id):
    """
    L'entité est-elle connue de Home Assistant ?

    HA accepte un appel de service sur une entité INEXISTANTE et répond 200 :
    il n'a simplement rien à faire. Sans cette vérification, JARVIS annonçait
    « c'est fait » pour une lampe qui n'existe pas — le pire mensonge possible,
    puisqu'il porte sur une action physique.
    """
    if entity_id in _ENTITES_FANTOMES:
        return False
    try:
        r = requests.get(f"{HA_URL}/api/states/{entity_id}",
                         headers=HA_HEADERS, timeout=5)
        if r.status_code == 404:
            _ENTITES_FANTOMES.add(entity_id)
            return False
        return r.status_code == 200
    except Exception:
        # HA injoignable : on ne conclut pas a une entite fantome, ce serait
        # confondre « n'existe pas » et « je n'ai pas pu verifier ».
        return True


def ha_appeler_service(domaine, service, entity_id, donnees=None):
    _update_ha_env()

    # Verifier AVANT d'agir. Un 200 de HA ne prouve pas qu'il s'est passe
    # quelque chose : sur cette installation, les 64 entites declarees dans
    # ce fichier sont absentes de Home Assistant, et chaque commande
    # renvoyait pourtant un succes.
    if not ha_entite_existe(entity_id):
        print(f"[HA] ENTITE INEXISTANTE : {entity_id} — commande {domaine}."
              f"{service} NON executee. Corriger la table dans ha_config.py.")
        return False

    try:
        payload = {"entity_id": entity_id}
        if donnees:
            payload.update(donnees)
        print(f"[HA DEBUG] Calling {domaine}/{service} for {entity_id} with {donnees}")
        r = requests.post(
            f"{HA_URL}/api/services/{domaine}/{service}",
            headers=HA_HEADERS, json=payload, timeout=5
        )
        print(f"[HA DEBUG] Response {r.status_code}: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[HA] Erreur service : {e}")
        return False


def entites_declarees_absentes():
    """
    Entités déclarées dans ce fichier mais absentes de Home Assistant.

    Alimente l'auto-diagnostic : une table de correspondance qui pointe vers
    le vide est une panne, pas une configuration.
    Renvoie [(table, nom_vocal, entity_id)] ou lève si HA est injoignable.
    """
    reels = {e["entity_id"] for e in requests.get(
        f"{HA_URL}/api/states", headers=HA_HEADERS, timeout=15).json()}
    domaines = ("light", "switch", "sensor", "climate", "scene", "lock",
                "cover", "media_player", "vacuum", "binary_sensor", "fan")
    absentes = []
    for nom_table, table in sorted(globals().items()):
        if not (nom_table.isupper() and isinstance(table, dict)):
            continue
        for cle, val in table.items():
            if (isinstance(val, str) and "." in val
                    and val.split(".")[0] in domaines and val not in reels):
                absentes.append((nom_table, cle, val))
    return absentes

def ha_get_etat(entity_id, attribut=None):
    _update_ha_env()
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        print(f"[HA DEBUG] GET {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        print(f"[HA DEBUG] Status={r.status_code}  Body={r.text[:200]!r}")
        data = r.json()
        if attribut:
            return data.get("attributes", {}).get(attribut, "inconnu")
        return data.get("state", "inconnu")
    except Exception as e:
        print(f"[HA] Erreur get etat : {e}")
        return "inconnu"

def ha_get_calendrier(entity_id):
    _update_ha_env()
    try:
        now   = datetime.now()
        start = now.strftime("%Y-%m-%dT00:00:00Z")
        end   = now.strftime("%Y-%m-%dT23:59:59Z")
        r = requests.get(
            f"{HA_URL}/api/calendars/{entity_id}",
            headers=HA_HEADERS,
            params={"start": start, "end": end},
            timeout=5
        )
        return r.json()
    except Exception as e:
        print(f"[HA] Erreur calendrier : {e}")
        return []

def ha_lumiere(entity_id, etat="on", luminosite=None, rgb=None):
    service_name = "toggle" if etat == "toggle" else ("turn_on" if etat == "on" else "turn_off")
    donnees = {}
    if etat == "on":
        if luminosite is not None:
            donnees["brightness"] = int(luminosite)
        if rgb is not None:
            donnees["rgb_color"] = rgb
    return ha_appeler_service("light", service_name, entity_id, donnees)

def ha_interrupteur(entity_id, etat="on"):
    service_name = "turn_on" if etat == "on" else "turn_off"
    return ha_appeler_service("switch", service_name, entity_id)

def ha_thermostat(entity_id, temperature):
    return ha_appeler_service("climate", "set_temperature", entity_id, {"temperature": temperature})

def ha_scene(scene_id):
    return ha_appeler_service("scene", "turn_on", scene_id)

def ha_verrou(entity_id, etat="lock"):
    service_name = "lock" if etat == "lock" else "unlock"
    return ha_appeler_service("lock", service_name, entity_id)

# ════════════════════════════════════════════════════════════════
#  FONCTIONS MÉTÉO
#  Utilisent Open-Meteo (gratuit) + Home Assistant en fallback.
# ════════════════════════════════════════════════════════════════

def geocoder_ville(ville):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ville, "count": 1, "language": "fr", "format": "json"},
            timeout=5
        )
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return res["latitude"], res["longitude"], res.get("name", ville), res.get("country", "")
    except Exception as e:
        print(f"[METEO] Erreur geocoding : {e}")
    return None, None, ville, ""

def get_meteo_structuree(ville=None):
    """Retourne les données météo structurées pour le panneau visuel frontend."""
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude" : lat, "longitude": lon,
                "current"  : "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weathercode",
                "timezone" : "Europe/Paris",
            },
            timeout=8
        )
        cur  = r.json()["current"]
        code = cur.get("weathercode", 0)
        return {
            "ville"      : nom_affiche,
            "temperature": round(float(cur.get("temperature_2m", 0))),
            "ressenti"   : round(float(cur.get("apparent_temperature", 0))),
            "humidite"   : round(float(cur.get("relative_humidity_2m", 0))),
            "vent"       : round(float(cur.get("wind_speed_10m", 0))),
            "code"       : code,
            "description": CODES_METEO.get(code, "inconnu"),
        }
    except Exception as e:
        print(f"[METEO_DATA] Erreur : {e}")
        return None

def get_meteo_actuelle(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude"       : lat, "longitude": lon,
                "current"        : "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weathercode,precipitation",
                "hourly"         : "temperature_2m,precipitation_probability",
                "daily"          : "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
                "timezone"       : "Europe/Paris",
                "forecast_days"  : 3,
                "wind_speed_unit": "kmh",
            },
            timeout=8
        )
        data = r.json()
        cur  = data["current"]
        code = cur.get("weathercode", 0)
        desc = CODES_METEO.get(code, "conditions inconnues")
        temp = round(float(cur.get("temperature_2m", 0)))
        return f"À {nom_affiche}, il fait {temp} degrés et le ciel est {desc}. C'est tout."
    except Exception as e:
        print(f"[METEO] Erreur : {e}")
        return "Je n'arrive pas à récupérer la météo pour le moment."

def get_meteo_ha():
    """Lit la météo depuis Home Assistant. Fallback quand Gemini est KO."""
    _update_ha_env()
    try:
        r    = requests.get(f"{HA_URL}/api/states/weather.forecast_amilly", headers=HA_HEADERS, timeout=5)
        data = r.json()
        etat  = data.get("state", "inconnu")
        attrs = data.get("attributes", {})
        temp     = attrs.get("temperature", "?")
        humidite = attrs.get("humidity", None)
        vent     = attrs.get("wind_speed", None)
        etats_fr = {
            "sunny"          : "ensoleillé",
            "clear-night"    : "clair",
            "partlycloudy"   : "partiellement nuageux",
            "cloudy"         : "nuageux",
            "rainy"          : "pluvieux",
            "pouring"        : "forte pluie",
            "snowy"          : "neigeux",
            "snowy-rainy"    : "pluie et neige mêlées",
            "windy"          : "venteux",
            "windy-variant"  : "très venteux",
            "fog"            : "brumeux",
            "hail"           : "grêle",
            "lightning"      : "orageux",
            "lightning-rainy": "orage et pluie",
            "exceptional"    : "conditions exceptionnelles",
        }
        desc    = etats_fr.get(etat, etat)
        reponse = f"À {VILLE_PAR_DEFAUT}, il fait {temp} degrés et le ciel est {desc}"
        if humidite:
            reponse += f", humidité à {humidite}%"
        if vent:
            reponse += f", vent à {vent} km/h"
        reponse += f", {_charger_user_name()}."
        return reponse
    except Exception as e:
        print(f"[METEO HA] Erreur : {e}")
        return None

def get_alertes_meteo(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, _ = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon, nom_affiche = LAT_PAR_DEFAUT, LON_PAR_DEFAUT, VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily"   : "weathercode,precipitation_sum,wind_speed_10m_max",
                "timezone": "Europe/Paris", "forecast_days": 3,
            },
            timeout=8
        )
        data    = r.json()
        daily   = data["daily"]
        alertes = []
        for i in range(len(daily["weathercode"])):
            code  = daily["weathercode"][i]
            pluie = daily.get("precipitation_sum", [0]*3)[i] or 0
            vent  = daily.get("wind_speed_10m_max", [0]*3)[i] or 0
            jour  = ["aujourd hui", "demain", "apres-demain"][i]
            if code in [95, 96, 99]:
                alertes.append(f"Orage prevu {jour}")
            if code in [71, 73, 75, 85, 86]:
                alertes.append(f"Neige prevue {jour}")
            if pluie > 20:
                alertes.append(f"Fortes pluies {jour} ({pluie}mm)")
            if vent > 60:
                alertes.append(f"Vents forts {jour} ({vent} km/h)")
        if alertes:
            return f"Alertes meteo pour {nom_affiche} : " + ", ".join(alertes) + "."
        return f"Aucune alerte meteo pour {nom_affiche} dans les 3 prochains jours."
    except Exception as e:
        return f"Impossible de verifier les alertes meteo : {e}"


# ════════════════════════════════════════════════════════════════
#  NOUVEAUX SERVICES - DASHBOARD CENTRAL DE DOMOTIQUE
# ════════════════════════════════════════════════════════════════

def ha_get_all_states() -> list:
    """Récupère tous les états des entités de Home Assistant."""
    _update_ha_env()
    try:
        url = f"{HA_URL}/api/states"
        print(f"[HA] Récupération de tous les états depuis {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"[HA] Échec récupération états. Code : {r.status_code}")
            return []
    except Exception as e:
        print(f"[HA] Erreur lors de la récupération de tous les états : {e}")
        return []

def ha_get_etat_complet(entity_id: str) -> dict | None:
    """Récupère l'état complet d'une entité spécifique."""
    _update_ha_env()
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[HA] Erreur ha_get_etat_complet pour {entity_id} : {e}")
    return None

async def handle_ha_ws_message(data: dict, websocket, connected_clients: set) -> bool:
    """Gère les messages WebSocket liés à Home Assistant."""
    msg_type = data.get("type", "")

    if msg_type == "ha_get_states":
        states = await asyncio.to_thread(ha_get_all_states)
        await websocket.send(json.dumps({
            "type": "ha_states",
            "success": len(states) > 0 or HA_URL != "",
            "states": states
        }))
        return True

    elif msg_type == "ha_call_service":
        domain = data.get("domain", "")
        service = data.get("service", "")
        entity_id = data.get("entity_id", "")
        service_data = data.get("service_data", None)

        success = await asyncio.to_thread(ha_appeler_service, domain, service, entity_id, service_data)

        updated_state = None
        if success:
            updated_state = await asyncio.to_thread(ha_get_etat_complet, entity_id)

        await websocket.send(json.dumps({
            "type": "ha_service_result",
            "success": success,
            "entity_id": entity_id,
            "state": updated_state
        }))

        # Diffuser le changement d'état à tous les clients connectés pour synchroniser l'UI
        if success and updated_state:
            await _broadcast_ha(connected_clients, {
                "type": "ha_state_changed",
                "entity_id": entity_id,
                "state": updated_state
            })
        return True

    return False

async def _broadcast_ha(clients: set, message: dict):
    if not clients:
        return
    msg = json.dumps(message)
    try:
        await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
    except Exception as e:
        print(f"[HA-WS] Erreur broadcast : {e}")
