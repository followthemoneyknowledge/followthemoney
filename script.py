#!/usr/bin/env python3
"""
Reel script generator for "Follow the Money" content pipeline.

Usage:
    python script.py                          # auto-pick best org from ORG_ANGLES
    python script.py --org "FIFA"             # specific org
    python script.py --list                   # show all orgs + cooldown status
    python script.py --org "FIFA" --voice     # generate + synthesise voiceover
    python script.py --org "FIFA" --run       # generate + render reel
    python script.py --all                    # ignore cooldown
"""

import argparse
import json
import os
import re
import random
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from pipeline.research import (
    fetch_wikipedia_summary,
    fetch_wikipedia_financials,
    extract_money_mentions,
    search_news,
    TextExtractor,
    fetch_url,
)
from pipeline.trends import ORG_ANGLES

load_dotenv(SCRIPT_DIR / ".env", override=False)

REELS_DIR = SCRIPT_DIR / "reels"
DB_PATH   = SCRIPT_DIR / "data" / "pipeline.db"

OPENROUTER_KEY   = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-opus-4-5")
OPENROUTER_URL   = "https://openrouter.ai/api/v1/chat/completions"

ELEVENLABS_KEY   = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "LXu5MIFyvPZCxBst8fPP")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
EDGE_TTS_VOICE   = os.getenv("EDGE_TTS_VOICE", "en-US-GuyNeural")

POSTED_COOLDOWN_DAYS = 14

console = Console()


# ── Narrative angle library ────────────────────────────────────────────────────
# Each entry: (name, instruction, signal_tags)
# signal_tags must match keys in _signals() — used to weight angle selection.

_ANGLES = [
    ("the nonprofit paradox",
     "Open by revealing the org is legally a nonprofit, then immediately show the revenue number. "
     "Let the contrast land before explaining anything. "
     "Walk through how they avoid tax while generating billions. "
     "Close by asking what the word 'nonprofit' is actually doing in this sentence.",
     {"is_nonprofit": True, "revenue_above_billion": True}),

    ("the broadcast machine",
     "Open by showing how much the org earns before a single ticket is sold. "
     "Establish that broadcasting rights are the actual business — everything else is theatre. "
     "Walk through who pays, how much, and what they get in return. "
     "Close by noting that the sport itself is now a vehicle for the media deal.",
     {"has_media_rights": True, "is_sports_league": True}),

    ("the franchise fee model",
     "Open by explaining that teams or members pay in — not just receive. "
     "Show the revenue split structure and how the centre extracts value from every match, game, or event. "
     "Close by noting that owning a club is actually licensing a brand, not building one.",
     {"is_sports_league": True, "revenue_above_billion": True}),

    ("the sponsorship economy",
     "Open with the total sponsorship number — name it before explaining it. "
     "Walk through what brands actually buy when they attach their name: eyeballs, association, scarcity. "
     "Close by asking whether the org is in the sport business or the attention business.",
     {"has_sponsorship": True}),

    ("the prize money gap",
     "Open by naming the prize money — it sounds like a lot. "
     "Then show total revenue. Do the subtraction. "
     "The difference between what the org keeps and what it gives the athletes is the story. "
     "Close by asking who really wins when the biggest event in the sport is held.",
     {"has_prize_money": True, "revenue_above_billion": True}),

    ("the platform play",
     "Open by revealing how little the core product generates compared to the platform built around it. "
     "Show the revenue layer that subsidises the visible product. "
     "Close with the observation that the thing you think they sell is not the business.",
     {"is_tech_platform": True}),

    ("the 50+1 exception",
     "Open by explaining the German football ownership rule that stops billionaires buying clubs outright. "
     "Show how clubs inside this structure still generate nine-figure revenues. "
     "Close by asking whether the model protects the sport or just changes who extracts the surplus.",
     {"is_bundesliga": True}),

    ("the global event machine",
     "Open by naming a single event and its total revenue — make the number feel concrete. "
     "Walk through where the money comes from: rights, hospitality, licensing, tickets. "
     "Close by showing how much of it the host city actually keeps.",
     {"is_global_event": True}),

    ("the invisible employer",
     "Open by noting how many athletes, staff, and contractors depend on this org for their income. "
     "Then show the revenue — and show what percentage flows to the people performing. "
     "Close by naming what the rest finances.",
     {"has_prize_money": True, "is_sports_league": True}),

    ("the data play",
     "Open by revealing that the most valuable thing the org owns is not the sport, the event, or the brand — it's the data. "
     "Walk through how fan data, betting data, and broadcast data are monetised. "
     "Close by asking what the product actually is when attention is the asset.",
     {"is_tech_platform": True, "revenue_above_billion": True}),
]


