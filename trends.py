#!/usr/bin/env python3
"""
Trend detection tool for "Follow the Money" content pipeline.
Finds trending orgs/events and surfaces their revenue angle.
"""

import feedparser
import urllib.request
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import sys

console = Console()

# Known orgs with pre-researched revenue angles
ORG_ANGLES = {
    "FIFA": "How FIFA makes money as a nonprofit (hint: $7.5B from one tournament)",
    "NFL": "How the NFL splits $20B in annual revenue between 32 owners",
    "NBA": "How the NBA's media rights deal pays every player's salary",
    "Olympics": "How the IOC makes billions while athletes go broke",
    "Formula 1": "How F1 monetizes a single race weekend",
    "Wimbledon": "How Wimbledon turns strawberries and TV rights into $350M/year",
    "NCAA": "How the NCAA built a billion-dollar 'amateur' sports empire",
    "UEFA": "How UEFA distributes Champions League money across Europe",
    "Super Bowl": "How one game generates $500M+ for a single city",
    "Coachella": "How Coachella turns music into a $1B fashion and brand deal machine",
    "Netflix": "How Netflix spends $17B on content and still profits",
    "Spotify": "How Spotify pays artists fractions of a cent and still loses money",
    "Amazon": "How AWS subsidizes everything else Amazon does",
    "Apple": "How Apple makes more from services than hardware now",
    "Nike": "How Nike makes money without owning a single factory",
    "Adidas": "How Adidas rebuilt after losing Kanye West ($250M/year)",
    "Tour de France": "How the Tour de France makes money with no ticket sales",
    "Glastonbury": "How Glastonbury stays affordable while generating $40M/year",
    "Eurovision": "How Eurovision became a $20M annual business for the EBU",
    "World Series": "How MLB's World Series revenue compares to the Super Bowl",
    # German football
    "Bundesliga": "How the Bundesliga makes €4B/year while keeping ticket prices the lowest in Europe",
    "Bayern Munich": "How Bayern Munich became Germany's most profitable club without a billionaire owner",
    "Borussia Dortmund": "How Borussia Dortmund makes money from a club that nearly went bankrupt in 2005",
    "RB Leipzig": "How Red Bull turned a fifth-division club into a Champions League contender in 10 years",
    "Bayer Leverkusen": "How a pharmaceutical company owns a football club — and why it works",
    "DFB": "How the German Football Association makes money from the national team",
    "DFL": "How the DFL distributes Bundesliga TV money across 18 clubs",
    "Stanley Cup": "How the NHL Stanley Cup playoffs generate $400M+ in revenue for the league",
}

SPORTS_KEYWORDS = list(ORG_ANGLES.keys()) + [
    "World Cup", "Champions League", "Premier League", "La Liga",
    "MLS", "IPL", "cricket", "tennis", "golf", "PGA", "boxing",
    "UFC", "WWE", "esports", "gaming tournament",
    # German football extras
    "Schalke", "Wolfsburg", "Eintracht", "Werder", "Hoffenheim",
    "VfB Stuttgart", "Freiburg", "Union Berlin",
]


