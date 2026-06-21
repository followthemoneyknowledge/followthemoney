# Follow the Money — Content Pipeline Design

## Concept
Short-form reels (45–90s) that explain how trending organizations, sports leagues, and brands actually make money. Published at the peak of trending events to ride existing audience attention.

**Core value proposition:** Sports fans don't follow finance. Finance people don't follow sports. This content is the bridge.

---

## Market Research Summary (June 2026)

### Verified Findings
- The "follow the money" sub-niche for sports/org revenue breakdowns has **no verified dominant creator** — confirmed gap.
- Closest existing creators:
  - **Kyla Scanlon** (US) — macro-economy explainers → CNN analyst, Penguin book deal, Vanderbilt fellowship
  - **Sharan Hegde** (India, 1M+ Instagram) — comedic finance reels using character-driven skits, left Big 4 accounting full-time
- **TikTok Creator Rewards:** $0.40–$1.00 per 1,000 qualified views (video must be 1min+, viewer watches 5s+)
- Platform payments alone are not viable — real monetization comes from brand sponsorships → media deals → institutional roles

### Monetization Ladder (Verified Model)
```
Short-form builds audience
    ↓
Audience unlocks brand sponsorships (fintech, investing apps)
    ↓
Sponsorships + reach unlock media deals, newsletters, courses
```

### Open Questions
- Who owns this specific sub-niche right now (sports org revenue breakdowns)?
- What do brands like NFL, NBA, FIFA pay creators for this content type?
- What are verified YouTube Shorts RPM rates for finance content?

---

## Content Pipeline Design

### Phase 1 — Trend Detection

**Goal:** Identify a trending org/event before or at peak attention.

**Sources:**
- Google Trends (daily check)
- Twitter/X trending topics
- Sports calendar (FIFA, Olympics, Super Bowl, F1, Coachella, etc.)
- Reddit: r/worldnews, r/soccer, r/nfl, r/formula1

**Trigger criteria:**
- Event is trending nationally or globally
- Org has publicly available revenue data (annual reports, Statista)
- Angle is counterintuitive ("FIFA is a nonprofit — here's how they made $7.5B anyway")

**Planned calendar anchors:**
| Month | Event | Angle |
|---|---|---|
| Jan | Super Bowl | How the NFL makes money from one game |
| Mar | March Madness | NCAA's billion-dollar "amateur" model |
| Jun | Wimbledon | How tennis prize money actually works |
| Jul | Olympics | IOC revenue: who pays, who profits |
| Nov | F1 season end | How Formula 1 monetizes a race weekend |
| Dec | FIFA Club World Cup | FIFA's revenue model post-2026 |

---

### Phase 2 — Revenue Research

**Goal:** Gather 5–7 concrete numbers from primary sources.

**Primary sources (in order of trust):**
1. Official annual reports (FIFA, IOC, NFL, NBA all publish)
2. SEC filings (for publicly traded sports orgs)
3. Statista (paid data, high reliability)
4. Major outlet reporting (Bloomberg, WSJ, FT)
5. Wikipedia revenue tables (as a starting pointer only)

**Revenue buckets to always cover:**
- Broadcasting / media rights
- Sponsorship / advertising
- Ticket sales / matchday revenue
- Licensing / merchandise
- Prize money distribution
- Operational costs (for contrast)

**Target output:** A one-page data sheet with 5–7 sourced numbers before scripting begins.

---

### Phase 3 — Script Template

**Structure (45–90 seconds):**

```
[0–5s]   HOOK — One shocking number
          "FIFA made $7.5 billion from a single tournament."

[5–15s]  SETUP — Brief context
          "Here's how a nonprofit organization pulls that off."

[15–50s] BREAKDOWN — 3–4 revenue buckets with numbers
          "Broadcasting rights: $3B. Sponsorships: $1.7B. Tickets: $500M."

[50–75s] SURPRISING FACT — The counterintuitive close
          "And after paying out $630M in prize money, they still netted $4.4B."

[75–90s] CTA — Simple, one action
          "Follow for the next breakdown."
```

**Tone:** Informative but conversational. No jargon. Numbers must be human-scaled
("enough to buy 3 Premier League clubs").

---

### Phase 4 — Production Stack

**Minimum viable stack:**
| Tool | Purpose | Cost |
|---|---|---|
| CapCut / DaVinci Resolve | Video editing, captions | Free |
| Canva | Motion graphics, number cards | Free / $13/mo |
| ElevenLabs | AI voiceover (if no face cam) | $5/mo |
| Pexels / Unsplash | B-roll footage | Free |

