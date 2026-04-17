# CourseraRepo

# This is a test repo for a Getting Started with Git project on Coursera.

## Folder Stats Viewer

`folder_stats.py` is a Tkinter GUI that shows stats for a selected folder and
its direct children (name, type, size, item count, modified time, extension).
Columns are sortable by clicking headers, and a filter bar narrows rows by
name, type, size range, and extension. Double-click a folder row to drill in.

Run:

```
python3 folder_stats.py            # opens empty, use Browse…
python3 folder_stats.py /some/path # opens on a specific folder
```

Uses only the Python standard library — no installs required.