# ── Hook templates ─────────────────────────────────────────────────────────────
# Tiered by revenue scale: (min_billion_threshold, [question variants], [answer variants])

_HOOKS = [
    (10,
     [
         "{org} made {amount} in a single year.",
         "{amount}. one year. one org.",
         "the number that makes {org} impossible to ignore: {amount}.",
         "{org} generated {amount}. here's the breakdown.",
     ],
     [
         "this isn't a rumour from a tabloid. it's in the annual report. "
         "{org} generated {amount} — and most of it came from sources most fans never think about.",
         "that number has been public for years. most people just haven't read the filing. "
         "{org} built a {amount} revenue machine, and the sport is only one piece of it.",
     ]),

    (1,
     [
         "{org} makes {amount} a year.",
         "{amount} a year. most people don't know where it goes.",
         "{org}: {amount} in revenue. here's how.",
         "what does {amount} buy {org}? influence, rights, and the sport itself.",
     ],
     [
         "a billion is a number most people use without meaning it. "
         "{org} earns it. the breakdown shows exactly where it comes from — "
         "and exactly who gets what.",
         "{org} is not in the business you think it's in. "
         "at {amount}, the real revenue drivers are more interesting than the sport.",
     ]),

    (0,
     [
         "{org} earns {amount} from this.",
         "the revenue number for {org}: {amount}.",
         "{amount} in annual revenue. here's the source.",
         "{org} and {amount}: where it comes from.",
     ],
     [
         "the number is public. the source breakdown is what most people miss. "
         "{org} generates {amount}, and the distribution tells you exactly who this organisation really serves.",
         "{org} is a business first. {amount} in revenue confirms it. "
         "what it spends that money on is a different — and more interesting — story.",
     ]),
]


# ── Data collection ────────────────────────────────────────────────────────────

