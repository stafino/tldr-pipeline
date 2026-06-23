"""Once-a-day digest tweet of today's top EU funding rounds.

Designed to be called at the end of cron-refresh.sh. Idempotent:
- Only tweets between POST_WINDOW_START and POST_WINDOW_END (UTC) so we
  don't fire at 3 AM when no one's looking.
- State file data/funding/.tweeted.json tracks the last date tweeted, so
  re-runs during the same UTC day no-op.

Env vars (required for actual posting; --dry-run skips them):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET

Usage:
  python scripts/tweet_funding.py --dry-run    # show what would post
  python scripts/tweet_funding.py              # actually post (during window)
  python scripts/tweet_funding.py --force-window  # bypass time guard
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("tweet_funding")

# Configuration (env-overridable)
POST_WINDOW_START = int(os.environ.get("TWEET_WINDOW_START_UTC", "9"))
POST_WINDOW_END = int(os.environ.get("TWEET_WINDOW_END_UTC", "11"))
MIN_USD = int(os.environ.get("TWEET_MIN_USD", "5000000"))
MAX_ROUNDS_IN_TWEET = 5
TWEET_MAX = 280
SITE_URL = "trylede.com/funding"
TWEETED_STATE = Path("data/funding/.tweeted.json")

# Country -> flag emoji. Covers everything we currently classify as EU.
COUNTRY_FLAGS = {
    "germany": "🇩🇪", "france": "🇫🇷", "uk": "🇬🇧", "united kingdom": "🇬🇧",
    "england": "🇬🇧", "scotland": "🇬🇧", "wales": "🇬🇧", "northern ireland": "🇬🇧",
    "spain": "🇪🇸", "italy": "🇮🇹", "netherlands": "🇳🇱", "sweden": "🇸🇪",
    "switzerland": "🇨🇭", "ireland": "🇮🇪", "poland": "🇵🇱", "belgium": "🇧🇪",
    "denmark": "🇩🇰", "finland": "🇫🇮", "norway": "🇳🇴", "austria": "🇦🇹",
    "portugal": "🇵🇹", "czechia": "🇨🇿", "czech republic": "🇨🇿",
    "estonia": "🇪🇪", "latvia": "🇱🇻", "lithuania": "🇱🇹", "iceland": "🇮🇸",
    "luxembourg": "🇱🇺", "greece": "🇬🇷", "romania": "🇷🇴", "bulgaria": "🇧🇬",
    "hungary": "🇭🇺", "slovakia": "🇸🇰", "slovenia": "🇸🇮", "croatia": "🇭🇷",
    "cyprus": "🇨🇾", "malta": "🇲🇹",
}


def _format_amount(usd: float | None, raw: str) -> str:
    if not usd:
        return raw or "?"
    if usd >= 1e9:
        return f"${usd/1e9:.1f}B".replace(".0B", "B")
    if usd >= 1e6:
        return f"${round(usd/1e6)}M"
    return f"${round(usd/1e3)}K"


def _flag(country: str) -> str:
    return COUNTRY_FLAGS.get((country or "").lower().strip(), "🇪🇺")


def _short_stage(label: str) -> str:
    """Compress "Series A" -> "A", "Pre-Seed" -> "Pre-Seed", etc."""
    t = (label or "").strip()
    if t.lower().startswith("series "):
        return t.split()[-1].upper()
    return t


def load_today_rounds(today: str) -> list[dict]:
    f = Path(f"data/funding/{today}.jsonl")
    if not f.exists():
        return []
    rounds = []
    for line in f.read_text().splitlines():
        if line.strip():
            rounds.append(json.loads(line))
    return rounds


def compose_tweet(rounds: list[dict], today: str) -> str:
    """Pack as many rounds as fit under TWEET_MAX."""
    header = f"🇪🇺 EU venture funding · {today}\n\n"
    footer = f"\n\n{SITE_URL}"

    lines: list[str] = []
    for r in rounds[:MAX_ROUNDS_IN_TWEET]:
        amt = _format_amount(r.get("amount_usd"), r.get("amount_raw", ""))
        flag = _flag(r.get("country", ""))
        stage = _short_stage(r.get("round_label", ""))
        company = (r.get("company") or "?")[:25]
        line = f"{flag} {amt} {company}"
        if stage:
            line += f" ({stage})"
        # First investor only. Word-boundary trim, strip trailing connectors
        invs = r.get("investors") or []
        if invs:
            inv = invs[0]
            if len(inv) > 30:
                cut = inv.rfind(" ", 0, 30)
                inv = inv[:cut] if cut > 12 else inv[:30]
            inv = inv.rstrip(" &,-/")  # drop dangling connectors after the cut
            if inv:
                line += f", led by {inv}"
        # Check whether adding this line still fits
        trial = header + "\n".join(lines + [line]) + footer
        if len(trial) > TWEET_MAX:
            break
        lines.append(line)

    if not lines:
        return ""
    return header + "\n".join(lines) + footer


def already_tweeted_today(today: str) -> bool:
    if not TWEETED_STATE.exists():
        return False
    try:
        state = json.loads(TWEETED_STATE.read_text())
    except json.JSONDecodeError:
        return False
    return state.get("last_date") == today


def mark_tweeted(today: str, tweet_id: str | None) -> None:
    TWEETED_STATE.parent.mkdir(parents=True, exist_ok=True)
    TWEETED_STATE.write_text(
        json.dumps({"last_date": today, "tweet_id": tweet_id, "posted_at": datetime.now(timezone.utc).isoformat()})
    )


def in_posting_window() -> bool:
    h = datetime.now(timezone.utc).hour
    return POST_WINDOW_START <= h < POST_WINDOW_END


def post_tweet(text: str) -> str | None:
    try:
        import tweepy  # type: ignore
    except ImportError:
        raise RuntimeError("tweepy not installed. Run: uv add tweepy")

    creds = {
        "consumer_key": os.environ.get("X_API_KEY"),
        "consumer_secret": os.environ.get("X_API_SECRET"),
        "access_token": os.environ.get("X_ACCESS_TOKEN"),
        "access_token_secret": os.environ.get("X_ACCESS_SECRET"),
    }
    missing = [k for k, v in creds.items() if not v]
    if missing:
        raise RuntimeError(f"X_* env vars missing: {missing}")

    client = tweepy.Client(**creds)
    resp = client.create_tweet(text=text)
    return resp.data.get("id") if resp and resp.data else None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="print the tweet but don't post")
    p.add_argument("--force-window", action="store_true", help="bypass the UTC posting window check")
    p.add_argument("--date", help="YYYY-MM-DD; default = today UTC")
    args = p.parse_args()

    today = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not args.force_window and not in_posting_window():
        log.info("skip: outside posting window (%d-%d UTC)", POST_WINDOW_START, POST_WINDOW_END)
        return 0

    if already_tweeted_today(today) and not args.dry_run:
        log.info("skip: already tweeted for %s", today)
        return 0

    rounds = load_today_rounds(today)
    eu_all = [
        r for r in rounds
        if r.get("region") == "EU" and (r.get("amount_usd") or 0) >= MIN_USD
    ]
    # Inline dedup: two sources often cover the same round. Group by
    # (lowercased company, amount_usd) and keep the one with the most
    # investors recorded (best metadata).
    by_key: dict[tuple[str, float], dict] = {}
    for r in eu_all:
        key = ((r.get("company") or "").strip().lower(), float(r.get("amount_usd") or 0))
        existing = by_key.get(key)
        if existing is None or len(r.get("investors") or []) > len(existing.get("investors") or []):
            by_key[key] = r
    eu = list(by_key.values())
    eu.sort(key=lambda r: r.get("amount_usd") or 0, reverse=True)

    if not eu:
        log.info("skip: no EU rounds >= $%dM for %s", MIN_USD // 1_000_000, today)
        return 0

    text = compose_tweet(eu, today)
    if not text:
        log.info("skip: nothing fit in tweet (rare; check formatter)")
        return 0

    print("=" * 60)
    print(text)
    print("=" * 60)
    print(f"({len(text)} chars; {min(len(eu), MAX_ROUNDS_IN_TWEET)} rounds shown of {len(eu)})")

    if args.dry_run:
        log.info("dry-run: not posting")
        return 0

    tweet_id = post_tweet(text)
    mark_tweeted(today, tweet_id)
    log.info("posted tweet %s", tweet_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
