# tiktic

**Personal resale ticket monitor for sold-out shows.**

Catch good deals (targeting ≤ $100 all-in) without living in browser tabs.

- **CashorTrade first** (face-value community — the best realistic path to low prices on sold-out tours)
- Full price history of *every* listing (above or below your cap)
- Hard configurable price cap that only gates notifications
- 300-mile radius from Burien, WA (WA / OR / BC Canada / Northern Idaho) — fully configurable
- Interactive decisions via Discord **or** Telegram ("Get it", "New threshold $85", "Pass because...")
- Clean, heavily commented Python codebase designed for learning

> **Status**: Early development (v0.1 in progress). Local `tiktic run` foreground mode only for now.

---

## Why this exists

All the good shows near you are sold out the second they go on sale. Resale is $200–$400+. CashorTrade and other fan-to-fan channels sometimes have real face-value or near-face-value tickets, but you can't watch 24/7.

tiktic watches the sources you care about, only bothers you when something is under your hard cap, and gives you a simple way to say "get it" or "wait for cheaper" — while quietly recording every listing (and every decision you make) so it can get smarter over time.

---

## Core Principles (non-negotiable)

- **CashorTrade is priority #1** for the $100 goal. We treat their platform with extreme respect (long delays, clear warnings, no auto-buying).
- **Notifications are gated**. A hard `price_cap_usd` (default 100) controls what you get pinged about.
- **History is sacred**. Every listing ever seen is stored with price, quantity, first/last seen, URL, etc. This data fuels future adaptive features.
- **The code should teach**. Exceptional comments, clean architecture, and learner-friendly design are first-class requirements.
- **You stay in control**. Interactive decisions. Easy to disable any source. Local-first.

---

## Quick Start (once v0.1 ships)

```bash
# After cloning + uv sync or pip install -e ".[dev]"
tiktic init                     # creates example config
tiktic config edit              # set your location, cap, artist, notifier tokens
tiktic seed-watch "Angine de Poitrine" --date 2026-10-15
tiktic run                      # foreground monitor with beautiful live table
```

See `tiktic --help` for everything.

---

## Configuration Highlights (`config.toml`)

```toml
[location]
home = "Burien, WA"
radius_miles = 300
included_regions = ["WA", "OR", "BC", "Northern ID"]   # explicit multi-region support

[price]
cap_usd = 100                    # hard cap. Notifications ONLY below this.
track_above_cap = true           # always true in this tool

[watch]
artists = ["Angine de Poitrine"]
# events = ["event-id-or-url"]   # or specific events

[notifiers]
enabled = ["discord", "telegram"]   # or just one
discord_webhook_url = "https://discord.com/api/webhooks/..."
telegram_bot_token = "..."
telegram_chat_id = "..."

[sources]
cashortrade_enabled = true
ticketmaster_enabled = true
seatgeek_enabled = true
```

Full schema and comments live in the code (`config.py`).

---

## Data Sources (v0.1)

| Priority | Source          | Method          | Notes / Risks                              |
|----------|-----------------|-----------------|--------------------------------------------|
| 1 (highest) | CashorTrade    | Playwright (respectful) | Best face-value chance. ToS prohibits automation — see warnings in code. |
| 2        | Ticketmaster   | Public Discovery API (`source=tmr`) | Good for resale existence + ranges. |
| 3        | SeatGeek       | Public API      | Strong event/venue/performer data + pricing signals. |

All sources are normalized to the same internal `Listing` model. Adding a new source is just implementing the `TicketClient` protocol.

**Legal / ToS note**: tiktic is for *personal* use only. We deliberately rate-limit, warn heavily, and make sources easy to disable. You are responsible for your own usage.

---

## Interactive Decisions (the fun part)

When a qualifying listing appears you get a rich card in Discord or Telegram with:

- Artist / date / venue / distance
- Price (all-in if available), quantity, section/row if known
- Direct link
- Buttons or reply commands:
  - `Get it`
  - `New threshold: 85`
  - `Pass (upper deck)`
  - `Snooze 2h`

Every decision is logged with the exact price at decision time + your reason. This is the foundation for Phase 5 adaptive suggestions ("You usually bite when it's < $92 in the 100s").

---

## Project Structure (clean layers)

```
src/tiktic/
├── cli.py                 # Typer entrypoint + commands
├── config.py              # Pydantic Settings + TOML + validation
├── models.py              # All domain models (heavily commented)
├── clients/
│   ├── base.py            # TicketClient protocol
│   ├── cashortrade.py     # Playwright scraper (highest priority)
│   ├── ticketmaster.py
│   └── seatgeek.py
├── services/
│   ├── monitor.py         # The polling loop
│   ├── evaluator.py       # Cap logic + deal scoring
│   └── decision.py        # Rich decision capture + state
├── notifications/
│   ├── base.py            # Notifier protocol (swappable)
│   ├── discord.py
│   ├── telegram.py
│   └── console.py         # Rich fallback
├── storage.py             # SQLite + full history
└── geo.py                 # 300mi + multi-region filtering
```

See the code for obsessive docstrings explaining *why* things are designed this way.

---

## Development

```bash
# Recommended: uv (or pip + venv)
uv sync --dev
pre-commit install
ruff check .
mypy src
pytest -q
tiktic --help
```

We use:
- `ruff` (lint + format)
- `mypy` strict
- `pytest` + `respx` for HTTP mocking
- `pre-commit`
- GitHub Actions CI on every push/PR

---

## Roadmap (high level)

**v0.1 (current)**: Local `tiktic run`, CashorTrade + TM + SG clients, hard cap + full history, Discord + Telegram, rich decisions, 300mi Burien WA geo, seeded with "Angine de Poitrine", exceptional comments.

**Later**:
- Smarter adaptive suggestions from your decision history
- Additional sources (StubHub etc.)
- Local Textual TUI mode
- Background service / Docker packaging
- Price trend visualizations

---

## Contributing / Philosophy

This is first and foremost a personal tool for the author, built in public as a learning project.

If you want to use it: great. Feedback and thoughtful PRs welcome, especially around:
- New respectful data sources
- Better deal scoring
- Making the comments even clearer for new Python learners

Please do **not** turn this into a high-speed scalper bot. That would violate the spirit (and likely the ToS of the sources).

---

## License

MIT — see [LICENSE](LICENSE).

---

Built with ❤️, paranoia about missing good tickets, and a strong belief that code should be readable and educational.

Seattle area • 2026
