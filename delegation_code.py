# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Délégation de tâches de code (mission D1)
=========================================================
JARVIS reconnaît une demande de code et sait à quel projet elle
s'adresse. Ce fichier ne lance AUCUN outil externe — juste la
détection et les vérifications de sécurité. L'exécution réelle
(Codex → OpenCode → OpenClaw, inspiré d'un pipeline Claude Code) est la
partie D2, plus bas.

POURQUOI UN REGISTRE DE PROJETS
JARVIS n'a pas de navigateur de fichiers en mode vocal. « Code-moi X
dans le projet Y » n'a de sens que si Y a déjà été déclaré une fois —
sinon JARVIS devine un chemin, ce que ce dépôt refuse de faire partout
ailleurs (ha_resolution.py : « ne jamais deviner »).

POURQUOI DES PRÉCONDITIONS SÉPARÉES DE L'EXÉCUTION
Un pipeline de délégation sérieux vérifie une
baseline git et la santé des outils AVANT de lancer quoi que ce soit. Même
logique ici, dans un module qu'on peut tester sans jamais invoquer
Codex/OpenCode/OpenClaw pour de vrai.
"""

import io
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile

import config

FICHIER_PROJETS = "projets_delegation.json"

# Jamais une cible valide : le dossier d'installation de JARVIS lui-même
# (un process qui modifierait son propre code source pendant qu'il tourne)
# et la config Claude Code (~/.claude), que Claude Code, membre de la
# chaîne, lit justement.
_INTERDITS = {
    os.path.normcase(os.path.dirname(os.path.abspath(__file__))),
    os.path.normcase(os.path.join(os.path.expanduser("~"), ".claude")),
}


def _dossiers_systeme():
    """Dossiers qu'un projet ne doit jamais CONTENIR : y lancer `git add -A`
    puis un agent revient à lui confier tout le profil ou tout le système."""
    env = os.environ
    return [d for d in (os.path.expanduser("~"), env.get("SystemRoot"), env.get("ProgramFiles"),
                        env.get("ProgramFiles(x86)"), env.get("ProgramData")) if d]


def _contient(parent, enfant):
    try:
        return os.path.commonpath([parent, enfant]) == parent
    except ValueError:          # lecteurs différents
        return False


def _refus_cible(chemin_projet):
    """
    None si le dossier peut servir de projet, sinon la raison du refus.

    Point unique, appelé à l'enregistrement, au diagnostic et à l'exécution.
    Refusés : l'installation de JARVIS et ~/.claude ; une racine de lecteur ;
    tout dossier qui contient le profil utilisateur, Windows, Program Files
    ou ProgramData (un sous-dossier de Program Files reste permis) ; tout ce
    qui est sous Windows ; et, si JARVIS_DOSSIERS_AUTORISES est défini, tout
    ce qui n'est pas dans un de ces dossiers.
    """
    brut = os.path.normcase(os.path.abspath(chemin_projet))
    reel = os.path.normcase(os.path.realpath(brut))
    if brut in _INTERDITS or reel in _INTERDITS:
        return "cible interdite : l'installation de JARVIS elle-même"
    if os.path.dirname(reel) == reel:
        return "cible interdite : la racine d'un lecteur"
    for d in _dossiers_systeme():
        d = os.path.normcase(os.path.realpath(d))
        if _contient(reel, d):
            return "cible interdite : ce dossier contient %s" % d
    windows = os.environ.get("SystemRoot")
    if windows and _contient(os.path.normcase(os.path.realpath(windows)), reel):
        return "cible interdite : dossier système"
    if (os.environ.get("JARVIS_DOSSIERS_AUTORISES") or "").strip():
        import file_access
        autorises = [os.path.normcase(d) for d in file_access.dossiers_autorises()]
        if not any(_contient(d, reel) for d in autorises):
            return "cible interdite : hors de JARVIS_DOSSIERS_AUTORISES"
    return None

# Les outils de la chaîne, dans l'ordre d'essai de executer_delegation().
# « jarvis » = l'agent de fichiers INTEGRE (agent_fichiers.py) : aucun binaire,
# il utilise le modele de JARVIS. Les autres sont des CLI externes, cherchees
# sur le PATH. Demande de l'utilisateur : que JARVIS sache faire comme Claude
# Code SANS dependre de Claude Code.
OUTILS_EXTERNES = ("claude", "codex", "opencode", "openclaw", "cursor-agent")
OUTILS_CHAINE = ("jarvis",) + OUTILS_EXTERNES
NOMS_OUTILS = {"jarvis": "mon agent intégré", "claude": "Claude Code", "codex": "Codex",
               "opencode": "OpenCode", "openclaw": "OpenClaw", "cursor-agent": "Cursor Agent"}

_VERBES_CODE = (
    r"code[- ]moi|codes[- ]moi|programme[- ]moi|d[ée]veloppe|"
    r"[ée]cris (?:un |une |le |la )?script|cr[ée]e (?:un |une )?script|"
    r"ajoute une fonctionnalit[ée]|corrige (?:le |la |un |une )?bug|"
    r"corrige le code|fais un fix|impl[ée]mente"
)

_MOTIF_DEMANDE = re.compile(_VERBES_CODE, re.IGNORECASE)
# Verbes du quotidien (lire, expliquer, modifier...) : trop courants pour
# declencher seuls — « explique-moi la photosynthese » n'est pas du code. Ils
# ne comptent QUE si la phrase nomme un projet (« ... dans le projet site »).
_VERBES_SOUPLES = (
    r"modifie|change|ajoute|supprime|explique|analyse|audite|relis|lis|r[ée]sume|"
    r"refactor\w*|r[ée]pare|documente|optimise|nettoie|cherche|trouve|renomme"
)
_MOTIF_DEMANDE_SOUPLE = re.compile(r"\b(?:" + _VERBES_SOUPLES + r")\b", re.IGNORECASE)
# « dans/pour/sur le projet X » — X capturé jusqu'à ponctuation/fin.
_MOTIF_PROJET = re.compile(
    r"(?:dans|pour|sur)\s+(?:le\s+|mon\s+|la\s+)?projet\s+([a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)


def _chemin_registre():
    return config.chemin_donnees(FICHIER_PROJETS, creer_dossier=True)


def _lire_registre():
    try:
        with io.open(_chemin_registre(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_registre(donnees):
    chemin = _chemin_registre()
    tmp = str(chemin) + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


def enregistrer_projet(nom, chemin_projet):
    """
    Déclare un projet. Renvoie (ok, message).

    Refuse un chemin inexistant, un fichier (pas un dossier), ou une des
    cibles interdites — jamais silencieusement accepté puis échoué plus
    tard, au moment où c'est le plus coûteux (en plein milieu d'un
    lancement Codex).
    """
    if not nom or not re.match(r"^[a-zA-Z0-9_\-]+$", nom):
        return False, "nom de projet invalide (lettres/chiffres/-/_ seulement)"
    chemin_abs = os.path.abspath(chemin_projet)
    refus = _refus_cible(chemin_abs)
    if refus:
        return False, refus
    if not os.path.isdir(chemin_abs):
        return False, "dossier introuvable : %s" % chemin_abs
    registre = _lire_registre()
    registre[nom.lower()] = chemin_abs
    _ecrire_registre(registre)
    return True, "projet « %s » -> %s" % (nom, chemin_abs)


def projets_connus():
    return dict(_lire_registre())


def detecter_delegation(texte):
    """
    None : pas une demande de délégation de code.
    Sinon : dict {"tache": str, "nom_projet": str|None, "chemin_projet": str|None}

    `nom_projet`/`chemin_projet` sont None si la phrase ne nomme aucun
    projet reconnu — à l'appelant de redemander LEQUEL, jamais de
    supposer "le seul projet enregistré" ou "le dernier utilisé".
    """
    if not texte:
        return None
    m = _MOTIF_PROJET.search(texte)
    if not _MOTIF_DEMANDE.search(texte) and not (m and _MOTIF_DEMANDE_SOUPLE.search(texte)):
        return None

    nom_projet = m.group(1).lower() if m else None
    chemin_projet = None
    if nom_projet:
        chemin_projet = _lire_registre().get(nom_projet)

    return {"tache": texte.strip(), "nom_projet": nom_projet, "chemin_projet": chemin_projet}


# « enregistre le projet site : C:\Users\VotreNom\site » — declarer un projet sans
# ouvrir un fichier JSON. Pense pour le canal TEXTE : dicter un chemin
# Windows a la voix ne marchera presque jamais.
_MOTIF_ENREGISTRER = re.compile(
    r"(?:enregistre|d[ée]clare)\s+(?:le\s+|mon\s+|un\s+)?projet\s+([a-zA-Z0-9_\-]+)"
    r"\s*(?:dans|:|=|->|sur)\s*(?:le\s+dossier\s+)?[\"']?(.+?)[\"']?\s*$",
    re.IGNORECASE)


def detecter_enregistrement(texte):
    """(nom, chemin) si la phrase declare un projet, sinon None. N'enregistre rien."""
    m = _MOTIF_ENREGISTRER.search((texte or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def _diagnostiquer(chemin_projet, agent_natif=False):
    """
    (bloquants, infos). Un BLOQUANT empêche de lancer quoi que ce soit ; une
    INFO est bonne à savoir sans rien empêcher (un outil absent, alors que la
    chaîne en essaie cinq ; un dossier pas encore sous git, dont
    executer_delegation() crée la baseline).

    Séparés parce que verifier_preconditions() les mélangeait : « pas un
    dépôt git — une baseline sera créée » y rendait ok=False pour un cas que
    la suite gère très bien, et « des modifications non commitées » (qui doit
    vraiment arrêter) y pesait pareil qu'un outil manquant.
    """
    bloquants, infos = [], []
    chemin_abs = os.path.abspath(chemin_projet) if chemin_projet else None

    if not chemin_abs or not os.path.isdir(chemin_abs):
        return ["dossier de projet introuvable : %r" % chemin_projet], []

    refus = _refus_cible(chemin_abs)
    if refus:
        return [refus], []

    absents = [o for o in OUTILS_EXTERNES if shutil.which(o) is None]
    if len(absents) == len(OUTILS_EXTERNES) and not agent_natif:
        bloquants.append("aucun outil de code disponible (agent intégré indisponible, et rien sur le PATH : %s)"
                         % ", ".join(OUTILS_EXTERNES))
    else:
        infos.extend("%s absent du PATH" % o for o in absents)

    if shutil.which("git") is None:
        bloquants.append("git absent du PATH — aucune baseline possible")
    else:
        r = subprocess.run(["git", "-C", chemin_abs, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            infos.append("pas un dépôt git — une baseline sera créée avant toute édition")
        elif r.stdout.strip():
            bloquants.append("des modifications non commitées existent déjà dans ce projet — "
                             "à traiter avant de laisser un outil externe éditer par-dessus")

    return bloquants, infos


def verifier_preconditions(chemin_projet):
    """
    (ok, raisons) — raisons est une liste, vide si ok.

    Ne lance AUCUN outil de code. Vérifie seulement que les conditions du
    pipeline (baseline git, dépendances présentes) tiennent — ou dit
    précisément ce qui manque, comme partout ailleurs dans ce dépôt.
    Strict : la moindre info compte comme raison. Pour décider de lancer ou
    non, utiliser preparer_execution().
    """
    bloquants, infos = _diagnostiquer(chemin_projet)
    raisons = bloquants + infos
    return (len(raisons) == 0, raisons)


def premier_outil_disponible(agent_natif=False):
    """Nom lisible du premier outil qui SERAIT essaye, ou None."""
    if agent_natif:
        return NOMS_OUTILS["jarvis"]
    for o in OUTILS_EXTERNES:
        if shutil.which(o):
            return NOMS_OUTILS[o]
    return None


def preparer_execution(chemin_projet, agent_natif=False):
    """
    (peut_lancer, bloquants, infos) — la question que se pose l'appelant
    juste avant de lancer un outil de code. `agent_natif` : l'appelant a un
    modele utilisable pour l'agent integre (main2.py : Gemini actif).
    """
    bloquants, infos = _diagnostiquer(chemin_projet, agent_natif)
    return (not bloquants, bloquants, infos)


def resume_changements(chemin_projet):
    """
    [(code, chemin)] des fichiers touchés depuis la baseline, NOUVEAUX
    fichiers compris. `git diff` seul ne montre pas un fichier créé et non
    ajouté : un outil qui ne fait que créer des fichiers rendait un diff
    vide, donc un compte-rendu « rien n'a changé ».
    """
    r = subprocess.run(["git", "-C", chemin_projet, "status", "--porcelain"],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=20)
    changements = []
    for ligne in r.stdout.splitlines():
        if len(ligne) > 3:
            changements.append((ligne[:2].strip() or "?", ligne[3:].strip().strip('"')))
    return changements


def resumer_resultat(res, nom_projet, changements):
    """
    La phrase que JARVIS dit une fois l'outil terminé. Ne dit JAMAIS « c'est
    fait » : l'outil a fini sans erreur, ce qui ne prouve pas que le code
    marche — personne ne l'a lancé ni testé ici.
    """
    if not res.get("succes"):
        erreur = (res.get("erreur") or "raison inconnue")[:250]
        return ("Aucun outil n'a réussi sur le projet %s. %s" % (nom_projet, erreur))
    outil = NOMS_OUTILS.get(res.get("outil"), res.get("outil") or "l'outil")
    outil = outil[:1].upper() + outil[1:]
    if not changements:
        return ("%s a terminé sur le projet %s sans modifier aucun fichier. "
                "Rien à relire." % (outil, nom_projet))
    noms = ", ".join(c[1] for c in changements[:4])
    reste = len(changements) - 4
    liste = noms + (" et %d autre(s)" % reste if reste > 0 else "")
    phrase = ("%s a terminé sur le projet %s : %d fichier(s) touché(s), %s. "
              "Rien n'est enregistré dans git et personne n'a testé le résultat — "
              "relis le diff avant de valider." % (outil, nom_projet, len(changements), liste))
    if res.get("outil") == "jarvis" and res.get("sortie"):
        phrase += " Mon résumé : " + str(res["sortie"]).strip()[:400]
    return phrase


# ═══ D2 — exécution réelle (Codex → OpenCode → OpenClaw) ══════════════════
#
# Chaîne d'outils en subprocess Python, jamais via un shell. NE COMMIT
# JAMAIS — le diff est renvoyé à l'appelant, qui décide.

TIMEOUT_CLAUDE = 300
MAX_TOURS_CLAUDE = 30
TIMEOUT_CODEX = 300
TIMEOUT_OPENCODE = 180
TIMEOUT_OPENCLAW = 180
TIMEOUT_CURSOR = 240

_GITIGNORE_DEFAUT = (
    ".env\n.env.*\n*.key\ncredentials.json\nnode_modules/\nvenv/\n"
    ".venv/\n__pycache__/\n*.pyc\n.DS_Store\n*.log\n"
)


def _assurer_baseline_git(chemin_projet):
    """
    (ok, message). Crée une baseline git si absente ; ne touche jamais un
    dépôt déjà là.

    Chaque étape est vérifiée : sans user.email configuré, `git commit`
    échouait en silence, le message disait quand même « baseline créée » et
    tout le projet apparaissait ensuite comme modifié par l'outil. On fournit
    donc une identité neutre quand git n'en a pas.
    """
    r = subprocess.run(["git", "-C", chemin_projet, "status"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode == 0:
        return True, "dépôt existant, baseline déjà là"

    gitignore = os.path.join(chemin_projet, ".gitignore")
    if not os.path.exists(gitignore):
        io.open(gitignore, "w", encoding="utf-8", newline="\n").write(_GITIGNORE_DEFAUT)
    identite = []
    for cle, defaut in (("user.name", "JARVIS"), ("user.email", "jarvis@localhost")):
        lu = subprocess.run(["git", "-C", chemin_projet, "config", cle],
                            capture_output=True, text=True, timeout=15)
        if lu.returncode != 0 or not lu.stdout.strip():
            identite += ["-c", "%s=%s" % (cle, defaut)]
    for etape, cmd, delai in (
            ("git init", ["init", "-q"], 15),
            ("git add", ["add", "-A"], 60),
            ("git commit", identite + ["commit", "-q", "--allow-empty",
                                       "-m", "Baseline avant délégation JARVIS"], 30)):
        r = subprocess.run(["git", "-C", chemin_projet] + cmd,
                           capture_output=True, text=True, timeout=delai)
        if r.returncode != 0:
            return False, "baseline impossible (%s) : %s" % (
                etape, (r.stderr or r.stdout).strip()[:200] or "code %d" % r.returncode)
    return True, "baseline créée"


def _resoudre(commande):
    """
    Chemin complet d'un exécutable, ou le nom brut si introuvable.

    Deux pièges Windows empilés, trouvés en testant réellement (pas en
    lisant la doc de subprocess) :

    1. subprocess.run(["codex", ...]) échoue quand `codex` est un shim
       npm : CreateProcess ne fait pas ce que fait un shell, ni PATHEXT.
    2. shutil.which("codex") tout court ne suffit pas non plus : npm pose
       DEUX fichiers du même nom — `codex` (shim shebang pour bash/WSL)
       et `codex.cmd` (le vrai lanceur Windows). which() retourne le
       premier trouvé, souvent celui SANS extension, que Windows refuse
       d'exécuter (WinError 193 : "n'est pas une application Win32
       valide"). On force donc .cmd/.exe/.bat en priorité.
    """
    for ext in (".cmd", ".exe", ".bat", ""):
        chemin = shutil.which(commande + ext)
        if chemin:
            return chemin

    # Un outil tout juste installé (cursor-agent) peut ne pas encore être
    # sur le PATH tant que la session n'a pas redémarré — le PATH système
    # se met à jour au niveau du registre, pas des process déjà ouverts.
    # Emplacement par défaut de son installeur officiel.
    _connus = {
        "cursor-agent": os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                     "cursor-agent", "cursor-agent.cmd"),
    }
    _repli = _connus.get(commande)
    if _repli and os.path.isfile(_repli):
        return _repli

    return commande


# Caractères que cmd.exe interprète même dans un argument qu'on croit
# protégé : avec eux, le texte d'une tâche passé à un .cmd peut lancer une
# autre commande (faille dite « BatBadBut » ; Python n'échappe rien ici).
_META_CMD = re.compile(r'["%!^&|<>()\r\n]')
# Dernière ligne d'un shim npm : "%dp0%\chemin\vers\cible" %*
_CIBLE_SHIM = re.compile(r'"%dp0%\\?([^"%]+)"\s+%\*')


def _argv_direct(chemin):
    """
    argv qui lance `chemin` SANS passer par cmd.exe, ou None.

    Un .cmd/.bat est toujours interprété par cmd.exe. Les shims npm (codex,
    opencode, openclaw, claude installé par npm) ne font qu'appeler node,
    ou un .exe du paquet, sur un fichier précis : on lit le shim et on lance
    cette cible directement. None = .cmd qu'on ne sait pas déplier.
    """
    if not chemin.lower().endswith((".cmd", ".bat")):
        return [chemin]
    try:
        m = _CIBLE_SHIM.search(io.open(chemin, encoding="utf-8", errors="replace").read())
    except OSError:
        return None
    if not m:
        return None
    dossier = os.path.dirname(chemin)
    cible = os.path.normpath(os.path.join(dossier, m.group(1)))
    if not os.path.isfile(cible):
        return None
    ext = os.path.splitext(cible)[1].lower()
    if ext == ".exe":
        return [cible]
    if ext in (".js", ".mjs", ".cjs"):
        node = os.path.join(dossier, "node.exe")
        if not os.path.isfile(node):
            node = shutil.which("node")
        if node and node.lower().endswith(".exe"):
            return [node, cible]
    return None


def _lancer(outil, args, **kw):
    """
    Point unique de lancement des outils externes : le texte de la tâche ne
    passe jamais par cmd.exe. Pour un .cmd impossible à déplier (cursor-agent
    passe par PowerShell), cmd.exe reste inévitable : on refuse alors tout
    argument qui contient un caractère qu'il interpréterait.
    """
    chemin = _resoudre(outil)
    argv = _argv_direct(chemin)
    if argv is None:
        if any(_META_CMD.search(str(a)) for a in args):
            return subprocess.CompletedProcess(
                [chemin], 1, "", "non lancé : la tâche contient un caractère que cmd.exe "
                "interpréterait (\" %% ! ^ & | < > ( ) ou saut de ligne) et %s passe par cmd.exe"
                % os.path.basename(chemin))
        argv = [chemin]
    return subprocess.run(argv + [str(a) for a in args], **kw)


def _opencode_reglage():
    """
    (modèle, (hôte, port) | None) du repli OpenCode, lus dans l'environnement.

    JARVIS_OPENCODE_MODELE vide = repli sauté. JARVIS_OPENCODE_PROXY
    (hôte:port), facultatif : un proxy local qui doit répondre avant qu'on
    lance OpenCode, sinon il resterait suspendu sur un fournisseur absent.
    """
    modele = (os.environ.get("JARVIS_OPENCODE_MODELE") or "").strip()
    proxy = (os.environ.get("JARVIS_OPENCODE_PROXY") or "").strip()
    hote, _, port = proxy.rpartition(":")
    return modele, ((hote or "127.0.0.1", int(port)) if port.isdigit() else None)


def _proxy_vivant(adresse):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        s.connect(adresse)
        return True
    except Exception:
        return False
    finally:
        s.close()


def _diff_du_projet(chemin_projet):
    r = subprocess.run(["git", "-C", chemin_projet, "diff"],
                       capture_output=True, text=True, timeout=20)
    return r.stdout


_CLAUDE_VALIDES = {}      # (chemin, mtime_ns, taille) -> bool


def _claude_authentique(chemin):
    """
    Le `claude` trouve est-il VRAIMENT Claude Code ? `claude --version` doit
    dire « Claude Code ».

    Un claude.exe tronque (telechargement interrompu : le runtime Bun sans
    la charge utile) repond « 1.4.0 » — il se comporte
    alors comme Bun, et `bun -p "<phrase>"` EVALUE la phrase comme un script
    JavaScript. La phrase venait de l'utilisateur, mais un outil qui execute
    du texte parle sans le savoir est exactement ce qu'on ne lance pas. Verifie
    donc avant, une fois par version de fichier.
    """
    try:
        st = os.stat(chemin)
        cle = (chemin, st.st_mtime_ns, st.st_size)
    except OSError:
        return False
    if cle not in _CLAUDE_VALIDES:
        try:
            r = subprocess.run((_argv_direct(chemin) or [chemin]) + ["--version"],
                               capture_output=True, encoding="utf-8",
                               errors="replace", timeout=20)
            _CLAUDE_VALIDES[cle] = "Claude Code" in (r.stdout or "")
        except Exception:
            _CLAUDE_VALIDES[cle] = False
    return _CLAUDE_VALIDES[cle]


def executer_delegation(chemin_projet, tache, modele=None, journal=None):
    """
    Essaie, dans l'ordre : l'agent intégré de JARVIS (si `modele` est fourni),
    Claude Code, Codex, OpenCode, OpenClaw, Cursor Agent — tant que les
    précédents échouent. Ne commit JAMAIS. Renvoie un dict :
        {"outil": str|None, "succes": bool, "diff": str, "sortie": str,
         "erreur": str|None, "baseline": str}

    `modele` : appelable `modele(systeme, historique, declarations)` fourni par
    main2.py (voir agent_gemini.py). Sans lui, l'agent intégré est sauté.

    Chaque échec est nommé — jamais un simple "ça n'a pas marché".
    """
    # Meme refus que a l'enregistrement du projet : ce module est appelable
    # directement, sans passer par le registre.
    refus = "cible absente" if not chemin_projet else _refus_cible(chemin_projet)
    if refus:
        return {"outil": None, "succes": False, "diff": "", "sortie": "",
                "erreur": refus, "baseline": ""}
    ok_base, baseline = _assurer_baseline_git(chemin_projet)
    if not ok_base:
        # Sans baseline, le diff mêlerait l'état d'avant et le travail de l'outil.
        return {"outil": None, "succes": False, "diff": "", "sortie": "",
                "erreur": baseline, "baseline": baseline}
    echecs = []

    # ── 0. Agent intégré de JARVIS ───────────────────────────────────────
    # Premier essai : aucune dependance externe, c'est le modele de JARVIS qui
    # travaille dans un bac a sable (agent_fichiers.py : lecture/ecriture
    # confinees au projet, pas de shell, pas de secrets). Demande de
    # l'utilisateur : « JARVIS comme Claude Code, sans besoin de Claude Code ».
    if modele is not None:
        import agent_fichiers
        res = agent_fichiers.executer_agent(chemin_projet, tache, modele, journal=journal)
        if res["succes"]:
            return {"outil": "jarvis", "succes": True, "diff": _diff_du_projet(chemin_projet),
                   "sortie": res["resume"], "erreur": None, "baseline": baseline}
        if res["ecrits"]:
            # Il a DEJA modifie des fichiers : lancer un autre outil par-dessus
            # une moitie de travail melangerait deux mains dans le meme diff.
            return {"outil": "jarvis", "succes": False, "diff": _diff_du_projet(chemin_projet),
                   "sortie": res["resume"],
                   "erreur": "Agent intégré : %s — %d fichier(s) déjà modifié(s) (%s), "
                             "je n'ai pas lancé d'autre outil par-dessus"
                             % (res["erreur"], len(res["ecrits"]), ", ".join(res["ecrits"][:4])),
                   "baseline": baseline}
        echecs.append("Agent intégré : %s" % res["erreur"])

    # ── 1. Claude Code ───────────────────────────────────────────────────
    # -p : mode non interactif. --permission-mode acceptEdits : les EDITIONS
    # de fichiers passent sans confirmation ; tout le reste (Bash...) est
    # REFUSE en mode -p au lieu de rester suspendu (doc officielle, page
    # cli-reference). Claude Code peut donc modifier des fichiers ici, pas
    # lancer de commande shell. Volontairement PAS bypassPermissions, qui
    # leverait toute verification. --max-turns borne la boucle agentique.
    # Le dossier cible passe par le cwd du subprocess (pas d'argument).
    #
    # NON TESTE EN REEL DE BOUT EN BOUT : les flags viennent de la
    # documentation. A valider une fois avec :
    #   python -c "import delegation_code as d; print(d.executer_delegation(
    #       r'<projet>', 'ajoute une ligne de commentaire en haut de README.md'))"
    chemin_claude = _resoudre("claude")
    if not os.path.isabs(chemin_claude):
        echecs.append("Claude Code : introuvable sur le PATH")
    elif not _claude_authentique(chemin_claude):
        echecs.append("Claude Code : le binaire %s ne répond pas comme Claude Code "
                      "(build tronqué ? il répond comme Bun) — non lancé" % chemin_claude)
    else:
        try:
            r0 = _lancer(
                "claude", ["-p", "--permission-mode", "acceptEdits",
                           "--max-turns", str(MAX_TOURS_CLAUDE), tache],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=TIMEOUT_CLAUDE, cwd=chemin_projet)
            if r0.returncode == 0 and r0.stdout.strip():
                return {"outil": "claude", "succes": True, "diff": _diff_du_projet(chemin_projet),
                       "sortie": r0.stdout[-2000:], "erreur": None, "baseline": baseline}
            echecs.append("Claude Code : %s" % (r0.stderr.strip()[:300] or "sortie vide, code %d" % r0.returncode))
        except subprocess.TimeoutExpired:
            echecs.append("Claude Code : timeout après %ds" % TIMEOUT_CLAUDE)
        except FileNotFoundError:
            echecs.append("Claude Code : introuvable sur le PATH")

    # ── 2. Codex ─────────────────────────────────────────────────────────
    fd, chemin_sortie = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    try:
        r = _lancer(
            "codex", ["exec", "-C", chemin_projet, "--sandbox", "workspace-write",
                      "-o", chemin_sortie, tache],
            capture_output=True, text=True, timeout=TIMEOUT_CODEX)
        sortie = ""
        if os.path.exists(chemin_sortie):
            sortie = io.open(chemin_sortie, encoding="utf-8", errors="replace").read()
        if r.returncode == 0 and sortie.strip():
            return {"outil": "codex", "succes": True, "diff": _diff_du_projet(chemin_projet),
                   "sortie": sortie, "erreur": None, "baseline": baseline}
        echecs.append("Codex : %s" % (r.stderr.strip()[:300] or "sortie vide, code %d" % r.returncode))
    except subprocess.TimeoutExpired:
        echecs.append("Codex : timeout après %ds" % TIMEOUT_CODEX)
    except FileNotFoundError:
        echecs.append("Codex : introuvable sur le PATH")
    finally:
        try:
            os.remove(chemin_sortie)
        except OSError:
            pass

    # ── 3. OpenCode (seulement si un modèle est configuré) ─────────────────
    modele_oc, proxy_oc = _opencode_reglage()
    if not modele_oc:
        echecs.append("OpenCode : JARVIS_OPENCODE_MODELE vide, repli non configuré")
    elif proxy_oc and not _proxy_vivant(proxy_oc):
        echecs.append("OpenCode : le proxy %s:%d ne répond pas, filet inutilisable" % proxy_oc)
    else:
        try:
            r2 = _lancer(
                "opencode", ["run", tache, "--dir", chemin_projet,
                             "--model", modele_oc, "--auto"],
                capture_output=True, text=True, timeout=TIMEOUT_OPENCODE)
            if r2.returncode == 0:
                return {"outil": "opencode", "succes": True, "diff": _diff_du_projet(chemin_projet),
                       "sortie": r2.stdout[-2000:], "erreur": None, "baseline": baseline}
            echecs.append("OpenCode : %s" % (r2.stderr.strip()[:300] or "code %d" % r2.returncode))
        except subprocess.TimeoutExpired:
            echecs.append("OpenCode : timeout après %ds" % TIMEOUT_OPENCODE)
        except FileNotFoundError:
            echecs.append("OpenCode : introuvable sur le PATH")

    # ── 4. OpenClaw (dernier filet avant Cursor) ────────────────────────────
    # Après Codex/OpenCode, jamais en 1er choix : OpenClaw sait aussi envoyer
    # des messages, et `openclaw agent` n'a pas de mode restreint aux seules
    # éditions. Ici : CLI locale, fichiers du projet, jamais de commit auto.
    try:
        r3 = _lancer(
            "openclaw", ["agent", "--local", "--message",
                         "%s (projet : %s)" % (tache, chemin_projet), "--json"],
            capture_output=True, text=True, timeout=TIMEOUT_OPENCLAW)
        if r3.returncode == 0:
            return {"outil": "openclaw", "succes": True, "diff": _diff_du_projet(chemin_projet),
                   "sortie": r3.stdout[-2000:], "erreur": None, "baseline": baseline}
        echecs.append("OpenClaw : %s" % (r3.stderr.strip()[:300] or "code %d" % r3.returncode))
    except subprocess.TimeoutExpired:
        echecs.append("OpenClaw : timeout après %ds" % TIMEOUT_OPENCLAW)
    except FileNotFoundError:
        echecs.append("OpenClaw : introuvable sur le PATH")

    # ── 5. Cursor Agent (dernier filet) ──────────────────────────────────
    # -p/--print : sortie scriptable, accès complet write/shell (comportement
    # documenté du flag, pas une supposition). --force : ne bloque pas sur
    # les prompts d'approbation en mode non-interactif — sans lui, la
    # commande reste suspendue en attendant une confirmation que personne
    # ne peut donner ici. Pas de --cwd chez cursor-agent : le dossier cible
    # passe par le `cwd` du subprocess, pas par un argument.
    try:
        r4 = _lancer(
            "cursor-agent", ["-p", "--force", "--sandbox", "enabled", tache],
            capture_output=True, text=True, timeout=TIMEOUT_CURSOR, cwd=chemin_projet)
        if r4.returncode == 0:
            return {"outil": "cursor-agent", "succes": True, "diff": _diff_du_projet(chemin_projet),
                   "sortie": r4.stdout[-2000:], "erreur": None, "baseline": baseline}
        echecs.append("Cursor Agent : %s" % (r4.stderr.strip()[:300] or "code %d" % r4.returncode))
    except subprocess.TimeoutExpired:
        echecs.append("Cursor Agent : timeout après %ds" % TIMEOUT_CURSOR)
    except FileNotFoundError:
        echecs.append("Cursor Agent : introuvable sur le PATH")

    return {"outil": None, "succes": False, "diff": "", "sortie": "",
           "erreur": " | ".join(echecs), "baseline": baseline}
