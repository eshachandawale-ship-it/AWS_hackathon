#!/usr/bin/env python3
"""Print CloudWatch log errors as a compact single-line table.

Usage:
    python3 scripts/show_errors_table.py
    python3 scripts/show_errors_table.py --hours 2 --limit 20
    python3 scripts/show_errors_table.py --log-group /hackathon/log-analysis/ecommerce-platform --region us-west-2
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

try:
    import boto3
except ImportError:
    print("pip install boto3", file=sys.stderr)
    sys.exit(1)

DEFAULT_LOG_GROUP = "/hackathon/log-analysis/ecommerce-platform"

COLUMNS = ("TIME", "SERVICE", "LEVEL", "CODE", "MESSAGE")
WIDTHS = (19, 18, 5, 4, 50)


def _cell(text: str, width: int) -> str:
    text = str(text).replace("\n", " ").strip()
    if len(text) > width:
        return text[: width - 1] + "…"
    return text.ljust(width)


def print_table(rows: list[tuple]) -> None:
    header = "  ".join(_cell(h, w) for h, w in zip(COLUMNS, WIDTHS))
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(_cell(v, w) for v, w in zip(row, WIDTHS)))


def parse_message(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"message": raw}


def fetch_errors(log_group: str, region: str, hours: int, limit: int) -> list[tuple]:
    client = boto3.client("logs", region_name=region)
    start = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
    end = int(datetime.now(timezone.utc).timestamp() * 1000)

    resp = client.filter_log_events(
        logGroupName=log_group,
        startTime=start,
        endTime=end,
        filterPattern='{ $.level = "ERROR" || $.level = "WARN" }',
        limit=limit,
    )

    rows: list[tuple] = []
    for event in resp.get("events", []):
        data = parse_message(event["message"])
        ts = datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rows.append(
            (
                ts,
                data.get("service", "?"),
                data.get("level", "?"),
                data.get("statusCode", data.get("status", "-")),
                data.get("message", data.get("msg", event["message"][:80])),
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Show log errors as a compact table")
    parser.add_argument("--log-group", default=DEFAULT_LOG_GROUP)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    rows = fetch_errors(args.log_group, args.region, args.hours, args.limit)
    if not rows:
        print(f"No ERROR/WARN events in last {args.hours}h — run seed script first:")
        print("  python3 scripts/seed_cloudwatch_logs.py --generate --region us-west-2")
        return

    print(f"\nLog group: {args.log_group}  |  last {args.hours}h  |  {len(rows)} events\n")
    print_table(rows)
    print()


if __name__ == "__main__":
    main()
