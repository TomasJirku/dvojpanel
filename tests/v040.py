# Tests for 0.4.0 features; exec'd inside test_release.py (shares its globals).


def v040():
    """0.4.0 Icon, Start-menu shortcut, DVOJPANEL env, Aktualizovat_index.bat tool"""
    check("dvojpanel.ico shipped", dp.ICON_FILE.exists())
    try:
        app.iconbitmap(str(dp.ICON_FILE))
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = e
    check("Tk loads the icon", ok is True, ok)

    # tool from the example config, real bat (copy) with fake Windchill scripts
    wc = os.path.join(HOME, "Skripty", "windchill")
    shutil.copy(os.path.join(WC_SRC, "Aktualizovat_index.bat"), wc)  # the real bat, fake phases
    write(os.path.join(wc, "windchill_index.py"), "print('faze 1: Příliš žluťoučký kůň')\n")
    write(os.path.join(wc, "windchill_vazby.py"), "print('faze 2 ok')\n")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", os.path.join(wc, ".venv")], check=True)
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()
    names_ = [t["nazev"] for t in app.tools]
    check("example config contains 'Aktualizovat index'", "Aktualizovat index" in names_, names_)
    log = run("Aktualizovat index", timeout=30)
    check("Aktualizovat_index.bat runs from Dvojpanel: both phases, Hotovo, rc 0",
          "[2/2]" in log and "Hotovo." in log and "■ Hotovo" in log, log)
    logs = os.listdir(os.path.join(wc, "log"))
    check("bat wrote its log in its own folder, lock removed",
          any(n.startswith("aktualizace_") for n in logs) and "beh.zamek" not in logs, logs)
    print("     timeout noise present:", "Input redirection" in log)

    bat = os.path.join(wc, "Aktualizovat_index.bat")
    text = open(bat, encoding="utf-8").read()
    write(bat, text.replace(":PAUZA\n", ":PAUZA\nif defined DVOJPANEL exit /b 0\n").replace(":PAUZA\r\n", ":PAUZA\r\nif defined DVOJPANEL exit /b 0\r\n"))
    log = run("Aktualizovat index", timeout=30)
    check("with 'if defined DVOJPANEL' in :PAUZA the timeout error disappears",
          "Hotovo." in log and "Input redirection" not in log, log)

    write(os.path.join(SCRIPTS, "env.py"), "import os\nprint('DVOJPANEL=' + str(os.environ.get('DVOJPANEL')))\n")
    dp.CONFIG_FILE.write_text(json.dumps({"nastroje": [{"nazev": "Env", "skript": "%DP_TEST%/scripts/env.py"}]}),
                              encoding="utf-8")
    app.reload_tools()
    log = run("Env")
    check("tools get DVOJPANEL=<version>", f"DVOJPANEL={VER}" in log, log)

    # shortcut
    lnk_dir = os.path.join(ENV, "startmenu")
    os.makedirs(lnk_dir)
    orig = dp.start_menu_folder
    dp.start_menu_folder = lambda: Path(lnk_dir)
    reset()
    fm = app.nametowidget(app.nametowidget(app["menu"]).entrycget("Soubor", "menu"))
    fm.invoke(fm.index("Vytvořit zástupce v nabídce Start…"))
    dp.start_menu_folder = orig
    lnk = os.path.join(lnk_dir, "Dvojpanel.lnk")
    check("menu creates Dvojpanel.lnk and explains pinning",
          os.path.exists(lnk) and kinds() == ["showinfo"] and "Připnout na hlavní panel" in calls[0][1][1], calls)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:L); "
          "$s.TargetPath; $s.Arguments; $s.WorkingDirectory; $s.IconLocation")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=dict(os.environ, L=lnk),
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.splitlines()
    exp_target = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    check("shortcut target = real pythonw.exe", out and os.path.normcase(out[0]) == os.path.normcase(exp_target), out)
    check("shortcut argument = quoted dvojpanel.py", len(out) > 1 and out[1] == f'"{os.path.join(REL, "dvojpanel.py")}"', out)
    check("shortcut working dir + icon", len(out) > 3 and out[2] == REL and out[3].lower().startswith(
        str(dp.ICON_FILE).lower()), out)
    reset()
    dp.create_shortcut(lnk_dir)
    check("creating again overwrites without error", os.path.exists(lnk))

    before = subprocess.run(["powershell", "-NoProfile", "-Command",
                             "(Get-Process pythonw -ErrorAction SilentlyContinue).Id"],
                            capture_output=True, text=True).stdout.split()
    subprocess.run(["cmd", "/c", "start", "", lnk])
    found = ""
    for _ in range(40):
        time.sleep(0.3)
        found = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-Process pythonw -ErrorAction SilentlyContinue | "
                                "Where-Object { $_.MainWindowTitle -like 'Dvojpanel*' } | "
                                "ForEach-Object { \"$($_.Id)|$($_.MainWindowTitle)|$($_.Path)\" }"],
                               capture_output=True, text=True).stdout.strip()
        if found:
            break
    check("launching the .lnk opens 'Dvojpanel <ver>' via pythonw.exe (no console)",
          f"|Dvojpanel {VER}|" in found and found.lower().endswith("pythonw.exe"), found)
    for line in found.splitlines():
        pid = line.split("|")[0]
        if pid not in before:
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)


section(v040)
