# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Assistant de configuration
========================================
Ce qu'on voit au premier lancement : ce que JARVIS peut faire, ce qu'on active,
et ce qu'il lui faut pour que ça marche.

DEUX MODES, UN SEUL CATALOGUE
La différence n'est pas deux listes : c'est le niveau d'exposition. Le mode
simple masque trois capacités et verrouille les garde-fous ; le mode avancé
montre tout. Les deux lisent `catalogue.CAPACITES`, donc une capacité ajoutée
apparaît des deux côtés sans rien recâbler.

CE QUI N'EST JAMAIS ENVOYÉ À LA PAGE
Les valeurs des clés. La page reçoit « GEMINI_API_KEY : renseignée » ou
« absente », jamais le contenu. Une interface qui affiche un secret finit par
le montrer dans une capture d'écran.

ON N'ÉCRASE PAS UNE CONFIGURATION EXISTANTE
Un champ laissé vide garde la valeur déjà en place. Sans ça, relancer
l'assistant pour changer une seule option effacerait tout le reste — et
c'est exactement ce qu'on fait après une mise à jour.

    venv\\Scripts\\python.exe installeur.py
"""

import io
import json
import os
import re
import sys
import threading

import config

RACINE = config.RACINE
PAGE = os.path.join(RACINE, "installeur", "page.html")

# ── Cerveaux : les modèles que JARVIS sait utiliser ──────────────────────
# Des clés d'API et Ollama, rien d'autre. Pas d'abonnement Claude ou Gemini :
# leurs conditions interdisent de les brancher dans un logiciel distribué, et
# le compte de l'utilisateur risquerait d'être suspendu.
# `id` = valeur de preferred_brain lue par main2 ; `test` = liste des modèles
# du fournisseur, qui répond 401/403 si la clé est mauvaise. La clé part
# dans un en-tête, jamais dans l'adresse (qui finit dans les journaux).
CERVEAUX = (
    {"id": "gemini", "nom": "Gemini (Google)", "variable": "GEMINI_API_KEY", "gratuit": True,
     "lien": "https://aistudio.google.com/apikey",
     "test": "https://generativelanguage.googleapis.com/v1beta/models",
     "entetes": {"x-goog-api-key": "{cle}"}},
    {"id": "groq", "nom": "Groq", "variable": "GROQ_API_KEY", "gratuit": True,
     "lien": "https://console.groq.com/keys",
     "test": "https://api.groq.com/openai/v1/models",
     "entetes": {"Authorization": "Bearer {cle}"}},
    {"id": "claude", "nom": "Claude (API Anthropic)", "variable": "ANTHROPIC_API_KEY", "gratuit": False,
     "lien": "https://console.anthropic.com/settings/keys",
     "test": "https://api.anthropic.com/v1/models",
     "entetes": {"x-api-key": "{cle}", "anthropic-version": "2023-06-01"}},
    {"id": "openai", "nom": "OpenAI", "variable": "OPENAI_API_KEY", "gratuit": False,
     "lien": "https://platform.openai.com/api-keys",
     "test": "https://api.openai.com/v1/models",
     "entetes": {"Authorization": "Bearer {cle}"}},
    {"id": "mistral", "nom": "Mistral", "variable": "MISTRAL_API_KEY", "gratuit": False,
     "lien": "https://console.mistral.ai/api-keys",
     "test": "https://api.mistral.ai/v1/models",
     "entetes": {"Authorization": "Bearer {cle}"}},
    {"id": "grok", "nom": "Grok (xAI)", "variable": "XAI_API_KEY", "gratuit": False,
     "lien": "https://console.x.ai",
     "test": "https://api.x.ai/v1/models",
     "entetes": {"Authorization": "Bearer {cle}"}},
)
OLLAMA = "http://127.0.0.1:11434/api/tags"


# ── Lecture / écriture du .env ───────────────────────────────────────────

def _fichier_env(racine=None):
    """Le chemin du .env. Parametrable pour que ce code soit testable ailleurs
    que sur l'installation reelle — RACINE est fige a l'import."""
    import pathlib
    return pathlib.Path(racine or RACINE) / ".env"


def _lire_env(racine=None):
    """{clé: valeur} du .env. Reste en mémoire, ne sort jamais d'ici."""
    chemin = _fichier_env(racine)
    valeurs = {}
    if not chemin.exists():
        return valeurs
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.rstrip("\n")
        if not ligne.strip() or ligne.lstrip().startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


