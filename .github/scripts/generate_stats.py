#!/usr/bin/env python3
"""
Generates two SVG cards — github-stats.svg and top-languages.svg — styled to
match the rest of the dashboard README. Runs inside a GitHub Action using the
default GITHUB_TOKEN; no personal access token, fork, or hosted service needed.

Requires only the Python standard library.
"""
import json
import os
import sys
import urllib.request

DISPLAY_FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO_FONT = "'SF Mono','Consolas','Roboto Mono','Courier New',monospace"

BG_TOP = "#0B0C0F"
BG_BOTTOM = "#000000"
TRACK_COLOR = "#24262B"
TEXT_PRIMARY = "#F5F6F7"
TEXT_SECONDARY = "#888D96"
TEXT_DIM = "#4B4F58"
PANEL_STROKE = "rgba(255,255,255,0.09)"
ACCENT = "#2DD4BF"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-stats-script",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(f"GitHub GraphQL API returned errors: {payload['errors']}")
    return payload["data"]["user"]


def panel_open(fid, title, w, h):
    return f'''<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">
<defs>
  <linearGradient id="{fid}Bg" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="{BG_TOP}"/><stop offset="100%" stop-color="{BG_BOTTOM}"/>
  </linearGradient>
</defs>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="url(#{fid}Bg)" stroke="{PANEL_STROKE}" stroke-width="1.5"/>
<circle cx="30" cy="28" r="4" fill="{ACCENT}"/>
<text x="42" y="32" font-family="{MONO_FONT}" font-size="12.5" letter-spacing="2.5" fill="{TEXT_DIM}">{title.upper()}</text>
<line x1="26" y1="42" x2="{w-26}" y2="42" stroke="{PANEL_STROKE}" stroke-width="1"/>
'''


def render_stats(data, out_path):
    repos = data["repositories"]
    total_stars = sum(n["stargazerCount"] for n in repos["nodes"])
    stats = [
        ("Public Repos", repos["totalCount"]),
        ("Followers", data["followers"]["totalCount"]),
        ("Total Stars", total_stars),
        ("Contributions (1y)", data["contributionsCollection"]["contributionCalendar"]["totalContributions"]),
    ]
    W, H = 620, 150
    col_w = (W - 52) / 4
    body = []
    for i, (label, value) in enumerate(stats):
        cx = 26 + col_w * i + col_w / 2
        body.append(f'''
<text x="{cx:.1f}" y="92" text-anchor="middle" font-family="{DISPLAY_FONT}" font-size="34" font-weight="800" fill="{TEXT_PRIMARY}" opacity="0">{value:,}
  <animate attributeName="opacity" values="0;1" dur="0.4s" begin="{0.15 + i*0.12:.2f}s" fill="freeze"/>
</text>
<text x="{cx:.1f}" y="116" text-anchor="middle" font-family="{MONO_FONT}" font-size="11.5" letter-spacing="1" fill="{TEXT_SECONDARY}">{label.upper()}</text>''')
    if len(stats) > 1:
        for i in range(1, len(stats)):
            x = 26 + col_w * i
            body.append(f'<line x1="{x:.1f}" y1="60" x2="{x:.1f}" y2="122" stroke="{PANEL_STROKE}" stroke-width="1"/>')
    svg = panel_open("stats", "GitHub Stats", W, H) + "".join(body) + "\n</svg>"
    with open(out_path, "w") as f:
        f.write(svg)


def render_top_langs(data, out_path, top_n=6):
    totals = {}
    colors = {}
    for repo in data["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or ACCENT
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    grand_total = sum(totals.values()) or 1

    W = 620
    ROW_H = 34
    TITLE_H = 54
    PAD_BOTTOM = 22
    BAR_X, BAR_W, BAR_H = 176, 336, 10
    PCT_X = BAR_X + BAR_W + 16
    H = TITLE_H + len(ranked) * ROW_H + PAD_BOTTOM

    body = []
    for i, (name, size) in enumerate(ranked):
        pct = size / grand_total * 100
        color = colors[name]
        cy = TITLE_H + i * ROW_H + ROW_H / 2
        bar_y = cy - BAR_H / 2
        target_w = BAR_W * pct / 100
        begin = 0.15 + i * 0.11
        body.append(f'''
<text x="26" y="{cy+4.5:.1f}" font-family="{MONO_FONT}" font-size="13" fill="{TEXT_SECONDARY}">{name}</text>
<rect x="{BAR_X}" y="{bar_y:.1f}" width="{BAR_W}" height="{BAR_H}" rx="{BAR_H/2}" fill="{TRACK_COLOR}"/>
<rect x="{BAR_X}" y="{bar_y:.1f}" width="{target_w:.1f}" height="{BAR_H}" rx="{BAR_H/2}" fill="{color}" stroke-dasharray="0" opacity="0">
  <animate attributeName="width" values="0;{target_w:.1f}" dur="0.9s" begin="{begin:.2f}s" fill="freeze" calcMode="spline" keySplines="0.22 0.61 0.36 1"/>
  <set attributeName="opacity" to="1" begin="{begin:.2f}s"/>
</rect>
<text x="{PCT_X}" y="{cy+4.5:.1f}" font-family="{MONO_FONT}" font-size="12.5" font-weight="700" fill="{TEXT_PRIMARY}" opacity="0">{pct:.1f}%
  <animate attributeName="opacity" values="0;1" dur="0.3s" begin="{begin+0.65:.2f}s" fill="freeze"/>
</text>''')
    svg = panel_open("langs", "Top Languages (Live)", W, H) + "".join(body) + "\n</svg>"
    with open(out_path, "w") as f:
        f.write(svg)


def main():
    login = os.environ.get("PROFILE_LOGIN") or os.environ["GITHUB_REPOSITORY_OWNER"]
    token = os.environ["GH_TOKEN"]
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out_dir, exist_ok=True)

    data = fetch(login, token)
    render_stats(data, os.path.join(out_dir, "github-stats.svg"))
    render_top_langs(data, os.path.join(out_dir, "top-languages.svg"))
    print(f"Generated github-stats.svg and top-languages.svg for {login} in {out_dir}/")


if __name__ == "__main__":
    main()
