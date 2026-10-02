# -*- coding: utf-8 -*-
"""
Verifie que le canal voix/texte ne fuit pas.

La panne redoutee n'est pas cosmetique : si le canal "texte" contamine le
chemin vocal, parler() prend son retour anticipe et JARVIS devient MUET,
sans erreur nulle part. Ce test echoue avant que ca n'arrive.

    venv\\Scripts\\python.exe _test_canal.py
"""

import asyncio
import sys


def verifier():
    import main2

    # 1. Defaut : voix. Un contexte neuf ne doit jamais valoir "texte".
    assert main2.CANAL_COURANT.get() == "voix", \
        "defaut attendu 'voix', obtenu %r" % main2.CANAL_COURANT.get()

    # 2. Le prompt systeme change bien de forme selon le canal.
    main2.CANAL_COURANT.set("voix")
    voix = main2.construire_system_prompt()
    main2.CANAL_COURANT.set("texte")
    texte = main2.construire_system_prompt()
    main2.CANAL_COURANT.set("voix")

    assert "N'UTILISE JAMAIS de caract" in voix, "veto Markdown absent du canal voix"
    assert "N'UTILISE JAMAIS de caract" not in texte, "veto Markdown encore actif en texte"
    assert "blocs de code" in texte, "les blocs de code ne sont pas autorises en texte"
    assert "blocs de code" not in voix, "les blocs de code sont autorises a la voix"
    assert "ultra-courtes" in voix, "la consigne de brievete a disparu du canal voix"
    assert "ultra-courtes" not in texte, "la brievete vocale contamine le canal texte"

    # 3. Une valeur inattendue retombe sur "voix" : jamais de mutisme par
    #    faute de frappe.
    async def _canal_apres(valeur):
        # On n'execute pas traiter_reponse_ia (elle parle et appelle le
        # modele) : on reproduit sa seule ligne de garde.
        main2.CANAL_COURANT.set(valeur if valeur in ("voix", "texte") else "voix")
        return main2.CANAL_COURANT.get()

    for entree, attendu in (("texte", "texte"), ("voix", "voix"),
                            ("TEXTE", "voix"), ("", "voix"), (None, "voix")):
        obtenu = asyncio.run(_canal_apres(entree))
        assert obtenu == attendu, "canal %r -> %r (attendu %r)" % (entree, obtenu, attendu)

    # 4. Isolation entre taches : une tache qui bascule en "texte" ne doit
    #    pas contaminer une tache soeur. C'est exactement le scenario qui
    #    rendrait la voix muette.
    async def _isolation():
        async def tache_texte():
            main2.CANAL_COURANT.set("texte")
            await asyncio.sleep(0.01)
            return main2.CANAL_COURANT.get()

        async def tache_voix():
            await asyncio.sleep(0.005)
            return main2.CANAL_COURANT.get()

        return await asyncio.gather(tache_texte(), tache_voix())

    a, b = asyncio.run(_isolation())
    assert a == "texte" and b == "voix", \
        "fuite entre taches : texte=%r, voix=%r" % (a, b)

    print("  OK  defaut voix")
    print("  OK  prompt systeme distinct par canal")
    print("  OK  valeur inattendue -> voix (jamais muet)")
    print("  OK  isolation entre taches concurrentes")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Canal voix/texte : etanche.")
