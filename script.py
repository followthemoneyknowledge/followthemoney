#!/usr/bin/env python3
"""
Script generator for "Follow the Money" content pipeline.
Takes an org name, fetches revenue data, and uses Claude to write a 90-second reel script.
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime

import json
import urllib.request
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

# Import research pipeline
sys.path.insert(0, str(Path(__file__).parent))
from research import research_org, fetch_wikipedia_summary, extract_money_mentions, fetch_wikipedia_financials, search_news, TextExtractor, fetch_url

console = Console()

SCRIPT_TEMPLATE = """
You are a short-form video script writer for a finance/sports channel called "Follow the Money."
Your scripts explain how organizations, sports leagues, and brands actually make money.

**Format rules:**
- Total spoken length: 75–90 seconds (target ~180 words)
- Conversational tone — no jargon, no filler words
- Every number must be human-scaled (e.g., "enough to buy 3 Premier League clubs")
- Write exactly 5 sections with timing markers as shown

**Script structure:**
[0–5s] HOOK — One shocking number. Single punchy sentence. No question marks.
[5–15s] SETUP — Brief context explaining what makes this surprising.
[15–50s] BREAKDOWN — 3–4 revenue streams with exact numbers. Short punchy sentences. Use "." not commas between items.
[50–75s] SURPRISING FACT — The counterintuitive close. What most people don't know.
[75–90s] CTA — "Follow for the next breakdown." (always this exact phrase, nothing else)

**Org:** {org}

**Revenue data found:**
{findings}

**Wikipedia context:**
{wiki_summary}

Write the script now. Output ONLY the 5 timed sections, nothing else. No intro, no explanation, no notes.
"""


def collect_findings_silently(org):
    """Collect revenue data without printing the full research display."""
    import urllib.parse

    findings = []

    # Wikipedia financials
    wiki_text = fetch_wikipedia_financials(org)
    wiki_findings = extract_money_mentions(wiki_text, org) if wiki_text else []
    wiki_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(org.replace(' ', '_'))}"
    for f in wiki_findings:
        f["source"] = "Wikipedia"
        f["url"] = wiki_url
    findings.extend(wiki_findings)

    # News articles
    articles = search_news(org, max_results=4)
    for article in articles:
        try:
            html, final_url = fetch_url(article["url"])
            parser = TextExtractor()
            parser.feed(html)
            text = parser.get_text()
            article_findings = extract_money_mentions(text, org)
            for f in article_findings:
                f["source"] = article["source"]
                f["url"] = final_url
            findings.extend(article_findings)
        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique = []
    for f in findings:
        key = re.sub(r'\s+', '', f["amount"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique[:8]


def format_findings_for_prompt(findings):
    if not findings:
        return "No revenue figures found automatically. Use general knowledge about this org."
    lines = []
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. {f['amount']} — {f['context'][:150]} (Source: {f['source']})")
    return "\n".join(lines)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-opus-4-5"


def generate_script(org, findings, wiki_summary, model=DEFAULT_MODEL):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error: OPENROUTER_API_KEY environment variable not set.[/red]")
        console.print("[dim]Set it with: export OPENROUTER_API_KEY=your_key_here[/dim]")
        sys.exit(1)

    prompt = SCRIPT_TEMPLATE.format(
        org=org,
        findings=format_findings_for_prompt(findings),
        wiki_summary=wiki_summary[:400] if wiki_summary else "Not available.",
    )

    console.print(f"\n[bold cyan]Generating script via OpenRouter ({model})...[/bold cyan]")

    payload = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/followthemoneyknowledge/followthemoney",
            "X-Title": "Follow the Money",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]["content"].strip()


def display_script(org, script_text):
    console.print()
    console.print(Panel(
        f"[bold cyan]Follow the Money[/bold cyan] — [bold]{org}[/bold]",
        subtitle="90-second reel script",
        box=box.DOUBLE,
    ))

    # Parse sections by timing markers
    sections = re.split(r'(\[\d+[–—-]\d+s\])', script_text)
    colors = {
        "HOOK": "bold yellow",
        "SETUP": "bold blue",
        "BREAKDOWN": "bold white",
        "SURPRISING": "bold magenta",
        "CTA": "bold green",
    }

    table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))
    table.add_column("Timing", style="dim", width=10)
    table.add_column("Script", style="white")

    i = 1
    while i < len(sections):
        timing = sections[i].strip() if i < len(sections) else ""
        content = sections[i + 1].strip() if i + 1 < len(sections) else ""
        if timing and content:
            # Detect section type for color
            style = "white"
            for key, color in colors.items():
                if key in content[:20].upper():
                    style = color
                    break
            table.add_row(timing, Text(content, style=style))
        i += 2

    console.print(table)

    # Word count and read time
    words = len(script_text.split())
    read_time = round(words / 2.5)  # ~150 wpm spoken pace
    console.print(f"\n[dim]Words: {words} | Estimated read time: ~{read_time}s[/dim]")


def save_script(org, script_text):
    scripts_dir = Path(__file__).parent / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    slug = re.sub(r'[^\w]+', '-', org.lower()).strip('-')
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    filename = scripts_dir / f"{slug}-{timestamp}.txt"

    with open(filename, "w") as f:
        f.write(f"# Follow the Money — {org}\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(script_text)
        f.write("\n")

    console.print(f"\n[bold green]Script saved:[/bold green] {filename}")
    return filename


def run(org, silent_research=False, model=DEFAULT_MODEL):
    console.print(Panel(
        f"[bold cyan]Follow the Money[/bold cyan] — Script Generator\n"
        f"[dim]Building 90-second reel script for: {org}[/dim]",
        box=box.DOUBLE,
    ))

    if silent_research:
        console.print("\n[bold]Collecting revenue data...[/bold]")
        findings = collect_findings_silently(org)
        wiki_summary = fetch_wikipedia_summary(org)
        console.print(f"[dim]Found {len(findings)} revenue figures[/dim]")
    else:
        console.print()
        findings = research_org(org)
        wiki_summary = fetch_wikipedia_summary(org)

    script_text = generate_script(org, findings, wiki_summary, model=model)
    display_script(org, script_text)
    save_script(org, script_text)

    return script_text


def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python3 script.py <org name> [--model <model>][/red]")
        console.print("[dim]Example: python3 script.py FIFA[/dim]")
        console.print("[dim]Example: python3 script.py FIFA --model google/gemini-2.0-flash-001[/dim]")
        console.print(f"[dim]Default model: {DEFAULT_MODEL}[/dim]")
        sys.exit(1)

    # Parse args: collect org name, check for --model flag
    raw_args = sys.argv[1:]
    model = DEFAULT_MODEL
    if "--model" in raw_args:
        idx = raw_args.index("--model")
        if idx + 1 < len(raw_args):
            model = raw_args[idx + 1]
            raw_args = raw_args[:idx] + raw_args[idx + 2:]

    org = " ".join(raw_args)
    run(org, silent_research=False, model=model)


if __name__ == "__main__":
    main()