def _collect_findings(org: str) -> tuple[list[dict], str]:
    """Returns (findings, wiki_summary) without printing the full research display."""
    import urllib.parse

    findings = []
    wiki_text    = fetch_wikipedia_financials(org)
    wiki_findings = extract_money_mentions(wiki_text, org) if wiki_text else []
    wiki_url     = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(org.replace(' ', '_'))}"
    for f in wiki_findings:
        f["source"] = "Wikipedia"
        f["url"]    = wiki_url
    findings.extend(wiki_findings)

    articles = search_news(org, max_results=4)
    for article in articles:
        try:
            html, final_url = fetch_url(article["url"])
            parser = TextExtractor()
            parser.feed(html)
            text = parser.get_text()
            for f in extract_money_mentions(text, org):
                f["source"] = article["source"]
                f["url"]    = final_url
                findings.append(f)
        except Exception:
            pass

    seen, unique = set(), []
    for f in findings:
        key = re.sub(r'\s+', '', f["amount"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(f)

    wiki_summary = fetch_wikipedia_summary(org)
    return unique[:8], wiki_summary


def _signals(org: str, findings: list[dict]) -> dict:
    """Derive boolean signals from org name + findings for angle scoring."""
    text     = " ".join(f.get("context", "") for f in findings).lower()
    org_low  = org.lower()
    amounts  = []
    for f in findings:
        raw = re.sub(r'[^\d.]', '', f.get("amount", "").split()[0])
        try:
            val = float(raw)
            if "billion" in f.get("amount", "").lower() or "bn" in f.get("amount", "").lower():
                val *= 1_000
            amounts.append(val)
        except ValueError:
            pass

    top_m = max(amounts) if amounts else 0  # value in millions

    nonprofits = {"fifa", "ioc", "ncaa", "ioc", "dfb", "dfl", "uefa", "rfu", "afl"}
    bundesliga_orgs = {"bundesliga", "bayern munich", "borussia dortmund", "rb leipzig",
                       "bayer leverkusen", "dfb", "dfl"}
    leagues = {"nfl", "nba", "mlb", "nhl", "bundesliga", "premier league", "la liga",
               "uefa", "fifa", "formula 1", "f1", "mls", "ncaa"}
    tech = {"netflix", "spotify", "amazon", "apple", "youtube", "tiktok", "meta"}
    events = {"super bowl", "world cup", "olympics", "wimbledon", "coachella",
              "glastonbury", "eurovision", "tour de france", "stanley cup"}

    return {
        "is_nonprofit":        any(n in org_low for n in nonprofits),
        "has_media_rights":    any(kw in text for kw in ("broadcast", "media rights", "tv deal", "television")),
        "has_sponsorship":     any(kw in text for kw in ("sponsor", "advertising", "naming rights")),
        "has_prize_money":     any(kw in text for kw in ("prize money", "prize fund", "purse")),
        "is_sports_league":    any(lg in org_low for lg in leagues),
        "is_tech_platform":    any(t in org_low for t in tech),
        "is_bundesliga":       any(b in org_low for b in bundesliga_orgs),
        "is_global_event":     any(ev in org_low for ev in events),
        "revenue_above_billion": top_m >= 1_000,
    }


def _score_angle(tags: dict, signals: dict) -> float:
    return sum(1 for k, v in tags.items() if signals.get(k) == v) + random.uniform(0, 0.4)


def _pick_angle(signals: dict) -> tuple[str, str]:
    name, instruction, _ = max(_ANGLES, key=lambda a: _score_angle(a[2], signals))
    return name, instruction


def _hook(org: str, findings: list[dict]) -> tuple[str, str]:
    amounts = []
    for f in findings:
        raw = re.sub(r'[^\d.]', '', f.get("amount", "").split()[0])
        try:
            val = float(raw)
            unit = f.get("amount", "").lower()
            if "trillion" in unit:
                val *= 1_000_000
            elif "billion" in unit or "bn" in unit:
                val *= 1_000
            amounts.append((val, f["amount"]))
        except ValueError:
            pass

    top_m, top_label = (max(amounts, key=lambda x: x[0]) if amounts else (0, "significant revenue"))
    top_b = top_m / 1_000

    fmt = dict(org=org, amount=top_label)
    for threshold, q_variants, a_variants in _HOOKS:
        if top_b >= threshold:
            return random.choice(q_variants).format(**fmt), random.choice(a_variants).format(**fmt)
    return f"{org} is bigger than you think.", "the numbers confirm it."


# ── Narration generation ───────────────────────────────────────────────────────

def _format_findings_for_prompt(findings: list[dict]) -> str:
    if not findings:
        return "No verified figures found — use general knowledge."
    return "\n".join(
        f"{i}. {f['amount']} — {f['context'][:150]} (Source: {f['source']})"
        for i, f in enumerate(findings, 1)
    )


def _generate_narration(org: str, findings: list[dict], wiki_summary: str,
                         angle_name: str, angle_instruction: str,
                         model: str = OPENROUTER_MODEL) -> str | None:
    if not OPENROUTER_KEY:
        console.print("  [red]✗ OPENROUTER_API_KEY not set — cannot generate narration[/red]")
        return None

    hook_q, _ = _hook(org, findings)

    prompt = f"""Write a 160–180 word voiceover script for a TikTok reel about how {org} makes money.
It must read naturally when spoken aloud at a calm, confident pace — exactly 60 to 75 seconds.
Do not include any preamble, label, section header, or title — output only the script text.

Revenue data:
{_format_findings_for_prompt(findings)}

Wikipedia context:
{wiki_summary[:300] if wiki_summary else 'Not available.'}

Hook to open with: "{hook_q}"

Tone: calm, editorial, finance journalist — no hype, no emojis, no hashtags.
Angle — {angle_name}:
{angle_instruction}

Structure:
[0–5s]   Hook — the opening line above, delivered exactly
[5–15s]  Setup — brief context that makes the hook surprising
[15–50s] Breakdown — 3–4 revenue streams with exact numbers, one sentence each
[50–75s] Surprising fact — the counterintuitive close most people miss
[75–90s] CTA — end with: "follow for the next breakdown."

Speak directly to the viewer. Short sentences. No filler phrases. Output only the script text, nothing else."""

    try:
        r = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "HTTP-Referer": "https://github.com/fol.lowthemoneyknowledge/fol.lowthemoney",
                "X-Title": "follow-the-money-reel",
            },
            json={
                "model":       model,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  400,
                "temperature": 0.75,
            },
            timeout=40,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        text = re.sub(r"(?i)^(here'?s?( is)?( the)? script:?\s*)+", "", text).strip()
        console.print(f"  [green]✓[/green] Narration generated ({len(text.split())} words)")
        return text
    except Exception as e:
        console.print(f"  [red]✗ OpenRouter error: {e}[/red]")
        return None


# ── Reveal sequence ────────────────────────────────────────────────────────────

def _build_reveal(org: str, findings: list[dict], brand: str,
                   n_sections: int, voice_duration: float = 0.0) -> list[dict]:
    """
    5-act reveal matching the HOOK → SETUP → BREAKDOWN → SURPRISING FACT → CTA structure.
    Returns per-frame caption data for reel_config.py.
    """
    hook_q, hook_a = _hook(org, findings)
    top_finding = findings[0] if findings else {"amount": "significant revenue", "context": ""}

    tag = f"{brand}  ·  follow the money"

    if voice_duration > 0:
        timings = [
            round(voice_duration * 0.07, 1),   # hook
            round(voice_duration * 0.13, 1),   # setup
            round(voice_duration * 0.47, 1),   # breakdown
            round(voice_duration * 0.28, 1),   # surprising fact
            round(voice_duration * 0.10, 1),   # cta
        ]
    else:
        timings = [5.0, 10.0, 35.0, 25.0, 10.0]

    def _frame(show_caption: bool, line1: str, line2: str, line3: str,
               hook_question, upper_title: str, hold: float) -> dict:
        return {
            "show_caption":  show_caption,
            "tag":           tag,
            "line1":         line1,
            "line2":         line2,
            "line3":         line3,
            "hook_question": hook_question,
            "hook_answer":   "",
            "upper_artist":  "",
            "upper_title":   upper_title,
            "hold_seconds":  hold,
        }

    frames = [
        # Act I — hook question (title frame)
        _frame(False, "", "", "", hook_q, org, timings[0]),
        # Act II — setup (clean)
        _frame(False, "", "", "", None, org, timings[1]),
        # Act III — breakdown (key number displayed)
        _frame(True, top_finding["amount"], "revenue", hook_a, None, org, timings[2]),
        # Act IV — surprising fact (clean)
        _frame(False, "", "", "", None, org, timings[3]),
        # Act V — CTA
        _frame(True, "follow", "for the next", "breakdown.", None, org, timings[4]),
    ]
    return frames


# ── Config generation ──────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _generate_config(org: str, reel_slug: str, brand: str,
                      findings: list[dict], angle_name: str,
                      reveal: list[dict],
                      narration_captions: list[dict] | None = None) -> str:
    top = findings[0] if findings else {"amount": "significant revenue"}
    hook_q, hook_a = _hook(org, findings)

    caption_full = (
        f"{org} generated {top['amount']} — and most people have no idea where it comes from. "
        f"{hook_a} "
        f"follow @fol.lowthemoney for the next breakdown."
    )

    _e = _esc
    lines = [
        '"""',
        f"╔══════════════════════════════════════════════════════════════╗",
        f"║  REEL CONFIG — {org:<44}  ║",
        f"║  Generated by script.py  ·  angle: {angle_name:<24}  ║",
        f"╚══════════════════════════════════════════════════════════════╝",
        '"""',
        "",
        "CONFIG = {",
        f'    "lot_id":         "{_e(reel_slug)}",',
        "",
        "    # ── Caption ────────────────────────────────────────────────",
        f'    "caption_tag":    "{_e(brand)}  ·  follow the money",',
        f'    "caption_line1":        "{_e(top["amount"])}",',
        f'    "caption_line2_label":  "annual revenue",',
        f'    "caption_line2":        "{_e(org)}",',
        f'    "caption_line3":        "here\'s how",',
        "",
        "    # ── Location metadata ─────────────────────────────────────",
        f'    "location_coords": "FOLLOW THE MONEY",',
        f'    "location_name":   "{_e(org.upper())}",',
        f'    "location_season": "{date.today().year}  ·  REVENUE BREAKDOWN",',
        f'    "frame_label":     "{_e(brand)}",',
        "",
        "    # ── Layout ────────────────────────────────────────────────",
        '    "photo_split":        False,',
        '    "photo_fit_first":    True,',
        '    "photo_center_crop":  True,',
        '    "hide_chrome":        False,',
        '    "block_reveal":       False,',
        '    "caption_no_box":     False,',
        "",
        "    # ── Style ─────────────────────────────────────────────────",
        '    "vibe":             "finance_editorial",',
        '    "caption_position": "center",',
        "",
        "    # ── Colours ───────────────────────────────────────────────",
        "    \"color_tag\":   (240, 240, 240),",
        "    \"color_line1\": (255, 215, 0),    # gold — the money number",
        "    \"color_line2\": (240, 240, 240),",
        "    \"color_line3\": (200, 200, 200),",
        "",
        "    \"caption_all_frames\": False,",
        "    \"cover_hold_seconds\": 2.0,",
        "",
        "    # ── Pacing ────────────────────────────────────────────────",
        '    "fps":          5,',
        '    "hold_seconds": 0.0,',
        '    "fade_seconds": 0.6,',
        "",
        "    # ── Social captions ───────────────────────────────────────",
        '    "topic":          "finance",',
        f'    "location":       "{_e(org.lower())}",',
        f'    "season":         "{date.today().year}",',
        '    "caption_full":   (',
        f'        "{_e(caption_full)}"',
        "    ),",
        f'    "caption_hero":   "{_e(hook_q)}",',
        f'    "personal_note":  "{_e(hook_a)}",',
        '    "engagement_hook": "what organisation should we break down next?",',
    ]

    if reveal:
        lines.append("")
        lines.append("    # ── Per-frame reveal ──────────────────────────────────────")
        lines.append('    "per_frame_captions": [')
        for fc in reveal:
            lines.append("        {")
            for key, val in fc.items():
                lines.append(f"            {repr(key)}: {repr(val)},")
            lines.append("        },")
        lines.append("    ],")

    if narration_captions:
        lines.append("")
        lines.append("    # ── Word-by-word narration captions ───────────────────────")
        lines.append('    "narration_captions": [')
        for cap in narration_captions:
            lines.append(
                f"        {{\"start\": {cap['start']:.3f}, "
                f"\"end\": {cap['end']:.3f}, "
                f"\"text\": {repr(cap['text'])}}},")
        lines.append("    ],")

    lines.append("}")
    return "\n".join(lines) + "\n"


