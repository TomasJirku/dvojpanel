# Tests for 0.5.0 ({soubor_cil}); exec'd inside test_release.py (shares its globals).
import glob


SAP_PANES = "Aktualizovat podle SAP (přehled pod kurzorem, export ve druhém panelu)"


def v050():
    """0.5.0 {soubor_cil} + real aktualizuj_ze_sap.py"""
    wc_py = os.path.join(WC_VENV, "Scripts", "python.exe")
    work = os.path.join(ENV, "sap")
    target_dir, sap_dir = os.path.join(work, "prehled"), os.path.join(work, "export")
    os.makedirs(target_dir); os.makedirs(sap_dir)
    target, sapx = os.path.join(target_dir, "PNs_Overview_TEST.xlsx"), os.path.join(sap_dir, "SAP_EXPORT.xlsx")
    subprocess.run([wc_py, "-c", f"""
from openpyxl import Workbook
wb = Workbook(); ws = wb.active; ws.title = "PNs"
ws.append(["Projekt G5x"]); ws.append([])
ws.append(["Pozice", "ZF #", "Customer #"])
ws.append([1, "R000W404E", "5B44869-05"])
ws.append([2, "R000W500B", "5B50000-03"])
ws.append([3, "R000W600A", "5B60000-01"])
wb.save(r"{target}")
wb = Workbook(); ws = wb.active
ws.append(["Indices", "Customer Part Number", "AUSP22"])
ws.append(["R000W404F", "5B44869-06", ""])
ws.append(["R000W500A", "5B50000-03", ""])
ws.append(["R000W600A", "5B60000-01", ""])
wb.save(r"{sapx}")
"""], check=True)

    # example config paths: %USERPROFILE%/Skripty/windchill/{aktualizuj_ze_sap.py,.venv}
    wc = os.path.join(HOME, "Skripty", "windchill")
    shutil.copy(os.path.join(WC_SRC, "aktualizuj_ze_sap.py"), wc)
    if os.path.exists(os.path.join(WC_SRC, "cesty.py")):  # imported by aktualizuj_ze_sap.py since 1.19.0
        shutil.copy(os.path.join(WC_SRC, "cesty.py"), wc)
    site = glob.glob(os.path.join(wc, ".venv", "Lib", "site-packages"))[0]
    write(os.path.join(site, "windchill_libs.pth"), os.path.join(WC_VENV, "Lib", "site-packages") + "\n")
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    write(os.path.join(SCRIPTS, "echo_args.py"), open(os.path.join(SCRIPTS, "echo_args.py"), encoding="utf-8").read())
    cfg = json.loads(dp.CONFIG_FILE.read_text(encoding="utf-8"))
    cfg["nastroje"] += [
        {"nazev": "Echo dva", "skript": "%DP_TEST%/scripts/echo_args.py", "argumenty": ["{soubor}", "{soubor_cil}"]},
        {"nazev": "Echo dva xlsx", "skript": "%DP_TEST%/scripts/echo_args.py",
         "argumenty": ["{soubor}", "{soubor_cil}"], "pripony": [".xlsx"]},
        {"nazev": "SAP aktualizace", "skript": "%USERPROFILE%/Skripty/windchill/aktualizuj_ze_sap.py",
         "python": "%USERPROFILE%/Skripty/windchill/.venv/Scripts/python.exe",
         "argumenty": ["{soubor}", "{soubor_cil}"], "pripony": [".xlsx"]},
    ]
    dp.CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    app.reload_tools()
    check("example config has the SAP tool", any(t["nazev"].startswith("Aktualizovat podle SAP") for t in app.tools))

    def cursor(pane, path):
        pane.load(os.path.dirname(path) if os.path.isfile(path) else path)
        pane.clear_marks()
        pane.tree.focus(path); pane.tree.selection_set(path)

    # placeholder basics
    cursor(app.left, os.path.join(L, "a.txt")); cursor(app.right, os.path.join(L, "data.xlsx"))
    app.right.load(L); app.right.tree.focus(os.path.join(L, "data.xlsx"))
    app.set_active(app.left)
    log = run("Echo dva")
    check("{soubor} = active pane cursor, {soubor_cil} = other pane cursor, in that order",
          (parsed(log) or {}).get("args") == [os.path.join(L, "a.txt"), os.path.join(L, "data.xlsx")], log)
    app.set_active(app.right)
    log = run("Echo dva")
    check("switching active pane swaps them",
          (parsed(log) or {}).get("args") == [os.path.join(L, "data.xlsx"), os.path.join(L, "a.txt")], log)
    app.set_active(app.left)
    app.right.tree.focus(os.path.join(L, "sub"))
    reset()
    app.run_tool(tool("Echo dva"))
    check("other pane cursor on folder -> clear error",
          kinds() == ["showerror"] and "ve druhém panelu není soubor" in calls[0][1][1], calls)
    app.right.load(os.path.join(L, "sub")); app.right.tree.focus(dp.UP)
    reset()
    app.run_tool(tool("Echo dva"))
    check("other pane cursor on [..] -> same error", kinds() == ["showerror"], calls)
    app.left.tree.focus(os.path.join(L, "sub")); app.left.tree.selection_set(os.path.join(L, "sub"))
    app.right.load(L); app.right.tree.focus(os.path.join(L, "a.txt"))
    reset()
    app.run_tool(tool("Echo dva"))
    check("{soubor} on folder -> 'v aktivním panelu' error",
          kinds() == ["showerror"] and "v aktivním panelu" in calls[0][1][1], calls)
    cursor(app.left, os.path.join(L, "data.xlsx"))
    app.right.tree.focus(os.path.join(L, "a.txt"))
    reset()
    app.run_tool(tool("Echo dva xlsx"))
    check("pripony also checks {soubor_cil}", kinds() == ["showwarning"] and "a.txt" in calls[0][1][1], calls)

    # real script: target in active (left) pane, SAP export in the other pane
    cursor(app.left, target); cursor(app.right, sapx)
    app.set_active(app.left)
    reset(False)  # preview, then decline the real run
    log = run(SAP_PANES, timeout=60)
    check("kontrola: target/SAP passed in right order",
          f"Cil: PNs_Overview_TEST.xlsx" in log and "SAP: SAP_EXPORT.xlsx (3 PN)" in log, log)
    check("kontrola finds update + marked cell, rc 2",
          "R000W404E -> R000W404F" in log and "BMW 5B44869-05 -> 5B44869-06" in log
          and "R000W500B: ZF # v SAP R000W500A" in log and "návratový kód 2" in log, log)
    check("kontrola writes nothing", not glob.glob(os.path.join(target_dir, "*zaloha*")), os.listdir(target_dir))

    app.set_active(app.right)  # swapped: SAP export would be treated as the target
    reset(False)
    log = run(SAP_PANES, timeout=60)
    check("swapped panes -> script refuses (missing header), rc 1, nothing written",
          "chybi hlavicka" in log and "návratový kód 1" in log and not glob.glob(os.path.join(sap_dir, "*zaloha*")), log)

    app.set_active(app.left)
    log = run("SAP aktualizace", timeout=60)
    backups = glob.glob(os.path.join(target_dir, "*zaloha*"))
    check("update run: backup created next to target", len(backups) == 1, os.listdir(target_dir))
    out = subprocess.run([wc_py, "-c", f"""
from openpyxl import load_workbook
ws = load_workbook(r"{target}").active
print([[c.value for c in r] for r in ws.iter_rows(min_row=4)])
print(ws["B5"].fill.fgColor.rgb, bool(ws["B5"].comment))
"""], capture_output=True, text=True).stdout
    check("target updated from SAP, higher generation marked",
          "'R000W404F', '5B44869-06'" in out and "FFFFC7CE True" in out, out)
    print("    ", log.strip().splitlines()[-1])


section(v050)
