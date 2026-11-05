# Tests for 0.3.0 features; exec'd inside test_release.py (shares its globals).


def marks():
    """0.3.0 Marking with Space / Insert"""
    lt = app.left.tree
    for n in os.listdir(R):
        dp.remove_path(os.path.join(R, n))
    app.left.load(L); app.right.load(R)
    select(app.left, "a.txt")
    a, b, d = (os.path.join(L, n) for n in ("a.txt", "b.txt", "data.xlsx"))
    if not os.path.exists(b):
        write(b, "y" * 2000); app.left.reload(); select(app.left, "a.txt")
    key(lt, "<space>")
    check("Space marks item and moves cursor down", app.left.marked == {a} and lt.focus() == b, (app.left.marked, lt.focus()))
    check("marked item has red 'marked' tag", "marked" in lt.item(a, "tags"))
    key(lt, "<Down>")
    check("arrow keeps marks", app.left.marked == {a} and lt.focus() == d, (app.left.marked, lt.focus()))
    key(lt, "<Insert>")
    check("Insert marks too", app.left.marked == {a, d}, app.left.marked)
    check("status 'Označeno 2'", app.left.status_var.get().startswith("Označeno 2 z"), app.left.status_var.get())
    check("selected_paths = marked (not the cursor selection)", app.left.selected_paths() == [a, d],
          app.left.selected_paths())
    lt.focus(a); lt.selection_set(a)
    key(lt, "<space>")
    check("Space again unmarks", app.left.marked == {d} and "marked" not in lt.item(a, "tags"))
    sub = os.path.join(L, "sub")
    lt.focus(sub); lt.selection_set(sub)
    key(lt, "<space>")
    check("folders can be marked; dir+marked tags", "marked" in lt.item(sub, "tags") and "dir" in lt.item(sub, "tags"))
    lt.focus(d); lt.selection_set(d)  # cursor on a marked file, marks = {d, sub}
    reset(True)
    key(lt, "<F5>")
    wait_job()
    check("F5 copies marked items (file + folder)", sorted(os.listdir(R)) == ["data.xlsx", "sub"], os.listdir(R))
    check("marks cleared after successful copy", not app.left.marked and "marked" not in lt.item(d, "tags"))
    app.left.load(sub)
    lt.focus(dp.UP); lt.selection_set(dp.UP)
    key(lt, "<space>")
    check("Space on [..] does not mark it", not app.left.marked)
    key(lt, "<space>")
    app.left.load(L)
    check("marks cleared when changing folder", not app.left.marked)
    for n in os.listdir(R):
        dp.remove_path(os.path.join(R, n))
    app.reload_both()


section(marks)