# Deux clics presque ensemble (deux appels de la page, deux fils) liraient le même fichier et
# l'un effacerait l'ajout de l'autre : lecture, fusion et écriture se font à tour de rôle.
_VERROU_ENV = threading.Lock()


def _ecrire_env(nouvelles, racine=None):
    """
    Fusionne dans .env, sans rien perdre.

    Les lignes existantes sont modifiées sur place — commentaires, ordre et
    clés inconnues sont conservés. Un fichier réécrit de zéro perdrait tout
    ce que l'utilisateur y a mis à la main.
    """
    with _VERROU_ENV:
        chemin = _fichier_env(racine)
        lignes = (io.open(chemin, encoding="utf-8", errors="replace").read().splitlines()
                  if chemin.exists() else [])
        restantes = dict(nouvelles)
        sortie = []
        for ligne in lignes:
            m = re.match(r"^(\s*)([A-Z0-9_]+)(\s*)=(.*)$", ligne)
            if m and m.group(2) in restantes:
                cle = m.group(2)
                sortie.append("%s%s=%s" % (m.group(1), cle, restantes.pop(cle)))
            else:
                sortie.append(ligne)
        if restantes:
            sortie.append("")
            sortie.append("# Ajouté par l'assistant de configuration")
            for cle, valeur in restantes.items():
                sortie.append("%s=%s" % (cle, valeur))

        tmp = str(chemin) + ".tmp"
        io.open(tmp, "w", encoding="utf-8", newline="\n").write("\n".join(sortie) + "\n")
        os.replace(tmp, chemin)
    return len(nouvelles)


def _jeton_aleatoire(n=48):
    import secrets
    return secrets.token_urlsafe(n)[:n]


def _cle(variable):
    """Valeur d'une clé : le .env d'abord (l'assistant vient peut-être de
    l'écrire), puis l'environnement. Reste en mémoire, ne sort jamais d'ici."""
    return (_lire_env().get(variable) or os.environ.get(variable) or "").strip()


