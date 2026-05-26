import csv
import sqlite3
from datetime import datetime


def load_csv_to_db(csv_path: str, db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            date          TEXT,
            week_day      TEXT,
            hour          TEXT,
            ticket_number TEXT,
            ticket_prefix TEXT,
            waiter        TEXT,
            product_name  TEXT,
            quantity      REAL,
            unitary_price INTEGER,
            total         INTEGER
        )
    """)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            iso_date = datetime.strptime(r['date'], '%m/%d/%Y').strftime('%Y-%m-%d')
            ticket_prefix = r['ticket_number'].split()[0]
            rows.append((
                iso_date,
                r['week_day'],
                r['hour'],
                r['ticket_number'],
                ticket_prefix,
                r['waiter'],
                r['product_name'],
                float(r['quantity']),
                int(r['unitary_price']),
                int(r['total']),
            ))

    conn.executemany(
        "INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
