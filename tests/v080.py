# Tests for 0.8.0 (Typ column, sort arrows, newer-target check, tool input window, help, adding tool files);
# exec'd inside harness.py.


def v080_columns():
    """0.8.0 Typ column and sort arrows in the headings"""
    folder = os.path.join(ENV, "typy")
    os.makedirs(os.path.join(folder, "slozka"))
    for n in ("b.xlsx", "a.txt", "c.txt", "bez_pripony"):
        write(os.path.join(folder, n), n)
    app.left.load(folder)
    pane, lt = app.left, app.left.tree
    check("columns Název / Typ / Velikost / Změněno", lt["columns"] == ("name", "type", "size", "date"), lt["columns"])
    types = {os.path.basename(i): lt.set(i, "type") for i in lt.get_children() if i != dp.UP}
    check("Typ of a folder is Složka, of a file the Windows type name",
          types["slozka"] == "Složka" and types["a.txt"] == dp.file_type("a.txt", False) != ""
          and types["a.txt"] == types["c.txt"] != types["b.xlsx"], types)
    check("file without extension: Soubor", types["bez_pripony"] == "Soubor"
          or types["bez_pripony"] == dp.file_type("bez_pripony", False), types)
    unknown = dp.file_type("x.dvojpaneltest", False)
    check("unknown extension: a name with the extension (from Windows or 'Soubor XYZ')",
          "DVOJPANELTEST" in unknown.upper(), unknown)

    def heads():
        return [lt.heading(c, "text") for c in pane.COLUMNS]

    def click(col):
        app.tk.call(lt.heading(col, "command"))
        app.update()

    pane.sort_col, pane.sort_rev = "name", False
    pane.refresh_view()
    check("default: Název ▲, other headings without an arrow",
          heads() == ["Název ▲", "Typ", "Velikost", "Změněno"], heads())
    click("name")
    check("second click: Název ▼ and order reversed",
          heads()[0] == "Název ▼" and names(pane)[1:] == ["c.txt", "bez_pripony", "b.xlsx", "a.txt"],
          (heads(), names(pane)))
    click("type")
    order = names(pane)
    by_type = sorted(["a.txt", "b.xlsx", "c.txt", "bez_pripony"], key=lambda n: (dp.file_type(n, False).lower(), n))
    check("sort by Typ: Typ ▲, files grouped by type, same type by name",
          heads() == ["Název", "Typ ▲", "Velikost", "Změněno"] and order[0] == "slozka" and order[1:] == by_type,
          (heads(), order))
    click("type")
    check("Typ ▼ reverses", heads()[1] == "Typ ▼" and names(pane)[1:] == by_type[::-1], names(pane))
    click("date")
    check("arrow moves to Změněno", heads() == ["Název", "Typ", "Velikost", "Změněno ▲"], heads())
    click("name")
    check("[..] row has an empty Typ", lt.set(dp.UP, "type") == "")