def _http(url, entetes=None, delai=8):
    """(code HTTP, corps). Code 0 : personne n'a répondu."""
    import urllib.error
    import urllib.request
    entetes = dict(entetes or {}, **{"User-Agent": "JARVIS-installeur"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=entetes),
                                    timeout=delai) as r:
            return r.status, r.read(500000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def _fichier_config():
    """jarvis_config.json, où main2 range preferred_brain (à côté de main2.py)."""
    return os.path.join(str(RACINE), "jarvis_config.json")


def _lire_config():
    """Le dict de jarvis_config.json. Lève une erreur s'il est illisible :
    l'écrire par-dessus effacerait les réglages qu'il contient."""
    chemin = _fichier_config()
    if not os.path.exists(chemin):
        return {}
    cfg = json.load(io.open(chemin, encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("jarvis_config.json ne contient pas un objet")
    return cfg


# ── L'API vue par la page ────────────────────────────────────────────────

class Api:
    """Tout ce que la page peut demander. Rien de plus."""

    def __init__(self):
        # Avec un « _ » devant : pywebview parcourt TOUS les attributs publics de l'objet qu'on lui donne,
        # y compris les objets, en profondeur. La fenêtre y est un objet .NET dont chaque propriété en
        # renvoie un neuf (Bounds.Empty.Empty…) : le parcours ne finissait jamais et la page n'avait pas
        # son API (visite du 16/11, pywebview 6.2.1). Un attribut en « _ » est ignoré.
        self._fenetre = None
        self.termine = False

    # -- lecture --------------------------------------------------------
    def donnees(self, mode="simple"):
        import catalogue
        import garde_fous
        presentes = _lire_env()
        reglages = []
        for variables, present, requis, role, source in config.configuration():
            reglages.append({
                "variables": list(variables),
                # PRÉSENCE, jamais la valeur.
                "renseigne": bool(present),
                "requis": bool(requis),
                "role": role,
                "source": source,
            })
        return {
            "version": config.VERSION,
            "systeme": config.SYSTEME,
            "premier": config.premier_demarrage(),
            "capacites": catalogue.catalogue(mode),
            "reglages": reglages,
            "gardes": garde_fous.etat(mode),
            "degradees": [{"nom": n, "manque": m}
                          for n, m in config.fonctionnalites_indisponibles()],
            "a_deja_un_jeton": bool(presentes.get("JARVIS_ACCESS_TOKEN")),
        }

    # -- écriture -------------------------------------------------------
    def enregistrer(self, mode, capacites, reglages, gardes_a_retirer=None):
        """
        Applique la configuration. Renvoie un compte rendu, jamais une valeur.

        Un réglage vide n'efface RIEN : il signifie « garde ce qui est là ».
        """
        import catalogue
        import garde_fous

        a_ecrire = {}
        for cle, valeur in (reglages or {}).items():
            valeur = (valeur or "").strip()
            if not valeur:
                continue                      # vide = inchangé
            if not re.match(r"^[A-Z0-9_]+$", cle):
                continue                      # nom de variable douteux : ignoré
            a_ecrire[cle] = valeur

        # Le jeton d'accès n'a pas à être inventé par l'utilisateur : c'est
        # une chaîne aléatoire, et lui en demander une donne des « jarvis123 ».
        if not _lire_env().get("JARVIS_ACCESS_TOKEN") and "JARVIS_ACCESS_TOKEN" not in a_ecrire:
            a_ecrire["JARVIS_ACCESS_TOKEN"] = _jeton_aleatoire()
            jeton_genere = True
        else:
            jeton_genere = False

        ecrits = _ecrire_env(a_ecrire) if a_ecrire else 0
        retenues, refusees = catalogue.definir_activees(capacites or [], mode=mode)

        gardes_retires, gardes_refuses = [], []
        for cle in (gardes_a_retirer or []):
            g = garde_fous.GARDES.get(cle)
            if not g:
                continue
            fait, message = garde_fous.desactiver(cle, g["phrase"], mode=mode)
            (gardes_retires if fait else gardes_refuses).append(
                cle if fait else "%s : %s" % (cle, message))

        return {
            "ok": True,
            "reglages_ecrits": ecrits,
            "jeton_genere": jeton_genere,
            "capacites": retenues,
            "capacites_refusees": refusees,
            "gardes_retires": gardes_retires,
            "gardes_refuses": gardes_refuses,
        }

    def verifier_cle(self, nom, valeur):
        """Contrôle de forme, pas de validité. On ne teste pas la clé en ligne."""
        valeur = (valeur or "").strip()
        if not valeur:
            return {"ok": True, "message": ""}
        if len(valeur) < 12:
            return {"ok": False, "message": "Cette clé semble trop courte."}
        if valeur.startswith(("http://", "https://")) and not nom.endswith("_URL"):
            return {"ok": False, "message": "C'est une adresse, pas une clé."}
        if re.search(r"\s", valeur):   # un retour à la ligne casserait le .env
            return {"ok": False, "message": "Une clé ne contient pas d'espace."}
        return {"ok": True, "message": ""}

    # -- cerveaux -------------------------------------------------------
    def cerveaux(self):
        """Ce qui est déjà là : clés présentes (jamais leur valeur), Ollama,
        OmniRoute, et le cerveau préféré actuel."""
        cles = [{"id": c["id"], "nom": c["nom"], "variable": c["variable"],
                 "gratuit": c["gratuit"], "lien": c["lien"],
                 # 12 caractères au moins, comme verifier_cle : un modèle de fichier de réglages
                 # (« votre_cle ») n'est pas une clé, et ne doit pas faire croire qu'un cerveau est prêt.
                 "presente": len(_cle(c["variable"])) >= 12} for c in CERVEAUX]
        code, corps = _http(OLLAMA, delai=1.5)
        try:
            modeles = [m["name"] for m in json.loads(corps)["models"]] if code == 200 else []
        except Exception:
            modeles = []
        # Même adresse que main2 : un routeur local compatible OpenAI. Un 401
        # veut dire qu'il est là mais protégé : il compte.
        omni = os.getenv("EXTRA_LLM_1_URL", "http://localhost:20128/v1").rstrip("/")
        try:
            actuel = _lire_config().get("preferred_brain", "auto")
        except Exception:
            actuel = "auto"
        return {
            "cles": cles,
            "ollama": {"actif": code == 200, "modeles": modeles[:12]},
            "omniroute": _http(omni + "/models", delai=1.5)[0] != 0,
            "actuel": actuel,
        }

    def tester_cle(self, nom, valeur=""):
        """Demande au fournisseur si la clé marche. Valeur vide = la clé déjà
        enregistrée. Le message ne contient jamais la clé."""
        c = next((c for c in CERVEAUX if c["variable"] == nom), None)
        if not c:
            return {"ok": False, "message": "Clé inconnue."}
        cle = (valeur or "").strip() or _cle(nom)
        if not cle:
            return {"ok": False, "message": "Aucune clé à tester."}
        code, _ = _http(c["test"], {k: v.format(cle=cle) for k, v in c["entetes"].items()})
        if code == 200:
            return {"ok": True, "code": code, "message": "La clé marche."}
        if code in (400, 401, 403):
            return {"ok": False, "code": code,
                    "message": "%s refuse cette clé (HTTP %d)." % (c["nom"], code)}
        return {"ok": False, "code": code,
                "message": "Pas de réponse claire de %s (%s)."
                           % (c["nom"], "HTTP %d" % code if code else "hors ligne ?")}

    def ajouter_cle(self, nom, valeur):
        """Range une clé de cerveau dans le .env après l'avoir essayée. Refusée
        seulement si le fournisseur dit non : hors ligne, on l'enregistre quand
        même plutôt que de bloquer l'installation."""
        valeur = (valeur or "").strip()
        if not any(c["variable"] == nom for c in CERVEAUX):
            return {"ok": False, "message": "Clé inconnue."}
        if not valeur:
            return {"ok": True, "message": ""}          # vide = on garde l'existante
        forme = self.verifier_cle(nom, valeur)
        if not forme["ok"]:
            return forme
        essai = self.tester_cle(nom, valeur)
        if essai.get("code") in (400, 401, 403):
            return {"ok": False, "message": essai["message"] + " Non enregistrée."}
        _ecrire_env({nom: valeur})
        return {"ok": True, "message": "Clé enregistrée et vérifiée." if essai["ok"]
                else "Clé enregistrée, sans vérification : " + essai["message"]}

    def choisir_cerveau(self, nom):
        """preferred_brain dans jarvis_config.json, sans toucher aux autres
        réglages. `claude_cli` (l'abonnement) n'est jamais proposé ici."""
        if nom not in {"auto", "omniroute"} | {c["id"] for c in CERVEAUX}:
            return {"ok": False, "message": "Choix inconnu."}
        try:
            cfg = _lire_config()
        except Exception:
            return {"ok": False, "message": "jarvis_config.json est illisible : rien n'a été modifié."}
        cfg["preferred_brain"] = nom
        tmp = _fichier_config() + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        os.replace(tmp, _fichier_config())
        return {"ok": True, "message": ""}

    def ouvrir(self, url):
        """Ouvre une page d'aide dans le navigateur du système."""
        import webbrowser
        webbrowser.open(url, new=2)
        return True

    def terminer(self):
        self.termine = True
        try:
            self._fenetre.destroy()
        except Exception:
            pass
        return True


def lancer():
    """Ouvre l'assistant. Renvoie True s'il est allé au bout."""
    try:
        import webview
    except ImportError:
        print("  pywebview n'est pas installé : assistant graphique indisponible.")
        return False
    if not os.path.exists(PAGE):
        print("  page introuvable : %s" % PAGE)
        return False

    api = Api()
    fenetre = webview.create_window(
        title="Configuration de J.A.R.V.I.S",
        url="file:///" + PAGE.replace("\\", "/"),
        width=980, height=720, min_size=(820, 600),
        background_color="#0B0D12",   # fond sombre de l'Orbe de verre
        js_api=api,
    )
    api._fenetre = fenetre
    webview.start(private_mode=False)
    return api.termine


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--donnees" in sys.argv:
        import json
        print(json.dumps(Api().donnees("avance"), ensure_ascii=False, indent=2)[:1800])
    else:
        lancer()
