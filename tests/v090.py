# Tests for 0.9.0 (git pull in the active pane's folder, font size); exec'd inside harness.py.
# Works only with repositories created inside the test folder.


def v090_git_pull():
    """0.9.0 Git pull (Ctrl+G) in the repository of the active pane's folder"""
    base = os.path.join(ENV, "git")
    origin, clone = os.path.join(base, "origin"), os.path.join(base, "klon")
    os.makedirs(os.path.join(origin, "sub"))

    def git(cwd, *args):
        r = subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"git {args}: {r.stdout}{r.stderr}")
        return r.stdout.strip()

    def commit(repo, message, **files):
        for rel, data in files.items():
            write(os.path.join(repo, *rel.split("/")), data)
        git(repo, "add", "-A")
        git(repo, "commit", "-m", message)

    def pull(timeout=40):
        app.clear_log()
        key(app.left.tree, "<Control-g>")
        pump(lambda: app.proc is None and "■" in log_text(), timeout)
        return log_text()

    git(origin, "init")
    write(os.path.join(origin, "sub", "prvni.txt"), "1")
    commit(origin, "prvni")
    git(base, "clone", origin, clone)
    sub = os.path.join(clone, "sub")

    check("find_git_root: repository root from a subfolder, None outside",
          dp.find_git_root(sub) == clone and dp.find_git_root(clone) == clone and dp.find_git_root(L) is None,
          (dp.find_git_root(sub), dp.find_git_root(L)))
    menubar = app.nametowidget(app["menu"])
    cm = app.nametowidget(menubar.entrycget(menubar.index("Příkazy"), "menu"))
    idx = cm.index("Git pull v aktuální složce")
    check("Příkazy → Git pull v aktuální složce (Ctrl+G)", cm.entrycget(idx, "accelerator") == "Ctrl+G")

    # the tool file comes with the pull: the menu must show it without "Načíst nástroje znovu"
    inc = os.path.join(clone, "dvojpanel_nastroje.json")
    dp.CONFIG_FILE.write_text(json.dumps({"vlozit": [inc.replace("\\", "/")]}), encoding="utf-8")
    app.reload_tools(startup=True)
    check("before the pull the included tool file is missing", app.tools == [] and app.tools_error, app.tools_error)
    commit(origin, "druhy", **{"sub/novy.txt": "2", "dvojpanel.py": '__version__ = "99.0.0"\n',
                              "dvojpanel_nastroje.json": json.dumps({"nastroje": [
                                  {"nazev": "Z gitu", "skript": "dvojpanel.py"}]})})

    app.right.load(R)
    app.left.load(sub)
    app.set_active(app.left)
    real_app_dir = dp.APP_DIR
    dp.APP_DIR = pathlib.Path(clone)  # as if the pulled repository were Dvojpanel itself
    try:
        reset()
        log = pull()
        check("Ctrl+G in a subfolder runs git pull --ff-only in the repository root",
              "▶ Git pull" in log and "pull --ff-only" in log and f"(složka: {clone})" in log, log)
        check("pull succeeded, new file is there and the pane shows it", "■ Hotovo" in log
              and os.path.exists(os.path.join(sub, "novy.txt")) and "novy.txt" in names(app.left),
              (log, names(app.left)))
        check("no dialog, status says done", not calls and app.status_var.get() == "Git pull: hotovo",
              (calls, app.status_var.get()))
        check("tools reloaded after the pull", [t["nazev"] for t in app.tools] == ["Z gitu"]
              and app.tools_error is None, (app.tools, app.tools_error))
        check("pull of Dvojpanel itself: note about the new version and restart",
              "verzi 99.0.0" in log and "po novém spuštění" in log, log)
    finally:
        dp.APP_DIR = real_app_dir

    reset()
    log = pull()
    check("nothing new: still succeeds, no restart note for another repository",
          "■ Hotovo" in log and "po novém spuštění" not in log and not calls, log)

    reset()
    cm.invoke(idx)
    pump(lambda: app.proc is None and "■ Hotovo" in log_text(), 40)
    check("menu item runs it too", log_text().count("▶ Git pull") == 2, log_text())

    # diverged history: --ff-only must fail and leave the local work alone
    commit(clone, "lokalni", **{"sub/lokalni.txt": "moje"})
    commit(origin, "treti", **{"sub/treti.txt": "3"})
    head = git(clone, "rev-parse", "HEAD")
    reset()
    log = pull()
    check("diverged history: error in the log, nothing merged or lost", "■ Skončilo s chybou" in log
          and git(clone, "rev-parse", "HEAD") == head and not os.path.exists(os.path.join(sub, "treti.txt"))
          and open(os.path.join(sub, "lokalni.txt"), encoding="utf-8").read() == "moje"
          and git(clone, "status", "--porcelain") == "", log)
    check("failed pull: status shows the error", app.status_var.get().startswith("Git pull: chyba"),
          app.status_var.get())

    app.left.load(L)
    reset()
    app.clear_log()
    app.git_pull()
    check("folder outside a repository: warning with the folder, nothing runs", kinds() == ["showwarning"]
          and L in calls[0][1][1] and app.proc is None and "▶" not in log_text(), (calls, log_text()))

    app.left.load(sub)
    real_which = dp.shutil.which
    dp.shutil.which = lambda name, *a, **k: None if name == "git" else real_which(name, *a, **k)
    try:
        reset()
        app.git_pull()
        check("git not installed: error, nothing runs", kinds() == ["showerror"] and "git nebyl nalezen" in calls[0][1][1]
              and app.proc is None, calls)
    finally:
        dp.shutil.which = real_which

    app.proc = object()  # a tool is running
    try:
        reset()
        app.clear_log()
        app.git_pull()
        check("a running tool blocks git pull", kinds() == ["showinfo"] and "▶" not in log_text(), calls)
    finally:
        app.proc = None

    app.show_help("Oblíbené a nastavení")
    text = app.help_window.text.get("1.0", "end")
    check("help explains git pull", "Git pull (Ctrl+G)" in text and "--ff-only" in text, text[:300])
    app.help_window.destroy()

    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()
    app.left.load(L)
    app.right.load(R)


