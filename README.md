# Dvojpanel

Dvoupanelový správce souborů pro Windows ve stylu Norton/Total Commanderu, který umí spouštět vlastní Python skripty nad vybranými soubory.

Používá **jen standardní knihovnu Pythonu** (tkinter). Nic se neinstaluje, stačí Python 3.10+.

## Spuštění

```
pythonw dvojpanel.py
```

`pythonw` spustí program bez konzolového okna. Pro ladění lze použít `python dvojpanel.py`.

### Spouštění z hlavního panelu (Windows 11)

Windows neumí připnout na hlavní panel přímo `.py` soubor, proto program vytvoří zástupce:

1. Spusť program poprvé, např. přes Win+R: `pythonw "C:\cesta\k\dvojpanel.py"`.
2. Menu **Soubor → Vytvořit zástupce v nabídce Start**.
3. Start → napiš „Dvojpanel“ → pravým tlačítkem → **Připnout na hlavní panel**.

Zástupce spouští `pythonw.exe` aktuálního Pythonu, takže se běžící okno sloučí s připnutou ikonou. Po aktualizaci Pythonu nebo přesunu složky programu vytvoř zástupce znovu (přepíše se) a připni ho znovu.

## Ovládání

| Klávesa | Akce |
|---|---|
| Tab | přepnutí panelu |
| Enter / dvojklik | otevřít složku nebo soubor |
| Backspace | o úroveň výš |
| Mezerník / Insert | označit / odznačit položku a posunout kurzor dolů (jako v NC) |
| Ctrl+A | označit vše; podruhé označení zruší |
| Ctrl+klik, Shift+šipky | výběr více položek myší / klávesnicí |
| F2 | přejmenovat |
| F3 / F4 | otevřít / upravit v Notepadu |
| F5 / F6 | kopírovat / přesunout do druhého panelu |
| F7 | nová složka |
| F8 | smazat do koše (na síťovém disku trvale, program varuje) |
| F9 | nabídka nástrojů |
| Ctrl+D | oblíbené složky |
| Ctrl+S | porovnat a synchronizovat složky |
| Esc | přerušit probíhající kopírování / přesun |
| Ctrl+R / Ctrl+Q | obnovit / konec |

Označené položky (červeně) mají přednost před výběrem: F5, F6, F8 i nástroje pracují s označenými, a pokud žádné nejsou, s vybranými. Po úspěšném kopírování nebo přesunu se označení zruší, při přechodu do jiné složky také.

U souborů od 16 MB se při kopírování ukazuje průběh v procentech ve stavovém řádku. Soubor se nejdřív zapisuje do dočasného souboru `*.dvojpanel-tmp` a teprve po dokončení nahradí cíl, takže přerušené nebo selhané kopírování nikdy nepoškodí existující soubor v cíli.

## Porovnání a synchronizace složek

**Příkazy → Porovnat a synchronizovat složky** (Ctrl+S) porovná složky z levého a pravého panelu (cesty lze v okně změnit).

- **Porovnat obsah binárně** porovná soubory bajt po bajtu. Bez této volby se porovnává jen velikost a čas změny (tolerance 2 s).
- **Včetně podsložek** projde celý strom. Složka, která je jen na jedné straně, se ukáže jako jeden řádek a zkopíruje se celá.
- Výchozí akce: co je jen na jedné straně, se zkopíruje na druhou; u rozdílných souborů vyhrává novější. Rozdílné soubory se stejným časem a konflikty soubor × složka zůstanou bez akce.
- Akci u vybraných řádků lze změnit klávesami → / ← / mezerník nebo tlačítky.
- **Synchronizovat** jen kopíruje, nic nemaže. Před spuštěním vypíše soubory, které se přepíšou. Po dokončení se složky porovnají znovu.

## Oblíbené složky

Menu **Oblíbené** (nebo Ctrl+D) otevře uloženou složku v aktivním panelu. **Přidat aktuální složku** uloží složku aktivního panelu, **Odebrat** ji smaže ze seznamu. Nedostupná síťová složka nezablokuje okno, program jen ohlásí chybu.

Seznam je v `oblibene.json` vedle `dvojpanel.py` (lokální, není v Gitu) a lze ho upravit i ručně (**Upravit oblibene.json**, pak **Načíst oblíbené znovu**):

