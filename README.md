# CI Status Dashboard — algojj

[![CI Status](https://github.com/algojj/ci-status/actions/workflows/ci-status.yml/badge.svg)](https://github.com/algojj/ci-status/actions/workflows/ci-status.yml)

Real-time CI/CD monitoring dashboard for all repositories in the **algojj** organization.

## Dashboard

**[View Dashboard](https://algojj.github.io/ci-status/)**

## How it works

1. A GitHub Actions workflow runs every **15 minutes** (Mon-Fri, 8am-9pm Argentina time)
2. It queries the GitHub API for all repos in the `algojj` org
3. For each repo, it fetches the latest workflow run status
4. Generates a static HTML dashboard and deploys it to GitHub Pages

## Features

- Dark mode Jenkins-style monitoring UI
- Status per repo: ✅ passing / ❌ failing / 🔄 running / ⚠️ sin CI
- Sorted by priority: failing repos shown first
- Last commit info, branch, duration, direct links to workflow runs
- Responsive design (mobile-friendly)
- Manual trigger available via "Run workflow" button

## Setup

### Required Secret

The workflow needs a `GH_PAT` secret with a Personal Access Token that has:
- `repo` scope (to read private repos and their actions)
- `read:org` scope (to list org repos)

Set it in: **Settings > Secrets and variables > Actions > New repository secret**

### GitHub Pages

Enable GitHub Pages in **Settings > Pages**:
- Source: **Deploy from a branch**
- Branch: **gh-pages** / root

### Manual Trigger

Go to **Actions > CI Status Dashboard > Run workflow** to trigger an immediate refresh.

## Files

```
.github/workflows/ci-status.yml   # Workflow: schedule + generate + deploy
scripts/generate_dashboard.py      # Python script that generates the HTML
README.md                          # This file
```
