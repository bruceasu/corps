# pgsql-client

自包含的 PostgreSQL tool，优先使用系统已安装的官方 `psql` 客户端；如果环境里没有，再回退到当前目录 `bin/` 下的 `psql-go` 精简版。

## 目录约定

- `tool.yaml`：tool 定义
- `run.py`：跨平台调度脚本
- `bin/psql-go` / `bin/psql-go.exe`：本地精简版客户端
- `pgpass.conf`：本地默认口令文件

## 默认行为

- 先查找 PATH 中的 `psql`
- 未找到时，使用 `./bin/psql-go` 或 `./bin/psql-go.exe`
- 如果没有显式传 `passFile`，默认使用同目录的 `pgpass.conf`

## 推荐分发方式

把整个 `pgsql-client` 目录一起分发，不要依赖源码树中的其它路径。

## 示例

```bash
java -jar corps.jar tool run \
  --name pgsql-client \
  --args-json "{\"query\":\"SELECT 1\",\"database\":\"demo\",\"user\":\"reader\",\"tuplesOnly\":\"true\"}" \
  --confirm
```
