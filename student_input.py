#!/usr/bin/env python3
import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd
import re
import sys

# =========================
# HARD-CODED SETTINGS
# =========================
INPUT_CSV_PATH = Path("/home/ddb/Documents/students.csv")        # <— change me
OUTPUT_DIR     = Path("/home/ddb/Documents/ouput")            # <— change me
OUTPUT_CSV_NAME = "students_with_tracking_id.csv"                   # output filename

SQLITE_DB_PATH = Path("students.db")              # <— change me
SQLITE_TABLE   = "names"                                # <— change me
SQL_IF_EXISTS  = "replace"                              # "replace" or "append"

CSV_ENCODING   = "utf-8"
CSV_DELIMITER  = "," # None = auto-detect; or set e.g. "," or "\t"

# If you choose Format 1 (combined column), we'll read this column:
COMBINED_NAME_COL = "Student Name"                      # <— change to your header

# If you choose Format 2 (separate columns), we’ll read these:
FIRST_COL = "First Name"                                # <— change to your header
LAST_COL  = "Last Name"                                 # <— change to your header

# =========================
# Helpers
# =========================
def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def to_title(s):
    s = _norm(s)
    if not s:
        return s
    return " ".join(
        [w if w.isupper() and len(w) > 1 else w.capitalize()
         for w in re.split(r"(\s+)", s)]
    )

def clean_first(first):
    first = _norm(first)
    # Remove single-letter initials like "A." or "B"
    if len(first) == 1 or re.match(r"^[A-Z]\.?$", first):
        return ""
    return to_title(first)

def parse_fullname(raw):
    """
    Parse "Last, First M." into (First, Last).
    Drop middle initials.
    """
    raw = _norm(raw)
    if not raw:
        return ("", "")

    if "," in raw:
        last, given = [p.strip() for p in raw.split(",", 1)]
        tokens = given.split()
        first = tokens[0] if tokens else ""
        return (clean_first(first), to_title(last))
    else:
        # Fallback: assume "First Last"
        tokens = raw.split()
        if len(tokens) == 1:
            return (clean_first(tokens[0]), "")
        return (clean_first(tokens[0]), to_title(tokens[-1]))

def read_csv(path: Path, encoding="utf-8", delimiter=None):
    kwargs = dict(encoding=encoding, dtype=str, keep_default_na=False)
    if delimiter is not None:
        kwargs["sep"] = delimiter
    return pd.read_csv(path, **kwargs)

def build_from_combined(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        raise ValueError(f"Combined name column '{col}' not found in CSV.")
    parsed = df[col].astype(str).map(parse_fullname)
    out = pd.DataFrame({
        "first_name": parsed.map(lambda t: t[0]),
        "last_name":  parsed.map(lambda t: t[1]),
    })
    return finalize(out)

def build_from_separate(df: pd.DataFrame, first_col: str, last_col: str) -> pd.DataFrame:
    for c in (first_col, last_col):
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found in CSV.")
    out = pd.DataFrame({
        "first_name": df[first_col].astype(str).map(clean_first),
        "last_name":  df[last_col].astype(str).map(to_title),
    })
    return finalize(out)

def finalize(out: pd.DataFrame) -> pd.DataFrame:
    # drop rows without usable names
    out = out[(out["first_name"].str.len() > 0) | (out["last_name"].str.len() > 0)].copy()
    # sort by first_name then last_name
    out.sort_values(by=["first_name", "last_name"], inplace=True, kind="mergesort", ignore_index=True)
    # add tracking_id starting at 100
    out.insert(0, "tracking_id", range(100, 100 + len(out)))
    return out

def to_sqlite(df: pd.DataFrame, sqlite_path: Path, table: str, if_exists: str = "replace"):
    conn = sqlite3.connect(sqlite_path)
    try:
        df_sql = df.copy()
        # include metadata in DB only (not required in CSV)
        df_sql["imported_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        df_sql["source_file"] = INPUT_CSV_PATH.name
        df_sql.to_sql(table, conn, if_exists=if_exists, index=False)
        if if_exists == "replace":
            conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_tracking_id ON {table}(tracking_id);")
            conn.commit()
    finally:
        conn.close()

def write_output_csv(df: pd.DataFrame, out_dir: Path, filename: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    df[["first_name", "last_name", "tracking_id"]].to_csv(out_path, index=False, encoding="utf-8")
    return out_path

# =========================
# Menu
# =========================
def menu():
    print("\n=== Name Import Menu ===")
    #print("1) Combined column (e.g., 'LastName, FirstName MI.')")
    print("2) Separate columns (First Name / Last Name)")
    choice = input("Select format [2]: ").strip()
    if choice not in { "2"}:
        print("Invalid choice.")
        sys.exit(1)
    return choice

def main():
    try:
        choice = menu()
        df = read_csv(INPUT_CSV_PATH, encoding=CSV_ENCODING, delimiter=CSV_DELIMITER)

        if choice == "1":
            cleaned = build_from_combined(df, COMBINED_NAME_COL)
        else:
            cleaned = build_from_separate(df, FIRST_COL, LAST_COL)

        # Save to SQLite
        to_sqlite(cleaned, SQLITE_DB_PATH, SQLITE_TABLE, if_exists=SQL_IF_EXISTS)

        # Export CSV (first_name, last_name, tracking_id)
        out_path = write_output_csv(cleaned, OUTPUT_DIR, OUTPUT_CSV_NAME)

        print(f"\n✅ Processed {len(cleaned)} rows.")
        print(f"   • SQLite: {SQLITE_DB_PATH} (table: {SQLITE_TABLE}, mode: {SQL_IF_EXISTS})")
        print(f"   • CSV: {out_path}")
        print("   • tracking_id starts at 100; sorted by first_name then last_name.")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
