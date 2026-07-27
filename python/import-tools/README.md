# import_tool — YAML 控制文件驱动的 CSV 导入工具

## 功能
- 通过 **YAML 控制文件** 描述：导入哪个 CSV、导入到哪个表、用哪个 DB
- 支持两种模式：
  - **模式 A**：引用 `config.yaml` 中预定义的 job（可选覆盖任意字段）
  - **模式 B**：控制文件独立包含全部执行信息，无需 job 引用
- 通过 native client 调用 `psql` / `mysql`
- 先导入 staging table，再执行 merge/upsert SQL
- 自动归档控制文件（`processing/` → `success/` 或 `failed/`）
- `--dry-run` 模式：仅校验 + 输出执行计划，不实际执行

## 架构图
```text
Python CLI (import_tool.py)
 ├── 接收控制文件（run-one 单个 / scan 批量）
 ├── 解析控制文件 → 合并 job 定义（模式 A）或直接使用（模式 B）
 ├── 解析 DB 配置（db_ref 引用 / 内联覆盖 / job 默认）
 ├── 生成临时 staging table + merge SQL 脚本
 ├── 调用 psql / mysql 执行
 ├── 归档控制文件（success / failed）
 └── 写日志
```

## 目录结构
```
python/
├── import_tool.py          # 主程序
├── config.yaml             # 全局配置（databases + jobs）
├── sql/                    # SQL merge 模板
│   ├── trade_snapshot_merge.sql
│   ├── trade_snapshot_no_tick_merge.sql
│   └── trades_statistics_snapshot_merge.sql
└── data/
    ├── incoming/           # 待处理的 YAML 控制文件
    ├── processing/         # 正在处理（自动移入）
    ├── success/            # 处理成功
    ├── failed/             # 处理失败
    └── logs/               # 执行日志
```

## 安装依赖

```bash
pip install pyyaml
```

---

## CLI 命令

### 处理单个控制文件

```bash
python import_tool.py run-one --file /path/to/control.yaml
```

### 扫描并处理目录下所有控制文件

```bash
# 默认扫描 data/incoming/
python import_tool.py scan

# 扫描指定目录
python import_tool.py scan --dir /path/to/exports/
```

### dry-run 模式（仅校验，不执行）

```bash
python import_tool.py --dry-run run-one --file control.yaml
python import_tool.py --dry-run scan
```

### 指定 config 路径

```bash
python import_tool.py --config /path/to/config.yaml run-one --file control.yaml
```

默认 config 路径为程序目录下的 `config.yaml`。

---

## config.yaml 详细说明

`config.yaml` 包含两部分：**databases**（数据库实例定义）和 **jobs**（Job 预定义）。

### 完整示例

