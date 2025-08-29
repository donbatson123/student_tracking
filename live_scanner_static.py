#!/usr/bin/env python3
# live_scanner_static.py — fullscreen UI, redraw ONLY after Enter
import sqlite3
from datetime import datetime
from pathlib import Path
from collections import deque
import re
import sys
import csv
from typing import Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.layout import Layout
from rich import box

# =========================
# CONFIG — edit these once
# =========================
SQLITE_DB_PATH = Path("students.db")   # <-- your SQLite DB path
NAMES_TABLE     = "names"                    # must have tracking_id, first_name, last_name
SCANS_TABLE     = "scans"                    # script will create if needed

# NEW: where to write daily CSVs
OUTPUT_DIR      = Path("/home/ddb/Documents/daily_list")  # e.g., /var/lib/scans or ./scans_out

TITLE           = "📚 Live Student Scanner"
COLOR_MAIN      = "bold green"
COLOR_HISTORY   = "cyan"
COLOR_HELP      = "magenta"
COLOR_WARN      = "bold yellow"
COLOR_ERROR     = "bold red"

PROMPT_TEXT     = "\n[bold]Scan or type tracking_id and press Enter:[/] "

# =========================
# DB helpers
# =========================
def ensure_scans_table(conn: sqlite3.Connection):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCANS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id INTEGER,
            first_name TEXT,
            last_name TEXT,
            time_hhmm TEXT,
            date_mmddyyyy TEXT
        )
    """)
    conn.commit()

def fetch_name_by_tracking_id(conn: sqlite3.Connection, tid: int) -> Optional[Tuple[str, str]]:
    cur = conn.execute(
        f"SELECT first_name, last_name FROM {NAMES_TABLE} WHERE tracking_id = ?",
        (tid,)
    )
    row = cur.fetchone()
    return (row[0], row[1]) if row else None

def insert_scan(conn: sqlite3.Connection, tid: int, first: str, last: str):
    now = datetime.now()
    time_hhmm = now.strftime("%H:%M")
    date_mmddyyyy = now.strftime("%m:%d:%Y")
    conn.execute(
        f"""INSERT INTO {SCANS_TABLE} (tracking_id, first_name, last_name, time_hhmm, date_mmddyyyy)
            VALUES (?, ?, ?, ?, ?)""",
        (tid, first, last, time_hhmm, date_mmddyyyy)
    )
    conn.commit()
    return time_hhmm, date_mmddyyyy

# =========================
# Daily CSV helpers
# =========================
def get_daily_csv_path(base_dir: Path, now: datetime) -> Path:
    month_folder = now.strftime("%m_%Y")            # e.g. 08_2025
    filename     = now.strftime("%m_%d_%Y.csv")     # e.g. 08_28_2025.csv
    out_dir = base_dir / month_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / filename

def append_daily_csv(base_dir: Path, row: dict):
    """
    Row keys: tracking_id, first_name, last_name, time_hhmm, date_mmddyyyy
    """
    now = datetime.now()
    path = get_daily_csv_path(base_dir, now)
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["tracking_id", "first_name", "last_name", "time_hhmm", "date_mmddyyyy"]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    return path

# =========================
# UI helpers (Rich)
# =========================
console = Console()

def render_main_panel(current_msg: str, sub_msg: str = "") -> Panel:
    body = current_msg if not sub_msg else f"{current_msg}\n[subdued]{sub_msg}[/subdued]"
    return Panel(
        Align.center(body, vertical="middle"),
        border_style=COLOR_MAIN,
        title=TITLE,
        padding=(2, 6),
    )

def render_history_panel(history: deque) -> Panel:
    tbl = Table.grid(expand=True)
    tbl.add_column(justify="left", ratio=1)
    if not history:
        tbl.add_row("[dim]No history yet[/dim]")
    else:
        for idx, (tid, first, last, hhmm, mdy) in enumerate(history, start=1):
            line = f"[{COLOR_HISTORY}]#{idx}[/]  [b]{first} {last}[/]  (ID {tid})  [dim]{hhmm} {mdy}[/dim]"
            tbl.add_row(line)

    return Panel(
        tbl,
        title="Last 3",
        border_style=COLOR_HISTORY,
        padding=(1, 2),
        box=box.ROUNDED
    )

def render_help_panel() -> Panel:
    help_text = (
        "[b]How to Use[/b]\n"
        "• Scan OR type a student's tracking_id and press Enter.\n"
        "• Name shows big in the center.\n"
        "• Recent scans show at bottom-right.\n\n"
        "[b]Messages[/b]\n"
        f"• [{COLOR_WARN}]Invalid scan[/]: Not a number — try again.\n"
        f"• [{COLOR_ERROR}]ID not found[/]: Not in the list — notify staff.\n\n"
        "[b]Stop[/b]\n"
        "• Press [b]CTRL+C[/b] once to quit.\n\n"
        "[dim]Time: HH:MM   Date: MM:DD:YYYY[/dim]"
    )
    return Panel(
        Align.left(help_text),
        title="Help",
        border_style=COLOR_HELP,
        padding=(1, 2),
        box=box.ROUNDED
    )

def render_prompt_panel() -> Panel:
    return Panel(
        Align.left("[b]Prompt:[/b] Scan [i]or[/i] type a tracking_id, then press Enter."),
        border_style="white",
        padding=(0, 1),
        box=box.SIMPLE
    )

def build_layout(current: str, subline: str, history: deque) -> Layout:
    layout = Layout()
    # Top area = main name + small prompt strip
    layout.split(
        Layout(name="top", ratio=4),
        Layout(name="bottom", ratio=2),
    )
    layout["top"].split(
        Layout(name="top_main", ratio=12),
        Layout(name="top_prompt", ratio=1),
    )
    # bottom splits horizontally: left (Help), right (History)
    layout["bottom"].split_row(
        Layout(name="bottom_left", ratio=3, minimum_size=42),
        Layout(name="bottom_right", ratio=2, minimum_size=32),
    )
    layout["top_main"].update(render_main_panel(current, subline))
    layout["top_prompt"].update(render_prompt_panel())
    layout["bottom_left"].update(render_help_panel())
    layout["bottom_right"].update(render_history_panel(history))
    return layout

# =========================
# Input / Normalize
# =========================
def normalize_scan(s: str) -> Optional[int]:
    digits = re.sub(r"\D", "", s or "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None

def beep_success():
    # Try rich bell first; fall back to ASCII bell.
    try:
        console.bell()
    except Exception:
        print("\a", end="", flush=True)

# =========================
# Main
# =========================
def main():
    if not SQLITE_DB_PATH.exists():
        console.print(f"[{COLOR_ERROR}]SQLite DB not found:[/] {SQLITE_DB_PATH}")
        sys.exit(1)

    # Ensure output directory exists up front
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        ensure_scans_table(conn)

        history = deque(maxlen=3)  # (tid, first, last, hhmm, mdy)
        current_line = "[dim]Scan or type a tracking_id to begin...[/dim]"
        subline = "Press Ctrl+C to exit."

        # Full-screen alt-buffer; we control all redraws manually (no live refresh).
        with console.screen():
            while True:
                try:
                    # 1) Draw the current UI snapshot
                    console.clear()
                    console.print(build_layout(current_line, subline, history))

                    # 2) Blocking input (no redraw while typing => no twitch)
                    try:
                        raw = console.input(PROMPT_TEXT).strip()
                    except Exception:
                        raw = input("\nScan or type tracking_id and press Enter: ").strip()

                    # 3) Process the entry
                    tid = normalize_scan(raw)
                    if tid is None:
                        current_line = f"[{COLOR_WARN}]Invalid scan[/]  (got: '{raw}'). Try again."
                        subline = "Expecting digits (tracking_id)."
                        continue

                    found = fetch_name_by_tracking_id(conn, tid)
                    if not found:
                        current_line = f"[{COLOR_ERROR}]ID {tid} not found[/]"
                        subline = "Make sure the names table is loaded and IDs start at 100."
                        continue

                    first, last = found
                    hhmm, mdy = insert_scan(conn, tid, first, last)

                    # Beep on success
                    beep_success()

                    # Append to daily CSV
                    csv_path = append_daily_csv(
                        OUTPUT_DIR,
                        {
                            "tracking_id": tid,
                            "first_name": first,
                            "last_name": last,
                            "time_hhmm": hhmm,
                            "date_mmddyyyy": mdy,
                        },
                    )

                    # Update UI
                    current_line = f"[{COLOR_MAIN}]{first} {last}[/]   [dim](ID {tid})[/dim]"
                    subline = f"[dim]{hhmm}  {mdy}[/dim]  [dim]→ {csv_path}[/dim]"
                    history.appendleft((tid, first, last, hhmm, mdy))

                    # Loop repeats: screen clears and redraws ONCE with updated info

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    current_line = f"[{COLOR_ERROR}]Error:[/] {e}"
                    subline = "Check console and DB paths."
                    # on next loop iteration, it will render the error
                    continue

        # Leaving console.screen() restores the normal terminal
        console.print("\n[bold]Exiting scanner…[/bold]")

    finally:
        conn.close()
        console.print("[dim]Connection closed.[/dim]")

if __name__ == "__main__":
    main()
