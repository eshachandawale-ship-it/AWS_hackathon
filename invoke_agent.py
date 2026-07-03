"""Invoke the deployed Log Analysis Agent via boto3."""

import json
import sys
import uuid

import boto3


def invoke(agent_arn: str, prompt: str, region: str = "us-west-2") -> dict:
    client = boto3.client("bedrock-agentcore", region_name=region)
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=payload,
        qualifier="DEFAULT",
    )

    content = []
    for chunk in response.get("response", []):
        content.append(chunk.decode("utf-8"))

    raw = "".join(content)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"response": raw}


def main():
    if len(sys.argv) < 3:
        print("Usage: python invoke_agent.py <AGENT_ARN> <PROMPT>")
        print('Example: python invoke_agent.py arn:aws:... "Analyze payment errors in the last hour"')
        sys.exit(1)

    agent_arn = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    result = invoke(agent_arn, prompt)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