def v090_font_size():
    """0.9.0 Font size: dvojpanel.json "velikost_pisma", Ctrl++ / Ctrl+- / Ctrl+0"""
    from tkinter import font as tkfont

    def size(name="TkDefaultFont"):
        return tkfont.nametofont(name, root=app).cget("size")

    def row_height():
        app.update()
        lt = app.left.tree
        return lt.bbox(lt.get_children()[0])[3]

    def log_size():
        return tkfont.Font(root=app, font=app.log_text["font"]).cget("size")

    def stored():
        return json.loads(dp.SETTINGS_FILE.read_text(encoding="utf-8"))

    if dp.SETTINGS_FILE.exists():
        os.remove(dp.SETTINGS_FILE)
    app.left.load(L); app.right.load(R)
    base, base_menu, base_row = size(), size("TkMenuFont"), row_height()
    check("default: velikost_pisma 9, fonts untouched", dp.SETTINGS_DEFAULTS["velikost_pisma"] == 9
          and app.settings["velikost_pisma"] == 9 and dp.font_delta == 0 and log_size() == 9, (base, log_size()))
    for bad in ("velké", 3, 40, True, 9.5):
        dp.SETTINGS_FILE.write_text(json.dumps({"velikost_pisma": bad}), encoding="utf-8")
        err = dp.load_settings()[1]
        check(f"velikost_pisma {bad!r} -> error naming the key", err and "velikost_pisma" in err, err)

    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R, "velikost_pisma": 14,
                                            "moje_poznamka": "x"}), encoding="utf-8")
    reset()
    app.reload_settings()
    pump(timeout=0.5)
    check("velikost_pisma 14 from the file: panes, menu and tool output grow by 5",
          size() == base + 5 and size("TkMenuFont") == base_menu + 5 and log_size() == 14 and not calls,
          (size(), size("TkMenuFont"), log_size(), calls))
    big_row = row_height()
    check("rows of the panes are higher, text fits", big_row > base_row
          and big_row >= tkfont.nametofont("TkDefaultFont", root=app).metrics("linespace"), (base_row, big_row))
    key(app.left.tree, "<F1>")
    hw = app.help_window
    check("help uses the size too", tkfont.Font(root=app, font=hw.text["font"]).cget("size") == 15,
          hw.text["font"])
    key(app.left.tree, "<Control-plus>")
    check("Ctrl++: 15, stored in dvojpanel.json, other keys kept, open help closed",
          size() == base + 6 and stored() == {"levy_panel": L, "pravy_panel": R, "velikost_pisma": 15,
                                               "moje_poznamka": "x"} and not hw.winfo_exists()
          and app.status_var.get() == "Velikost písma: 15", (size(), stored(), app.status_var.get()))
    key(app.left.tree, "<Control-minus>")
    key(app.left.tree, "<Control-minus>")
    check("Ctrl+- twice: 13", size() == base + 4 and stored()["velikost_pisma"] == 13, (size(), stored()))
    mb = app.nametowidget(app["menu"])
    fmenu = app.nametowidget(mb.entrycget(mb.index("Soubor"), "menu"))
    fmenu.invoke(fmenu.index("Větší písmo"))
    fmenu.invoke(fmenu.index("Menší písmo"))
    check("menu Soubor → Větší / Menší písmo", stored()["velikost_pisma"] == 13 and size() == base + 4, stored())
    key(app.left.tree, "<Control-Key-0>")
    check("Ctrl+0: default size, rows and tool output back", size() == base and size("TkMenuFont") == base_menu
          and row_height() == base_row and log_size() == 9 and stored()["velikost_pisma"] == 9
          and "výchozí" in app.status_var.get(), (size(), row_height(), log_size(), stored()))

    dp.SETTINGS_FILE.write_text(json.dumps({"velikost_pisma": 24}), encoding="utf-8")
    app.settings, _ = dp.load_settings()
    app.apply_font_size()
    app.change_font_size(1)
    check("upper limit 24", app.settings["velikost_pisma"] == 24 and size() == base + 15, size())
    dp.SETTINGS_FILE.write_text(json.dumps({"velikost_pisma": 6}), encoding="utf-8")
    app.settings, _ = dp.load_settings()
    app.apply_font_size()
    app.change_font_size(-1)
    check("lower limit 6", app.settings["velikost_pisma"] == 6 and size() == base - 3 and row_height() > 0, size())

    dp.SETTINGS_FILE.write_text("{ rozbité", encoding="utf-8")
    reset()
    app.change_font_size(1)
    check("broken dvojpanel.json: error, file kept, size unchanged", kinds() == ["showerror"]
          and dp.SETTINGS_FILE.read_text(encoding="utf-8") == "{ rozbité" and size() == base - 3, (calls, size()))

    # a fresh start reads the size
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R, "velikost_pisma": 12}),
                                encoding="utf-8")
    app2 = dp.App()
    app2.update()
    check("startup uses velikost_pisma", tkfont.nametofont("TkDefaultFont", root=app2).cget("size") == base + 3
          and app2.settings["velikost_pisma"] == 12)
    app2.destroy()
    os.remove(dp.SETTINGS_FILE)
    app.settings, _ = dp.load_settings()
    app.apply_font_size()
    app.update()
    check("back to the default for the rest of the tests", size() == base and row_height() == base_row
          and dp.font_delta == 0)
    app.left.load(L); app.right.load(R)


for fn in (v090_git_pull, v090_font_size):
    section(fn)
