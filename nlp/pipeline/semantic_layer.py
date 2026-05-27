from datetime import date
from pathlib import Path

import yaml


class SemanticLayer:
    def __init__(self, yaml_path: str | Path | None = None):
        if yaml_path is None:
            yaml_path = Path(__file__).resolve().parent.parent / "schema" / "domain.yaml"
        self.yaml_path = Path(yaml_path)
        with open(self.yaml_path, encoding="utf-8") as f:
            self.descriptor = yaml.safe_load(f)

    def get_kpis(self) -> list[dict]:
        return self.descriptor.get("kpis", [])

    def get_date_anchor(self) -> tuple[str, str]:
        """Return (date_range.start, date_range.end) as ISO-8601 strings from domain.yaml."""
        sales = self.descriptor.get("tables", {}).get("sales", {})
        date_range = sales.get("date_range", {})
        start = date_range.get("start")
        end = date_range.get("end")
        if not isinstance(start, str) or not isinstance(end, str):
            raise KeyError(
                "domain.yaml tables.sales.date_range must define start and end as ISO strings"
            )
        date.fromisoformat(start)
        date.fromisoformat(end)
        return (start, end)

    def render_ddl(self) -> str:
        """Render CREATE TABLE DDL with comments from the YAML descriptor (spec §5.2)."""
        tables = self.descriptor.get("tables", {})
        sales = tables.get("sales", {})
        columns = sales.get("columns", {})
        date_range = sales.get("date_range", {})
        sample_values = sales.get("sample_values", {})

        span = date_range.get("span_days", 60)

        col_comments = {
            "date": "ISO date YYYY-MM-DD. Use strftime() for grouping. Already normalized.",
            "week_day": "Day of week: Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday",
            "hour": "Transaction time HH:MM. Use CAST(substr(hour,1,2) AS INTEGER) for hour int.",
            "ticket_number": "Unique receipt ID. Use COUNT(DISTINCT ticket_number) for transactions.",
            "ticket_prefix": "Register/type code: FCA | FCB | NCA | NCB",
            "waiter": "Staff ID as text: 0, 51, 52, 101, 102, 103, 104, 105, 116",
            "product_name": "Product sold (68 unique items; 'ART. INEXISTENTE' = unregistered)",
            "quantity": "Units sold. Negative = return/refund. May be fractional.",
            "unitary_price": "Price per unit in ARS (Argentine pesos)",
            "total": "Line total = quantity * unitary_price. Negative for returns.",
        }

        col_lines = []
        col_names = list(columns.keys())
        for i, name in enumerate(col_names):
            col_def = columns[name]
            col_type = col_def.get("type", "TEXT")
            comment = col_comments.get(name, col_def.get("description", "").split("\n")[0])
            comma = "," if i < len(col_names) - 1 else ""
            col_lines.append(f"    {name:<14} {col_type},{comma}    -- {comment}")

        col_block = "\n".join(col_lines)

        products = sample_values.get("product_name", [])
        product_samples = ", ".join(f"'{p}'" for p in products[:5])
        week_days = sample_values.get("week_day", [])
        week_day_samples = ", ".join(week_days)
        waiters = sample_values.get("waiter", [])
        waiter_samples = ", ".join(f"'{w}'" for w in waiters)

        kpi_lines = []
        for kpi in self.descriptor.get("kpis", []):
            note = kpi.get("note", "")
            suffix = f"       [{note}]" if note else ""
            kpi_lines.append(f"-- {kpi['name']}:{' ' * (18 - len(kpi['name']))}{kpi['definition']}{suffix}")
        kpi_block = "\n".join(kpi_lines)

        return f"""-- Table: sales | Domain: Point-of-Sale | Argentine confectionery shop
-- Each row = one product sold within a receipt. Multiple rows share ticket_number.
-- Dataset: 24,212 rows | Sep 21 – Nov 20, 2024 ({span} days) | 68 products | 11,771 tickets
CREATE TABLE sales (
{col_block}
);

-- Sample product values: {product_samples}
-- Sample week_day values: {week_day_samples}
-- Sample waiter values: {waiter_samples}

-- KPI expressions:
{kpi_block}
"""
