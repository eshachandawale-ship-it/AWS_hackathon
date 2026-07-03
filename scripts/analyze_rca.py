#!/usr/bin/env python3
"""Extract a single primary Root Cause Analysis from CloudWatch logs.

Uses the same investigation strategy as the Log Analysis Agent tools:
  detect patterns → correlate traces → pick ONE primary RCA

Usage:
    python3 scripts/analyze_rca.py --region us-west-2
    python3 scripts/analyze_rca.py --region us-west-2 --hours 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import boto3
except ImportError:
    print("pip install boto3", file=sys.stderr)
    sys.exit(1)

LOG_GROUP = "/hackathon/log-analysis/ecommerce-platform"

# Known injected incident signatures (from generate_synthetic_logs.py)
INCIDENT_SIGNATURES = [
    {
        "id": "payment_gateway_timeout",
        "match": lambda m, s, c: s == 504 or (c == "payment-service" and s >= 500 and "timeout" in m.lower()),
        "rca": "Upstream payment provider did not respond within the 30s timeout window.",
        "service": "payment-service",
        "severity": "CRITICAL",
    },
    {
        "id": "db_pool_exhaustion",
        "match": lambda m, s, c: "connection pool exhausted" in m.lower() or s == 503,
        "rca": "order-service exhausted its database connection pool (max 50 connections).",
        "service": "order-service",
        "severity": "HIGH",
    },
    {
        "id": "auth_brute_force",
        "match": lambda m, s, c: s in (401, 403) and "auth" in m.lower(),
        "rca": "Burst of failed login attempts from a single IP — possible brute-force attack.",
        "service": "auth-service",
        "severity": "HIGH",
    },
    {
        "id": "cascade_failure",
        "match": lambda m, s, c: s in (502, 500) and "downstream" in m.lower() or "not confirmed" in m.lower(),
        "rca": "Downstream payment-service failure cascaded to order creation failures.",
        "service": "order-service",
        "severity": "HIGH",
    },
]


def fetch_error_events(client, hours: int, limit: int = 200) -> list[dict]:
    """Fetch ERROR/5xx events and parse JSON from @message."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    resp = client.filter_log_events(
        logGroupName=LOG_GROUP,
        startTime=int(start.timestamp() * 1000),
        endTime=int(end.timestamp() * 1000),
        filterPattern='{ $.level = "ERROR" || $.statusCode >= 500 }',
        limit=limit,
    )

    rows: list[dict] = []
    for event in resp.get("events", []):
        raw = event["message"]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"message": raw}
        ts = datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc).isoformat()
        rows.append(
            {
                "@timestamp": ts,
                "service": data.get("service", "unknown"),
                "statusCode": data.get("statusCode", 0),
                "@message": data.get("message", raw),
                "traceId": data.get("traceId", ""),
                "_raw": data,
            }
        )
    return rows


def run_query(client, query: str, hours: int) -> list[dict]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    resp = client.start_query(
        logGroupName=LOG_GROUP,
        startTime=int(start.timestamp() * 1000),
        endTime=int(end.timestamp() * 1000),
        queryString=query,
    )
    query_id = resp["queryId"]
    for _ in range(60):
        result = client.get_query_results(queryId=query_id)
        if result["status"] == "Complete":
            rows = []
            for row in result.get("results", []):
                rows.append({c["field"]: c["value"] for c in row})
            return rows
        if result["status"] in ("Failed", "Cancelled", "Timeout"):
            return []
        time.sleep(0.5)
    return []


