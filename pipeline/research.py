#!/usr/bin/env python3
"""
Revenue research builder for "Follow the Money" content pipeline.
Given an org name, fetches revenue figures from news articles and Wikipedia.
Outputs a structured data sheet ready for script writing.
"""

import re
import sys
import urllib.request
import urllib.parse
import feedparser
from html.parser import HTMLParser
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Revenue categories to look for
REVENUE_KEYWORDS = [
    "revenue", "income", "earnings", "profit", "turnover",
    "broadcasting", "media rights", "tv deal", "sponsorship",
    "ticket", "matchday", "licensing", "merchandise",
    "prize money", "distribution", "deal worth",
]

MONEY_PATTERN = re.compile(
    r'(?:€|£|\$|USD|EUR|GBP)?\s*'
    r'(\d[\d,\.]*)\s*'
    r'(trillion|billion|million|bn|m\b)',
    re.IGNORECASE
)


class TextExtractor(HTMLParser):
    """Strips HTML tags and returns plain text."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.text_parts.append(data)

    def get_text(self):
        return " ".join(self.text_parts)


def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.url  # capture after redirect
        return resp.read().decode("utf-8", errors="ignore"), final_url


def search_news(org, max_results=5):
    """Search Google News RSS for revenue articles about the org."""
    query = urllib.parse.quote(f"{org} revenue annual report")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            feed = feedparser.parse(resp.read())
        results = []
        for entry in feed.entries[:max_results]:
            # Pull snippet text from RSS description/summary
            snippet = entry.get("summary", "") or entry.get("description", "")
            # Strip HTML tags from snippet
            parser = TextExtractor()
            parser.feed(snippet)
            snippet_text = parser.get_text().strip()
            results.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "source": entry.get("source", {}).get("title", "Unknown"),
                "snippet": snippet_text,
            })
        return results
    except Exception as e:
        console.print(f"[red]News search failed: {e}[/red]")
        return []


def extract_money_mentions(text, org):
    """Extract sentences containing money amounts from plain text."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    findings = []

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20 or len(sentence) > 400:
            continue

        has_money = MONEY_PATTERN.search(sentence)
        has_keyword = any(kw in sentence.lower() for kw in REVENUE_KEYWORDS)
        has_org = org.lower().split()[0] in sentence.lower()

        if has_money and (has_keyword or has_org):
            # Normalize the money amount for display
            money = MONEY_PATTERN.search(sentence)
            if money:
                findings.append({
                    "amount": f"{money.group(1)} {money.group(2)}",
                    "context": sentence[:200],
                })

    # Deduplicate by amount
    seen = set()
    unique = []
    for f in findings:
        key = re.sub(r'\s+', '', f["amount"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique[:8]


def fetch_wikipedia_summary(org):
    """Fetch a short description of the org from Wikipedia."""
    slug = urllib.parse.quote(org.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        raw, _ = fetch_url(url)
        import json
        data = json.loads(raw)
        return data.get("extract", "")[:300]
    except Exception:
        return ""


def fetch_wikipedia_financials(org):
    """Extract money figures from Wikipedia full article text."""
    slug = urllib.parse.quote(org.replace(" ", "_"))
    url = f"https://en.wikipedia.org/w/api.php?action=parse&page={slug}&prop=wikitext&format=json"
    try:
        import json
        raw, _ = fetch_url(url)
        data = json.loads(raw)
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        # Strip wiki markup
        text = re.sub(r'\{\{[^}]+\}\}', '', wikitext)
        text = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', text)
        text = re.sub(r"'{2,}", '', text)
        text = re.sub(r'<[^>]+>', '', text)
        return text
    except Exception:
        return ""


def research_org(org):
    console.print(Panel(
        f"[bold cyan]Revenue Research: {org}[/bold cyan]\n"
        f"[dim]Searching news + Wikipedia for financial data[/dim]",
        box=box.DOUBLE,
    ))

    # 1. Wikipedia context
    console.print("\n[bold]Fetching Wikipedia summary...[/bold]")
    summary = fetch_wikipedia_summary(org)
    if summary:
        console.print(Panel(summary, title="Wikipedia Context", border_style="dim"))

    # 2. Wikipedia financials
    console.print("\n[bold]Scanning Wikipedia for financial figures...[/bold]")
    wiki_text = fetch_wikipedia_financials(org)
    wiki_findings = extract_money_mentions(wiki_text, org) if wiki_text else []

    # 3. Search news articles
    console.print(f"\n[bold]Searching news for '{org} revenue'...[/bold]")
    articles = search_news(org)
    console.print(f"[dim]Found {len(articles)} articles[/dim]")

    all_findings = []
    sources_used = []

    # Add Wikipedia findings first
    for f in wiki_findings:
        f["source"] = "Wikipedia"
        f["url"] = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(org.replace(' ', '_'))}"
    all_findings.extend(wiki_findings)
    if wiki_findings:
        sources_used.append({"source": "Wikipedia", "url": all_findings[0]["url"], "title": org})

    # 4. Fetch and extract from news articles
    for article in articles:
        console.print(f"[dim]  → {article['source']}: {article['title'][:65]}[/dim]")
        try:
            html, final_url = fetch_url(article["url"])
            parser = TextExtractor()
            parser.feed(html)
            text = parser.get_text()
            findings = extract_money_mentions(text, org)
            if findings:
                for f in findings:
                    f["source"] = article["source"]
                    f["url"] = final_url
                all_findings.extend(findings)
                sources_used.append({**article, "url": final_url})
        except Exception as e:
            console.print(f"[dim red]    Skipped ({type(e).__name__})[/dim red]")

    # 4. Deduplicate across all articles
    seen = set()
    unique_findings = []
    for f in all_findings:
        key = re.sub(r'\s+', '', f["amount"].lower())
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    # 5. Display data sheet
    console.print()
    if not unique_findings:
        console.print(Panel(
            "[yellow]No revenue figures extracted automatically.\n"
            "Check the articles below manually.[/yellow]",
            title="Data Sheet",
        ))
    else:
        table = Table(title=f"Revenue Data Sheet — {org}", box=box.ROUNDED, show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Amount", style="bold green", width=15)
        table.add_column("Context", style="white")
        table.add_column("Source", style="cyan", width=14)

        for i, f in enumerate(unique_findings[:7], 1):
            table.add_row(
                str(i),
                f["amount"],
                f["context"][:120] + ("..." if len(f["context"]) > 120 else ""),
                f["source"][:14],
            )
        console.print(table)

    # 6. Show sources
    if sources_used:
        console.print("\n[bold]Sources:[/bold]")
        for a in sources_used:
            console.print(f"  [dim]• {a['source']}[/dim] — {a['url'][:80]}")

    # 7. Script prompt hint
    console.print(Panel(
        f"[bold]Suggested reel hook:[/bold]\n"
        f"Pick the most surprising number above and complete:\n\n"
        f"  \"{org} made [AMOUNT] from [SOURCE].\"\n"
        f"  \"Here's exactly how they did it.\"",
        title="Script Starter",
        border_style="green",
    ))


def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python3 research.py <org name>[/red]")
        console.print("[dim]Example: python3 research.py FIFA[/dim]")
        console.print("[dim]Example: python3 research.py 'Borussia Dortmund'[/dim]")
        sys.exit(1)

    org = " ".join(sys.argv[1:])
    research_org(org)


if __name__ == "__main__":
    main()