```yaml
app:
  base_dir: .                              # 工作目录基准路径

# ── 数据库实例定义 ──
# 每个 key 是一个实例名（供 job 和控制文件引用）
databases:
  pg_local:                                # 实例名，控制文件用 db_ref: pg_local 引用
    type: postgres                         # 必填：postgres | mysql
    psql_path: psql                        # psql 可执行文件路径
    host: localhost
    port: 5432
    database: riskdb
    user: postgres
    pgpass_file: ./config/pgpass.conf      # PostgreSQL 密码文件

  pg_prod:
    type: postgres
    psql_path: /usr/bin/psql
    host: prod-db.internal
    port: 5432
    database: riskdb
    user: riskmanager
    pgpass_file: /etc/pgpass.conf

  mysql_local:
    type: mysql
    mysql_path: mysql                      # mysql 可执行文件路径
    host: localhost
    port: 3306
    database: riskdb
    user: root
    defaults_extra_file: ./config/mysql.cnf  # MySQL 认证配置

# ── Job 预定义 ──
# 控制文件通过 job: <name> 引用，减少重复配置
jobs:
  - name: trade_snapshot                   # Job 名称（控制文件中 job: trade_snapshot）
    enabled: true                          # 是否启用
    db: pg_local                           # 默认使用哪个 DB 实例
    target_table: risk_manage.trade_snapshot_data   # 目标表（schema.table）
    staging_table_prefix: staging_trade_snapshot     # 临时表前缀
    copy_columns:                          # CSV → staging 的列名列表（顺序与 CSV 一致）
      - import_date
      - order_id
      - ticket
      - login
      - symbol
      - side
      - volume
      - volume_label
      - open_time
      - open_time_jst
      - close_time_jst
      - close_time
      - hold_time
      - hold_label
      - open_price
      - close_price
      - profit
      - swaps
      - commission
      - reason
      - flag
      - client_type
      - business_type
      - platform
      - tick_1s_label
      - tick_1s_rate
      - tick_5s_label
      - tick_5s_rate
      - tick_10s_label
      - tick_10s_rate
      - tick_30s_label
      - tick_30s_rate
      - tick_60s_label
      - tick_60s_rate
      - tick_120s_label
      - tick_120s_rate
      - tick_profit_closedprofit_count
    merge_sql_file: trade_snapshot_merge.sql  # sql/ 目录下的 merge 模板

  - name: trade_snapshot_no_tick           # 无 tick 列版本
    enabled: true
    db: pg_local
    target_table: risk_manage.trade_snapshot_data
    staging_table_prefix: staging_trade_snapshot_no_tick
    copy_columns:
      - import_date
      - order_id
      - ticket
      - login
      - symbol
      - side
      - volume
      - volume_label
      - open_time
      - open_time_jst
      - close_time_jst
      - close_time
      - hold_time
      - hold_label
      - open_price
      - close_price
      - profit
      - swaps
      - commission
      - reason
      - flag
      - client_type
      - business_type
      - platform
    merge_sql_file: trade_snapshot_no_tick_merge.sql

  - name: trades_statistics_snapshot
    enabled: true
    db: pg_local
    target_table: risk_manage.trades_statistics_snapshot
    staging_table_prefix: staging_trades_statistics_snapshot
    copy_columns:
      - platform
      - business_type
      - login
      - symbol
      - source_type
      - region
      - profit
      - swap
      - commission
      - volume
      - base_volume
      - count
      - 10m_bucket_count
      - tickprofitcount
      - buy_pnl
      - buy_base_volume
      - buy_count
      - sell_pnl
      - sell_base_volume
      - sell_count
      - positive_pnl
      - positive_base_volume
      - positive_count
      - negative_pnl
      - negative_base_volume
      - negative_count
      - lotlabel_pnl_map
      - lotlabel_base_volume_map
      - lotlabel_count_map
      - hold_label_pnl_map
      - hold_label_base_map
      - hold_label_count_map
    merge_sql_file: trades_statistics_snapshot_merge.sql
```

### 字段参考

| 区域 | 字段 | 必填 | 说明 |
|------|------|------|------|
| **databases.\<name\>** | `type` | ✅ | `postgres` 或 `mysql` |
| | `host` / `port` / `database` / `user` | ✅ | 连接信息 |
| | `psql_path` | postgres | `psql` 可执行文件路径 |
| | `pgpass_file` | postgres | PostgreSQL 密码文件路径 |
| | `mysql_path` | mysql | `mysql` 可执行文件路径 |
| | `defaults_extra_file` | mysql | MySQL 认证配置文件路径 |
| **jobs[]** | `name` | ✅ | Job 名称，控制文件通过此名称引用 |
| | `enabled` | — | 默认 `true` |
| | `db` | ✅ | 引用 databases 中的实例名 |
| | `target_table` | ✅ | 目标表（schema.table） |
| | `staging_table_prefix` | ✅ | 临时表名前缀 |
| | `copy_columns` | ✅ | CSV 列名列表（顺序必须与 CSV 列一致） |
| | `merge_sql_file` | ✅ | `sql/` 下的 merge 模板文件名 |

---

## 控制文件（CONTROL YAML）详细说明

控制文件是 import_tool 的核心输入，每个控制文件描述一次导入任务。

### 必填字段

| 字段 | 说明 |
|------|------|
| `csv_path` | CSV 文件的绝对路径 |
| `import_date` | 导入日期（`yyyy-MM-dd` 格式），用于 SQL 模板参数替换 |

### 可选字段

