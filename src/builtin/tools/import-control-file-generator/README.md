# import-control-file-generator

为现有 CSV 生成 `import-tool` 可直接消费的 YAML 控制文件。

## 用途

- 根据 `job + csvPath + importDate` 快速生成标准 control file
- 也支持不依赖 `job` 的完整 inline 模式
- 方便 skill 在“发现 CSV -> 生成控制文件 -> 调 import-tool 导入”链路中直接调用

## 依赖

- Python
- `pyyaml`
- 共享使用 `../import-tool/generate_control_file.py`

## 示例

```bash
java -jar corps.jar tool run \
  --name import-control-file-generator \
  --args-json "{\"job\":\"trade_snapshot\",\"csvPath\":\"D:/exports/demo.csv\",\"importDate\":\"2026-05-03\"}" \
  --confirm
```