def v080_newer():
    """0.8.0 Copy / move: overwrite only older, warn about newer targets"""
    src, dst = os.path.join(ENV, "zdroj"), os.path.join(ENV, "cil")
    old_t, new_t = 1_700_000_000, 1_750_000_000

    def setup():
        for d in (src, dst):
            if os.path.exists(d):
                shutil.rmtree(d)
            os.makedirs(os.path.join(d, "slozka"))
        # starsi_v_cili.txt: the target is older -> replaced; novejsi_v_cili.txt: the target is newer -> kept
        for rel, s_time, d_time in (("starsi_v_cili.txt", new_t, old_t), ("novejsi_v_cili.txt", old_t, new_t),
                                    (os.path.join("slozka", "uvnitr_novejsi.txt"), old_t, new_t),
                                    (os.path.join("slozka", "uvnitr_starsi.txt"), new_t, old_t)):
            write(os.path.join(src, rel), "ZDROJ " + rel)
            write(os.path.join(dst, rel), "CIL " + rel)
            os.utime(os.path.join(src, rel), (s_time, s_time))
            os.utime(os.path.join(dst, rel), (d_time, d_time))
        write(os.path.join(src, "novy.txt"), "ZDROJ novy")
        app.left.load(src); app.right.load(dst)

    def content(*rel):
        p = os.path.join(*rel)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else None

    items = ["starsi_v_cili.txt", "novejsi_v_cili.txt", "slozka", "novy.txt"]

    def go(move, answer):
        reset(True, answer)
        app.transfer(move, [os.path.join(src, n) for n in items], dst, app.left)
        wait_job()

    setup()
    go(False, None)
    msg = calls[1][1][1] if len(calls) > 1 else ""
    check("existing items -> own question with the count",
          kinds() == ["askokcancel", "ask_conflict"] and "V cíli už existuje 3 z 4 položek" in msg, calls)
    check("question names the file that is NEWER in the target, with both dates",
          "NOVĚJŠÍ verze u 1 souborů" in msg and "novejsi_v_cili.txt" in msg and "starsi_v_cili.txt" not in msg
          and dp.fmt_time(new_t) in msg and dp.fmt_time(old_t) in msg, msg)
    check("question mentions merged folders", "Složky (1) se sloučí" in msg, msg)
    check("Storno changes nothing", content(dst, "starsi_v_cili.txt").startswith("CIL")
          and not os.path.exists(os.path.join(dst, "novy.txt")))

    go(False, "older")
    check("Přepsat jen starší: older target replaced, newer kept, new file copied",
          content(dst, "starsi_v_cili.txt").startswith("ZDROJ") and content(dst, "novejsi_v_cili.txt").startswith("CIL")
          and content(dst, "novy.txt") == "ZDROJ novy", os.listdir(dst))
    check("... also inside a merged folder",
          content(dst, "slozka", "uvnitr_starsi.txt").startswith("ZDROJ")
          and content(dst, "slozka", "uvnitr_novejsi.txt").startswith("CIL"))
    check("kept target keeps its time", int(os.path.getmtime(os.path.join(dst, "novejsi_v_cili.txt"))) == new_t)

    setup()
    go(False, "all")
    check("Přepsat vše overwrites the newer target too",
          content(dst, "novejsi_v_cili.txt").startswith("ZDROJ")
          and content(dst, "slozka", "uvnitr_novejsi.txt").startswith("ZDROJ"))

    setup()
    go(False, "skip")
    check("Přeskočit existující: only the new file",
          content(dst, "starsi_v_cili.txt").startswith("CIL") and content(dst, "novy.txt") == "ZDROJ novy")

    setup()
    go(True, "older")
    check("move + only older: copied files leave the source",
          not os.path.exists(os.path.join(src, "starsi_v_cili.txt")) and not os.path.exists(os.path.join(src, "novy.txt"))
          and not os.path.exists(os.path.join(src, "slozka", "uvnitr_starsi.txt")), os.listdir(src))
    check("move + only older: files not overwritten stay in the source (nothing lost)",
          content(src, "novejsi_v_cili.txt").startswith("ZDROJ")
          and content(src, "slozka", "uvnitr_novejsi.txt").startswith("ZDROJ")
          and content(dst, "novejsi_v_cili.txt").startswith("CIL"), os.listdir(src))
    check("no error dialog", "showerror" not in kinds(), calls)

    setup()
    reset(True, "older")
    app.transfer(False, [os.path.join(src, "novy.txt")], dst, app.left)
    wait_job()
    check("nothing exists in the target -> no question", kinds() == ["askokcancel"], calls)

    setup()
    for n in ("starsi_v_cili.txt", "novejsi_v_cili.txt"):
        os.utime(os.path.join(dst, n), (new_t, new_t))
        os.utime(os.path.join(src, n), (new_t, new_t))
    msg = dp.conflict_message([os.path.join(src, "starsi_v_cili.txt")], dst, [os.path.join(src, "starsi_v_cili.txt")])
    check("same time is not reported as newer", "není v cíli novější" in msg, msg)
    check("same time is not overwritten by 'only older'",
          dp.target_is_newer(os.path.join(src, "starsi_v_cili.txt"), os.path.join(dst, "starsi_v_cili.txt")))
    app.left.load(L); app.right.load(R)


