# Tests for 0.12.0 (Soubor → Tmavý režim, "tmavy_rezim" in dvojpanel.json); exec'd inside harness.py.


def v120_dark_mode():
    """0.12.0 Soubor → Tmavý režim recolors the program and is stored in dvojpanel.json"""
    D = dp.DARK_COLORS

    def file_menu():
        mb = app.nametowidget(app["menu"])
        first = next(i for i in range(mb.index("end") + 1) if mb.type(i) == "cascade")
        return app.nametowidget(mb.entrycget(first, "menu"))

    def toggle():
        fm = file_menu()
        fm.invoke(fm.index("Tmavý režim"))
        pump(timeout=0.3)

    def stored():
        return json.loads(dp.SETTINGS_FILE.read_text(encoding="utf-8")) if dp.SETTINGS_FILE.exists() else {}

    def theme():
        return dp.ttk.Style(app).theme_use()

    if dp.SETTINGS_FILE.exists():
        os.remove(dp.SETTINGS_FILE)
    app.left.load(L); app.right.load(R)
    app.set_active(app.left)
    light_log = str(app.log_text["background"])
    fm = file_menu()
    check("light by default: setting false, system ttk theme, light colors",
          dp.SETTINGS_DEFAULTS["tmavy_rezim"] is False and app.settings["tmavy_rezim"] is False
          and not dp.colors["dark"] and theme() == app.base_theme and theme() != "clam", (theme(), dp.colors))
    check("Soubor → Tmavý režim is a check item, unchecked", fm.type(fm.index("Tmavý režim")) == "checkbutton"
          and app.dark_var.get() is False)

    reset()
    sync = app.open_sync() or app.sync_window
    pump(timeout=0.3)
    toggle()
    check("on: stored in dvojpanel.json, status line, no dialog", stored() == {"tmavy_rezim": True}
          and app.settings["tmavy_rezim"] is True and app.dark_var.get() is True
          and app.status_var.get() == "Tmavý režim zapnut" and not calls, (stored(), app.status_var.get(), calls))
    check("on: ttk theme clam with dark colors", theme() == "clam"
          and dp.ttk.Style(app).lookup("Treeview", "background") == D["field"]
          and dp.ttk.Style(app).lookup(".", "foreground") == D["fg"], theme())
    check("on: window, tool output and pane marker recolored", str(app["background"]) == D["bg"]
          and str(app.log_text["background"]) == D["field"] and str(app.log_text["foreground"]) == D["fg"]
          and str(app.left.marker["background"]) == D["bg"] and str(app.left.marker["foreground"]) == D["marker_on"]
          and str(app.right.marker["foreground"]) == D["marker_off"],
          (str(app["background"]), str(app.log_text["background"]), str(app.left.marker["foreground"])))
    check("on: folders, marks and drop target in dark colors",
          str(app.left.tree.tag_configure("dir", "foreground")) == D["dir"]
          and str(app.left.tree.tag_configure("marked", "foreground")) == D["mark"]
          and str(app.right.tree.tag_configure("drop", "background")) == D["drop"])
    check("on: rebuilt menus are dark", str(file_menu()["background"]) == D["bg"] and str(file_menu()["foreground"]) == D["fg"]
          and str(app.tools_menu["background"]) == D["bg"], str(file_menu()["background"]))
    check("on: the open compare window is recolored", sync is not None and sync.winfo_exists()
          and str(sync["background"]) == D["bg"]
          and str(sync.tree.tag_configure(dp.RIGHT_ONLY, "foreground")) == D["sync_right"])
    sync.close()
    pump(timeout=0.2)
    app.show_help()
    pump(timeout=0.3)
    hw = app.help_window
    check("on: help window (F1) is dark", str(hw["background"]) == D["bg"] and str(hw.text["background"]) == D["field"]
          and str(hw.listbox["background"]) == D["field"] and str(hw.text.tag_cget("h2", "foreground")) == D["dir"]
          and str(hw.text.tag_cget("code", "background")) == D["code"], (str(hw.text["background"]),))
    hw.destroy()
    pump(timeout=0.2)
    check("on: a new window and a popup menu take the dark colors",
          str(dp.tk.Toplevel(app)["background"]) == D["bg"] and str(dp.tk.Menu(app)["background"]) == D["bg"])
    for w in app.winfo_children():
        if w.winfo_class() == "Toplevel" and w is not app.help_window and w is not app.sync_window:
            w.destroy()

    reset()
    toggle()
    check("off: stored, system theme and light colors back", stored() == {"tmavy_rezim": False}
          and theme() == app.base_theme and not dp.colors["dark"] and str(app.log_text["background"]) == light_log
          and str(app.left.tree.tag_configure("dir", "foreground")) == dp.LIGHT_COLORS["dir"]
          and app.status_var.get() == "Tmavý režim vypnut" and not calls,
          (stored(), theme(), str(app.log_text["background"]), calls))
    check("off: menus and new windows light again", str(file_menu()["background"]) != D["bg"]
          and str(dp.tk.Text(app)["background"]) == light_log)

    dp.SETTINGS_FILE.write_text(json.dumps({"tmavy_rezim": "ano"}), encoding="utf-8")
    err = dp.load_settings()[1]
    check("tmavy_rezim must be true or false", err and "'tmavy_rezim'" in err, err)

    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R, "tmavy_rezim": True}), encoding="utf-8")
    reset()
    app.reload_settings()
    pump(timeout=0.3)
    check("Načíst nastavení znovu applies tmavy_rezim", theme() == "clam" and dp.colors["dark"]
          and app.dark_var.get() is True and str(app.log_text["background"]) == D["field"] and not calls, calls)
    dp.SETTINGS_FILE.write_text(json.dumps({"levy_panel": L, "pravy_panel": R}), encoding="utf-8")
    app.reload_settings()
    pump(timeout=0.3)
    check("Načíst nastavení znovu without the key = light", theme() == app.base_theme and not dp.colors["dark"]
          and app.dark_var.get() is False)

    dp.SETTINGS_FILE.write_text("{ rozbité", encoding="utf-8")
    reset()
    toggle()
    check("a broken dvojpanel.json: error, nothing overwritten, stays light", kinds() == ["showerror"]
          and dp.SETTINGS_FILE.read_text(encoding="utf-8") == "{ rozbité" and not dp.colors["dark"]
          and app.dark_var.get() is False and theme() == app.base_theme, (calls, theme()))
    os.remove(dp.SETTINGS_FILE)
    app.settings = dp.load_settings()[0]


