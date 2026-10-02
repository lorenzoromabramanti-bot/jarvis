# -*- coding: utf-8 -*-
"""Vérifie delegation_code.py — détection, registre, préconditions. Aucun outil lancé."""

import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import delegation_code as dc

echecs = []


def verifier(libelle, condition, detail=None):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        if detail is not None:
            print("      ->", repr(detail)[:300])
        echecs.append(libelle)


# Isoler le vrai registre, comme pour taches_nocturnes.
_chemin_reel = dc._chemin_registre()
_sauvegarde = None
if os.path.exists(_chemin_reel):
    _sauvegarde = io.open(_chemin_reel, encoding="utf-8").read()

try:
    dc._ecrire_registre({})

    # ── Détection ────────────────────────────────────────────────────────
    for phrase in ["code-moi un script qui trie mes photos dans le projet site",
                   "développe une fonctionnalité de recherche pour le projet jarvis",
                   "corrige le bug d'affichage dans le projet site"]:
        verifier("détecte une demande de code : %r" % phrase[:40],
                  dc.detecter_delegation(phrase) is not None)

    for phrase in ["quelle heure il est", "raconte-moi ta journée", "code de la route, tu connais ?"]:
        verifier("ne détecte PAS sur une phrase normale : %r" % phrase,
                  dc.detecter_delegation(phrase) is None)

    r = dc.detecter_delegation("code-moi une page d'accueil pour le projet site")
    verifier("nom de projet extrait", r["nom_projet"] == "site")
    verifier("chemin absent tant que non enregistré", r["chemin_projet"] is None)

    r2 = dc.detecter_delegation("code-moi un script")
    verifier("aucun projet nommé -> nom_projet None (pas de supposition)", r2["nom_projet"] is None)

    # ── Registre ─────────────────────────────────────────────────────────
    # Un dossier réel mais DIFFÉRENT de celui de JARVIS — sinon ce cas se
    # confond avec le test "cible interdite" juste en dessous.
    import tempfile
    _dossier_test = tempfile.mkdtemp(prefix="jarvis_test_delegation_")
    ok, msg = dc.enregistrer_projet("test-projet", _dossier_test)
    verifier("enregistrement d'un dossier réel réussit", ok)

    ok2, msg2 = dc.enregistrer_projet("test-projet", "Z:\\ce\\dossier\\n_existe\\pas")
    verifier("enregistrement d'un dossier inexistant refusé", not ok2)

    ok3, msg3 = dc.enregistrer_projet("jarvis-lui-meme", os.path.dirname(os.path.abspath(__file__)))
    verifier("s'enregistrer soi-même refusé", not ok3 and "interdite" in msg3)

    ok4, msg4 = dc.enregistrer_projet("nom invalide!!", os.path.dirname(os.path.abspath(__file__)))
    verifier("nom de projet avec caractères interdits refusé", not ok4)

    r3 = dc.detecter_delegation("code-moi un menu pour le projet test-projet")
    verifier("chemin résolu une fois le projet enregistré", r3["chemin_projet"] is not None)

    # ── Préconditions ────────────────────────────────────────────────────
    ok_pre, raisons = dc.verifier_preconditions(None)
    verifier("préconditions refusées sans chemin", not ok_pre and raisons)

    ok_pre2, raisons2 = dc.verifier_preconditions("Z:\\dossier\\inexistant")
    verifier("préconditions refusées : dossier inexistant", not ok_pre2)

    ok_pre3, raisons3 = dc.verifier_preconditions(os.path.dirname(os.path.abspath(__file__)))
    print("  ..  préconditions sur le vrai dossier JARVIS : ok=%s raisons=%s" % (ok_pre3, raisons3))
    verifier("JARVIS lui-même toujours refusé même via verifier_preconditions",
              not ok_pre3 and any("interdite" in r for r in raisons3))

    # ── Résolution des exécutables (D2) ─────────────────────────────────
    # Bug réel trouvé en testant en direct : shutil.which("codex") seul
    # renvoie parfois le shim SANS extension (posé par npm pour bash/WSL),
    # que Windows refuse d'exécuter. _resoudre() doit préférer .cmd/.exe/.bat.
    for outil in ("claude", "codex", "opencode", "openclaw", "cursor-agent"):
        chemin = dc._resoudre(outil)
        verifier("%s résolu vers un .cmd/.exe/.bat (pas le shim nu)" % outil,
                  chemin.lower().endswith((".cmd", ".exe", ".bat")))

    verifier("commande inconnue renvoyée telle quelle (pas d'exception)",
              dc._resoudre("outil-qui-n-existe-pas-du-tout") == "outil-qui-n-existe-pas-du-tout")

    # ── Cibles interdites : la config Claude Code aussi ─────────────────
    ok5, msg5 = dc.enregistrer_projet("cfg-claude", os.path.join(os.path.expanduser("~"), ".claude"))
    verifier("~/.claude refuse comme cible (etait annonce, absent de l'ensemble)",
              not ok5 and "interdite" in msg5)

    # ── Déclarer un projet par une phrase ────────────────────────────────
    verifier("« enregistre le projet site : C:\\a\\b » -> (site, C:\\a\\b)",
              dc.detecter_enregistrement("enregistre le projet site : C:\\a\\b") == ("site", "C:\\a\\b"))
    verifier("chemin avec espaces et guillemets",
              dc.detecter_enregistrement('déclare le projet mon-site dans "C:\\Mes Docs\\site"')
              == ("mon-site", "C:\\Mes Docs\\site"))
    verifier("une phrase normale ne declare rien",
              dc.detecter_enregistrement("code-moi un script dans le projet site") is None)

    # ── Préconditions : bloquant vs simple info ──────────────────────────
    import subprocess as _sp
    _git_ok = _sp.run(["git", "--version"], capture_output=True).returncode == 0
    _vrai_which = dc.shutil.which
    # Toutes les outils de la chaine « presents » : le test ne doit pas
    # dependre de ce qui est installe sur la machine qui le lance.
    dc.shutil.which = lambda n, *a, **k: ("X:\\faux\\%s.exe" % n) if n in dc.OUTILS_EXTERNES else _vrai_which(n, *a, **k)
    try:
        _dossier_nu = tempfile.mkdtemp(prefix="jarvis_test_nu_")
        peut, bloq, infos = dc.preparer_execution(_dossier_nu)
        verifier("dossier hors git : on PEUT lancer (la baseline sera creee)",
                  peut and not bloq and any("pas un dépôt git" in i for i in infos))
        ok_strict, _ = dc.verifier_preconditions(_dossier_nu)
        verifier("verifier_preconditions reste strict : une info suffit a dire non", not ok_strict)

        dc.shutil.which = lambda n, *a, **k: None if n in dc.OUTILS_EXTERNES else _vrai_which(n, *a, **k)
        peut_a, bloq_a, _ = dc.preparer_execution(_dossier_nu)
        verifier("aucun outil de la chaine sur le PATH -> bloquant",
                  not peut_a and any("aucun outil" in b for b in bloq_a))
        dc.shutil.which = lambda n, *a, **k: ("X:\\faux\\%s.exe" % n) if n in dc.OUTILS_EXTERNES else _vrai_which(n, *a, **k)

        peut_i, bloq_i, _ = dc.preparer_execution("Z:\\dossier\\inexistant")
        verifier("dossier inexistant -> bloquant", not peut_i and bloq_i)
        peut_j, bloq_j, _ = dc.preparer_execution(os.path.dirname(os.path.abspath(__file__)))
        verifier("l'installation de JARVIS -> bloquant", not peut_j and any("interdite" in b for b in bloq_j))

        if _git_ok:
            _repo = tempfile.mkdtemp(prefix="jarvis_test_repo_")
            _git = ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", _repo]
            _sp.run(["git", "init", "-q", _repo], capture_output=True)
            io.open(os.path.join(_repo, "a.txt"), "w").write("un\n")
            _sp.run(_git + ["add", "-A"], capture_output=True)
            _sp.run(_git + ["commit", "-q", "-m", "base"], capture_output=True)
            peut_p, bloq_p, _ = dc.preparer_execution(_repo)
            verifier("depot propre -> on peut lancer", peut_p and not bloq_p)

            io.open(os.path.join(_repo, "a.txt"), "a").write("deux\n")
            io.open(os.path.join(_repo, "neuf.txt"), "w").write("nouveau\n")
            peut_s, bloq_s, _ = dc.preparer_execution(_repo)
            verifier("modifications non commitees -> BLOQUANT (jamais editer par-dessus)",
                      not peut_s and any("non commitées" in b for b in bloq_s))
            ch = dict((c[1], c[0]) for c in dc.resume_changements(_repo))
            verifier("resume_changements voit le fichier modifie ET le nouveau",
                      "a.txt" in ch and "neuf.txt" in ch)
            _shutil2 = __import__("shutil")
            _shutil2.rmtree(_repo, ignore_errors=True)
        _shutil3 = __import__("shutil")
        _shutil3.rmtree(_dossier_nu, ignore_errors=True)
    finally:
        dc.shutil.which = _vrai_which

    # ── Chaine d'execution : jamais lancee pour de vrai ──────────────────
    import agent_fichiers as _af

    class _Faux:
        def __init__(self, rc=0, out="fait", err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err

    _appels = []
    _vrai_run = dc.subprocess.run
    _vrai_resoudre = dc._resoudre
    _vrai_agent = _af.executer_agent

    def _outils_lances(appels):
        # Les appels git (baseline, diff) et « --version » (controle d'identite
        # de claude) ne sont pas des lancements d'outil de code.
        return [c for c in appels if os.path.basename(c[0][0]).lower() not in ("git", "git.exe")
                and c[0][-1] != "--version"]

    def _faux_run(reponse_outil, version="2.1.218 (Claude Code)"):
        def _run(cmd, *a, **k):
            _appels.append((list(cmd), k))
            if os.path.basename(cmd[0]).lower() in ("git", "git.exe"):
                return _Faux(0, "")      # baseline/diff : git n'est pas l'outil teste ici
            if cmd[-1] == "--version":
                return _Faux(0, version)
            return reponse_outil(cmd)
        return _run

    _projet = tempfile.mkdtemp(prefix="jarvis_test_exec_")
    _faux_claude = os.path.join(_projet, "faux_claude.exe")        # un fichier qui EXISTE : _claude_authentique le stat
    io.open(_faux_claude, "w").write("x")
    dc._resoudre = lambda c: _faux_claude if c == "claude" else _vrai_resoudre(c)
    try:
        # -- Sans modele : Claude Code est le premier outil externe
        dc._CLAUDE_VALIDES.clear()
        dc.subprocess.run = _faux_run(lambda cmd: _Faux(0, "ok"))
        res = dc.executer_delegation(_projet, "ajoute un commentaire")
        _outils = _outils_lances(_appels)
        verifier("sans modele : Claude Code est le premier outil externe, et il suffit quand il reussit",
                  len(_outils) == 1 and res["outil"] == "claude" and res["succes"], res)
        argv, kw = _outils[0]
        verifier("mode non interactif (-p) + permission acceptEdits", "-p" in argv and
                  argv[argv.index("--permission-mode") + 1] == "acceptEdits")
        verifier("JAMAIS bypassPermissions ni --dangerously-skip-permissions",
                  "bypassPermissions" not in argv and "--dangerously-skip-permissions" not in argv)
        verifier("boucle bornee (--max-turns)", "--max-turns" in argv)
        verifier("dossier cible passe par le cwd du subprocess", kw.get("cwd") == _projet)
        verifier("la tache est passee telle quelle, en dernier argument", argv[-1] == "ajoute un commentaire")
        verifier("aucun commit lance par la chaine (depot deja la : pas meme de baseline)",
                  not any("commit" in c[0] for c in _appels))

        # -- Claude Code en echec : l'erreur est NOMMEE, la chaine continue
        _appels.clear(); dc._CLAUDE_VALIDES.clear()
        dc.subprocess.run = _faux_run(lambda cmd: _Faux(1, "", "quota depasse"))
        res2 = dc.executer_delegation(_projet, "ajoute un commentaire")
        verifier("Claude Code en echec : l'erreur est nommee dans le compte-rendu",
                  not res2["succes"] and "Claude Code : quota depasse" in res2["erreur"])
        verifier("... et la chaine continue vers les autres outils", "Codex :" in res2["erreur"])

        # -- IDENTITE : un claude.exe tronque repond « 1.4.0 » (Bun) ; `bun -p "<phrase>"`
        #    EVALUERAIT la phrase comme du JavaScript. Il ne doit JAMAIS etre lance.
        _appels.clear(); dc._CLAUDE_VALIDES.clear()
        dc.subprocess.run = _faux_run(lambda cmd: _Faux(1, "", "x"), version="1.4.0")
        res3 = dc.executer_delegation(_projet, "console.log(process.env)")
        lances_avec_p = [c for c in _appels if c[0][0] == _faux_claude and "-p" in c[0]]
        verifier("un claude qui repond comme Bun n'est JAMAIS lance avec la phrase de l'utilisateur", not lances_avec_p, lances_avec_p)
        verifier("... et le compte-rendu dit pourquoi", "ne répond pas comme Claude Code" in res3["erreur"], res3["erreur"])
        dc._CLAUDE_VALIDES.clear()
        dc.subprocess.run = _faux_run(lambda cmd: _Faux(1, "", "x"), version="")
        res3b = dc.executer_delegation(_projet, "x")
        verifier("un claude muet ou illisible n'est pas lance non plus", "ne répond pas comme Claude Code" in res3b["erreur"])

        # -- Agent integre : premier essai quand un modele est fourni
        dc.subprocess.run = _faux_run(lambda cmd: _Faux(0, "ok"))
        recu = {}

        def _agent_ok(racine, tache, modele, **k):
            recu.update(racine=racine, tache=tache, modele=modele)
            return {"succes": True, "resume": "J'ai fait le changement. Rien n'a été exécuté.", "erreur": None,
                    "tours": 3, "ecrits": ["a.txt"], "actions": []}
        _af.executer_agent = _agent_ok
        _appels.clear(); dc._CLAUDE_VALIDES.clear()
        _mod = object()
        r4 = dc.executer_delegation(_projet, "ajoute un commentaire", modele=_mod)
        verifier("avec un modele : l'AGENT INTEGRE passe en premier et suffit (aucun outil externe lance)",
                  r4["outil"] == "jarvis" and r4["succes"] and not _outils_lances(_appels), (r4, _appels))
        verifier("... il recoit le dossier, la tache et le modele tels quels",
                  recu == {"racine": _projet, "tache": "ajoute un commentaire", "modele": _mod})
        verifier("... son resume devient la sortie", "Rien n'a été exécuté" in r4["sortie"])

        _af.executer_agent = lambda racine, tache, modele, **k: {
            "succes": False, "resume": "", "erreur": "quota Gemini", "tours": 1, "ecrits": [], "actions": []}
        _appels.clear(); dc._CLAUDE_VALIDES.clear()
        r5 = dc.executer_delegation(_projet, "ajoute un commentaire", modele=_mod)
        verifier("agent integre en echec SANS avoir ecrit : la chaine continue (Claude Code prend la suite)",
                  r5["outil"] == "claude" and r5["succes"], r5)

        _af.executer_agent = lambda racine, tache, modele, **k: {
            "succes": False, "resume": "", "erreur": "délai dépassé", "tours": 9, "ecrits": ["a.py", "b.py"], "actions": []}
        _appels.clear(); dc._CLAUDE_VALIDES.clear()
        r6 = dc.executer_delegation(_projet, "ajoute un commentaire", modele=_mod)
        verifier("agent integre en echec APRES avoir ecrit : la chaine S'ARRETE (jamais un 2e outil par-dessus)",
                  not r6["succes"] and r6["outil"] == "jarvis" and not _outils_lances(_appels)
                  and "a.py" in r6["erreur"] and "déjà modifié" in r6["erreur"], r6)

        # -- Cible interdite : refusee meme en appelant directement, sans rien lancer
        _appels.clear()
        r7 = dc.executer_delegation(os.path.dirname(os.path.abspath(dc.__file__)), "x", modele=_mod)
        verifier("l'installation de JARVIS est refusee par executer_delegation lui-meme (pas seulement au registre)",
                  not r7["succes"] and "interdite" in r7["erreur"] and not _appels)
        verifier("... et un chemin vide aussi", not dc.executer_delegation("", "x")["succes"])
    finally:
        dc.subprocess.run = _vrai_run
        dc._resoudre = _vrai_resoudre
        _af.executer_agent = _vrai_agent
        __import__("shutil").rmtree(_projet, ignore_errors=True)

    # ── De bout en bout, VRAIE boucle + VRAI git, modele scripte ─────────
    if _git_ok:
        _repo2 = tempfile.mkdtemp(prefix="jarvis_test_e2e_")
        try:
            _g = ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", _repo2]
            _sp.run(["git", "init", "-q", _repo2], capture_output=True)
            io.open(os.path.join(_repo2, "f.py"), "w").write("def f():\n    return 1\n")
            _sp.run(_g + ["add", "-A"], capture_output=True)
            _sp.run(_g + ["commit", "-q", "-m", "base"], capture_output=True)
            _etapes = iter([
                {"texte": "", "appels": [{"id": "1", "nom": "lire", "args": {"chemin": "f.py"}}], "brut": None},
                {"texte": "", "appels": [{"id": "2", "nom": "remplacer",
                                          "args": {"chemin": "f.py", "ancien": "return 1", "nouveau": "return 2"}}], "brut": None},
                {"texte": "", "appels": [{"id": "3", "nom": "terminer", "args": {"resume": "f renvoie 2. Rien exécuté."}}], "brut": None}])
            r8 = dc.executer_delegation(_repo2, "fais renvoyer 2 à f", modele=lambda s, h, d: next(_etapes))
            verifier("bout en bout : l'agent integre modifie le fichier, le diff git le montre, rien n'est commite",
                      r8["outil"] == "jarvis" and r8["succes"] and "+    return 2" in r8["diff"]
                      and _sp.run(_g + ["log", "--oneline"], capture_output=True, text=True).stdout.count("\n") == 1, r8)
            ch2 = dc.resume_changements(_repo2)
            phrase = dc.resumer_resultat(r8, "demo", ch2)
            verifier("le compte-rendu parle nomme l'agent, le fichier, et reprend son resume",
                      phrase.startswith("Mon agent intégré a terminé") and "f.py" in phrase and "f renvoie 2" in phrase, phrase)
        finally:
            __import__("shutil").rmtree(_repo2, ignore_errors=True)

    # ── Securite du lancement et des cibles (revue 1.2.0, #2 #10 #15) ────
    import shutil as _sh
    _bac = tempfile.mkdtemp(prefix="jarvis_test_secu_")
    _vrai_run2, _vrai_resoudre2 = dc.subprocess.run, dc._resoudre
    _env_avant = {k: os.environ.get(k) for k in ("JARVIS_DOSSIERS_AUTORISES", "JARVIS_OPENCODE_MODELE",
                                                  "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
    try:
        # #2 BatBadBut : un shim npm (meme forme que codex.cmd) ne doit jamais
        # faire passer la tache par cmd.exe. Avant : « & echo INJECTE » s'executait.
        os.makedirs(os.path.join(_bac, "node_modules", "faux"))
        io.open(os.path.join(_bac, "node_modules", "faux", "faux.js"), "w").write(
            'console.log("ARGV=" + JSON.stringify(process.argv.slice(2)))')
        io.open(os.path.join(_bac, "faux.cmd"), "w").write(
            '@ECHO off\r\nSET dp0=%~dp0\r\n"node"  "%dp0%\\node_modules\\faux\\faux.js" %*\r\n')
        io.open(os.path.join(_bac, "opaque.cmd"), "w").write('@echo off\r\necho LANCE %*\r\n')
        _cible = {"faux": os.path.join(_bac, "faux.cmd"), "opaque": os.path.join(_bac, "opaque.cmd")}
        dc._resoudre = lambda c: _cible.get(c, c)
        for tache in ('ajoute "une page & echo INJECTE', 'ajoute un bouton "Copier & coller'):
            if _sh.which("node"):
                rr = dc._lancer("faux", ["exec", tache], capture_output=True, text=True, timeout=60)
                verifier("#2 shim npm deplie : la tache arrive entiere, rien d'execute (%r)" % tache[-14:],
                          rr.stdout.strip() == "ARGV=" + __import__("json").dumps(["exec", tache], separators=(",", ":"))
                          and not rr.stderr.strip(), (rr.stdout, rr.stderr))
            ro = dc._lancer("opaque", ["-p", tache], capture_output=True, text=True)
            verifier("#2 .cmd non depliable + caractere cmd : refuse sans lancer (%r)" % tache[-14:],
                      ro.returncode == 1 and "non lancé" in ro.stderr and "LANCE" not in ro.stdout, ro)
        dc._resoudre = _vrai_resoudre2

        # #10 cibles : racine, profil entier, dossier systeme, liste blanche
        _maison = os.path.expanduser("~")
        for cible, motif in ((os.path.splitdrive(_bac)[0] + "\\", "racine"),
                             (_maison, "contient"), (os.path.dirname(_maison), "contient"),
                             (os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp"), "système")):
            okc, msgc = dc.enregistrer_projet("cible", cible)
            verifier("#10 %s refuse (%s)" % (cible, motif), not okc and motif in msgc, msgc)
        _a, _b = os.path.join(_bac, "a"), os.path.join(_bac, "b")
        os.makedirs(_a); os.makedirs(_b)
        os.environ["JARVIS_DOSSIERS_AUTORISES"] = _a
        verifier("#10 JARVIS_DOSSIERS_AUTORISES : dedans accepte, dehors refuse",
                  dc.enregistrer_projet("dedans", _a)[0] and not dc.enregistrer_projet("dehors", _b)[0])
        del os.environ["JARVIS_DOSSIERS_AUTORISES"]

        # #10 baseline : git sans identite -> commit quand meme, et l'echec n'est jamais annonce reussi
        if _git_ok:
            _vide = os.path.join(_bac, "gitconfig_vide")
            io.open(_vide, "w").close()
            os.environ["GIT_CONFIG_GLOBAL"], os.environ["GIT_CONFIG_NOSYSTEM"] = _vide, "1"
            io.open(os.path.join(_b, "f.txt"), "w").write("x\n")
            okb, msgb = dc._assurer_baseline_git(_b)
            _log = _sp.run(["git", "-C", _b, "log", "--oneline"], capture_output=True, text=True).stdout
            verifier("#10 baseline creee meme sans user.email configure", okb and _log.count("\n") == 1, (msgb, _log))
            dc.subprocess.run = lambda cmd, *a, **k: _Faux(128, "", "fatal: refus simule") \
                if "commit" in cmd else _vrai_run2(cmd, *a, **k)
            okc2, msgc2 = dc._assurer_baseline_git(_a)
            verifier("#10 commit en echec -> (False, raison), jamais « baseline créée »",
                      not okc2 and "commit" in msgc2 and "créée" not in msgc2, msgc2)
            dc.subprocess.run = _vrai_run2

        # #15 OpenCode : sans JARVIS_OPENCODE_MODELE, le repli est saute proprement
        os.environ.pop("JARVIS_OPENCODE_MODELE", None)
        _vus = []
        dc.subprocess.run = lambda cmd, *a, **k: (_vus.append(list(cmd)), _Faux(0, "") if os.path.basename(
            cmd[0]).lower() in ("git", "git.exe") else _Faux(1, "", "x"))[1]
        dc._resoudre = lambda c: "X:\\faux\\%s.exe" % c
        _r15 = dc.executer_delegation(_b, "x")
        verifier("#15 modele OpenCode vide : repli saute, nomme, jamais lance",
                  "JARVIS_OPENCODE_MODELE vide" in _r15["erreur"]
                  and not any("opencode" in c[0] for c in _vus), _r15["erreur"])
        os.environ["JARVIS_OPENCODE_MODELE"] = "fournisseur/modele"
        _vus.clear()
        dc.executer_delegation(_b, "x")
        _oc = [c for c in _vus if "opencode" in c[0]]
        verifier("#15 modele OpenCode configure : passe tel quel a --model",
                  _oc and _oc[0][_oc[0].index("--model") + 1] == "fournisseur/modele", _vus)
    finally:
        dc.subprocess.run, dc._resoudre = _vrai_run2, _vrai_resoudre2
        for k, v in _env_avant.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _sh.rmtree(_bac, ignore_errors=True)

    # ── Qui serait essaye ? ──────────────────────────────────────────────
    verifier("premier outil : l'agent integre quand un modele existe",
              dc.premier_outil_disponible(agent_natif=True) == "mon agent intégré")
    _vrai_which2 = dc.shutil.which
    dc.shutil.which = lambda n, *a, **k: None if n in dc.OUTILS_EXTERNES else _vrai_which2(n, *a, **k)
    try:
        _d0 = tempfile.mkdtemp(prefix="jarvis_test_nu2_")
        peut_x, bloq_x, _ = dc.preparer_execution(_d0)
        peut_y, bloq_y, _ = dc.preparer_execution(_d0, agent_natif=True)
        verifier("rien sur le PATH ET pas de modele -> bloquant ; avec l'agent integre -> on peut lancer",
                  not peut_x and any("aucun outil" in b for b in bloq_x) and peut_y and not bloq_y, (bloq_x, bloq_y))
        verifier("premier outil : None quand rien n'est disponible", dc.premier_outil_disponible() is None)
        __import__("shutil").rmtree(_d0, ignore_errors=True)
    finally:
        dc.shutil.which = _vrai_which2

    # ── Detection : verbes de lecture/modification, projet NOMME obligatoire ──
    for phrase, attendu in (("explique-moi le fichier main.py dans le projet site", "site"),
                            ("lis README dans le projet site", "site"),
                            ("modifie la couleur du bouton pour le projet site", "site"),
                            ("cherche la fonction total dans le projet demo", "demo"),
                            ("refactorise le module dans le projet x", "x")):
        r = dc.detecter_delegation(phrase)
        verifier("verbe souple + projet nomme : %r" % phrase[:44], r is not None and r["nom_projet"] == attendu, r)
    for phrase in ("explique-moi la photosynthese", "cherche un restaurant pour ce soir",
                   "modifie mon reveil pour demain", "lis-moi mes mails", "le plan du projet changement de vie"):
        verifier("verbe souple SANS projet nomme : rien (%r)" % phrase[:40], dc.detecter_delegation(phrase) is None)

    # ── Compte-rendu parle : jamais « c'est fait » sans preuve ───────────
    p1 = dc.resumer_resultat({"succes": True, "outil": "claude"}, "site",
                              [("M", "a.txt"), ("??", "b.txt")])
    verifier("succes : dit l'outil, les fichiers, et que rien n'est teste ni commite",
              "Claude Code" in p1 and "a.txt" in p1 and "testé" in p1 and "git" in p1)
    verifier("succes sans changement : le dit franchement",
              "sans modifier aucun fichier" in dc.resumer_resultat(
                  {"succes": True, "outil": "codex"}, "site", []))
    verifier("echec : reprend la raison",
              "quota" in dc.resumer_resultat({"succes": False, "erreur": "quota depasse"}, "site", []))

finally:
    if _sauvegarde is not None:
        io.open(_chemin_reel, "w", encoding="utf-8").write(_sauvegarde)
    elif os.path.exists(_chemin_reel):
        os.remove(_chemin_reel)
    try:
        import shutil as _shutil
        _shutil.rmtree(_dossier_test, ignore_errors=True)
    except NameError:
        pass

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Délégation de code (détection D1) : conforme.")
