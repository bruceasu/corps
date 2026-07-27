#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV import tool — 通过 YAML 控制文件驱动，支持 PostgreSQL / MySQL。

控制文件支持两种模式：
  模式 A：引用 config.yaml 中的 job，控制文件字段可覆盖 job 默认值
  模式 B：不引用 job，控制文件自身包含全部执行信息

用法：
  python import_tool.py scan                         # 扫描 data/incoming/*.yaml
  python import_tool.py scan --dir /path/to/dir      # 扫描指定目录
  python import_tool.py scan --dry-run               # 仅校验+输出执行计划
  python import_tool.py run-one --file xxx.yaml       # 处理单个控制文件
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Missing dependency: pyyaml")
    print("Install with: pip install pyyaml")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class JobConfig:
    """Job 配置（来自 config.yaml 或控制文件内联）"""
    name: str
    enabled: bool
    db: str                      # 引用 databases 中的 key
    target_table: str
    staging_table_prefix: str
    copy_columns: List[str]
    merge_sql_file: str


@dataclass
class ResolvedTask:
    """解析后的完整任务"""
    control_file: Path
    csv_path: Path
    import_date: str
    target_table: str
    staging_table_prefix: str
    copy_columns: List[str]
    merge_sql_file: str
    sql_file: Optional[Path]     # 预生成的 SQL 文件
    db_config: Dict[str, Any]    # 合并后的 DB 配置（含 type）
    db_name: str                 # 用于显示的 DB 实例名
    job_name: str                # job name 或 "(inline)"
    params: Dict[str, str]       # 额外模板替换参数


# ---------------------------------------------------------------------------
# ImportTool
# ---------------------------------------------------------------------------

