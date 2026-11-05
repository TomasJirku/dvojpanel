# Tests for 0.6.0; exec'd inside test_release.py (shares its globals).
from tkinter import filedialog


def tree_xy(pane, item, col="name"):
    """Screen and widget coordinates of the middle of a cell."""
    t = pane.tree
    t.see(item)
    app.update()
    x, y, w, h = t.bbox(item, col)
    return x + min(w // 2, 30), y + h // 2


CLOCK = [10_000_000]


def mouse(pane, seq, item=None, xy=None, state=0, target=None, double=False):
    """Generate a mouse event on pane.tree at a cell, optionally with the pointer over another widget.
    Event times are 1 s apart so Tk never merges presses into a double-click unless double=True."""
    t = pane.tree
    CLOCK[0] += 50 if double else 1000
    x, y = xy if xy else tree_xy(pane, item)
    tw = target or t
    rx, ry = tw.winfo_rootx() + x, tw.winfo_rooty() + y
    t.event_generate(seq, x=rx - t.winfo_rootx(), y=ry - t.winfo_rooty(), rootx=rx, rooty=ry, state=state, time=CLOCK[0])
    app.update()


def drag(src, item, dest_pane, dest_item=None, shift=False, dest_xy=None):
    """Press on item in src, move over dest (row or empty area), release."""
    mouse(src, "<Button-1>", item)
    mouse(src, "<B1-Motion>", xy=(tree_xy(src, item)[0] + 15, tree_xy(src, item)[1] + 15), state=0x100)
    xy = dest_xy or tree_xy(dest_pane, dest_item)
    st = 0x100 | (1 if shift else 0)
    mouse(src, "<B1-Motion>", xy=xy, state=st, target=dest_pane.tree)
    status = app.status_var.get()
    mouse(src, "<ButtonRelease-1>", xy=xy, state=st, target=dest_pane.tree)
    return status


def v060_rename():
    """0.6.0 Rename in place"""
    check("rename_error: empty", dp.rename_error(L, "a.txt", "  ") is not None)
    check("rename_error: invalid chars", "?" in (dp.rename_error(L, "a.txt", "a?b.txt") or ""))
    check("rename_error: trailing dot", dp.rename_error(L, "a.txt", "a.") is not None)
    check("rename_error: existing", "už existuje" in (dp.rename_error(L, "a.txt", "b.txt") or ""))
    check("rename_error: case-only change allowed", dp.rename_error(L, "a.txt", "A.txt") is None)
    check("rename_error: ok", dp.rename_error(L, "a.txt", "nový.txt") is None)

    lt = app.left.tree
    app.left.load(L); app.right.load(L)
    select(app.left, "file with space.txt")
    reset()
    key(lt, "<F2>")
    ed = app.left.editor
    check("F2 opens an entry over the name", ed is not None and ed[0].winfo_ismapped(), ed)
    if ed:
        e = ed[0]
        check("name without extension preselected", e.selection_get() == "file with space", e.selection_get())
        check("entry has keyboard focus", app.focus_get() is e, app.focus_get())
        ed[2].set("x/y.txt")
        key(e, "<Return>")
        check("invalid name -> error, file kept",
              kinds() == ["showerror"] and os.path.exists(os.path.join(L, "file with space.txt")), calls)
    select(app.left, "data.xlsx")
    reset()
    key(lt, "<F2>")
    ed = app.left.editor
    ed[2].set("Data.xlsx")
    key(ed[0], "<Return>")
    check("case-only rename works", "Data.xlsx" in os.listdir(L) and not calls, (os.listdir(L), calls))
    select(app.left, "Data.xlsx")
    key(lt, "<F2>")
    ed = app.left.editor
    ed[2].set("  data.xlsx  ")
    app.right.tree.focus_force()  # focus moves away = commit (like Explorer)
    pump(timeout=0.3)
    check("focus out commits, spaces trimmed", "data.xlsx" in os.listdir(L) and app.left.editor is None, os.listdir(L))
    check("focus stays where the user clicked", app.focus_get() is app.right.tree, app.focus_get())
    select(app.left, "sub")
    key(lt, "<F2>")
    ed = app.left.editor
    check("folder: whole name preselected", ed and ed[0].selection_get() == "sub")
    key(ed[0], "<Escape>")
    check("Esc cancels, no job cancel side effects", app.left.editor is None and os.path.isdir(os.path.join(L, "sub")))
    select(app.left, "a.txt")
    reset()
    key(lt, "<F2>")
    app.left.reload()
    check("reload closes the editor without renaming", app.left.editor is None and os.path.exists(os.path.join(L, "a.txt")))

    # slow second click on the name of the selected item
    select(app.left, "a.txt")
    a = os.path.join(L, "a.txt")
    mouse(app.left, "<Button-1>", a)
    mouse(app.left, "<ButtonRelease-1>", a)
    check("slow click schedules rename", app.left.rename_job is not None)
    pump(lambda: app.left.editor is not None, 2)
    check("slow click opens editor after delay", app.left.editor is not None)
    if app.left.editor:
        key(app.left.editor[0], "<Escape>")
    select(app.left, "a.txt")
    mouse(app.left, "<Button-1>", a)
    mouse(app.left, "<ButtonRelease-1>", a, double=True)
    mouse(app.left, "<Button-1>", a, double=True)  # second press within the double-click time
    mouse(app.left, "<ButtonRelease-1>", a, double=True)
    pump(timeout=1)
    check("double click does not rename (opens file)", app.left.editor is None and a in started, started)
    select(app.left, "b.txt")
    mouse(app.left, "<Button-1>", a)
    mouse(app.left, "<ButtonRelease-1>", a)
    check("click on an unselected item does not rename", app.left.rename_job is None)
    select(app.left, "a.txt")
    mouse(app.left, "<Button-1>", a, xy=tree_xy(app.left, a, "size"))
    mouse(app.left, "<ButtonRelease-1>", a, xy=tree_xy(app.left, a, "size"))
    check("second click on size column does not rename", app.left.rename_job is None)
    select(app.left, "a.txt")
    mouse(app.left, "<Button-1>", a, state=4)
    mouse(app.left, "<ButtonRelease-1>", a, state=4)
    check("Ctrl+click does not rename", app.left.rename_job is None)


def v060_swap():
    """0.6.0 Swap panes (Ctrl+U)"""
    app.left.load(L); app.right.load(R)
    select(app.left, "b.txt")
    app.left.set_marked(os.path.join(L, "a.txt"), True)
    key(app.left.tree, "<Control-u>")
    check("Ctrl+U swaps folders", app.left.path == R and app.right.path == L, (app.left.path, app.right.path))
    check("active side stays left", app.active is app.left)
    check("cursor follows the folder", app.right.tree.focus() == os.path.join(L, "b.txt"), app.right.tree.focus())
    check("marks cleared", not app.left.marked and not app.right.marked)
    mb = app.nametowidget(app["menu"])
    cm = app.nametowidget(mb.entrycget(mb.index("Příkazy"), "menu"))
    cm.invoke(cm.index("Prohodit panely"))
    check("menu Příkazy → Prohodit panely swaps back", app.left.path == L and app.right.path == R)


def v060_drag():
    """0.6.0 Drag & drop inside the program"""
    app.left.load(L); app.right.load(R)
    app.geometry("1150x760+20+20")
    app.lift(); app.focus_force()
    pump(timeout=0.5)
    a = os.path.join(L, "a.txt")
    select(app.left, "a.txt")
    reset(True)
    status = drag(app.left, a, app.right, dest_xy=(50, app.right.tree.winfo_height() - 10))
    check("hover shows target in status", "Kopírovat 1 položek do: " + R in status, status)
    wait_job()
    check("drag to other pane copies (asks first)", os.path.exists(os.path.join(R, "a.txt"))
          and os.path.exists(a) and kinds() == ["askokcancel"], (calls, os.listdir(R)))
    check("cursor restored", str(app.left.tree["cursor"]) == "" and app.drag is None)

    os.makedirs(os.path.join(R, "cil"))
    app.right.reload()
    select(app.left, "b.txt")
    reset(True)
    status = drag(app.left, os.path.join(L, "b.txt"), app.right, os.path.join(R, "cil"), shift=True)
    check("Shift = move, hover on folder row targets that folder",
          status.startswith("Přesunout 1 položek do: " + os.path.join(R, "cil")), status)
    wait_job()
    check("moved into folder row", os.path.exists(os.path.join(R, "cil", "b.txt"))
          and not os.path.exists(os.path.join(L, "b.txt")))
    shutil.move(os.path.join(R, "cil", "b.txt"), os.path.join(L, "b.txt"))
    app.left.reload(); app.right.reload()

    # multi-selection survives the press and is dragged as a whole
    select(app.left, "a.txt", "b.txt")
    reset(True, True)
    drag(app.left, a, app.right, os.path.join(R, "cil"))
    wait_job()
    check("multi-selection dragged together", sorted(os.listdir(os.path.join(R, "cil"))) == ["a.txt", "b.txt"],
          os.listdir(os.path.join(R, "cil")))
    select(app.left, "a.txt", "b.txt")
    mouse(app.left, "<Button-1>", a)
    mouse(app.left, "<ButtonRelease-1>", a)
    check("plain click in a multi-selection selects just that item", app.left.tree.selection() == (a,),
          app.left.tree.selection())

    # marks are dragged when the drag starts on a marked item
    shutil.rmtree(os.path.join(R, "cil")); os.makedirs(os.path.join(R, "cil")); app.right.reload()
    select(app.left, "a.txt")
    app.left.set_marked(os.path.join(L, "data.xlsx"), True)
    app.left.set_marked(os.path.join(L, "b.txt"), True)
    reset(True)
    drag(app.left, os.path.join(L, "b.txt"), app.right, os.path.join(R, "cil"))
    wait_job()
    check("marked items dragged, marks cleared after success",
          sorted(os.listdir(os.path.join(R, "cil"))) == ["b.txt", "data.xlsx"] and not app.left.marked,
          os.listdir(os.path.join(R, "cil")))

    # same pane: onto a folder row moves/copies there, onto empty space nothing happens
    select(app.left, "a.txt")
    reset(True)
    drag(app.left, a, app.left, dest_xy=(50, app.left.tree.winfo_height() - 10))
    pump(timeout=0.3)
    check("drop into its own folder does nothing", not calls and not app.busy, calls)
    reset(True)
    drag(app.left, a, app.left, os.path.join(L, "sub"))
    wait_job()
    check("drop onto folder row in the same pane copies into it", os.path.exists(os.path.join(L, "sub", "a.txt")))
    os.remove(os.path.join(L, "sub", "a.txt"))
    select(app.left, "sub")
    reset(True)
    drag(app.left, os.path.join(L, "sub"), app.left, os.path.join(L, "sub"))
    pump(timeout=0.3)
    check("folder onto itself does nothing", not calls, calls)
    app.left.load(os.path.join(L, "sub")); app.right.load(R)
    inner = os.path.join(L, "sub", "inner.txt")
    select(app.left, "inner.txt")
    reset(True)
    drag(app.left, inner, app.right, dp.UP)
    wait_job()
    check("drop onto [..] of other pane = its parent folder", os.path.exists(os.path.join(HOME, "inner.txt")))
    os.remove(os.path.join(HOME, "inner.txt"))

    # Esc cancels the drag
    app.left.load(L); app.right.load(R)
    select(app.left, "a.txt")
    reset(True)
    mouse(app.left, "<Button-1>", a)
    mouse(app.left, "<B1-Motion>", xy=tree_xy(app.right, os.path.join(R, "cil")), state=0x100, target=app.right.tree)
    check("drop row highlighted", app.right.tree.tag_has("drop") == (os.path.join(R, "cil"),),
          app.right.tree.tag_has("drop"))
    key(app.left.tree, "<Escape>")
    check("Esc ends drag, highlight removed", app.drag is None and not app.right.tree.tag_has("drop"))
    mouse(app.left, "<ButtonRelease-1>", xy=tree_xy(app.right, os.path.join(R, "cil")), state=0x100,
          target=app.right.tree)
    pump(timeout=0.3)
    check("release after Esc does nothing", not calls and not os.path.exists(os.path.join(R, "cil", "a.txt")), calls)
    reset(False)
    drag(app.left, a, app.right, os.path.join(R, "cil"))
    pump(timeout=0.3)
    check("Storno in the confirmation copies nothing", not os.path.exists(os.path.join(R, "cil", "a.txt")))
    shutil.rmtree(os.path.join(R, "cil"))
    for n in ("a.txt",):
        p = os.path.join(R, n)
        if os.path.exists(p):
            os.remove(p)
    app.left.load(L); app.right.load(R)


def v060_favorites_bar():
    """0.6.0 Favorites bar"""
    bar = app.fav_bar
    proj = os.path.join(HOME, "Projekty", "P-1234 Zakázka")
    dp.save_favorites([{"nazev": "Zakázka", "cesta": proj}, {"cesta": "%DP_TEST%\\home\\L"}])
    app.reload_favorites()
    texts = [b["text"] for b in bar.buttons]
    check("bar shows favorites + Přidat", texts == ["★ Zakázka", "★ %DP_TEST%\\home\\L", "+ Přidat"], texts)
    check("bar visible by default, above the panes", bar.winfo_ismapped() and bar.winfo_y() < app.main.winfo_y())
    app.set_active(app.right)
    bar.buttons[0].invoke()
    pump(lambda: app.right.path == proj, 5)
    check("button opens folder in active pane", app.right.path == proj, app.right.path)
    app.open_favorite(app.favorites[1], app.other)
    pump(lambda: app.left.path == L, 5)
    check("context menu 'druhý panel' opens in the other pane", app.left.path == L and app.right.path == proj)
    app.right.load(R)
    # narrow window wraps the buttons into more rows
    many = [{"nazev": f"Projekt číslo {i}", "cesta": proj} for i in range(12)]
    dp.save_favorites(many)
    app.reload_favorites()
    app.geometry("500x700"); pump(timeout=0.5)
    rows_narrow = len(bar.rows)
    app.geometry("1600x760"); pump(timeout=0.5)
    check("buttons wrap in a narrow window", rows_narrow > len(bar.rows) >= 1, (rows_narrow, len(bar.rows)))
    check("no button cut off", all(b.winfo_rootx() + b.winfo_width() <= bar.winfo_rootx() + bar.winfo_width() + 1
                                   for b in bar.buttons))
    app.geometry("1150x760")
    fm = app.favorites_menu
    fm.invoke(fm.index("Zobrazit lištu oblíbených"))
    pump(timeout=0.2)
    check("menu hides bar and stores it in dvojpanel.json",
          not bar.winfo_ismapped() and json.loads(dp.SETTINGS_FILE.read_text(encoding="utf-8"))
          == {"lista_oblibenych": False}, dp.SETTINGS_FILE.read_text(encoding="utf-8") if dp.SETTINGS_FILE.exists() else "")
    check("oblibene.json untouched by the setting",
          json.loads(dp.FAVORITES_FILE.read_text(encoding="utf-8")) == {"oblibene": many})
    app.reload_favorites()
    check("stays hidden after reload", not bar.winfo_ismapped())
    fm.invoke(fm.index("Zobrazit lištu oblíbených"))
    pump(timeout=0.2)
    check("shown again", bar.winfo_ismapped() and bar.winfo_y() < app.main.winfo_y())
    os.remove(dp.FAVORITES_FILE)
    app.reload_favorites()
    check("no favorites: only the Přidat button", [b["text"] for b in bar.buttons] == ["+ Přidat"])
    os.remove(dp.SETTINGS_FILE)


def v060_settings():
    """0.6.0 dvojpanel.json start folders"""
    check("no dvojpanel.json -> defaults", dp.load_settings() == (dp.SETTINGS_DEFAULTS, None))
    reset()
    mb = app.nametowidget(app["menu"])
    fmenu = app.nametowidget(mb.entrycget(mb.index("Soubor"), "menu"))
    fmenu.invoke(fmenu.index("Upravit dvojpanel.json"))
    check("Upravit creates file with defaults and opens Notepad",
          launched == [["notepad.exe", str(dp.SETTINGS_FILE)]]
          and json.loads(dp.SETTINGS_FILE.read_text(encoding="utf-8")) == dp.SETTINGS_DEFAULTS, launched)
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": "%DP_TEST%/home/R", "pravy_panel": L,
                                            "lista_oblibenych": True, "moje_poznamka": "x"}), encoding="utf-8")
    app.left.load(HOME); app.right.load(HOME)
    reset()
    fmenu.invoke(fmenu.index("Načíst nastavení znovu"))
    pump(lambda: app.left.path == R and app.right.path == L, 5)
    check("reload opens start folders per pane (%VAR% expanded)", app.left.path == R and app.right.path == L,
          (app.left.path, app.right.path))
    app.left.load(L); app.right.load(os.path.join(L, "sub"))
    reset(True)
    fmenu.invoke(fmenu.index("Uložit aktuální složky jako výchozí…"))
    data = json.loads(dp.SETTINGS_FILE.read_text(encoding="utf-8"))
    check("save current folders asks, keeps other keys",
          kinds() == ["askyesno"] and data == {"levy_panel": L, "pravy_panel": os.path.join(L, "sub"),
                                               "lista_oblibenych": True, "moje_poznamka": "x"}, data)
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": "Z:/neni/tu", "pravy_panel": R}), encoding="utf-8")
    reset()
    app.reload_settings()
    pump(lambda: kinds() == ["showerror"] and app.right.path == R, 10)
    check("missing start folder -> error, other pane still opens", kinds() == ["showerror"] and app.right.path == R
          and app.left.path == L, (calls, app.left.path, app.right.path))
    dp.SETTINGS_FILE.write_text("{ rozbité", encoding="utf-8")
    reset()
    app.reload_settings()
    check("broken JSON -> error", kinds() == ["showerror"] and "dvojpanel.json" in calls[0][1][1], calls)
    reset()
    app.fav_bar_var.set(False)
    app.toggle_favorites_bar()
    check("toggle with broken file refused, file kept",
          kinds() == ["showerror"] and dp.SETTINGS_FILE.read_text(encoding="utf-8") == "{ rozbité", calls)
    app.show_favorites_bar(True)
    dp.SETTINGS_FILE.write_text(json.dumps({"lista_oblibenych": "ano"}), encoding="utf-8")
    check("wrong type -> error", dp.load_settings()[1] is not None)
    os.remove(dp.SETTINGS_FILE)

    # a fresh start with dvojpanel.json opens the start folders
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": R, "pravy_panel": os.path.join(L, "sub")}), encoding="utf-8")
    reset()
    app2 = dp.App()
    end = time.time() + 5
    while time.time() < end and not (app2.left.path == R and app2.right.path == os.path.join(L, "sub")):
        app2.update(); time.sleep(0.02)
    check("startup opens start folders", app2.left.path == R and app2.right.path == os.path.join(L, "sub"),
          (app2.left.path, app2.right.path))
    app2.destroy()
    os.remove(dp.SETTINGS_FILE)
    app.update()


