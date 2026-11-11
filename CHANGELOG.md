# Changelog

## 0.10.0 – 2026-11-11
- **Jazyk programu**: Soubor → **Jazyk / Language** přepne čeština / English / Deutsch / Polski – menu, tlačítka,
  hlášky, okno porovnání i celou nápovědu (F1). Změna platí hned a uloží se do `dvojpanel.json` jako
  `"jazyk"` (`cs`, `en`, `de`, `pl`; výchozí `cs`).
- Překlady jsou v novém souboru `preklady.json` vedle programu (patří do release ZIPu). Když chybí nebo je
  poškozený, program to ohlásí a zůstane česky.
- Česky zůstávají klíče v `nastroje.json` a názvy / popisy nástrojů, jak jsou v něm zapsané; systémová okna
  jsou v jazyce Windows.
- Testy: `tests\v100.py` hlídá, že každý text programu má překlad ve všech jazycích se stejnými zástupnými
  symboly a že přeložená nápověda má stejnou stavbu jako česká.

## 0.9.0 – 2026-11-10
- Příkazy → **Git pull v aktuální složce** (Ctrl+G): spustí `git pull --ff-only` v repozitáři, do kterého patří
  složka aktivního panelu (i z podsložky). Výpis je v dolním panelu, po úspěchu se obnoví panely a načtou
  nástroje. Vlastní commity a změny git nepřepíše, skončí chybou. Po aktualizaci samotného Dvojpanelu program
  připomene nové spuštění. Složku mimo repozitář a chybějící git ohlásí.
- **Velikost písma**: `"velikost_pisma"` v `dvojpanel.json` (6 až 24 bodů, výchozí 9) pro panely, menu,
  tlačítka, výstup nástrojů i nápovědu; výška řádků se přizpůsobí. Ctrl++ / Ctrl+- / Ctrl+0 (také menu Soubor)
  ji změní hned a uloží.
- Testy: skript Windchillu `aktualizuj_ze_sap.py` od 1.26.0 potřebuje `sloupce_prehledu.py` a sloupce
  `MM/PP` a `Mat. Name` v exportu SAP.

## 0.8.0 – 2026-11-06
- Sloupec **Typ** v panelech: druh souboru, jak ho pojmenují Windows (např. „List Microsoft Excelu“), složky
  „Složka“; lze podle něj řadit.
- Záhlaví sloupce, podle kterého se řadí, ukazuje směr: `▲` vzestupně, `▼` sestupně.
- Kopírování / přesun do cíle, kde položky už existují: program upozorní na soubory, které jsou v cíli
  **novější** (s datem obou), a nabídne Přepsat jen starší (výchozí) / Přepsat vše / Přeskočit existující /
  Storno. „Jen starší“ platí i uvnitř slučovaných složek; při přesunu nepřepsané soubory zůstanou ve zdroji.
- Nástroj, který se sám ptá (Python `input()`, `set /p`, `pause` – typicky skript spuštěný bez parametrů, který
  chce PN nebo CR), dostane okno pro zadání s tím, co nástroj vypsal; dřív skončil chybou EOFError.
- Nápověda (F1, menu Nápověda): ovládání, kopírování, nástroje; téma **Moje nástroje** popisuje každý načtený
  nástroj (na co se ptá, s čím pracuje, náhled, výstupní složka). Nový nepovinný klíč nástroje `popis`.
- Nástroje → **Přidat nástroje projektu…**: soubor `dvojpanel_nastroje.json` se vybere dialogem a program ho
  sám zapíše do `"vlozit"` v `nastroje.json`. Chybějící vložený soubor ohlásí i tuto opravu.
- Testy: projekt Windchill může mít git checkout v podsložce `windchill-index` a `.venv` o úroveň výš.

## 0.7.0 – 2026-11-02
- `nastroje.json`: `"vlozit"` načte soubory nástrojů, které si udržují projekty samy (Windchill:
  `dvojpanel_nastroje.json`). Relativní cesty jsou vůči vloženému souboru, chybějící soubor se ohlásí
  a ostatní nástroje fungují dál. Šablona vkládá nástroje Windchillu místo jejich výpisu.
- `"skupina"`: podmenu v menu Nástroje / F9 (i jako výchozí pro celý vložený soubor).
- `"nahled"`: nástroj nejdřív běží s argumentem pro kontrolu (např. `--jen-kontrola`), naostro až po
  potvrzení; dotazy a dialogy se podruhé neopakují. Chyba v náhledu nebo `DVOJPANEL:BEZ_ZMEN` = žádný dotaz.
- Řádky výstupu `DVOJPANEL:…` jsou zprávy pro program a v dolním panelu se nezobrazují.
- Automatické testy jsou v repozitáři: `python tests\spustit_testy.py`.

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
