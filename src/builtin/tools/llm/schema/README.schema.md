# Tool/Skill 输出 Schema 约定

简要说明：该约定定义了工具/skill 返回给调度器或上游组件的标准结构，优先保证可机器解析的 `result` 字段，并提供统一的错误与元数据描述。

- Schema 文件：[workspace/tools/llm/schema/tool_response.schema.json](workspace/tools/llm/schema/tool_response.schema.json#L1-L200)
- 示例响应：[workspace/tools/llm/schema/example_response.json](workspace/tools/llm/schema/example_response.json#L1-L200)

主要字段说明：
- `version`：Schema 版本（必填）。
- `status`：`success|partial|error`（必填）。
- `result`：机器可解析的输出（成功或部分成功时应存在）。
- `error`：错误详情（出错或部分成功时应存在）。
- `metadata`：运行时信息（provider、model、promptLength 等，可选且可扩展）。
- `human_readable`：可选的人类可读文本（不依赖于解析器）。

集成建议：
1. 在调用 LLM 时，要求模型仅输出符合 schema 的 JSON（或在 `---json---` fenced block 中）。
2. 使用 `--schema-file` 或 `--schema` 将 `tool_response.schema.json` 传入 `workspace/tools/llm/run.py`，并启用 `--require-schema` 以强制校验通过。
3. 校验失败时，调度器应记录 `schemaErrors` 并在必要时触发重试或人工审查。

CLI 示例：
```bash
python workspace/tools/llm/run.py \
  --prompt '请返回符合 schema 的 JSON 响应' \
  --format json \
  --schema-file workspace/tools/llm/schema/tool_response.schema.json \
  --require-schema
```

兼容性与演进：
- 若需变更 schema，请更新 `version` 并采用向后兼容策略（新增字段为可选）。
- 对重大变更，按 semver 增加主版本并通知上游消费者。
