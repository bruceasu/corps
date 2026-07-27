# playwright-ui-smoke-test

Run a lightweight browser-based UI smoke test using `playwright-cli`.

## Flow

1. Open the target page
2. Capture a Playwright CLI snapshot
3. Capture a screenshot
4. Ask the LLM to produce a concise QA-style smoke report
5. Close the session

## Example

```bash
java -jar target/corps-1.0-SNAPSHOT.jar skill run \
  --name playwright-ui-smoke-test \
  --input-json "{\"url\":\"https://example.com\",\"session\":\"demo\",\"expectedText\":\"Example Domain\"}" \
  --provider groq \
  --model llama-3.1-8b-instant \
  --confirm \
  --config D:/03_projects/suk/corps/corps.properties
```

Save the report to a specific file:

```bash
java -jar target/corps-1.0-SNAPSHOT.jar skill run \
  --name playwright-ui-smoke-test \
  --input-json "{\"url\":\"https://example.com\",\"session\":\"demo\",\"reportOutput\":\"D:/tmp/ui-smoke-report.md\"}" \
  --provider groq \
  --model llama-3.1-8b-instant \
  --confirm \
  --config D:/03_projects/suk/corps/corps.properties
```

## Notes

- This skill depends on the external `playwright-cli` tool.
- Install `playwright-cli` first:

```bash
npm install -g @playwright/cli@latest
```

- If `reportOutput` is omitted, the report is saved under `workspace/tools/playwright-cli/output/` using the session name when available.
