"""Generate synthetic e-commerce microservice logs for hackathon prototype.

No proprietary data — all logs are fabricated for demonstration.

Usage:
    python scripts/generate_synthetic_logs.py
    python scripts/generate_synthetic_logs.py --output data/generated/logs.jsonl --hours 2
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVICES = ["api-gateway", "auth-service", "payment-service", "order-service", "inventory-service"]
LEVELS = ["INFO", "INFO", "INFO", "WARN", "ERROR"]
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]
ENDPOINTS = {
    "api-gateway": ["/api/v1/orders", "/api/v1/products", "/api/v1/users", "/api/v1/checkout"],
    "auth-service": ["/auth/login", "/auth/refresh", "/auth/validate", "/auth/logout"],
    "payment-service": ["/payments/charge", "/payments/refund", "/payments/status"],
    "order-service": ["/orders/create", "/orders/status", "/orders/cancel"],
    "inventory-service": ["/inventory/check", "/inventory/reserve", "/inventory/release"],
}


def _base_entry(ts: datetime, service: str, level: str, **extra) -> dict:
    return {
        "@timestamp": ts.isoformat(),
        "service": service,
        "level": level,
        "traceId": str(uuid.uuid4()),
        "requestId": str(uuid.uuid4())[:8],
        "environment": "hackathon-prototype",
        **extra,
    }


def _normal_traffic(ts: datetime) -> dict:
    service = random.choice(SERVICES)
    level = random.choice(LEVELS)
    latency = random.randint(20, 400)
    status = 200 if level != "ERROR" else random.choice([400, 404, 500])

    return _base_entry(
        ts,
        service,
        level,
        method=random.choice(HTTP_METHODS),
        endpoint=random.choice(ENDPOINTS[service]),
        statusCode=status,
        latencyMs=latency,
        message=f"{level}: {service} processed request in {latency}ms",
        userId=f"user-{random.randint(1000, 9999)}",
    )


def _payment_timeout_incident(ts: datetime) -> dict:
    return _base_entry(
        ts,
        "payment-service",
        "ERROR",
        method="POST",
        endpoint="/payments/charge",
        statusCode=504,
        latencyMs=random.randint(5000, 15000),
        message="ERROR: Payment gateway timeout — upstream provider did not respond within 30s",
        errorType="GatewayTimeout",
        orderId=f"ord-{random.randint(10000, 99999)}",
    )


def _auth_brute_force(ts: datetime) -> dict:
    return _base_entry(
        ts,
        "auth-service",
        "WARN",
        method="POST",
        endpoint="/auth/login",
        statusCode=random.choice([401, 403]),
        latencyMs=random.randint(50, 200),
        message="WARN: Authentication failed — invalid credentials",
        sourceIp=f"203.0.113.{random.randint(1, 254)}",
        attemptCount=random.randint(1, 50),
    )


def _db_pool_exhaustion(ts: datetime) -> dict:
    return _base_entry(
        ts,
        "order-service",
        "ERROR",
        method="POST",
        endpoint="/orders/create",
        statusCode=503,
        latencyMs=random.randint(2000, 5000),
        message="ERROR: Database connection pool exhausted — max connections (50) reached",
        errorType="ConnectionPoolExhausted",
        activeConnections=50,
    )


def _cascade_failure(ts: datetime, trace_id: str) -> list[dict]:
    """Simulate a request failing across multiple services with shared traceId."""
    return [
        _base_entry(
            ts,
            "api-gateway",
            "ERROR",
            method="POST",
            endpoint="/api/v1/checkout",
            statusCode=502,
            latencyMs=8200,
            message="ERROR: Bad gateway — downstream payment-service unavailable",
            traceId=trace_id,
        ),
        _base_entry(
            ts + timedelta(milliseconds=50),
            "payment-service",
            "ERROR",
            method="POST",
            endpoint="/payments/charge",
            statusCode=504,
            latencyMs=7900,
            message="ERROR: Payment gateway timeout",
            traceId=trace_id,
        ),
        _base_entry(
            ts + timedelta(milliseconds=120),
            "order-service",
            "ERROR",
            method="POST",
            endpoint="/orders/create",
            statusCode=500,
            latencyMs=150,
            message="ERROR: Order creation failed — payment not confirmed",
            traceId=trace_id,
        ),
    ]


def generate_logs(hours: int = 2, events_per_minute: int = 30) -> list[dict]:
    """Generate synthetic logs with injected incident scenarios."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    logs: list[dict] = []

    current = start
    incident_windows = [
        (start + timedelta(minutes=20), "payment_timeout", 15),
        (start + timedelta(minutes=45), "auth_brute_force", 25),
        (start + timedelta(minutes=70), "db_pool", 10),
        (start + timedelta(minutes=90), "cascade", 1),
    ]

    while current < now:
        for window_start, incident_type, count in incident_windows:
            if window_start <= current < window_start + timedelta(minutes=5):
                if incident_type == "payment_timeout" and random.random() < 0.3:
                    logs.append(_payment_timeout_incident(current))
                    continue
                if incident_type == "auth_brute_force" and random.random() < 0.5:
                    logs.append(_auth_brute_force(current))
                    continue
                if incident_type == "db_pool" and random.random() < 0.4:
                    logs.append(_db_pool_exhaustion(current))
                    continue
                if incident_type == "cascade" and count > 0:
                    trace_id = str(uuid.uuid4())
                    logs.extend(_cascade_failure(current, trace_id))
                    incident_windows = [
                        (w[0], w[1], w[2] - 1) if w[1] == "cascade" else w
                        for w in incident_windows
                    ]
                    continue

        for _ in range(events_per_minute // 6):
            logs.append(_normal_traffic(current + timedelta(seconds=random.randint(0, 9))))

        current += timedelta(seconds=10)

    logs.sort(key=lambda e: e["@timestamp"])
    return logs


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic log data")
    parser.add_argument("--output", default="data/generated/logs.jsonl", help="Output file path")
    parser.add_argument("--hours", type=int, default=2, help="Hours of log history")
    parser.add_argument("--rate", type=int, default=30, help="Events per minute")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    logs = generate_logs(hours=args.hours, events_per_minute=args.rate)

    with output.open("w", encoding="utf-8") as f:
        for entry in logs:
            f.write(json.dumps(entry) + "\n")

    print(f"Generated {len(logs)} log entries → {output}")
    print(f"Services: {', '.join(SERVICES)}")
    print("Injected scenarios: payment timeouts, auth brute force, DB pool exhaustion, cascade failures")


if __name__ == "__main__":
    main()
