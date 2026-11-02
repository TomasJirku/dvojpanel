"""
Dvojpanel – dvoupanelový správce souborů pro Windows se spouštěním vlastních skriptů.
Pouze standardní knihovna Pythonu (tkinter), nic se neinstaluje.

Spuštění:  python dvojpanel.py   (nebo pythonw dvojpanel.py bez konzole)

Ovládání:
  Tab              přepnutí panelu
  Enter / dvojklik otevřít složku nebo soubor
  Backspace        o úroveň výš
  Mezerník / Insert označit položku a posunout se dolů   Ctrl+A označit vše / zrušit
  Ctrl+klik, Shift+šipky   výběr více položek
  F2 přejmenovat (přímo v řádku, také pomalý druhý klik na jméno)
  F3 otevřít       F4 upravit v Notepadu
  F5 kopírovat     F6 přesunout    F7 nová složka   F8 smazat do koše
  F9 nástroje (vlastní skripty z nastroje.json)
  Přetažení myší do druhého panelu nebo na složku = kopírovat, se Shiftem přesunout
  Ctrl+D oblíbené složky   Ctrl+S porovnat a synchronizovat složky   Ctrl+U prohodit panely
  Esc přerušit kopírování   Ctrl+R obnovit   Ctrl+Q konec
  Klik na záhlaví sloupce = řazení
"""
__version__ = "0.6.0"

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
from tkinter import ttk, messagebox, simpledialog, filedialog

IS_WINDOWS = sys.platform == "win32"
UP = ".."
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "nastroje.json"
CONFIG_EXAMPLE = APP_DIR / "nastroje.example.json"
FAVORITES_FILE = APP_DIR / "oblibene.json"
SETTINGS_FILE = APP_DIR / "dvojpanel.json"
ICON_FILE = APP_DIR / "dvojpanel.ico"
PLACEHOLDER = re.compile(r"\{(\w+)(?::([^}]*))?\}")
CHUNK = 1024 * 1024
BIG_FILE = 16 * 1024 * 1024  # files from this size up report progress in percent
MTIME_TOLERANCE = 2  # seconds; FAT and some network shares store times with 2 s precision
MARK_COLOR = "#c8102e"
DROP_COLOR = "#cfe3ff"
DRAG_THRESHOLD = 6  # pixels the mouse must travel before a press becomes a drag
RENAME_DELAY = 600  # ms; a slow second click on the name starts renaming (like Explorer)
INVALID_NAME_CHARS = '<>:"/\\|?*' if sys.platform == "win32" else "/"


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


def rename_error(folder, old, new):
    """Why `old` in `folder` cannot be renamed to `new`, or None. Never allows overwriting."""
    if not new.strip() or new in (".", ".."):
        return "Název nesmí být prázdný."
    bad = sorted({c for c in new if c in INVALID_NAME_CHARS})
    if bad:
        return f"Název nesmí obsahovat znaky: {' '.join(bad)}"
    if IS_WINDOWS and new != new.rstrip(" ."):
        return "Název nesmí končit mezerou ani tečkou."
    # a change of letter case only (a.txt -> A.txt) is the same file on Windows, not a collision
    if os.path.normcase(new) != os.path.normcase(old) and os.path.lexists(os.path.join(folder, new)):
        return f"Položka s tímto názvem už existuje:\n{new}"
    return None


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


class Cancelled(Exception):
    """User cancelled a running background operation."""


def copy_file(src, dst, progress=None, cancel=None):
    """Copy a file with metadata in chunks, calling progress(done, total) for big files.

    Writes to a temporary file first, so a failed or cancelled copy never destroys an existing target.
    """
    total = os.path.getsize(src)
    tmp = dst + ".dvojpanel-tmp"
    try:
        with open(src, "rb") as fin, open(tmp, "wb") as fout:
            done, last_pct = 0, -1
            while chunk := fin.read(CHUNK):
                if cancel is not None and cancel.is_set():
                    raise Cancelled
                fout.write(chunk)
                done += len(chunk)
                if progress and total >= BIG_FILE and done * 100 // total != last_pct:
                    last_pct = done * 100 // total
                    progress(done, total)
        shutil.copystat(src, tmp)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return dst


def files_equal(a, b, cancel=None, progress=None):
    """Byte-by-byte comparison; progress(done, total) is called for big files."""
    total = os.path.getsize(a)
    if total != os.path.getsize(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        done, last_pct = 0, -1
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled
            x, y = fa.read(CHUNK), fb.read(CHUNK)
            if x != y:
                return False
            if not x:
                return True
            done += len(x)
            if progress and total >= BIG_FILE and done * 100 // total != last_pct:
                last_pct = done * 100 // total
                progress(done, total)


def progress_copier(label, report, cancel):
    """copy_function for shutil that reports '<label>: <file> – NN %' for big files."""
    def copier(src, dst):
        name = os.path.basename(src)

        def progress(done, total):
            report(f"{label}: {name} – {done * 100 // total} % ({human_size(done)} z {human_size(total)})",
                   done * 100 / total)
        return copy_file(src, dst, progress, cancel)
    return copier


def gui_python_executable():
    """pythonw.exe of the running interpreter (no console window), falling back to the interpreter itself."""
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        alt = exe[: -len("python.exe")] + "pythonw.exe"
        if os.path.exists(alt):
            return alt
    return exe


def start_menu_folder():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def create_shortcut(folder):
    """Create Dvojpanel.lnk in folder (target pythonw.exe, so the running window groups with a pinned icon).

    Uses the WScript.Shell COM object through PowerShell, both part of Windows. Returns the .lnk path.
    """
    lnk = Path(folder) / "Dvojpanel.lnk"
    env = dict(os.environ, DP_LNK=str(lnk), DP_TARGET=gui_python_executable(),
               DP_ARGS=f'"{APP_DIR / "dvojpanel.py"}"', DP_DIR=str(APP_DIR),
               DP_ICON=str(ICON_FILE) if ICON_FILE.exists() else "")
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:DP_LNK); "
              "$s.TargetPath = $env:DP_TARGET; $s.Arguments = $env:DP_ARGS; "
              "$s.WorkingDirectory = $env:DP_DIR; $s.Description = 'Dvojpanel - správce souborů'; "
              "if ($env:DP_ICON) { $s.IconLocation = $env:DP_ICON + ',0' }; $s.Save()")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                                capture_output=True, text=True, errors="replace", timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise OSError(f"Nelze spustit PowerShell: {e}") from e
    if result.returncode != 0 or not lnk.exists():
        raise OSError(result.stderr.strip() or "PowerShell zástupce nevytvořil.")
    return lnk


def open_with_default_app(path):
    if IS_WINDOWS:
        # like Explorer: a .bat that relies on its working directory finds its files
        os.startfile(path, cwd=os.path.dirname(os.path.abspath(path)))
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------- workers (run in a thread)

def transfer_worker(sources, dest, move, overwrite, cancel, report):
    errors = []
    verb = "Přesouvám" if move else "Kopíruji"
    for i, src in enumerate(sources, 1):
        name = os.path.basename(src)
        target = os.path.join(dest, name)
        label = f"{verb} {i}/{len(sources)}"
        report(f"{label}: {name}")
        copier = progress_copier(label, report, cancel)
        try:
            if cancel.is_set():
                raise Cancelled
            exists = os.path.lexists(target)
            if exists and not overwrite:
                continue
            if exists and os.path.isdir(src) != os.path.isdir(target):
                errors.append(f"{name}: v cíli existuje položka jiného typu")
                continue
            if move and not exists:
                shutil.move(src, target, copy_function=copier)
                continue
            # copy (or overwrite-move = copy over the target, then remove the source)
            if os.path.isdir(src):
                shutil.copytree(src, target, dirs_exist_ok=True, copy_function=copier)
            else:
                copier(src, target)
            if move:
                remove_path(src)
        except Cancelled:
            errors.append("Přerušeno uživatelem.")
            break
        except OSError as e:
            errors.append(f"{name}: {e}")
    return errors