def v080_tool_input():
    """0.8.0 A tool that asks (input(), set /p, pause) gets a window"""
    menu = os.path.join(SCRIPTS, "menu.py")
    write(menu, "print('Odkud nacist cisla dilu?')\nprint('  1  ze schranky')\nprint('  4  zadat rucne')\n"
                "v = input('Volba [1]: ')\nc = input('Cislo CR nebo odchylky (DN): ')\n"
                "print('ANSWERS:' + repr((v, c)))\n")
    slow = os.path.join(SCRIPTS, "slow.py")
    write(slow, "import time\nprint('Stahuji...', end='', flush=True)\ntime.sleep(1.2)\nprint(' hotovo')\n"
                "print('DVOJPANEL:BEZ_ZMEN')\n")
    setp = os.path.join(SCRIPTS, "setp.bat")
    write(setp, "@echo off\r\nset /p PN=Cislo dilu: \r\necho PN=[%PN%]\r\n")
    pause = os.path.join(SCRIPTS, "pause.bat")
    write(pause, "@echo off\r\necho pred\r\npause\r\necho po\r\n")
    multi = os.path.join(SCRIPTS, "multi.py")
    write(multi, "rows = []\nwhile True:\n    r = input('  ')\n    if not r:\n        break\n    rows.append(r)\n"
                 "print('ROWS:' + repr(rows))\n")
    cfg = {"nastroje": [{"nazev": "Menu", "skript": menu}, {"nazev": "Pomalý", "skript": slow},
                        {"nazev": "Set p", "skript": setp}, {"nazev": "Pauza", "skript": pause},
                        {"nazev": "Řádky", "skript": multi},
                        {"nazev": "Input", "skript": os.path.join(SCRIPTS, "input.py")}]}
    dp.CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    app.reload_tools()

    reset("4", "CR0627559")
    log = run("Menu")
    check("two questions -> two input windows, answers reach the script",
          kinds() == ["ask_tool_input", "ask_tool_input"] and "ANSWERS:('4', 'CR0627559')" in log, (calls, log))
    if len(calls) == 2:
        _, title, context, prompt = calls[0][1]
        check("window shows the tool name, its output above the question and the question",
              title == "Menu" and context == ["Odkud nacist cisla dilu?", "  1  ze schranky", "  4  zadat rucne"]
              and prompt == "Volba [1]: ", calls[0][1])
        check("second window: earlier answer in the context", calls[1][1][3] == "Cislo CR nebo odchylky (DN): "
              and calls[1][1][2][-1] == "Volba [1]: 4", calls[1][1])
    check("log shows the question with the answer like a console",
          "Volba [1]: 4\n" in log and "Cislo CR nebo odchylky (DN): CR0627559\n" in log, log)

    reset()
    log = run("Input", timeout=10)
    check("Esc (None) closes the input: input() ends with EOFError, the tool does not hang",
          kinds() == ["ask_tool_input"] and "EOFError" in log and "(vstup ukončen)" in log, (calls, log))

    reset("nemělo by se ptát")
    log = run("Pomalý")
    check("unfinished line that is no question (Stahuji...) -> no window, line completed in the log",
          kinds() == [] and "Stahuji... hotovo" in log, (calls, log))
    check("protocol line still hidden", "DVOJPANEL:" not in log, log)

    reset("R000W600A")
    log = run("Set p")
    check(".bat set /p gets the window and the value", kinds() == ["ask_tool_input"]
          and "PN=[R000W600A]" in log, (calls, log))

    reset("")
    log = run("Pauza")
    check(".bat pause gets the window and continues", kinds() == ["ask_tool_input"] and "po" in log.split("pred", 1)[-1]
          and "■ Hotovo" in log, (calls, log))

    reset("A1", "B2", "")
    log = run("Řádky")
    check("repeated prompt (rows until an empty one)", "ROWS:['A1', 'B2']" in log and len(calls) == 3, (calls, log))
    reset("X1\nX2\nX3", "")
    log = run("Řádky")
    check("pasted lines answer several prompts at once", "ROWS:['X1', 'X2', 'X3']" in log, (calls, log))

    for text, expect in (("Volba [1]: ", True), ("Pokračovat? ", True), ("  ", True), ("[a/N]", True),
                         ("Stahuji...", False), ("50 %", False), ("DVOJPANEL:X:", False),
                         ("Pokračujte stisknutím libovolné klávesy...", True), ("Press any key to continue . . . ", True)):
        check(f"looks_like_prompt({text!r}) == {expect}", dp.looks_like_prompt(text) == expect)


