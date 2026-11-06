# Tests for 0.7.0 (included tool files, groups, preview -> confirm); exec'd inside harness.py.


def run_flow(name, marks, timeout=20):
    """Run a tool and wait until `marks` result lines (■) are logged and nothing runs any more."""
    app.clear_log()
    app.run_tool(tool(name))
    pump(lambda: app.proc is None and log_text().count("■") >= marks, timeout)
    pump(timeout=0.2)
    return log_text()


def all_args(log):
    return [json.loads(ln[5:])["args"] for ln in log.splitlines() if ln.startswith("ARGS:")]


def v070_include():
    """0.7.0 Included tool files ("vlozit"), groups"""
    proj = os.path.join(ENV, "projekt X")
    os.makedirs(os.path.join(proj, "skripty"))
    os.makedirs(os.path.join(proj, "vystupy"))
    shutil.copy(os.path.join(SCRIPTS, "echo_args.py"), os.path.join(proj, "skripty", "echo.py"))
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", os.path.join(proj, ".venv")], check=True)
    inc = os.path.join(proj, "dvojpanel_nastroje.json")
    write(inc, json.dumps({"skupina": "Projekt X", "nastroje": [
        {"nazev": "X relativní", "skript": "skripty/echo.py", "python": ".venv/Scripts/python.exe",
         "zobrazit_slozku": "vystupy"},
        {"nazev": "X vlastní skupina", "skupina": "Jiná", "skript": "skripty/echo.py"},
    ]}, ensure_ascii=False))
    local = {"nazev": "Lokální", "skript": "%DP_TEST%/scripts/echo_args.py"}
    dp.CONFIG_FILE.write_text(json.dumps({"vlozit": ["%DP_TEST%/projekt X/dvojpanel_nastroje.json"],
                                          "nastroje": [local]}, ensure_ascii=False), encoding="utf-8")
    reset()
    app.reload_tools()
    check("included tools load after local ones, no error",
          [t["nazev"] for t in app.tools] == ["Lokální", "X relativní", "X vlastní skupina"]
          and app.tools_error is None and not calls, (app.tools, app.tools_error, calls))
    check("file-level skupina is the default, a tool's own wins",
          [t.get("skupina") for t in app.tools] == [None, "Projekt X", "Jiná"])
    tm = app.tools_menu
    entries = [(tm.type(i), tm.entrycget(i, "label")) for i in range(tm.index("end") + 1) if tm.type(i) != "separator"]
    check("menu: ungrouped tool, then one submenu per group",
          entries[:3] == [("command", "Lokální"), ("cascade", "Projekt X"), ("cascade", "Jiná")], entries)
    sub = app.nametowidget(tm.entrycget(1, "menu"))
    check("submenu contains its tools", sub.entrycget(0, "label") == "X relativní")
    app.right.load(R)
    log = run("X relativní")
    p = parsed(log) or {}
    check("relative skript/python/cwd resolve against the included file's folder",
          p.get("cwd") == os.path.join(proj, "skripty")
          and os.path.join(proj, ".venv").lower() in log.lower(), log)
    check("relative zobrazit_slozku too", app.right.path == os.path.join(proj, "vystupy"), app.right.path)
    sub.invoke(0)
    pump(lambda: app.proc is None and "■" in log_text(), 10)
    check("tool runs from the submenu", "■ Hotovo" in log_text())

    dp.CONFIG_FILE.write_text(json.dumps({"vlozit": "%DP_TEST%/projekt X/dvojpanel_nastroje.json"}),
                              encoding="utf-8")
    app.reload_tools()
    check("vlozit may be a single string", len(app.tools) == 2 and app.tools_error is None)

    dp.CONFIG_FILE.write_text(json.dumps({"vlozit": ["%DP_TEST%/neni.json", "%DP_TEST%/projekt X/dvojpanel_nastroje.json"],
                                          "nastroje": [local]}), encoding="utf-8")
    reset()
    app.reload_tools()
    check("missing include -> error shown, the other tools still load",
          kinds() == ["showerror"] and "neexistuje" in calls[0][1][1] and len(app.tools) == 3, (calls, app.tools))
    check("menu shows the warning on top", tm.entrycget(0, "label").startswith("⚠ Vložený soubor nástrojů neexistuje")
          and tm.entrycget(0, "state") == "disabled", tm.entrycget(0, "label"))
    reset()
    app.reload_tools(startup=True)
    check("at startup only logged", not calls and "neexistuje" in log_text())

    bad = os.path.join(ENV, "spatny.json")
    for content, needle in (("{ rozbité", "Chyba ve vloženém souboru"),
                            (json.dumps({"vlozit": ["x.json"], "nastroje": []}), "nesmí dál vkládat"),
                            (json.dumps({"nastroje": [{"nazev": "bez skriptu"}]}), "musí mít 'nazev' a 'skript'")):
        write(bad, content)
        dp.CONFIG_FILE.write_text(json.dumps({"vlozit": [bad], "nastroje": [local]}), encoding="utf-8")
        app.reload_tools(startup=True)
        check(f"bad include reported: {needle}", needle in (app.tools_error or "")
              and [t["nazev"] for t in app.tools] == ["Lokální"], app.tools_error)

    # the shipped template includes the Windchill tool file
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()
    groups = [tm.entrycget(i, "label") for i in range(tm.index("end") + 1) if tm.type(i) == "cascade"]
    check("template: Windchill tools in three groups",
          groups == ["Windchill – index a dotazy", "Windchill – přehled PN", "Windchill – změny (CR / DN)"]
          and app.tools_error is None, (groups, app.tools_error))
    check("template: all Windchill paths point into the Windchill folder",
          all(dp.tool_path(t, t["skript"]).startswith(WC_TEST) for t in app.tools if t.get("skupina")))