def delete_worker(paths, report):
    report(f"Mažu {len(paths)} položek…")
    send_to_recycle_bin(paths)
    return []


# ---------------------------------------------------------------- folder compare / sync

SAME, DIFFERENT, LEFT_ONLY, RIGHT_ONLY, TYPE_CONFLICT = "same", "different", "left", "right", "conflict"
TO_RIGHT, TO_LEFT, NO_ACTION = ">", "<", ""


def scan_tree(root, recursive, cancel):
    """Return ({normcase relpath: (relpath, is_dir, size, mtime)}, errors)."""
    found, errors, stack = {}, [], [""]
    while stack:
        rel_dir = stack.pop()
        if cancel.is_set():
            raise Cancelled
        try:
            with os.scandir(os.path.join(root, rel_dir)) as it:
                entries = list(it)
        except OSError as e:
            errors.append(f"{os.path.join(root, rel_dir)}: {e}")
            continue
        for entry in entries:
            rel = os.path.join(rel_dir, entry.name)
            try:
                is_dir = entry.is_dir()
                st = entry.stat()
            except OSError as e:
                errors.append(f"{entry.path}: {e}")
                continue
            found[os.path.normcase(rel)] = (rel, is_dir, 0 if is_dir else st.st_size, st.st_mtime)
            is_link = entry.is_symlink() or getattr(entry, "is_junction", lambda: False)()
            if is_dir and recursive and not is_link:
                stack.append(rel)
    return found, errors


def compare_worker(left, right, recursive, binary, cancel, report):
    """Compare two folders. Returns (rows, errors); a row is a dict with rel, status, left, right, action
    where left/right are (is_dir, size, mtime) or None."""
    report("Načítám levou složku…")
    lmap, errors = scan_tree(left, recursive, cancel)
    report("Načítám pravou složku…")
    rmap, rerrors = scan_tree(right, recursive, cancel)
    errors += rerrors

    one_sided = set()  # folders present on one side only: shown as one row, contents skipped

    def under_one_sided(key):
        parent = os.path.dirname(key)
        while parent:
            if parent in one_sided:
                return True
            parent = os.path.dirname(parent)
        return False

    keys = sorted(set(lmap) | set(rmap))
    rows = []
    for n, key in enumerate(keys, 1):
        if cancel.is_set():
            raise Cancelled
        if under_one_sided(key):
            continue
        l, r = lmap.get(key), rmap.get(key)
        rel = (l or r)[0]
        linfo, rinfo = (l[1:] if l else None), (r[1:] if r else None)
        if l and r and l[1] and r[1]:
            continue  # folder on both sides: its contents are compared item by item
        if not r or not l:
            status, action = (LEFT_ONLY, TO_RIGHT) if l else (RIGHT_ONLY, TO_LEFT)
            if (l or r)[1]:
                one_sided.add(key)
        elif l[1] != r[1]:
            status, action = TYPE_CONFLICT, NO_ACTION
        else:
            report(f"Porovnávám {n}/{len(keys)}: {rel}")
            if l[2] != r[2]:
                same = False
            elif binary:
                def progress(done, total, rel=rel, n=n):
                    report(f"Porovnávám {n}/{len(keys)}: {rel} – {done * 100 // total} %", done * 100 / total)
                try:
                    same = files_equal(os.path.join(left, l[0]), os.path.join(right, r[0]), cancel, progress)
                except OSError as e:
                    errors.append(f"{rel}: {e}")
                    continue
            else:
                same = abs(l[3] - r[3]) <= MTIME_TOLERANCE
            if same:
                status, action = SAME, NO_ACTION
            else:
                status = DIFFERENT
                if abs(l[3] - r[3]) <= MTIME_TOLERANCE:
                    action = NO_ACTION  # same time, different content: the user decides
                else:
                    action = TO_RIGHT if l[3] > r[3] else TO_LEFT
        rows.append({"rel": rel, "status": status, "left": linfo, "right": rinfo, "action": action})
    return rows, errors


def sync_worker(left, right, rows, cancel, report):
    """Copy each row in the direction of its action. Returns a list of errors."""
    todo = [r for r in rows if r["action"] in (TO_RIGHT, TO_LEFT)]
    errors = []
    for i, row in enumerate(todo, 1):
        src_root, dst_root = (left, right) if row["action"] == TO_RIGHT else (right, left)
        src, dst = os.path.join(src_root, row["rel"]), os.path.join(dst_root, row["rel"])
        label = f"Synchronizuji {i}/{len(todo)}"
        report(f"{label}: {row['rel']}")
        copier = progress_copier(label, report, cancel)
        try:
            if cancel.is_set():
                raise Cancelled
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=copier)
            else:
                copier(src, dst)
        except Cancelled:
            errors.append("Přerušeno uživatelem.")
            break
        except OSError as e:
            errors.append(f"{row['rel']}: {e}")
    return errors


# ---------------------------------------------------------------- favorites

