# trading-strategy-data-pipeline

Data pipeline for the Trading Strategy Platform.

## Branching Strategy

This repository follows a **4-tier** branching model.

```
[feature/*]  ──>  [deployment]  ──>  [staging]  ──>  [main]
```

### Branches

| Branch | Purpose | Base | Protected |
|--------|---------|------|-----------|
| `main` | Production. Never push directly. | — | Yes |
| `staging` | Pre-production. Always exists. PRs from `deployment` only. | `main` | Yes |
| `deployment` | Development integration. Always exists. PRs from `feature/*` only. | `staging` | Yes |
| `feature/*` | All dev work. Short-lived. | `deployment` | No |

### Rules

1. **`main` is production** — direct pushes are forbidden. Only `staging` can PR into it.
2. **`staging` is pre-production** — always exists. Receives PRs from `deployment`. PRs into `main` for releases.
3. **`deployment` is the dev integration branch** — always exists, branched from `staging`. All feature branches are cut from here and PR back here.
4. **Feature branches** — always branched from `deployment`. Named `feature/<short-description>`. PR back into `deployment` when done.

### Workflow

```
main (prod)
  └── staging (pre-prod)            ← branched from main
        └── deployment (dev/integration) ← branched from staging
              ├── feature/my-feature     ← branched from deployment
              ├── feature/another        ← branched from deployment
              └── ...
```

**Merge flow:**
```
feature/* → deployment → staging → main
```

### Quick-start for a new feature

```bash
# 1. Make sure your local deployment branch is up to date
git checkout deployment
git pull origin deployment

# 2. Branch off deployment
git checkout -b feature/my-feature

# 3. Do your work, then push
git push -u origin feature/my-feature

# 4. Open a PR: feature/my-feature → deployment
# 5. After testing, open a PR: deployment → staging
# 6. After sign-off, open a PR: staging → main
```

### For AI agents (Claude Code)

- **Never push directly to `main`, `staging`, or `deployment`.**
- All development work goes on a `feature/*` branch cut from `deployment`.
- PRs always flow: `feature/*` → `deployment` → `staging` → `main`.
- When creating a new repository under this project, apply the same 4-tier structure: `main`, `staging`, `deployment`, `feature/*`.
