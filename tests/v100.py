# Tests for 0.10.0 (language: Czech, English, German, Polish from preklady.json); exec'd inside harness.py.


def v100_translations():
    """0.10.0 preklady.json covers every text of the program in every language"""
    import ast
    import re
    import string
    src = open(os.path.join(REL, "dvojpanel.py"), encoding="utf-8").read()
    keys, dynamic = set(), []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("tr", "tr_mark"):
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
            else:
                dynamic.append(ast.unparse(arg))
    data = json.loads(dp.LANG_FILE.read_text(encoding="utf-8"))
    langs = data["jazyky"]
    check("languages: cs in the program, en / de / pl in preklady.json",
          langs == ["en", "de", "pl"] and list(dp.LANGUAGES) == ["cs"] + langs, (langs, dp.LANGUAGES))
    check("the program has texts to translate", len(keys) > 200, len(keys))
    missing = sorted(keys - set(data["texty"]))
    check("every tr() / tr_mark() text has translations", not missing, missing[:10])
    unused = sorted(set(data["texty"]) - keys)
    check("no translations of texts the program no longer has", not unused, unused[:10])
    # tr(variable) is only used for texts marked with tr_mark() where they are defined
    check("tr() of a variable only for marked texts", set(dynamic) <= {
        "EMPTY_PLACEHOLDER[name]", "default_label", "FILE_PROMPTS[name][1]", "self.TITLES[col]",
        "self.STATUS_TEXT[row['status']]"}, dynamic)

    def fields(text):
        return sorted(f"{name}:{spec}!{conv}" for _, name, spec, conv in string.Formatter().parse(text)
                      if name is not None)

    def edges(text):
        return len(text) - len(text.lstrip(" \n")), len(text) - len(text.rstrip(" \n")), text.count("\n")

    wrong = [(cs, lang) for cs, variants in data["texty"].items() for lang, text in zip(langs, variants)
             if len(variants) != len(langs) or not text.strip() or fields(cs) != fields(text) or edges(cs) != edges(text)]
    check("translations keep the {placeholders}, line breaks and outer spaces", not wrong, wrong[:10])

    def kind(line):
        return ("h" if line.startswith("## ") else "t" if "\t" in line else "b" if line.startswith("• ")
                else "n" if re.match(r"\d\.", line) else "e" if not line else "p")

    topics = dict(dp.HELP_TOPICS)
    check("help: every topic is translated", set(data["napoveda"]) == set(topics),
          set(data["napoveda"]) ^ set(topics))
    for lang in langs:
        diff = [title for title, body in topics.items()
                if [kind(ln) for ln in data["napoveda"][title][lang][1:]]
                != ([kind(ln) for ln in body.split("\n")] if body else [])]
        check(f"help ({lang}): same headings, tables and bullets as the Czech text", not diff, diff)
        titles = [data["napoveda"][title][lang][0] for title in topics]
        check(f"help ({lang}): titles translated and unique", len(set(titles)) == len(titles)
              and not set(titles) & set(topics), titles)