# ── Voice synthesis ────────────────────────────────────────────────────────────

def _synthesise_voice(text: str, out_path: Path) -> float:
    """Synthesise voiceover. Returns audio duration in seconds, or 0.0 on failure."""
    if ELEVENLABS_KEY:
        try:
            r = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
                headers={
                    "xi-api-key": ELEVENLABS_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text":    text,
                    "model_id": ELEVENLABS_MODEL,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=60,
            )
            r.raise_for_status()
            out_path.write_bytes(r.content)
            console.print(f"  [green]✓[/green] ElevenLabs audio → {out_path.name}")
        except Exception as e:
            console.print(f"  [yellow]⚠ ElevenLabs failed ({e}) — trying edge-tts fallback[/yellow]")
            ELEVENLABS_KEY and _edge_tts_fallback(text, out_path)
    else:
        _edge_tts_fallback(text, out_path)

    return _audio_duration(out_path) if out_path.exists() else 0.0


def _edge_tts_fallback(text: str, out_path: Path) -> None:
    try:
        import asyncio, edge_tts
        async def _run():
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            await communicate.save(str(out_path))
        asyncio.run(_run())
        console.print(f"  [green]✓[/green] edge-tts audio → {out_path.name}")
    except Exception as e:
        console.print(f"  [red]✗ edge-tts failed: {e}[/red]")


