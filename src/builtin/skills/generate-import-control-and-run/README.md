# generate-import-control-and-run

把两个外部 tool 串起来：

1. `import-control-file-generator`
2. `import-tool`

适合在 skill 或 chat 中处理“我已经有 CSV，请帮我生成控制文件并导入”这种需求。

## 示例

```bash
java -jar corps.jar skill run \
  --name generate-import-control-and-run \
  --args-json "{\"job\":\"trade_snapshot\",\"csvPath\":\"D:/exports/demo.csv\",\"importDate\":\"2026-05-03\",\"dryRun\":\"true\"}" \
  --confirm
```
