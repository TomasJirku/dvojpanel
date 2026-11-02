# Changelog

## 0.6.0 – 2026-11-02
- Přejmenování přímo v řádku (F2 nebo pomalý druhý klik na jméno), jméno bez přípony předvybrané,
  Enter / klik jinam potvrdí, Esc zruší. Kontrola neplatných znaků; existující položku nepřepíše.
- Lišta oblíbených složek nad panely (klik = aktivní panel, pravé tlačítko = druhý panel / odebrat,
  „+ Přidat“), zalamuje se do více řádků; lze skrýt v menu Oblíbené.
- Ctrl+U (Příkazy → Prohodit panely) prohodí složky levého a pravého panelu.
- Přetažení myší uvnitř programu: do druhého panelu nebo na složku (i `[..]`) = kopírovat, se Shiftem
  přesunout; stejné potvrzení a řešení kolizí jako F5/F6, Esc zruší. Vícenásobný výběr se při tahu zachová.
- `dvojpanel.json` (lokální): výchozí složky levého a pravého panelu při spuštění a zobrazení lišty
  oblíbených; Soubor → Uložit aktuální složky jako výchozí / Upravit / Načíst nastavení znovu.
- Zástupné symboly `{vybrat_soubor:Popisek|.xlsx}` a `{ulozit_soubor:Popisek|.xlsx}`: soubor se vybere
  v okně „Otevřít“ / „Uložit jako“ místo kurzorem v panelech; dialog si pamatuje poslední složku.
- `pripony` kontrolují jen soubory, které nástroj z panelů opravdu bere.

## 0.5.3 – 2026-11-02
- Šablona `nastroje.example.json` a README: nástroje Windchillu ukazují na skutečnou složku projektu
  `C:/Projects/MojeAplikace/Windchill` místo neexistující `%USERPROFILE%/Skripty/windchill`.

## 0.5.2 – 2026-11-01
- Oprava: Enter / dvojklik spustí soubor s pracovní složkou v jeho složce, jako Průzkumník.
  `.bat`, který počítá s vlastní složkou, dřív běžel ve složce Dvojpanelu a nenašel své soubory.

## 0.5.1 – 2026-11-01
- Šablona `nastroje.example.json`: „Windchill: dotaz“ běží přes `.venv` projektu (jinak chyběl `openpyxl`
  a `requests`) a ukládá do nového `vystupy\zmeny_<datum_čas>.xlsx` místo přepisování jednoho souboru.
- Šablona: místo starého `uprav_export_CR_a_DN.py` jeho nástupce `uprava_exportu_AffectedObjects.py` přes `.venv`;
  otevírá skutečnou výstupní složku `C:\Deviation_Export\Output`.

## 0.5.0 – 2026-11-01
- Zástupný symbol `{soubor_cil}`: soubor pod kurzorem ve druhém panelu (dva soubory v pevném pořadí).
- `pripony` kontroluje i `{soubor_cil}`; srozumitelnější chyba, když pod kurzorem není soubor.
- Šablona: nástroj „Windchill: přehled PN podle SAP (kontrola)“ (`aktualizuj_ze_sap.py`).

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