def v080_help():
    """0.8.0 Help (F1) with the tools explained"""
    inc = os.path.join(ENV, "napoveda_nastroje.json")
    write(inc, json.dumps({"skupina": "Windchill – test", "nastroje": [
        {"nazev": "Dotaz PN", "skript": "dotaz.py", "argumenty": ["{zadat:Čísla dílů (PN)}", "--vystup", "xlsx"],
         "zobrazit_slozku": "vystupy", "popis": "Najde změny k dílům."},
        {"nazev": "Doplnit přehled", "skript": "dopln.py", "argumenty": ["{soubor}"], "pripony": [".xlsx"],
         "nahled": "--jen-kontrola"},
        {"nazev": "SAP", "skript": "sap.py", "argumenty": ["{vybrat_soubor:Export ze SAP|.xlsx}", "{cil}"]},
        {"nazev": "Bez parametrů", "skript": "podklad.py"},
    ]}, ensure_ascii=False))
    dp.CONFIG_FILE.write_text(json.dumps({"vlozit": [inc]}), encoding="utf-8")
    app.reload_tools()
    if app.help_window is not None and app.help_window.winfo_exists():
        app.help_window.destroy()
    key(app.left.tree, "<F1>")
    hw = app.help_window
    check("F1 opens the help window", hw is not None and hw.winfo_exists() and hw.winfo_viewable())
    topics = list(hw.listbox.get(0, "end")) if hw else []
    check("help topics include using and setting up tools and my tools",
          {"Začínáme", "Klávesy a myš", "Kopírování, přesun a mazání", "Nástroje – jak je používat", "Moje nástroje",
           "Nástroje – nastavení", "Pro autory skriptů"} <= set(topics), topics)

    def text():
        return hw.text.get("1.0", "end")

    check("first topic shown, bottom bar has F1", text().startswith("Začínáme") and any(
        b.winfo_class() == "TButton" and b["text"] == "F1 Nápověda"
        for f in app.winfo_children() for b in f.winfo_children()), text()[:80])
    for title in topics:
        hw.show(title)
        check(f"topic '{title}' has text", text().startswith(title) and len(text()) > 200, text()[:200])
    hw.show("Nástroje – jak je používat")
    check("tools topic explains the input window and the preview",
          "otevře okno pro zadání" in text() and "Provést změny naostro?" in text(), text())
    hw.show("Kopírování, přesun a mazání")
    check("copy topic explains 'only older'", "Přepsat jen starší" in text() and "NOVĚJŠÍ" in text())
    hw.show("Nástroje – nastavení")
    check("setup topic explains vlozit and the menu item", "Přidat nástroje projektu…" in text()
          and "dvojpanel_nastroje.json" in text())

    hw.destroy()
    app.tools_menu.invoke(app.tools_menu.index("Nápověda k nástrojům"))
    hw = app.help_window
    t = text()
    check("Nástroje → Nápověda k nástrojům opens 'Moje nástroje'", t.startswith("Moje nástroje"), t[:80])
    check("my tools: group, name, popis, what it asks", "Windchill – test" in t and "Dotaz PN" in t
          and "Najde změny k dílům." in t and "zeptá se v okně: Čísla dílů (PN)" in t, t)
    check("my tools: output folder, cursor file, extensions, preview",
          os.path.join(ENV, "vystupy") in t and "souborem pod kurzorem v aktivním panelu" in t
          and "jen soubory: .xlsx" in t and "nejdřív náhled" in t, t)
    check("my tools: file dialog and other pane folder", "vybereš soubor: Export ze SAP (.xlsx)" in t
          and "složku druhého panelu" in t, t)
    check("my tools: a tool without arguments mentions the input window",
          "spustí se bez parametrů" in t and "okno pro zadání" in t, t)
    menubar = app.nametowidget(app["menu"])
    help_menu = app.nametowidget(menubar.entrycget(menubar.index("Nápověda"), "menu"))
    hw.show("Začínáme")
    help_menu.invoke(help_menu.index("Moje nástroje"))
    check("Nápověda → Moje nástroje reuses the window", app.help_window is hw and text().startswith("Moje nástroje"))
    help_menu.invoke(help_menu.index("Nápověda"))
    check("Nápověda menu item", app.help_window is hw)
    key(hw, "<Escape>")
    check("Esc closes the help", not hw.winfo_exists())

    dp.CONFIG_FILE.write_text(json.dumps({"vlozit": ["%DP_TEST%/neni_tady.json"]}), encoding="utf-8")
    app.reload_tools(startup=True)
    check("missing include explains the fix", "Přidat nástroje projektu" in (app.tools_error or ""), app.tools_error)
    app.show_help(dp.MY_TOOLS)
    hw = app.help_window
    check("my tools shows the problem", "Problém s nástroji" in text() and "neni_tady.json" in text(), text()[:300])
    app.help_window.destroy()


