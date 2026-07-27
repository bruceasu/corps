# mysql-client

自包含的 MySQL tool，优先使用系统已安装的官方 `mysql` 客户端；如果环境里没有，再回退到当前目录 `bin/` 下的 `mysql-go` 精简版。

## 目录约定

- `tool.yaml`：tool 定义
- `run.py`：跨平台调度脚本
- `bin/mysql-go` / `bin/mysql-go.exe`：本地精简版客户端
- `my.cnf`：本地默认配置文件
- `.my.cnf.example`：示例配置

## 默认行为

- 先查找 PATH 中的 `mysql`
- 未找到时，使用 `./bin/mysql-go` 或 `./bin/mysql-go.exe`
- 如果没有显式传 `defaultsFile`，默认使用同目录的 `my.cnf`

## 推荐分发方式

把整个 `mysql-client` 目录一起分发，不要依赖源码树中的其它路径。

## 示例

```bash
java -jar corps.jar tool run \
  --name mysql-client \
  --args-json "{\"query\":\"SELECT 1\",\"database\":\"demo\",\"user\":\"reader\",\"tuplesOnly\":\"true\"}" \
  --confirm
```
