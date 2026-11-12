# Tests for 0.11.0 (Alt+F5: pack the item under the cursor with 7-Zip); exec'd inside harness.py.
# Without an installed 7-Zip only the checks that need no real archive run.


def v110_pack():
    """0.11.0 Alt+F5 packs the folder under the cursor into name.7z (7-Zip)"""
    base = os.path.join(ENV, "zabalit")
    folder = os.path.join(base, "Žluťoučký projekt")
    os.makedirs(os.path.join(folder, "sub"))
    write(os.path.join(folder, "sub", "a.txt"), "ahoj")
    write(os.path.join(folder, "@b.txt"), "b")
    write(os.path.join(base, "sam.txt"), "sam")
    target = folder + ".7z"
    tmp = target + dp.ARCHIVE_TMP
    exe = dp.find_7zip()

    def pack(*ans, how=lambda: key(app.left.tree, "<Alt-F5>"), timeout=60):
        reset(*ans)
        app.clear_log()
        how()
        pump(lambda: app.proc is None and "■" in log_text(), timeout)
        return log_text()

    def listing(archive):
        r = subprocess.run([exe, "l", "-ba", "-slt", "-sccUTF-8", archive], capture_output=True)
        return sorted(ln[7:] for ln in r.stdout.decode("utf-8").splitlines() if ln.startswith("Path = "))

    def start():
        app.left.load(base); app.right.load(R)
        select(app.left, "Žluťoučký projekt")

    menubar = app.nametowidget(app["menu"])
    cm = app.nametowidget(menubar.entrycget(menubar.index("Příkazy"), "menu"))
    idx = cm.index("Zabalit položku pod kurzorem (7-Zip)…")
    check("Příkazy → Zabalit položku pod kurzorem (Alt+F5)", cm.entrycget(idx, "accelerator") == "Alt+F5")
    check("cesta_7zip: default empty, a number is an error naming the key",
          dp.SETTINGS_DEFAULTS["cesta_7zip"] == "" and app.settings["cesta_7zip"] == "")
    dp.SETTINGS_FILE.write_text(json.dumps({"cesta_7zip": 7}), encoding="utf-8")
    err = dp.load_settings()[1]
    os.remove(dp.SETTINGS_FILE)
    check("cesta_7zip must be a text", err and "'cesta_7zip'" in err, err)
    check("find_7zip: a configured path is used as written, a wrong one finds nothing",
          dp.find_7zip(sys.executable) == sys.executable and dp.find_7zip(os.path.join(base, "neni.exe")) is None)

    start()
    real_find = dp.find_7zip
    dp.find_7zip = lambda configured="": None
    try:
        reset()
        app.clear_log()
        key(app.left.tree, "<Alt-F5>")
        check("7-Zip not found: error that names cesta_7zip, nothing runs", kinds() == ["showerror"]
              and "7z.exe" in calls[0][1][1] and "cesta_7zip" in calls[0][1][1] and app.proc is None
              and "▶" not in log_text() and not os.path.exists(target), calls)
    finally:
        dp.find_7zip = real_find

    app.left.tree.focus(dp.UP)
    reset()
    app.pack()
    check("cursor on [..]: only a hint", kinds() == ["showinfo"] and app.proc is None, calls)
    app.proc = object()  # a tool is running
    try:
        reset()
        app.pack()
        check("a running tool blocks packing", kinds() == ["showinfo"], calls)
    finally:
        app.proc = None

    if exe is None:
        check("7-Zip is not installed here: packing itself not tested", True)
        app.left.load(L)
        return

    start()
    log = pack(False)
    check("Alt+F5 asks first; Cancel packs nothing", kinds() == ["askokcancel"] and folder in calls[0][1][1]
          and target in calls[0][1][1] and "▶" not in log and not os.path.exists(target), (calls, log))

    start()
    log = pack()
    check("packing runs 7-Zip in the log and ends with Hotovo", "▶ Zabalit (7-Zip)" in log and "■ Hotovo" in log
          and f"Archiv: {target}" in log and app.status_var.get() == "Zabalit (7-Zip): hotovo",
          (log, app.status_var.get()))
    check("the archive is next to the folder, no temporary file left, the pane shows it",
          os.path.isfile(target) and not os.path.exists(tmp) and "Žluťoučký projekt.7z" in names(app.left)
          and os.path.isdir(folder), names(app.left))
    check("the archive holds the folder with its content (names with diacritics and @)", listing(target) == sorted([
        "Žluťoučký projekt", "Žluťoučký projekt\\sub", "Žluťoučký projekt\\sub\\a.txt",
        "Žluťoučký projekt\\@b.txt"]), listing(target))
    check("7-Zip output is readable (UTF-8)", "Žluťoučký projekt" in log and "�" not in log, log)

    # the archive exists: ask, and No keeps it
    old = open(target, "rb").read()
    write(os.path.join(folder, "novy.txt"), "novy")
    start()
    log = pack(False)
    check("existing archive: question, No keeps the old one", kinds() == ["askyesno"] and target in calls[0][1][1]
          and "▶" not in log and open(target, "rb").read() == old, (calls, log))
    start()
    write(tmp, "zbytek")  # left by a killed run
    log = pack(True, how=lambda: cm.invoke(idx))
    check("existing archive: Yes replaces it (menu item, stale temporary file does not matter)",
          "■ Hotovo" in log and "Žluťoučký projekt\\novy.txt" in listing(target) and not os.path.exists(tmp),
          (log, listing(target)))

    # a failed run leaves the old archive alone
    old = open(target, "rb").read()
    real_find = dp.find_7zip
    fail = os.path.join(SCRIPTS, "sedmzip_chyba.bat")
    write(fail, '@echo off\r\necho rozbito> "%~8"\r\necho chyba\r\nexit /b 2\r\n')
    dp.find_7zip = lambda configured="": fail
    try:
        start()
        log = pack(True)
        check("7-Zip fails: error in the log, old archive untouched, no temporary file",
              "■ Skončilo s chybou" in log and "Archiv nevznikl." in log and open(target, "rb").read() == old
              and not os.path.exists(tmp) and app.status_var.get().startswith("Zabalit (7-Zip): chyba"),
              (log, app.status_var.get()))
        warn = os.path.join(SCRIPTS, "sedmzip_varovani.bat")
        write(warn, '@echo off\r\necho neuplny> "%~8"\r\necho WARNING\r\nexit /b 1\r\n')
        dp.find_7zip = lambda configured="": warn
        start()
        log = pack(True)
        check("7-Zip warning (code 1): archive kept and a warning shown", kinds() == ["askyesno", "showwarning"]
              and target in calls[1][1][1] and open(target, "rb").read().strip() == b"neuplny"
              and not os.path.exists(tmp) and "■ Skončilo s chybou" in log, (calls, log))
        # stopped by the user: the return code of a killed process is 1 too, but nothing may be kept
        slow = os.path.join(SCRIPTS, "sedmzip_pomalu.py")
        write(slow, "import sys, time\nopen(sys.argv[8], 'w').write('pul')\nprint('bezi', flush=True)\n"
                    "time.sleep(60)\n")
        dp.find_7zip = lambda configured="": sys.executable
        real_start = app.start_tool
        app.start_tool = lambda tool, cmd, cwd, **k: real_start(tool, [cmd[0], slow] + cmd[1:], cwd, **k)
        old = open(target, "rb").read()
        try:
            start()
            reset(True)
            app.clear_log()
            key(app.left.tree, "<Alt-F5>")
            pump(lambda: "bezi" in log_text() and os.path.exists(tmp), 20)
            app.stop_tool()
            pump(lambda: app.proc is None and "■" in log_text(), 20)
        finally:
            app.start_tool = real_start
        check("stopped packing: no archive from the half-written file, old archive untouched",
              "Archiv nevznikl." in log_text() and not os.path.exists(tmp) and open(target, "rb").read() == old
              and kinds() == ["askyesno"], (log_text(), calls))
    finally:
        dp.find_7zip = real_find

    # a single file and a name taken by a folder
    select(app.left, "sam.txt")
    log = pack()
    check("a file under the cursor is packed into name.ext.7z", "■ Hotovo" in log
          and listing(os.path.join(base, "sam.txt.7z")) == ["sam.txt"], log)
    os.remove(target)
    os.mkdir(target)
    start()
    log = pack()
    check("a folder already has the archive's name: error, nothing runs", kinds() == ["showerror"]
          and target in calls[0][1][1] and "▶" not in log and os.path.isdir(target), (calls, log))
    os.rmdir(target)

    app.show_help("Kopírování, přesun a mazání")
    text = app.help_window.text.get("1.0", "end")
    check("help explains packing", "Alt+F5 zabalit (7-Zip)" in text and "cesta_7zip" in text, text[:300])
    app.show_help("Klávesy a myš")
    check("help: Alt+F5 among the keys", "Alt+F5" in app.help_window.text.get("1.0", "end"))
    app.help_window.destroy()
    start()
    reset(False)
    key(app.left.tree, "<F5>")
    check("plain F5 is still copying (asks, Cancel)", kinds() == ["askokcancel"] and calls[0][1][0] == "Kopírovat"
          and app.proc is None, calls)
    app.left.load(L); app.right.load(R)


for fn in (v110_pack,):
    section(fn)