def v070_preview():
    """0.7.0 Preview (nahled) -> confirm -> real run"""
    script = os.path.join(SCRIPTS, "nahled.py")
    write(script, "import json, sys, os\n"
                  "print('ARGS:' + json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd()}))\n"
                  "if '--jen-kontrola' in sys.argv and 'beze-zmen' in sys.argv: print('DVOJPANEL:BEZ_ZMEN')\n"
                  "rc = [a for a in sys.argv if a.startswith('--rc=')]\n"
                  "sys.exit(int(rc[0][5:]) if rc and '--jen-kontrola' in sys.argv else 0)\n")
    bat = os.path.join(SCRIPTS, "dir with space", "nahled.bat")
    write(bat, "@echo off\r\necho BAT=%*\r\n")
    S = "%DP_TEST%/scripts/nahled.py"
    cfg = {"nastroje": [
        {"nazev": "N zadat", "skript": S, "argumenty": ["{zadat:Číslo}", "pevný"], "nahled": "--jen-kontrola"},
        {"nazev": "N seznam", "skript": S, "nahled": ["--jen-kontrola", "--podrobne"]},
        {"nazev": "N rc2", "skript": S, "argumenty": ["--rc=2"], "nahled": "--jen-kontrola"},
        {"nazev": "N rc1", "skript": S, "argumenty": ["--rc=1"], "nahled": "--jen-kontrola"},
        {"nazev": "N beze změn", "skript": S, "argumenty": ["beze-zmen"], "nahled": "--jen-kontrola"},
        {"nazev": "N bat", "skript": "%DP_TEST%/scripts/dir with space/nahled.bat", "argumenty": ["a b"],
         "nahled": "--jen-kontrola", "zobrazit_slozku": "%DP_TEST%/out"},
        {"nazev": "N dialog", "skript": S, "argumenty": ["{vybrat_soubor:Vstup|.txt}"], "nahled": "--jen-kontrola"},
    ]}
    dp.CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    app.reload_tools()
    app.left.load(L); app.right.load(R)

    reset("123", True)
    log = run_flow("N zadat", 2)
    check("preview with flag, then real run without it; {zadat} asked once",
          all_args(log) == [["123", "pevný", "--jen-kontrola"], ["123", "pevný"]]
          and kinds() == ["askstring", "askyesno"], (log, calls))
    check("log marks the preview and the real run", "N zadat – náhled" in log and "■ Náhled hotov" in log
          and log.rstrip().endswith("■ Hotovo"), log)
    reset("123", False)
    log = run_flow("N zadat", 1)
    pump(timeout=0.5)
    check("declined -> no real run", all_args(log) == [["123", "pevný", "--jen-kontrola"]]
          and "Zrušeno, nic se nezapsalo" in log and app.proc is None, log)
    reset(True)
    log = run_flow("N seznam", 2)
    check("nahled as a list of flags", all_args(log) == [["--jen-kontrola", "--podrobne"], []], log)
    reset(True)
    log = run_flow("N rc2", 2)
    check("preview rc 2 (needs attention) still asks", kinds() == ["askyesno"] and len(all_args(log)) == 2, log)
    reset(True)
    log = run_flow("N rc1", 1)
    pump(timeout=0.5)
    check("preview error -> no question, nothing written",
          not calls and len(all_args(log)) == 1 and "Náhled skončil s chybou (návratový kód 1)" in log, (log, calls))
    reset(True)
    log = run_flow("N beze změn", 1)
    pump(timeout=0.5)
    check("DVOJPANEL:BEZ_ZMEN -> no question, line hidden from the log",
          not calls and "beze změn, není co zapsat" in log and "DVOJPANEL:" not in log, (log, calls))
    reset(True)
    app.right.load(R)
    log = run_flow("N bat", 2)
    check(".bat preview and real run", log.count("BAT=") == 2 and "BAT=\"a b\" --jen-kontrola" in log, log)
    check("zobrazit_slozku only after the real run", app.right.path == OUT, app.right.path)

    from tkinter import filedialog
    real = filedialog.askopenfilename
    asked = []
    filedialog.askopenfilename = lambda **k: (asked.append(k), os.path.join(L, "a.txt"))[1]
    try:
        reset(True)
        log = run_flow("N dialog", 2)
    finally:
        filedialog.askopenfilename = real
    check("file dialog asked once for both runs", len(asked) == 1
          and all_args(log) == [[os.path.join(L, "a.txt"), "--jen-kontrola"], [os.path.join(L, "a.txt")]], log)

    # the real Windchill script through the template: matching files -> "beze změn", no question
    wc = os.path.join(HOME, "Skripty", "windchill")
    wc_py = os.path.join(WC_VENV, "Scripts", "python.exe")
    same = os.path.join(ENV, "sap_shoda")
    os.makedirs(same)
    target, sapx = os.path.join(same, "PNs_Overview.xlsx"), os.path.join(same, "SAP.xlsx")
    subprocess.run([wc_py, "-c", f"""
from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["Pozice", "ZF #", "Customer #"]); ws.append([1, "R000W600A", "5B60000-01"]); wb.save(r"{target}")
wb = Workbook(); ws = wb.active
ws.append(["Indices", "Customer Part Number", "AUSP22"]); ws.append(["R000W600A", "5B60000-01", ""]); wb.save(r"{sapx}")
"""], check=True)
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()
    for n in ("aktualizuj_ze_sap.py", "cesty.py"):
        shutil.copy(os.path.join(WC_SRC, n), wc)
    app.left.load(same); app.right.load(same)
    app.left.tree.focus(target); app.right.tree.focus(sapx)
    app.set_active(app.left)
    reset(True)
    log = run_flow("Aktualizovat podle SAP (přehled pod kurzorem, export ve druhém panelu)", 1, timeout=60)
    pump(timeout=0.5)
    check("real SAP script: nothing to change -> no question, no backup",
          "Vse souhlasi" in log and "beze změn" in log and not calls
          and not [n for n in os.listdir(same) if "zaloha" in n], (log, calls))
    app.left.load(L); app.right.load(R)


for fn in (v070_include, v070_preview):
    section(fn)
