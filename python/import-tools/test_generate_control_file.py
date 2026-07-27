import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import generate_control_file
import import_tool


class GenerateControlFileTest(unittest.TestCase):

    def test_build_control_payload_for_job_mode(self):
        args = Namespace(
            job="trade_snapshot",
            csv_path="/data/exports/2026-03-10_trades_both.csv",
            import_date="2026-03-10",
            output=None,
            target_table=None,
            staging_table_prefix=None,
            copy_columns="",
            copy_column=[],
            merge_sql_file=None,
            db_ref=None,
            sql_file=None,
            param=[],
            db_type=None,
            db_psql_path=None,
            db_mysql_path=None,
            db_host=None,
            db_port=None,
            db_database=None,
            db_user=None,
            db_pgpass_file=None,
            db_pgpassword=None,
            db_defaults_extra_file=None,
        )

        payload = generate_control_file.build_control_payload(args)
        self.assertEqual("trade_snapshot", payload["job"])
        self.assertEqual("/data/exports/2026-03-10_trades_both.csv", payload["csv_path"])
        self.assertEqual("2026-03-10", payload["import_date"])
        self.assertNotIn("copy_columns", payload)

    def test_build_control_payload_for_standalone_mode(self):
        args = Namespace(
            job=None,
            csv_path="/data/exports/custom.csv",
            import_date="2026-03-10",
            output=None,
            target_table="risk_manage.custom_report",
            staging_table_prefix="staging_custom_report",
            copy_columns="import_date,login,symbol,profit",
            copy_column=["volume"],
            merge_sql_file="custom_merge.sql",
            db_ref="pg_local",
            sql_file=None,
            param=["source=manual"],
            db_type=None,
            db_psql_path=None,
            db_mysql_path=None,
            db_host=None,
            db_port=None,
            db_database=None,
            db_user=None,
            db_pgpass_file=None,
            db_pgpassword=None,
            db_defaults_extra_file=None,
        )

        payload = generate_control_file.build_control_payload(args)
        generate_control_file.validate_payload(payload)

        self.assertEqual(
            ["import_date", "login", "symbol", "profit", "volume"],
            payload["copy_columns"],
        )
        self.assertEqual({"source": "manual"}, payload["params"])
        self.assertEqual("pg_local", payload["db_ref"])

    def test_write_control_file_is_resolvable_by_import_tool(self):
        repo_python_dir = Path(__file__).resolve().parent
        config = import_tool.load_config(str(repo_python_dir / "config.yaml"))
        app = import_tool.ImportTool(config, dry_run=True, config_dir=repo_python_dir)

        args = Namespace(
            job="trades_statistics_snapshot",
            csv_path="/data/exports/weekly_2026-03-02_2026-03-08_trades_statistics_by_region.csv",
            import_date="2026-03-02",
            output=None,
            target_table="risk_manage.trades_statistics_weekly_snapshot",
            staging_table_prefix=None,
            copy_columns="",
            copy_column=[],
            merge_sql_file=None,
            db_ref=None,
            sql_file=None,
            param=[],
            db_type=None,
            db_psql_path=None,
            db_mysql_path=None,
            db_host=None,
            db_port=None,
            db_database=None,
            db_user=None,
            db_pgpass_file=None,
            db_pgpassword=None,
            db_defaults_extra_file=None,
        )

        payload = generate_control_file.build_control_payload(args)
        generate_control_file.validate_payload(payload)

        with tempfile.TemporaryDirectory() as td:
            control_path = Path(td) / "weekly.control.yaml"
            generate_control_file.write_control_file(payload, control_path)
            control = app.read_control_yaml(control_path)
            task = app.resolve_task(control, control_path)

        self.assertEqual("trades_statistics_snapshot", task.job_name)
        self.assertEqual("risk_manage.trades_statistics_weekly_snapshot", task.target_table)
        self.assertEqual("trades_statistics_snapshot_merge.sql", task.merge_sql_file)

    def test_validate_payload_allows_standalone_sql_file_mode(self):
        payload = {
            "csv_path": "/data/exports/custom.csv",
            "import_date": "2026-03-10",
            "sql_file": "/data/sql/custom.sql",
            "db_ref": "pg_local",
        }

        generate_control_file.validate_payload(payload)

    def test_examples_are_resolvable_by_import_tool(self):
        repo_python_dir = Path(__file__).resolve().parent
        config = import_tool.load_config(str(repo_python_dir / "config.yaml"))
        app = import_tool.ImportTool(config, dry_run=True, config_dir=repo_python_dir)

        example_dir = repo_python_dir / "examples"
        example_files = sorted(example_dir.glob("*.yaml"))
        self.assertTrue(example_files)

        for example_file in example_files:
            with self.subTest(example=example_file.name):
                control = app.read_control_yaml(example_file)
                task = app.resolve_task(control, example_file)
                self.assertTrue(task.import_date)
                self.assertTrue(task.csv_path)


if __name__ == "__main__":
    unittest.main()