def parse_status_code(value: str | int | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def pick_primary_incident(rows: list[dict]) -> dict | None:
    """Score incidents and return the single highest-priority root cause."""
    scores: dict[str, dict] = {}

    for row in rows:
        msg = str(row.get("@message", row.get("message", "")))
        raw_data = row.get("_raw", {})
        message = msg
        status = parse_status_code(row.get("statusCode") or raw_data.get("statusCode"))
        service = str(row.get("service") or raw_data.get("service", "unknown"))
        ts = row.get("@timestamp", raw_data.get("@timestamp", ""))
        trace = str(row.get("traceId") or raw_data.get("traceId", ""))

        for sig in INCIDENT_SIGNATURES:
            if sig["match"](message, status, service):
                key = sig["id"]
                if key not in scores:
                    scores[key] = {
                        **sig,
                        "count": 0,
                        "first_seen": ts,
                        "trace_ids": set(),
                        "evidence": [],
                    }
                scores[key]["count"] += 1
                if trace and trace != "unknown":
                    scores[key]["trace_ids"].add(trace)
                if len(scores[key]["evidence"]) < 3:
                    scores[key]["evidence"].append(
                        f"{ts} | {service} | HTTP {status} | {message[:70]}"
                    )

    if not scores:
        # Fallback: service with most ERROR events
        by_service: dict[str, int] = {}
        for row in rows:
            svc = str(row.get("service", "unknown"))
            by_service[svc] = by_service.get(svc, 0) + 1
        top_service = max(by_service, key=by_service.get)
        return {
            "id": "elevated_error_rate",
            "severity": "HIGH",
            "service": top_service,
            "rca": f"{top_service} generated the highest ERROR volume in the window — likely upstream dependency or resource exhaustion.",
            "count": by_service[top_service],
            "trace_ids": set(),
            "evidence": [
                f"{r.get('@timestamp')} | {r.get('service')} | HTTP {r.get('statusCode')} | {str(r.get('@message', ''))[:70]}"
                for r in rows
                if r.get("service") == top_service
            ][:3],
        }

    severity_rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}

    def rank(item: dict) -> tuple:
        return (
            severity_rank.get(item["severity"], 0),
            item["count"],
            len(item["trace_ids"]),
        )

    return max(scores.values(), key=rank)


def print_rca(incident: dict, hours: int, total_errors: int) -> None:
    print()
    print("=" * 72)
    print("  ROOT CAUSE ANALYSIS — Log Analysis Agent")
    print("=" * 72)
    print(f"  Log group : {LOG_GROUP}")
    print(f"  Window    : last {hours}h  |  {total_errors} ERROR events analyzed")
    print()
    print("  PRIMARY ROOT CAUSE")
    print("  " + "-" * 68)
    print(f"  Severity  : {incident['severity']}")
    print(f"  Service   : {incident['service']}")
    print(f"  Incident  : {incident['id'].replace('_', ' ').title()}")
    print(f"  Cause     : {incident['rca']}")
    print(f"  Events    : {incident['count']} matching log entries")
    if incident["trace_ids"]:
        sample = next(iter(incident["trace_ids"]))[:36]
        print(f"  TraceId   : {sample} (+ {len(incident['trace_ids']) - 1} correlated)")
    print()
    print("  EVIDENCE")
    print("  " + "-" * 68)
    for line in incident["evidence"]:
        print(f"  {line}")
    print()
    print("  RECOMMENDED ACTION")
    print("  " + "-" * 68)
    actions = {
        "payment_gateway_timeout": "Add circuit breaker + increase timeout; check payment provider SLA.",
        "db_pool_exhaustion": "Increase pool size or add connection queuing; investigate slow queries.",
        "auth_brute_force": "Block source IP at WAF; enable rate limiting on /auth/login.",
        "cascade_failure": "Fix upstream payment-service; add retry with backoff on order-service.",
        "elevated_error_rate": f"Inspect {incident['service']} dependencies, recent deploys, and error logs around peak timestamps.",
    }
    print(f"  1. {actions.get(incident['id'], 'Investigate affected service and deploy fix.')}")
    print("=" * 72)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract single RCA from CloudWatch logs")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--log-group", default=LOG_GROUP)
    args = parser.parse_args()

    global LOG_GROUP
    LOG_GROUP = args.log_group

    client = boto3.client("logs", region_name=args.region)

    error_rows = fetch_error_events(client, args.hours)

    if not error_rows:
        print("No ERROR events found. Seed logs first:")
        print("  python3 scripts/seed_cloudwatch_logs.py --generate --region us-west-2")
        sys.exit(1)

    incident = pick_primary_incident(error_rows)

    print_rca(incident, args.hours, len(error_rows))


if __name__ == "__main__":
    main()