def load_favorites():
    """Return (favorites, error_message); a favorite is a dict with 'cesta' and optional 'nazev'."""
    if not FAVORITES_FILE.exists():
        return [], None
    try:
        data = json.loads(FAVORITES_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return [], f"Chyba v oblibene.json: {e}"
    favorites = data.get("oblibene", []) if isinstance(data, dict) else []
    for i, fav in enumerate(favorites, 1):
        if not isinstance(fav, dict) or not fav.get("cesta"):
            return [], f"oblibene.json: položka č. {i} musí mít 'cesta'."
    return favorites, None


def save_favorites(favorites):
    write_json(FAVORITES_FILE, {"oblibene": favorites})


def write_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- settings (dvojpanel.json)

SETTINGS_DEFAULTS = {"levy_panel": "%USERPROFILE%", "pravy_panel": "%USERPROFILE%", "lista_oblibenych": True}


def load_settings():
    """Return (settings, error_message); missing keys and a missing file fall back to the defaults."""
    settings = dict(SETTINGS_DEFAULTS)
    if not SETTINGS_FILE.exists():
        return settings, None
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return settings, f"Chyba v dvojpanel.json: {e}"
    if not isinstance(data, dict):
        return settings, "dvojpanel.json musí obsahovat objekt { … }."
    for key in ("levy_panel", "pravy_panel"):
        if key in data and not (isinstance(data[key], str) and data[key].strip()):
            return settings, f"dvojpanel.json: '{key}' musí být cesta ke složce."
    if "lista_oblibenych" in data and not isinstance(data["lista_oblibenych"], bool):
        return settings, "dvojpanel.json: 'lista_oblibenych' musí být true nebo false."
    settings.update(data)
    return settings, None


def save_setting(key, value):
    """Change one key and keep everything else the user wrote into the file."""
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig")) if SETTINGS_FILE.exists() else {}
    except ValueError:
        data = None
    if not isinstance(data, dict):  # never overwrite a file the user has to fix by hand
        raise OSError("dvojpanel.json obsahuje chybu, oprav ho nejdřív ručně.")
    data[key] = value
    write_json(SETTINGS_FILE, data)


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


EMPTY_PLACEHOLDER = {"soubor": "Pod kurzorem v aktivním panelu není soubor.",
                     "soubor_cil": "Pod kurzorem ve druhém panelu není soubor."}


FILE_PROMPTS = {"vybrat_soubor": ("open", "Vyber soubor"), "ulozit_soubor": ("save", "Uložit jako")}


def parse_file_prompt(label, default_label, tool_exts):
    """'Popisek|.xlsx .xls' -> ('Popisek', ['.xlsx', '.xls']); without '|' the tool's 'pripony' apply."""
    text, sep, exts = (label or "").partition("|")
    exts = exts.replace(",", " ").split() if sep else list(tool_exts)
    exts = [e.lower() if e.startswith(".") else "." + e.lower() for e in exts]
    return text.strip() or default_label, exts


def build_command(tool, ctx, ask, pick=None):
    """Build (command, working_dir) for a tool.

    command is a list, or a ready command line (str) for .bat/.cmd scripts.
    ctx: soubory (list), soubor, soubor_cil, slozka, cil (str). ask(label) -> str or None.
    pick(kind, label, exts) -> path or None shows a file dialog; kind is "open" or "save".
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
            if name in FILE_PROMPTS:
                kind, default_label = FILE_PROMPTS[name]
                key = (name, label)
                if key not in answers:  # the same placeholder twice means the same file
                    if pick is None:
                        raise ValueError(f"{{{name}}} tu nelze použít.")
                    value = pick(kind, *parse_file_prompt(label, default_label, tool.get("pripony", [])))
                    if not value:
                        raise ToolCancelled
                    answers[key] = os.path.normpath(value)
                return answers[key]
            value = ctx.get(name)
            if not isinstance(value, str):
                raise ValueError(f"Neznámý zástupný symbol {{{name}}} v nástroji „{tool['nazev']}“.")
            if not value:
                raise ValueError(EMPTY_PLACEHOLDER.get(name, f"Pro {{{name}}} není nic vybráno."))
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
        cmd = [script]  # wrapped for cmd.exe below, once arguments are added
    else:
        cmd = [script]

    for arg in tool.get("argumenty", []):
        if arg == "{soubory}":
            if not ctx["soubory"]:
                raise ValueError("Nástroj potřebuje vybrané soubory, ale žádný není vybrán.")
            cmd.extend(ctx["soubory"])
        else:
            cmd.append(substitute(str(arg)))

    if suffix in (".bat", ".cmd"):
        # cmd /c strips the first and last quote when the line has more than two, which breaks
        # a quoted script path followed by quoted arguments; /s plus an outer pair keeps it intact
        cmd = f'cmd /s /c "{subprocess.list2cmdline(cmd)}"'

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
        self.anchor = None  # start of a Shift+arrow range
        self.marked = set()  # NC-style marks (Space/Insert); take precedence over the selection
        self.editor = None  # (entry, item, var) while a name is being edited in place
        self.rename_job = None  # pending slow-click rename
        self.press = None  # mouse press that may become a click, a slow click or a drag

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
        self.tree.tag_configure("marked", foreground=MARK_COLOR)  # configured later = wins over "dir"
        self.tree.tag_configure("drop", background=DROP_COLOR)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x")

        t = self.tree
        t.bind("<Return>", lambda e: self.activate_item())
        t.bind("<Double-1>", lambda e: (self.cancel_rename_timer(), self.activate_item()))
        t.bind("<Button-1>", self.on_press)
        t.bind("<B1-Motion>", self.on_motion)
        t.bind("<ButtonRelease-1>", self.on_release)
        t.bind("<MouseWheel>", lambda e: self.finish_rename(True, refocus=False))
        t.bind("<BackSpace>", lambda e: self.go_up())
        t.bind("<Tab>", lambda e: (self.app.switch_pane(), "break")[1])
        t.bind("<Control-a>", lambda e: (self.mark_all(), "break")[1])
        t.bind("<space>", lambda e: self.toggle_mark())
        t.bind("<Insert>", lambda e: self.toggle_mark())
        t.bind("<Shift-Up>", lambda e: self.extend_selection(-1))
        t.bind("<Shift-Down>", lambda e: self.extend_selection(1))
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
        if os.path.normcase(path) != os.path.normcase(self.path):
            self.marked.clear()
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
        self.finish_rename(False, refocus=False)  # the edited row is about to disappear
        self.cancel_rename_timer()
        key ={"name": lambda i: i[0].lower(), "size": lambda i: i[2], "date": lambda i: i[3]}[self.sort_col]
        dirs = sorted((i for i in self.items if i[1]), key=key, reverse=self.sort_rev)
        files = sorted((i for i in self.items if not i[1]), key=key, reverse=self.sort_rev)

        self.tree.delete(*self.tree.get_children())
        self.sizes = {}
        if os.path.dirname(self.path) != self.path:
            self.tree.insert("", "end", iid=UP, values=("[..]", "", ""))
        self.marked &= {os.path.join(self.path, i[0]) for i in self.items}  # drop vanished items
        for name, is_dir, size, mtime in dirs + files:
            iid = os.path.join(self.path, name)
            self.sizes[iid] = size
            tags = (("dir",) if is_dir else ()) + (("marked",) if iid in self.marked else ())
            self.tree.insert("", "end", iid=iid, tags=tags,
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
    def set_marked(self, item, marked):
        tags = [t for t in self.tree.item(item, "tags") if t != "marked"]
        if marked:
            self.marked.add(item)
            tags.append("marked")
        else:
            self.marked.discard(item)
        self.tree.item(item, tags=tags)

    def toggle_mark(self):
        """Space/Insert: toggle the mark under the cursor and move down (like Norton Commander)."""
        t = self.tree
        item = t.focus()
        if not item:
            return "break"
        if item != UP:
            self.set_marked(item, item not in self.marked)
        nxt = t.next(item)
        if nxt:
            t.focus(nxt)
            t.selection_set(nxt)
            t.see(nxt)
        self.update_status()
        return "break"

    def mark_all(self):
        """Ctrl+A: mark everything, or clear the marks when everything is already marked."""
        items = [i for i in self.tree.get_children() if i != UP]
        mark = not items or set(items) != self.marked
        for item in items:
            self.set_marked(item, mark)
        self.update_status()

    def clear_marks(self):
        for item in list(self.marked):
            if self.tree.exists(item):
                self.set_marked(item, False)
        self.marked.clear()
        self.update_status()

    def extend_selection(self, step):
        """Shift+Up/Down: move the cursor and select the range from the anchor (ttk has no such binding)."""
        t = self.tree
        children = t.get_children()
        focus = t.focus()
        if focus not in children:
            return "break"
        i = children.index(focus) + step
        if not 0 <= i < len(children):
            return "break"
        if self.anchor not in children or t.selection() in ((), (focus,)):
            self.anchor = focus  # a fresh range starts at the cursor
        lo, hi = sorted((children.index(self.anchor), i))
        t.selection_set([c for c in children[lo:hi + 1] if c != UP])
        t.focus(children[i])
        t.see(children[i])
        return "break"

    def cursor_file(self):
        """File under the cursor, or "" for a folder / [..] / nothing."""
        focus = self.tree.focus()
        return focus if focus and focus != UP and os.path.isfile(focus) else ""

    def selected_paths(self):
        """Marked items if there are any, otherwise the selection."""
        if self.marked:
            return [i for i in self.tree.get_children() if i in self.marked]
        return [i for i in self.tree.selection() if i != UP]

    def update_status(self):
        sel = self.selected_paths()
        total = sum(self.sizes.get(p, 0) for p in sel)
        word = "Označeno" if self.marked else "Vybráno"
        self.status_var.set(f"{word} {len(sel)} z {len(self.items)}, {human_size(total)}")

    def set_marker(self, active):
        self.marker.configure(fg="#2e9e3e" if active else "#999999")

    # -- rename in place
    def start_rename(self):
        """Put an entry over the name of the item under the cursor (F2 or a slow second click)."""
        self.rename_job = None
        t = self.tree
        item = t.focus()
        if not item or item == UP or self.editor is not None or not t.exists(item):
            return
        t.see(item)
        t.update_idletasks()
        box = t.bbox(item, "name")
        if not box:
            return
        x, y, width, height = box
        old = os.path.basename(item)
        var = tk.StringVar(value=old)
        entry = ttk.Entry(t, textvariable=var)
        entry.place(x=x, y=y, width=width, height=height)
        # like Explorer: preselect the name without the extension
        stem = len(os.path.splitext(old)[0]) if not os.path.isdir(item) else len(old)
        entry.selection_range(0, stem or len(old))
        entry.icursor(stem or len(old))
        entry.focus_set()
        entry.bind("<Return>", lambda e: (self.finish_rename(True), "break")[1])
        entry.bind("<KP_Enter>", lambda e: (self.finish_rename(True), "break")[1])
        entry.bind("<Escape>", lambda e: (self.finish_rename(False), "break")[1])
        entry.bind("<FocusOut>", lambda e: self.finish_rename(True, refocus=False))
        self.editor = (entry, item, var)

    def finish_rename(self, commit, refocus=True):
        if self.editor is None:
            return
        entry, item, var = self.editor
        self.editor = None  # first: destroying the entry or an error dialog fires FocusOut again
        new = var.get().strip()
        entry.destroy()
        if refocus:
            self.tree.focus_set()
        if commit:
            self.app.rename_item(self, item, new)

    def cancel_rename_timer(self):
        if self.rename_job is not None:
            self.after_cancel(self.rename_job)
            self.rename_job = None

    # -- mouse: slow click to rename, drag & drop between panes
    def on_press(self, event):
        t = self.tree
        self.cancel_rename_timer()
        self.finish_rename(True, refocus=False)
        self.press = None
        if t.identify_region(event.x, event.y) not in ("cell", "tree"):
            return None
        item = t.identify_row(event.y)
        if not item:
            return None
        plain = not event.state & 0x0005  # neither Shift nor Control
        self.press = {"item": item, "x": event.x_root, "y": event.y_root, "dragging": False,
                      "collapse": None,
                      # a second click on the only selected item of the focused pane, on its name
                      "slow_click": plain and item != UP and t.focus_get() is t and t.focus() == item
                                    and t.selection() == (item,) and t.identify_column(event.x) == "#1"}
        if plain and item in t.selection() and len(t.selection()) > 1:
            # keep the multi-selection so it can be dragged; a plain click collapses it on release
            self.press["collapse"] = item
            t.focus(item)
            t.focus_set()
            return "break"
        return None

    def on_motion(self, event):
        p = self.press
        if p is None or p["item"] == UP:
            return
        if not p["dragging"]:
            if max(abs(event.x_root - p["x"]), abs(event.y_root - p["y"])) < DRAG_THRESHOLD:
                return
            items = self.drag_items(p["item"])
            if not items:
                self.press = None
                return
            p["dragging"] = True
            self.app.drag_start(self, items)
        self.app.drag_motion(event)

    def on_release(self, event):
        p, self.press = self.press, None
        if p is None:
            return
        if p["dragging"]:
            self.app.drag_drop(event)
        elif p["collapse"]:
            self.tree.selection_set(p["collapse"])
        elif p["slow_click"] and self.tree.identify_row(event.y) == p["item"]:
            self.rename_job = self.after(RENAME_DELAY, self.start_rename)

    def drag_items(self, item):
        """What a drag starting on `item` carries: the marks if it is marked, otherwise the selection."""
        if item in self.marked:
            return [i for i in self.tree.get_children() if i in self.marked]
        selection = [i for i in self.tree.selection() if i != UP]
        return selection if item in selection else [item]

    def show_drop_row(self, row):
        """Highlight the folder row a drop would go into (None = no highlight)."""
        for item in self.tree.tag_has("drop"):
            self.tree.item(item, tags=[t for t in self.tree.item(item, "tags") if t != "drop"])
        if row is not None and self.tree.exists(row):
            self.tree.item(row, tags=list(self.tree.item(row, "tags")) + ["drop"])


# ---------------------------------------------------------------- compare / sync window

class SyncWindow(tk.Toplevel):
    STATUS_TEXT = {SAME: "stejné", DIFFERENT: "liší se", LEFT_ONLY: "jen vlevo", RIGHT_ONLY: "jen vpravo",
                   TYPE_CONFLICT: "soubor × složka"}
    ACTION_TEXT = {TO_RIGHT: "→", TO_LEFT: "←", NO_ACTION: ""}

    def __init__(self, app, left, right):
        super().__init__(app)
        self.app = app
        self.title("Porovnat a synchronizovat složky")
        self.geometry("1050x620")
        self.rows = []
        self.compared = None  # (left, right) the rows belong to
        self.running = False
        self.cancel = threading.Event()

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.left_var, self.right_var = tk.StringVar(), tk.StringVar()
        for r, (label, var) in enumerate((("Levá:", self.left_var), ("Pravá:", self.right_var))):
            ttk.Label(top, text=label).grid(row=r, column=0, sticky="w", padx=(0, 4))
            ttk.Entry(top, textvariable=var).grid(row=r, column=1, sticky="ew", pady=1)
        top.columnconfigure(1, weight=1)

        opts = ttk.Frame(self, padding=(6, 0))
        opts.pack(fill="x")
        self.recursive = tk.BooleanVar(value=True)
        self.binary = tk.BooleanVar(value=True)
        self.show_same = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Včetně podsložek", variable=self.recursive).pack(side="left")
        ttk.Checkbutton(opts, text="Porovnat obsah binárně (jinak jen velikost a čas)",
                        variable=self.binary).pack(side="left", padx=10)
        ttk.Checkbutton(opts, text="Zobrazit stejné", variable=self.show_same,
                        command=self.refresh).pack(side="left")
        self.compare_btn = ttk.Button(opts, text="Porovnat", command=self.compare)
        self.compare_btn.pack(side="right")

        body = ttk.Frame(self, padding=6)
        body.pack(fill="both", expand=True)
        cols = (("rel", "Cesta", 330, "w", True), ("lsize", "Vlevo", 90, "e", False),
                ("ldate", "Změněno vlevo", 125, "center", False), ("action", "Akce", 50, "center", False),
                ("rsize", "Vpravo", 90, "e", False), ("rdate", "Změněno vpravo", 125, "center", False),
                ("status", "Stav", 110, "w", False))
        self.tree = ttk.Treeview(body, columns=[c[0] for c in cols], show="headings", selectmode="extended")
        for col, title, width, anchor, stretch in cols:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
        for status, color in ((LEFT_ONLY, "#0b4ea2"), (RIGHT_ONLY, "#2e7d32"), (DIFFERENT, MARK_COLOR),
                              (TYPE_CONFLICT, "#b26a00"), (SAME, "#888888")):
            self.tree.tag_configure(status, foreground=color)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Right>", lambda e: self.set_action(TO_RIGHT))
        self.tree.bind("<Left>", lambda e: self.set_action(TO_LEFT))
        self.tree.bind("<space>", lambda e: self.set_action(NO_ACTION))

        actions = ttk.Frame(self, padding=(6, 0))
        actions.pack(fill="x")
        ttk.Button(actions, text="→ Kopírovat doprava (→)",
                   command=lambda: self.set_action(TO_RIGHT)).pack(side="left")
        ttk.Button(actions, text="← Kopírovat doleva (←)",
                   command=lambda: self.set_action(TO_LEFT)).pack(side="left", padx=4)
        ttk.Button(actions, text="Nic nedělat (mezerník)",
                   command=lambda: self.set_action(NO_ACTION)).pack(side="left")
        self.summary_var = tk.StringVar()
        ttk.Label(actions, textvariable=self.summary_var).pack(side="left", padx=10)

        bottom = ttk.Frame(self, padding=6)
        bottom.pack(fill="x")
        self.progress_var = tk.StringVar(value="Zvol složky a stiskni Porovnat.")
        ttk.Label(bottom, textvariable=self.progress_var, anchor="w").pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Zavřít", command=self.close).pack(side="right")
        self.cancel_btn = ttk.Button(bottom, text="Přerušit", command=self.cancel.set, state="disabled")
        self.cancel_btn.pack(side="right", padx=4)
        self.sync_btn = ttk.Button(bottom, text="Synchronizovat", command=self.sync, state="disabled")
        self.sync_btn.pack(side="right")
        self.progress = ttk.Progressbar(bottom, length=200, maximum=100)
        self.progress.pack(side="right", padx=8)

        self.bind("<Escape>", lambda e: self.cancel.set())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.set_paths(left, right)
        self.compare_btn.focus_set()

    def set_paths(self, left, right):
        if not self.running:
            self.left_var.set(left)
            self.right_var.set(right)

    def set_buttons(self):
        self.compare_btn["state"] = "disabled" if self.running else "normal"
        self.cancel_btn["state"] = "normal" if self.running else "disabled"
        has_work = any(r["action"] for r in self.rows)
        self.sync_btn["state"] = "normal" if has_work and not self.running else "disabled"

    # -- background work (results come back through app.jobs)
    def start(self, func, *args, on_done):
        self.running = True
        self.app.busy = True
        self.cancel.clear()
        self.set_buttons()

        def report(text, percent=None):
            self.app.jobs.put(("call", (self.show_progress, (text, percent))))

        def runner():
            try:
                result, error = func(*args, self.cancel, report), None
            except Cancelled:
                result, error = None, "Přerušeno uživatelem."
            except Exception as e:  # noqa: BLE001 – show anything to the user
                result, error = None, str(e)
            self.app.jobs.put(("call", (self.job_done, (on_done, result, error))))

        threading.Thread(target=runner, daemon=True).start()

    def show_progress(self, text, percent):
        if self.winfo_exists():
            self.progress_var.set(text)
            self.progress["value"] = percent or 0

    def job_done(self, on_done, result, error):
        self.app.busy = False
        self.running = False
        if not self.winfo_exists():
            self.app.reload_both()
            return
        self.progress["value"] = 0
        self.set_buttons()
        if error:
            self.progress_var.set(error)
            messagebox.showerror("Porovnání složek", error, parent=self)
            return
        on_done(result)

    def show_errors(self, errors):
        if errors:
            extra = f"\n… a dalších {len(errors) - 15}" if len(errors) > 15 else ""
            messagebox.showerror("Chyby", "\n".join(errors[:15]) + extra, parent=self)

    # -- compare
    def compare(self):
        if self.running or self.app.is_busy():
            return
        left, right = (os.path.abspath(os.path.expandvars(v.get().strip())) for v in (self.left_var, self.right_var))
        for path in (left, right):
            if not os.path.isdir(path):
                messagebox.showerror("Porovnání složek", f"Složka neexistuje:\n{path}", parent=self)
                return
        if is_inside(left, right) or is_inside(right, left):
            messagebox.showwarning("Porovnání složek", "Složky jsou stejné nebo jedna leží uvnitř druhé.",
                                   parent=self)
            return
        self.rows, self.compared = [], None
        self.refresh()
        self.start(compare_worker, left, right, self.recursive.get(), self.binary.get(),
                   on_done=lambda result: self.compared_done(left, right, *result))

    def compared_done(self, left, right, rows, errors):
        self.rows, self.compared = rows, (left, right)
        self.refresh()
        self.set_buttons()
        self.progress_var.set(f"Porovnáno, položek: {len(rows)}" + (f", chyb: {len(errors)}" if errors else ""))
        self.show_errors(errors)

    def refresh(self):
        def fmt(info):
            if info is None:
                return "", ""
            is_dir, size, mtime = info
            return ("<DIR>" if is_dir else human_size(size)), fmt_time(mtime)

        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self.rows):
            if row["status"] == SAME and not self.show_same.get():
                continue
            is_dir = (row["left"] or row["right"])[0]
            self.tree.insert("", "end", iid=str(i), tags=(row["status"],), values=(
                row["rel"] + ("\\" if is_dir else ""), *fmt(row["left"]), self.ACTION_TEXT[row["action"]],
                *fmt(row["right"]), self.STATUS_TEXT[row["status"]]))
        self.update_summary()

    def update_summary(self):
        def count(action):
            items = [r for r in self.rows if r["action"] == action]
            src = "left" if action == TO_RIGHT else "right"
            return len(items), sum(r[src][1] for r in items)

        (nr, br), (nl, bl) = count(TO_RIGHT), count(TO_LEFT)
        undecided = sum(1 for r in self.rows if r["status"] == DIFFERENT and not r["action"])
        conflicts = sum(1 for r in self.rows if r["status"] == TYPE_CONFLICT)
        same = sum(1 for r in self.rows if r["status"] == SAME)
        self.summary_var.set(f"Doprava: {nr} ({human_size(br)})   Doleva: {nl} ({human_size(bl)})   "
                             f"Bez akce: {undecided}   Konflikty: {conflicts}   Stejné: {same}")

    def set_action(self, action):
        for iid in self.tree.selection():
            row = self.rows[int(iid)]
            if row["status"] in (SAME, TYPE_CONFLICT):
                continue
            if (action == TO_RIGHT and row["left"] is None) or (action == TO_LEFT and row["right"] is None):
                continue  # nothing to copy from that side
            row["action"] = action
            self.tree.set(iid, "action", self.ACTION_TEXT[action])
        self.update_summary()
        self.set_buttons()
        return "break"

    # -- sync
    def sync(self):
        todo = [r for r in self.rows if r["action"]]
        if self.running or not todo or self.app.is_busy():
            return
        left, right = self.compared
        n_right = sum(1 for r in todo if r["action"] == TO_RIGHT)
        overwritten = [r["rel"] for r in todo if r["right" if r["action"] == TO_RIGHT else "left"] is not None]
        msg = f"Zkopírovat {n_right} položek doprava a {len(todo) - n_right} doleva?\n\n{left}\n⇄ {right}"
        if overwritten:
            listing = "\n".join(overwritten[:10]) + (f"\n… a dalších {len(overwritten) - 10}"
                                                     if len(overwritten) > 10 else "")
            msg += (f"\n\nPŘEPÍŠE se {len(overwritten)} existujících souborů, jejich dosavadní obsah "
                    f"se ztratí:\n{listing}")
        if not messagebox.askokcancel("Synchronizovat", msg, icon="warning", parent=self):
            return
        self.start(sync_worker, left, right, todo, on_done=self.synced)

    def synced(self, errors):
        self.app.reload_both()
        self.show_errors(errors)
        left, right = self.compared
        self.left_var.set(left)
        self.right_var.set(right)
        self.compare()  # show the new state

    def close(self):
        if self.running:
            self.cancel.set()
        self.destroy()


# ---------------------------------------------------------------- main window

class FavoritesBar(ttk.Frame):
    """Buttons for favorite folders; they wrap to more rows when the window is narrow."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.buttons = []
        self.rows = []
        self.width = 0
        self.bind("<Configure>", lambda e: self.layout(e.width) if e.width != self.width else None)

    def fill(self, favorites):
        for b in self.buttons:
            b.destroy()
        self.buttons = []
        for fav in favorites:
            b = ttk.Button(self, text="★ " + (fav.get("nazev") or fav["cesta"]), style="Toolbutton",
                           takefocus=False, command=lambda f=fav: self.app.open_favorite(f))
            b.bind("<Button-3>", lambda e, f=fav: self.app.favorite_context_menu(e, f))
            self.buttons.append(b)
        self.buttons.append(ttk.Button(self, text="+ Přidat", style="Toolbutton", takefocus=False,
                                       command=self.app.add_favorite))
        self.layout(self.winfo_width())

    def layout(self, width):
        if width <= 1:  # not mapped yet
            width = max(self.app.winfo_width(), 800)
        self.width = width
        for row in self.rows:
            row.destroy()
        self.rows = []
        used = 0
        for b in self.buttons:
            w = b.winfo_reqwidth()
            if not self.rows or (used and used + w > width):
                self.rows.append(ttk.Frame(self))
                self.rows[-1].pack(fill="x")
                used = 0
            b.pack(in_=self.rows[-1], side="left")
            b.lift()  # the row frames were created later and would cover the buttons
            used += w


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Dvojpanel {__version__}")
        self.geometry("1150x760")
        if IS_WINDOWS and ICON_FILE.exists():
            try:
                self.iconbitmap(default=str(ICON_FILE))  # default= also applies to dialogs
            except tk.TclError:
                pass
        self.busy = False
        self.proc = None
        self.tools, self.tools_error = [], None
        self.favorites, self.favorites_error = [], None
        self.jobs = queue.Queue()
        self.cancel = threading.Event()
        self.cancellable = False
        self.job_pane = None
        self.sync_window = None
        self.settings, self.settings_error = load_settings()
        self.drag = None  # {"pane", "items", "target"} while items are dragged with the mouse
        self.last_dirs = {}  # (tool, label) -> folder last used in a {vybrat_soubor}/{ulozit_soubor} dialog

        self.fav_bar = FavoritesBar(self, self)
        self.fav_bar_var = tk.BooleanVar(value=True)
        main = ttk.PanedWindow(self, orient="vertical")
        main.pack(fill="both", expand=True, padx=4, pady=4)
        self.main = main
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

        status = ttk.Frame(self)
        status.pack(fill="x", padx=4)
        self.status_var = tk.StringVar(value="Připraveno")
        ttk.Label(status, textvariable=self.status_var, anchor="w", relief="sunken").pack(
            side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(status, length=220, maximum=100)  # packed only while in use

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
        self.bind("<Control-d>", lambda e: self.show_favorites_popup())
        self.bind("<Control-s>", lambda e: self.open_sync())
        self.bind("<Control-u>", lambda e: self.swap_panes())
        self.bind("<Escape>", lambda e: self.drag_cancel() if self.drag else self.cancel_job())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_menu()

        home = os.path.expanduser("~")
        self.left.load(home)
        self.right.load(home)
        self.set_active(self.left)
        self.left.tree.focus_set()
        if self.settings_error:
            self.log(f"⚠ {self.settings_error}\n")
        else:
            self.open_start_folders()
        self.after(100, self.poll_jobs)

    # -- settings (dvojpanel.json)
    def open_start_folders(self):
        """Start folders from dvojpanel.json; checked in a thread like favorites (network shares)."""
        for pane, key in ((self.left, "levy_panel"), (self.right, "pravy_panel")):
            path = expand_path(self.settings[key])
            if os.path.normcase(path) != os.path.normcase(pane.path):
                self.open_folder(pane, path, f"Výchozí složka ({key}) není dostupná")

    def edit_settings(self):
        if not SETTINGS_FILE.exists():
            try:
                write_json(SETTINGS_FILE, SETTINGS_DEFAULTS)
            except OSError as e:
                messagebox.showerror("Nastavení", f"Nelze vytvořit dvojpanel.json:\n{e}")
                return
        subprocess.Popen(["notepad.exe" if IS_WINDOWS else "xdg-open", str(SETTINGS_FILE)])

    def save_start_folders(self):
        if not messagebox.askyesno("Výchozí složky", "Při spuštění otevírat tyto složky?\n\n"
                                   f"Levý panel: {self.left.path}\nPravý panel: {self.right.path}"):
            return
        try:
            save_setting("levy_panel", self.left.path)
            save_setting("pravy_panel", self.right.path)
        except OSError as e:
            messagebox.showerror("Nastavení", f"Nelze uložit dvojpanel.json:\n{e}")
            return
        self.settings.update(levy_panel=self.left.path, pravy_panel=self.right.path)
        self.status_var.set("Výchozí složky uloženy do dvojpanel.json")

    def reload_settings(self):
        self.settings, self.settings_error = load_settings()
        if self.settings_error:
            messagebox.showerror("Nastavení", self.settings_error)
            return
        self.show_favorites_bar(self.settings["lista_oblibenych"])
        self.open_start_folders()
        self.status_var.set("Nastavení načteno")

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

    def swap_panes(self):
        """Ctrl+U: the left pane gets the right folder and vice versa; the active side stays."""
        left, right = self.left, self.right
        if os.path.normcase(left.path) == os.path.normcase(right.path):
            return
        focus = [os.path.basename(f) if (f := p.tree.focus()) and f != UP else None for p in (left, right)]
        lpath, rpath = left.path, right.path
        left.load(rpath, focus[1])
        right.load(lpath, focus[0])
        self.active.tree.focus_set()

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
        pane.start_rename()

    def rename_item(self, pane, item, new):
        """Finish an in-place rename; never overwrites an existing item."""
        old, folder = os.path.basename(item), os.path.dirname(item)
        if new == old or self.is_busy():
            return
        error = rename_error(folder, old, new)
        if error:
            messagebox.showerror("Přejmenovat", error)
            return
        try:
            os.rename(item, os.path.join(folder, new))
        except OSError as e:
            messagebox.showerror("Přejmenovat", str(e))
            return
        if os.path.normcase(pane.path) == os.path.normcase(folder):
            pane.load(pane.path, focus_name=new)
        other = self.right if pane is self.left else self.left
        if os.path.normcase(other.path) == os.path.normcase(folder):
            other.reload()

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

    def transfer(self, move, sources=None, dest=None, src_pane=None):
        """F5/F6 (selection of the active pane into the other one) or a mouse drop (explicit items)."""
        if self.is_busy():
            return
        if sources is None:
            src_pane, dest = self.active, self.other.path
            sources = src_pane.selected_paths()
        if not sources:
            return
        if any(os.path.normcase(os.path.dirname(s)) == os.path.normcase(dest) for s in sources):
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
        self.job_pane = src_pane
        self.run_job(transfer_worker, sources, dest, move, overwrite, self.cancel, cancellable=True)

    # -- drag & drop between panes (and onto folders), only inside the program
    def drag_start(self, pane, items):
        self.drag = {"pane": pane, "items": items, "target": None}
        for p in (self.left, self.right):
            p.tree.configure(cursor="plus")

    def drop_target(self, x_root, y_root):
        """(pane, highlighted row or None, destination folder) under the pointer, or None."""
        drag = self.drag
        widget = self.winfo_containing(x_root, y_root)
        if widget is None:
            return None
        name = str(widget)
        for pane in (self.left, self.right):
            if name != str(pane) and not name.startswith(str(pane) + "."):
                continue
            row, dest = None, pane.path  # onto a file, onto itself or below the list = the pane's folder
            if widget is pane.tree:
                hit = pane.tree.identify_row(y_root - pane.tree.winfo_rooty())
                if hit == UP:
                    row, dest = UP, os.path.dirname(pane.path)
                elif hit and hit not in drag["items"] and os.path.isdir(hit):
                    row, dest = hit, hit
            if pane is drag["pane"] and row is None:
                return None  # dropping into the folder it came from does nothing
            return pane, row, dest
        return None

    def drag_motion(self, event):
        if self.drag is None:
            return
        target = self.drop_target(event.x_root, event.y_root)
        old = self.drag["target"]
        if old and (not target or old[:2] != target[:2]):
            old[0].show_drop_row(None)
        if target and (not old or old[:2] != target[:2]):
            target[0].show_drop_row(target[1])
        self.drag["target"] = target
        n = len(self.drag["items"])
        if target:
            verb = "Přesunout" if event.state & 0x0001 else "Kopírovat"
            self.status_var.set(f"{verb} {n} položek do: {target[2]}   (Shift = přesunout, Esc = zrušit)")
        else:
            self.status_var.set(f"Přetažení {n} položek: pusť nad druhým panelem nebo nad složkou")
        cursor = "plus" if target else "no"
        for p in (self.left, self.right):
            p.tree.configure(cursor=cursor)

    def drag_end(self):
        drag, self.drag = self.drag, None
        for p in (self.left, self.right):
            p.tree.configure(cursor="")
            p.show_drop_row(None)
        self.status_var.set("Připraveno")
        return drag

    def drag_cancel(self):
        self.drag_end()

    def drag_drop(self, event):
        if self.drag is None:  # cancelled with Esc
            return
        target = self.drop_target(event.x_root, event.y_root)
        drag = self.drag_end()
        if target:
            self.transfer(bool(event.state & 0x0001), drag["items"], target[2], drag["pane"])

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
    def run_job(self, func, *args, cancellable=False):
        self.busy = True
        self.cancellable = cancellable
        self.cancel.clear()

        def report(text, percent=None):
            self.jobs.put(("progress", (text, percent)))

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
                    self.show_progress(*data)
                elif kind == "call":  # run a callback from a worker thread in the GUI thread
                    func, args = data
                    func(*args)
                elif kind == "log":
                    self.log(data)
                elif kind == "done":
                    self.finish_job(data)
                elif kind == "tool_done":
                    self.finish_tool(*data)
        except queue.Empty:
            pass
        self.after(100, self.poll_jobs)

    def show_progress(self, text, percent=None):
        if self.busy and self.cancellable and not self.cancel.is_set():
            text += "   (Esc = přerušit)"
        self.status_var.set(text)
        if percent is None:
            return
        if not self.progress.winfo_ismapped():
            self.progress.pack(side="right", padx=(4, 0))
        self.progress["value"] = percent

    def hide_progress(self):
        self.progress["value"] = 0
        self.progress.pack_forget()

    def cancel_job(self):
        if self.busy and self.cancellable and not self.cancel.is_set():
            self.cancel.set()
            self.status_var.set("Přerušuji…")

    def finish_job(self, errors):
        self.busy = False
        self.hide_progress()
        self.status_var.set(f"Hotovo, chyb: {len(errors)}" if errors else "Hotovo")
        if not errors and self.job_pane is not None:
            self.job_pane.clear_marks()  # like NC: marks go away after a successful operation
        self.job_pane = None
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
        file_menu.add_command(label="Uložit aktuální složky jako výchozí…", command=self.save_start_folders)
        file_menu.add_command(label="Upravit dvojpanel.json", command=self.edit_settings)
        file_menu.add_command(label="Načíst nastavení znovu", command=self.reload_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Vytvořit zástupce v nabídce Start…", command=self.make_shortcut)
        file_menu.add_separator()
        file_menu.add_command(label="Konec", accelerator="Ctrl+Q", command=self.on_close)
        menubar.add_cascade(label="Soubor", menu=file_menu)
        cmd_menu = tk.Menu(menubar, tearoff=False)
        cmd_menu.add_command(label="Porovnat a synchronizovat složky…", accelerator="Ctrl+S",
                             command=self.open_sync)
        cmd_menu.add_command(label="Prohodit panely", accelerator="Ctrl+U", command=self.swap_panes)
        menubar.add_cascade(label="Příkazy", menu=cmd_menu)
        self.favorites_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Oblíbené", menu=self.favorites_menu)
        self.tools_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Nástroje", menu=self.tools_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="O programu", command=lambda: messagebox.showinfo(
            "O programu", f"Dvojpanel {__version__}\nPython {sys.version.split()[0]}"))
        menubar.add_cascade(label="Nápověda", menu=help_menu)
        self.configure(menu=menubar)
        self.reload_tools(startup=True)
        self.reload_favorites(startup=True)

    def make_shortcut(self):
        if not IS_WINDOWS:
            messagebox.showinfo("Zástupce", "Zástupce lze vytvořit jen ve Windows.")
            return
        try:
            lnk = create_shortcut(start_menu_folder())
        except OSError as e:
            messagebox.showerror("Zástupce", f"Zástupce se nepodařilo vytvořit:\n{e}\n\n"
                                 "Ručně: pravým tlačítkem na plochu → Nový → Zástupce, umístění:\n"
                                 f"\"{gui_python_executable()}\" \"{APP_DIR / 'dvojpanel.py'}\"")
            return
        messagebox.showinfo("Zástupce", f"Zástupce vytvořen:\n{lnk}\n\n"
                            "Připnutí na hlavní panel: Start → napiš „Dvojpanel“ → pravým tlačítkem → "
                            "Připnout na hlavní panel.\n\n"
                            "Po aktualizaci Pythonu nebo přesunu složky programu zástupce vytvoř znovu.")

    # -- favorites
    def fill_favorites_menu(self, menu):
        menu.delete(0, "end")
        if self.favorites:
            for fav in self.favorites:
                menu.add_command(label=fav.get("nazev") or fav["cesta"],
                                 command=lambda f=fav: self.open_favorite(f))
        else:
            menu.add_command(label=self.favorites_error or "Žádné oblíbené složky", state="disabled")
        menu.add_separator()
        menu.add_command(label="Přidat aktuální složku…", command=self.add_favorite)
        remove_menu = tk.Menu(menu, tearoff=False)
        for fav in self.favorites:
            remove_menu.add_command(label=fav.get("nazev") or fav["cesta"],
                                    command=lambda f=fav: self.remove_favorite(f))
        menu.add_cascade(label="Odebrat", menu=remove_menu, state="normal" if self.favorites else "disabled")
        menu.add_command(label="Upravit oblibene.json", command=self.edit_favorites)
        menu.add_command(label="Načíst oblíbené znovu", command=self.reload_favorites)
        menu.add_separator()
        menu.add_checkbutton(label="Zobrazit lištu oblíbených", variable=self.fav_bar_var,
                             command=self.toggle_favorites_bar)

    def show_favorites_bar(self, visible):
        self.fav_bar_var.set(visible)
        if visible and not self.fav_bar.winfo_manager():
            self.fav_bar.pack(fill="x", padx=4, pady=(4, 0), before=self.main)
        elif not visible:
            self.fav_bar.pack_forget()

    def toggle_favorites_bar(self):
        visible = self.fav_bar_var.get()
        try:
            save_setting("lista_oblibenych", visible)
        except OSError as e:
            messagebox.showerror("Nastavení", f"Nelze uložit dvojpanel.json:\n{e}")
        self.settings["lista_oblibenych"] = visible
        self.show_favorites_bar(visible)

    def favorite_context_menu(self, event, fav):
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Otevřít v aktivním panelu", command=lambda: self.open_favorite(fav))
        menu.add_command(label="Otevřít ve druhém panelu", command=lambda: self.open_favorite(fav, self.other))
        menu.add_separator()
        menu.add_command(label="Odebrat z oblíbených…", command=lambda: self.remove_favorite(fav))
        menu.tk_popup(event.x_root, event.y_root)

    def reload_favorites(self, startup=False):
        self.favorites, self.favorites_error = load_favorites()
        self.fill_favorites_menu(self.favorites_menu)
        self.fav_bar.fill(self.favorites)
        self.show_favorites_bar(self.settings["lista_oblibenych"])
        if self.favorites_error:
            self.log(f"⚠ {self.favorites_error}\n")
            if not startup:
                messagebox.showerror("Oblíbené", self.favorites_error)
        elif not startup:
            self.status_var.set(f"Načteno oblíbených: {len(self.favorites)}")

    def show_favorites_popup(self):
        menu = tk.Menu(self, tearoff=False)
        self.fill_favorites_menu(menu)
        tree = self.active.tree
        menu.tk_popup(tree.winfo_rootx() + 40, tree.winfo_rooty() + 40)

    def open_favorite(self, fav, pane=None):
        self.open_folder(pane or self.active, expand_path(fav["cesta"]), "Složka není dostupná")

    def open_folder(self, pane, path, error):
        """Check the folder in a thread first: an unreachable network share can block for many seconds."""
        self.status_var.set(f"Otevírám {path}…")

        def check():
            ok = os.path.isdir(path)
            self.jobs.put(("call", (self.folder_checked, (pane, path, ok, error))))

        threading.Thread(target=check, daemon=True).start()

    def folder_checked(self, pane, path, ok, error):
        if not ok:
            self.status_var.set("Připraveno")
            messagebox.showerror("Dvojpanel", f"{error}:\n{path}")
            return
        pane.load(path)
        self.status_var.set("Připraveno")
        if pane is self.active:
            pane.tree.focus_set()

    def add_favorite(self):
        favorites, error = load_favorites()
        if error:  # never overwrite a file the user has to fix by hand
            messagebox.showerror("Oblíbené", error)
            return
        path = self.active.path
        if any(os.path.normcase(expand_path(f["cesta"])) == os.path.normcase(path) for f in favorites):
            messagebox.showinfo("Oblíbené", f"Složka už v oblíbených je:\n{path}")
            return
        name = simpledialog.askstring("Přidat do oblíbených", "Název:",
                                      initialvalue=os.path.basename(path) or path, parent=self)
        if name is None:
            return
        favorites.append({"nazev": name.strip() or path, "cesta": path})
        self.store_favorites(favorites)

    def remove_favorite(self, fav):
        favorites, error = load_favorites()
        if error:
            messagebox.showerror("Oblíbené", error)
            return
        if fav not in favorites:
            self.reload_favorites()
            return
        if messagebox.askyesno("Oblíbené", f"Odebrat z oblíbených?\n{fav.get('nazev') or fav['cesta']}"):
            favorites.remove(fav)
            self.store_favorites(favorites)

    def store_favorites(self, favorites):
        try:
            save_favorites(favorites)
        except OSError as e:
            messagebox.showerror("Oblíbené", f"Nelze uložit oblibene.json:\n{e}")
        self.reload_favorites(startup=True)

    def edit_favorites(self):
        if not FAVORITES_FILE.exists():
            try:
                save_favorites([])
            except OSError as e:
                messagebox.showerror("Oblíbené", f"Nelze vytvořit oblibene.json:\n{e}")
                return
        subprocess.Popen(["notepad.exe" if IS_WINDOWS else "xdg-open", str(FAVORITES_FILE)])

    # -- folder compare / sync
    def open_sync(self):
        if self.sync_window is not None and self.sync_window.winfo_exists():
            self.sync_window.set_paths(self.left.path, self.right.path)
            self.sync_window.deiconify()
            self.sync_window.lift()
            return
        self.sync_window = SyncWindow(self, self.left.path, self.right.path)

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
        ctx = {"soubory": files,
               "soubor": pane.cursor_file(),
               "soubor_cil": self.other.cursor_file(),
               "slozka": pane.path,
               "cil": self.other.path}

        exts = [e.lower() for e in tool.get("pripony", [])]
        args = " ".join(str(a) for a in tool.get("argumenty", []))
        if exts:
            # the selection only matters to tools that take files from the panes, not to file dialogs
            uses_panes = "{soubor" in args or not any(f"{{{name}" in args for name in FILE_PROMPTS)
            checked = list(files) if uses_panes else []
            if ctx["soubor_cil"] and "{soubor_cil}" in args:
                checked.append(ctx["soubor_cil"])
            wrong = [os.path.basename(f) for f in checked if os.path.splitext(f)[1].lower() not in exts]
            if wrong:
                messagebox.showwarning(tool["nazev"], f"Nástroj přijímá jen: {', '.join(exts)}\n\n"
                                       f"Nevyhovuje: {', '.join(wrong[:5])}")
                return
        try:
            cmd, cwd = build_command(tool, ctx, lambda label: simpledialog.askstring(
                tool["nazev"], f"{label}:", parent=self),
                lambda kind, label, exts: self.pick_file(tool, kind, label, exts))
        except ToolCancelled:
            return
        except ValueError as e:
            messagebox.showerror(tool["nazev"], str(e))
            return

        line = cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd)
        self.log(f"\n▶ {tool['nazev']}\n  {line}\n  (složka: {cwd})\n")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", DVOJPANEL=__version__)
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

    def pick_file(self, tool, kind, label, exts):
        """File dialog for {vybrat_soubor} / {ulozit_soubor}; starts where this prompt was last used."""
        key = (tool["nazev"], label)
        folder = self.last_dirs.get(key)
        if not folder or not os.path.isdir(folder):
            folder = self.active.path
        types = [(f"{label} ({' '.join(exts)})", " ".join("*" + e for e in exts))] if exts else []
        types.append(("Všechny soubory", "*.*"))
        options = dict(parent=self, title=f"{tool['nazev']}: {label}", initialdir=folder, filetypes=types)
        if kind == "open":
            path = filedialog.askopenfilename(**options)
        else:
            path = filedialog.asksaveasfilename(defaultextension=exts[0] if exts else "", **options)
        if not path:
            return None
        path = os.path.normpath(path)
        if exts and os.path.splitext(path)[1].lower() not in exts:
            messagebox.showwarning(tool["nazev"], f"{label}: nástroj přijímá jen {', '.join(exts)}\n\n"
                                   f"Nevyhovuje: {os.path.basename(path)}")
            return None
        self.last_dirs[key] = os.path.dirname(path)
        return path

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
