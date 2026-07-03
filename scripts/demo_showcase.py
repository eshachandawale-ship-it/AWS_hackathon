#!/usr/bin/env python3
"""
Offline demo — shows what Log Analysis Agent output looks like.
No AWS deploy required. Run: python3 scripts/demo_showcase.py
"""

from __future__ import annotations

import json
import sys
import textwrap
import time
from datetime import datetime, timezone

# ── ANSI colours (works in most terminals) ──────────────────────────────────
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def pause(seconds: float = 0.4):
    time.sleep(seconds)


def header(title: str):
    width = 72
    print(f"\n{BOLD}{CYAN}{'═' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * width}{RESET}\n")


def step(label: str, detail: str = ""):
    print(f"{GREEN}▶{RESET} {BOLD}{label}{RESET}")
    if detail:
        for line in detail.splitlines():
            print(f"  {DIM}{line}{RESET}")
    pause(0.3)


def tool_call(name: str, args: dict, result_summary: str):
    print(f"\n  {YELLOW}🔧 Tool:{RESET} {BOLD}{name}{RESET}")
    print(f"  {DIM}Args: {json.dumps(args)}{RESET}")
    pause(0.5)
    print(f"  {DIM}Result: {result_summary}{RESET}")
    pause(0.4)


def agent_response(text: str):
    print(f"\n{BOLD}{'─' * 72}{RESET}")
    print(f"{BOLD}Agent Response:{RESET}\n")
    print(textwrap.indent(text.strip(), "  "))
    print(f"\n{BOLD}{'─' * 72}{RESET}")


# ── Mock CloudWatch data (matches synthetic seed script) ────────────────────
MOCK_FINDINGS = {
    "errors_by_service": [
        ("payment-service", 47),
        ("auth-service", 31),
        ("order-service", 18),
        ("api-gateway", 12),
    ],
    "incidents": [
        {
            "time": "2026-07-03T08:12:04Z",
            "service": "payment-service",
            "level": "ERROR",
            "status": 504,
            "msg": "Payment gateway timeout — upstream did not respond within 30s",
        },
        {
            "time": "2026-07-03T08:12:06Z",
            "service": "order-service",
            "level": "ERROR",
            "status": 500,
            "msg": "Order creation failed — payment not confirmed",
        },
        {
            "time": "2026-07-03T08:35:22Z",
            "service": "auth-service",
            "level": "WARN",
            "status": 401,
            "msg": "Authentication failed — 47 attempts from 203.0.113.88",
        },
    ],
}


def build_analysis_report() -> str:
    return """
### Executive Summary
System health is **DEGRADED**. Three distinct incident patterns detected in the
last 2 hours across payment, auth, and order services. Payment gateway timeouts
are the highest-severity issue affecting checkout completion.

### Findings

| Severity  | Service          | Issue                              | Evidence                          |
|-----------|------------------|------------------------------------|-----------------------------------|
| CRITICAL  | payment-service  | Gateway timeout (HTTP 504)         | 47 errors, latency 5–15s          |
| HIGH      | auth-service     | Auth failure burst (possible brute force) | 31 failures from single IP |
| HIGH      | order-service    | Cascade failure after payment timeout | 18 errors, shared traceId    |
| MEDIUM    | api-gateway      | Downstream 502 from payment-service | 12 errors, latency >8s           |

### Root Cause Analysis
1. **Payment gateway timeout (08:12 UTC)** — payment-service returned HTTP 504 after
   5–15s latency. Upstream payment provider did not respond within the 30s timeout.
2. **Cascade to order-service** — orders sharing traceId `a3f8c2e1-...` failed because
   payment confirmation never arrived (HTTP 500 on /orders/create).
3. **Auth brute-force pattern (08:35 UTC)** — 47 consecutive 401/403 responses from
   IP 203.0.113.88 against /auth/login within 5 minutes.

### Recommended Actions
1. Increase payment-service timeout or add circuit breaker for gateway calls
2. Block/limit IP 203.0.113.88 at WAF; enable rate limiting on /auth/login
3. Add retry with exponential backoff for order-service → payment-service calls
4. Create CloudWatch alarm: `ErrorCount > 10 per 5min` on payment-service

### Suggested CloudWatch Alarms
- `Hackathon/LogAnalysis` ErrorCount > 20 (5-min) → SNS alert
- Logs Insights: `filter statusCode = 504 | stats count() by bin(5m)` → anomaly detection
""".strip()


def run_demo():
    header("Log Analysis Agent — Live Demo Preview")
    print(f"  {DIM}Model: Claude Sonnet 4 on Amazon Bedrock AgentCore Runtime{RESET}")
    print(f"  {DIM}Log group: /hackathon/log-analysis/ecommerce-platform{RESET}")
    print(f"  {DIM}Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}{RESET}")
    pause(0.8)

    # User prompt
    prompt = "Analyze all errors in the last 2 hours and identify root causes"
    print(f"\n{BOLD}User:{RESET} {prompt}\n")
    pause(0.6)

    step("Agent reasoning", "Planning CloudWatch investigation strategy...")
    step("Selecting tools", "detect_error_patterns → build_incident_timeline → query_logs_insights")

    tool_call(
        "detect_error_patterns",
        {"log_group": "/hackathon/log-analysis/ecommerce-platform", "hours_back": 2},
        f"CRITICAL: 47 payment errors, auth spike detected, 3 correlated traces",
    )

    tool_call(
        "build_incident_timeline",
        {"log_group": "/hackathon/log-analysis/ecommerce-platform", "hours_back": 2},
        f"3 correlated events with shared traceId (payment → order cascade)",
    )

    tool_call(
        "query_logs_insights",
        {
            "query": "filter statusCode >= 500 | stats count() by service",
            "hours_back": 2,
        },
        "payment-service: 47, auth-service: 31, order-service: 18, api-gateway: 12",
    )

    step("Generating report", "Synthesizing findings with evidence citations...")
    pause(0.5)

    agent_response(build_analysis_report())

    # Memory follow-up demo
    header("Memory Demo — Follow-up (same session)")
    print(f"{BOLD}User:{RESET} What was the root cause of the payment issues you found earlier?\n")
    pause(0.5)

    followup = """
Based on our earlier analysis (session memory), the payment-service root cause was
**upstream gateway timeout** — HTTP 504 responses with 5–15 second latency starting
at 08:12 UTC. The payment provider did not respond within the configured 30s timeout
window during peak traffic.

This cascaded to order-service (18 failures) because orders could not confirm payment.
I recommend checking the payment provider status page and enabling a circuit breaker.
""".strip()

    agent_response(followup)

    # Footer
    header("Demo Complete")
    print("  This preview uses synthetic data matching scripts/generate_synthetic_logs.py")
    print("  Deploy for live CloudWatch queries:  npx agentcore deploy -y")
    print("  Invoke live agent:                   npx agentcore invoke \"Analyze errors...\"")
    print(f"\n  {DIM}Full judge script: docs/DEMO_GUIDE.md{RESET}\n")


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\nDemo interrupted.")
        sys.exit(0)
