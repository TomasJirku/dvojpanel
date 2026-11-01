# CLAUDE.md – kontext pro Claude Code

## Projekt
Dvojpanel: dvoupanelový správce souborů pro Windows (tkinter) se spouštěním vlastních skriptů.
Jeden soubor `dvojpanel.py`, verze v `__version__`.

## Tvrdá omezení
- **Jen standardní knihovna Pythonu.** Cílový firemní PC má oficiální Python, ale nelze instalovat balíčky ani jiný software. Žádný `pip install`, žádné .exe balení.
- Cílová platforma Windows, Python 3.14. Kód musí jít aspoň importovat i mimo Windows (Windows API jen za `IS_WINDOWS`, `ctypes` importovat lokálně).
- UI texty česky, komentáře a identifikátory v kódu anglicky (klíče v `nastroje.json` jsou česky kvůli uživateli).
- Žádná tichá ztráta dat: mazání do koše, při kolizích se ptát, chyby vždy zobrazit.

## Konvence
- `nastroje.json` je lokální a v `.gitignore`; změny formátu promítnout do `nastroje.example.json` a README.
- Každá změna funkčnosti: zvýšit `__version__` a doplnit `CHANGELOG.md`.
- Dlouhé operace ve vlákně, komunikace s GUI jen přes `self.jobs` (queue) a `poll_jobs`.

## Testování
GUI nelze testovat bez displeje. Logiku (`transfer_worker`, `build_command`, `load_tools`, `is_inside`) lze testovat
s podvrženým modulem `tkinter` v `sys.modules`. Finální ověření ručně na Windows na testovací složce.
