# Sample Agent Output — Log Analysis Agent Demo

This is what a successful invocation looks like for hackathon judges.

---

## User Prompt

```
Analyze all errors in the last 2 hours and identify root causes
```

---

## Agent Tool Calls (observable in CloudWatch GenAI Observability)

### 1. `detect_error_patterns`
```json
{
  "log_group": "/hackathon/log-analysis/ecommerce-platform",
  "hours_back": 2,
  "severity_assessment": [
    {"level": "CRITICAL", "reason": "47 errors detected across services"},
    {"level": "CRITICAL", "reason": "Authentication failure spike detected"}
  ]
}
```

### 2. `build_incident_timeline`
```json
{
  "event_count": 3,
  "correlated_traces": {
    "a3f8c2e1-7b2d-4c9a-8e1f-2d6c5b4a3910": [
      {"@timestamp": "2026-07-03T08:12:04Z", "service": "payment-service", "statusCode": 504},
      {"@timestamp": "2026-07-03T08:12:06Z", "service": "order-service", "statusCode": 500}
    ]
  }
}
```

### 3. `query_logs_insights`
```
payment-service  → 47 server errors
auth-service     → 31 auth failures
order-service    → 18 errors
api-gateway      → 12 downstream errors
```

---

## Agent Response

### Executive Summary
System health is **DEGRADED**. Three distinct incident patterns detected in the
last 2 hours across payment, auth, and order services.

### Findings

| Severity | Service | Issue | Evidence |
|----------|---------|-------|----------|
| CRITICAL | payment-service | Gateway timeout (504) | 47 errors, 5–15s latency |
| HIGH | auth-service | Auth failure burst | 31 failures from 203.0.113.88 |
| HIGH | order-service | Cascade after payment fail | 18 errors, shared traceId |
| MEDIUM | api-gateway | Downstream 502 | 12 errors |

### Root Cause Analysis
Payment gateway timeout at 08:12 UTC caused cascade failures. Auth brute-force
pattern detected at 08:35 UTC from single IP.

### Recommended Actions
1. Add circuit breaker on payment-service gateway calls
2. WAF rate-limit on /auth/login
3. CloudWatch alarm: ErrorCount > 10 per 5min on payment-service

---

## Memory Follow-up (same session)

**User:** What was the root cause of the payment issues you found earlier?

**Agent:** Based on our earlier analysis, the payment-service root cause was upstream
gateway timeout (HTTP 504, 5–15s latency at 08:12 UTC). This cascaded to
order-service because payment confirmation never arrived.

---

## Run the live terminal demo

```bash
python3 scripts/demo_showcase.py
```
