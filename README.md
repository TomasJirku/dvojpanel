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
| F2 | přejmenovat přímo v řádku (také pomalý druhý klik na jméno vybrané položky) |
| F3 / F4 | otevřít / upravit v Notepadu |
| F5 / F6 | kopírovat / přesunout do druhého panelu |
| F7 | nová složka |
| F8 | smazat do koše (na síťovém disku trvale, program varuje) |
| F9 | nabídka nástrojů |
| F1 | nápověda (ovládání a vysvětlení všech nástrojů) |
| Ctrl+D | oblíbené složky |
| Ctrl+S | porovnat a synchronizovat složky |
| Ctrl+U | prohodit složky levého a pravého panelu |
| Esc | přerušit probíhající kopírování / přesun |
| Ctrl+R / Ctrl+Q | obnovit / konec |

Panely mají sloupce Název, Typ (druh souboru podle Windows, např. „List Microsoft Excelu“), Velikost a Změněno. Klik na záhlaví řadí, druhý klik obrátí směr; sloupec, podle kterého se řadí, má v záhlaví `▲` (vzestupně) nebo `▼` (sestupně). Složky jsou vždy nahoře.

Přejmenování v řádku: předvybere se jméno bez přípony, Enter nebo klik jinam potvrdí, Esc zruší. Existující položku nikdy nepřepíše, program ohlásí chybu.

### Přetažení myší

Položky lze přetáhnout myší **do druhého panelu** (do jeho složky) nebo **na složku** v kterémkoli panelu, včetně `[..]`. Přetažení kopíruje, se **Shiftem** přesouvá. Platí totéž co u F5 / F6: potvrzení, dotaz při kolizích, průběh v procentech. Přetahují se označené položky, pokud tah začne na označené, jinak výběr. Esc přetažení zruší. Funguje jen uvnitř Dvojpanelu, ne z/do Průzkumníku.

Označené položky (červeně) mají přednost před výběrem: F5, F6, F8 i nástroje pracují s označenými, a pokud žádné nejsou, s vybranými. Po úspěšném kopírování nebo přesunu se označení zruší, při přechodu do jiné složky také.

### Když položka v cíli už existuje

F5 / F6 (i přetažení) se zeptá, co s položkami, které v cíli už jsou. Soubory, které jsou v cíli **novější** než kopírované, vypíše i s datem obou. Volby:

| Volba | Co udělá |
|---|---|
| Přepsat jen starší (výchozí) | nahradí jen soubory, které jsou v cíli starší; novější a stejně staré (tolerance 2 s) nechá |
| Přepsat vše | nahradí všechny existující soubory, i novější |
| Přeskočit existující | zkopíruje jen to, co v cíli není |
| Storno | nic |

Složky se sloučí a volba platí pro každý soubor uvnitř. Při přesunu zůstanou nepřepsané soubory ve zdroji, nic se neztratí.

U souborů od 16 MB se při kopírování ukazuje průběh v procentech ve stavovém řádku. Soubor se nejdřív zapisuje do dočasného souboru `*.dvojpanel-tmp` a teprve po dokončení nahradí cíl, takže přerušené nebo selhané kopírování nikdy nepoškodí existující soubor v cíli.

## Porovnání a synchronizace složek

**Příkazy → Porovnat a synchronizovat složky** (Ctrl+S) porovná složky z levého a pravého panelu (cesty lze v okně změnit).

- **Porovnat obsah binárně** porovná soubory bajt po bajtu. Bez této volby se porovnává jen velikost a čas změny (tolerance 2 s).
- **Včetně podsložek** projde celý strom. Složka, která je jen na jedné straně, se ukáže jako jeden řádek a zkopíruje se celá.
- Výchozí akce: co je jen na jedné straně, se zkopíruje na druhou; u rozdílných souborů vyhrává novější. Rozdílné soubory se stejným časem a konflikty soubor × složka zůstanou bez akce.
- Akci u vybraných řádků lze změnit klávesami → / ← / mezerník nebo tlačítky.
- **Synchronizovat** jen kopíruje, nic nemaže. Před spuštěním vypíše soubory, které se přepíšou. Po dokončení se složky porovnají znovu.

## Oblíbené složky

Lišta nad panely ukazuje oblíbené složky jako tlačítka: klik otevře složku v aktivním panelu, pravé tlačítko nabídne otevření ve druhém panelu nebo odebrání, **+ Přidat** uloží složku aktivního panelu. Při úzkém okně se tlačítka zalomí do více řádků. Skrýt ji lze v menu **Oblíbené → Zobrazit lištu oblíbených**.

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

## Nastavení (dvojpanel.json)

