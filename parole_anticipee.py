"""Parole anticipée : JARVIS dit la 1re phrase d'une réponse vocale pendant que le modèle écrit la suite.

Mesuré le 23/10/2026 : la réponse entière arrivait en ~3,7 s avant le premier mot. En flux, la 1re phrase
part dès qu'elle est écrite (gain attendu ~2 s). Réglage « parole_anticipee » (true par défaut) dans
jarvis_config.json pour revenir à l'ancien comportement.

Utilisé par main2.py : demander_omniroute et le chemin Gemini de demander_ia lisent en flux quand une
Anticipation est active (canal voix, PC, pas Discord) ; traiter_reponse_ia dit ensuite la suite.
"""
import asyncio
import re

import appels_outils

_FIN_DE_PHRASE = re.compile(r"[.!?…](?=\s)")
_PAUSE = re.compile(r"[,;:](?=\s)")


def premiere_phrase(texte, mini=12, pause_mini=50):
    """Début de `texte` jusqu'à la 1re fin de phrase suivie d'un blanc, d'au moins `mini` caractères.

    Phrase longue (06/11 : souvent 150 caractères, soit 2,6 s de synthèse) : on part à la 1re pause
    (virgule, point-virgule, deux-points) placée après `pause_mini` caractères.
    Rien après le début d'un bloc d'action JSON (« { ») ni d'un faux appel d'outil (pseudo-XML, voir
    appels_outils.py) : ils ne sont jamais dits à voix haute.
    None tant que rien n'est prêt.
    """
    avant_action = appels_outils.avant_appel(texte).split("{", 1)[0]
    for m in _FIN_DE_PHRASE.finditer(avant_action):
        if m.end() >= mini:
            return avant_action[:m.end()].strip()
    for m in _PAUSE.finditer(avant_action):
        if m.end() >= pause_mini:
            return avant_action[:m.end()].strip()
    return None


class Anticipation:
    """Suit une réponse qui arrive en flux et confie sa 1re phrase à `parler` dès qu'elle est complète."""

    def __init__(self, parler):
        self._parler = parler
        self.dit = ""      # ce qui a déjà été confié à la voix
        self.tache = None  # la tâche parler(dit), à attendre avant de dire la suite

    def morceau(self, texte_jusquici):
        if self.tache is None:
            phrase = premiere_phrase(texte_jusquici)
            if phrase:
                self.dit = phrase
                self.tache = asyncio.ensure_future(self._parler(phrase, memoire=False))

    def suite(self, texte_complet):
        """Ce qu'il reste à dire après la phrase déjà confiée à la voix, sans attendre qu'elle soit dite.

        Si la réponse finale ne commence pas par cette phrase (cerveau de secours), elle est renvoyée entière.
        main2 la passe à parler(..., apres=self.tache), qui prépare sa voix pendant la 1re phrase.
        """
        if self.tache is None or not texte_complet.startswith(self.dit):
            return texte_complet
        return texte_complet[len(self.dit):].strip()

    async def reste(self, texte_complet):
        """Attend la fin de la 1re phrase, puis renvoie la suite (vide si on lui a coupé la parole)."""
        if self.tache is not None and await self.tache:
            return ""
        return self.suite(texte_complet)


async def texte_en_flux(ouvrir, extraire, anticipation=None, delai=None, delai_suite=60.0):
    """Lit un flux synchrone (SDK OpenAI ou Gemini) dans un fil, sans figer la boucle asyncio.

    `ouvrir()` renvoie l'itérateur de morceaux, `extraire(morceau)` leur texte (ou None).
    Renvoie (texte complet, dernier morceau).

    `delai` : temps maximal avant que la voix démarre (ou, sans anticipation, avant la fin) ; dépassé,
    TimeoutError, et l'appelant passe au cerveau suivant au lieu de rester muet (06/11 : une réponse
    d'OmniRoute a mis 74 s). Une fois la voix partie, la suite a `delai_suite`. Si la voix a déjà commencé
    et que le flux casse ou traîne, renvoie le texte reçu jusque-là au lieu de lever : sinon un cerveau de
    secours dirait autre chose juste après la 1re phrase.
    """
    boucle = asyncio.get_running_loop()
    file = asyncio.Queue()
    fin = object()
    recu, dernier = [], [None]
    parti = asyncio.Event()  # la 1re phrase est confiée à la voix

    def lire():
        try:
            for m in ouvrir():
                boucle.call_soon_threadsafe(file.put_nowait, m)
        except Exception as e:  # remise à la boucle, levée par consommer()
            boucle.call_soon_threadsafe(file.put_nowait, e)
        finally:
            boucle.call_soon_threadsafe(file.put_nowait, fin)

    async def consommer():
        while (m := await file.get()) is not fin:
            if isinstance(m, Exception):
                raise m
            dernier[0] = m
            recu.append(extraire(m) or "")
            if anticipation is not None:
                anticipation.morceau("".join(recu))
                if anticipation.tache is not None:
                    parti.set()

    boucle.run_in_executor(None, lire)  # comme asyncio.to_thread ; après un délai dépassé, le fil finit seul
    lecture = asyncio.ensure_future(consommer())
    attente = asyncio.ensure_future(parti.wait())
    try:
        fait, _ = await asyncio.wait({lecture, attente}, timeout=delai, return_when=asyncio.FIRST_COMPLETED)
        if not fait:
            raise TimeoutError(f"rien à dire après {delai} s")
        await asyncio.wait_for(lecture, timeout=delai_suite)  # déjà finie : rend son résultat ou son erreur
    except Exception:
        lecture.cancel()
        if anticipation is not None and anticipation.tache is not None and recu:
            return "".join(recu), dernier[0]
        raise
    finally:
        attente.cancel()
    return "".join(recu), dernier[0]