| 字段 | 适用模式 | 说明 |
|------|---------|------|
| `job` | 模式 A | 引用 config.yaml 中的 job 名称 |
| `db_ref` | A / B | 切换到其他 DB 实例（覆盖 job 默认 DB） |
| `target_table` | A（覆盖）/ B | 目标表 |
| `staging_table_prefix` | A（覆盖）/ B | 临时表前缀 |
| `copy_columns` | A（覆盖）/ B | CSV 列名列表 |
| `merge_sql_file` | A（覆盖）/ B | merge SQL 模板文件名 |
| `sql_file` | A / B | 预生成的 SQL 文件路径（有则跳过 SQL 生成） |
| `db` | B | 内联 DB 配置（直接在控制文件中定义连接信息） |
| `params` | A / B | 额外的模板变量，会注入 SQL 模板渲染上下文 |

### DB 解析优先级

```text
1. db_ref → 引用 config.yaml databases 中的实例（最高优先）
2. job.db → 使用 job 定义中的默认 DB（模式 A 时）
3. db（内联）→ 控制文件内嵌连接信息（模式 B 时）
内联 db 字段可部分覆盖 db_ref 解析后的值。
```

---

## 控制文件示例

### 示例 1：模式 A — 最简引用

最常见的用法。Java 端自动生成此格式。

```yaml
# 2026-03-10_trades_both.csv.control.yaml
job: trade_snapshot
csv_path: /data/exports/2026-03-10_trades_both.csv
import_date: "2026-03-10"
```

- `job: trade_snapshot` 引用 config.yaml 预定义 job
- `target_table`、`copy_columns`、`merge_sql_file`、`db` 全部使用 job 默认值
- 控制文件只需 3 行

### 示例 2：模式 A — 引用 + 切换 DB

导入到生产环境数据库（覆盖 job 的默认 db）：

```yaml
# 2026-03-10_trades_both_prod.control.yaml
job: trade_snapshot
csv_path: /data/exports/2026-03-10_trades_both.csv
import_date: "2026-03-10"
db_ref: pg_prod                            # 覆盖 job 默认的 pg_local → pg_prod
```

### 示例 3：模式 A — 引用 + 覆盖目标表

临时导入到测试表（仅覆盖 target_table）：

```yaml
# test_import.control.yaml
job: trade_snapshot
csv_path: /data/exports/2026-03-10_trades_both.csv
import_date: "2026-03-10"
target_table: risk_manage_test.trade_snapshot_data   # 覆盖 job 默认目标表
```

### 示例 4：模式 A — 引用 + 覆盖多个字段

覆盖 columns 和 merge SQL（例如实验性导入）：

```yaml
# custom_import.control.yaml
job: trade_snapshot
csv_path: /data/exports/2026-03-10_trades_both.csv
import_date: "2026-03-10"
db_ref: pg_prod
target_table: risk_manage_staging.trade_snapshot_exp
staging_table_prefix: staging_experiment
merge_sql_file: trade_snapshot_merge_v2.sql          # 使用自定义 merge SQL
```

### 示例 5：模式 A — 使用预生成 SQL

当 SQL 已经预先生成好，跳过模板渲染：

```yaml
# prebuilt_sql.control.yaml
job: trade_snapshot
csv_path: /data/exports/2026-03-10_trades_both.csv
import_date: "2026-03-10"
sql_file: /data/exports/2026-03-10_trades_both.csv.sql   # 跳过 SQL 生成，直接执行此文件
```

### 示例 6：模式 A — 带额外模板参数

通过 `params` 向 SQL 模板注入自定义变量：

```yaml
# with_params.control.yaml
job: trades_statistics_snapshot
csv_path: /data/exports/2026-03-10_statistics_by_region.csv
import_date: "2026-03-10"
params:
  region_filter: tokyo                     # 模板中用 ${region_filter} 引用
```

### 示例 7：模式 B — 完全独立（无 job 引用）

完全自包含，不依赖 config.yaml 中的 job 定义：

```yaml
# standalone.control.yaml
csv_path: /data/exports/custom_report.csv
import_date: "2026-03-10"
target_table: risk_manage.custom_report
staging_table_prefix: staging_custom
copy_columns:
  - date
  - account_id
  - symbol
  - pnl
  - volume
merge_sql_file: custom_report_merge.sql
db_ref: pg_local                           # 引用 config.yaml 中的 DB 实例
```

