# Hackathon Demo Guide — All AgentCore Capabilities

Complete walkthrough for demonstrating **Runtime**, **Memory**, **Observability**, **On-Demand Evaluation**, **Online Evaluation**, and **corner cases** in the AWS-provided VS Code environment.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Amazon Bedrock AgentCore                          │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   RUNTIME    │  │    MEMORY    │  │      EVALUATIONS         │  │
│  │ LogAnalysis  │  │ LogAnalysis  │  │ On-demand + Online (25%) │  │
│  │ Agent        │◄─┤ Memory       │  │ 3 custom + Builtin       │  │
│  │ (Sonnet 4)   │  │ STM + LTM    │  │                          │  │
│  └──────┬───────┘  └──────────────┘  └──────────────────────────┘  │
│         │                                                            │
│         │ auto-instrumented (OpenTelemetry)                          │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              OBSERVABILITY → CloudWatch                       │   │
│  │  Traces │ Sessions │ Metrics │ GenAI Dashboard │ Logs Insights│   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CloudWatch Tools (6) → Logs, Insights, Metrics, Pattern Detection  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pre-Flight Checklist (AWS Environment)

```bash
# Verify credentials
aws sts get-caller-identity

# Enable Claude Sonnet 4 in Bedrock console (Model access)

# One-time: Enable CloudWatch Transaction Search
# Console → CloudWatch → Application Signals → Transaction search → Enable

# Install tools
npm install -g @aws/agentcore
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv not installed
```

Edit `agentcore/aws-targets.json` with your account ID (root must be a JSON **array**):

```json
[
  {
    "name": "default",
    "description": "AWS Hackathon workshop",
    "account": "123456789012",
    "region": "us-west-2"
  }
]
```

Get your account ID:

```bash
aws sts get-caller-identity --query Account --output text
```

---

## 1. Runtime Demo

Deploy and invoke the agent on AgentCore Runtime.

```bash
# Seed synthetic logs (no proprietary data)
pip install -r requirements.txt
python3 scripts/seed_cloudwatch_logs.py --generate

# Generate CDK infra if missing
bash scripts/setup_cdk.sh

# Deploy all resources
npx agentcore deploy -y

# Check status
agentcore status

# Basic invocation
agentcore invoke "Analyze all errors in the last 2 hours and rank by severity"

# Streaming response
agentcore invoke --stream "Detect authentication anomalies in auth-service"

# Local dev (hot reload)
agentcore dev
```

**What to show judges:** Agent runs serverless on AgentCore Runtime, uses Claude Sonnet 4, calls CloudWatch tools autonomously.

---

## 2. Memory Demo

Memory persists investigation context across turns (short-term + long-term strategies).

```bash
SESSION="hackathon-memory-demo"

# Turn 1: Initial analysis
agentcore invoke --session-id $SESSION \
  "Analyze payment-service errors in the last 2 hours"

# Turn 2: Follow-up (agent recalls Turn 1 via AgentCore Memory)
agentcore invoke --session-id $SESSION \
  "What was the root cause of the payment issues you found earlier?"

# Turn 3: Store preference (LTM — USER_PREFERENCE strategy)
agentcore invoke --session-id $SESSION \
  "Remember: I only want CRITICAL and HIGH severity findings"

# Turn 4: Preference applied
agentcore invoke --session-id $SESSION \
  "Re-analyze auth-service — apply my severity filter"
```

**Memory strategies enabled:**
| Strategy | Purpose |
|----------|---------|
| SEMANTIC | Recall relevant facts from past investigations |
| SUMMARIZATION | Compressed session summaries |
| USER_PREFERENCE | Analyst severity/filter preferences |
| EPISODIC | Meaningful investigation episodes |

**Env var:** `MEMORY_LOGANALYSISMEMORY_ID` (auto-injected by AgentCore on deploy)

---

## 3. Observability Demo

AgentCore Runtime auto-instruments with OpenTelemetry — no code changes needed.

```bash
# Stream runtime logs
agentcore logs --follow

# List recent traces
agentcore traces list

# Download a specific trace
agentcore traces get <trace-id>

# Check deployment health
agentcore status
```

**CloudWatch Console paths:**
| View | Location |
|------|----------|
| GenAI Observability | CloudWatch → GenAI Observability → AgentCore tab |
| Agent logs | CloudWatch → Log groups → `/aws/bedrock-agentcore/runtimes/...` |
| Logs Insights | CloudWatch → Logs → Logs Insights |

**Sample Logs Insights query** (token usage):
```
fields @timestamp, @message
| filter @message like /token/
| stats sum(inputTokens) as total_input, sum(outputTokens) as total_output
```

---

## 4. On-Demand Evaluation Demo

Run evaluators against historical traces after invocations.