def v100_switch():
    """0.10.0 Soubor → Jazyk / Language switches the whole program"""
    def cascades():
        mb = app.nametowidget(app["menu"])
        return [mb.entrycget(i, "label") for i in range(mb.index("end") + 1) if mb.type(i) == "cascade"]

    def file_menu():
        mb = app.nametowidget(app["menu"])
        first = next(i for i in range(mb.index("end") + 1) if mb.type(i) == "cascade")  # 0 is the tear-off
        return app.nametowidget(mb.entrycget(first, "menu"))

    def labels(menu):
        return [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                if menu.type(i) in ("command", "cascade", "checkbutton")]

    def choose(name):
        fm = file_menu()
        lm = app.nametowidget(fm.entrycget(fm.index("Jazyk / Language"), "menu"))
        lm.invoke(lm.index(name))
        pump(timeout=0.3)

    def bar():
        return [b["text"] for b in app.key_bar.winfo_children()]

    def heads():
        return [app.left.tree.heading(c, "text") for c in app.left.COLUMNS]

    def stored():
        return json.loads(dp.SETTINGS_FILE.read_text(encoding="utf-8")) if dp.SETTINGS_FILE.exists() else {}

    if dp.SETTINGS_FILE.exists():
        os.remove(dp.SETTINGS_FILE)
    echo = os.path.join(SCRIPTS, "echo_args.py")
    dp.CONFIG_FILE.write_text(json.dumps({"nastroje": [{"nazev": "Ozvěna", "skript": echo, "popis": "Můj popis."}]},
                                         ensure_ascii=False), encoding="utf-8")
    app.reload_tools()
    folder = os.path.join(ENV, "jazyk")
    os.makedirs(folder)
    write(os.path.join(folder, "x.txt"), "x")
    app.left.load(folder); app.right.load(R)
    app.set_active(app.left)
    czech_menus, czech_bar, czech_file = cascades(), bar(), labels(file_menu())
    check("default language is Czech", dp.language == "cs" and app.settings["jazyk"] == "cs"
          and dp.SETTINGS_DEFAULTS["jazyk"] == "cs" and czech_menus[0] == "Soubor" and "F5 Kopírovat" in czech_bar,
          (dp.language, czech_menus, czech_bar))
    fm = file_menu()
    lm = app.nametowidget(fm.entrycget(fm.index("Jazyk / Language"), "menu"))
    check("Soubor → Jazyk / Language offers the four languages",
          labels(lm) == [] and [lm.entrycget(i, "label") for i in range(lm.index("end") + 1)]
          == ["Čeština", "English", "Deutsch", "Polski"])

    reset()
    choose("English")
    check("English: stored in dvojpanel.json, no dialog", dp.language == "en" and stored() == {"jazyk": "en"}
          and not calls, (dp.language, stored(), calls))
    check("English: menus", cascades() == ["File", "Commands", "Favorites", "Tools", "Help"], cascades())
    check("English: File menu items", "Refresh" in labels(file_menu()) and "Exit" in labels(file_menu())
          and "Jazyk / Language" in labels(file_menu()), labels(file_menu()))
    check("English: F-key bar", bar() == ["F1 Help", "F2 Rename", "F3 Open", "F4 Edit", "F5 Copy", "F6 Move",
                                          "F7 New folder", "F8 Delete", "F9 Tools"], bar())
    check("English: column headings and status line", heads()[0].startswith("Name") and heads()[2:] == ["Size", "Modified"]
          and app.status_var.get() == "Language: English", (heads(), app.status_var.get()))
    check("English: Tools menu and favorites bar", "Reload tools" in labels(app.tools_menu)
          and "Ozvěna" in labels(app.tools_menu) and app.fav_bar.buttons[-1]["text"] == "+ Add",
          labels(app.tools_menu))
    select(app.left, "x.txt")
    check("English: pane status", app.left.status_var.get().startswith("Selected"), app.left.status_var.get())
    reset()
    app.git_pull()
    check("English: message box texts", kinds() == ["showwarning"]
          and calls[0][1][1].startswith("This folder is not in a git repository:"), calls)
    reset(False)
    select(app.left, "x.txt")
    key(app.left.tree, "<F8>")
    check("English: confirmation of deleting", calls and calls[0][1][0] == "Delete"
          and calls[0][1][1] == "Move 1 items to the Recycle Bin?", calls)
    log = run("Ozvěna")
    check("English: tool output frame", "■ Done" in log and "(folder: " in log
          and app.status_var.get() == "Ozvěna: done", (log, app.status_var.get()))
    key(app.left.tree, "<F1>")
    hw = app.help_window
    titles = list(hw.listbox.get(0, "end"))
    text = hw.text.get("1.0", "end")
    check("English: help window and topics", hw.title().startswith("Help – Dvojpanel") and titles[0] == "Getting started"
          and "My tools" in titles and text.startswith("Getting started") and "file manager with two panes" in text,
          (hw.title(), titles, text[:100]))
    for index, title in enumerate(titles):
        hw.show(dp.HELP_TOPICS[index][0])  # topics are still identified by their Czech titles
        text = hw.text.get("1.0", "end")
        check(f"English: topic '{title}' has text", text.startswith(title) and len(text) > 150, text[:120])
    app.show_help(dp.MY_TOOLS)
    text = hw.text.get("1.0", "end")
    check("English: My tools describes the tools, the tool's own 'popis' stays as written",
          text.startswith("My tools") and "Ozvěna" in text and "Můj popis." in text and "Runs: echo_args.py" in text and "No group" in text
          and "runs without parameters" in text, text)
    app.open_sync()
    sw = app.sync_window
    check("English: compare window", sw.title() == "Compare and synchronize folders"
          and sw.tree.heading("status", "text") == "Status" and sw.compare_btn["text"] == "Compare")

    for name, code, menus, f5, topic in (
            ("Deutsch", "de", ["Datei", "Befehle", "Favoriten", "Tools", "Hilfe"], "F5 Kopieren", "Erste Schritte"),
            ("Polski", "pl", ["Plik", "Polecenia", "Ulubione", "Narzędzia", "Pomoc"], "F5 Kopiuj", "Pierwsze kroki")):
        choose(name)
        check(f"{name}: menus, bar, stored", dp.language == code and cascades() == menus and f5 in bar()
              and stored() == {"jazyk": code} and app.status_var.get().endswith(name),
              (cascades(), bar(), stored(), app.status_var.get()))
        check(f"{name}: windows opened in the previous language are closed", not hw.winfo_exists()
              and not sw.winfo_exists())
        key(app.left.tree, "<F1>")
        hw = app.help_window
        titles = list(hw.listbox.get(0, "end"))
        check(f"{name}: help", titles[0] == topic and hw.text.get("1.0", "end").startswith(topic), titles)
        for index, title in enumerate(titles):
            hw.show(dp.HELP_TOPICS[index][0])
            text = hw.text.get("1.0", "end")
            check(f"{name}: topic '{title}' has text", text.startswith(title) and len(text) > 150, text[:120])
        app.open_sync()
        sw = app.sync_window
        check(f"{name}: no Czech left in the menus", not set(labels(file_menu())) & (set(czech_file) - {
            "Jazyk / Language", "Upravit dvojpanel.json"}) and not set(bar()) & set(czech_bar),
            (labels(file_menu()), bar()))

    choose("Čeština")
    check("back to Czech: everything as before", dp.language == "cs" and cascades() == czech_menus
          and bar() == czech_bar and labels(file_menu()) == czech_file and stored() == {"jazyk": "cs"}
          and heads()[0].startswith("Název") and app.status_var.get() == "Jazyk: Čeština",
          (cascades(), bar(), stored(), app.status_var.get()))
    check("F keys still work after the bar was rebuilt", True)
    key(app.left.tree, "<F1>")
    check("F1 after switching back", app.help_window.winfo_exists()
          and app.help_window.text.get("1.0", "end").startswith("Začínáme"))
    app.help_window.destroy()

    # dvojpanel.json written by hand
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R, "jazyk": "de"}), encoding="utf-8")
    reset()
    app.reload_settings()
    pump(timeout=0.3)
    check('"jazyk": "de" in dvojpanel.json + reload', dp.language == "de" and cascades()[0] == "Datei" and not calls,
          (dp.language, cascades(), calls))
    for bad in ("xx", 1, None):
        dp.SETTINGS_FILE.write_text(json.dumps({"jazyk": bad}), encoding="utf-8")
        err = dp.load_settings()[1]
        check(f"jazyk {bad!r} -> error naming the key and the choices", err and "'jazyk'" in err and '"pl"' in err, err)
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R}), encoding="utf-8")
    app.reload_settings()
    pump(timeout=0.3)
    check("no jazyk in the file -> Czech", dp.language == "cs" and cascades() == czech_menus, cascades())

    # missing or broken preklady.json: the program says so and stays Czech
    real_file = dp.LANG_FILE
    try:
        dp.LANG_FILE = pathlib.Path(ENV) / "neni" / "preklady.json"
        reset()
        choose("English")
        check("missing preklady.json: error, still Czech, setting not changed", kinds() == ["showerror"]
              and "preklady.json" in calls[0][1][1] and dp.language == "cs" and cascades() == czech_menus
              and "jazyk" not in stored() and app.language_var.get() == "cs", (calls, dp.language, stored()))
        dp.LANG_FILE = pathlib.Path(ENV) / "rozbite_preklady.json"
        dp.LANG_FILE.write_text("{ rozbité", encoding="utf-8")
        check("broken preklady.json: error message, Czech", dp.set_language("pl") and dp.language == "cs"
              and dp.tr("Složka") == "Složka")
    finally:
        dp.LANG_FILE = real_file

    dp.SETTINGS_FILE.write_text("{ rozbité", encoding="utf-8")
    reset()
    choose("English")
    check("broken dvojpanel.json: error, file kept, language unchanged", kinds() == ["showerror"]
          and dp.SETTINGS_FILE.read_text(encoding="utf-8") == "{ rozbité" and dp.language == "cs"
          and cascades() == czech_menus, (calls, dp.language))

    # a fresh start in English
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R, "jazyk": "en"}), encoding="utf-8")
    app2 = dp.App()
    app2.update()
    mb2 = app2.nametowidget(app2["menu"])
    check("startup uses jazyk", dp.language == "en" and mb2.entrycget(mb2.index("File"), "label") == "File"
          and app2.status_var.get() in ("Ready", "Opening {0}…".format(L), "Opening {0}…".format(R))
          and app2.left.tree.heading("name", "text").startswith("Name"), (dp.language, app2.status_var.get()))
    app2.destroy()
    os.remove(dp.SETTINGS_FILE)
    app.reload_settings()
    pump(timeout=0.5)
    check("back to Czech for the rest of the tests", dp.language == "cs" and cascades() == czech_menus
          and bar() == czech_bar)
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()
    app.left.load(L); app.right.load(R)


for fn in (v100_translations, v100_switch):
    section(fn)