def v080_add_tool_file():
    """0.8.0 Nástroje → Přidat nástroje projektu… writes "vlozit" for the user"""
    from tkinter import filedialog
    proj = os.path.join(ENV, "projekt Y")
    os.makedirs(proj)
    shutil.copy(os.path.join(SCRIPTS, "echo_args.py"), os.path.join(proj, "y.py"))
    inc = os.path.join(proj, "dvojpanel_nastroje.json")
    write(inc, json.dumps({"skupina": "Projekt Y", "nastroje": [{"nazev": "Y nástroj", "skript": "y.py"}]},
                          ensure_ascii=False))
    local = {"nazev": "Lokální", "skript": "%DP_TEST%/scripts/echo_args.py"}
    dp.CONFIG_FILE.write_text(json.dumps({"nastroje": [local], "vlastni_klic": 1}, ensure_ascii=False),
                              encoding="utf-8")
    app.reload_tools()
    real = filedialog.askopenfilename
    picked = []
    filedialog.askopenfilename = lambda **k: (picked.append(k), picked_file[0])[1]
    try:
        picked_file = [inc.replace("\\", "/")]
        reset()
        app.tools_menu.invoke(app.tools_menu.index("Přidat nástroje projektu…"))
        data = json.loads(dp.CONFIG_FILE.read_text(encoding="utf-8"))
        check("file dialog for a .json", picked and "*.json" in str(picked[0].get("filetypes")), picked)
        check("vlozit written, the rest of nastroje.json kept",
              data.get("vlozit") == [inc.replace("\\", "/")] and data.get("nastroje") == [local]
              and data.get("vlastni_klic") == 1, data)
        check("tools reloaded, info shown", [t["nazev"] for t in app.tools] == ["Lokální", "Y nástroj"]
              and kinds() == ["showinfo"] and "Přidáno 1 nástrojů" in calls[0][1][1], (app.tools, calls))
        reset()
        app.add_tool_file()
        check("same file again -> 'už je vložený', nothing doubled", kinds() == ["showinfo"]
              and "už je vložený" in calls[0][1][1]
              and len(json.loads(dp.CONFIG_FILE.read_text(encoding="utf-8"))["vlozit"]) == 1, calls)

        before = dp.CONFIG_FILE.read_text(encoding="utf-8")
        bad = os.path.join(ENV, "neni_nastroj.json")
        write(bad, json.dumps({"neco": 1}))
        picked_file[0] = bad
        reset()
        app.add_tool_file()
        check("a JSON without tools -> error, nastroje.json unchanged", kinds() == ["showerror"]
              and "není soubor nástrojů" in calls[0][1][1] and dp.CONFIG_FILE.read_text(encoding="utf-8") == before,
              calls)
        picked_file[0] = ""
        reset()
        app.add_tool_file()
        check("cancelled dialog -> nothing", not calls and dp.CONFIG_FILE.read_text(encoding="utf-8") == before)
        dp.CONFIG_FILE.write_text("{ rozbité", encoding="utf-8")
        picked_file[0] = inc
        picked.clear()
        reset()
        app.add_tool_file()
        check("broken nastroje.json -> error, file not overwritten, no dialog", kinds() == ["showerror"]
              and dp.CONFIG_FILE.read_text(encoding="utf-8") == "{ rozbité" and not picked, calls)
    finally:
        filedialog.askopenfilename = real
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()


for fn in (v080_columns, v080_newer, v080_tool_input, v080_help, v080_add_tool_file):
    section(fn)
