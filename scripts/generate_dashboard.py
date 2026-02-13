"""
CI Status Dashboard Generator
Queries all repos in algojj org, gets latest workflow status, generates static HTML.
"""

import html as html_mod
import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
ORG_NAME = os.environ.get("ORG_NAME", "algojj")
API = "https://api.github.com"
HEADERS = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"}
AR_TZ = timezone(timedelta(hours=-3))


def api_get(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        print(f"Rate limited. Headers: {resp.headers.get('X-RateLimit-Remaining')}")
        sys.exit(1)
    return resp


def get_all_repos():
    repos = []
    page = 1
    while True:
        resp = api_get(f"{API}/orgs/{ORG_NAME}/repos", {"per_page": 100, "page": page, "type": "all"})
        if resp.status_code != 200:
            print(f"Error listing repos: {resp.status_code} {resp.text[:200]}")
            break
        data = resp.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def get_latest_run(repo_name):
    resp = api_get(f"{API}/repos/{ORG_NAME}/{repo_name}/actions/runs", {"per_page": 1})
    if resp.status_code != 200 or not resp.json().get("workflow_runs"):
        return None
    return resp.json()["workflow_runs"][0]


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def get_status_info(run):
    if run is None:
        return "no_ci", "Sin CI", "⚠️"
    status = run.get("status", "")
    conclusion = run.get("conclusion", "")
    if status in ("in_progress", "queued", "waiting"):
        return "running", "Running", "🔄"
    if conclusion == "success":
        return "success", "Passing", "✅"
    if conclusion == "failure":
        return "failure", "Failing", "❌"
    if conclusion == "cancelled":
        return "cancelled", "Cancelled", "⏹️"
    return "unknown", conclusion or status or "Unknown", "❓"


def build_repo_data(repos):
    results = []
    for repo in repos:
        name = repo["name"]
        print(f"  Checking {name}...")
        run = get_latest_run(name)
        status_key, status_label, status_icon = get_status_info(run)

        entry = {
            "name": name,
            "url": repo["html_url"],
            "private": repo.get("private", False),
            "status_key": status_key,
            "status_label": status_label,
            "status_icon": status_icon,
        }

        if run:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            updated = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
            duration_s = int((updated - created).total_seconds())

            entry.update({
                "run_url": run["html_url"],
                "run_name": run.get("name", run.get("display_title", "")),
                "branch": run.get("head_branch", ""),
                "commit_msg": (run.get("display_title") or run.get("head_commit", {}).get("message", ""))[:80],
                "commit_date": created.astimezone(AR_TZ).strftime("%Y-%m-%d %H:%M"),
                "duration": format_duration(duration_s),
                "workflow": run.get("name", ""),
            })
        results.append(entry)

    # Sort: failing > running > cancelled > no_ci > unknown > success
    order = {"failure": 0, "running": 1, "cancelled": 2, "no_ci": 3, "unknown": 4, "success": 5}
    results.sort(key=lambda r: (order.get(r["status_key"], 99), r["name"]))
    return results


def count_statuses(data):
    counts = {}
    for r in data:
        k = r["status_key"]
        counts[k] = counts.get(k, 0) + 1
    return counts


def generate_html(data, counts, timestamp):
    total = len(data)
    failing = counts.get("failure", 0)
    passing = counts.get("success", 0)
    running = counts.get("running", 0)
    no_ci = counts.get("no_ci", 0)
    other = total - failing - passing - running - no_ci

    health = "ALL GREEN" if failing == 0 else f"{failing} FAILING"
    health_color = "#4caf50" if failing == 0 else "#f44336"

    rows = ""
    for r in data:
        status_class = r["status_key"]
        run_link = ""
        commit_info = ""
        duration = ""
        branch = ""

        if r.get("run_url"):
            run_link = f'<a href="{r["run_url"]}" target="_blank" class="run-link">View Run</a>'
            commit_info = f'<span class="commit-msg">{r.get("commit_msg", "")}</span><br><span class="commit-date">{r.get("commit_date", "")}</span>'
            duration = r.get("duration", "")
            branch = r.get("branch", "")

        # Build copy-to-clipboard text for failed/non-success items
        copy_btn = ""
        if r["status_key"] in ("failure", "cancelled") and r.get("run_url"):
            copy_text = (
                f'El pipeline "{r.get("workflow", "")}" fallo en el repo algojj/{r["name"]}, '
                f'branch: {r.get("branch", "?")}, '
                f'commit: "{r.get("commit_msg", "")}" ({r.get("commit_date", "")}). '
                f'Run: {r.get("run_url", "")} — '
                f'Por favor revisa los logs del workflow y decime que paso.'
            )
            safe_text = html_mod.escape(copy_text, quote=True)
            copy_btn = f'<button class="copy-btn" data-copy="{safe_text}" title="Copy for Claude Code">📋</button>'

        rows += f"""
        <tr class="status-{status_class}">
            <td class="status-cell"><span class="status-icon">{r["status_icon"]}</span> {r["status_label"]}</td>
            <td><a href="{r["url"]}" target="_blank" class="repo-link">{r["name"]}</a>{"  🔒" if r.get("private") else ""}</td>
            <td class="branch-cell">{branch}</td>
            <td class="commit-cell">{commit_info}</td>
            <td class="duration-cell">{duration}</td>
            <td class="action-cell">{run_link} {copy_btn}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CI Status — algojj</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
}}
.header {{
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 20px 24px;
}}
.header-top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}}
.title {{
    font-size: 24px;
    font-weight: 700;
    color: #f0f6fc;
}}
.title span {{ color: #58a6ff; }}
.health-badge {{
    font-size: 14px;
    font-weight: 700;
    padding: 6px 16px;
    border-radius: 20px;
    background: {health_color}22;
    color: {health_color};
    border: 1px solid {health_color}44;
}}
.stats {{
    display: flex;
    gap: 16px;
    margin-top: 12px;
    flex-wrap: wrap;
}}
.stat {{
    font-size: 13px;
    padding: 4px 12px;
    border-radius: 12px;
    background: #21262d;
    border: 1px solid #30363d;
}}
.stat-total {{ color: #8b949e; }}
.stat-pass {{ color: #3fb950; }}
.stat-fail {{ color: #f85149; }}
.stat-run {{ color: #d29922; }}
.stat-noci {{ color: #8b949e; }}
.timestamp {{
    font-size: 12px;
    color: #8b949e;
    margin-top: 8px;
}}
.container {{
    padding: 16px 24px;
    overflow-x: auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}}
th {{
    text-align: left;
    padding: 10px 12px;
    background: #161b22;
    border-bottom: 2px solid #30363d;
    color: #8b949e;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
    z-index: 1;
}}
td {{
    padding: 10px 12px;
    border-bottom: 1px solid #21262d;
    vertical-align: middle;
}}
tr:hover {{ background: #161b2288; }}
.status-cell {{
    white-space: nowrap;
    font-weight: 600;
    min-width: 110px;
}}
.status-icon {{ font-size: 16px; }}
.status-failure .status-cell {{ color: #f85149; }}
.status-success .status-cell {{ color: #3fb950; }}
.status-running .status-cell {{ color: #d29922; }}
.status-no_ci .status-cell {{ color: #8b949e; }}
.status-cancelled .status-cell {{ color: #8b949e; }}
.status-failure {{ background: #f8514908; }}
.repo-link {{
    color: #58a6ff;
    text-decoration: none;
    font-weight: 600;
}}
.repo-link:hover {{ text-decoration: underline; }}
.run-link {{
    color: #8b949e;
    text-decoration: none;
    font-size: 12px;
    padding: 3px 8px;
    border: 1px solid #30363d;
    border-radius: 6px;
    white-space: nowrap;
}}
.run-link:hover {{ background: #21262d; color: #58a6ff; border-color: #58a6ff; }}
.branch-cell {{
    color: #7ee787;
    font-family: monospace;
    font-size: 12px;
}}
.commit-cell {{ max-width: 300px; }}
.commit-msg {{
    color: #c9d1d9;
    font-size: 13px;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.commit-date {{ color: #8b949e; font-size: 11px; }}
.duration-cell {{
    color: #8b949e;
    font-family: monospace;
    font-size: 12px;
    white-space: nowrap;
}}
.action-cell {{ white-space: nowrap; display: flex; align-items: center; gap: 6px; }}
.copy-btn {{
    background: none;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 3px 6px;
    cursor: pointer;
    font-size: 14px;
    color: #8b949e;
    transition: all 0.2s;
    line-height: 1;
}}
.copy-btn:hover {{ background: #21262d; border-color: #58a6ff; }}
.copy-btn.copied {{ border-color: #3fb950; }}
@media (max-width: 768px) {{
    .header {{ padding: 16px; }}
    .container {{ padding: 12px; }}
    .branch-cell, .duration-cell {{ display: none; }}
    .commit-cell {{ max-width: 160px; }}
    table {{ font-size: 13px; }}
    td, th {{ padding: 8px 6px; }}
    .stats {{ gap: 8px; }}
    .stat {{ font-size: 12px; padding: 3px 8px; }}
}}
@media (max-width: 480px) {{
    .commit-cell {{ display: none; }}
    .title {{ font-size: 18px; }}
}}
</style>
</head>
<body>
<div class="header">
    <div class="header-top">
        <div class="title">⚡ <span>algojj</span> CI Status</div>
        <div class="health-badge">{health}</div>
    </div>
    <div class="stats">
        <span class="stat stat-total">{total} repos</span>
        <span class="stat stat-pass">✅ {passing} passing</span>
        <span class="stat stat-fail">❌ {failing} failing</span>
        <span class="stat stat-run">🔄 {running} running</span>
        <span class="stat stat-noci">⚠️ {no_ci} sin CI</span>
        {"<span class='stat stat-noci'>⏹️ " + str(other) + " other</span>" if other > 0 else ""}
    </div>
    <div class="timestamp">Last updated: {timestamp} (Argentina) — Refreshes every 15 min (Mon-Fri 8am-9pm ART)</div>
</div>
<div class="container">
<table>
<thead>
    <tr>
        <th>Status</th>
        <th>Repository</th>
        <th>Branch</th>
        <th>Last Commit</th>
        <th>Duration</th>
        <th>Actions</th>
    </tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<script>
document.querySelectorAll('.copy-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
        var text = this.getAttribute('data-copy');
        navigator.clipboard.writeText(text).then(function() {{
            btn.textContent = '✅';
            btn.classList.add('copied');
            setTimeout(function() {{ btn.textContent = '📋'; btn.classList.remove('copied'); }}, 2000);
        }});
    }});
}});
</script>
</body>
</html>"""
    return html


def main():
    if not GH_TOKEN:
        print("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
        sys.exit(1)

    print(f"Fetching repos for org '{ORG_NAME}'...")
    repos = get_all_repos()
    print(f"Found {len(repos)} repos")

    print("Checking CI status for each repo...")
    data = build_repo_data(repos)
    counts = count_statuses(data)

    now_ar = datetime.now(AR_TZ)
    timestamp = now_ar.strftime("%Y-%m-%d %H:%M:%S")

    html = generate_html(data, counts, timestamp)

    os.makedirs("/tmp/dashboard", exist_ok=True)
    with open("/tmp/dashboard/index.html", "w") as f:
        f.write(html)

    with open("/tmp/dashboard/status.json", "w") as f:
        json.dump({"timestamp": timestamp, "total": len(data), "counts": counts,
                    "repos": [{k: v for k, v in r.items()} for r in data]}, f, indent=2)

    print(f"\nDashboard generated: {len(data)} repos")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
