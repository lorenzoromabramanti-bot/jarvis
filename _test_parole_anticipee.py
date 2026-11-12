"""Tests de parole_anticipee.py (sans réseau ni audio) : venv\\Scripts\\python.exe _test_parole_anticipee.py"""
import asyncio
import time

from parole_anticipee import Anticipation, premiere_phrase, texte_en_flux


def test_premiere_phrase():
    assert premiere_phrase("Salut Alex ! Ça") == "Salut Alex !"
    assert premiere_phrase("Oui. Il fait beau aujourd'hui. Et") == "Oui. Il fait beau aujourd'hui."  # « Oui. » trop court seul
    assert premiere_phrase("Il fait 3.5 degrés") is None  # un point dans un nombre n'est pas une fin de phrase
    assert premiere_phrase('Je lance ça {"action": "x"}. Voilà. ') is None  # jamais de JSON à voix haute
    # jamais de faux appel d'outil (pseudo-XML) à voix haute, même avec une virgule assez loin pour partir
    faux = ('<dots_function_call>\ninvoke name="voir_ecran">\n<parameter name="instruction">regarde l\'écran pour voir '
            'quelle musique est en train de jouer (sur Spotify, Deezer, YouTube)\n</parameter>\n</invoke>')
    assert premiere_phrase(faux) is None
    assert premiere_phrase("Je regarde ça tout de suite. " + faux) == "Je regarde ça tout de suite."  # le vrai texte avant part
    assert premiere_phrase("Bonjour, je suis là.") is None  # la phrase n'est pas encore finie dans le flux
    assert premiere_phrase("Bonjour, je suis là.\n") == "Bonjour, je suis là."
    assert premiere_phrase("\n Salut tout le monde ! Oui") == "Salut tout le monde !"
    # Phrase longue : départ à la 1re pause après 50 caractères, jamais sur une virgule de nombre.
    assert premiere_phrase("La mer est salée parce que, depuis des milliards d'années, l'érosion") == \
        "La mer est salée parce que, depuis des milliards d'années,"
    assert premiere_phrase("Oui, alors en gros il fait 13,5 degrés dehors et") is None
    assert premiere_phrase("Le ciel est bleu à cause de la diffusion Rayleigh : les molécules") == \
        "Le ciel est bleu à cause de la diffusion Rayleigh :"
    assert premiere_phrase("Oui, c'est ça. Et puis, plus tard dans la journée, il") == "Oui, c'est ça."


def faux_parler(dits, coupe=False):
    async def parler(texte, memoire=True):
        assert memoire is False  # la mémoire reçoit la réponse entière ailleurs, une seule fois
        dits.append(texte)
        await asyncio.sleep(0)
        return coupe
    return parler


async def test_anticipation():
    dits = []
    a = Anticipation(faux_parler(dits))
    a.morceau("Salut")
    assert a.tache is None
    a.morceau("Salut Alex ! Il")
    a.morceau("Salut Alex ! Il fait beau. ")  # déjà lancée : ignorée
    assert await a.reste("Salut Alex ! Il fait beau.") == "Il fait beau."
    assert dits == ["Salut Alex !"]

    coupe = Anticipation(faux_parler([], coupe=True))
    coupe.morceau("Salut Alex ! Il")
    assert await coupe.reste("Salut Alex ! Il fait beau.") == ""  # on lui a coupé la parole

    autre = Anticipation(faux_parler([]))
    autre.morceau("Salut Alex ! Il")
    assert await autre.reste("Bonjour. Réponse du secours.") == "Bonjour. Réponse du secours."

    rien = Anticipation(faux_parler([]))
    assert await rien.reste("Réponse locale.") == "Réponse locale."

    s = Anticipation(faux_parler([]))
    assert s.suite("Bonjour.") == "Bonjour."  # rien d'anticipé : tout reste à dire
    s.morceau("Salut Alex ! Il")
    assert s.suite("Salut Alex ! Il fait beau.") == "Il fait beau."  # sans attendre la 1re phrase
    assert s.suite("Autre réponse.") == "Autre réponse."
    await s.tache


async def test_flux():
    dits = []
    a = Anticipation(faux_parler(dits))
    texte, dernier = await texte_en_flux(lambda: iter(["Salut ", "Alex ! ", "Ça va ?"]), lambda m: m, a)
    assert (texte, dernier) == ("Salut Alex ! Ça va ?", "Ça va ?")
    assert dits == ["Salut Alex !"] and await a.reste(texte) == "Ça va ?"

    def casse_tout_de_suite():
        raise RuntimeError("502")
    try:
        await texte_en_flux(casse_tout_de_suite, lambda m: m, Anticipation(faux_parler([])))
        raise AssertionError("aurait dû lever")
    except RuntimeError:
        pass  # rien n'a été dit : le cerveau suivant peut prendre la main

    def casse_apres():
        yield "Salut Alex ! "
        raise RuntimeError("coupure")
    assert (await texte_en_flux(casse_apres, lambda m: m, Anticipation(faux_parler([]))))[0] == "Salut Alex ! "

    def trop_lent_apres():
        yield "Salut Alex ! "
        time.sleep(0.6)
        yield "jamais lu"
    debut = time.perf_counter()
    assert (await texte_en_flux(trop_lent_apres, lambda m: m, Anticipation(faux_parler([])),
                                delai=0.2, delai_suite=0.2))[0] == "Salut Alex ! "  # la voix est partie : on garde le début
    assert time.perf_counter() - debut < 0.5
    # La voix partie avant `delai`, la suite a son propre délai : réponse entière malgré 0,6 s de pause.
    assert (await texte_en_flux(trop_lent_apres, lambda m: m, Anticipation(faux_parler([])),
                                delai=0.2))[0] == "Salut Alex ! jamais lu"

    def trop_lent():
        time.sleep(0.4)
        yield "trop tard"
    try:
        await texte_en_flux(trop_lent, lambda m: m, Anticipation(faux_parler([])), delai=0.1)
        raise AssertionError("aurait dû lever")
    except TimeoutError:
        pass

    assert (await texte_en_flux(lambda: iter(["a", None, "b"]), lambda m: m))[0] == "ab"  # sans anticipation


if __name__ == "__main__":
    test_premiere_phrase()
    asyncio.run(test_anticipation())
    asyncio.run(test_flux())
    print("OK : parole anticipée")
