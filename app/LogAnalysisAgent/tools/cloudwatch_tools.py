"""Specialized CloudWatch tools for log analysis."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from strands import tool

from config import AWS_REGION, DEFAULT_LOG_GROUP, INSIGHTS_QUERY_TIMEOUT
from corner_cases import clamp_hours_back, safe_error_response


def _logs_client():
    return boto3.client("logs", region_name=AWS_REGION)


def _cloudwatch_client():
    return boto3.client("cloudwatch", region_name=AWS_REGION)


def _epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _parse_time_range(hours_back: int = 1) -> tuple[int, int]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours_back)
    return _epoch_ms(start), _epoch_ms(end)


def _run_insights_query(
    log_group: str,
    query: str,
    hours_back: int = 1,
) -> dict[str, Any]:
    """Execute a CloudWatch Logs Insights query and wait for results."""
    if not log_group or not log_group.strip():
        return {"status": "Error", "error": "log_group is required", "hint": "Use list_log_groups to discover groups"}

    if not query or not query.strip():
        return {"status": "Error", "error": "query is required", "hint": "See docs/sample_queries.md for examples"}

    hours_back = clamp_hours_back(hours_back)
    client = _logs_client()
    start_ms, end_ms = _parse_time_range(hours_back)

    try:
        response = client.start_query(
            logGroupName=log_group,
            startTime=start_ms,
            endTime=end_ms,
            queryString=query,
        )
        query_id = response["queryId"]

        deadline = time.time() + INSIGHTS_QUERY_TIMEOUT
        while time.time() < deadline:
            result = client.get_query_results(queryId=query_id)
            status = result["status"]
            if status == "Complete":
                results = result.get("results", [])
                return {
                    "status": "Complete",
                    "statistics": result.get("statistics", {}),
                    "results": results,
                    "result_count": len(results),
                    "query_id": query_id,
                    "empty": len(results) == 0,
                    "hint": "No matching logs — widen hours_back or check if data was seeded" if not results else None,
                }
            if status in ("Failed", "Cancelled", "Timeout"):
                return {"status": status, "error": f"Query {status.lower()}", "query_id": query_id}
            time.sleep(0.5)

        return {"status": "Timeout", "error": "Query timed out", "query_id": query_id, "hint": "Simplify query or reduce hours_back"}
    except ClientError as exc:
        return safe_error_response("query_logs_insights", exc)


@tool
def list_log_groups(prefix: str = "/hackathon/") -> str:
    """List CloudWatch log groups, optionally filtered by prefix.

    Args:
        prefix: Log group name prefix filter (default: /hackathon/)

    Returns:
        JSON list of log groups with names, stored bytes, and retention.
    """
    client = _logs_client()
    try:
        paginator = client.get_paginator("describe_log_groups")
        groups = []
        for page in paginator.paginate(logGroupNamePrefix=prefix):
            for group in page.get("logGroups", []):
                groups.append(
                    {
                        "name": group["logGroupName"],
                        "stored_bytes": group.get("storedBytes", 0),
                        "retention_days": group.get("retentionInDays", "Never expire"),
                        "creation_time": group.get("creationTime"),
                    }
                )
        return json.dumps({"log_groups": groups, "count": len(groups)}, indent=2)
    except ClientError as exc:
        return json.dumps(safe_error_response("list_log_groups", exc))


@tool
def query_logs_insights(
    query: str,
    log_group: str = DEFAULT_LOG_GROUP,
    hours_back: int = 1,
) -> str:
    """Run a CloudWatch Logs Insights query against a log group.

    Use CloudWatch Logs Insights query syntax. Common patterns:
    - fields @timestamp, @message | sort @timestamp desc | limit 50
    - filter @message like /ERROR/ | stats count() by bin(5m)
    - filter statusCode >= 500 | stats count() by service

    Args:
        query: CloudWatch Logs Insights query string.
        log_group: Target log group name.
        hours_back: How many hours of logs to search (default: 1).

    Returns:
        JSON with query results, statistics, and status.
    """
    result = _run_insights_query(log_group, query, hours_back)
    return json.dumps(result, indent=2, default=str)


@tool
def filter_log_events(
    filter_pattern: str = "",
    log_group: str = DEFAULT_LOG_GROUP,
    hours_back: int = 1,
    limit: int = 50,
) -> str:
    """Filter recent log events using CloudWatch filter patterns.

    Filter pattern examples:
    - "ERROR" — match ERROR in message
    - "{ $.statusCode = 500 }" — JSON filter for statusCode 500
    - "?ERROR ?WARN" — match ERROR or WARN

    Args:
        filter_pattern: CloudWatch Logs filter pattern (empty = all events).
        log_group: Target log group name.
        hours_back: How many hours back to search.
        limit: Maximum events to return (max 100).

    Returns:
        JSON list of matching log events with timestamps and messages.
    """
    client = _logs_client()
    hours_back = clamp_hours_back(hours_back)
    start_ms, end_ms = _parse_time_range(hours_back)
    limit = min(max(limit, 1), 100)

    try:
        kwargs: dict[str, Any] = {
            "logGroupName": log_group,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern

        response = client.filter_log_events(**kwargs)
        events = [
            {
                "timestamp": datetime.fromtimestamp(
                    e["timestamp"] / 1000, tz=timezone.utc
                ).isoformat(),
                "message": e["message"],
                "log_stream": e.get("logStreamName"),
            }
            for e in response.get("events", [])
        ]
        return json.dumps(
            {
                "events": events,
                "count": len(events),
                "log_group": log_group,
                "empty": len(events) == 0,
                "hint": "No events matched — verify log group has data or adjust filter_pattern" if not events else None,
            },
            indent=2,
        )
    except ClientError as exc:
        return json.dumps(safe_error_response("filter_log_events", exc))


@tool
def get_metric_statistics(
    namespace: str = "Hackathon/LogAnalysis",
    metric_name: str = "ErrorCount",
    dimensions: str = "",
    hours_back: int = 1,
    period_seconds: int = 300,
    statistic: str = "Sum",
) -> str:
    """Retrieve CloudWatch metric statistics for monitoring dashboards.

    Args:
        namespace: CloudWatch metric namespace.
        metric_name: Metric name (e.g., ErrorCount, Latency, RequestCount).
        dimensions: JSON string of dimensions, e.g. '{"Service":"payment-service"}'.
        hours_back: Hours of data to retrieve.
        period_seconds: Aggregation period in seconds (default: 300 = 5 min).
        statistic: Statistic type: Sum, Average, Maximum, Minimum, SampleCount.

    Returns:
        JSON with datapoints and summary statistics.
    """
    client = _cloudwatch_client()
    hours_back = clamp_hours_back(hours_back)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours_back)

    dim_list = []
    if dimensions:
        try:
            dim_dict = json.loads(dimensions)
            dim_list = [{"Name": k, "Value": v} for k, v in dim_dict.items()]
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid dimensions JSON"})

    try:
        response = client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dim_list,
            StartTime=start,
            EndTime=end,
            Period=period_seconds,
            Statistics=[statistic],
        )
        datapoints = sorted(response.get("Datapoints", []), key=lambda d: d["Timestamp"])
        return json.dumps(
            {
                "namespace": namespace,
                "metric_name": metric_name,
                "statistic": statistic,
                "datapoints": [
                    {
                        "timestamp": dp["Timestamp"].isoformat(),
                        "value": dp.get(statistic, 0),
                    }
                    for dp in datapoints
                ],
                "count": len(datapoints),
            },
            indent=2,
            default=str,
        )
    except ClientError as exc:
        return json.dumps(safe_error_response("get_metric_statistics", exc))


@tool
def detect_error_patterns(
    log_group: str = DEFAULT_LOG_GROUP,
    hours_back: int = 1,
) -> str:
    """Automatically detect error patterns, anomalies, and spikes in logs.

    Runs multiple CloudWatch Logs Insights queries to find:
    - Error count by service and severity
    - HTTP 5xx status code spikes
    - Authentication failure bursts
    - Top error messages

    Args:
        log_group: Target log group name.
        hours_back: Hours of logs to analyze.

    Returns:
        JSON report with detected patterns, counts, and severity ratings.
    """
    queries = {
        "errors_by_service": (
            "fields service, level "
            "| filter level = 'ERROR' or level = 'CRITICAL' "
            "| stats count() as error_count by service "
            "| sort error_count desc"
        ),
        "http_5xx_by_service": (
            "fields service, statusCode "
            "| filter statusCode >= 500 "
            "| stats count() as server_errors by service, statusCode "
            "| sort server_errors desc"
        ),
        "auth_failures": (
            "fields service, statusCode, @message "
            "| filter service = 'auth-service' and (statusCode = 401 or statusCode = 403) "
            "| stats count() as failures by bin(5m) "
            "| sort failures desc"
        ),
        "top_error_messages": (
            "fields @message, service "
            "| filter level = 'ERROR' "
            "| stats count() as occurrences by @message "
            "| sort occurrences desc "
            "| limit 10"
        ),
        "latency_outliers": (
            "fields service, latencyMs "
            "| filter latencyMs > 1000 "
            "| stats count() as slow_requests, avg(latencyMs) as avg_latency by service "
            "| sort slow_requests desc"
        ),
    }

    hours_back = clamp_hours_back(hours_back)
    report: dict[str, Any] = {"log_group": log_group, "hours_back": hours_back, "patterns": {}}

    for name, query in queries.items():
        result = _run_insights_query(log_group, query, hours_back)
        report["patterns"][name] = {
            "status": result.get("status"),
            "results": result.get("results", []),
            "statistics": result.get("statistics", {}),
        }

    def _sum_field(results: list, field_name: str) -> int:
        total = 0
        for row in results:
            for cell in row:
                if cell.get("field") == field_name:
                    total += int(cell.get("value", 0))
        return total

    # Assign severity based on findings
    severities = []
    errors = report["patterns"].get("errors_by_service", {}).get("results", [])
    if errors:
        total_errors = _sum_field(errors, "error_count")
        if total_errors > 50:
            severities.append({"level": "CRITICAL", "reason": f"{total_errors} errors detected across services"})
        elif total_errors > 10:
            severities.append({"level": "HIGH", "reason": f"{total_errors} errors detected"})

    http5xx = report["patterns"].get("http_5xx_by_service", {}).get("results", [])
    if http5xx:
        severities.append({"level": "HIGH", "reason": "HTTP 5xx errors detected in services"})

    auth = report["patterns"].get("auth_failures", {}).get("results", [])
    if len(auth) > 3:
        severities.append({"level": "CRITICAL", "reason": "Authentication failure spike detected (possible brute force)"})

    report["severity_assessment"] = severities if severities else [{"level": "LOW", "reason": "No major anomalies detected"}]

    return json.dumps(report, indent=2, default=str)


@tool
def build_incident_timeline(
    log_group: str = DEFAULT_LOG_GROUP,
    hours_back: int = 1,
    severity_filter: str = "ERROR",
) -> str:
    """Build a chronological incident timeline from correlated log events.

    Correlates errors and warnings across microservices to show how incidents
    propagate through the system (e.g., payment timeout → order failure → retry storm).

    Args:
        log_group: Target log group name.
        hours_back: Hours of logs to include.
        severity_filter: Log level to include (ERROR, WARN, or CRITICAL).

    Returns:
        JSON timeline of correlated events sorted chronologically.
    """
    query = (
        f"fields @timestamp, service, level, statusCode, latencyMs, @message, traceId "
        f"| filter level = '{severity_filter}' or level = 'CRITICAL' or statusCode >= 500 "
        f"| sort @timestamp asc "
        f"| limit 100"
    )
    hours_back = clamp_hours_back(hours_back)
    result = _run_insights_query(log_group, query, hours_back)

    timeline = []
    for row in result.get("results", []):
        entry = {field["field"]: field["value"] for field in row}
        timeline.append(entry)

    # Group by traceId for correlation
    traces: dict[str, list] = {}
    for entry in timeline:
        trace_id = entry.get("traceId", "unknown")
        traces.setdefault(trace_id, []).append(entry)

    return json.dumps(
        {
            "status": result.get("status"),
            "event_count": len(timeline),
            "timeline": timeline,
            "correlated_traces": {
                tid: events for tid, events in traces.items() if len(events) > 1
            },
        },
        indent=2,
        default=str,
    )


CLOUDWATCH_TOOLS = [
    list_log_groups,
    query_logs_insights,
    filter_log_events,
    get_metric_statistics,
    detect_error_patterns,
    build_incident_timeline,
]
