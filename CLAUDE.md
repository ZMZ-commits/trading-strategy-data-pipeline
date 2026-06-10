# Trading Strategy Platform

## Branching Strategy

This repository follows a **3-tier** branching model with three permanent long-lived branches.

```
[feature/*]  ──>  [dev]  ──>  [staging]  ──>  [main]
```

### Branches

| Branch | Purpose | Base | Protected |
|--------|---------|------|-----------|
| `main` | Production. Never push directly. | — | Yes — cannot be deleted or pushed to |
| `staging` | Pre-production. Never push directly. | `main` | Yes — cannot be deleted or pushed to |
| `dev` | Development integration. Never push directly. | `staging` | Yes — cannot be deleted or pushed to |
| `feature/*` | All dev work. Short-lived. Deleted after merge. | `dev` | No |

### Rules

1. **`main` is production** — only `staging` can PR into it. No direct pushes ever.
2. **`staging` is pre-production** — only `dev` can PR into it. No direct pushes ever.
3. **`dev` is the dev integration branch** — only `feature/*` branches can PR into it. No direct pushes ever.
4. **Feature branches** — always branched from `dev`. Named `feature/<short-description>`. PR back into `dev` when done, then **deleted**.
5. **`main`, `staging`, and `dev` are permanent** — they must always exist and must never be deleted or force-pushed.

### Workflow

```
main (prod)
  └── staging (pre-prod)     ← branched from main
        └── dev (dev)        ← branched from staging
              ├── feature/my-feature  ← branched from dev
              ├── feature/another     ← branched from dev
              └── ...
```

**Merge flow:**
```
feature/* → dev → staging → main
```

### Deployed environments

| Branch | Environment | UI | API |
|--------|-------------|-----|-----|
| `main` | Production | `trading.zemingzhang.com` | `api.zemingzhang.com` |
| `staging` | Staging | `trading-stg.zemingzhang.com` | `api-stg.zemingzhang.com` |
| `dev` | Dev | `trading-dev.zemingzhang.com` | `api-dev.zemingzhang.com` |

### Quick-start for a new feature

```bash
# 1. Make sure your local dev branch is up to date
git checkout dev
git pull origin dev

# 2. Branch off dev
git checkout -b feature/my-feature

# 3. Do your work, then push
git push -u origin feature/my-feature

# 4. Open a PR: feature/my-feature → dev
# 5. After testing, open a PR: dev → staging
# 6. After sign-off, open a PR: staging → main
# 7. Delete the feature branch after merge
```

### For AI agents (Claude Code)

- **Never push directly to `main`, `staging`, or `dev`.**
- **Never delete `main`, `staging`, or `dev`.**
- All development work goes on a `feature/*` branch cut from `dev`.
- PRs always flow: `feature/*` → `dev` → `staging` → `main`.
- Feature branches are deleted after merge.
- When creating a new repository under this project, apply the same structure: `main`, `staging`, `dev`, `feature/*`.
