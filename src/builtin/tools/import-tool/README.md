# import-tool

自包含的 CSV 导入工具，基于 `import_tool.py`，支持 PostgreSQL / MySQL。

## 目录约定

- `tool.yaml`：tool 定义
- `run.py`：统一入口，负责选择数据库客户端并补丁配置
- `import_tool.py`：原始导入程序
- `config.yaml`：默认配置
- `sql/`：merge SQL 模板
- `bin/`：本地 bundled `psql-go` / `mysql-go`
- `config/pgpass.conf`：PostgreSQL 本地口令文件
- `config/mysql.cnf`：MySQL 本地认证配置

## 默认行为

- 优先使用系统 PATH 中的原生 `psql` / `mysql`
- 如果系统中没有，则回退到当前目录 `bin/` 下的 bundled 精简版
- 默认使用本目录中的 `config.yaml`
- wrapper 会自动把配置中的 `psql_path` / `mysql_path` 重写到当前机器可用的程序路径

## 常见用法

扫描默认目录：

```bash
java -jar corps.jar tool run \
  --name import-tool \
  --args-json "{\"command\":\"scan\",\"dryRun\":\"true\"}" \
  --confirm
```

处理单个控制文件：

```bash
java -jar corps.jar tool run \
  --name import-tool \
  --args-json "{\"command\":\"run-one\",\"file\":\"D:/exports/demo.control.yaml\"}" \
  --confirm
```
