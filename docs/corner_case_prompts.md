# Corner-case test prompts for hackathon demo
# Run each with: agentcore invoke --session-id corner-cases "<prompt>"

# ── Input validation ──
# agentcore invoke ""
# agentcore invoke "   "

# ── Missing / invalid log data ──
Analyze errors in /this-log-group-does-not-exist from the last hour
Find all CRITICAL errors in /hackathon/log-analysis/ecommerce-platform from the last 24 hours
List all log groups under /hackathon/

# ── Ambiguous requests (agent should clarify) ──
Find problems
Something is wrong

# ── Tool selection stress tests ──
Run an automated error pattern scan on the default log group
Build an incident timeline for all ERROR level events in the last 3 hours
What is the error rate per service in 5-minute bins?

# ── Memory multi-turn sequence (use same --session-id) ──
# Turn 1: Analyze payment-service errors in the last 2 hours
# Turn 2: What was the root cause you identified earlier?
# Turn 3: Remember I only care about CRITICAL severity
# Turn 4: Re-check auth-service with my severity filter

# ── Metrics corner case ──
Get ErrorCount metrics for payment-service from Hackathon/LogAnalysis namespace