def v060_file_prompts():
    """0.6.0 {vybrat_soubor} / {ulozit_soubor}"""
    check("parse label + exts", dp.parse_file_prompt("Přehled PN|.xlsx xls", "x", []) == ("Přehled PN", [".xlsx", ".xls"]))
    check("parse without | uses pripony", dp.parse_file_prompt("Export", "x", [".XLSX"]) == ("Export", [".xlsx"]))
    check("parse empty label -> default", dp.parse_file_prompt(None, "Vyber soubor", []) == ("Vyber soubor", []))
    try:
        dp.build_command({"nazev": "t", "skript": os.path.join(SCRIPTS, "echo_args.py"),
                          "argumenty": ["{vybrat_soubor}"]}, {"soubory": []}, lambda l: None)
        check("no pick callback -> ValueError", False)
    except ValueError:
        check("no pick callback -> ValueError", True)

    dialogs = []
    picks = []

    def fake(kind):
        def f(**k):
            dialogs.append((kind, k))
            return picks.pop(0) if picks else ""
        return f

    real = filedialog.askopenfilename, filedialog.asksaveasfilename
    filedialog.askopenfilename, filedialog.asksaveasfilename = fake("open"), fake("save")
    try:
        cfg = json.loads(dp.CONFIG_FILE.read_text(encoding="utf-8"))
        E = "%DP_TEST%/scripts/echo_args.py"
        cfg["nastroje"] += [
            {"nazev": "Dva soubory dialogem", "skript": E,
             "argumenty": ["{vybrat_soubor:Cílový přehled PN|.xlsx}", "{vybrat_soubor:Export ze SAP|.xlsx}",
                           "--znovu", "{vybrat_soubor:Cílový přehled PN|.xlsx}"], "pripony": [".xlsx"]},
            {"nazev": "Uložit dialogem", "skript": E, "argumenty": ["--vystup", "{ulozit_soubor:Výsledek|.xlsx}"]},
            {"nazev": "Dialog s pripony", "skript": E, "argumenty": ["{vybrat_soubor:Vstup}"], "pripony": [".txt"]},
        ]
        dp.CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        app.reload_tools()
        app.left.load(L); app.right.load(R)
        select(app.left, "a.txt")  # wrong extension selected: must not matter for dialog tools
        target, sapx = os.path.join(L, "data.xlsx"), os.path.join(R, "SAP.xlsx")
        write(sapx, "s")
        picks[:] = [target.replace("\\", "/"), sapx.replace("\\", "/")]
        reset()
        log = run("Dva soubory dialogem")
        check("selection with other extension does not block a dialog tool", not calls, calls)
        check("two dialogs, labels in titles, filter .xlsx, same label asked once",
              [d[1]["title"] for d in dialogs] == ["Dva soubory dialogem: Cílový přehled PN",
                                                    "Dva soubory dialogem: Export ze SAP"]
              and dialogs[0][1]["filetypes"][0] == ("Cílový přehled PN (.xlsx)", "*.xlsx"), dialogs)
        check("dialog starts in the active pane folder", dialogs[0][1]["initialdir"] == L, dialogs[0][1]["initialdir"])
        check("paths passed normalized, in order", (parsed(log) or {}).get("args") == [target, sapx, "--znovu", target], log)
        dialogs.clear()
        app.left.load(HOME)
        picks[:] = [target, sapx]
        run("Dva soubory dialogem")
        check("next time each dialog starts where it was last used",
              [d[1]["initialdir"] for d in dialogs] == [L, R], [d[1]["initialdir"] for d in dialogs])
        dialogs.clear()
        picks[:] = [""]
        app.clear_log()
        app.run_tool(tool("Dva soubory dialogem"))
        pump(timeout=0.3)
        check("cancel in the dialog -> tool does not run", app.proc is None and "▶" not in log_text(), log_text())
        picks[:] = [os.path.join(L, "a.txt")]
        reset()
        app.clear_log()
        app.run_tool(tool("Dva soubory dialogem"))
        check("wrong extension picked -> warning, not run", kinds() == ["showwarning"] and "▶" not in log_text(), calls)
        dialogs.clear()
        out = os.path.join(OUT, "vysledek.xlsx")
        picks[:] = [out.replace("\\", "/")]
        log = run("Uložit dialogem")
        check("{ulozit_soubor}: save dialog with default extension",
              dialogs and dialogs[0][0] == "save" and dialogs[0][1]["defaultextension"] == ".xlsx"
              and (parsed(log) or {}).get("args") == ["--vystup", out], (dialogs, log))
        dialogs.clear()
        picks[:] = [os.path.join(L, "a.txt")]
        log = run("Dialog s pripony")
        check("without | the filter comes from pripony", dialogs[0][1]["filetypes"][0] == ("Vstup (.txt)", "*.txt")
              and (parsed(log) or {}).get("args") == [os.path.join(L, "a.txt")], (dialogs, log))
        # template tool with the real aktualizuj_ze_sap.py (files from test_v050)
        sapdir = os.path.join(ENV, "sap")
        target = os.path.join(sapdir, "prehled", "PNs_Overview_TEST.xlsx")
        sapx = os.path.join(sapdir, "export", "SAP_EXPORT.xlsx")
        dialogs.clear()
        picks[:] = [target, sapx]
        answers[:] = [False]  # preview only
        log = run("Aktualizovat podle SAP (výběr souborů)", timeout=60)
        check("template dialog tool runs real script with picked files in order",
              "Cil: PNs_Overview_TEST.xlsx" in log and "SAP: SAP_EXPORT.xlsx" in log
              and [d[1]["title"].rsplit(": ", 1)[1] for d in dialogs] == ["Cílový přehled PN", "Export ze SAP"], log)
    finally:
        filedialog.askopenfilename, filedialog.asksaveasfilename = real


for fn in (v060_rename, v060_swap, v060_drag, v060_favorites_bar, v060_settings, v060_file_prompts):
    section(fn)