class ImportTool:

    @staticmethod
    def _resolve_path(raw: str, anchor: Path) -> Path:
        """解析路径：展开 ~ 和环境变量，相对路径基于 anchor 目录。"""
        expanded = os.path.expandvars(os.path.expanduser(raw))
        p = Path(expanded)
        if p.is_absolute():
            return p.resolve()
        return (anchor / p).resolve()

    def __init__(self, config: Dict[str, Any], dry_run: bool = False,
                 config_dir: Optional[Path] = None) -> None:
        self.config = config
        self.dry_run = dry_run
        self._log_lock = threading.Lock()
        anchor = config_dir or Path.cwd()
        # base_dir: 支持 ~、$ENV_VAR，相对路径基于 config.yaml 所在目录
        self.base_dir = self._resolve_path(config["app"]["base_dir"], anchor)
        self.incoming_dir = self.base_dir / "data" / "incoming"
        self.processing_dir = self.base_dir / "data" / "processing"
        self.success_dir = self.base_dir / "data" / "success"
        self.failed_dir = self.base_dir / "data" / "failed"
        self.logs_dir = self.base_dir / "data" / "logs"
        # sql_dir: 支持 ~、$ENV_VAR，默认为程序安装目录下的 sql/
        install_dir = Path(__file__).resolve().parent
        raw_sql = config.get("app", {}).get("sql_dir", "")
        if raw_sql:
            self.sql_dir = self._resolve_path(raw_sql, anchor)
        else:
            self.sql_dir = install_dir / "sql"

        self._ensure_dirs()

        # databases 命名实例
        self.databases: Dict[str, Dict[str, Any]] = config.get("databases", {})

        # jobs 列表
        self.jobs: List[JobConfig] = [
            JobConfig(
                name=j["name"],
                enabled=j.get("enabled", True),

                db=j.get("db", ""),
                target_table=j.get("target_table", ""),
                staging_table_prefix=j.get("staging_table_prefix", ""),
                copy_columns=j.get("copy_columns", []),
                merge_sql_file=j.get("merge_sql_file", ""),
            )
            for j in config.get("jobs", [])
        ]

    # -----------------------------------------------------------------------
    # 目录管理
    # -----------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        for d in [
            self.incoming_dir, self.processing_dir,
            self.success_dir, self.failed_dir,
            self.logs_dir, self.sql_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # 日志
    # -----------------------------------------------------------------------

    def log(self, message: str) -> None:
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {message}"
        with self._log_lock:
            print(line)
            log_file = self.logs_dir / f"import_{dt.datetime.now().strftime('%Y%m%d')}.log"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    # -----------------------------------------------------------------------
    # 扫描控制文件
    # -----------------------------------------------------------------------

    def scan_control_files(self, scan_dir: Optional[Path] = None) -> List[Path]:
        target = scan_dir or self.incoming_dir
        files: List[Path] = []
        for ext in ("*.yaml", "*.yml"):
            files.extend(target.glob(ext))
        return sorted(files)

    # -----------------------------------------------------------------------
    # 控制文件解析
    # -----------------------------------------------------------------------

    @staticmethod
    def read_control_yaml(path: Path) -> Dict[str, Any]:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"控制文件格式错误（不是 YAML 字典）: {path}")
        return raw

    @staticmethod
    def _parse_copy_columns(value: Any) -> List[str]:
        """copy_columns 支持逗号分隔字符串或 YAML list"""
        if isinstance(value, list):
            return [str(c).strip() for c in value if str(c).strip()]
        if isinstance(value, str):
            return [c.strip() for c in value.split(",") if c.strip()]
        return []

    # -----------------------------------------------------------------------
    # Job 解析（模式 A / 模式 B）
    # -----------------------------------------------------------------------

    def find_job(self, name: str) -> JobConfig:
        for j in self.jobs:
            if j.name == name:
                return j
        raise ValueError(f"config.yaml 中不存在 job: {name}")

    def resolve_task(self, control: Dict[str, Any], control_file: Path) -> ResolvedTask:
        """根据控制文件内容 + config.yaml 合并出完整任务"""

        # 必填字段
        csv_path_str = control.get("csv_path", "")
        import_date = str(control.get("import_date", ""))
        if not csv_path_str:
            raise ValueError(f"控制文件缺少 csv_path: {control_file}")
        if not import_date:
            raise ValueError(f"控制文件缺少 import_date: {control_file}")

        csv_path = Path(os.path.expandvars(os.path.expanduser(csv_path_str)))
        sql_file_str = control.get("sql_file", "")
        sql_file = Path(os.path.expandvars(os.path.expanduser(sql_file_str))) if sql_file_str else None

        job_name_raw = control.get("job", "")

        if job_name_raw:
            # ── 模式 A：引用 job + 覆盖 ──
            job = self.find_job(job_name_raw)
            target_table = control.get("target_table") or job.target_table
            staging_table_prefix = control.get("staging_table_prefix") or job.staging_table_prefix
            copy_columns = self._parse_copy_columns(control.get("copy_columns")) or list(job.copy_columns)
            merge_sql_file = control.get("merge_sql_file") or job.merge_sql_file
            job_db_ref = job.db
            job_name = job.name
        else:
            # ── 模式 B：独立完整 ──
            target_table = control.get("target_table", "")
            staging_table_prefix = control.get("staging_table_prefix", "")
            copy_columns = self._parse_copy_columns(control.get("copy_columns"))
            merge_sql_file = control.get("merge_sql_file", "")
            job_db_ref = ""
            job_name = "(inline)"

            # 模式 B 校验：无 sql_file 时必须有足够信息生成 SQL
            if not sql_file:
                if not target_table:
                    raise ValueError(f"模式 B 无 sql_file 时，target_table 必填: {control_file}")
                if not copy_columns and not merge_sql_file:
                    raise ValueError(f"模式 B 无 sql_file 时，copy_columns 或 merge_sql_file 至少需要一个: {control_file}")

        # DB 解析
        db_config, db_name = self._resolve_db(control, job_db_ref)

        # 额外参数
        params = {str(k): str(v) for k, v in control.get("params", {}).items()} if control.get("params") else {}

        return ResolvedTask(
            control_file=control_file,
            csv_path=csv_path,
            import_date=import_date,
            target_table=target_table,
            staging_table_prefix=staging_table_prefix,
            copy_columns=copy_columns,
            merge_sql_file=merge_sql_file,
            sql_file=sql_file,
            db_config=db_config,
            db_name=db_name,
            job_name=job_name,
            params=params,
        )

    # -----------------------------------------------------------------------
    # DB 配置解析
    # -----------------------------------------------------------------------

    def _resolve_db(self, control: Dict[str, Any], job_db_ref: str) -> tuple[Dict[str, Any], str]:
        """
        DB 解析优先级：
        1. db_ref 引用 databases 实例 → 作为 base
        2. 没有 db_ref 时，使用 job 的 db 引用
        3. 控制文件内联 db.* 逐字段覆盖 base

        返回 (合并后的 db dict, 显示用 db 名)
        """
        db_ref = control.get("db_ref", "")
        inline_db: Dict[str, Any] = control.get("db", {}) or {}

        # 确定 base DB 名
        base_name = db_ref or job_db_ref

        if base_name:
            if base_name not in self.databases:
                raise ValueError(f"databases 中不存在实例: {base_name}")
            base = deepcopy(self.databases[base_name])
            display = db_ref or base_name
        elif inline_db:
            # 纯内联 DB（模式 B 无 job 引用时）
            base = {}
            display = "(inline)"
        else:
            raise ValueError("无法确定 DB 连接：控制文件无 db_ref / db，job 也无 db 引用")

        # 内联覆盖
        if inline_db:
            for k, v in inline_db.items():
                if v is not None and str(v).strip():
                    base[k] = v
            if db_ref:
                display = db_ref

        if "type" not in base:
            raise ValueError(f"DB 配置缺少 type (postgres/mysql): display={display}")

        return base, display

    # -----------------------------------------------------------------------
    # 文件移动
    # -----------------------------------------------------------------------

    def move_file(self, src: Path, dst_dir: Path) -> Path:
        dst = dst_dir / src.name
        if dst.exists():
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = dst_dir / f"{src.stem}_{ts}{src.suffix}"
        shutil.move(str(src), str(dst))
        return dst

    # -----------------------------------------------------------------------
    # Staging table 名
    # -----------------------------------------------------------------------

    @staticmethod
    def build_staging_table_name(prefix: str) -> str:
        now = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{prefix}_{now}"

    # -----------------------------------------------------------------------
    # SQL 生成
    # -----------------------------------------------------------------------

    def render_sql_template(self, template_text: str, context: Dict[str, str]) -> str:
        rendered = template_text
        for k, v in context.items():
            rendered = rendered.replace("${" + k + "}", v)
        return rendered

    def load_merge_sql(self, merge_sql_file: str) -> str:
        sql_path = self.sql_dir / merge_sql_file
        if not sql_path.exists():
            raise FileNotFoundError(f"Merge SQL 模板文件未找到: {sql_path}")
        return sql_path.read_text(encoding="utf-8")

    def generate_postgres_script(self, task: ResolvedTask, staging_table: str) -> str:
        copy_columns = ",".join(task.copy_columns)
        merge_sql_template = self.load_merge_sql(task.merge_sql_file)

        context = {
            "staging_table": staging_table,
            "target_table": task.target_table,
            "import_date": task.import_date,
        }
        context.update(task.params)
        merge_sql = self.render_sql_template(merge_sql_template, context)

        csv_path = task.csv_path.resolve().as_posix()

        return f"""
BEGIN;
SET statement_timeout = '30min';
CREATE TEMP TABLE {staging_table} ON COMMIT DROP
AS
SELECT * FROM {task.target_table}
WHERE 1 = 0;

\\copy {staging_table} ({copy_columns}) FROM '{csv_path}' WITH ( FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', ESCAPE '"', NULL '' );

{merge_sql}

COMMIT;
""".strip()

    def generate_mysql_script(self, task: ResolvedTask, staging_table: str) -> str:
        copy_columns = ",".join(f"`{c}`" for c in task.copy_columns)
        merge_sql_template = self.load_merge_sql(task.merge_sql_file)

        context = {
            "staging_table": staging_table,
            "target_table": task.target_table,
            "import_date": task.import_date,
        }
        context.update(task.params)
        merge_sql = self.render_sql_template(merge_sql_template, context)

        csv_path = str(task.csv_path.resolve()).replace("\\", "\\\\")

        return f"""
START TRANSACTION;

CREATE TEMPORARY TABLE {staging_table} LIKE {task.target_table};

LOAD DATA LOCAL INFILE '{csv_path}'
INTO TABLE {staging_table}
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\\n'
IGNORE 1 ROWS
({copy_columns});

{merge_sql}

COMMIT;
""".strip()

    # -----------------------------------------------------------------------
    # 执行 DB 命令
    # -----------------------------------------------------------------------

    def run_postgres(self, db: Dict[str, Any], sql_file: Path) -> None:
        psql_path = os.path.expandvars(os.path.expanduser(db.get("psql_path", "psql")))

        env = os.environ.copy()
        pgpass = db.get("pgpass_file")
        pgpassword = db.get("pgpassword", "")
        if pgpass:
            env["PGPASSFILE"] = str(Path(os.path.expandvars(os.path.expanduser(pgpass))).resolve())
        elif pgpassword:
            env["PGPASSWORD"] = pgpassword

        cmd = [
            psql_path,
            "-h", str(db.get("host", "localhost")),
            "-p", str(db.get("port", 5432)),
            "-U", str(db.get("user", "")),
            "-d", str(db.get("database", "")),
            "-v", "ON_ERROR_STOP=1",
            "-f", str(sql_file),
        ]

        self.log(f"[DEBUG] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        if result.stdout:
            self.log("[PSQL-STDOUT]\n" + result.stdout.rstrip())
        if result.stderr:
            self.log("[PSQL-STDERR]\n" + result.stderr.rstrip())
        if result.returncode != 0:
            raise RuntimeError(f"psql failed with code {result.returncode}")

    def run_mysql(self, db: Dict[str, Any], sql_file: Path) -> None:
        mysql_path = os.path.expandvars(os.path.expanduser(db.get("mysql_path", "mysql")))

        env = os.environ.copy()
        option_file = db.get("defaults_extra_file")

        cmd = [mysql_path]
        if option_file:
            cmd.append(f"--defaults-extra-file={str(Path(os.path.expandvars(os.path.expanduser(option_file))).resolve())}")
        cmd += [
            "--local-infile=1",
            "-h", str(db.get("host", "localhost")),
            "-P", str(db.get("port", 3306)),
            "-u", str(db.get("user", "")),
            str(db.get("database", "")),
            "-e", f"source {sql_file}",
        ]

        self.log(f"[DEBUG] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        if result.stdout:
            self.log("[MYSQL-STDOUT]\n" + result.stdout.rstrip())
        if result.stderr:
            self.log("[MYSQL-STDERR]\n" + result.stderr.rstrip())
        if result.returncode != 0:
            raise RuntimeError(f"mysql failed with code {result.returncode}")

    def _execute_sql(self, db: Dict[str, Any], sql_file: Path) -> None:
        db_type = db["type"]
        if db_type == "postgres":
            self.run_postgres(db, sql_file)
        elif db_type == "mysql":
            self.run_mysql(db, sql_file)
        else:
            raise ValueError(f"不支持的 db type: {db_type}")

    # -----------------------------------------------------------------------
    # CSV 工具
    # -----------------------------------------------------------------------

    def validate_csv_header(self, file_path: Path, expected_columns: List[str]) -> None:
        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        header_lower = [h.strip().lower() for h in header]
        expected_lower = [c.lower() for c in expected_columns]

        if header_lower[:len(expected_lower)] != expected_lower:
            raise ValueError(
                f"CSV 表头不匹配.\n"
                f"期望: {expected_columns}\n"
                f"实际: {header}"
            )

    def count_csv_rows(self, file_path: Path) -> int:
        with file_path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f) - 1

    # -----------------------------------------------------------------------
    # dry-run 输出
    # -----------------------------------------------------------------------

    def print_dry_run(self, task: ResolvedTask) -> None:
        db = task.db_config
        db_type = db.get("type", "?")
        host = db.get("host", "?")
        port = db.get("port", "?")
        database = db.get("database", "?")

        csv_exists = task.csv_path.exists()
        csv_info = f"exists, {self.count_csv_rows(task.csv_path)} rows" if csv_exists else "NOT FOUND"

        sql_info = "dynamic generation"
        if task.sql_file:
            sql_exists = task.sql_file.exists()
            sql_info = f"{task.sql_file} ({'exists' if sql_exists else 'NOT FOUND'})"

        print(f"[DRY-RUN] file={task.control_file.name} job={task.job_name} db={task.db_name}")
        print(f"  csv: {task.csv_path} ({csv_info})")
        print(f"  sql: {sql_info}")
        print(f"  target: {task.target_table}")
        print(f"  staging_prefix: {task.staging_table_prefix}")
        print(f"  copy_columns: {','.join(task.copy_columns) if task.copy_columns else '(from sql_file)'}")
        print(f"  db: {db_type} @ {host}:{port}/{database}")
        if task.merge_sql_file:
            print(f"  merge_sql: {task.merge_sql_file}")
        if task.params:
            print(f"  params: {task.params}")
        print()

    # -----------------------------------------------------------------------
    # 核心处理
    # -----------------------------------------------------------------------

    def process_control_file(self, control_path: Path) -> bool:
        self.log(f"[START] control={control_path.name}")

        try:
            control = self.read_control_yaml(control_path)
            task = self.resolve_task(control, control_path)
        except Exception as e:
            self.log(f"[FAILED] control={control_path.name} 解析失败: {e}")
            self.log(traceback.format_exc())
            return False

        if self.dry_run:
            self.print_dry_run(task)
            return True

        # 移动控制文件到 processing
        processing_control = self.move_file(control_path, self.processing_dir)

        try:
            if not task.csv_path.exists():
                raise FileNotFoundError(f"CSV 文件不存在: {task.csv_path}")

            if task.sql_file and task.sql_file.exists():
                # 使用预生成的 SQL
                self._execute_sql(task.db_config, task.sql_file)
            else:
                # 动态生成 SQL
                if not task.copy_columns:
                    raise ValueError("动态生成 SQL 需要 copy_columns")
                if not task.merge_sql_file:
                    raise ValueError("动态生成 SQL 需要 merge_sql_file")

                staging_table = self.build_staging_table_name(task.staging_table_prefix)
                db_type = task.db_config["type"]

                if db_type == "postgres":
                    sql_text = self.generate_postgres_script(task, staging_table)
                elif db_type == "mysql":
                    sql_text = self.generate_mysql_script(task, staging_table)
                else:
                    raise ValueError(f"不支持的 db type: {db_type}")

                # 写入临时 SQL 文件并执行
                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sql", encoding="utf-8") as tmp:
                    tmp.write(sql_text)
                    tmp_path = Path(tmp.name)

                try:
                    self._execute_sql(task.db_config, tmp_path)
                finally:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except OSError:
                        pass

            # 成功 → 移动到 success
            self.move_file(processing_control, self.success_dir)
            self.log(f"[SUCCESS] control={control_path.name} job={task.job_name}")
            return True

        except Exception as e:
            self.log(f"[FAILED] control={control_path.name} job={task.job_name} error={e}")
            self.log(traceback.format_exc())
            if processing_control.exists():
                self.move_file(processing_control, self.failed_dir)
            return False

    # -----------------------------------------------------------------------
    # 批量处理
    # -----------------------------------------------------------------------

    def process_all(self, scan_dir: Optional[Path] = None, workers: int = 1) -> int:
        files = self.scan_control_files(scan_dir)
        if not files:
            self.log("[INFO] 未找到 YAML 控制文件。")
            return 0

        if workers <= 1:
            # 顺序执行
            success_count = sum(1 for f in files if self.process_control_file(f))
        else:
            # 并行执行
            actual_workers = min(workers, len(files))
            self.log(f"[INFO] 并行执行: workers={actual_workers} files={len(files)}")
            success_count = 0
            with ThreadPoolExecutor(max_workers=actual_workers) as pool:
                futures = {pool.submit(self.process_control_file, f): f for f in files}
                for future in as_completed(futures):
                    if future.result():
                        success_count += 1

        self.log(f"[DONE] total={len(files)} success={success_count} failed={len(files) - success_count}")
        return 0

    def process_one(self, file_path: str) -> int:
        path = Path(file_path)
        if not path.is_absolute():
            path = self.incoming_dir / path
        if not path.exists():
            self.log(f"[ERROR] 控制文件不存在: {path}")
            return 1
        ok = self.process_control_file(path)
        return 0 if ok else 1

    # -----------------------------------------------------------------------
    # 恢复
    # -----------------------------------------------------------------------

    def recover_processing_files(self) -> None:
        for pattern in ("*.yaml", "*.yml"):
            for f in self.processing_dir.glob(pattern):
                self.log(f"[RECOVER] moving back {f.name}")
                self.move_file(f, self.incoming_dir)


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "config.yaml"


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EPILOG = """\
使用示例:
  # 扫描默认目录 (data/incoming/) 下的所有 YAML 控制文件并执行导入
  python import_tool.py scan

  # 扫描指定目录
  python import_tool.py scan --dir /path/to/controls

  # dry-run 模式：仅校验并输出执行计划，不实际执行
  python import_tool.py --dry-run scan

  # 4 线程并行执行
  python import_tool.py scan --workers 4

  # 处理单个控制文件
  python import_tool.py run-one --file data/incoming/trades.yaml

  # 使用自定义配置文件
  python import_tool.py --config /etc/import/config.yaml scan

控制文件示例 (模式 A — 引用 config.yaml 中的 job):
  job: trade_snapshot
  csv_path: /data/exports/2026-03-10_trades_both.csv
  import_date: "2026-03-10"

控制文件示例 (模式 B — 完全内联):
  csv_path: /data/exports/custom.csv
  import_date: "2026-03-10"
  target_table: my_table
  staging_table_prefix: stg_my
  copy_columns: [col1, col2, col3]
  merge_sql_file: my_merge.sql
  db_ref: production_pg
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YAML 控制文件驱动的 CSV 导入工具",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="config.yaml 路径（默认：程序目录下的 config.yaml）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅校验控制文件并输出执行计划，不实际执行")

    sub = parser.add_subparsers(dest="command", required=True)

    scan_cmd = sub.add_parser("scan", help="扫描并处理目录下的 YAML 控制文件")
    scan_cmd.add_argument("--dir", default=None, help="扫描目录（默认 data/incoming/）")
    scan_cmd.add_argument("--workers", type=int, default=1, help="并行线程数（默认 1 = 顺序执行）")

    run_one_cmd = sub.add_parser("run-one", help="处理单个控制文件")
    run_one_cmd.add_argument("--file", required=True, help="控制文件路径（YAML）")

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}", file=sys.stderr)
        return 2

    cfg = load_config(str(config_path))
    app = ImportTool(cfg, dry_run=args.dry_run, config_dir=config_path.resolve().parent)

    if args.command == "scan":
        scan_dir = Path(args.dir) if args.dir else None
        return app.process_all(scan_dir, workers=args.workers)
    if args.command == "run-one":
        return app.process_one(args.file)

    return 1


if __name__ == "__main__":
    sys.exit(main())
