import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ingest import load_csv_to_db

CSV_PATH = "/app/data.csv"
DB_PATH = "/app/sales.db"

SCHEMA_DDL = """-- Table: sales | Domain: Point-of-Sale | Argentine confectionery shop
-- Each row = one product sold within a receipt. Multiple rows share ticket_number.
-- Dataset: 24,212 rows | Sep 21 – Nov 20, 2024 (60 days) | 68 products | 11,771 tickets
CREATE TABLE sales (
    date          TEXT,    -- ISO date YYYY-MM-DD. Use strftime() for grouping. Already normalized.
    week_day      TEXT,    -- Day of week: Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday
    hour          TEXT,    -- Transaction time HH:MM. Use CAST(substr(hour,1,2) AS INTEGER) for hour int.
    ticket_number TEXT,    -- Unique receipt ID. Use COUNT(DISTINCT ticket_number) for transactions.
    ticket_prefix TEXT,    -- Register/type code: FCA | FCB | NCA | NCB
    waiter        TEXT,    -- Staff ID as text: 0, 51, 52, 101, 102, 103, 104, 105, 116
    product_name  TEXT,    -- Product sold (68 unique items; 'ART. INEXISTENTE' = unregistered)
    quantity      REAL,    -- Units sold. Negative = return/refund. May be fractional.
    unitary_price INTEGER, -- Price per unit in ARS (Argentine pesos)
    total         INTEGER  -- Line total = quantity * unitary_price. Negative for returns.
);

-- Sample product values: 'Alfajor Sin Azucar Suelto', 'Alf. 150 aniv. Suelto',
--   'Alfajor 70 cacao x un', 'Conito choc x un', 'Tableta 70 cacao x80g'
-- Sample week_day values: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
-- Sample waiter values: '0', '51', '52', '101', '102', '103', '104', '105', '116'

-- KPI expressions:
-- total_revenue:      SUM(total)       [add WHERE total > 0 to exclude returns]
-- total_units_sold:   SUM(quantity)
-- avg_ticket_value:   SUM(total) * 1.0 / COUNT(DISTINCT ticket_number)
-- transaction_count:  COUNT(DISTINCT ticket_number)
"""


class ExecuteRequest(BaseModel):
    sql: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(CSV_PATH):
        raise RuntimeError(f"data.csv not found at {CSV_PATH}")
    load_csv_to_db(CSV_PATH, DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/execute")
def execute(request: ExecuteRequest):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(request.sql)
        if cursor.description is None:
            conn.commit()
            return {"columns": [], "rows": [], "row_count": 0}
        columns = [col[0] for col in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except sqlite3.Error as exc:
        return {"error": str(exc), "sql": request.sql}
    finally:
        conn.close()


@app.get("/schema")
def schema():
    try:
        return {"ddl": SCHEMA_DDL}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/health")
def health():
    try:
        conn = sqlite3.connect(DB_PATH)
        row_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        conn.close()
        return {"status": "ok", "row_count": row_count}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
