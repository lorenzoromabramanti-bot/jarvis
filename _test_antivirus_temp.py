"""Règle « lancé depuis un dossier temporaire » : un composant du chemin, pas une sous-chaîne (faux positif uv du 16/10)."""
from antivirus_scanner import lance_depuis_temp

# Vrais dossiers temporaires : détectés.
assert lance_depuis_temp("evil.exe", r"C:\Users\Alex\AppData\Local\Temp\evil.exe")
assert lance_depuis_temp("x.bat", r"C:\Windows\TEMP\sub\x.bat")
assert lance_depuis_temp("a.exe", "/tmp/a.exe")

# Le faux positif d'origine : « .tmpHRMK5Y » d'uv contient « tmp » sans être un dossier tmp.
assert not lance_depuis_temp("python.exe", r"C:\Users\Alex\AppData\Local\uv\cache\builds-v0\.tmpHRMK5Y\Scripts\python.exe")
assert not lance_depuis_temp("word.exe", r"C:\Users\Alex\Templates\word.exe")
assert not lance_depuis_temp("tempo.exe", r"C:\Games\tempo.exe")

# Extension : seuls .exe et .bat comptent ; chemin ou nom vides ne plantent pas.
assert not lance_depuis_temp("notes.txt", r"C:\Temp\notes.txt")
assert not lance_depuis_temp("", "")
assert not lance_depuis_temp(None, None)

print("OK _test_antivirus_temp")
