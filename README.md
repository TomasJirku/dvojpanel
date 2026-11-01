# Dvojpanel

Dvoupanelový správce souborů pro Windows ve stylu Norton/Total Commanderu, který umí spouštět vlastní Python skripty nad vybranými soubory.

Používá **jen standardní knihovnu Pythonu** (tkinter). Nic se neinstaluje, stačí Python 3.10+.

## Spuštění

```
pythonw dvojpanel.py
```

`pythonw` spustí program bez konzolového okna. Pro ladění lze použít `python dvojpanel.py`.

## Ovládání

| Klávesa | Akce |
|---|---|
| Tab | přepnutí panelu |
| Enter / dvojklik | otevřít složku nebo soubor |
| Backspace | o úroveň výš |
| Ctrl+klik, Shift+šipky, Ctrl+A | výběr více položek |
| F2 | přejmenovat |
| F3 / F4 | otevřít / upravit v Notepadu |
| F5 / F6 | kopírovat / přesunout do druhého panelu |
| F7 | nová složka |
| F8 | smazat do koše (na síťovém disku trvale, program varuje) |
| F9 | nabídka nástrojů |
| Ctrl+R / Ctrl+Q | obnovit / konec |

## Nástroje

Nástroje se definují v `nastroje.json` vedle `dvojpanel.py`. Při prvním spuštění se soubor vytvoří ze šablony `nastroje.example.json`. Upravit ho lze z menu **Nástroje → Upravit nastroje.json** a pak **Načíst nástroje znovu**.

`nastroje.json` obsahuje lokální cesty, proto není v Gitu. Šablona ano.

```json
{
  "nastroje": [
    {
      "nazev": "Windchill: dotaz na číslo dílu",
      "skript": "%USERPROFILE%/Skripty/windchill/dotaz.py",
      "argumenty": ["{zadat:Číslo dílu (PN)}", "--xlsx", "{cil}/dotaz_vysledek.xlsx"]
    }
  ]
}
```

| Klíč | Povinný | Význam |
|---|---|---|
| `nazev` | ano | text v menu |
| `skript` | ano | cesta ke skriptu (`.py`, `.bat`, `.cmd`, `.exe`); relativní cesta je vůči složce programu |
| `argumenty` | ne | seznam argumentů, může obsahovat zástupné symboly |
| `pripony` | ne | povolené přípony vybraných souborů, např. `[".xlsx"]` |
| `pracovni_slozka` | ne | pracovní složka; výchozí je složka skriptu |
| `zobrazit_slozku` | ne | po úspěšném doběhnutí se tato složka otevře v druhém panelu |
| `python` | ne | jiný interpret, např. Python z virtuálního prostředí |

Cesty mohou používat `/` i `\` (v JSONu se zpětné lomítko musí zdvojit) a proměnné jako `%USERPROFILE%`.

### Zástupné symboly

| Symbol | Nahradí se |
|---|---|
| `{soubory}` | všemi vybranými soubory v aktivním panelu (každý jako samostatný argument; musí stát v argumentu sám) |
| `{soubor}` | souborem pod kurzorem |
| `{slozka}` | složkou aktivního panelu |
| `{cil}` | složkou druhého panelu |
| `{skript_slozka}` | složkou skriptu |
| `{zadat:Popisek}` | hodnotou, na kterou se program zeptá v dialogu |

### Pravidla pro skripty

- Výstup (`print`) i chyby se zobrazují v dolním panelu. Výstup je v UTF-8.
- Skript nesmí čekat na `input()`. Vstup je zavřený, takže `input()` skončí chybou místo zamrznutí. Hodnoty předávej argumenty nebo přes `{zadat:...}`.
- Návratový kód 0 znamená úspěch, cokoli jiného chybu.
- Běží vždy jen jeden nástroj; zastavit ho lze v menu Nástroje.

## Licence

Soukromý projekt.
