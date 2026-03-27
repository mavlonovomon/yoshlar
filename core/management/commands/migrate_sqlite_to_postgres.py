from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _is_text_type(col_type: str) -> bool:
    normalized = (col_type or "").lower()
    return any(token in normalized for token in ("char", "text", "clob"))


def _load_target_unique_columns(pg_conn):
    unique_columns = {}
    column_specs = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                c.is_nullable,
                c.data_type,
                c.character_maximum_length
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.constraint_schema = kcu.constraint_schema
            JOIN information_schema.columns c
              ON c.table_name = tc.table_name
             AND c.column_name = kcu.column_name
             AND c.table_schema = tc.constraint_schema
            WHERE tc.constraint_schema = current_schema()
              AND tc.constraint_type IN ('UNIQUE', 'PRIMARY KEY')
            ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
            """
        )
        rows = cur.fetchall()

    by_constraint = {}
    for table_name, constraint_name, column_name, is_nullable, data_type, max_length in rows:
        by_constraint.setdefault((table_name, constraint_name), []).append(
            {
                "column_name": column_name,
                "is_nullable": is_nullable == "YES",
                "data_type": data_type or "",
                "max_length": max_length,
            }
        )

    for (table_name, _constraint_name), cols in by_constraint.items():
        for col in cols:
            column_specs[(table_name, col["column_name"])] = {
                "nullable": col["is_nullable"],
                "max_length": col["max_length"],
                "data_type": col["data_type"],
            }
        if len(cols) != 1:
            continue
        col = cols[0]
        if col["column_name"] == "id":
            continue
        if not _is_text_type(col["data_type"]):
            continue
        unique_columns.setdefault(table_name, []).append(col["column_name"])

    return unique_columns, column_specs


def _make_placeholder(pk_value, max_length):
    value = f"u{pk_value}"
    if max_length:
        value = value[: int(max_length)]
    return value


class Command(BaseCommand):
    help = "Copy all data from a SQLite database into PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(settings.BASE_DIR / "yoshlar.db"),
            help="Path to the source SQLite database file.",
        )
        parser.add_argument(
            "--database-url",
            default=os.environ.get("DATABASE_URL", ""),
            help="PostgreSQL DATABASE_URL. Defaults to the current environment variable.",
        )

    def handle(self, *args, **options):
        if psycopg is None:
            raise CommandError("psycopg topilmadi. Avval psycopg o'rnatilishi kerak.")

        source_path = Path(options["source"]).resolve()
        if not source_path.exists():
            raise CommandError(f"Source SQLite database not found: {source_path}")

        target_url = (options["database_url"] or "").strip()
        if not target_url:
            raise CommandError("DATABASE_URL is required for PostgreSQL migration.")

        self.stdout.write(self.style.NOTICE(f"Source: {source_path}"))
        self.stdout.write(self.style.NOTICE("Connecting to PostgreSQL..."))

        sqlite_conn = sqlite3.connect(str(source_path))
        sqlite_conn.row_factory = None
        pg_conn = psycopg.connect(target_url)

        try:
            target_unique_columns, column_specs = _load_target_unique_columns(pg_conn)
            source_tables = [
                row[0]
                for row in sqlite_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]

            with pg_conn:
                with pg_conn.cursor() as pg_cur:
                    pg_cur.execute("SET session_replication_role = replica")
                    pg_cur.execute(
                        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() ORDER BY tablename"
                    )
                    target_tables = [row[0] for row in pg_cur.fetchall()]
                    target_table_set = set(target_tables)
                    if target_tables:
                        truncate_sql = "TRUNCATE TABLE " + ", ".join(_quote_ident(t) for t in target_tables) + " RESTART IDENTITY CASCADE"
                        self.stdout.write(self.style.WARNING("Clearing target PostgreSQL tables..."))
                        pg_cur.execute(truncate_sql)

                self.stdout.write(self.style.WARNING("Copying data..."))
                copied = 0
                for table in source_tables:
                    if table not in target_table_set:
                        self.stdout.write(self.style.WARNING(f"Skipping source-only table {table} (not in PostgreSQL schema)."))
                        continue

                    cols_info = sqlite_conn.execute(f'PRAGMA table_info({_quote_ident(table)})').fetchall()
                    if not cols_info:
                        continue

                    columns = [col[1] for col in cols_info]
                    column_index = {name: idx for idx, name in enumerate(columns)}
                    quoted_columns = ", ".join(_quote_ident(col) for col in columns)
                    select_sql = f'SELECT {quoted_columns} FROM {_quote_ident(table)}'
                    copy_sql = f'COPY {_quote_ident(table)} ({quoted_columns}) FROM STDIN'
                    unique_columns = target_unique_columns.get(table, [])
                    unique_seen = {col: set() for col in unique_columns}
                    pk_cols = [col for col in cols_info if col[5]]
                    pk_name = pk_cols[0][1] if len(pk_cols) == 1 else None
                    pk_index = column_index.get(pk_name) if pk_name else None

                    row_count = 0
                    with pg_conn.cursor() as pg_cur:
                        with pg_cur.copy(copy_sql) as copy:
                            for row in sqlite_conn.execute(select_sql):
                                row = list(row)
                                pk_value = row[pk_index] if pk_index is not None else row_count + 1
                                for idx, value in enumerate(row):
                                    col_name = columns[idx]
                                    spec = column_specs.get((table, col_name), {})
                                    max_length = spec.get("max_length")
                                    if isinstance(value, str) and max_length and len(value) > int(max_length):
                                        row[idx] = value[: int(max_length)]

                                for unique_col in unique_columns:
                                    idx = column_index.get(unique_col)
                                    if idx is None:
                                        continue
                                    original_value = row[idx]
                                    col_meta = cols_info[idx]
                                    spec = column_specs.get((table, unique_col), {})
                                    nullable = spec.get("nullable", not bool(col_meta[3]))
                                    max_length = spec.get("max_length")
                                    if original_value is None:
                                        continue
                                    stripped = original_value.strip() if isinstance(original_value, str) else original_value
                                    needs_fix = False
                                    if isinstance(original_value, str) and not original_value.strip():
                                        needs_fix = True
                                    elif stripped in unique_seen[unique_col]:
                                        needs_fix = True
                                    if needs_fix:
                                        if nullable and isinstance(original_value, str) and not original_value.strip():
                                            row[idx] = None
                                        else:
                                            row[idx] = _make_placeholder(pk_value, max_length)
                                    unique_seen[unique_col].add(row[idx])
                                copy.write_row(tuple(row))
                                row_count += 1

                        pk_cols = [col for col in cols_info if col[5]]
                        if len(pk_cols) == 1 and pk_cols[0][1] == "id":
                            seq_sql = f"SELECT pg_get_serial_sequence(%s, %s)"
                            pg_cur.execute(seq_sql, (table, "id"))
                            seq_name = pg_cur.fetchone()[0]
                            if seq_name:
                                pg_cur.execute(
                                    f"SELECT setval(%s, COALESCE((SELECT MAX({_quote_ident('id')}) FROM {_quote_ident(table)}), 1), EXISTS (SELECT 1 FROM {_quote_ident(table)}))",
                                    (seq_name,),
                                )

                    copied += row_count
                    self.stdout.write(self.style.SUCCESS(f"{table}: {row_count} rows"))

                self.stdout.write(self.style.SUCCESS(f"Copied {copied} rows total."))
                with pg_conn.cursor() as pg_cur:
                    pg_cur.execute("SET session_replication_role = origin")
        finally:
            sqlite_conn.close()
            pg_conn.close()