def progress():
    """0.3.0 Progress in percent, Esc cancel, safe overwrite"""
    lt = app.left.tree
    big = os.path.join(L, "big.bin")
    write(big, os.urandom(1024 * 1024) * 300, "wb")  # 300 MB
    app.left.reload(); app.right.load(R)
    hist, pcts = [], []
    orig = app.show_progress

    def spy(text, percent=None):
        if percent is not None:
            pcts.append(percent)
        orig(text, percent)
        hist.append(app.status_var.get())
    app.show_progress = spy
    select(app.left, "big.bin")
    reset(True)
    key(lt, "<F5>")
    bar_seen = pump(lambda: app.progress.winfo_ismapped(), 10)
    wait_job()
    app.show_progress = orig
    pct_texts = [h for h in hist if " %" in h]
    check("status shows percent for big file", pct_texts and "big.bin" in pct_texts[-1], hist[-3:])
    print("     e.g.:", pct_texts[len(pct_texts) // 2] if pct_texts else None)
    check("percent goes up to 100, at most ~101 updates", pcts and pcts[-1] == 100 and len(pcts) <= 101,
          (len(pcts), pcts[-1:] if pcts else None))
    check("progress bar visible during copy, hidden after", bar_seen and not app.progress.winfo_ismapped())
    check("status mentions Esc", any("Esc = přerušit" in h for h in hist))
    check("copy identical, mtime kept", dp.files_equal(big, os.path.join(R, "big.bin"))
          and abs(os.path.getmtime(big) - os.path.getmtime(os.path.join(R, "big.bin"))) < 0.01)
    check("no temp file left", not [n for n in os.listdir(R) if n.endswith(".dvojpanel-tmp")], os.listdir(R))

    write(os.path.join(R, "big.bin"), "OLD CONTENT")
    reset(True, True)  # confirm, overwrite
    key(lt, "<F5>")
    pump(lambda: " %" in app.status_var.get(), 10)
    key(lt, "<Escape>")
    wait_job()
    check("Esc cancels copy, user is told", any("Přerušeno" in str(c[1]) for c in calls), calls[-1:])
    check("cancelled overwrite keeps the old target intact",
          open(os.path.join(R, "big.bin"), encoding="utf-8").read() == "OLD CONTENT")
    check("cancelled copy leaves no temp file", not [n for n in os.listdir(R) if n.endswith(".dvojpanel-tmp")])
    check("source untouched", os.path.getsize(big) == 300 * 1024 * 1024)

    os.remove(os.path.join(R, "big.bin"))
    reset(True)
    app.left.reload()
    select(app.left, "big.bin")
    key(lt, "<F6>")
    wait_job()
    check("F6 within one drive = rename (fast), file moved", os.path.isfile(os.path.join(R, "big.bin"))
          and not os.path.exists(big))
    os.remove(os.path.join(R, "big.bin"))
    app.reload_both()
    reset()
    app.busy = False
    key(lt, "<Escape>")
    check("Esc while idle does nothing", not calls and app.status_var.get() != "Přerušuji…")


section(progress)


def sync():
    """0.3.0 Compare and synchronize folders (binary)"""
    SL, SR = os.path.join(ENV, "SL"), os.path.join(ENV, "SR")
    for d in (SL, SR):
        os.makedirs(os.path.join(d, "common", "deep"))
    t_old, t_new = 1_700_000_000, 1_700_100_000

    def mk(root, rel, data, t):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, data, "wb")
        os.utime(path, (t, t))
    blob = os.urandom(40 * 1024 * 1024)
    for root in (SL, SR):
        mk(root, "same.txt", b"same", t_old)
        mk(root, "big_same.bin", blob, t_old)
        mk(root, "common/deep/same2.txt", b"x", t_old)
    mk(SL, "Case.txt", b"c", t_old); mk(SR, "case.txt", b"c", t_old)
    mk(SL, "diff_same_size.bin", b"AAAA", t_old); mk(SR, "diff_same_size.bin", b"AAAB", t_old)
    mk(SL, "newer_left.txt", b"new version", t_new); mk(SR, "newer_left.txt", b"old", t_old)
    mk(SL, "newer_right.txt", b"old", t_old); mk(SR, "newer_right.txt", b"newer", t_new)
    mk(SL, "only_left.txt", b"L", t_old)
    mk(SR, "only_right.txt", b"R", t_old)
    mk(SL, "onlyleftdir/a/b.txt", b"b", t_old); mk(SL, "onlyleftdir/c.txt", b"c", t_old)
    mk(SL, "common/deep/only_left_deep.txt", b"d", t_old)
    mk(SL, "conflict", b"file", t_old); os.makedirs(os.path.join(SR, "conflict"))
    mk(SL, "touched_same.txt", b"same content", t_new); mk(SR, "touched_same.txt", b"same content", t_old)

    cancel = threading.Event()
    rows, errors = dp.compare_worker(SL, SR, True, True, cancel, lambda *a: None)
    by = {r["rel"]: r for r in rows}
    st = {k: (v["status"], v["action"]) for k, v in by.items()}
    check("no compare errors", not errors, errors)
    check("identical files SAME (binary, 40 MB too)", st.get("same.txt") == ("same", "")
          and st.get("big_same.bin") == ("same", "") and st.get(os.path.join("common", "deep", "same2.txt")) == ("same", ""), st)
    check("names differing only in case match (Windows)", "Case.txt" in st and st["Case.txt"][0] == "same", st)
    check("same size + same time but different bytes -> DIFFERENT, no default action",
          st.get("diff_same_size.bin") == ("different", ""), st.get("diff_same_size.bin"))
    check("newer left -> copy right", st.get("newer_left.txt") == ("different", ">"))
    check("newer right -> copy left", st.get("newer_right.txt") == ("different", "<"))
    check("only left -> right / only right -> left",
          st.get("only_left.txt") == ("left", ">") and st.get("only_right.txt") == ("right", "<"))
    check("one-sided folder is one row, contents not listed",
          st.get("onlyleftdir") == ("left", ">") and not any(k.startswith("onlyleftdir" + os.sep) for k in st), st)
    check("file only in a common subfolder found",
          st.get(os.path.join("common", "deep", "only_left_deep.txt")) == ("left", ">"))
    check("file vs folder -> conflict, no action", st.get("conflict") == ("conflict", ""))
    check("same bytes, different time -> SAME in binary mode", st.get("touched_same.txt") == ("same", ""))
    rows_q, _ = dp.compare_worker(SL, SR, True, False, cancel, lambda *a: None)
    stq = {r["rel"]: r["status"] for r in rows_q}
    check("quick mode: same size+time counts as same, different time as different",
          stq.get("diff_same_size.bin") == "same" and stq.get("touched_same.txt") == "different", stq)
    rows_nr, _ = dp.compare_worker(SL, SR, False, True, cancel, lambda *a: None)
    check("non-recursive: nothing from subfolders", not any(os.sep in r["rel"] for r in rows_nr),
          [r["rel"] for r in rows_nr])

    # GUI
    app.left.load(SL); app.right.load(SR)
    key(app.left.tree, "<Control-s>")
    win = app.sync_window
    check("Ctrl+S opens sync window with both pane paths",
          win is not None and win.left_var.get() == SL and win.right_var.get() == SR)
    reset()
    win.compare()
    pump(lambda: not win.running and win.compared, 30)
    shown = {win.tree.set(i, "rel"): i for i in win.tree.get_children()}
    check("result shown, identical hidden by default", "newer_left.txt" in shown and "same.txt" not in shown, list(shown))
    win.show_same.set(True); win.refresh()
    check("'Zobrazit stejné' shows them", "same.txt" in {win.tree.set(i, "rel") for i in win.tree.get_children()})
    win.show_same.set(False); win.refresh()
    shown = {win.tree.set(i, "rel"): i for i in win.tree.get_children()}
    check("folder row has trailing \\", "onlyleftdir\\" in shown, list(shown))
    print("     summary:", win.summary_var.get())

    iid = shown["diff_same_size.bin"]
    win.tree.selection_set(iid); win.tree.focus(iid)
    key(win.tree, "<Left>")
    check("← key sets action copy left", win.rows[int(iid)]["action"] == "<" and win.tree.set(iid, "action") == "←")
    iid2 = shown["only_right.txt"]
    win.tree.selection_set(iid2)
    key(win.tree, "<Right>")
    check("cannot copy right a file that exists only right", win.rows[int(iid2)]["action"] == "<")
    iid3 = shown["conflict"]
    win.tree.selection_set(iid3)
    key(win.tree, "<Right>")
    check("conflict row cannot get an action", win.rows[int(iid3)]["action"] == "")
    iid4 = shown["newer_right.txt"]
    win.tree.selection_set(iid4)
    key(win.tree, "<space>")
    check("Space = no action", win.rows[int(iid4)]["action"] == "")

    reset(False)
    win.sync()
    msg = calls[0][1][1] if calls else ""
    check("sync asks first and lists overwritten files",
          kinds() == ["askokcancel"] and "PŘEPÍŠE se 2" in msg and "newer_left.txt" in msg
          and "diff_same_size.bin" in msg, msg)
    check("cancel = nothing copied", not os.path.exists(os.path.join(SR, "only_left.txt")))
    reset(True)
    win.sync()
    pump(lambda: not win.running and win.compared and not app.busy, 30)
    pump(timeout=0.5)
    pump(lambda: not win.running, 30)
    rd = lambda root, rel: open(os.path.join(root, rel), "rb").read()
    check("only_left copied right", rd(SR, "only_left.txt") == b"L")
    check("only_right copied left", rd(SL, "only_right.txt") == b"R")
    check("newer left overwrote right, mtime kept",
          rd(SR, "newer_left.txt") == b"new version" and int(os.path.getmtime(os.path.join(SR, "newer_left.txt"))) == t_new)
    check("diff_same_size copied left per user choice", rd(SL, "diff_same_size.bin") == b"AAAB")
    check("'no action' row untouched", rd(SL, "newer_right.txt") == b"old")
    check("whole one-sided folder copied", rd(SR, os.path.join("onlyleftdir", "a", "b.txt")) == b"b")
    check("deep file copied into existing subfolder", rd(SR, os.path.join("common", "deep", "only_left_deep.txt")) == b"d")
    check("conflict untouched", os.path.isfile(os.path.join(SL, "conflict")) and os.path.isdir(os.path.join(SR, "conflict")))
    remaining = sorted((r["rel"], r["status"]) for r in win.rows if r["status"] != "same")
    check("auto re-compare after sync: only conflict + skipped row remain",
          remaining == [("conflict", "conflict"), ("newer_right.txt", "different")], remaining)
    check("nothing silently deleted (left file count did not drop)",
          os.path.exists(os.path.join(SL, "only_left.txt")) and os.path.exists(os.path.join(SR, "only_right.txt")))

    reset()
    win.left_var.set(SL); win.right_var.set(os.path.join(SL, "common"))
    win.compare()
    check("nested folders refused", kinds() == ["showwarning"], calls)
    reset()
    win.right_var.set(os.path.join(ENV, "neni"))
    win.compare()
    check("missing folder -> error", kinds() == ["showerror"], calls)
    win.set_paths(SL, SR)
    reset()
    win.compare()
    pump(lambda: "big_same.bin" in win.progress_var.get() or not win.running, 20)
    win.cancel.set()
    pump(lambda: not win.running, 20)
    check("compare can be cancelled", any("Přerušeno" in str(c[1]) for c in calls) or win.compared, (calls, win.progress_var.get()))
    check("app not left busy after cancel", not app.busy)
    win.compare()
    pump(timeout=0.2)
    win.close()
    pump(lambda: not app.busy, 20)
    check("closing during compare releases busy flag", not app.busy)
    key(app.left.tree, "<Control-s>")
    check("Ctrl+S reopens a new window after close", app.sync_window is not win and app.sync_window.winfo_exists())
    app.sync_window.close()
    app.left.load(L); app.right.load(R)


section(sync)


def favorites():
    """0.3.0 Favorite folders"""
    fm = app.favorites_menu
    labels = lambda: [fm.entrycget(i, "label") for i in range(fm.index("end") + 1) if fm.type(i) != "separator"]
    check("no oblibene.json at start", not dp.FAVORITES_FILE.exists())
    check("menu says no favorites", labels()[0] == "Žádné oblíbené složky", labels())
    proj = os.path.join(HOME, "Projekty", "P-1234 Zakázka")
    os.makedirs(proj)
    app.left.load(proj)
    app.set_active(app.left)
    reset("Zakázka 1234")
    fm.invoke(fm.index("Přidat aktuální složku…"))
    check("add asks for name with folder name as default",
          calls and calls[0][2].get("initialvalue") == "P-1234 Zakázka", calls)
    data = json.loads(dp.FAVORITES_FILE.read_text(encoding="utf-8"))
    check("oblibene.json written", data == {"oblibene": [{"nazev": "Zakázka 1234", "cesta": proj}]}, data)
    check("menu lists favorite", labels()[0] == "Zakázka 1234", labels())
    reset()
    fm.invoke(fm.index("Přidat aktuální složku…"))
    check("duplicate refused with info", kinds() == ["showinfo"], calls)

    app.left.load(L)
    fm.invoke(0)
    pump(lambda: app.left.path == proj, 5)
    check("favorite opens in active pane", app.left.path == proj, app.left.path)

    data["oblibene"] += [{"nazev": "Přes proměnnou", "cesta": "%DP_TEST%\\home\\L"},
                         {"cesta": "Z:/neexistuje/projekt"},
                         {"nazev": "Síť nedostupná", "cesta": "\\\\neexistujici-server-dp\\projekty"}]
    dp.FAVORITES_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    reset()
    fm.invoke(fm.index("Načíst oblíbené znovu"))
    check("reload picks up edits, name falls back to path",
          labels()[:4] == ["Zakázka 1234", "Přes proměnnou", "Z:/neexistuje/projekt", "Síť nedostupná"], labels())
    app.set_active(app.right)
    fm.invoke(1)
    pump(lambda: app.right.path == L, 5)
    check("%VAR% path opens in the active (right) pane", app.right.path == L and app.left.path == proj)
    reset()
    fm.invoke(2)
    pump(lambda: calls, 10)
    check("missing folder -> error, pane unchanged", kinds() == ["showerror"] and app.right.path == L, calls)
    reset()
    t0 = time.time()
    fm.invoke(3)
    ticks = 0
    while not calls and time.time() - t0 < 60:
        app.update(); ticks += 1; time.sleep(0.02)
    check("unreachable UNC share -> error, GUI stayed responsive meanwhile",
          kinds() == ["showerror"] and ticks > 5, (calls, round(time.time() - t0, 1), ticks))
    print(f"     UNC check took {time.time() - t0:.1f} s")

    reset(True)
    rm = app.nametowidget(fm.entrycget(fm.index("Odebrat"), "menu"))
    rm.invoke(2)
    data = json.loads(dp.FAVORITES_FILE.read_text(encoding="utf-8"))
    check("remove asks and deletes only that entry",
          kinds() == ["askyesno"] and [f["cesta"] for f in data["oblibene"]] ==
          [proj, "%DP_TEST%\\home\\L", "\\\\neexistujici-server-dp\\projekty"], data)

    dp.FAVORITES_FILE.write_text("{ rozbité", encoding="utf-8")
    reset()
    app.reload_favorites()
    check("broken JSON -> error, menu shows it", kinds() == ["showerror"] and "oblibene.json" in labels()[0], labels())
    reset()
    fm.invoke(fm.index("Přidat aktuální složku…"))
    check("adding with broken file refused, file not overwritten",
          kinds() == ["showerror"] and dp.FAVORITES_FILE.read_text(encoding="utf-8") == "{ rozbité", calls)
    os.remove(dp.FAVORITES_FILE)
    reset()
    fm.invoke(fm.index("Upravit oblibene.json"))
    check("Upravit creates empty file and opens Notepad",
          launched == [["notepad.exe", str(dp.FAVORITES_FILE)]]
          and json.loads(dp.FAVORITES_FILE.read_text(encoding="utf-8")) == {"oblibene": []}, launched)
    app.reload_favorites()
    check("Ctrl+D is bound", app.bind("<Control-d>") != "")
    app.left.load(L); app.right.load(R)


section(favorites)
