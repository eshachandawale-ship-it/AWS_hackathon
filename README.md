# Log Analysis Agent — AWS Hackathon Prototype

Production-grade **Amazon Bedrock AgentCore** agent demonstrating **Runtime**, **Memory**, **Observability**, **On-Demand Evaluation**, **Online Evaluation**, and **corner-case handling**.

| Capability | Implementation |
|------------|----------------|
| **Runtime** | `LogAnalysisAgent` on AgentCore Runtime (Strands + Claude Sonnet 4) |
| **Memory** | `LogAnalysisMemory` — STM + LTM (Semantic, Summarization, User Preference, Episodic) |
| **Observability** | Auto OpenTelemetry → CloudWatch GenAI Observability |
| **On-Demand Eval** | 3 custom evaluators + `Builtin.Faithfulness` |
| **Online Eval** | `LogAnalysisQualityMonitor` at 25% sampling |
| **CloudWatch Tools** | 6 specialized tools for log analysis |
| **Corner Cases** | Input validation, empty results, IAM errors, graceful fallbacks |

> **Full demo walkthrough:** [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md)

## Run a quick results preview (no deploy needed)

Shows realistic agent output — tool calls, findings table, root cause, memory follow-up:

```bash
python3 scripts/demo_showcase.py
```

See also: [docs/sample_demo_output.md](docs/sample_demo_output.md)

## Fix CloudFormation Deploy Failures

**Symptom:** `NoStack: CloudFormationStack object does not hold a stack` or missing `agentcore/.cli/deployed-state.json`

**Cause:** Full `agentcore.json` deploys runtime + 4 memory strategies + 3 evaluators + online eval in one stack. Any single `CREATE_FAILED` rolls back everything.

**Fix (workshop):**

```bash
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION=us-west-2

# One-command fix: clean stack + minimal deploy
bash scripts/fix_deploy.sh

# After phase1 works, add features incrementally:
bash scripts/fix_deploy.sh phase2   # + LTM memory + evaluators
bash scripts/fix_deploy.sh full     # + online eval

# Diagnose if still failing:
bash scripts/diagnose_deploy.sh
```

**Prerequisites:**
- Claude Sonnet 4 enabled in Bedrock (us-west-2)
- Node 20+ (`node --version`)
- `npm install` in project root (for local `@aws/agentcore`)

## Quick Start (AWS VS Code Environment)

```bash
# 1. Configure
# Edit agentcore/aws-targets.json with your account ID
# Enable Claude Sonnet 4 in Bedrock console
# Enable CloudWatch Transaction Search (one-time)

# 2. Install
npm install -g @aws/agentcore
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Seed logs + deploy
pip install -r requirements.txt
python3 scripts/seed_cloudwatch_logs.py --generate

# Generate CDK infra (if agentcore/cdk is missing)
bash scripts/setup_cdk.sh

agentcore deploy -y

# 4. Demo everything
chmod +x scripts/demo_full_stack.sh && ./scripts/demo_full_stack.sh
```

## Capability Demos

### Runtime
```bash
agentcore invoke --stream "Analyze payment-service errors in the last 2 hours"
```

### Memory (multi-turn)
```bash
agentcore invoke --session-id demo "Analyze all errors in the last hour"
agentcore invoke --session-id demo "What root cause did you find earlier?"
```

### Observability
```bash
agentcore logs --follow
agentcore traces list
# Console: CloudWatch → GenAI Observability → AgentCore
```

### On-Demand Evaluation
```bash
# Wait 5-10 min after invocations for traces
agentcore run eval --runtime LogAnalysisAgent --evaluator LogAnalysisSessionQuality --days 1
agentcore evals history
```

### Online Evaluation
```bash
agentcore logs evals --runtime LogAnalysisAgent --since 1h
```

### Corner Cases
```bash
agentcore invoke ""                                          # empty prompt
agentcore invoke "Analyze /nonexistent/log-group for errors" # missing log group
```
See [docs/corner_case_prompts.md](docs/corner_case_prompts.md)

## Project Structure

```
├── agentcore/agentcore.json     # Runtime + Memory + Evaluators + Online Eval
├── app/LogAnalysisAgent/
│   ├── main.py                  # Entrypoint
│   ├── agent_factory.py         # Per-session agent + memory cache
│   ├── memory/session.py        # AgentCore Memory integration
│   ├── corner_cases.py          # Input validation
│   └── tools/cloudwatch_tools.py
├── scripts/demo_full_stack.sh   # One-command full demo
└── docs/DEMO_GUIDE.md           # Judge demo script (5 min)
```

## Evaluators

| Name | Level | Purpose |
|------|-------|---------|
| LogAnalysisSessionQuality | SESSION | Overall investigation quality |
| LogAnalysisTraceAccuracy | TRACE | Per-turn response accuracy |
| CloudWatchToolUsage | TOOL_CALL | Correct tool selection |
| Builtin.Faithfulness | — | Grounded responses (online eval) |

## Synthetic Data

No proprietary logs. Generate and seed:
```bash
python3 scripts/generate_synthetic_logs.py
python3 scripts/seed_cloudwatch_logs.py --generate
```

Log group: `/hackathon/log-analysis/ecommerce-platform`

## Cleanup

```bash
agentcore remove all && agentcore deploy -y
```
