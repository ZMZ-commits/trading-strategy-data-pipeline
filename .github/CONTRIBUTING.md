# Contributing

Please read the branching strategy in [CLAUDE.md](../CLAUDE.md) before contributing.

## Branch rules (enforced)

```
[feature/*]  ──>  [deployment]  ──>  [staging]  ──>  [main]
```

| Branch | Rule |
|--------|------|
| `main` | No direct pushes. PR from `staging` only. |
| `staging` | No direct pushes. PR from `deployment` only. |
| `deployment` | No direct pushes. PR from `feature/*` only. |
| `feature/*` | Branch from `deployment`. |

## Opening a PR

- Feature work → open PR into **`deployment`**
- Integration → open PR from **`deployment`** into **`staging`**
- Release → open PR from **`staging`** into **`main`**
