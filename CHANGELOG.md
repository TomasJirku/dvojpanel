# Changelog

## 0.4.0 – 2026-11-01
- Soubor → Vytvořit zástupce v nabídce Start: zástupce s ikonou, který lze připnout na hlavní panel Windows 11.
- Vlastní ikona programu (`dvojpanel.ico`) v okně i na hlavním panelu.
- Nástroje dostávají proměnnou prostředí `DVOJPANEL` (verze), aby skript poznal, že běží z Dvojpanelu.
- Šablona `nastroje.example.json`: nový nástroj „Windchill: aktualizovat index“ (`Aktualizovat_index.bat`).

## 0.3.0 – 2026-11-01
- Průběh v procentech (stavový řádek + ukazatel) při kopírování a přesunu souborů od 16 MB; Esc přeruší.
- Kopírování přes dočasný soubor: přerušené nebo selhané kopírování nepoškodí existující cíl.
- Označování položek Mezerníkem a Insertem jako v NC (červeně), Ctrl+A označí vše / zruší označení.
  Označené položky mají přednost před výběrem, po úspěšné operaci se označení zruší.
- Porovnání a synchronizace složek (Ctrl+S): binárně nebo podle velikosti a času, s podsložkami,
  volba směru u každé položky, synchronizace jen kopíruje a před přepsáním souborů je vypíše.
- Oblíbené složky (menu Oblíbené, Ctrl+D) v lokálním `oblibene.json`; nedostupná síťová cesta nezablokuje okno.
- Oprava: `.bat`/`.cmd` nástroj ve složce s mezerou v cestě selhal, pokud měl argument s mezerou
  (např. soubor s mezerou v názvu přes `{soubory}`).
- Oprava: Shift+šipky nahoru/dolů rozšiřují výběr, jak uvádí README (dříve jen posouvaly kurzor).

## 0.2.0 – 2026-11-01
- Nástroje: spouštění vlastních skriptů nad vybranými soubory (F9, menu Nástroje).
- Konfigurace v `nastroje.json` (lokální, mimo Git), šablona `nastroje.example.json`.
- Zástupné symboly `{soubory}`, `{soubor}`, `{slozka}`, `{cil}`, `{skript_slozka}`, `{zadat:Popisek}`.
- Výstup skriptu v dolním panelu, návratový kód, možnost nástroj zastavit.
- Volitelné `pripony`, `pracovni_slozka`, `zobrazit_slozku`, `python`.
- Menu Soubor / Nástroje / Nápověda, verze v titulku okna.

## 0.1.0 – 2026-11-01
- Dva panely, výběr disku, adresní řádek, řazení podle sloupců.
- F2 přejmenovat, F3 otevřít, F4 Notepad, F5 kopírovat, F6 přesunout, F7 nová složka, F8 koš.
- Kopírování a přesun na pozadí, řešení kolizí, varování u síťových disků (bez koše).