```json
{
  "oblibene": [
    {"nazev": "Projekt 1234", "cesta": "\\\\server\\projekty\\P-1234"},
    {"nazev": "Skripty", "cesta": "%USERPROFILE%/Skripty"}
  ]
}
```

`cesta` je povinná, `nazev` volitelný (jinak se v menu ukáže cesta). Platí stejná pravidla pro cesty jako u nástrojů.

## Nástroje

Nástroje se definují v `nastroje.json` vedle `dvojpanel.py`. Při prvním spuštění se soubor vytvoří ze šablony `nastroje.example.json`. Upravit ho lze z menu **Nástroje → Upravit nastroje.json** a pak **Načíst nástroje znovu**.

`nastroje.json` obsahuje lokální cesty, proto není v Gitu. Šablona ano.

```json
{
  "nastroje": [
    {
      "nazev": "Windchill: dotaz na číslo dílu → XLSX",
      "skript": "%USERPROFILE%/Skripty/windchill/dotaz.py",
      "python": "%USERPROFILE%/Skripty/windchill/.venv/Scripts/python.exe",
      "argumenty": ["{zadat:Čísla dílů (PN), více oddělit mezerou}", "--vystup", "xlsx"],
      "zobrazit_slozku": "%USERPROFILE%/Skripty/windchill/vystupy"
    }
  ]
}
```

| Klíč | Povinný | Význam |
|---|---|---|
| `nazev` | ano | text v menu |
| `skript` | ano | cesta ke skriptu (`.py`, `.bat`, `.cmd`, `.exe`); relativní cesta je vůči složce programu |
| `argumenty` | ne | seznam argumentů, může obsahovat zástupné symboly |
| `pripony` | ne | povolené přípony vybraných souborů (a `{soubor_cil}`, pokud ho nástroj používá), např. `[".xlsx"]` |
| `pracovni_slozka` | ne | pracovní složka; výchozí je složka skriptu |
| `zobrazit_slozku` | ne | po úspěšném doběhnutí se tato složka otevře v druhém panelu |
| `python` | ne | jiný interpret, např. Python z virtuálního prostředí |

Cesty mohou používat `/` i `\` (v JSONu se zpětné lomítko musí zdvojit) a proměnné jako `%USERPROFILE%`.

### Zástupné symboly

| Symbol | Nahradí se |
|---|---|
| `{soubory}` | všemi vybranými soubory v aktivním panelu (každý jako samostatný argument; musí stát v argumentu sám) |
| `{soubor}` | souborem pod kurzorem v aktivním panelu |
| `{soubor_cil}` | souborem pod kurzorem ve druhém panelu |
| `{slozka}` | složkou aktivního panelu |
| `{cil}` | složkou druhého panelu |
| `{skript_slozka}` | složkou skriptu |
| `{zadat:Popisek}` | hodnotou, na kterou se program zeptá v dialogu |

Dva soubory ve správném pořadí (např. cílový sešit a zdrojový export) předáš tak, že jeden máš pod kurzorem v aktivním panelu a druhý ve druhém panelu:

```json
{
  "nazev": "Windchill: přehled PN podle SAP (kontrola)",
  "skript": "%USERPROFILE%/Skripty/windchill/aktualizuj_ze_sap.py",
  "python": "%USERPROFILE%/Skripty/windchill/.venv/Scripts/python.exe",
  "argumenty": ["{soubor}", "{soubor_cil}", "--jen-kontrola"],
  "pripony": [".xlsx"]
}
```

### Pravidla pro skripty

- Výstup (`print`) i chyby se zobrazují v dolním panelu. Výstup je v UTF-8.
- Skript nesmí čekat na `input()`. Vstup je zavřený, takže `input()` skončí chybou místo zamrznutí. Hodnoty předávej argumenty nebo přes `{zadat:...}`.
- Návratový kód 0 znamená úspěch, cokoli jiného chybu.
- Běží vždy jen jeden nástroj; zastavit ho lze v menu Nástroje.
- Nástroj dostane proměnnou prostředí `DVOJPANEL` (verze programu), podle které pozná, že běží z Dvojpanelu. Např. `.bat`, který po dvojkliku čeká (`pause`/`timeout`), může čekání přeskočit: `if defined DVOJPANEL exit /b 0`. Jinak `timeout` vypíše „Input redirection is not supported“ (vstup je zavřený) a skončí, výsledek nástroje to neovlivní.

## Licence

Soukromý projekt.
