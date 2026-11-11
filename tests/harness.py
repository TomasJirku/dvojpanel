"""End-to-end GUI test of Dvojpanel (README-driven), run by spustit_testy.py on a copy of the program.

Usage: python harness.py <program_dir> <env_dir>
Needs Windows with a display. Read-only use of the Windchill project (DP_WINDCHILL, default
C:\\Projects\\MojeAplikace\\Windchill): its .bat, scripts and dvojpanel_nastroje.json are copied.
A git checkout in its subfolder windchill-index is used when the tool file is only there; the .venv
(WC_VENV) may be in the project folder or one level up.
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import time
import threading
import traceback

REL, ENV = map(os.path.abspath, sys.argv[1:3])


class Ver(str):
    """Version string that compares numerically ("0.10" > "0.6")."""

    def _key(self, other):
        return tuple(int(x) for x in str(other).split("."))

    def __lt__(self, other):
        return self._key(self) < self._key(other)

    def __le__(self, other):
        return self._key(self) <= self._key(other)

    def __gt__(self, other):
        return self._key(self) > self._key(other)

    def __ge__(self, other):
        return self._key(self) >= self._key(other)


def program_version():
    import re as _re
    src = open(os.path.join(REL, "dvojpanel.py"), encoding="utf-8").read()
    return _re.search(r'^__version__ = "([^"]+)"', src, _re.M).group(1)


VER = Ver(os.environ.get("VER") or program_version())
WC_SRC = os.environ.get("DP_WINDCHILL", r"C:\Projects\MojeAplikace\Windchill")
if not os.path.isdir(WC_SRC):
    sys.exit(f"Windchill project not found: {WC_SRC} (set DP_WINDCHILL)")
if not os.path.exists(os.path.join(WC_SRC, "dvojpanel_nastroje.json")) \
        and os.path.exists(os.path.join(WC_SRC, "windchill-index", "dvojpanel_nastroje.json")):
    WC_SRC = os.path.join(WC_SRC, "windchill-index")  # the git checkout inside the working folder
WC_VENV = next((v for v in (os.path.join(WC_SRC, ".venv"), os.path.join(os.path.dirname(WC_SRC), ".venv"))
                if os.path.exists(os.path.join(v, "Scripts", "python.exe"))), os.path.join(WC_SRC, ".venv"))
if os.path.exists(ENV):
    shutil.rmtree(ENV)
HOME = os.path.join(ENV, "home")
L, R = os.path.join(HOME, "L"), os.path.join(HOME, "R")
SCRIPTS = os.path.join(ENV, "scripts")
OUT = os.path.join(ENV, "out")
for d in (L, R, SCRIPTS, OUT, os.path.join(L, "sub"), os.path.join(SCRIPTS, "dir with space")):
    os.makedirs(d, exist_ok=True)


def write(path, data, mode="w"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        f.write(data)


write(os.path.join(L, "a.txt"), "x" * 10)
write(os.path.join(L, "b.txt"), "y" * 2000)
write(os.path.join(L, "data.xlsx"), "z" * 500)
write(os.path.join(L, "file with space.txt"), "12345")
write(os.path.join(L, "sub", "inner.txt"), "inner")
for i, n in enumerate(["a.txt", "b.txt", "data.xlsx", "file with space.txt"]):
    t = 1_700_000_000 + [3, 1, 4, 2][i] * 86400
    os.utime(os.path.join(L, n), (t, t))

os.environ["USERPROFILE"] = HOME
os.environ["HOME"] = HOME
os.environ["DP_TEST"] = ENV

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"), flush=True)


def section(fn):
    print(f"\n== {fn.__doc__}", flush=True)
    try:
        fn()
    except Exception:
        check(f"{fn.__doc__}: no exception", False, traceback.format_exc())


# ---------------------------------------------------------------- static checks
def static():
    """Static: stdlib only, Python 3.10 syntax, version"""
    src = open(os.path.join(REL, "dvojpanel.py"), encoding="utf-8").read()
    tree = ast.parse(src, feature_version=(3, 10))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module.split(".")[0])
    nonstd = mods - set(sys.stdlib_module_names)
    check("only stdlib imports", not nonstd, nonstd)
    check("parses with Python 3.10 grammar", True)
    check("__version__ == 0.2.0", f'__version__ = "{VER}"' in src)
    check("nastroje.json not shipped in release", not os.path.exists(os.path.join(REL, "nastroje.json")))
    check("nastroje.example.json shipped", os.path.exists(os.path.join(REL, "nastroje.example.json")))


section(static)

# ---------------------------------------------------------------- import with stubs
sys.path.insert(0, REL)
import dvojpanel as dp  # noqa: E402
from tkinter import messagebox, simpledialog  # noqa: E402

calls, answers = [], []


def stub(kind, default):
    def f(*a, **k):
        calls.append((kind, a, k))
        return answers.pop(0) if answers else default
    return f


for kind, default in [("showerror", "ok"), ("showinfo", "ok"), ("showwarning", "ok"),
                      ("askokcancel", True), ("askyesno", True), ("askyesnocancel", None)]:
    setattr(messagebox, kind, stub(kind, default))
simpledialog.askstring = stub("askstring", None)
for _name in ("ask_conflict", "ask_tool_input"):  # own dialogs since 0.8
    if hasattr(dp, _name):
        setattr(dp, _name, stub(_name, None))


def conflict(answer):
    """Answer to the 'already exists' question: True = overwrite, False = skip, None = cancel."""
    if VER < "0.8":
        return answer
    return {True: "all", False: "skip", None: None}[answer]


CONFLICT = "askyesnocancel" if VER < "0.8" else "ask_conflict"

launched = []
real_popen = subprocess.Popen


def fake_popen(cmd, *a, **k):
    if isinstance(cmd, list) and cmd and cmd[0] in ("notepad.exe", "xdg-open"):
        launched.append(cmd)
        return None
    return real_popen(cmd, *a, **k)


subprocess.Popen = fake_popen
started = []
started_cwd = []
os.startfile = lambda p, *a, **k: (started.append(p), started_cwd.append(k.get("cwd")))


def reset(*ans):
    calls.clear()
    answers[:] = list(ans)
    launched.clear()
    started.clear()


def kinds():
    return [c[0] for c in calls]


# the template points at the real Windchill project; tests must never touch it
import pathlib
_ex = pathlib.Path(dp.CONFIG_EXAMPLE).read_text(encoding="utf-8").replace(
    "C:/Projects/MojeAplikace/Windchill", "%USERPROFILE%/Skripty/windchill")
dp.CONFIG_EXAMPLE = pathlib.Path(ENV) / "nastroje.example.test.json"
dp.CONFIG_EXAMPLE.write_text(_ex, encoding="utf-8")
# the included Windchill tool file, copied to where the redirected template looks for it
WC_TEST = os.path.join(HOME, "Skripty", "windchill")
os.makedirs(WC_TEST, exist_ok=True)
shutil.copy(os.path.join(WC_SRC, "dvojpanel_nastroje.json"), WC_TEST)
cfg_existed = dp.CONFIG_FILE.exists()
app = dp.App()
app.update()


def pump(cond=lambda: False, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        app.update()
        if cond():
            return True
        time.sleep(0.02)
    app.update()
    return cond()


def key(widget, seq, **kw):
    widget.focus_force()
    app.update()
    widget.event_generate(seq, **kw)
    app.update()


def names(pane):
    return [os.path.basename(i) for i in pane.tree.get_children() if i != dp.UP]


def select(pane, *items):
    paths = [os.path.join(pane.path, n) for n in items]
    if hasattr(pane, "clear_marks"):
        pane.clear_marks()
    pane.tree.focus_force()
    app.update()
    app.set_active(pane)
    pane.tree.selection_set(paths)
    pane.tree.focus(paths[0])
    app.update()


def wait_job():
    return pump(lambda: not app.busy, 20)


def startup():
    """Startup, title, menu, first-run nastroje.json"""
    check("nastroje.json absent before first start", not cfg_existed)
    check("window title has version", app.title() == f"Dvojpanel {VER}", app.title())
    check("both panes start in home", app.left.path == HOME and app.right.path == HOME,
          (app.left.path, app.right.path))
    check("nastroje.json created from example on first start",
          dp.CONFIG_FILE.exists() and dp.CONFIG_FILE.read_bytes() == dp.CONFIG_EXAMPLE.read_bytes())
    n_ex = len(json.loads(dp.CONFIG_EXAMPLE.read_text(encoding="utf-8"))["nastroje"]) + len(json.loads(
        open(os.path.join(WC_TEST, "dvojpanel_nastroje.json"), encoding="utf-8").read())["nastroje"])
    check(f"{n_ex} example tools loaded", len(app.tools) == n_ex and app.tools_error is None, app.tools_error)
    menubar = app.nametowidget(app["menu"])
    labels = [menubar.entrycget(i, "label") for i in range(menubar.index("end") + 1) if menubar.type(i) == "cascade"]
    exp_menus = ["Soubor", "Příkazy", "Oblíbené", "Nástroje", "Nápověda"] if VER >= "0.3" else ["Soubor", "Nástroje", "Nápověda"]
    check("menus " + "/".join(exp_menus), labels == exp_menus, labels)
    tm = app.tools_menu
    tlabels = [tm.entrycget(i, "label") for i in range(tm.index("end") + 1) if tm.type(i) == "command"]
    exp = [t["nazev"] for t in app.tools if not t.get("skupina")] + ["Upravit nastroje.json", "Načíst nástroje znovu",
                                             "Zastavit běžící nástroj", "Vymazat výstup"]
    if VER >= "0.8":
        exp[-2:-2] = ["Přidat nástroje projektu…"]
        exp.append("Nápověda k nástrojům")
    check("Nástroje menu entries", tlabels == exp, tlabels)
    reset()
    help_menu = app.nametowidget(menubar.entrycget(menubar.index("Nápověda"), "menu"))
    help_menu.invoke(help_menu.index("O programu"))
    check("O programu shows version", calls and f"Dvojpanel {VER}" in calls[0][1][1], calls)
    reset()
    tm.invoke(tm.index("Upravit nastroje.json"))
    check("Upravit nastroje.json opens Notepad", launched == [["notepad.exe", str(dp.CONFIG_FILE)]], launched)
    check("drive list contains C:\\", "C:\\" in app.left.drive_box["values"], app.left.drive_box["values"])


section(startup)
app.left.load(L)
app.right.load(R)
app.set_active(app.left)


def navigation():
    """Navigation: Tab, Enter, Backspace, double-click, address bar, drives"""
    lt, rt = app.left.tree, app.right.tree
    key(lt, "<Tab>")
    check("Tab switches to right pane", app.active is app.right)
    check("active marker green / inactive gray",
          app.right.marker["fg"] == "#2e9e3e" and app.left.marker["fg"] == "#999999")
    key(rt, "<Tab>")
    check("Tab switches back", app.active is app.left)

    sub = os.path.join(L, "sub")
    lt.focus(sub); lt.selection_set(sub)
    key(lt, "<Return>")
    check("Enter opens folder", app.left.path == sub, app.left.path)
    check("[..] row present and focused", lt.focus() == dp.UP)
    key(lt, "<Return>")
    check("Enter on [..] goes up, cursor on previous folder", app.left.path == L and lt.focus() == sub,
          (app.left.path, lt.focus()))
    app.left.load(sub)
    key(lt, "<BackSpace>")
    check("Backspace goes up, cursor on previous folder", app.left.path == L and lt.focus() == sub)

    app.left.load(L)
    lt.see(sub)
    app.update()
    x, y, w, h = lt.bbox(sub)
    for _ in range(2):
        lt.event_generate("<ButtonPress-1>", x=x + 10, y=y + 5)
        lt.event_generate("<ButtonRelease-1>", x=x + 10, y=y + 5)
    app.update()
    check("double-click opens folder", app.left.path == sub, app.left.path)
    app.left.load(L)

    reset()
    f = os.path.join(L, "a.txt")
    lt.focus(f); lt.selection_set(f)
    key(lt, "<Return>")
    check("Enter on file opens with default app", started == [f], started)
    if VER >= "0.5.2":
        check("opened with the file's folder as working directory", started_cwd[-1:] == [L], started_cwd)

    entry = [w for w in app.left.winfo_children()[0].winfo_children() if w.winfo_class() == "TEntry"][0]
    app.left.path_var.set(sub)
    key(entry, "<Return>")
    check("address bar Enter navigates", app.left.path == sub)
    reset()
    app.left.path_var.set(os.path.join(L, "neexistuje"))
    key(entry, "<Return>")
    check("bad path in address bar -> error + path restored",
          kinds() == ["showerror"] and app.left.path == sub and app.left.path_var.get() == sub, calls)

    app.left.drive_var.set("C:\\")
    app.left.drive_box.event_generate("<<ComboboxSelected>>")
    app.update()
    check("drive selection loads drive root", app.left.path == "C:\\", app.left.path)
    check("no [..] at drive root", dp.UP not in lt.get_children())
    app.left.load(L)

    gone = os.path.join(L, "gone", "deeper")
    os.makedirs(gone)
    app.left.load(gone)
    shutil.rmtree(os.path.join(L, "gone"))
    key(lt, "<Control-r>")
    check("Ctrl+R after folder vanished falls back to existing parent", app.left.path == L, app.left.path)
    write(os.path.join(L, "external.txt"), "e")
    key(lt, "<Control-r>")
    check("Ctrl+R shows externally created file", "external.txt" in names(app.left))
    os.remove(os.path.join(L, "external.txt"))
    app.left.reload()


section(navigation)


def selection_sort():
    """Selection (Ctrl+A, Ctrl+click, Shift+arrows), status, sorting"""
    lt = app.left.tree
    app.left.load(L)
    key(lt, "<Control-a>")
    sel = app.left.selected_paths()
    check("Ctrl+A selects all except [..]", len(sel) == 5 and dp.UP not in sel, sel)
    word = "Označeno" if VER >= "0.3" else "Vybráno"
    check("status shows count and size", app.left.status_var.get() == f"{word} 5 z 5, 2.5 kB",
          app.left.status_var.get())
    if VER >= "0.3":
        key(lt, "<Control-a>")
        check("Ctrl+A again clears marks", not app.left.marked and app.left.status_var.get().startswith("Vybráno"),
              app.left.status_var.get())

    a, b = os.path.join(L, "a.txt"), os.path.join(L, "data.xlsx")
    lt.selection_set(a); lt.focus(a)
    app.update()
    x, y, _, _ = lt.bbox(b)
    lt.event_generate("<Control-ButtonPress-1>", x=x + 10, y=y + 5)
    lt.event_generate("<ButtonRelease-1>", x=x + 10, y=y + 5)
    app.update()
    check("Ctrl+click adds to selection", set(lt.selection()) == {a, b}, lt.selection())

    lt.selection_set(a); lt.focus(a)
    key(lt, "<Shift-Down>")
    key(lt, "<Shift-Down>")
    print("     Treeview class bindings:", [b for b in app.tk.call("bind", "Treeview") if "Shift" in str(b) or "Up" in str(b) or "Down" in str(b)])
    check("Shift+Down extends selection", len(lt.selection()) == 3, lt.selection())
    key(lt, "<Shift-Up>")
    check("Shift+Up shrinks it back", set(lt.selection()) == {a, os.path.join(L, "b.txt")}
          and lt.focus() == os.path.join(L, "b.txt"), lt.selection())
    key(lt, "<Down>")
    key(lt, "<Shift-Up>")
    check("after plain arrow, Shift+Up starts a new range at cursor",
          set(lt.selection()) == {os.path.join(L, "b.txt"), os.path.join(L, "data.xlsx")}, lt.selection())
    lt.selection_set(a); lt.focus(a)
    key(lt, "<Shift-Up>")
    key(lt, "<Shift-Up>")
    check("Shift+Up over [..] never selects [..]", dp.UP not in lt.selection(), lt.selection())

    def order():
        return names(app.left)

    def click(col):
        app.tk.call(lt.heading(col, "command"))
        app.update()

    check("default: folders first, name ascending",
          order() == ["sub", "a.txt", "b.txt", "data.xlsx", "file with space.txt"], order())
    click("size")
    check("sort by size asc", order() == ["sub", "file with space.txt", "a.txt", "data.xlsx", "b.txt"], order())
    click("size")
    check("sort by size desc", order() == ["sub", "b.txt", "data.xlsx", "a.txt", "file with space.txt"], order())
    click("date")
    check("sort by date asc", order() == ["sub", "b.txt", "file with space.txt", "a.txt", "data.xlsx"], order())
    click("name")
    check("sort by name asc again", order()[1] == "a.txt", order())


section(selection_sort)


def f2(lt, answer):
    """F2 with `answer` typed (None = cancel): dialog before 0.6, in-place editor since."""
    if VER < "0.6":
        reset(answer)
        key(lt, "<F2>")
        return
    reset()
    key(lt, "<F2>")
    pane = app.left if lt is app.left.tree else app.right
    if pane.editor is None:
        return
    entry, _, var = pane.editor
    if answer is None:
        key(entry, "<Escape>")
    else:
        var.set(answer)
        key(entry, "<Return>")
    pump(timeout=0.2)


def file_ops():
    """F2 rename, F3/F4 open/edit, F7 new folder"""
    lt = app.left.tree
    app.left.load(L); app.right.load(L)
    select(app.left, "a.txt")
    f2(lt, "c.txt")
    check("F2 renames", os.path.exists(os.path.join(L, "c.txt")) and not os.path.exists(os.path.join(L, "a.txt")))
    check("F2 keeps cursor on renamed file", lt.focus() == os.path.join(L, "c.txt"))
    check("other pane in same folder refreshed", "c.txt" in names(app.right))
    select(app.left, "c.txt")
    f2(lt, "b.txt")
    check("F2 onto existing name -> error, nothing lost",
          kinds() == (["askstring", "showerror"] if VER < "0.6" else ["showerror"])
          and os.path.getsize(os.path.join(L, "b.txt")) == 2000, calls)
    select(app.left, "c.txt")
    f2(lt, None)
    check("F2 cancel does nothing", os.path.exists(os.path.join(L, "c.txt")))
    select(app.left, "c.txt")
    f2(lt, "a.txt")
    app.right.load(R)

    select(app.left, "a.txt")
    reset()
    key(lt, "<F3>")
    check("F3 opens file", started == [os.path.join(L, "a.txt")], started)
    key(lt, "<F4>")
    check("F4 opens Notepad", launched == [["notepad.exe", os.path.join(L, "a.txt")]], launched)
    reset()
    select(app.left, "sub")
    key(lt, "<F4>")
    check("F4 on folder does nothing", not launched)

    reset("nova")
    key(lt, "<F7>")
    check("F7 creates folder and focuses it",
          os.path.isdir(os.path.join(L, "nova")) and lt.focus() == os.path.join(L, "nova"))
    reset("nova")
    key(lt, "<F7>")
    check("F7 existing name -> error", kinds() == ["askstring", "showerror"], calls)
    reset("a?b")
    key(lt, "<F7>")
    check("F7 invalid name -> error", kinds() == ["askstring", "showerror"], calls)
    os.rmdir(os.path.join(L, "nova"))
    app.left.reload()


section(file_ops)


def copy_move():
    """F5 copy, F6 move, conflicts, guards"""
    lt = app.left.tree
    app.left.load(L); app.right.load(R)
    select(app.left, "a.txt", "sub")
    reset(False)
    key(lt, "<F5>")
    check("F5 cancel at confirm does nothing", not os.listdir(R))
    reset(True)
    key(lt, "<F5>")
    wait_job()
    check("F5 copies file and folder", os.path.isfile(os.path.join(R, "a.txt"))
          and os.path.isfile(os.path.join(R, "sub", "inner.txt")))
    check("F5 keeps source", os.path.isfile(os.path.join(L, "a.txt")))
    check("F5 confirm text names target", calls and R in calls[0][1][1], calls)
    check("status Hotovo + right pane refreshed", app.status_var.get() == "Hotovo" and "a.txt" in names(app.right),
          app.status_var.get())

    write(os.path.join(L, "a.txt"), "NEW")
    select(app.left, "a.txt")
    reset(True, conflict(None))
    key(lt, "<F5>")
    check("conflict -> asks; Storno does nothing",
          kinds() == ["askokcancel", CONFLICT] and open(os.path.join(R, "a.txt")).read() == "x" * 10, calls)
    reset(True, conflict(False))
    key(lt, "<F5>"); wait_job()
    check("conflict Ne = skip", open(os.path.join(R, "a.txt")).read() == "x" * 10)
    reset(True, conflict(True))
    key(lt, "<F5>"); wait_job()
    check("conflict Ano = overwrite", open(os.path.join(R, "a.txt")).read() == "NEW")

    os.makedirs(os.path.join(R, "b.txt"))
    select(app.left, "b.txt")
    reset(True, conflict(True))
    key(lt, "<F5>"); wait_job()
    check("overwrite file onto folder -> error shown, nothing lost",
          "showerror" in kinds() and os.path.isdir(os.path.join(R, "b.txt"))
          and os.path.getsize(os.path.join(L, "b.txt")) == 2000, calls)
    os.rmdir(os.path.join(R, "b.txt"))

    app.right.load(L)
    select(app.left, "a.txt")
    reset()
    key(lt, "<F5>")
    check("same folder -> warning", kinds() == ["showwarning"], calls)
    app.right.load(os.path.join(L, "sub"))
    select(app.left, "sub")
    reset()
    key(lt, "<F5>")
    check("copy folder into itself -> warning", kinds() == ["showwarning"], calls)
    app.right.load(R)

    reset()
    app.busy = True
    key(lt, "<F5>")
    app.busy = False
    check("operation while busy -> info", kinds() == ["showinfo"], calls)

    select(app.left, "b.txt")
    reset(True)
    key(lt, "<F6>"); wait_job()
    check("F6 moves file", os.path.isfile(os.path.join(R, "b.txt")) and not os.path.exists(os.path.join(L, "b.txt")))
    os.makedirs(os.path.join(L, "m")); write(os.path.join(L, "m", "1.txt"), "1")
    os.makedirs(os.path.join(R, "m")); write(os.path.join(R, "m", "2.txt"), "2")
    app.left.reload()
    select(app.left, "m")
    reset(True, conflict(False))
    key(lt, "<F6>"); wait_job()
    check("F6 conflict skip keeps source", os.path.isfile(os.path.join(L, "m", "1.txt")))
    reset(True, conflict(True))
    key(lt, "<F6>"); wait_job()
    check("F6 conflict overwrite merges folders and removes source",
          sorted(os.listdir(os.path.join(R, "m"))) == ["1.txt", "2.txt"] and not os.path.exists(os.path.join(L, "m")))

    big = os.path.join(L, "big.bin")
    write(big, os.urandom(1024) * 100 * 1024, "wb")  # 100 MB
    app.left.reload()
    select(app.left, "big.bin")
    reset(True)
    hist, orig_set = [], app.status_var.set
    app.status_var.set = lambda v: (hist.append(v), orig_set(v))
    key(lt, "<F5>")
    wait_job()
    app.status_var.set = orig_set
    seen = any(h.startswith("Kopíruji 1/1") for h in hist)
    check("progress shown in status bar during copy", seen, app.status_var.get())
    check("big file copied intact", os.path.getsize(os.path.join(R, "big.bin")) == os.path.getsize(big))
    os.remove(big); os.remove(os.path.join(R, "big.bin"))
    app.reload_both()


section(copy_move)


def recycle_bin_items():
    ps = ("$s=New-Object -ComObject Shell.Application; "
          "$s.Namespace(10).Items() | ForEach-Object { $_.Name }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    return out


def delete():
    """F8 delete to Recycle Bin, network warning"""
    lt = app.left.tree
    stamp = time.strftime("%H%M%S")
    fname, dname = f"dvojpanel_test_{stamp}.txt", f"dvojpanel_test_dir_{stamp}"
    write(os.path.join(L, fname), "delete me")
    os.makedirs(os.path.join(L, dname)); write(os.path.join(L, dname, "x.txt"), "x")
    app.left.reload()

    orig = dp.is_network_path
    check("local path is not network", not orig(L))
    dp.is_network_path = lambda p: True
    select(app.left, fname)
    reset(False)
    key(lt, "<F8>")
    dp.is_network_path = orig
    check("network disk -> warning about permanent delete",
          calls and "TRVALE" in calls[0][1][1], calls)
    check("answer No keeps file", os.path.exists(os.path.join(L, fname)))

    select(app.left, fname, dname)
    reset(True)
    key(lt, "<F8>")
    check("F8 asks 'do koše'", calls and "do koše" in calls[0][1][1], calls)
    wait_job()
    check("F8 removed file and folder",
          not os.path.exists(os.path.join(L, fname)) and not os.path.exists(os.path.join(L, dname)), calls)
    check("no error dialog", "showerror" not in kinds(), calls)
    rb = recycle_bin_items()
    check("items are in Recycle Bin", fname in rb and dname in rb, rb[-500:])


if not os.environ.get("SKIP_RB"):
    section(delete)

# ---------------------------------------------------------------- tools
write(os.path.join(SCRIPTS, "echo_args.py"),
      "import os, sys, json\nprint('Příliš žluťoučký kůň')\n"
      "print('ARGS:' + json.dumps({'cwd': os.getcwd(), 'args': sys.argv[1:]}))\n")
shutil.copy(os.path.join(SCRIPTS, "echo_args.py"), os.path.join(REL, "nastroje", "echo_args.py"))
write(os.path.join(SCRIPTS, "fail.py"), "import sys\nprint('chyba!', file=sys.stderr)\nsys.exit(3)\n")
write(os.path.join(SCRIPTS, "input.py"), "x = input('Zadej: ')\nprint('got', x)\n")
write(os.path.join(SCRIPTS, "sleep.py"), "import time\nprint('start', flush=True)\ntime.sleep(60)\n")
write(os.path.join(SCRIPTS, "dir with space", "run.bat"), "@echo off\r\necho BAT1=%~1\r\necho BAT2=%~2\r\n")
write(os.path.join(SCRIPTS, "run.cmd"), "@echo off\r\necho CMD1=%~1\r\n")
write(os.path.join(SCRIPTS, "czech.bat"), "@echo off\r\necho Příliš žluťoučký\r\n")
E = "%DP_TEST%/scripts/echo_args.py"
TOOLS = [
    {"nazev": "Relativní", "skript": "nastroje/echo_args.py", "argumenty": ["{soubory}"]},
    {"nazev": "Vše", "skript": E, "argumenty": ["{soubor}", "{slozka}", "{cil}", "{skript_slozka}",
                                                 "--x={zadat:Číslo}", "{zadat:Číslo}", "{zadat:Druhé}"]},
    {"nazev": "Přípony", "skript": E, "argumenty": ["{soubory}"], "pripony": [".XLSX"]},
    {"nazev": "Pracovní", "skript": E, "pracovni_slozka": "{cil}"},
    {"nazev": "Zobrazit", "skript": E, "zobrazit_slozku": "%DP_TEST%\\out"},
    {"nazev": "Fail", "skript": "%DP_TEST%\\scripts\\fail.py", "zobrazit_slozku": "%DP_TEST%/out"},
    {"nazev": "Input", "skript": "%DP_TEST%/scripts/input.py"},
    {"nazev": "Sleep", "skript": "%DP_TEST%/scripts/sleep.py"},
    {"nazev": "Bat mezera", "skript": "%DP_TEST%/scripts/dir with space/run.bat",
     "argumenty": ["{soubor}", "hello world"]},
    {"nazev": "Cmd", "skript": "%DP_TEST%/scripts/run.cmd", "argumenty": ["a b"]},
    {"nazev": "Bat česky", "skript": "%DP_TEST%/scripts/czech.bat"},
    {"nazev": "Exe", "skript": "%SystemRoot%\\System32\\hostname.exe"},
    {"nazev": "Python", "skript": E, "python": sys.executable.replace("\\", "/")},
    {"nazev": "Chybí", "skript": "%DP_TEST%/scripts/neni.py"},
    {"nazev": "Neznámý", "skript": E, "argumenty": ["{neznamy}"]},
    {"nazev": "Soubory uvnitř", "skript": E, "argumenty": ["--f={soubory}"]},
    {"nazev": "Soubor", "skript": E, "argumenty": ["{soubor}"]},
]


def tool(name):
    return next(t for t in app.tools if t["nazev"] == name)


def log_text():
    return app.log_text.get("1.0", "end")


def run(name, timeout=15):
    app.clear_log()
    app.run_tool(tool(name))
    pump(lambda: app.proc is None and "■" in log_text(), timeout)
    return log_text()


def parsed(log):
    line = next((ln for ln in log.splitlines() if ln.startswith("ARGS:")), None)
    return json.loads(line[5:]) if line else None


def tools():
    """Tools: config loading, placeholders, script rules"""
    dp.CONFIG_FILE.write_text("{ broken", encoding="utf-8")
    reset()
    app.tools_menu.invoke(app.tools_menu.index("Načíst nástroje znovu"))
    check("invalid JSON -> error dialog + disabled menu item",
          kinds() == ["showerror"] and app.tools_menu.entrycget(0, "state") == "disabled", calls)
    dp.CONFIG_FILE.write_text(json.dumps({"nastroje": [{"nazev": "x"}]}), encoding="utf-8")
    reset()
    app.reload_tools()
    check("tool without 'skript' -> error", calls and "'skript'" in calls[0][1][1], calls)
    dp.CONFIG_FILE.write_text(json.dumps({"nastroje": TOOLS}, ensure_ascii=False), encoding="utf-8-sig")
    reset()
    app.reload_tools()
    check("valid config with BOM loads", len(app.tools) == len(TOOLS) and not calls, (app.tools_error, calls))
    check("status 'Načteno nástrojů'", app.status_var.get() == f"Načteno nástrojů: {len(TOOLS)}")

    app.left.load(L); app.right.load(R)
    select(app.left, "a.txt", "file with space.txt", "sub")
    log = run("Relativní")
    p = parsed(log)
    check("relative script path, {soubory} = selected files only (each separate arg)",
          p and p["args"] == [os.path.join(L, "a.txt"), os.path.join(L, "file with space.txt")], log)
    check("default cwd = script folder", p and p["cwd"] == os.path.join(REL, "nastroje"), p)
    check("UTF-8 Czech output in log", "Příliš žluťoučký kůň" in log, log)
    check("log shows ▶ name, command, folder and ■ Hotovo",
          "▶ Relativní" in log and "(složka:" in log and "■ Hotovo" in log, log)
    check("status 'hotovo'", app.status_var.get() == "Relativní: hotovo", app.status_var.get())

    select(app.left, "a.txt")
    reset("123", "druhá hodnota")
    log = run("Vše")
    p = parsed(log)
    check("{zadat} asked once per label, 2 dialogs", kinds() == ["askstring", "askstring"], calls)
    check("{zadat} dialog label", calls and calls[0][1][1] == "Číslo:", calls)
    check("{soubor},{slozka},{cil},{skript_slozka},{zadat} substituted",
          p and p["args"] == [os.path.join(L, "a.txt"), L, R, SCRIPTS, "--x=123", "123", "druhá hodnota"], p)
    reset(None)
    app.clear_log()
    app.run_tool(tool("Vše"))
    pump(timeout=1)
    check("cancelling {zadat} does not run tool", app.proc is None and "▶" not in log_text(), log_text())

    select(app.left, "a.txt", "data.xlsx")
    reset()
    app.clear_log()
    app.run_tool(tool("Přípony"))
    check("pripony: wrong extension -> warning, not run",
          kinds() == ["showwarning"] and "a.txt" in calls[0][1][1] and app.proc is None, calls)
    select(app.left, "data.xlsx")
    log = run("Přípony")
    check("pripony: matching (case-insensitive) runs", "■ Hotovo" in log, log)

    log = run("Pracovní")
    check("pracovni_slozka with placeholder", (parsed(log) or {}).get("cwd") == R, log)

    app.right.load(R)
    run("Zobrazit")
    check("zobrazit_slozku opened in other pane after success", app.right.path == OUT, app.right.path)
    app.right.load(R)
    log = run("Fail")
    check("non-zero exit -> error + code in log", "návratový kód 3" in log and "chyba!" in log, log)
    check("stderr shown, status shows error", app.status_var.get() == "Fail: chyba 3", app.status_var.get())
    check("zobrazit_slozku NOT opened after failure", app.right.path == R, app.right.path)

    t0 = time.time()
    log = run("Input", timeout=10)
    check("input() fails fast instead of hanging", "EOFError" in log and time.time() - t0 < 8, log)

    log = run("Exe")
    check(".exe via %SystemRoot% and backslashes", os.environ["COMPUTERNAME"].lower() in log.lower(), log)
    log = run("Python")
    check("custom 'python' interpreter", "■ Hotovo" in log and parsed(log), log)
    log = run("Cmd")
    check(".cmd script with argument", "CMD1=a b" in log, log)

    select(app.left, "file with space.txt")
    log = run("Bat mezera")
    check(".bat in folder with space + quoted args",
          f"BAT1={os.path.join(L, 'file with space.txt')}" in log and "BAT2=hello world" in log, log)
    check(".bat command logged as cmd /s /c", 'cmd /s /c ""' in log, log)
    log = run("Bat česky")
    check(".bat Czech output readable", "Příliš žluťoučký" in log, log)

    reset()
    app.run_tool(tool("Chybí"))
    check("missing script -> error dialog", kinds() == ["showerror"] and "neexistuje" in calls[0][1][1], calls)
    reset()
    app.run_tool(tool("Neznámý"))
    check("unknown placeholder -> error", kinds() == ["showerror"] and "{neznamy}" in calls[0][1][1], calls)
    select(app.left, "a.txt")
    reset()
    app.run_tool(tool("Soubory uvnitř"))
    check("{soubory} inside argument -> error (README: must stand alone)", kinds() == ["showerror"], calls)
    if calls:
        print("     message:", calls[0][1][1].replace("\n", " "))
    select(app.left, "sub")
    reset()
    app.run_tool(tool("Soubor"))
    check("{soubor} with folder under cursor -> error", kinds() == ["showerror"], calls)
    reset()
    app.run_tool(tool("Relativní"))
    check("{soubory} with no file selected -> error", kinds() == ["showerror"], calls)

    select(app.left, "a.txt")
    app.clear_log()
    app.run_tool(tool("Sleep"))
    pump(lambda: "start" in log_text(), 10)
    check("long tool running, output streamed live", app.proc is not None and "start" in log_text(), log_text())
    reset()
    app.run_tool(tool("Relativní"))
    check("only one tool at a time", kinds() == ["showinfo"], calls)
    reset(False)
    app.on_close()
    check("close while tool runs asks; No keeps app", kinds() == ["askyesno"] and app.winfo_exists(), calls)
    app.tools_menu.invoke(app.tools_menu.index("Zastavit běžící nástroj"))
    pump(lambda: app.proc is None, 10)
    check("Zastavit stops tool", app.proc is None and "Zastavuji" in log_text() and "návratový kód" in log_text(),
          log_text())
    app.tools_menu.invoke(app.tools_menu.index("Vymazat výstup"))
    check("Vymazat výstup clears log", log_text().strip() == "")

    orig = sys.executable
    sys.executable = os.path.join(os.path.dirname(orig), "pythonw.exe")
    check("tools under pythonw use python.exe", dp.python_executable() == os.path.join(os.path.dirname(orig), "python.exe"))
    sys.executable = orig


section(tools)


def paths():
    """Script paths: spaces, diacritics, ~, .., vars, interpreters, example config"""
    weird = os.path.join(SCRIPTS, "Moje skripty", "čeština")
    os.makedirs(weird)
    shutil.copy(os.path.join(SCRIPTS, "echo_args.py"), os.path.join(weird, "výpis souborů.py"))
    os.makedirs(os.path.join(HOME, "skripty"), exist_ok=True)  # same folder as Skripty on Windows
    shutil.copy(os.path.join(SCRIPTS, "echo_args.py"), os.path.join(HOME, "skripty", "echo.py"))
    shutil.copy(os.path.join(os.environ["SystemRoot"], "System32", "hostname.exe"),
                os.path.join(SCRIPTS, "dir with space", "host name.exe"))
    venv = os.path.join(ENV, "venv s mezerou")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", venv], check=True)
    # example config: create the scripts it points to under the (test) USERPROFILE
    ex_dir = os.path.join(HOME, "Skripty")
    os.makedirs(os.path.join(ex_dir, "windchill", "vystupy"), exist_ok=True)
    write(os.path.join(ex_dir, "windchill", "uprava_exportu_AffectedObjects.py"),
          "import sys\nprint('export upraven', sys.prefix)\n")
    shutil.copy(os.path.join(SCRIPTS, "echo_args.py"), os.path.join(ex_dir, "windchill", "dotaz.py"))
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", os.path.join(ex_dir, "windchill", ".venv")],
                   check=True)
    os.makedirs("C:/Deviation_Export/Output", exist_ok=True)

    bat = "%DP_TEST%/scripts/dir with space/run.bat"
    W = os.path.join(weird, "výpis souborů.py")
    ptools = [
        {"nazev": "P diakritika", "skript": W, "argumenty": ["{soubory}"]},
        {"nazev": "P tilda", "skript": "~/skripty/echo.py"},
        {"nazev": "P tečky", "skript": "nastroje/../nastroje/echo_args.py"},
        {"nazev": "P lomítka mix", "skript": "%DP_TEST%\\scripts/echo_args.py"},
        {"nazev": "P bez proměnné", "skript": "%NEEXISTUJE_DP%/x.py"},
        {"nazev": "P bat bez arg", "skript": bat},
        {"nazev": "P bat 1 arg", "skript": bat, "argumenty": ["x"]},
        {"nazev": "P bat 2 args", "skript": bat, "argumenty": ["x", "y"]},
        {"nazev": "P bat arg mezera", "skript": bat, "argumenty": ["a b"]},
        {"nazev": "P exe mezera", "skript": "%DP_TEST%/scripts/dir with space/host name.exe"},
        {"nazev": "P exe mezera arg", "skript": "%DP_TEST%/scripts/dir with space/host name.exe",
         "argumenty": ["/?"]},
        {"nazev": "P venv mezera", "skript": W, "python": venv + "\\Scripts\\python.exe"},
        {"nazev": "P venv %VAR%", "skript": E, "python": "%DP_TEST%/venv s mezerou/Scripts/python.exe"},
        {"nazev": "P python jménem", "skript": E, "python": "python"},
        {"nazev": "P python neexistuje", "skript": E, "python": "C:/neni/python.exe"},
        {"nazev": "P prac. relativní", "skript": E, "pracovni_slozka": "nastroje"},
        {"nazev": "P prac. neexistuje", "skript": E, "pracovni_slozka": "C:/neni/slozka"},
        {"nazev": "P zobrazit relativní", "skript": E, "zobrazit_slozku": "nastroje"},
    ]
    dp.CONFIG_FILE.write_text(json.dumps({"nastroje": ptools}, ensure_ascii=False), encoding="utf-8")
    app.reload_tools()
    app.left.load(L); app.right.load(R)

    select(app.left, "file with space.txt")
    log = run("P diakritika")
    p = parsed(log)
    check("script in 'Moje skripty/čeština/výpis souborů.py'",
          p and p["args"] == [os.path.join(L, "file with space.txt")] and p["cwd"] == weird, log)
    log = run("P tilda")
    check("~ expands to USERPROFILE", (parsed(log) or {}).get("cwd") == os.path.join(HOME, "skripty"), log)
    log = run("P tečky")
    check("relative path with .. normalized", (parsed(log) or {}).get("cwd") == os.path.join(REL, "nastroje"), log)
    log = run("P lomítka mix")
    check("mixed / and \\ in path", "■ Hotovo" in log, log)
    reset()
    app.run_tool(tool("P bez proměnné"))
    check("undefined %VAR% -> clear 'Skript neexistuje' error",
          kinds() == ["showerror"] and "neexistuje" in calls[0][1][1], calls)
    if calls:
        print("     message:", calls[0][1][1].replace("\n", " "))

    for name, expect in [("P bat bez arg", ["BAT1=", "■ Hotovo"]),
                         ("P bat 1 arg", ["BAT1=x"]),
                         ("P bat 2 args", ["BAT1=x", "BAT2=y"]),
                         ("P bat arg mezera", ["BAT1=a b"])]:
        log = run(name)
        check(f".bat in folder with space: {name}", all(e in log for e in expect), log)
    log = run("P exe mezera")
    check(".exe in folder with space", os.environ["COMPUTERNAME"].lower() in log.lower(), log)
    log = run("P exe mezera arg")
    check(".exe in folder with space + arg", "■" in log and "Nelze spustit" not in log, log)

    log = run("P venv mezera", timeout=20)
    check("venv interpreter with space in path", "■ Hotovo" in log and parsed(log), log)
    log = run("P venv %VAR%", timeout=20)
    check("venv interpreter via %VAR% and /", "■ Hotovo" in log, log)
    log = run("P python jménem")
    check("interpreter by bare name 'python' (PATH)", "■ Hotovo" in log, log)
    reset()
    log = run("P python neexistuje", timeout=3)
    check("missing interpreter -> visible error", "Nelze spustit" in log or "showerror" in kinds(), (log, calls))
    log = run("P prac. relativní")
    check("relative pracovni_slozka resolved against program folder",
          (parsed(log) or {}).get("cwd") == os.path.join(REL, "nastroje"), log)
    reset()
    log = run("P prac. neexistuje", timeout=3)
    check("missing pracovni_slozka -> visible error", "Nelze spustit" in log or "showerror" in kinds(), (log, calls))
    app.right.load(R)
    run("P zobrazit relativní")
    check("relative zobrazit_slozku", app.right.path == os.path.join(REL, "nastroje"), app.right.path)

    # the shipped example config, unchanged
    shutil.copyfile(dp.CONFIG_EXAMPLE, dp.CONFIG_FILE)
    app.reload_tools()
    app.right.load(R)
    select(app.left, "a.txt", "b.txt" if os.path.exists(os.path.join(L, "b.txt")) else "a.txt")
    log = run("Ukázka: vypsat vybrané soubory")
    check("example: Ukázka (nastroje/ukazka.py) runs", "Celkem souborů" in log and "■ Hotovo" in log, log)
    wc_venv = os.path.join(ex_dir, "windchill", ".venv")
    log = run("Úprava exportu AffectedObjects (C:\\Deviation_Export)")
    check("example: AffectedObjects script runs via project .venv",
          "export upraven" in log and wc_venv.lower() in log.lower(), log)
    check("example: zobrazit_slozku C:/Deviation_Export/Output opened",
          os.path.normcase(app.right.path) == os.path.normcase(r"C:\Deviation_Export\Output"), app.right.path)
    app.right.load(R)
    reset("PN-12345 PN-67890")
    log = run("Dotaz na čísla dílů → XLSX")
    p = parsed(log)
    check("example: dotaz via .venv, {zadat} + --vystup xlsx",
          p and p["args"] == ["PN-12345 PN-67890", "--vystup", "xlsx"] and wc_venv.lower() in log.lower(), log)
    check("example: dotaz opens vystupy in other pane",
          app.right.path == os.path.join(ex_dir, "windchill", "vystupy"), app.right.path)


section(paths)


def bat_fix():
    """Proposed fix for .bat quoting: cmd /s /c \"<list2cmdline>\""""
    bat = os.path.join(SCRIPTS, "dir with space", "run.bat")
    for args in (["a b", "c d"], [], ["x"], [os.path.join(L, "file with space.txt"), "&echo INJECTED"]):
        line = 'cmd /s /c "' + subprocess.list2cmdline([bat] + args) + '"'
        out = subprocess.run(line, capture_output=True, text=True).stdout
        exp1 = args[0] if args else ""
        check(f"fixed .bat call with args {args}", f"BAT1={exp1}" in out and "INJECTED" not in out.replace("BAT2=&echo INJECTED", ""), out)




