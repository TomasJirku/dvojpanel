"""
Dvojpanel – dvoupanelový správce souborů pro Windows se spouštěním vlastních skriptů.
Pouze standardní knihovna Pythonu (tkinter), nic se neinstaluje.

Spuštění:  python dvojpanel.py   (nebo pythonw dvojpanel.py bez konzole)

Ovládání:
  Tab              přepnutí panelu
  Enter / dvojklik otevřít složku nebo soubor
  Backspace        o úroveň výš
  Ctrl+klik, Shift+šipky, Ctrl+A   výběr více položek
  F2 přejmenovat   F3 otevřít      F4 upravit v Notepadu
  F5 kopírovat     F6 přesunout    F7 nová složka   F8 smazat do koše
  F9 nástroje (vlastní skripty z nastroje.json)
  Ctrl+R obnovit   Ctrl+Q konec
  Klik na záhlaví sloupce = řazení
"""
__version__ = "0.2.0"

import json
import os
import re
import sys
import shutil
import string
import queue
import threading
import subprocess
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

IS_WINDOWS = sys.platform == "win32"
UP = ".."
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "nastroje.json"
CONFIG_EXAMPLE = APP_DIR / "nastroje.example.json"
PLACEHOLDER = re.compile(r"\{(\w+)(?::([^}]*))?\}")


# ---------------------------------------------------------------- helpers

def human_size(n):
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_time(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except (OSError, ValueError, OverflowError):
        return ""


def list_drives():
    if not IS_WINDOWS:
        return ["/"]
    return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]


def is_inside(child, parent):
    """True if child is parent itself or lies somewhere below it."""
    child = os.path.normcase(os.path.abspath(child))
    parent = os.path.normcase(os.path.abspath(parent))
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives
        return False


def is_network_path(path):
    if not IS_WINDOWS:
        return False
    if path.startswith("\\\\"):
        return True
    import ctypes
    root = os.path.splitdrive(path)[0] + "\\"
    return ctypes.windll.kernel32.GetDriveTypeW(root) == 4  # DRIVE_REMOTE


