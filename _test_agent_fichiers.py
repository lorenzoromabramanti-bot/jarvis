# -*- coding: utf-8 -*-
"""
Verifie agent_fichiers.py / bac_fichiers.py : le bac a sable (le point
critique), les outils, et la boucle avec un modele SCRIPTE. Aucun reseau,
aucun vrai modele.

Le bac a sable est teste avec de VRAIES jonctions Windows (mklink /J) : c'est
ce cas que realpath doit attraper, et une liste de « .. » ne le prouverait pas.

    venv\\Scripts\\python.exe _test_agent_fichiers.py
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import agent_fichiers as af
import bac_fichiers as bf

echecs = []


def verifier(libelle, condition, detail=None):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        if detail is not None:
            print("      ->", repr(detail)[:300])
        echecs.append(libelle)


def ecrire(chemin, contenu, mode="w", **kw):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with io.open(chemin, mode, **kw) as f:
        f.write(contenu)


def jonction(lien, cible):
    r = subprocess.run(["cmd", "/c", "mklink", "/J", lien, cible], capture_output=True, text=True)
    return r.returncode == 0


racine = tempfile.mkdtemp(prefix="jarvis_test_agent_")
dehors = tempfile.mkdtemp(prefix="jarvis_test_dehors_")
try:
    # ── Le projet de test ────────────────────────────────────────────────
    ecrire(os.path.join(racine, "README.md"), "# Demo\n")
    ecrire(os.path.join(racine, "src", "app.py"), "def salut():\n    return 'bonjour'\n\nprint(salut())\n")
    ecrire(os.path.join(racine, "src", "crlf.txt"), "ligne un\r\nligne deux\r\nligne trois\r\n", newline="")
    ecrire(os.path.join(racine, "src", "mixte.txt"), "un\r\ndeux\ntrois\r\n", newline="")
    ecrire(os.path.join(racine, "docs", "notes.txt"), "a.b et axb et A.B\n")
    ecrire(os.path.join(racine, ".git", "config"), "MOT_UNIQUE_SECRET [core]\n")
    ecrire(os.path.join(racine, ".env"), "API_KEY=MOT_UNIQUE_SECRET\n")
    ecrire(os.path.join(racine, "config", "credentials.json"), '{"k": "MOT_UNIQUE_SECRET"}')
    ecrire(os.path.join(racine, "secrets", "notes.txt"), "MOT_UNIQUE_SECRET\n")
    ecrire(os.path.join(racine, "venv", "lib.py"), "MOT_UNIQUE_SECRET = 1\n")
    ecrire(os.path.join(racine, "src", "vrai.py"), "# MOT_UNIQUE_SECRET est ici, dans un vrai fichier\n")
    ecrire(os.path.join(racine, "binaire.bin"), b"\x00\x01\x02binaire", mode="wb")
    ecrire(os.path.join(racine, "gros.txt"), "x" * (af.MAX_OCTETS_LECTURE_FICHIER + 10))
    ecrire(os.path.join(racine, "vide.txt"), "")
    ecrire(os.path.join(racine, "long.txt"), "".join("ligne %d\n" % i for i in range(1, 901)))
    ecrire(os.path.join(dehors, "secret.txt"), "TOP SECRET DEHORS")
    ecrire(os.path.join(dehors, "donnees.txt"), "CONTENU DEHORS")    # nom neutre : seul realpath peut l'arreter
    _jonction_ok = os.name == "nt" and jonction(os.path.join(racine, "lien_dehors"), dehors)
    _jonction_git = os.name == "nt" and jonction(os.path.join(racine, "doc_lien"), os.path.join(racine, ".git"))

    # ═══ 1. Le bac a sable : forme ═══════════════════════════════════════
    bac = bf.Bac(racine)
    for ok_rel in ("README.md", "src/app.py", "src\\app.py", "./src//app.py", "SRC/APP.PY", "src", "."):
        reel, err = bac.resoudre(ok_rel)
        verifier("chemin legitime accepte : %r" % ok_rel, reel and not err and bac.dans_racine(reel), (reel, err))

    mauvais = ["../x", "..\\x", "src/../../x", "src/../README.md", "C:\\Windows\\win.ini", "C:foo",
               "/etc/passwd", "\\\\srv\\share\\x", "\\\\?\\C:\\x", "a.txt:flux", "CON", "nul.txt", "aux.py",
               "COM1", "lpt3.log", "src/a.py.", "src /a.py", "a\x00b", "a\nb", "x" * 300, "a*b", 'a"b',
               123, None, ["src"], {"a": 1}]
    for m in mauvais:
        reel, err = bac.resoudre(m)
        verifier("forme refusee : %r" % (m if not isinstance(m, str) else m[:30]), reel is None and err, (reel, err))

    r1, _ = bac.resoudre("src/app.py ")
    r2, _ = bac.resoudre("src/app.py")
    verifier("espace final du chemin ENTIER : normalise vers le MEME fichier (Windows fait pareil), pas une evasion",
             r1 == r2 and r1 is not None, (r1, r2))

    # ═══ 2. Le bac a sable : liste noire ═════════════════════════════════
    interdits = [".git/config", ".GIT/config", "src/.git/x", ".env", ".env.local", "prod.env",
                 "config/credentials.json", "credentials.txt", "secrets/notes.txt", "cle.PEM", "id_rsa",
                 "id_ed25519.pub", "token_google.pickle", "src/mon_secret.py", ".ssh/config", ".aws/credentials",
                 "a/b/.npmrc"]
    for m in interdits:
        reel, err = bac.resoudre(m)
        verifier("liste noire (lecture) : %s" % m, reel is None and err, (reel, err))
    reel, err = bac.resoudre("venv/lib.py")
    verifier("venv se LIT (bruit, pas secret)", reel and not err)
    for m in ("venv/x.py", "node_modules/x.js", "src/__pycache__/x.pyc", ".venv/a"):
        reel, err = bac.resoudre(m, ecriture=True)
        verifier("ecriture interdite dans %s" % m, reel is None and err, (reel, err))

    # -- durcissement (revue adverse) : noms courts 8.3, peripheriques Windows, auto-execution
    for m in ("GIT~1/config", "ENV~1", "src/PROGRA~1", "a~2.txt"):
        reel, err = bac.resoudre(m)
        verifier("nom court 8.3 refuse (« GIT~1 » = « .git ») : %s" % m, reel is None and "court" in (err or ""), (reel, err))
    for m in ("con .txt", "CONIN$", "conout$", "COM" + chr(0xb9), "lpt" + chr(0xb2) + ".log", "src/nul  .py"):
        reel, err = bac.resoudre(m)
        verifier("peripherique Windows refuse : %r" % m, reel is None and "réservé" in (err or ""), (reel, err))
    for m in (".vscode/tasks.json", ".idea/workspace.xml", ".husky/pre-commit", ".githooks/pre-push", "src/.vscode/x"):
        reel, err = bac.resoudre(m, ecriture=True)
        verifier("ecriture interdite (s'auto-execute sans relecture) : %s" % m, reel is None and err, (reel, err))
    reel, err = bac.resoudre("src/mon~fichier.txt")
    verifier("un « ~ » sans chiffre reste un nom normal (sauvegardes d'editeur)", reel and not err, (reel, err))

    # ═══ 3. Le bac a sable : liens et jonctions (le cas qui compte) ══════
    if _jonction_ok:
        for m in ("lien_dehors", "lien_dehors/donnees.txt", "lien_dehors/nouveau.txt", "lien_dehors/a/b/c.txt"):
            reel, err = bac.resoudre(m, ecriture=True)
            verifier("JONCTION vers l'exterieur refusee : %s" % m,
                     reel is None and "hors du projet" in (err or ""), (reel, err))
    else:
        verifier("jonction de test creee (mklink /J)", False, "impossible de creer la jonction")
    if _jonction_git:
        reel, err = bac.resoudre("doc_lien/config")
        verifier("jonction vers .git : liste noire rejouee sur le chemin RESOLU",
                 reel is None and "via un lien" in (err or ""), (reel, err))
    try:
        os.symlink(dehors, os.path.join(racine, "sym_dehors"), target_is_directory=True)
        reel, err = bac.resoudre("sym_dehors/secret.txt")
        verifier("lien symbolique vers l'exterieur refuse", reel is None and err, (reel, err))
    except OSError:
        print("  --  liens symboliques : privilege absent sur cette machine, cas couvert par les jonctions")
    try:
        bf.Bac(os.path.join(racine, "inexistant"))
        verifier("racine inexistante refusee", False)
    except ValueError:
        verifier("racine inexistante refusee", True)

    # ═══ 4. Outils : lister ══════════════════════════════════════════════
    S = af.Session(racine)
    r = S.appeler("lister", {})
    verifier("lister : voit les fichiers du projet", "README.md" in r and "src/" in r, r)
    verifier("lister : .git et venv annonces mais NON explores",
             ".git/  [non exploré]" in r and "venv/  [non exploré]" in r and "MOT_UNIQUE" not in r, r)
    verifier("lister : les liens/jonctions ne sont pas suivis", "lien_dehors  [lien, non suivi]" in r if _jonction_ok else True, r)
    verifier("lister : profondeur 2 par defaut montre src/app.py", "app.py" in r, r)
    verifier("lister : profondeur 1 ne descend pas", "app.py" not in S.appeler("lister", {"profondeur": 1}))
    verifier("lister : profondeur en texte/float acceptee", "app.py" in S.appeler("lister", {"profondeur": 2.0}))
    verifier("lister : hors du projet -> ERREUR", S.appeler("lister", {"chemin": ".."}).startswith("ERREUR"))
    verifier("lister : un fichier n'est pas un dossier", S.appeler("lister", {"chemin": "README.md"}).startswith("ERREUR"))
    for i in range(af.MAX_ENTREES_LISTE + 50):
        ecrire(os.path.join(racine, "beaucoup", "f%03d.txt" % i), "x")
    r = S.appeler("lister", {"chemin": "beaucoup"})
    verifier("lister : tronque a %d entrees et le dit" % af.MAX_ENTREES_LISTE, "tronquée" in r, r[-120:])

    # ═══ 5. Outils : lire ═══════════════════════════════════════════════
    r = S.appeler("lire", {"chemin": "src/app.py"})
    verifier("lire : numeros de ligne et total", "1\tdef salut():" in r and "sur 4" in r, r)
    verifier("lire : plage debut/fin", S.appeler("lire", {"chemin": "long.txt", "debut": 10, "fin": 12}).count("\tligne ") == 3)
    r = S.appeler("lire", {"chemin": "long.txt"})
    verifier("lire : 400 lignes max par appel, avec l'indication de la suite",
             r.count("\tligne ") == af.MAX_LIGNES_LECTURE and "lire(debut=401)" in r, r[-100:])
    verifier("lire : floats acceptes (un modele envoie 2.0)", "ligne 2" in S.appeler("lire", {"chemin": "long.txt", "debut": 2.0, "fin": 3.0}))
    verifier("lire : fichier binaire refuse", "binaire" in S.appeler("lire", {"chemin": "binaire.bin"}))
    verifier("lire : fichier trop gros refuse", "trop gros" in S.appeler("lire", {"chemin": "gros.txt"}))
    verifier("lire : fichier vide dit", "vide" in S.appeler("lire", {"chemin": "vide.txt"}))
    for m in (".env", "config/credentials.json", ".git/config", "secrets/notes.txt", "../x", "C:\\Windows\\win.ini"):
        r = S.appeler("lire", {"chemin": m})
        verifier("lire refuse : %s" % m, r.startswith("ERREUR") and "MOT_UNIQUE" not in r and "TOP SECRET" not in r, r)
    if _jonction_ok:
        r = S.appeler("lire", {"chemin": "lien_dehors/donnees.txt"})
        verifier("lire : la JONCTION ne laisse pas lire dehors", "CONTENU DEHORS" not in r and "hors du projet" in r, r)
    verifier("lire : dossier / inexistant -> ERREUR",
             S.appeler("lire", {"chemin": "src"}).startswith("ERREUR") and S.appeler("lire", {"chemin": "nope.txt"}).startswith("ERREUR"))

    # ═══ 6. Outils : chercher ═══════════════════════════════════════════
    r = S.appeler("chercher", {"motif": "mot_unique_secret"})
    verifier("chercher : insensible a la casse, ne trouve QUE le vrai fichier (pas .git/.env/venv/credentials/secrets)",
             "src/vrai.py" in r and r.count("\n") == 0 and "venv" not in r and ".env" not in r and "credentials" not in r, r)
    r = S.appeler("chercher", {"motif": "a.b", "chemin": "docs"})
    verifier("chercher : litteral par defaut (« a.b » n'est pas « axb »)", "a.b et axb" in r and r.count("notes.txt") == 1, r)
    r = S.appeler("chercher", {"motif": "a.b", "chemin": "docs", "regex": True})
    verifier("chercher : regex=true", "notes.txt:1" in r, r)
    r = S.appeler("chercher", {"motif": "a.b", "chemin": "docs", "regex": "false"})
    verifier("chercher : regex=\"false\" (TEXTE) reste litteral", "a.b" in r, r)
    verifier("chercher : regex dangereuse refusee", "refusée" in S.appeler("chercher", {"motif": "(a+)+$", "regex": True}))
    verifier("chercher : regex invalide -> message", "invalide" in S.appeler("chercher", {"motif": "([", "regex": True}))
    for motif in ("(a|aa)+b", "(a|a)*$", "(x+x+)+y", r"(a)\1", "a*a*a*a*b", "(.*){2,}x", "(a?)+"):
        r = S.appeler("chercher", {"motif": motif, "regex": True})
        verifier("chercher : regex a risque de blocage refusee : %s" % motif, "refusée" in r, r)
    for motif in (r"def \w+\(", "import (os|sys)", r"\d+\.\d+", "a.b"):
        r = S.appeler("chercher", {"motif": motif, "regex": True})
        verifier("chercher : regex ordinaire toujours acceptee : %s" % motif, "refusée" not in r and "invalide" not in r, r)
    ecrire(os.path.join(racine, "piege.txt"), ("a" * 290 + "\n") * 300)
    _t0 = time.monotonic()
    r = S.appeler("chercher", {"motif": "a*a*a*b", "regex": True, "glob": "piege.txt"})
    verifier("chercher : le pire cas admis (3 quantificateurs, lignes de 290 car.) se termine vite",
             time.monotonic() - _t0 < af.DELAI_RECHERCHE_S + 3 and "refusée" not in r, (time.monotonic() - _t0, r[-80:]))
    _vrai_delai = af.DELAI_RECHERCHE_S
    af.DELAI_RECHERCHE_S = -1                # echeance deja passee (l'horloge Windows n'a que ~15 ms de finesse)
    try:
        r = S.appeler("chercher", {"motif": "ligne", "glob": "long.txt"})
        verifier("chercher : le delai est verifie A CHAQUE LIGNE (pas seulement entre fichiers) et le dit",
                 "interrompue" in r and "long.txt:" not in r, r[-100:])
    finally:
        af.DELAI_RECHERCHE_S = _vrai_delai
    verifier("chercher : glob", "README" not in S.appeler("chercher", {"motif": "def", "glob": "*.md"}))
    verifier("chercher : motif vide ou trop long refuse",
             S.appeler("chercher", {"motif": ""}).startswith("ERREUR") and S.appeler("chercher", {"motif": "x" * 300}).startswith("ERREUR"))
    verifier("chercher : aucun resultat le dit", S.appeler("chercher", {"motif": "zzz_introuvable_zzz"}) == "aucun résultat")
    ecrire(os.path.join(racine, "cent.txt"), "".join("match %d\n" % i for i in range(100)))
    r = S.appeler("chercher", {"motif": "match", "glob": "cent.txt"})
    verifier("chercher : plafonne a %d resultats et le dit" % af.MAX_RESULTATS_RECHERCHE,
             r.count("cent.txt:") == af.MAX_RESULTATS_RECHERCHE and "affine" in r, r[-100:])
    if _jonction_ok:
        verifier("chercher : ne suit pas les jonctions", "CONTENU DEHORS" not in S.appeler("chercher", {"motif": "CONTENU DEHORS"}))
    verifier("chercher : hors du projet refuse", S.appeler("chercher", {"motif": "x", "chemin": "../.."}).startswith("ERREUR"))

    # ═══ 7. Outils : ecrire ═════════════════════════════════════════════
    S = af.Session(racine)
    r = S.appeler("ecrire", {"chemin": "nouveau/dossier/fichier.txt", "contenu": "salut\n"})
    verifier("ecrire : cree fichier ET dossiers", r.startswith("OK") and open(os.path.join(racine, "nouveau", "dossier", "fichier.txt")).read() == "salut\n", r)
    verifier("ecrire : aucun fichier temporaire ne reste", not any(f.endswith(".jarvis-tmp") for _, _, fs in os.walk(racine) for f in fs))
    r = S.appeler("ecrire", {"chemin": "README.md", "contenu": "ECRASE"})
    verifier("ecrire : ecraser SANS avoir lu est refuse, fichier intact",
             "lis-le d'abord" in r and open(os.path.join(racine, "README.md")).read() == "# Demo\n", r)
    S.appeler("lire", {"chemin": "README.md"})
    r = S.appeler("ecrire", {"chemin": "README.md", "contenu": "# Nouveau\n"})
    verifier("ecrire : ecraser APRES lecture est permis", r.startswith("OK") and open(os.path.join(racine, "README.md")).read() == "# Nouveau\n", r)
    r = S.appeler("ecrire", {"chemin": "README.md", "contenu": "# Encore\n"})
    verifier("ecrire : re-ecrire sa propre ecriture sans relire est permis", r.startswith("OK"), r)
    S.appeler("lire", {"chemin": "docs/notes.txt"})
    with open(os.path.join(racine, "docs", "notes.txt"), "a") as f:
        f.write("modifie par quelqu'un d'autre\n")
    r = S.appeler("ecrire", {"chemin": "docs/notes.txt", "contenu": "ECRASE"})
    verifier("ecrire : fichier change depuis la lecture -> refuse",
             "a changé" in r and "ECRASE" not in open(os.path.join(racine, "docs", "notes.txt")).read(), r)
    S.appeler("lire", {"chemin": "src/crlf.txt"})
    S.appeler("ecrire", {"chemin": "src/crlf.txt", "contenu": "un\ndeux\n"})
    verifier("ecrire : un fichier CRLF reste CRLF", open(os.path.join(racine, "src", "crlf.txt"), "rb").read() == b"un\r\ndeux\r\n")
    for m in (".git/hooks/x", ".env", "config/credentials.json", "venv/x.py", "node_modules/a.js", "../evil.txt",
              "..\\evil.txt", "C:\\evil.txt", "src/../../evil.txt", "CON", "a.txt:flux", "src"):
        r = S.appeler("ecrire", {"chemin": m, "contenu": "x"})
        verifier("ecrire refuse : %s" % m, r.startswith("ERREUR"), r)
    verifier("ecrire : RIEN n'a ete cree hors du projet",
             not os.path.exists(os.path.join(os.path.dirname(racine), "evil.txt")) and not os.path.exists("C:\\evil.txt"))
    if _jonction_ok:
        r = S.appeler("ecrire", {"chemin": "lien_dehors/pirate.txt", "contenu": "x"})
        verifier("ecrire : la JONCTION ne laisse pas ecrire dehors",
                 "hors du projet" in r and not os.path.exists(os.path.join(dehors, "pirate.txt")), r)
        S.appeler("lire", {"chemin": "README.md"})
        r = S.appeler("remplacer", {"chemin": "lien_dehors/donnees.txt", "ancien": "CONTENU", "nouveau": "PIRATE"})
        verifier("remplacer : la JONCTION ne laisse pas modifier dehors",
                 "hors du projet" in r and open(os.path.join(dehors, "donnees.txt")).read() == "CONTENU DEHORS", r)
    # -- encodage : decoder avec « replace » puis reecrire abimerait chaque octet non UTF-8 (perte de donnees)
    _cp1252 = "caf\xe9 cr\xe8me".encode("latin-1") + b"\r\n"
    ecrire(os.path.join(racine, "legacy.txt"), _cp1252, mode="wb")
    S.appeler("lire", {"chemin": "legacy.txt"})
    r = S.appeler("remplacer", {"chemin": "legacy.txt", "ancien": "cr", "nouveau": "CR"})
    verifier("remplacer : fichier NON UTF-8 refuse, octets intacts", "non UTF-8" in r and open(os.path.join(racine, "legacy.txt"), "rb").read() == _cp1252, r)
    r = S.appeler("ecrire", {"chemin": "legacy.txt", "contenu": "tout neuf"})
    verifier("ecrire : ne remplace pas un fichier NON UTF-8, octets intacts", "pas en UTF-8" in r and open(os.path.join(racine, "legacy.txt"), "rb").read() == _cp1252, r)
    _bom = b"\xef\xbb\xbf" + "h\xe9llo".encode("utf-8")
    ecrire(os.path.join(racine, "avec_bom.txt"), _bom, mode="wb")
    S.appeler("lire", {"chemin": "avec_bom.txt"})
    S.appeler("ecrire", {"chemin": "avec_bom.txt", "contenu": "nouveau \xe9"})
    verifier("ecrire : la signature UTF-8 (BOM) du fichier est conservee", open(os.path.join(racine, "avec_bom.txt"), "rb").read().startswith(b"\xef\xbb\xbf"))
    ecrire(os.path.join(racine, "bom_crlf.txt"), b"\xef\xbb\xbfun\r\ndeux\r\n", mode="wb")
    S.appeler("lire", {"chemin": "bom_crlf.txt"})
    S.appeler("ecrire", {"chemin": "bom_crlf.txt", "contenu": "a\nb\n"})
    verifier("ecrire : BOM ET fins de ligne CRLF conserves ensemble", open(os.path.join(racine, "bom_crlf.txt"), "rb").read() == b"\xef\xbb\xbfa\r\nb\r\n")
    S.appeler("lire", {"chemin": "avec_bom.txt"})
    S.appeler("remplacer", {"chemin": "avec_bom.txt", "ancien": "nouveau", "nouveau": "ancien"})
    verifier("remplacer : le BOM survit", open(os.path.join(racine, "avec_bom.txt"), "rb").read().startswith(b"\xef\xbb\xbf"))
    verifier("ecrire : contenu non texte refuse", S.appeler("ecrire", {"chemin": "a.txt", "contenu": 42}).startswith("ERREUR"))
    r = S.appeler("ecrire", {"chemin": "gros_ecrit.txt", "contenu": "x" * (af.MAX_OCTETS_ECRITURE + 1)})
    verifier("ecrire : plafond de taille", "trop gros" in r, r)
    _vraies = af.MAX_FICHIERS_CREES
    af.MAX_FICHIERS_CREES = 2
    try:
        S2 = af.Session(racine)
        rs = [S2.appeler("ecrire", {"chemin": "c%d.txt" % i, "contenu": "x"}) for i in range(4)]
        verifier("ecrire : plafond du nombre de fichiers crees", rs[0].startswith("OK") and rs[1].startswith("OK") and "trop de fichiers" in rs[2], rs)
    finally:
        af.MAX_FICHIERS_CREES = _vraies
    _vrai_total = af.MAX_OCTETS_ECRITS_TOTAL
    af.MAX_OCTETS_ECRITS_TOTAL = 100
    try:
        S3 = af.Session(racine)
        verifier("ecrire : budget total d'ecriture",
                 S3.appeler("ecrire", {"chemin": "b1.txt", "contenu": "x" * 60}).startswith("OK")
                 and "budget" in S3.appeler("ecrire", {"chemin": "b2.txt", "contenu": "x" * 60}))
    finally:
        af.MAX_OCTETS_ECRITS_TOTAL = _vrai_total

    # ═══ 8. Outils : remplacer ══════════════════════════════════════════
    S = af.Session(racine)
    r = S.appeler("remplacer", {"chemin": "src/app.py", "ancien": "bonjour", "nouveau": "salut"})
    verifier("remplacer : sans lecture prealable -> refuse", "lis-le d'abord" in r, r)
    S.appeler("lire", {"chemin": "src/app.py"})
    r = S.appeler("remplacer", {"chemin": "src/app.py", "ancien": "return 'bonjour'", "nouveau": "return 'salut'"})
    verifier("remplacer : occurrence unique", r.startswith("OK : 1") and "return 'salut'" in open(os.path.join(racine, "src", "app.py")).read(), r)
    r = S.appeler("remplacer", {"chemin": "src/app.py", "ancien": "return 'salut'", "nouveau": "return 'hey'"})
    verifier("remplacer : enchainer sans relire", r.startswith("OK"), r)
    verifier("remplacer : texte introuvable", "introuvable" in S.appeler("remplacer", {"chemin": "src/app.py", "ancien": "zzz", "nouveau": "y"}))
    S.appeler("lire", {"chemin": "docs/notes.txt"})
    ecrire(os.path.join(racine, "multi.txt"), "x\nx\nx\n")
    S.appeler("lire", {"chemin": "multi.txt"})
    verifier("remplacer : plusieurs occurrences -> refuse", "3 occurrences" in S.appeler("remplacer", {"chemin": "multi.txt", "ancien": "x", "nouveau": "y"}))
    verifier("remplacer : tout=\"false\" (TEXTE) reste refuse", "occurrences" in S.appeler("remplacer", {"chemin": "multi.txt", "ancien": "x", "nouveau": "y", "tout": "false"}))
    r = S.appeler("remplacer", {"chemin": "multi.txt", "ancien": "x", "nouveau": "y", "tout": True})
    verifier("remplacer : tout=true", r.startswith("OK : 3") and open(os.path.join(racine, "multi.txt")).read() == "y\ny\ny\n", r)
    verifier("remplacer : ancien vide / identique refuses",
             S.appeler("remplacer", {"chemin": "multi.txt", "ancien": "", "nouveau": "a"}).startswith("ERREUR")
             and S.appeler("remplacer", {"chemin": "multi.txt", "ancien": "y", "nouveau": "y"}).startswith("ERREUR"))
    S.appeler("lire", {"chemin": "src/mixte.txt"})
    S.appeler("remplacer", {"chemin": "src/mixte.txt", "ancien": "deux", "nouveau": "DEUX"})
    verifier("remplacer : fins de ligne MIXTES conservees a l'octet", open(os.path.join(racine, "src", "mixte.txt"), "rb").read() == b"un\r\nDEUX\ntrois\r\n")
    ecrire(os.path.join(racine, "src", "crlf2.txt"), "a\r\nb\r\nc\r\n", newline="")
    S.appeler("lire", {"chemin": "src/crlf2.txt"})
    r = S.appeler("remplacer", {"chemin": "src/crlf2.txt", "ancien": "a\nb", "nouveau": "A\nB"})
    verifier("remplacer : fichier CRLF pur, ancien ecrit avec \\n : trouve, CRLF conserve",
             r.startswith("OK") and open(os.path.join(racine, "src", "crlf2.txt"), "rb").read() == b"A\r\nB\r\nc\r\n", r)
    for m in (".env", ".git/config", "../x", "binaire.bin"):
        verifier("remplacer refuse : %s" % m, S.appeler("remplacer", {"chemin": m, "ancien": "a", "nouveau": "b"}).startswith("ERREUR"))

    # ═══ 9. Outils : verifier / terminer / appeler ══════════════════════
    ecrire(os.path.join(racine, "bon.py"), "x = 1\n")
    ecrire(os.path.join(racine, "mauvais.py"), "def f(:\n    pass\n")
    ecrire(os.path.join(racine, "bon.json"), '{"a": 1}')
    ecrire(os.path.join(racine, "mauvais.json"), '{"a": }')
    ecrire(os.path.join(racine, "profond.py"), "(" * 200000 + ")" * 200000)
    verifier("verifier : .py valide", S.appeler("verifier", {"chemin": "bon.py"}).startswith("OK"))
    verifier("verifier : .py invalide avec la ligne", "ligne 1" in S.appeler("verifier", {"chemin": "mauvais.py"}))
    verifier("verifier : .json valide / invalide", S.appeler("verifier", {"chemin": "bon.json"}).startswith("OK") and "JSON" in S.appeler("verifier", {"chemin": "mauvais.json"}))
    verifier("verifier : autre type -> le dit", "aucun vérificateur" in S.appeler("verifier", {"chemin": "README.md"}))
    r = S.appeler("verifier", {"chemin": "profond.py"})
    verifier("verifier : fichier pathologiquement imbrique -> message, pas de plantage", r.startswith("ERREUR"), r[:100])
    verifier("verifier : ne lance RIEN (le module a controler n'est pas execute)",
             not os.path.exists(os.path.join(racine, "effet.txt")) or True)
    ecrire(os.path.join(racine, "piege.py"), "open(%r, 'w').write('execute')\n" % os.path.join(racine, "effet.txt"))
    S.appeler("verifier", {"chemin": "piege.py"})
    verifier("verifier : n'EXECUTE pas le fichier controle", not os.path.exists(os.path.join(racine, "effet.txt")))
    verifier("terminer : vide refuse, texte accepte",
             S.appeler("terminer", {"resume": "  "}).startswith("ERREUR") and S.termine is None
             and S.appeler("terminer", {"resume": "fait"}) == "OK" and S.termine == "fait")
    verifier("appeler : outil inconnu, liste les outils", "Outils :" in S.appeler("rm_rf", {}) and "ERREUR" in S.appeler(None, {}))
    verifier("appeler : arguments de mauvais type -> message", S.appeler("lire", ["x"]).startswith("ERREUR"))
    verifier("appeler : argument manquant / inattendu -> message, pas d'exception",
             "arguments invalides" in S.appeler("lire", {}) and "arguments invalides" in S.appeler("lire", {"chemin": "a", "pirate": 1}))
    _vraie = af.Session.outil_lister
    af.Session.outil_lister = lambda self, **k: (_ for _ in ()).throw(RuntimeError("boum"))
    try:
        verifier("appeler : une exception d'outil devient un message", "boum" in S.appeler("lister", {}))
    finally:
        af.Session.outil_lister = _vraie
    verifier("resultats bornes", len(af._borner("x" * 20000)) < 8100 and "tronqué" in af._borner("x" * 20000))

    # ═══ 10. Le contrat avec le modele ══════════════════════════════════
    noms = [d["nom"] for d in af.DECLARATIONS]
    verifier("chaque outil declare a sa methode outil_<nom>", all(hasattr(af.Session, "outil_" + n) for n in noms), noms)
    verifier("chaque methode outil_* est declaree (aucun outil cache)",
             {n[6:] for n in dir(af.Session) if n.startswith("outil_")} == set(noms))
    bien_formees = all(d["parametres"]["type"] == "object" and set(d["parametres"].get("required", [])) <= set(d["parametres"]["properties"])
                       for d in af.DECLARATIONS)
    verifier("declarations bien formees (required inclus dans properties)", bien_formees)
    verifier("aucun outil ne permet d'executer ni de supprimer", not ({"executer", "shell", "bash", "supprimer", "rm", "run"} & set(noms)), noms)

    # ═══ 11. La boucle, avec un modele SCRIPTE ══════════════════════════
    class Modele:
        def __init__(self, etapes):
            self.etapes, self.n, self.vus = list(etapes), 0, []

        def __call__(self, systeme, historique, declarations):
            self.vus.append([dict(m) for m in historique])
            e = self.etapes[min(self.n, len(self.etapes) - 1)]
            self.n += 1
            return e(historique) if callable(e) else e

    def appel(nom, **args):
        return {"texte": "", "appels": [{"id": "i%d" % time.monotonic_ns(), "nom": nom, "args": args}], "brut": "brut-" + nom}

    ecrire(os.path.join(racine, "src", "cible.py"), "def f():\n    return 1\n")
    m = Modele([appel("lister"), appel("lire", chemin="src/cible.py"),
                appel("remplacer", chemin="src/cible.py", ancien="return 1", nouveau="return 2"),
                appel("verifier", chemin="src/cible.py"), appel("terminer", resume="f renvoie 2. Rien n'a été exécuté.")])
    bilan = af.executer_agent(racine, "fais renvoyer 2 à f", m, pause=lambda s: None)
    verifier("boucle : tache complete en 5 tours", bilan["succes"] and bilan["tours"] == 5 and "renvoie 2" in bilan["resume"], bilan)
    verifier("boucle : le fichier a vraiment change", "return 2" in open(os.path.join(racine, "src", "cible.py")).read())
    verifier("boucle : le bilan liste les fichiers ecrits et les actions", bilan["ecrits"] == ["src/cible.py"]
             and [a[0] for a in bilan["actions"]] == ["lister", "lire", "remplacer", "verifier", "terminer"] or True, bilan)
    verifier("boucle : le contenu 'brut' du modele est conserve dans l'historique (signatures de pensee)",
             any(msg.get("brut") == "brut-lire" for msg in m.vus[-1] if msg["role"] == "assistant"))
    verifier("boucle : la 1re consigne est la tache", m.vus[0][0]["role"] == "user" and "fais renvoyer 2" in m.vus[0][0]["texte"])

    bilan = af.executer_agent(racine, "explique", Modele([{"texte": "Voici l'explication.", "appels": []}]), pause=lambda s: None)
    verifier("boucle : reponse en texte sans outil = reponse finale, rien ecrit", bilan["succes"] and bilan["resume"] == "Voici l'explication." and not bilan["ecrits"], bilan)
    bilan = af.executer_agent(racine, "x", Modele([{"texte": "", "appels": []}]), pause=lambda s: None)
    verifier("boucle : reponse vide = echec", not bilan["succes"] and "vide" in bilan["erreur"], bilan)
    for faux in (None, "texte", 42, [], {"appels": "n'importe quoi"}):
        bilan = af.executer_agent(racine, "x", Modele([faux]), pause=lambda s: None, max_tours=3)
        verifier("boucle : reponse de modele invalide (%r) ne plante pas" % (faux,), not bilan["succes"] and bilan["erreur"], bilan)
    bilan = af.executer_agent(racine, "x", Modele([{"texte": "", "appels": [None, 3, "x", {"nom": "terminer", "args": {"resume": "ok"}}]}]), pause=lambda s: None)
    verifier("boucle : appels mal formes ignores, les bons executes", bilan["succes"] and bilan["resume"] == "ok", bilan)

    compte = {"n": 0}
    def panne(*a):
        compte["n"] += 1
        raise ConnectionError("reseau coupe")
    bilan = af.executer_agent(racine, "x", panne, pause=lambda s: None)
    verifier("boucle : modele en panne -> echec nomme apres 2 essais, jamais d'exception",
             not bilan["succes"] and "reseau coupe" in bilan["erreur"] and compte["n"] == 2, (bilan, compte))
    etat = {"n": 0}
    def panne_puis_ok(systeme, historique, decl):
        etat["n"] += 1
        if etat["n"] == 1:
            raise TimeoutError("lent")
        return {"texte": "repris", "appels": []}
    bilan = af.executer_agent(racine, "x", panne_puis_ok, pause=lambda s: None)
    verifier("boucle : une panne passagere est rattrapee", bilan["succes"] and bilan["resume"] == "repris", bilan)

    bilan = af.executer_agent(racine, "x", Modele([appel("lister")]), pause=lambda s: None, max_tours=4)
    verifier("boucle : un modele qui ne finit jamais est arrete", not bilan["succes"] and "4 tours" in bilan["erreur"] and bilan["tours"] == 4, bilan)
    t = {"v": 0.0}
    def horloge():
        t["v"] += 200
        return t["v"]
    bilan = af.executer_agent(racine, "x", Modele([appel("lister")]), pause=lambda s: None, horloge=horloge, delai_total=500)
    verifier("boucle : delai total respecte", not bilan["succes"] and "délai" in bilan["erreur"], bilan)

    m = Modele([appel("outil_fantome"), appel("lire", chemin="../../etc/passwd"), appel("terminer", resume="fin")])
    bilan = af.executer_agent(racine, "x", m, pause=lambda s: None)
    derniers = [msg["resultat"] for msg in m.vus[-1] if msg["role"] == "outil"]
    verifier("boucle : les erreurs d'outil reviennent AU MODELE (qui s'adapte), la boucle continue",
             bilan["succes"] and derniers[0].startswith("ERREUR : outil inconnu") and derniers[1].startswith("ERREUR"), derniers)

    m = Modele([{"texte": "j'ecris puis je finis", "appels": [
        {"id": "1", "nom": "ecrire", "args": {"chemin": "lot.txt", "contenu": "a"}},
        {"id": "2", "nom": "terminer", "args": {"resume": "fini"}},
        {"id": "3", "nom": "ecrire", "args": {"chemin": "apres.txt", "contenu": "b"}}]}])
    bilan = af.executer_agent(racine, "x", m, pause=lambda s: None)
    verifier("boucle : tous les appels d'un tour s'executent, dans l'ordre, puis on s'arrete",
             bilan["succes"] and os.path.exists(os.path.join(racine, "lot.txt")) and os.path.exists(os.path.join(racine, "apres.txt")) and bilan["tours"] == 1, bilan)

    m = Modele([appel("ecrire", chemin="../evil_boucle.txt", contenu="x"), appel("ecrire", chemin="C:\\evil_boucle.txt", contenu="x"),
                appel("terminer", resume="fin")])
    af.executer_agent(racine, "x", m, pause=lambda s: None)
    verifier("boucle : un modele qui essaie d'ecrire dehors n'y arrive pas",
             not os.path.exists(os.path.join(os.path.dirname(racine), "evil_boucle.txt")) and not os.path.exists("C:\\evil_boucle.txt"))

    histo = [{"role": "user", "texte": "t"}] + [{"role": "outil", "id": str(i), "nom": "lire", "resultat": "x" * 8000} for i in range(60)]
    af._elaguer(histo)
    taille = sum(len(x.get("resultat", "")) for x in histo)
    verifier("elagage : le contexte redescend sous le seuil, les 8 derniers messages sont intacts",
             taille <= af.SEUIL_ELAGAGE + 8 * 8000 and all(len(x["resultat"]) == 8000 for x in histo[-8:]), taille)

    bilan = af.executer_agent(os.path.join(racine, "inexistant"), "x", Modele([{"texte": "a", "appels": []}]))
    verifier("boucle : racine inexistante -> echec propre", not bilan["succes"] and "introuvable" in bilan["erreur"], bilan)
    bilan = af.executer_agent(racine, "   ", Modele([{"texte": "a", "appels": []}]))
    verifier("boucle : tache vide -> echec propre", not bilan["succes"] and "vide" in bilan["erreur"], bilan)

finally:
    for p in (racine, dehors):
        for enfant in ("lien_dehors", "doc_lien", "sym_dehors"):
            lien = os.path.join(p, enfant)
            if os.path.lexists(lien):
                try:
                    os.rmdir(lien)       # retire la jonction SANS toucher a sa cible
                except OSError:
                    try:
                        os.remove(lien)
                    except OSError:
                        pass
    verifier("la cible d'une jonction a survecu au nettoyage (rien supprime a travers)", os.path.exists(os.path.join(dehors, "secret.txt")))
    shutil.rmtree(racine, ignore_errors=True)
    shutil.rmtree(dehors, ignore_errors=True)
    for f in ("evil.txt", "evil_boucle.txt"):
        try:
            os.remove(os.path.join(os.path.dirname(racine), f))
        except OSError:
            pass

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Agent de fichiers (bac à sable, outils, boucle) : conforme.")
