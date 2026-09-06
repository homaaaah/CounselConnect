# Frontend Features

Feature folders hold domain-specific frontend code.

Current feature folders:

```text
accounts/
appointments/
assistant/
auth/
content/
counselor/
enrollment/
messaging/
sos/
wellness/
```

When a feature grows, prefer this shape:

```text
{feature}/
  api/          API calls for this feature
  components/   UI used only by this feature
  hooks/        React hooks used only by this feature
  pages/        Feature route pages
  index.ts      Public exports
```

Shared UI belongs in `src/components`, and shared API transport belongs in
`src/services`.

