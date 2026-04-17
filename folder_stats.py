"""Folder Stats Viewer.

A Tkinter GUI that lists a folder's direct children with stats (size,
modified time, extension, item count), supports click-to-sort columns,
and provides filters over the scanned data.

Run:  python3 folder_stats.py
"""

import os
import sys
from datetime import datetime
from tkinter import Tk, StringVar, filedialog, messagebox
from tkinter import ttk


SIZE_UNITS = [("B", 1), ("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)]

COLUMNS = ("name", "type", "size", "items", "modified", "extension")
COLUMN_LABELS = {
    "name": "Name",
    "type": "Type",
    "size": "Size",
    "items": "Items",
    "modified": "Modified",
    "extension": "Extension",
}


def human_size(num_bytes):
    if num_bytes is None:
        return "N/A"
    size = float(num_bytes)
    for unit, factor in reversed(SIZE_UNITS):
        if size >= factor or unit == "B":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size / factor:.2f} {unit}"
    return f"{int(size)} B"


def parse_size(value, unit):
    """Return bytes from a (numeric-string, unit-label) pair, or None if blank/invalid."""
    value = value.strip()
    if not value:
        return None
    try:
        num = float(value)
    except ValueError:
        return None
    for u, factor in SIZE_UNITS:
        if u == unit:
            return int(num * factor)
    return None


def folder_total_size(path):
    """Recursively total the size of files beneath `path`. Symlinks not followed."""
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                total += os.path.getsize(fpath)
            except OSError:
                continue
    return total


def scan_folder(path):
    """Return (entries, summary). Entries: list of dicts, one per direct child."""
    entries = []
    total_size = 0
    file_count = 0
    folder_count = 0

    try:
        with os.scandir(path) as it:
            children = list(it)
    except (PermissionError, FileNotFoundError, OSError) as e:
        raise RuntimeError(f"Cannot read folder: {e}") from e

    for entry in children:
        is_dir = False
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
        except OSError:
            is_dir = False

        try:
            stat_res = entry.stat(follow_symlinks=False)
            mtime = datetime.fromtimestamp(stat_res.st_mtime)
        except OSError:
            mtime = None

        if is_dir:
            folder_count += 1
            try:
                size = folder_total_size(entry.path)
            except OSError:
                size = None
            try:
                with os.scandir(entry.path) as sub:
                    items = sum(1 for _ in sub)
            except OSError:
                items = None
            ext = ""
            row_type = "Folder"
        else:
            file_count += 1
            try:
                size = stat_res.st_size if mtime is not None else None
            except OSError:
                size = None
            items = None
            ext = os.path.splitext(entry.name)[1].lower().lstrip(".")
            row_type = "File"

        if size is not None:
            total_size += size

        entries.append({
            "name": entry.name,
            "type": row_type,
            "size": size,
            "items": items,
            "modified": mtime,
            "extension": ext,
            "path": entry.path,
            "is_dir": is_dir,
        })

    summary = {
        "total_size": total_size,
        "file_count": file_count,
        "folder_count": folder_count,
        "entry_count": len(entries),
    }
    return entries, summary


class FolderStatsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Folder Stats Viewer")
        self.root.geometry("1000x620")

        self.current_path = None
        self.entries = []           # full scanned list
        self.visible_entries = []   # after filter + sort, in row order
        self.sort_state = ("name", True)  # (column, ascending)

        self._build_toolbar()
        self._build_filter_bar()
        self._build_table()
        self._build_status_bar()

    # -- UI construction -------------------------------------------------

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(8, 6))
        bar.pack(fill="x")

        ttk.Button(bar, text="Browse…", command=self.on_browse).pack(side="left")
        ttk.Button(bar, text="Up", command=self.on_up).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Refresh", command=self.on_refresh).pack(side="left", padx=(6, 0))

        self.path_var = StringVar(value="(no folder selected)")
        ttk.Label(bar, textvariable=self.path_var, foreground="#444").pack(
            side="left", padx=(12, 0)
        )

    def _build_filter_bar(self):
        bar = ttk.LabelFrame(self.root, text="Filters", padding=(8, 6))
        bar.pack(fill="x", padx=8, pady=(0, 4))

        ttk.Label(bar, text="Name contains:").grid(row=0, column=0, sticky="w")
        self.name_filter = StringVar()
        ttk.Entry(bar, textvariable=self.name_filter, width=18).grid(
            row=0, column=1, padx=(4, 12)
        )

        ttk.Label(bar, text="Type:").grid(row=0, column=2, sticky="w")
        self.type_filter = StringVar(value="All")
        ttk.Combobox(
            bar,
            textvariable=self.type_filter,
            values=["All", "Files only", "Folders only"],
            state="readonly",
            width=12,
        ).grid(row=0, column=3, padx=(4, 12))

        ttk.Label(bar, text="Min size:").grid(row=0, column=4, sticky="w")
        self.min_size_value = StringVar()
        ttk.Entry(bar, textvariable=self.min_size_value, width=6).grid(
            row=0, column=5, padx=(4, 2)
        )
        self.min_size_unit = StringVar(value="B")
        ttk.Combobox(
            bar,
            textvariable=self.min_size_unit,
            values=[u for u, _ in SIZE_UNITS],
            state="readonly",
            width=4,
        ).grid(row=0, column=6, padx=(0, 12))

        ttk.Label(bar, text="Max size:").grid(row=0, column=7, sticky="w")
        self.max_size_value = StringVar()
        ttk.Entry(bar, textvariable=self.max_size_value, width=6).grid(
            row=0, column=8, padx=(4, 2)
        )
        self.max_size_unit = StringVar(value="GB")
        ttk.Combobox(
            bar,
            textvariable=self.max_size_unit,
            values=[u for u, _ in SIZE_UNITS],
            state="readonly",
            width=4,
        ).grid(row=0, column=9, padx=(0, 12))

        ttk.Label(bar, text="Extension:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.ext_filter = StringVar(value="All")
        self.ext_combo = ttk.Combobox(
            bar, textvariable=self.ext_filter, values=["All"], state="readonly", width=14
        )
        self.ext_combo.grid(row=1, column=1, padx=(4, 12), pady=(6, 0))

        ttk.Button(bar, text="Apply", command=self.apply_filters).grid(
            row=1, column=8, pady=(6, 0), sticky="e"
        )
        ttk.Button(bar, text="Clear", command=self.clear_filters).grid(
            row=1, column=9, pady=(6, 0), sticky="e"
        )

    def _build_table(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.tree = ttk.Treeview(frame, columns=COLUMNS, show="headings", selectmode="browse")
        for col in COLUMNS:
            self.tree.heading(
                col,
                text=COLUMN_LABELS[col],
                command=lambda c=col: self.on_sort(c),
            )
        self.tree.column("name", width=260, anchor="w")
        self.tree.column("type", width=70, anchor="w")
        self.tree.column("size", width=110, anchor="e")
        self.tree.column("items", width=70, anchor="e")
        self.tree.column("modified", width=160, anchor="w")
        self.tree.column("extension", width=90, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.on_double_click)

    def _build_status_bar(self):
        self.status_var = StringVar(value="Select a folder to begin.")
        ttk.Label(
            self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4)
        ).pack(fill="x", side="bottom")

    # -- Event handlers --------------------------------------------------

    def on_browse(self):
        path = filedialog.askdirectory(title="Select a folder")
        if path:
            self.load_folder(path)

    def on_up(self):
        if not self.current_path:
            return
        parent = os.path.dirname(os.path.abspath(self.current_path))
        if parent and parent != self.current_path:
            self.load_folder(parent)

    def on_refresh(self):
        if self.current_path:
            self.load_folder(self.current_path)

    def on_double_click(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self.visible_entries):
            entry = self.visible_entries[idx]
            if entry["is_dir"]:
                self.load_folder(entry["path"])

    def on_sort(self, column):
        col, ascending = self.sort_state
        if col == column:
            ascending = not ascending
        else:
            ascending = True
        self.sort_state = (column, ascending)
        self.render_rows()

    # -- Data loading and rendering -------------------------------------

    def load_folder(self, path):
        try:
            entries, summary = scan_folder(path)
        except RuntimeError as e:
            messagebox.showerror("Scan failed", str(e))
            return

        self.current_path = path
        self.entries = entries
        self.path_var.set(path)

        extensions = sorted({e["extension"] for e in entries if e["extension"]})
        self.ext_combo["values"] = ["All"] + extensions
        if self.ext_filter.get() not in self.ext_combo["values"]:
            self.ext_filter.set("All")

        self._summary = summary
        self.apply_filters()

    def apply_filters(self):
        name_needle = self.name_filter.get().strip().lower()
        type_choice = self.type_filter.get()
        min_bytes = parse_size(self.min_size_value.get(), self.min_size_unit.get())
        max_bytes = parse_size(self.max_size_value.get(), self.max_size_unit.get())
        ext_choice = self.ext_filter.get()

        filtered = []
        for e in self.entries:
            if name_needle and name_needle not in e["name"].lower():
                continue
            if type_choice == "Files only" and e["is_dir"]:
                continue
            if type_choice == "Folders only" and not e["is_dir"]:
                continue
            size = e["size"]
            if min_bytes is not None and (size is None or size < min_bytes):
                continue
            if max_bytes is not None and (size is None or size > max_bytes):
                continue
            if ext_choice != "All" and e["extension"] != ext_choice:
                continue
            filtered.append(e)

        self.visible_entries = filtered
        self.render_rows()

    def clear_filters(self):
        self.name_filter.set("")
        self.type_filter.set("All")
        self.min_size_value.set("")
        self.max_size_value.set("")
        self.ext_filter.set("All")
        self.apply_filters()

    def render_rows(self):
        column, ascending = self.sort_state

        def sort_key(entry):
            v = entry[column]
            if column == "size":
                return (v is None, v if v is not None else 0)
            if column == "items":
                return (v is None, v if v is not None else -1)
            if column == "modified":
                return (v is None, v if v is not None else datetime.min)
            return (False, (v or "").lower() if isinstance(v, str) else v)

        self.visible_entries.sort(key=sort_key, reverse=not ascending)

        for col in COLUMNS:
            label = COLUMN_LABELS[col]
            if col == column:
                arrow = " \u25b2" if ascending else " \u25bc"
                self.tree.heading(col, text=label + arrow)
            else:
                self.tree.heading(col, text=label)

        self.tree.delete(*self.tree.get_children())
        for e in self.visible_entries:
            self.tree.insert(
                "",
                "end",
                values=(
                    e["name"],
                    e["type"],
                    human_size(e["size"]),
                    "" if e["items"] is None else e["items"],
                    e["modified"].strftime("%Y-%m-%d %H:%M:%S") if e["modified"] else "N/A",
                    e["extension"],
                ),
            )

        self._update_status()

    def _update_status(self):
        s = getattr(self, "_summary", None)
        if s is None:
            self.status_var.set("Select a folder to begin.")
            return
        shown = len(self.visible_entries)
        total = s["entry_count"]
        self.status_var.set(
            f"Showing {shown} of {total} entries  |  "
            f"{s['file_count']} files, {s['folder_count']} folders  |  "
            f"Total size: {human_size(s['total_size'])}"
        )


def main():
    root = Tk()
    app = FolderStatsApp(root)
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        app.load_folder(os.path.abspath(sys.argv[1]))
    root.mainloop()


if __name__ == "__main__":
    main()