def remove_path(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def send_to_recycle_bin(paths):
    """Delete through the Windows shell so items land in the Recycle Bin."""
    if not IS_WINDOWS:
        raise OSError("Koš je podporován jen ve Windows.")
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        if ctypes.sizeof(ctypes.c_void_p) == 4:
            _pack_ = 1
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", ctypes.c_void_p),
            ("pTo", ctypes.c_void_p),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 0x4, 0x10, 0x40, 0x400

    text = "\0".join(os.path.abspath(p) for p in paths) + "\0\0"
    buf = (ctypes.c_wchar * len(text))(*text)  # double-null-terminated list
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = ctypes.addressof(buf)
    op.fFlags = FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if result != 0:
        raise OSError(f"Mazání selhalo (kód {result:#x}).")


def open_with_default_app(path):
    if IS_WINDOWS:
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------- workers (run in a thread)

def transfer_worker(sources, dest, move, overwrite, report):
    errors = []
    verb = "Přesouvám" if move else "Kopíruji"
    for i, src in enumerate(sources, 1):
        name = os.path.basename(src)
        target = os.path.join(dest, name)
        report(f"{verb} {i}/{len(sources)}: {name}")
        try:
            exists = os.path.lexists(target)
            if exists and not overwrite:
                continue
            if exists and os.path.isdir(src) != os.path.isdir(target):
                errors.append(f"{name}: v cíli existuje položka jiného typu")
                continue
            if move and not exists:
                shutil.move(src, target)
                continue
            # copy (or overwrite-move = copy over the target, then remove the source)
            if os.path.isdir(src):
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                shutil.copy2(src, target)
            if move:
                remove_path(src)
        except OSError as e:
            errors.append(f"{name}: {e}")
    return errors


def delete_worker(paths, report):
    report(f"Mažu {len(paths)} položek…")
    send_to_recycle_bin(paths)
    return []


# ---------------------------------------------------------------- tools (user scripts)

class ToolCancelled(Exception):
    """User cancelled an input prompt."""


def expand_path(path):
    """Expand %VARS% and ~, resolve relative paths against the app folder."""
    path = os.path.expandvars(os.path.expanduser(str(path)))
    if not os.path.isabs(path):
        path = os.path.join(APP_DIR, path)
    return os.path.normpath(path)


def python_executable():
    """Interpreter for tools; python.exe instead of pythonw.exe so output can be captured."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        alt = exe[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(alt):
            return alt
    return exe


def load_tools():
    """Return (tools, error_message)."""
    if not CONFIG_FILE.exists() and CONFIG_EXAMPLE.exists():
        try:
            shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)
        except OSError as e:
            return [], f"Nelze vytvořit nastroje.json: {e}"
    if not CONFIG_FILE.exists():
        return [], "Chybí soubor nastroje.json."
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return [], f"Chyba v nastroje.json: {e}"
    tools = data.get("nastroje", []) if isinstance(data, dict) else []
    for i, tool in enumerate(tools, 1):
        if not isinstance(tool, dict) or not tool.get("nazev") or not tool.get("skript"):
            return [], f"nastroje.json: nástroj č. {i} musí mít 'nazev' a 'skript'."
    return tools, None


def build_command(tool, ctx, ask):
    """Build (command, working_dir) for a tool.

    ctx: soubory (list), soubor, slozka, cil (str). ask(label) -> str or None.
    Raises ValueError for config/selection problems, ToolCancelled on cancel.
    """
    script = expand_path(tool["skript"])
    if not os.path.isfile(script):
        raise ValueError(f"Skript neexistuje:\n{script}")
    ctx = dict(ctx, skript_slozka=os.path.dirname(script))
    answers = {}

    def substitute(text):
        def repl(m):
            name, label = m.group(1), m.group(2)
            if name == "zadat":
                label = label or "Hodnota"
                if label not in answers:
                    value = ask(label)
                    if value is None:
                        raise ToolCancelled
                    answers[label] = value
                return answers[label]
            value = ctx.get(name)
            if not isinstance(value, str):
                raise ValueError(f"Neznámý zástupný symbol {{{name}}} v nástroji „{tool['nazev']}“.")
            if not value:
                raise ValueError(f"Pro {{{name}}} není nic vybráno.")
            return value
        return PLACEHOLDER.sub(repl, text)

    suffix = os.path.splitext(script)[1].lower()
    if suffix in (".py", ".pyw"):
        interp = tool.get("python")
        if not interp:
            interp = python_executable()
        elif "/" in interp or "\\" in interp:
            interp = expand_path(interp)
        cmd = [interp, script]
    elif suffix in (".bat", ".cmd"):
        cmd = ["cmd", "/c", script]
    else:
        cmd = [script]

    for arg in tool.get("argumenty", []):
        if arg == "{soubory}":
            if not ctx["soubory"]:
                raise ValueError("Nástroj potřebuje vybrané soubory, ale žádný není vybrán.")
            cmd.extend(ctx["soubory"])
        else:
            cmd.append(substitute(str(arg)))

    if tool.get("pracovni_slozka"):
        cwd = expand_path(substitute(tool["pracovni_slozka"]))
    else:
        cwd = os.path.dirname(script)
    return cmd, cwd


# ---------------------------------------------------------------- one panel

class Pane(ttk.Frame):
    COLUMNS = ("name", "size", "date")

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.path = ""
        self.items = []
        self.sizes = {}
        self.sort_col, self.sort_rev = "name", False

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 2))
        self.marker = tk.Label(top, text="●", fg="#999999")
        self.marker.pack(side="left")
        self.drive_var = tk.StringVar()
        self.drive_box = ttk.Combobox(top, textvariable=self.drive_var, values=list_drives(),
                                      width=6, state="readonly")
        self.drive_box.pack(side="left")
        self.drive_box.bind("<<ComboboxSelected>>", lambda e: self.load(self.drive_var.get()))
        self.path_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.path_var)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        entry.bind("<Return>", lambda e: self.load(self.path_var.get()))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=self.COLUMNS, show="headings", selectmode="extended")
        for col, title in zip(self.COLUMNS, ("Název", "Velikost", "Změněno")):
            self.tree.heading(col, text=title, command=lambda c=col: self.sort_by(c))
        self.tree.column("name", width=280)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("date", width=125, anchor="center", stretch=False)
        self.tree.tag_configure("dir", foreground="#0b4ea2")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x")

        t = self.tree
        t.bind("<Return>", lambda e: self.activate_item())
        t.bind("<Double-1>", lambda e: self.activate_item())
        t.bind("<BackSpace>", lambda e: self.go_up())
        t.bind("<Tab>", lambda e: (self.app.switch_pane(), "break")[1])
        t.bind("<Control-a>", lambda e: (self.select_all(), "break")[1])
        t.bind("<FocusIn>", lambda e: self.app.set_active(self))
        t.bind("<<TreeviewSelect>>", lambda e: self.update_status())

    # -- navigation
    def load(self, path, focus_name=None):
        path = os.path.abspath(path)
        try:
            entries = list(os.scandir(path))
        except OSError as e:
            messagebox.showerror("Chyba", f"Nelze otevřít:\n{path}\n\n{e}")
            self.path_var.set(self.path)
            return
        self.path = path
        self.path_var.set(path)
        self.drive_var.set(os.path.splitdrive(path)[0] + "\\" if IS_WINDOWS else "/")
        self.items = []
        for entry in entries:
            try:
                is_dir = entry.is_dir()
                st = entry.stat()
            except OSError:
                continue
            self.items.append((entry.name, is_dir, 0 if is_dir else st.st_size, st.st_mtime))
        self.refresh_view(focus_name)

    def refresh_view(self, focus_name=None):
        key = {"name": lambda i: i[0].lower(), "size": lambda i: i[2], "date": lambda i: i[3]}[self.sort_col]
        dirs = sorted((i for i in self.items if i[1]), key=key, reverse=self.sort_rev)
        files = sorted((i for i in self.items if not i[1]), key=key, reverse=self.sort_rev)

        self.tree.delete(*self.tree.get_children())
        self.sizes = {}
        if os.path.dirname(self.path) != self.path:
            self.tree.insert("", "end", iid=UP, values=("[..]", "", ""))
        for name, is_dir, size, mtime in dirs + files:
            iid = os.path.join(self.path, name)
            self.sizes[iid] = size
            self.tree.insert("", "end", iid=iid, tags=("dir",) if is_dir else (),
                             values=(f"[{name}]" if is_dir else name,
                                     "<DIR>" if is_dir else human_size(size),
                                     fmt_time(mtime)))

        target = os.path.join(self.path, focus_name) if focus_name else None
        children = self.tree.get_children()
        sel = target if target and self.tree.exists(target) else (children[0] if children else None)
        if sel:
            self.tree.focus(sel)
            self.tree.selection_set(sel)
            self.tree.see(sel)
        self.update_status()

    def reload(self):
        path = self.path
        while path and not os.path.isdir(path):  # folder may have been deleted/moved
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
        focus = self.tree.focus()
        self.drive_box["values"] = list_drives()
        self.load(path, os.path.basename(focus) if focus and focus != UP else None)

    def activate_item(self):
        item = self.tree.focus()
        if not item:
            return
        if item == UP:
            self.go_up()
        elif os.path.isdir(item):
            self.load(item)
        else:
            self.app.open_file(item)

    def go_up(self):
        parent = os.path.dirname(self.path)
        if parent != self.path:
            self.load(parent, focus_name=os.path.basename(self.path))

    def sort_by(self, col):
        if col == self.sort_col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, False
        focus = self.tree.focus()
        self.refresh_view(os.path.basename(focus) if focus and focus != UP else None)

    # -- selection
    def select_all(self):
        self.tree.selection_set([i for i in self.tree.get_children() if i != UP])

    def selected_paths(self):
        return [i for i in self.tree.selection() if i != UP]

    def update_status(self):
        sel = self.selected_paths()
        total = sum(self.sizes.get(p, 0) for p in sel)
        self.status_var.set(f"Vybráno {len(sel)} z {len(self.items)}, {human_size(total)}")

    def set_marker(self, active):
        self.marker.configure(fg="#2e9e3e" if active else "#999999")


# ---------------------------------------------------------------- main window

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Dvojpanel {__version__}")
        self.geometry("1150x760")
        self.busy = False
        self.proc = None
        self.tools, self.tools_error = [], None
        self.jobs = queue.Queue()

        main = ttk.PanedWindow(self, orient="vertical")
        main.pack(fill="both", expand=True, padx=4, pady=4)
        panes = ttk.PanedWindow(main, orient="horizontal")
        self.left, self.right = Pane(panes, self), Pane(panes, self)
        panes.add(self.left, weight=1)
        panes.add(self.right, weight=1)
        main.add(panes, weight=4)
        self.active = self.left

        log_frame = ttk.Frame(main)
        self.log_text = tk.Text(log_frame, height=8, wrap="word", state="disabled",
                                font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        main.add(log_frame, weight=1)

        self.status_var = tk.StringVar(value="Připraveno")
        ttk.Label(self, textvariable=self.status_var, anchor="w", relief="sunken").pack(fill="x", padx=4)

        keys = [("F2", "Přejmenovat", self.rename), ("F3", "Otevřít", self.open_current),
                ("F4", "Upravit", self.edit_current), ("F5", "Kopírovat", lambda: self.transfer(False)),
                ("F6", "Přesunout", lambda: self.transfer(True)), ("F7", "Nová složka", self.make_dir),
                ("F8", "Smazat", self.delete), ("F9", "Nástroje", self.show_tools_popup)]
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=4, pady=4)
        for key, label, cmd in keys:
            ttk.Button(bar, text=f"{key} {label}", command=cmd, takefocus=False).pack(
                side="left", fill="x", expand=True)
            self.bind(f"<{key}>", lambda e, c=cmd: c())
        self.bind("<Control-r>", lambda e: self.reload_both())
        self.bind("<Control-q>", lambda e: self.on_close())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_menu()

        home = os.path.expanduser("~")
        self.left.load(home)
        self.right.load(home)
        self.set_active(self.left)
        self.left.tree.focus_set()
        self.after(100, self.poll_jobs)

    # -- panes
    @property
    def other(self):
        return self.right if self.active is self.left else self.left

    def set_active(self, pane):
        self.active = pane
        self.left.set_marker(pane is self.left)
        self.right.set_marker(pane is self.right)

    def switch_pane(self):
        target = self.other
        target.tree.focus_set()
        if not target.tree.focus():
            children = target.tree.get_children()
            if children:
                target.tree.focus(children[0])
                target.tree.selection_set(children[0])
        self.set_active(target)

    def reload_both(self):
        self.left.reload()
        self.right.reload()

    def is_busy(self):
        if self.busy:
            messagebox.showinfo("Probíhá operace", "Počkej, až doběhne předchozí operace.")
        return self.busy

    # -- file actions
    def open_file(self, path):
        try:
            open_with_default_app(path)
        except OSError as e:
            messagebox.showerror("Chyba", str(e))

    def open_current(self):
        item = self.active.tree.focus()
        if item and item != UP:
            self.open_file(item)

    def edit_current(self):
        item = self.active.tree.focus()
        if item and item != UP and os.path.isfile(item):
            subprocess.Popen(["notepad.exe" if IS_WINDOWS else "xdg-open", item])

    def rename(self):
        pane = self.active
        item = pane.tree.focus()
        if not item or item == UP or self.is_busy():
            return
        old = os.path.basename(item)
        new = simpledialog.askstring("Přejmenovat", "Nový název:", initialvalue=old, parent=self)
        if not new or new == old:
            return
        try:
            os.rename(item, os.path.join(pane.path, new))
        except OSError as e:
            messagebox.showerror("Chyba", str(e))
            return
        pane.load(pane.path, focus_name=new)
        if os.path.normcase(self.other.path) == os.path.normcase(pane.path):
            self.other.reload()

    def make_dir(self):
        pane = self.active
        if self.is_busy():
            return
        name = simpledialog.askstring("Nová složka", "Název složky:", parent=self)
        if not name:
            return
        try:
            os.mkdir(os.path.join(pane.path, name))
        except OSError as e:
            messagebox.showerror("Chyba", str(e))
            return
        pane.load(pane.path, focus_name=name)

    def transfer(self, move):
        if self.is_busy():
            return
        src_pane, dest = self.active, self.other.path
        sources = src_pane.selected_paths()
        if not sources:
            return
        if os.path.normcase(src_pane.path) == os.path.normcase(dest):
            messagebox.showwarning("Stejná složka", "Zdroj a cíl jsou stejná složka.")
            return
        for s in sources:
            if os.path.isdir(s) and is_inside(dest, s):
                messagebox.showwarning("Nelze", f"Složku nelze kopírovat do sebe sama:\n{s}")
                return
        verb = "Přesunout" if move else "Kopírovat"
        if not messagebox.askokcancel(verb, f"{verb} {len(sources)} položek do:\n{dest}"):
            return
        conflicts = [s for s in sources if os.path.lexists(os.path.join(dest, os.path.basename(s)))]
        overwrite = False
        if conflicts:
            answer = messagebox.askyesnocancel(
                "Položky už existují",
                f"{len(conflicts)} položek v cíli už existuje.\n\n"
                "Ano = přepsat (složky se sloučí)\nNe = přeskočit\nStorno = nic nedělat")
            if answer is None:
                return
            overwrite = answer
        self.run_job(transfer_worker, sources, dest, move, overwrite)

    def delete(self):
        if self.is_busy():
            return
        paths = self.active.selected_paths()
        if not paths:
            return
        msg = f"Přesunout {len(paths)} položek do koše?"
        if is_network_path(self.active.path):
            msg = f"POZOR: síťový disk nemá koš, {len(paths)} položek se smaže TRVALE.\n\nPokračovat?"
        if messagebox.askyesno("Smazat", msg, icon="warning"):
            self.run_job(delete_worker, paths)

    # -- background jobs
    def run_job(self, func, *args):
        self.busy = True

        def report(text):
            self.jobs.put(("progress", text))

        def runner():
            try:
                errors = func(*args, report)
            except Exception as e:  # noqa: BLE001 – show anything to the user
                errors = [str(e)]
            self.jobs.put(("done", errors))

        threading.Thread(target=runner, daemon=True).start()

    def poll_jobs(self):
        try:
            while True:
                kind, data = self.jobs.get_nowait()
                if kind == "progress":
                    self.status_var.set(data)
                elif kind == "log":
                    self.log(data)
                elif kind == "done":
                    self.finish_job(data)
                elif kind == "tool_done":
                    self.finish_tool(*data)
        except queue.Empty:
            pass
        self.after(100, self.poll_jobs)

    def finish_job(self, errors):
        self.busy = False
        self.status_var.set(f"Hotovo, chyb: {len(errors)}" if errors else "Hotovo")
        self.reload_both()
        if errors:
            extra = f"\n… a dalších {len(errors) - 15}" if len(errors) > 15 else ""
            messagebox.showerror("Chyby", "\n".join(errors[:15]) + extra)

    # -- menu and tools
    def build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Obnovit", accelerator="Ctrl+R", command=self.reload_both)
        file_menu.add_separator()
        file_menu.add_command(label="Konec", accelerator="Ctrl+Q", command=self.on_close)
        menubar.add_cascade(label="Soubor", menu=file_menu)
        self.tools_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Nástroje", menu=self.tools_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="O programu", command=lambda: messagebox.showinfo(
            "O programu", f"Dvojpanel {__version__}\nPython {sys.version.split()[0]}"))
        menubar.add_cascade(label="Nápověda", menu=help_menu)
        self.configure(menu=menubar)
        self.reload_tools(startup=True)

    def fill_tools_menu(self, menu):
        menu.delete(0, "end")
        if self.tools:
            for tool in self.tools:
                menu.add_command(label=tool["nazev"], command=lambda t=tool: self.run_tool(t))
        else:
            menu.add_command(label=self.tools_error or "Žádné nástroje", state="disabled")
        menu.add_separator()
        menu.add_command(label="Upravit nastroje.json", command=self.edit_tools)
        menu.add_command(label="Načíst nástroje znovu", command=self.reload_tools)
        menu.add_command(label="Zastavit běžící nástroj", command=self.stop_tool)
        menu.add_command(label="Vymazat výstup", command=self.clear_log)

    def reload_tools(self, startup=False):
        self.tools, self.tools_error = load_tools()
        self.fill_tools_menu(self.tools_menu)
        if self.tools_error:
            self.log(f"⚠ {self.tools_error}\n")
            if not startup:
                messagebox.showerror("Nástroje", self.tools_error)
        elif not startup:
            self.status_var.set(f"Načteno nástrojů: {len(self.tools)}")

    def show_tools_popup(self):
        menu = tk.Menu(self, tearoff=False)
        self.fill_tools_menu(menu)
        tree = self.active.tree
        menu.tk_popup(tree.winfo_rootx() + 40, tree.winfo_rooty() + 40)

    def edit_tools(self):
        if not CONFIG_FILE.exists():
            load_tools()  # creates it from the example
        if CONFIG_FILE.exists():
            subprocess.Popen(["notepad.exe" if IS_WINDOWS else "xdg-open", str(CONFIG_FILE)])

    def run_tool(self, tool):
        if self.proc is not None:
            messagebox.showinfo("Nástroj běží",
                                "Počkej, až doběhne předchozí nástroj, nebo ho zastav v menu Nástroje.")
            return
        pane = self.active
        files = [p for p in pane.selected_paths() if os.path.isfile(p)]
        focus = pane.tree.focus()
        ctx = {"soubory": files,
               "soubor": focus if focus and focus != UP and os.path.isfile(focus) else "",
               "slozka": pane.path,
               "cil": self.other.path}

        exts = [e.lower() for e in tool.get("pripony", [])]
        if exts:
            wrong = [os.path.basename(f) for f in files if os.path.splitext(f)[1].lower() not in exts]
            if wrong:
                messagebox.showwarning(tool["nazev"], f"Nástroj přijímá jen: {', '.join(exts)}\n\n"
                                       f"Nevyhovuje: {', '.join(wrong[:5])}")
                return
        try:
            cmd, cwd = build_command(tool, ctx, lambda label: simpledialog.askstring(
                tool["nazev"], f"{label}:", parent=self))
        except ToolCancelled:
            return
        except ValueError as e:
            messagebox.showerror(tool["nazev"], str(e))
            return

        self.log(f"\n▶ {tool['nazev']}\n  {subprocess.list2cmdline(cmd)}\n  (složka: {cwd})\n")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
        except OSError as e:
            self.log(f"  Nelze spustit: {e}\n")
            return
        self.proc = proc
        self.status_var.set(f"Běží: {tool['nazev']}")

        def reader():
            for line in proc.stdout:
                self.jobs.put(("log", line))
            self.jobs.put(("tool_done", (tool, proc.wait())))

        threading.Thread(target=reader, daemon=True).start()

    def finish_tool(self, tool, returncode):
        self.proc = None
        if returncode == 0:
            self.log("■ Hotovo\n")
            self.status_var.set(f"{tool['nazev']}: hotovo")
        else:
            self.log(f"■ Skončilo s chybou (návratový kód {returncode})\n")
            self.status_var.set(f"{tool['nazev']}: chyba {returncode}")
        self.reload_both()
        if returncode == 0 and tool.get("zobrazit_slozku"):
            folder = expand_path(tool["zobrazit_slozku"])
            if os.path.isdir(folder):
                self.other.load(folder)

    def stop_tool(self):
        if self.proc is not None:
            self.proc.terminate()
            self.log("  Zastavuji nástroj…\n")

    def log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def on_close(self):
        if self.proc is not None:
            if not messagebox.askyesno("Nástroj běží", "Nástroj stále běží. Ukončit ho a zavřít?"):
                return
            self.proc.terminate()
        self.destroy()


if __name__ == "__main__":
    if IS_WINDOWS:
        try:  # sharp text on high-DPI displays
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    App().mainloop()
