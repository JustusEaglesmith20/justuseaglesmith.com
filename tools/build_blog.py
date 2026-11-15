#!/usr/bin/env python3
"""Turn posts/*.md into static pages under blog/.

Run by .github/workflows/static.yml on every push to main, just before the
site is uploaded to GitHub Pages. The generated blog/ folder is never
committed; it exists only in the deploy.

    posts/2026-11-15-my-post.md  ->  blog/my-post/index.html
    (all published posts)        ->  blog/index.html

Front matter keys: title, date, summary (optional), draft (optional).
Local preview:  pip install markdown pyyaml && python tools/build_blog.py
"""
import datetime as dt
import html
import pathlib
import re
import shutil
import sys

import markdown
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTS = ROOT / "posts"
OUT = ROOT / "blog"
SITE = "Justus Eaglesmith"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
<meta name="description" content="{description}" />
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css" />
<style>
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0}}
  body{{font-family:system-ui,-apple-system,sans-serif;line-height:1.55;color:#111;background:#fff;font-size:16px}}
  .container{{max-width:760px;margin:0 auto;padding:48px 24px 80px}}
  h1{{font-size:32px;margin:0 0 4px;line-height:1.2}}
  h2{{margin-top:36px}} h3{{margin-top:28px}}
  a{{color:#0645ad}}
  nav{{margin-bottom:32px}}
  .meta{{color:#555;margin:0 0 28px}}
  .posts{{list-style:none;padding:0}}
  .posts li{{margin-bottom:24px}}
  .posts a{{font-size:20px;font-weight:600}}
  .posts p{{margin:4px 0 0}}
  img{{max-width:100%;height:auto}}
  pre{{overflow-x:auto;padding:14px;background:#f6f8fa;border-radius:6px;font-size:14px}}
  code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
  :not(pre)>code{{background:#f6f8fa;padding:2px 5px;border-radius:4px;font-size:.9em}}
  blockquote{{margin:16px 0;padding:0 16px;border-left:3px solid #ccc;color:#444}}
  table{{border-collapse:collapse}} th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left}}
</style>
</head>
<body>
<div class="container">
<nav>{nav}</nav>
{content}
</div>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
</body>
</html>
"""


def split_front_matter(text):
    """Return (meta dict, body). Tolerates a missing or broken header."""
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.S)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as err:
        print(f"  warning: unreadable front matter ({err}); using filename", file=sys.stderr)
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[match.end():]


def to_date(value, fallback):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    found = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    try:
        return dt.date(*map(int, found.groups())) if found else fallback
    except ValueError:
        return fallback


def load(path):
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    stem = path.stem
    name_date = to_date(stem, None)
    base = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", stem) or stem
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "post"
    return {
        "slug": slug,
        "title": str(meta.get("title") or base.replace("-", " ").title()),
        "date": to_date(meta.get("date"), name_date or dt.date.fromtimestamp(path.stat().st_mtime)),
        "summary": str(meta.get("summary") or "").strip(),
        "draft": meta.get("draft") in (True, "true", "True", "yes"),
        "body": body,
    }


def pretty(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def write(path, **parts):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.format(**parts), encoding="utf-8")


def main():
    posts = [load(p) for p in sorted(POSTS.glob("*.md")) if p.name != "README.md"]
    live = sorted((p for p in posts if not p["draft"]), key=lambda p: (p["date"], p["slug"]), reverse=True)

    if OUT.exists():
        shutil.rmtree(OUT)

    seen = set()
    for post in live:
        while post["slug"] in seen:  # two posts with the same title
            post["slug"] += "-2"
        seen.add(post["slug"])
        body = markdown.markdown(post["body"], extensions=["extra", "sane_lists", "smarty"])
        write(
            OUT / post["slug"] / "index.html",
            title=f"{html.escape(post['title'])} · {SITE}",
            description=html.escape(post["summary"], quote=True),
            nav='<a href="/">Home</a> · <a href="/blog/">Writing</a>',
            content=f"<article>\n<h1>{html.escape(post['title'])}</h1>\n"
                    f"<p class=\"meta\">{pretty(post['date'])}</p>\n{body}\n</article>",
        )

    items = "\n".join(
        f'<li><a href="/blog/{p["slug"]}/">{html.escape(p["title"])}</a>'
        f'<p class="meta" style="margin:2px 0 0">{pretty(p["date"])}</p>'
        + (f"<p>{html.escape(p['summary'])}</p>" if p["summary"] else "")
        + "</li>"
        for p in live
    ) or "<li>No posts yet.</li>"
    write(
        OUT / "index.html",
        title=f"Writing · {SITE}",
        description="Notes on what I am learning.",
        nav='<a href="/">Home</a>',
        content=f"<h1>Writing</h1>\n<p class=\"meta\">Notes on what I am learning.</p>\n<ul class=\"posts\">\n{items}\n</ul>",
    )
    print(f"built {len(live)} post(s), skipped {len(posts) - len(live)} draft(s)")


if __name__ == "__main__":
    main()