**Optional upgrades:**
| Tool | Purpose | Cost |
|---|---|---|
| Adobe Premiere | Pro editing | $55/mo |
| Epidemic Sound | Licensed music | $15/mo |
| Descript | Auto-captions + editing | $24/mo |

**Format specs:**
- Aspect ratio: 9:16 (vertical)
- Length: 60–90s (TikTok Rewards minimum is 60s)
- Captions: Always on (85% of short-form is watched muted)
- Thumbnail: Bold number + org logo

---

### Phase 5 — Publishing Strategy

**Platforms (in priority order):**
1. **TikTok** — highest organic reach, $0.40–$1.00/1K views via Creator Rewards
2. **Instagram Reels** — repurpose same video, brand deal visibility
3. **YouTube Shorts** — long-tail searchability, cross-promotes long-form

**Posting cadence:**
- 2–3 reels/week minimum to stay in algorithm
- Always post within 24–48h of an event peaking in trending

**Cross-posting rule:** Same video, same day, all three platforms. No platform-exclusive content at start.

---

### Phase 6 — Monetization Progression

**Stage 1 — 0 to 10K followers**
- Pure content investment, no revenue
- Goal: establish format, build library, test hooks

**Stage 2 — 10K to 100K followers**
- Inbound brand inquiries start (fintech, investing apps, trading platforms)
- First sponsorship deals: $200–$2,000 per reel
- Start email list / newsletter as owned audience

**Stage 3 — 100K+ followers**
- Sponsorship rates: $2,000–$20,000 per reel
- Media deal potential (podcast, column, newsletter monetization)
- Course or paid community as secondary revenue

**Target sponsors for this niche:**
- Investing apps: Robinhood, eToro, Trading 212, Public
- Financial tools: YNAB, Copilot, QuickBooks
- Sports-adjacent fintech: Fanatics, DraftKings, Sorare

---

## Tooling — `trends.py`

### What It Does
A CLI tool that detects trending topics in real time and matches them against a curated list of orgs/events with pre-written revenue angles. Run it daily to decide what reel to produce next.

### How to Run

```bash
# Full output: trending topics + opportunities + calendar
python3 trends.py

# Trending topics and opportunities only
python3 trends.py trends

# Content calendar only
python3 trends.py calendar
```

### Data Sources
| Source | URL | Fallback order |
|---|---|---|
| Google Trends RSS | `trends.google.com/trending/rss?geo=US` | Primary |
| Google News RSS | `news.google.com/rss?hl=en-US&gl=US&ceid=US:en` | Fallback |

### Output
1. **Top Trending Topics (US)** — live list of what's trending right now
2. **Content Opportunities** — matched orgs with a suggested reel angle
3. **Planned Calendar** — fixed upcoming event anchors (Super Bowl, Olympics, etc.)

### Example Output (June 21, 2026)
```
Trending: "iran world cup"
→ Org: World Cup
→ Angle: Research how World Cup makes money
```

### Org Angle Library
Pre-loaded angles for 20 orgs including FIFA, NFL, NBA, Olympics, F1, Wimbledon,
NCAA, UEFA, Netflix, Spotify, Amazon, Apple, Nike, Adidas, and more.

When a new trending org is not in the library, the tool flags it with a generic
"Research how [org] makes money" prompt.

### Dependencies
```bash
pip3 install feedparser rich
```

### Next Planned Features
- [ ] Revenue research fetcher — auto-pull numbers from Wikipedia/annual reports when a match is found
- [ ] Script generator — draft the 90-second reel script from fetched numbers
- [ ] Expanded org library — add 50+ orgs with specific revenue angles

---

## MVP Plan (First 30 Days)

| Week | Goal | Output |
|---|---|---|
| 1 | Set up accounts, branding, tools | Profiles live on TikTok, Reels, Shorts |
| 2 | Produce first 3 reels | FIFA, NFL, one wildcard org |
| 3 | Post + analyze performance | Hook vs. retention data |
| 4 | Iterate format based on data | Refined script template |

**First reel topic:** FIFA 2026 Club World Cup — "How FIFA makes $1B from a tournament no one asked for."

---

## Success Metrics

| Metric | 30-day target | 90-day target |
|---|---|---|
| Followers (TikTok) | 1,000 | 10,000 |
| Views per reel | 10,000 avg | 100,000 avg |
| Email subscribers | 100 | 1,000 |
| Revenue | $0 | First sponsorship |
