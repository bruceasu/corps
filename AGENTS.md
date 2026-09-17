# AGENTS.md
This repository uses OpenSpec-lite TOML workflow.
Before coding:
- read .ai/<task>/task.toml if exists
- read openspec/changes/<task>/tasks.md if exists
- read design.md if exists
- read related specs under openspec/specs/
- archived changes live under openspec/changes/archive/

Rules:
- one task at a time
- avoid unrelated refactors
- preserve backward compatibility
- update TODO and Verification
- use %% notes for uncertainties
