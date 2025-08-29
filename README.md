# 📚 Live Student Scanner

`live_scanner_static.py` is a terminal-based barcode (or keyboard) scanner interface built with Python and [Rich](https://github.com/Textualize/rich).  
It displays scanned student names in a fullscreen UI, keeps a short history, writes scans to SQLite, and logs each scan into a **daily CSV file**.

---

## ✨ Features

- **Fullscreen UI** (no screen flicker while typing)
- **Scan or type** student `tracking_id` and press Enter
- **Center display**: most recent student scanned
- **Lower-right corner**: last 3 scans
- **Lower-left corner**: on-screen help
- **Audible beep** on successful scans
- **Data storage**:
  - SQLite database (`names` table for student list, `scans` table for scan log)
  - Daily CSV logs:
    - Stored in `OUTPUT_DIR/mm_yyyy/`
    - File format: `mm_dd_yyyy.csv`
    - Columns: `tracking_id, first_name, last_name, time_hhmm, date_mmddyyyy`

---

## 🛠 Requirements

- Python 3.8+
- Dependencies:
  - [rich](https://pypi.org/project/rich/)

Install with:

```bash
pip install rich


⚙️ Setup

Clone this repo or copy the script into a folder.

Ensure you have a SQLite database with a names table that looks like:

CREATE TABLE names (
    tracking_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT
);


(You can populate this using the import script that generates tracking_ids.)

Edit the config section in live_scanner_static.py:

▶️ Usage

Run the script:

python live_scanner_static.py


Scan or type a tracking_id and press Enter.

If valid:

Name appears big in the center

Screen beeps

Entry logged in scans table + daily CSV

If invalid or not found:

Error message is shown

Quit: press CTRL+C.

📂 Example Output
output_dir/
└── 08_2025/
    ├── 08_28_2025.csv
    └── 08_29_2025.csv


Example CSV row:

tracking_id,first_name,last_name,time_hhmm,date_mmddyyyy
100,John,Smith,14:32,08:28:2025


🔊 Notes

On successful scan, you’ll hear a short beep.

Make sure your terminal allows the ASCII bell (or Rich bell).

CSV log files are safe to open in Excel, Google Sheets, or any text editor.

