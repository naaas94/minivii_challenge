import sqlite3
import sys
import tempfile
from pathlib import Path

_DB_ROOT = Path(__file__).resolve().parent.parent
if str(_DB_ROOT) not in sys.path:
    sys.path.insert(0, str(_DB_ROOT))

from ingest import load_csv_to_db

HEADER = (
    "date,week_day,hour,ticket_number,waiter,product_name,quantity,unitary_price,total\n"
)
ROW = "01/15/2024,Monday,12:00,T-1 A,Waiter A,Widget,1.0,100,100\n"


def _write_csv(path: Path, row_count: int) -> None:
    path.write_text(HEADER + ROW * row_count, encoding="utf-8")


def test_load_csv_to_db_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "data.csv"
        db_path = Path(tmp) / "sales.db"
        _write_csv(csv_path, 3)

        load_csv_to_db(str(csv_path), str(db_path))
        load_csv_to_db(str(csv_path), str(db_path))

        conn = sqlite3.connect(db_path)
        (count,) = conn.execute("SELECT COUNT(*) FROM sales").fetchone()
        conn.close()
        assert count == 3


def test_load_csv_to_db_extracts_ticket_prefix():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "data.csv"
        db_path = Path(tmp) / "sales.db"
        _write_csv(csv_path, 1)

        load_csv_to_db(str(csv_path), str(db_path))

        conn = sqlite3.connect(db_path)
        prefix = conn.execute(
            "SELECT ticket_prefix FROM sales LIMIT 1"
        ).fetchone()[0]
        conn.close()
        assert prefix == "T-1"
