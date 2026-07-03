# Sample CloudWatch Logs Insights Queries

Use these with the agent or directly in the CloudWatch console.

## Error rate by service (5-minute bins)

```
fields @timestamp, service, level
| filter level = 'ERROR' or level = 'CRITICAL'
| stats count() as errors by service, bin(5m)
| sort errors desc
```

## HTTP 5xx errors

```
fields service, statusCode, @message
| filter statusCode >= 500
| stats count() as server_errors by service, statusCode
| sort server_errors desc
```

## Authentication failure spike

```
fields @timestamp, sourceIp, statusCode
| filter service = 'auth-service' and (statusCode = 401 or statusCode = 403)
| stats count() as failures by bin(1m), sourceIp
| sort failures desc
```

## Slow requests (>1s latency)

```
fields service, latencyMs, endpoint
| filter latencyMs > 1000
| stats count() as slow_count, avg(latencyMs) as avg_latency, max(latencyMs) as max_latency by service
| sort slow_count desc
```

## Correlated failures by traceId

```
fields @timestamp, service, level, statusCode, traceId, @message
| filter level = 'ERROR' or statusCode >= 500
| sort @timestamp asc
| limit 50
```

## Payment gateway timeouts

```
fields @timestamp, orderId, latencyMs, @message
| filter service = 'payment-service' and statusCode = 504
| sort @timestamp desc
| limit 20
```