def v121_active_pane():
    """0.12.1 the active pane has a colored strip, the inactive one dims its selection (light and dark)"""
    if dp.SETTINGS_FILE.exists():
        os.remove(dp.SETTINGS_FILE)
    app.left.load(L); app.right.load(R)

    def state(pane):
        return str(pane.accent["background"]), str(pane.tree["style"])

    for dark in (False, True):
        app.settings["tmavy_rezim"] = dark
        app.apply_theme()
        pump(timeout=0.2)
        c = dp.colors
        name = "dark" if dark else "light"
        app.set_active(app.left)
        check(f"{name}: left active = accent strip and normal selection, right dimmed",
              state(app.left) == (c["accent"], "Treeview") and state(app.right) == (c["accent_off"], "Inactive.Treeview"),
              (state(app.left), state(app.right)))
        key(app.left.tree, "<Tab>")
        check(f"{name}: Tab moves the strip and the dimming", app.active is app.right
              and state(app.right) == (c["accent"], "Treeview") and state(app.left) == (c["accent_off"], "Inactive.Treeview"),
              (state(app.left), state(app.right)))
        sel = {tuple(str(x) for x in spec[:-1]): str(spec[-1])  # [(state…, value)]
               for spec in dp.ttk.Style(app).map("Inactive.Treeview", "background")}
        check(f"{name}: the inactive pane shows selected rows in the dim color",
              ("selected",) in sel and sel[("selected",)] == c["dim_select"], sel)
    app.settings["tmavy_rezim"] = False
    app.apply_theme()
    app.set_active(app.left)
    pump(timeout=0.2)


for fn in (v120_dark_mode, v121_active_pane):
    section(fn)
