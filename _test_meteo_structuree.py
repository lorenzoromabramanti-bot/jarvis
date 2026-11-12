# -*- coding: utf-8 -*-
"""Carte météo de l'Orbe de verre : get_meteo_structuree() rend les heures, la pluie et le mini/maxi,
et reste utilisable (température du moment) quand l'API ne les donne pas."""
import ha_config

ECHECS = []


def verifier(nom, ok):
    print(("  OK  " if ok else "  ÉCHEC  ") + nom)
    if not ok:
        ECHECS.append(nom)


class _Reponse:
    def __init__(self, donnees):
        self._d = donnees

    def json(self):
        return self._d


def _appeler(donnees):
    ha_config.geocoder_ville = lambda ville: (48.85, 2.35, "Paris", "FR")
    ha_config.requests.get = lambda *a, **k: _Reponse(donnees)
    return ha_config.get_meteo_structuree("Paris")


HEURES = [f"2026-11-12T{h:02d}:00" for h in range(24)] + [f"2026-11-13T{h:02d}:00" for h in range(24)]
COMPLET = {
    "current": {"time": "2026-11-12T20:15", "temperature_2m": 14.4, "apparent_temperature": 13.6,
                "relative_humidity_2m": 80, "wind_speed_10m": 9.2, "weathercode": 3},
    "hourly": {"time": HEURES, "temperature_2m": [10 + (i % 24) * 0.25 for i in range(48)],
               "precipitation_probability": [None if i == 22 else 3 for i in range(48)]},
    "daily": {"temperature_2m_max": [16.4, 12.0], "temperature_2m_min": [10.5, 9.0]},
}

m = _appeler(COMPLET)
verifier("température et description du moment", m["temperature"] == 14 and m["description"])
verifier("10 prochaines heures, la première est l'heure en cours", len(m["heures"]) == 10 and m["heures"][0]["h"] == 20)
verifier("les heures passent minuit sans se répéter", [x["h"] for x in m["heures"]] == [20, 21, 22, 23, 0, 1, 2, 3, 4, 5])
verifier("pluie = maximum des 6 prochaines heures, valeurs vides ignorées", m["pluie"] == 3)
verifier("mini et maxi du jour", (m["mini"], m["maxi"]) == (10, 16))

m = _appeler({"current": COMPLET["current"]})
verifier("sans prévisions : la température du moment suffit", m["temperature"] == 14 and "heures" not in m)

m = _appeler({"current": {**COMPLET["current"], "time": "2026-11-12T20:15"}, "hourly": {"time": HEURES[:2],
              "temperature_2m": [1, 2], "precipitation_probability": [0, 0]}, "daily": {}})
verifier("prévisions incomplètes : ni plantage ni champs à moitié remplis", m["temperature"] == 14 and "mini" not in m)

print("\nMétéo structurée : " + ("conforme." if not ECHECS else f"{len(ECHECS)} échec(s)."))
raise SystemExit(1 if ECHECS else 0)
