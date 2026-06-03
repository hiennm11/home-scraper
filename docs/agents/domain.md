# Domain Docs

Single-context repo:

```
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Quy tắc tiêu thụ

- Đọc `CONTEXT.md` ở root trước khi explore codebase.
- Đọc `docs/adr/` nếu có ADR liên quan đến area đang làm.
- Nếu các file này chưa tồn tại → **im lặng bỏ qua**, đừng flag hay đề xuất tạo. Skill `/grill-with-docs` sẽ tạo lazy khi có terms/decisions thực sự.
- Dùng đúng glossary từ `CONTEXT.md`, đừng tự bịa synonym.
- Nếu output mâu thuẫn với ADR có sẵn → flag rõ ràng, không âm thầm override.