`dvojpanel.json` vedle `dvojpanel.py` (lokální, není v Gitu) určuje výchozí složky obou panelů při spuštění a zobrazení lišty oblíbených. Nejsnáz ho vytvoříš přes **Soubor → Uložit aktuální složky jako výchozí**, ručně přes **Soubor → Upravit dvojpanel.json** a pak **Načíst nastavení znovu**:

```json
{
  "levy_panel": "C:/Projects/MojeAplikace/Windchill/vystupy",
  "pravy_panel": "\\\\server\\projekty",
  "lista_oblibenych": true
}
```

Všechny klíče jsou volitelné, výchozí je domovská složka (`%USERPROFILE%`) a zobrazená lišta. Cesty jako u nástrojů. Nedostupná složka nezablokuje start, program jen ohlásí chybu a panel zůstane v domovské složce.

## Nástroje

Nápověda programu (F1, téma **Moje nástroje**) popisuje každý načtený nástroj: na co se ptá, s čím pracuje, jestli dělá náhled a kam ukládá.

Nástroje se definují v `nastroje.json` vedle `dvojpanel.py`. Při prvním spuštění se soubor vytvoří ze šablony `nastroje.example.json`. Upravit ho lze z menu **Nástroje → Upravit nastroje.json** a pak **Načíst nástroje znovu**.

`nastroje.json` obsahuje lokální cesty, proto není v Gitu. Šablona ano.

### Nástroje dodané projektem (`vlozit`)

Projekt se skripty si může nástroje pro Dvojpanel udržovat sám ve vlastním souboru v Gitu, např. Windchill v `dvojpanel_nastroje.json`. `nastroje.json` ho jen vloží; po `git pull` v projektu stačí **Načíst nástroje znovu** a nové nástroje jsou v menu, nic se nekopíruje ani nepřepisuje.

Šablona už vkládá `C:/Projects/MojeAplikace/Windchill/dvojpanel_nastroje.json`, takže nový `nastroje.json` ho má sám. Když je projekt jinde (nebo starší `nastroje.json` odkaz nemá), nahoře v menu Nástroje je ⚠ a stačí **Nástroje → Přidat nástroje projektu…**: vybereš `dvojpanel_nastroje.json` a program ho zapíše do `"vlozit"` sám, zbytek souboru nechá. Ručně to vypadá takto:

```json
{
  "vlozit": ["C:/Projects/MojeAplikace/Windchill/dvojpanel_nastroje.json"],
  "nastroje": [
    {"nazev": "Můj vlastní skript", "skript": "%USERPROFILE%/skripty/muj.py"}
  ]
}
```

- Vložený soubor má stejný tvar (`"nastroje": [...]`). **Relativní cesty v něm (`skript`, `python`, `pracovni_slozka`, `zobrazit_slozku`) jsou vůči jeho složce**, takže funguje v každé kopii projektu.
- `"skupina"` na úrovni souboru je výchozí podmenu pro jeho nástroje, každý nástroj může mít vlastní.
- Chybějící nebo chybný vložený soubor program ohlásí (v menu nahoře a ve výstupu), ostatní nástroje fungují dál. Vložený soubor nesmí dál vkládat.
- Vlastní nástroje v `nastroje.json` jsou v menu první, vložené za nimi.

Jeden nástroj:

```json
{
  "nazev": "Dotaz na čísla dílů → XLSX",
  "skupina": "Windchill – index a dotazy",
  "skript": "dotaz.py",
  "python": ".venv/Scripts/python.exe",
  "argumenty": ["{zadat:Čísla dílů (PN), více oddělit mezerou}", "--vystup", "xlsx"],
  "zobrazit_slozku": "vystupy"
}
```

| Klíč | Povinný | Význam |
|---|---|---|
| `nazev` | ano | text v menu |
| `popis` | ne | vysvětlení pro nápovědu (F1 → Moje nástroje) |
| `skript` | ano | cesta ke skriptu (`.py`, `.bat`, `.cmd`, `.exe`); relativní cesta je vůči složce programu (ve vloženém souboru vůči jeho složce) |
| `argumenty` | ne | seznam argumentů, může obsahovat zástupné symboly |
| `pripony` | ne | povolené přípony souborů z panelů (`{soubory}`, `{soubor}`, `{soubor_cil}`) a filtr dialogů `{vybrat_soubor}` bez vlastních přípon, např. `[".xlsx"]` |
| `pracovni_slozka` | ne | pracovní složka; výchozí je složka skriptu |
| `zobrazit_slozku` | ne | po úspěšném doběhnutí se tato složka otevře v druhém panelu |
| `python` | ne | jiný interpret, např. Python z virtuálního prostředí |
| `skupina` | ne | podmenu v menu Nástroje / F9 |
| `nahled` | ne | argument(y) pro zkušební běh, např. `"--jen-kontrola"`: viz Náhled a potvrzení |

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
| `{vybrat_soubor:Popisek\|.xlsx}` | souborem vybraným v okně „Otevřít“ (popisek v titulku, za `\|` povolené přípony) |
| `{ulozit_soubor:Popisek\|.xlsx}` | cestou z okna „Uložit jako“ (přípona se doplní, na přepsání se zeptá Windows) |