def shutdown():
    """Ctrl+Q closes"""
    key(app.left.tree, "<Control-q>")
    try:
        alive = app.winfo_exists()
    except Exception:
        alive = False
    check("Ctrl+Q closes window", not alive)


if VER >= "0.3":
    exec(open(os.path.join(os.path.dirname(__file__), 'v030.py'), encoding='utf-8').read())
if VER >= "0.4":
    from pathlib import Path
    exec(open(os.path.join(os.path.dirname(__file__), 'v040.py'), encoding='utf-8').read())
if VER >= "0.5":
    exec(open(os.path.join(os.path.dirname(__file__), 'v050.py'), encoding='utf-8').read())
if VER >= "0.6":
    exec(open(os.path.join(os.path.dirname(__file__), 'v060.py'), encoding='utf-8').read())
if VER >= "0.7":
    exec(open(os.path.join(os.path.dirname(__file__), 'v070.py'), encoding='utf-8').read())
if VER >= "0.8":
    exec(open(os.path.join(os.path.dirname(__file__), 'v080.py'), encoding='utf-8').read())
if VER >= "0.9":
    exec(open(os.path.join(os.path.dirname(__file__), 'v090.py'), encoding='utf-8').read())
if VER >= "0.10":
    exec(open(os.path.join(os.path.dirname(__file__), 'v100.py'), encoding='utf-8').read())
section(shutdown)


def launch():
    """Launch: python / pythonw dvojpanel.py"""
    exe_dir = os.path.dirname(sys.executable)
    for exe in ("python.exe", "pythonw.exe"):
        env = dict(os.environ, USERPROFILE=HOME)
        p = real_popen([os.path.join(exe_dir, exe), os.path.join(REL, "dvojpanel.py")], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        title = ""
        for _ in range(30):
            time.sleep(0.3)
            title = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    f"(Get-Process -Id {p.pid}).MainWindowTitle"],
                                   capture_output=True, text=True).stdout.strip()
            if title or p.poll() is not None:
                break
        alive = p.poll() is None
        p.kill()
        _, err = p.communicate()
        check(f"{exe} dvojpanel.py starts with window 'Dvojpanel 0.2.0'", alive and title == f"Dvojpanel {VER}",
              (title, err.decode(errors="replace")[-500:]))


section(launch)

passed = sum(r[1] for r in results)
print(f"\n{passed}/{len(results)} passed")
for n, ok, d in results:
    if not ok:
        print(f"FAIL: {n}\n      {str(d)[:1500]}")
sys.exit(0 if passed == len(results) else 1)
