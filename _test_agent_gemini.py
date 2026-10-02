# -*- coding: utf-8 -*-
"""
Verifie agent_gemini.py avec les VRAIES classes du SDK google-genai, sans
reseau : conversion de l'historique, lecture des reponses, et la config
envoyee (outils declares, appel automatique desactive, delai HTTP).

    venv\\Scripts\\python.exe _test_agent_gemini.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from google.genai import types

import agent_fichiers as af
import agent_gemini as ag

echecs = []


def verifier(libelle, condition, detail=None):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        if detail is not None:
            print("      ->", repr(detail)[:300])
        echecs.append(libelle)


def reponse(*parts, finish=None):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(parts)), finish_reason=finish)])


# ── Historique neutre -> Content Gemini ──────────────────────────────────
brut = types.Content(role="model", parts=[
    types.Part(function_call=types.FunctionCall(id="a", name="lister", args={"chemin": "."}),
               thought_signature=b"SIGNATURE"),
    types.Part(function_call=types.FunctionCall(id="b", name="lire", args={"chemin": "x.py"}))])
histo = [
    {"role": "user", "texte": "TÂCHE : x"},
    {"role": "assistant", "texte": "", "appels": [], "brut": brut},
    {"role": "outil", "id": "a", "nom": "lister", "resultat": "README.md"},
    {"role": "outil", "id": "b", "nom": "lire", "resultat": "1\tcode"},
    {"role": "assistant", "texte": "ok", "appels": [{"id": "c", "nom": "terminer", "args": {"resume": "fin"}}], "brut": None},
]
c = ag.contenus_gemini(types, histo)
verifier("un Content par message, les 2 resultats d'outils regroupes en UN seul", len(c) == 4, [x.role for x in c])
verifier("le tour utilisateur porte la tache", c[0].role == "user" and c[0].parts[0].text == "TÂCHE : x")
verifier("le contenu BRUT du modele est renvoye tel quel (signature de pensee intacte)",
         c[1] is brut and c[1].parts[0].thought_signature == b"SIGNATURE")
verifier("2 appels paralleles -> 2 reponses d'outil dans le MEME message, dans l'ordre",
         c[2].role == "user" and [p.function_response.name for p in c[2].parts] == ["lister", "lire"]
         and c[2].parts[0].function_response.response == {"resultat": "README.md"}
         and c[2].parts[0].function_response.id == "a")
verifier("sans brut : l'assistant est reconstruit (texte + function_call)",
         c[3].role == "model" and c[3].parts[0].text == "ok" and c[3].parts[1].function_call.name == "terminer"
         and c[3].parts[1].function_call.args == {"resume": "fin"})
verifier("historique vide -> liste vide", ag.contenus_gemini(types, []) == [])

# ── Lecture des reponses ─────────────────────────────────────────────────
lu = ag.lire_reponse(reponse(types.Part(text="je regarde"),
                             types.Part(function_call=types.FunctionCall(id="z", name="lire", args={"chemin": "a.py", "debut": 2.0}))))
verifier("texte + appel lus, args en dict", lu["texte"] == "je regarde" and lu["appels"] == [
    {"id": "z", "nom": "lire", "args": {"chemin": "a.py", "debut": 2.0}}], lu)
verifier("le brut est conserve", isinstance(lu["brut"], types.Content))
lu = ag.lire_reponse(reponse(types.Part(text="pensee interne", thought=True), types.Part(text="reponse")))
verifier("les parties de PENSEE ne sont pas prises pour la reponse", lu["texte"] == "reponse", lu)
lu = ag.lire_reponse(reponse(types.Part(function_call=types.FunctionCall(name="terminer", args={"resume": "ok"}))))
verifier("appel sans id accepte (id None)", lu["appels"][0]["id"] is None and lu["appels"][0]["nom"] == "terminer")
for libelle, rep in (
        ("aucun candidat", types.GenerateContentResponse(candidates=[])),
        ("contenu absent", types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="MALFORMED_FUNCTION_CALL")])),
        ("aucune partie", reponse(finish="SAFETY"))):
    try:
        ag.lire_reponse(rep)
        verifier("reponse vide/bloquee leve une erreur (%s)" % libelle, False)
    except RuntimeError as e:
        verifier("reponse vide/bloquee leve une erreur qui NOMME la raison (%s)" % libelle,
                 "sans contenu" in str(e), str(e))

# ── Le modele fabrique : ce qu'il envoie a Gemini ────────────────────────
class FauxClient:
    def __init__(self, sorties):
        self.sorties, self.appels = list(sorties), []
        self.models = self

    def generate_content(self, **kw):
        self.appels.append(kw)
        s = self.sorties.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


vus = {"suivi": [], "erreurs": []}
client = FauxClient([reponse(types.Part(function_call=types.FunctionCall(name="lister", args={}))),
                     ConnectionError("reseau")])
modele = ag.creer_modele(client, types, "gemini-test", suivi=vus["suivi"].append, sur_erreur=vus["erreurs"].append, delai_ms=12345)
res = modele(af.SYSTEME, [{"role": "user", "texte": "t"}], af.DECLARATIONS)
kw = client.appels[0]
cfg = kw["config"]
verifier("le modele choisi et l'historique sont transmis", kw["model"] == "gemini-test" and len(kw["contents"]) == 1)
verifier("la consigne systeme est transmise", cfg.system_instruction == af.SYSTEME)
noms = [d.name for d in cfg.tools[0].function_declarations]
verifier("les 7 outils sont declares, avec leur schema", noms == [d["nom"] for d in af.DECLARATIONS]
         and cfg.tools[0].function_declarations[1].parameters_json_schema["required"] == ["chemin"], noms)
verifier("l'appel automatique de fonctions est DESACTIVE (c'est le bac a sable qui execute)",
         cfg.automatic_function_calling.disable is True)
verifier("delai HTTP borne", cfg.http_options.timeout == 12345)
verifier("resultat normalise + suivi appele", res["appels"][0]["nom"] == "lister" and len(vus["suivi"]) == 1)
try:
    modele(af.SYSTEME, [{"role": "user", "texte": "t"}], af.DECLARATIONS)
    verifier("une erreur du SDK remonte", False)
except ConnectionError:
    verifier("une erreur du SDK remonte, apres avoir ete signalee a sur_erreur", len(vus["erreurs"]) == 1)

def suivi_qui_plante(rep):
    raise ValueError("le suivi ne doit jamais casser l'appel")
client2 = FauxClient([reponse(types.Part(text="ok"))])
res = ag.creer_modele(client2, types, "m", suivi=suivi_qui_plante)(af.SYSTEME, [{"role": "user", "texte": "t"}], af.DECLARATIONS)
verifier("un suivi qui plante n'empeche pas la reponse", res["texte"] == "ok")

# ── De bout en bout : la vraie boucle + les vraies classes, faux reseau ──
import os, shutil, tempfile
racine = tempfile.mkdtemp(prefix="jarvis_test_gem_")
try:
    with open(os.path.join(racine, "a.py"), "w") as f:
        f.write("x = 1\n")
    client3 = FauxClient([
        reponse(types.Part(function_call=types.FunctionCall(id="1", name="lire", args={"chemin": "a.py"}))),
        reponse(types.Part(function_call=types.FunctionCall(id="2", name="remplacer", args={"chemin": "a.py", "ancien": "x = 1", "nouveau": "x = 2"})),
                types.Part(function_call=types.FunctionCall(id="3", name="verifier", args={"chemin": "a.py"}))),
        reponse(types.Part(function_call=types.FunctionCall(id="4", name="terminer", args={"resume": "x vaut 2. Rien n'a ete execute."}))),
    ])
    bilan = af.executer_agent(racine, "mets x a 2", ag.creer_modele(client3, types, "m"), pause=lambda s: None)
    verifier("boucle + adaptateur : tache faite avec les vraies classes du SDK",
             bilan["succes"] and open(os.path.join(racine, "a.py")).read() == "x = 2\n" and bilan["tours"] == 3, bilan)
    dernier = client3.appels[-1]["contents"]
    verifier("le 3e appel renvoie a Gemini les reponses d'outils GROUPEES (2 appels paralleles -> 1 message a 2 parties)",
             dernier[-1].role == "user" and len(dernier[-1].parts) == 2
             and [p.function_response.name for p in dernier[-1].parts] == ["remplacer", "verifier"], [x.role for x in dernier])
finally:
    shutil.rmtree(racine, ignore_errors=True)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Adaptateur Gemini de l'agent de fichiers : conforme.")