Dva soubory ve správném pořadí (např. cílový sešit a zdrojový export) předáš tak, že jeden máš pod kurzorem v aktivním panelu a druhý ve druhém panelu:

```json
{
  "nazev": "Aktualizovat podle SAP (přehled pod kurzorem, export ve druhém panelu)",
  "skript": "aktualizuj_ze_sap.py",
  "python": ".venv/Scripts/python.exe",
  "argumenty": ["{soubor}", "{soubor_cil}"],
  "pripony": [".xlsx"]
}
```

Spolehlivější je výběr dialogem: popisek přesně řekne, který soubor se čeká, a nezáleží na kurzoru. Dialog začne ve složce aktivního panelu, příště tam, kde byl tento soubor vybrán naposledy (do zavření programu). Stejný symbol se stejným popiskem použitý dvakrát se ptá jen jednou.

```json
{
  "nazev": "Aktualizovat podle SAP (výběr souborů)",
  "skript": "aktualizuj_ze_sap.py",
  "python": ".venv/Scripts/python.exe",
  "argumenty": ["{vybrat_soubor:Cílový přehled PN|.xlsx}", "{vybrat_soubor:Export ze SAP|.xlsx}"],
  "nahled": "--jen-kontrola"
}
```

### Náhled a potvrzení (`nahled`)

Nástroj, který něco zapisuje, nemusí mít dvě verze „kontrola“ a „aktualizovat“. S `"nahled": "--jen-kontrola"` (nebo seznamem argumentů):

1. Program spustí skript s argumenty a navíc `--jen-kontrola`. Výstup je v dolním panelu.
2. Doběhne-li náhled s kódem 0 nebo 2 (2 = něco vyžaduje pozornost), zeptá se **Provést změny naostro?**
3. Po potvrzení spustí skript znovu bez `--jen-kontrola`. Na nic se znovu neptá (`{zadat}`, dialogy souborů platí z náhledu).

Náhled s jiným kódem (chyba) nic nezapíše a na nic se neptá. Když skript v náhledu vypíše řádek `DVOJPANEL:BEZ_ZMEN`, program oznámí „beze změn“ a také se neptá. `zobrazit_slozku` se otevře až po ostrém běhu.

### Pravidla pro skripty

- Výstup (`print`) i chyby se zobrazují v dolním panelu. Výstup je v UTF-8.
- Skript se může ptát přes `input()` (nebo `.bat` přes `set /p`, `pause`): když jeho výpis skončí nedokončeným řádkem, který končí `:`, `?`, `]` nebo `>` (nebo výzvou „libovolné klávesy“), a 0,3 s se nic neděje, Dvojpanel otevře okno pro zadání. V okně je, co nástroj vypsal (např. nabídka voleb), otázka a pole. Enter odešle (i prázdné), Esc vstup zavře a `input()` skončí chybou `EOFError`. Do logu se zapíše otázka i odpověď. Vložený víceřádkový text odpoví na víc otázek za sebou. Hodnoty známé předem je pořád pohodlnější předat argumenty nebo `{zadat:...}`.
- Návratový kód 0 znamená úspěch, cokoli jiného chybu.
- Běží vždy jen jeden nástroj; zastavit ho lze v menu Nástroje.
- Řádky začínající `DVOJPANEL:` jsou zprávy pro program a ve výstupu se nezobrazují (zatím `DVOJPANEL:BEZ_ZMEN`, viz Náhled a potvrzení).
- Nástroj dostane proměnnou prostředí `DVOJPANEL` (verze programu), podle které pozná, že běží z Dvojpanelu. Např. `.bat`, který po dvojkliku čeká (`pause`/`timeout`), může čekání přeskočit: `if defined DVOJPANEL exit /b 0`. Jinak `pause` otevře okno pro zadání (stačí Enter) a `timeout` vypíše „Input redirection is not supported“ a skončí, výsledek nástroje to neovlivní.

## Testy

```
python tests\spustit_testy.py
```

Automatický test celého programu přes skutečné okno (klávesy, myš, dialogy podvržené), asi 5 minut. Program se zkopíruje do dočasné složky, takže lokální `nastroje.json`, `oblibene.json` ani `dvojpanel.json` se nezmění. Projekt Windchill (`C:\Projects\MojeAplikace\Windchill`, jinde proměnná `DP_WINDCHILL`; má-li `dvojpanel_nastroje.json` jen v podsložce `windchill-index`, použije se ta a `.venv` o úroveň výš) se jen čte. Návratový kód 0 = vše prošlo. Potřebuje Windows s displejem.

## Licence

Soukromý projekt.
