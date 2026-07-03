"""Seed synthetic logs into Amazon CloudWatch Logs.

Prerequisites:
    - AWS credentials configured
    - Log group created (run infrastructure stack or create manually)

Usage:
    python scripts/seed_cloudwatch_logs.py
    python scripts/seed_cloudwatch_logs.py --log-group /hackathon/log-analysis/ecommerce-platform
    python scripts/seed_cloudwatch_logs.py --input data/generated/logs.jsonl --region us-east-1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

DEFAULT_LOG_GROUP = "/hackathon/log-analysis/ecommerce-platform"
BATCH_SIZE = 100


def ensure_log_group(client, log_group: str, retention_days: int = 7) -> None:
    try:
        client.create_log_group(logGroupName=log_group)
        print(f"Created log group: {log_group}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise
        print(f"Log group already exists: {log_group}")

    try:
        client.put_retention_policy(
            logGroupName=log_group,
            retentionInDays=retention_days,
        )
    except ClientError:
        pass


def load_logs(input_path: Path) -> list[dict]:
    logs = []
    with input_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                logs.append(json.loads(line))
    return logs


def push_logs(client, log_group: str, logs: list[dict], stream_prefix: str = "synthetic") -> int:
    """Push logs to CloudWatch in batches, grouped by service."""
    by_service: dict[str, list[dict]] = {}
    for entry in logs:
        service = entry.get("service", "unknown")
        by_service.setdefault(service, []).append(entry)

    total = 0
    for service, service_logs in by_service.items():
        stream_name = f"{stream_prefix}/{service}/{int(time.time())}"
        client.create_log_stream(logGroupName=log_group, logStreamName=stream_name)

        events = []
        for entry in service_logs:
            payload = dict(entry)
            ts_str = payload.pop("@timestamp", None)
            if ts_str:
                from datetime import datetime

                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                timestamp_ms = int(ts.timestamp() * 1000)
            else:
                timestamp_ms = int(time.time() * 1000)

            events.append({
                "timestamp": timestamp_ms,
                "message": json.dumps(payload),
            })

        for i in range(0, len(events), BATCH_SIZE):
            batch = events[i : i + BATCH_SIZE]
            client.put_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                logEvents=batch,
            )
            total += len(batch)

        print(f"  Pushed {len(events)} events for {service}")

    return total


def publish_metrics(client, logs: list[dict], namespace: str = "Hackathon/LogAnalysis") -> None:
    """Publish aggregate error metrics to CloudWatch for the metrics tool."""
    from collections import defaultdict
    from datetime import datetime, timezone

    error_counts: dict[str, int] = defaultdict(int)
    for entry in logs:
        if entry.get("level") in ("ERROR", "CRITICAL") or entry.get("statusCode", 0) >= 500:
            error_counts[entry.get("service", "unknown")] += 1

    if not error_counts:
        return

    now = datetime.now(timezone.utc)
    for service, count in error_counts.items():
        client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": "ErrorCount",
                    "Dimensions": [{"Name": "Service", "Value": service}],
                    "Value": count,
                    "Unit": "Count",
                    "Timestamp": now,
                }
            ],
        )
    print(f"Published ErrorCount metrics for {len(error_counts)} services")


def main():
    parser = argparse.ArgumentParser(description="Seed CloudWatch with synthetic logs")
    parser.add_argument("--log-group", default=DEFAULT_LOG_GROUP)
    parser.add_argument("--input", default="data/generated/logs.jsonl")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--generate", action="store_true", help="Generate logs before seeding")
    parser.add_argument("--retention-days", type=int, default=7)
    args = parser.parse_args()

    input_path = Path(args.input)

    if args.generate or not input_path.exists():
        print("Generating synthetic logs...")
        subprocess.run(
            [sys.executable, "scripts/generate_synthetic_logs.py", "--output", str(input_path)],
            check=True,
        )

    logs = load_logs(input_path)
    print(f"Loaded {len(logs)} log entries from {input_path}")

    logs_client = boto3.client("logs", region_name=args.region)
    cw_client = boto3.client("cloudwatch", region_name=args.region)

    ensure_log_group(logs_client, args.log_group, args.retention_days)
    total = push_logs(logs_client, args.log_group, logs)
    publish_metrics(cw_client, logs)

    print(f"\nDone! Seeded {total} events to {args.log_group}")
    print(f"Test with: agentcore invoke \"Analyze errors in {args.log_group} from the last 2 hours\"")


if __name__ == "__main__":
    main()
