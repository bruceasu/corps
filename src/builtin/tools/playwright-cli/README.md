# playwright-cli

Run Playwright CLI browser automation commands through corps as an external tool.

This tool expects `playwright-cli` to already exist in `PATH`.

## Requirements

- Node.js 18+
- `playwright-cli`

Recommended install:

```bash
npm install -g @playwright/cli@latest
```

If the command is not found, the tool fails fast and prints the recommended install command.

Reference:

- https://github.com/microsoft/playwright-cli
- https://github.com/microsoft/playwright

## Supported actions

- `open`
- `goto`
- `snapshot`
- `click`
- `fill`
- `type`
- `press`
- `screenshot`
- `close`
- `list`
- `show`
- `close-all`
- `kill-all`
- `check`
- `uncheck`
- `text-content`

## Examples

Dry-run:

```bash
python run.py --action open --url https://example.com --session demo --dry-run true
```

Open and inspect:

```bash
python run.py --action open --url https://example.com --session demo
python run.py --action snapshot --session demo
python run.py --action screenshot --session demo
python run.py --action close --session demo
```
