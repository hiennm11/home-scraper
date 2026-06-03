# Issue tracker: GitHub

Issues và PRD của repo này sống trên GitHub Issues. Dùng `gh` CLI cho mọi thao tác.

## Conventions

- **Tạo issue**: `gh issue create --title "..." --body "..."`
- **Đọc issue**: `gh issue view <number> --comments`
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments`
- **Comment**: `gh issue comment <number> --body "..."`
- **Gán/gỡ label**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Repo được suy từ `git remote -v` — `gh` tự động detect khi chạy trong clone.
