#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate YAML control files for python/import_tool.py.

This tool writes the same top-level control-file fields used by the Java
ImportControlFile model, and also supports the extra optional fields that
import_tool.py can consume directly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

try:
    import yaml
except ImportError:
    print("Missing dependency: pyyaml")
    print("Install with: pip install pyyaml")
    sys.exit(1)


def parse_copy_columns(copy_columns: str, copy_column_items: List[str]) -> List[str]:
    values: List[str] = []
    if copy_columns:
        values.extend(item.strip() for item in copy_columns.split(","))
    if copy_column_items:
        values.extend(item.strip() for item in copy_column_items)
    return [item for item in values if item]


def parse_key_value_pairs(values: List[str], option_name: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"{option_name} 必须使用 key=value 形式: {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"{option_name} 的 key 不能为空: {raw}")
        parsed[key] = value
    return parsed


def build_inline_db(args: argparse.Namespace) -> Dict[str, str]:
    db: Dict[str, str] = {}
    mappings = {
        "type": args.db_type,
        "psql_path": args.db_psql_path,
        "mysql_path": args.db_mysql_path,
        "host": args.db_host,
        "port": str(args.db_port) if args.db_port is not None else "",
        "database": args.db_database,
        "user": args.db_user,
        "pgpass_file": args.db_pgpass_file,
        "pgpassword": args.db_pgpassword,
        "defaults_extra_file": args.db_defaults_extra_file,
    }
    for key, value in mappings.items():
        if value not in (None, ""):
            db[key] = value
    return db


def build_control_payload(args: argparse.Namespace) -> Dict[str, object]:
    copy_columns = parse_copy_columns(args.copy_columns, args.copy_column)
    params = parse_key_value_pairs(args.param, "--param")
    inline_db = build_inline_db(args)

    payload: Dict[str, object] = {
        "job": args.job,
        "csv_path": args.csv_path,
        "import_date": args.import_date,
        "target_table": args.target_table,
        "staging_table_prefix": args.staging_table_prefix,
        "copy_columns": copy_columns or None,
        "merge_sql_file": args.merge_sql_file,
        "db_ref": args.db_ref,
        "sql_file": args.sql_file,
        "params": params or None,
        "db": inline_db or None,
    }

    return {key: value for key, value in payload.items() if value is not None}


def validate_payload(payload: Dict[str, object]) -> None:
    if not payload.get("csv_path"):
        raise ValueError("csv_path 必填")
    if not payload.get("import_date"):
        raise ValueError("import_date 必填")

    has_job = bool(payload.get("job"))
    has_sql_file = bool(payload.get("sql_file"))
    has_db_ref = bool(payload.get("db_ref"))
    has_inline_db = bool(payload.get("db"))

    if not has_job:
        if not has_sql_file:
            if not payload.get("target_table"):
                raise ValueError("未指定 job 且未指定 sql_file 时，target_table 必填")
            if not payload.get("copy_columns"):
                raise ValueError("未指定 job 且未指定 sql_file 时，copy_columns 必填")
            if not payload.get("merge_sql_file"):
                raise ValueError("未指定 job 且未指定 sql_file 时，merge_sql_file 必填")
        if not (has_db_ref or has_inline_db):
            raise ValueError("未指定 job 时，必须提供 db_ref 或内联 db")

    if has_inline_db and "type" not in payload["db"]:
        raise ValueError("使用内联 db 时，db_type 必填")


def default_output_path(csv_path: str) -> Path:
    return Path(f"{csv_path}.control.yaml")


def dump_yaml(payload: Dict[str, object]) -> str:
    return yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def write_control_file(payload: Dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dump_yaml(payload), encoding="utf-8")


EPILOG = """\
示例:
  # Java trades_both 对应的最简模式 A
  python generate_control_file.py \
    --job trade_snapshot \
    --csv-path C:/data/exports/2026-03-10_trades_both.csv \
    --import-date 2026-03-10

  # Java weekly statistics 对应场景，覆盖 target_table
  python generate_control_file.py \
    --job trades_statistics_snapshot \
    --csv-path C:/data/exports/weekly_2026-03-02_2026-03-08_trades_statistics_by_region.csv \
    --import-date 2026-03-02 \
    --target-table risk_manage.trades_statistics_weekly_snapshot \
    --output C:/data/exports/weekly_2026-03-02_2026-03-08_import_by_region.control.yaml

  # 完整模式 B，不依赖 job
  python generate_control_file.py \
    --csv-path C:/data/exports/custom.csv \
    --import-date 2026-03-10 \
    --target-table risk_manage.custom_report \
    --staging-table-prefix staging_custom_report \
    --copy-columns import_date,login,symbol,profit \
    --merge-sql-file trades_statistics_snapshot_merge.sql \
    --db-ref pg_local \
    --output C:/data/exports/custom.control.yaml
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成 python/import_tool.py 使用的 YAML control file",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--job", help="config.yaml 中的 job 名称（模式 A）")
    parser.add_argument("--csv-path", required=True, help="CSV 文件路径")
    parser.add_argument("--import-date", required=True, help="导入日期，格式 yyyy-MM-dd")
    parser.add_argument("--output", help="输出 control file 路径，默认 <csv_path>.control.yaml")

    parser.add_argument("--target-table", help="目标表名")
    parser.add_argument("--staging-table-prefix", help="staging 表名前缀")
    parser.add_argument("--copy-columns", default="", help="逗号分隔的 copy_columns")
    parser.add_argument(
        "--copy-column",
        action="append",
        default=[],
        help="重复传入单个 copy column，可与 --copy-columns 混用",
    )
    parser.add_argument("--merge-sql-file", help="sql/ 目录下的 merge SQL 模板名")
    parser.add_argument("--db-ref", help="config.yaml databases 中的实例名")
    parser.add_argument("--sql-file", help="预生成 SQL 文件路径")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="额外模板参数，格式 key=value，可重复传入",
    )

    parser.add_argument("--db-type", choices=["postgres", "mysql"], help="内联 db.type")
    parser.add_argument("--db-psql-path", help="内联 db.psql_path")
    parser.add_argument("--db-mysql-path", help="内联 db.mysql_path")
    parser.add_argument("--db-host", help="内联 db.host")
    parser.add_argument("--db-port", type=int, help="内联 db.port")
    parser.add_argument("--db-database", help="内联 db.database")
    parser.add_argument("--db-user", help="内联 db.user")
    parser.add_argument("--db-pgpass-file", help="内联 db.pgpass_file")
    parser.add_argument("--db-pgpassword", help="内联 db.pgpassword")
    parser.add_argument("--db-defaults-extra-file", help="内联 db.defaults_extra_file")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        payload = build_control_payload(args)
        validate_payload(payload)
    except ValueError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2

    output_path = Path(args.output) if args.output else default_output_path(args.csv_path)
    write_control_file(payload, output_path)
    print(f"Generated control file: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