> **Wait 5–10 minutes** after invocations for traces to propagate to CloudWatch.

```bash
# Session-level quality (overall investigation)
agentcore run eval \
  --runtime LogAnalysisAgent \
  --evaluator LogAnalysisSessionQuality \
  --days 1

# Per-turn accuracy
agentcore run eval \
  --runtime LogAnalysisAgent \
  --evaluator LogAnalysisTraceAccuracy \
  --days 1

# Tool selection correctness
agentcore run eval \
  --runtime LogAnalysisAgent \
  --evaluator CloudWatchToolUsage \
  --days 1

# Built-in faithfulness check
agentcore run eval \
  --runtime LogAnalysisAgent \
  --evaluator Builtin.Faithfulness \
  --days 1

# Multiple evaluators at once
agentcore run eval \
  --runtime LogAnalysisAgent \
  --evaluator LogAnalysisSessionQuality LogAnalysisTraceAccuracy Builtin.Faithfulness \
  --days 1

# View results
agentcore evals history --runtime LogAnalysisAgent
```

**Evaluators configured:**

| Evaluator | Level | What it measures |
|-----------|-------|------------------|
| LogAnalysisSessionQuality | SESSION | Overall investigation quality |
| LogAnalysisTraceAccuracy | TRACE | Per-response accuracy |
| CloudWatchToolUsage | TOOL_CALL | Correct tool selection |
| Builtin.Faithfulness | — | Response grounded in context |

---

## 5. Online Evaluation Demo

Continuous evaluation samples 25% of live traffic automatically.

```bash
# Already configured in agentcore.json — deployed with agentcore deploy
# Config: LogAnalysisQualityMonitor (25% sampling)

# View online eval logs
agentcore logs evals --runtime LogAnalysisAgent --since 1h

# Follow online eval logs in real-time
agentcore logs evals --runtime LogAnalysisAgent --follow

# Pause/resume monitoring
agentcore pause online-eval LogAnalysisQualityMonitor
agentcore resume online-eval LogAnalysisQualityMonitor
```

**Demo flow:**
1. Deploy agent (`agentcore deploy`)
2. Make 4+ invocations (to get sampled evals at 25%)
3. Wait 5–10 minutes
4. Check `agentcore logs evals` and CloudWatch GenAI Observability

---

## 6. Corner Cases Demo

Demonstrate robust error handling.

```bash
# Empty prompt → structured error
agentcore invoke ""

# Non-existent log group → helpful hint
agentcore invoke "Analyze /does-not-exist/log-group for errors"

# Ambiguous request → agent asks for clarification
agentcore invoke "Find problems"

# Multi-turn with memory fallback (works even if memory ID missing locally)
agentcore dev "Analyze errors"   # stateless in local dev without MEMORY_* env
```

**Handled in code:**

| Corner Case | Behavior |
|-------------|----------|
| Empty/missing prompt | Returns structured error with example |
| Prompt > 32K chars | Rejects with guidance to split |
| Invalid `hours_back` | Clamped to 1–168 hours |
| Log group not found | `ResourceNotFoundException` + seed script hint |
| Access denied | IAM policy attachment instructions |
| Empty query results | `empty: true` + widen window hint |
| Query timeout | Suggests simpler query |
| API throttling | Retry guidance |
| Memory not configured | Graceful fallback to stateless mode |

---

## 7. One-Command Full Demo

```bash
chmod +x scripts/demo_full_stack.sh
./scripts/demo_full_stack.sh
```

---

## Demo Script for Judges (5 minutes)

| Time | Action | Capability |
|------|--------|------------|
| 0:00 | `agentcore status` | Show deployed resources |
| 0:30 | Invoke with analysis prompt | **Runtime** + CloudWatch tools |
| 1:30 | Follow-up in same session | **Memory** |
| 2:30 | `agentcore logs` / traces | **Observability** |
| 3:30 | `agentcore run eval` | **On-demand Evaluation** |
| 4:00 | `agentcore logs evals` | **Online Evaluation** |
| 4:30 | Empty prompt / bad log group | **Corner cases** |

---

## Troubleshooting (AWS Environment)

| Issue | Fix |
|-------|-----|
| Model access denied | Enable Claude Sonnet 4 in Bedrock console |
| No traces in eval | Wait 5–10 min; increase `--days` |
| CloudWatch access denied | Attach `HackathonLogAnalysisAgentPolicy` from CDK output |
| Memory not working locally | Expected — memory requires deployed `MEMORY_LOGANALYSISMEMORY_ID` |
| CDK project not found | Run `bash scripts/setup_cdk.sh` then redeploy |
| uv not found | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

---

## Cleanup

```bash
agentcore remove all && agentcore deploy -y
cd infrastructure && cdk destroy
```