### 示例 8：模式 B — 内联 DB 配置

完全独立，连 DB 配置也不引用 config.yaml：

```yaml
# fully_inline.control.yaml
csv_path: /data/exports/adhoc_data.csv
import_date: "2026-03-10"
target_table: public.adhoc_import
staging_table_prefix: staging_adhoc
copy_columns:
  - col_a
  - col_b
  - col_c
merge_sql_file: adhoc_merge.sql
db:
  type: postgres
  psql_path: /usr/bin/psql
  host: 192.168.1.100
  port: 5432
  database: analytics
  user: etl_user
  pgpass_file: /home/etl/.pgpass
```

---

## 执行示例

### 场景 1：Java 生成控制文件 → Python 执行

Java 端运行 `DailyStatCommand` 后，在 `exports/` 目录生成 CSV 和控制文件：

```
exports/
├── 2026-03-10_trades_both.csv
├── 2026-03-10_trades_both.csv.control.yaml      ← job: trade_snapshot
├── 2026-03-10_trades_close_only.csv
├── 2026-03-10_trades_close_only.csv.control.yaml ← job: trade_snapshot_no_tick
├── 2026-03-10_trades_open_only.csv
├── 2026-03-10_trades_open_only.csv.control.yaml  ← job: trade_snapshot_no_tick
├── 2026-03-10_import_by_region.control.yaml      ← job: trades_statistics_snapshot
└── ...
```

逐个执行：
```bash
python import_tool.py run-one \
  --file exports/2026-03-10_trades_both.csv.control.yaml
```

批量执行：
```bash
python import_tool.py scan --dir exports/
```

先 dry-run 验证再执行：
```bash
# 步骤1：dry-run 检查
python import_tool.py --dry-run scan --dir exports/

# 步骤2：确认无误后执行
python import_tool.py scan --dir exports/
```

### 场景 2：导入到生产数据库

```bash
# 准备控制文件（手动或脚本修改 db_ref）
cat > /tmp/prod_import.yaml << 'EOF'
job: trade_snapshot
csv_path: /data/exports/2026-03-10_trades_both.csv
import_date: "2026-03-10"
db_ref: pg_prod
EOF

# dry-run 验证
python import_tool.py --dry-run run-one --file /tmp/prod_import.yaml

# 执行
python import_tool.py run-one --file /tmp/prod_import.yaml
```

### 场景 3：使用自定义 config

```bash
python import_tool.py --config /etc/import/prod-config.yaml \
  run-one --file control.yaml
```

---

## SQL 模板说明

merge SQL 模板放在 `sql/` 目录下，支持以下占位符（`${variable}` 格式）：

| 占位符 | 来源 | 说明 |
|--------|------|------|
| `${staging_table}` | 自动生成 | 临时 staging 表名 |
| `${target_table}` | job / 控制文件 | 最终目标表名 |
| `${import_date}` | 控制文件 | 导入日期（`yyyy-MM-dd`） |
| 自定义 | `params` | 控制文件 `params` 中的键值对 |

### 当前可用的模板

| 模板文件 | 对应 Job | 说明 |
|---------|---------|------|
| `trade_snapshot_merge.sql` | `trade_snapshot` | 含 tick 列的交易快照 merge（ON CONFLICT 7 列） |
| `trade_snapshot_no_tick_merge.sql` | `trade_snapshot_no_tick` | 无 tick 列版本（不覆盖 tick 数据） |
| `trades_statistics_snapshot_merge.sql` | `trades_statistics_snapshot` | 统计快照 merge（ON CONFLICT 5 列） |

---

## 需要手工准备的东西

### PostgreSQL
- 确保 `psql` 可执行（或在 config.yaml 中指定 `psql_path` 的完整路径）
- 创建 `pgpass.conf`（格式：`host:port:database:user:password`），并设置 `chmod 600`

### MySQL
- 确保 `mysql` 可执行（或在 config.yaml 中指定 `mysql_path` 的完整路径）
- 创建 `defaults-extra-file`（`mysql.cnf`）并配置认证信息：
  ```ini
  [client]
  password=your_password
  ```