def _audio_duration(path: Path) -> float:
    try:
        import subprocess as sp
        result = sp.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ── SQLite tracking ────────────────────────────────────────────────────────────

def _ensure_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posted_reels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            org         TEXT NOT NULL,
            angle       TEXT,
            reel_slug   TEXT,
            reel_dir    TEXT,
            voice_used  INTEGER DEFAULT 0,
            brand       TEXT,
            posted_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _posted_orgs(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT org, posted_at FROM posted_reels "
        "WHERE posted_at >= datetime('now', ?)",
        (f"-{POSTED_COOLDOWN_DAYS} days",),
    ).fetchall()
    return {r["org"]: r["posted_at"] for r in rows}


def _record_posted(conn: sqlite3.Connection, org: str, angle: str,
                    reel_slug: str, reel_dir: str,
                    *, voice_used: bool = False, brand: str = "") -> None:
    conn.execute(
        "INSERT INTO posted_reels (org, angle, reel_slug, reel_dir, voice_used, brand) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (org, angle, reel_slug, reel_dir, int(voice_used), brand),
    )
    conn.commit()


# ── List mode ──────────────────────────────────────────────────────────────────

def _print_list(posted: dict) -> None:
    table = Table(title="Follow the Money — Org Library", box=box.SIMPLE_HEAVY)
    table.add_column("Org", style="bold cyan", width=22)
    table.add_column("Angle", style="white")
    table.add_column("Status", style="dim", width=14)

    for org, angle in sorted(ORG_ANGLES.items()):
        status = f"[dim]on cooldown[/dim]" if org in posted else "[green]ready[/green]"
        table.add_row(org, angle[:70], status)
    console.print(table)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Follow the Money reel script for a trending org."
    )
    parser.add_argument("--org",    default=None, help="Org name (e.g. 'FIFA')")
    parser.add_argument("--list",   action="store_true", help="List all orgs and exit")
    parser.add_argument("--voice",  action="store_true", help="Synthesise voiceover via ElevenLabs")
    parser.add_argument("--images", action="store_true", help="Fetch images from Wikimedia Commons")
    parser.add_argument("--run",    action="store_true", help="Render reel after generation")
    parser.add_argument("--all",    action="store_true", help="Ignore cooldown — pick any org")
    parser.add_argument("--brand",  default="@fol.lowthemoney", help="Brand handle for captions")
    parser.add_argument("--model",  default=OPENROUTER_MODEL, help="OpenRouter model override")
    args = parser.parse_args()

    console.print(Panel(
        "[bold cyan]Follow the Money[/bold cyan] — Reel Generator\n"
        "[dim]Research · Script · Config · Voice[/dim]",
        box=box.DOUBLE,
    ))

    conn   = _ensure_db()
    posted = _posted_orgs(conn)

    if args.list:
        _print_list(posted)
        conn.close()
        return

    # ── Pick org ───────────────────────────────────────────────
    if args.org:
        org = args.org
    else:
        pool = [o for o in ORG_ANGLES if o not in posted] if not args.all else list(ORG_ANGLES)
        if not pool:
            console.print(f"  [yellow]ℹ All orgs on cooldown — picking least-recently posted.[/yellow]")
            pool = sorted(ORG_ANGLES, key=lambda o: posted.get(o, ""))
        org = random.choice(pool)
        console.print(f"[dim]Auto-selected org: {org}[/dim]")

    console.print(f"\n[bold]▸ Org:[/bold] {org}")

    # ── Research ───────────────────────────────────────────────
    console.print("\n[bold]▸ Researching revenue data...[/bold]")
    findings, wiki_summary = _collect_findings(org)
    console.print(f"  [dim]{len(findings)} revenue figure(s) found[/dim]")

    # ── Pick angle ─────────────────────────────────────────────
    signals    = _signals(org, findings)
    angle_name, angle_instruction = _pick_angle(signals)
    console.print(f"  [dim]Angle: {angle_name}[/dim]")

    # ── Generate narration ─────────────────────────────────────
    if not OPENROUTER_KEY:
        console.print("[red]Error: OPENROUTER_API_KEY not set.[/red]")
        console.print("[dim]Add it to .env or: export OPENROUTER_API_KEY=your_key[/dim]")
        conn.close()
        sys.exit(1)

    console.print("\n[bold]▸ Generating narration script...[/bold]")
    narration = _generate_narration(org, findings, wiki_summary, angle_name, angle_instruction,
                                     model=args.model)
    if not narration:
        conn.close()
        sys.exit(1)

    # ── Create reel folder ─────────────────────────────────────
    slug     = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9-]", "-", org.lower())).strip("-")
    reel_slug = f"ftm-{slug}-{date.today().isoformat()}"
    reel_dir  = REELS_DIR / reel_slug
    reel_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]▸ Reel folder:[/bold] reels/{reel_slug}/")

    # ── Save narration text ────────────────────────────────────
    script_path = reel_dir / "narration.txt"
    script_path.write_text(f"# Follow the Money — {org}\n# Angle: {angle_name}\n\n{narration}\n")
    console.print(f"  [green]✓[/green] narration.txt")

    # ── Voiceover (optional) ───────────────────────────────────
    voice_duration  = 0.0
    narr_captions:  list[dict] = []

    if args.voice:
        console.print("\n[bold]▸ Synthesising voiceover...[/bold]")
        vo_path = reel_dir / "voiceover.mp3"
        voice_duration = _synthesise_voice(narration, vo_path)
        if voice_duration > 0:
            console.print(f"  Audio duration: {voice_duration:.1f}s")

    # ── Fetch images from Wikimedia Commons (optional) ────────
    if args.images:
        console.print("\n[bold]▸ Fetching images from Wikimedia Commons...[/bold]")
        from pipeline.fetch_images import download_images as _dl_images
        saved = _dl_images(org, reel_dir / "images")
        console.print(f"  [green]✓[/green] {len(saved)} image(s) → images/")

    # ── Build reveal + config ──────────────────────────────────
    reveal      = _build_reveal(org, findings, args.brand, 5, voice_duration)
    config_src  = _generate_config(org, reel_slug, args.brand, findings,
                                    angle_name, reveal,
                                    narration_captions=narr_captions or None)
    config_path = reel_dir / "reel_config.py"
    config_path.write_text(config_src)
    console.print(f"  [green]✓[/green] reel_config.py")

    # ── Display narration preview ──────────────────────────────
    console.print()
    console.print(Panel(narration, title=f"[bold]{org}[/bold] — narration preview",
                         subtitle=f"angle: {angle_name}", box=box.ROUNDED))

    words     = len(narration.split())
    read_time = round(words / 2.5)
    console.print(f"[dim]Words: {words} | Est. read time: ~{read_time}s[/dim]")

    # ── Record ─────────────────────────────────────────────────
    _record_posted(conn, org, angle_name, reel_slug, str(reel_dir.relative_to(SCRIPT_DIR)),
                   voice_used=args.voice and voice_duration > 0, brand=args.brand)
    conn.close()

    # ── Summary ────────────────────────────────────────────────
    console.print()
    console.print("═" * 62)
    console.print("  READY TO RENDER")
    console.print(f"  Reel folder: reels/{reel_slug}/")
    console.print()
    console.print("  Files:")
    console.print(f"    narration.txt    — spoken script")
    console.print(f"    reel_config.py   — render config")
    if args.voice and voice_duration > 0:
        console.print(f"    voiceover.mp3    — synthesised audio")
    if not args.images:
        console.print()
        console.print("  Add images (pick one):")
        console.print(f"    python pipeline/fetch_images.py \"{org}\" reels/{reel_slug}")
        console.print(f"    python pipeline/fetch_images.py \"{org}\" reels/{reel_slug} --query \"stadium crowd\"")
        console.print(f"    # or drop JPGs manually into reels/{reel_slug}/images/")
    console.print()
    console.print("  To render:")
    console.print(f"    python reel/make_reel.py reels/{reel_slug}")
    console.print("═" * 62)

    if args.run:
        reel_template = SCRIPT_DIR / "reel" / "make_reel.py"
        if reel_template.exists():
            console.print("\n[bold]▸ Running make_reel.py...[/bold]")
            subprocess.run([sys.executable, str(reel_template), str(reel_dir)])
        else:
            console.print("[yellow]  ⚠ reel/make_reel.py not found — skipping render[/yellow]")


if __name__ == "__main__":
    main()