GEO_CONFIG = {
    "US": {"trends": "https://trends.google.com/trending/rss?geo=US",
           "news": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"},
    "DE": {"trends": "https://trends.google.com/trending/rss?geo=DE",
           "news": "https://news.google.com/rss?hl=de&gl=DE&ceid=DE:de"},
}


def fetch_rss(url, count=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        feed = feedparser.parse(resp.read())
    return [entry.title for entry in feed.entries[:count]]


def fetch_trending(geo="US", count=20):
    config = GEO_CONFIG.get(geo.upper(), GEO_CONFIG["US"])
    try:
        topics = fetch_rss(config["trends"], count)
        console.print(f"[dim]Source: Google Trends RSS [{geo.upper()}] ({len(topics)} topics)[/dim]")
        return topics
    except Exception as e:
        console.print(f"[yellow]Trends RSS failed ({e}), falling back to Google News [{geo.upper()}]...[/yellow]")

    try:
        topics = fetch_rss(config["news"], count)
        console.print(f"[dim]Source: Google News RSS [{geo.upper()}] ({len(topics)} topics)[/dim]")
        return topics
    except Exception as e:
        console.print(f"[red]All sources failed for {geo.upper()}: {e}[/red]")
        return []


def match_orgs(trending_topics):
    matches = []
    for topic in trending_topics:
        topic_lower = topic.lower()
        for keyword in SPORTS_KEYWORDS:
            if keyword.lower() in topic_lower or topic_lower in keyword.lower():
                angle = ORG_ANGLES.get(keyword, f"Research how {keyword} makes money")
                matches.append({
                    "trending": topic,
                    "org": keyword,
                    "angle": angle,
                })
                break
    return matches


def show_trending_table(topics, geo="US"):
    geo_label = {"US": "United States", "DE": "Germany"}.get(geo.upper(), geo.upper())
    table = Table(title=f"Top Trending Topics ({geo_label})", box=box.SIMPLE_HEAVY)
    table.add_column("#", style="dim", width=3)
    table.add_column("Topic", style="bold")
    for i, topic in enumerate(topics[:15], 1):
        table.add_row(str(i), topic)
    console.print(table)


def show_opportunities(matches):
    if not matches:
        console.print(Panel(
            "[yellow]No direct org matches today.\nCheck back during a major sports event or scan manually.[/yellow]",
            title="Content Opportunities",
        ))
        return

    table = Table(title="Content Opportunities", box=box.ROUNDED, show_lines=True)
    table.add_column("Trending Topic", style="cyan", width=20)
    table.add_column("Org", style="bold green", width=15)
    table.add_column("Reel Angle", style="white")

    for m in matches:
        table.add_row(m["trending"], m["org"], m["angle"])

    console.print(table)
    console.print(f"\n[bold green]{len(matches)} opportunity(ies) found.[/bold green]")


def show_calendar():
    console.print(Panel(
        "[bold]Upcoming content calendar anchors:[/bold]\n\n"
        "  Jul 2026  —  Olympics (Paris)\n"
        "  Aug 2026  —  NFL Preseason\n"
        "  Sep 2026  —  F1 Season final stretch\n"
        "  Oct 2026  —  MLB World Series\n"
        "  Nov 2026  —  Formula 1 season end\n"
        "  Dec 2026  —  FIFA Club World Cup\n"
        "  Jan 2027  —  Super Bowl\n"
        "  Mar 2027  —  March Madness",
        title="Planned Calendar",
    ))


def main():
    console.print(Panel(
        "[bold cyan]Follow the Money[/bold cyan] — Trend Detection Tool\n"
        "[dim]Finds trending orgs and surfaces their revenue angle[/dim]",
        box=box.DOUBLE,
    ))

    args = sys.argv[1:]
    mode = "all"
    geos = ["US", "DE"]  # default: both
    research_mode = False
    script_mode = False

    for arg in args:
        if arg.upper() in GEO_CONFIG:
            geos = [arg.upper()]
        elif arg in ("trends", "calendar"):
            mode = arg
        elif arg == "research":
            research_mode = True
        elif arg == "script":
            script_mode = True

    all_matches = []

    if mode in ("all", "trends"):
        for geo in geos:
            console.print(f"\n[bold]Fetching Google Trends ({geo})...[/bold]")
            topics = fetch_trending(geo)
            if topics:
                show_trending_table(topics, geo)
                matches = match_orgs(topics)
                console.print()
                show_opportunities(matches)
                all_matches.extend(matches)
            else:
                console.print(f"[red]Could not fetch trending data for {geo}.[/red]")

    if mode in ("all", "calendar"):
        console.print()
        show_calendar()

    # Auto-launch research on first match
    if research_mode and all_matches:
        import subprocess
        org = all_matches[0]["org"]
        console.print(f"\n[bold cyan]Launching revenue research for: {org}[/bold cyan]")
        subprocess.run([sys.executable, "research.py", org])

    # Auto-generate script for first match
    if script_mode and all_matches:
        org = all_matches[0]["org"]
        console.print(f"\n[bold cyan]Generating reel script for: {org}[/bold cyan]")
        import script as script_module
        script_module.run(org, silent_research=True)


if __name__ == "__main__":
    main()
