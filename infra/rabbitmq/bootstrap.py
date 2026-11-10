"""Import broker topology after the RabbitMQ default account is created.

Adds TTL retry queues and DLQs for the four main queues in definitions.json.
No passwords or hashes are stored in definitions.json.
"""
import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
username = os.environ["RABBITMQ_DEFAULT_USER"]
password = os.environ["RABBITMQ_DEFAULT_PASS"]
topology = json.loads(Path("/setup/definitions.json").read_text())
source_queues = [entry["name"] for entry in topology["queues"]]

for source in source_queues:
    topology["queues"].append({
        "name": source + ".dlq", "vhost": "/", "durable": True,
        "auto_delete": False, "arguments": {}
    })
    for seconds in (10, 60, 300):
        topology["queues"].append({
            "name": f"{source}.retry.{seconds}s", "vhost": "/",
            "durable": True, "auto_delete": False,
            "arguments": {
                "x-message-ttl": seconds * 1000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": source
            }
        })

api_url = f"http://{host}:15672/api/definitions"
auth = base64.b64encode(f"{username}:{password}".encode()).decode()
request = Request(
    api_url,
    data=json.dumps(topology).encode(),
    headers={"Content-Type": "application/json", "Authorization": "Basic " + auth},
    method="POST",
)
for attempt in range(30):
    try:
        with urlopen(request, timeout=8) as response:
            if response.status not in range(200, 300):
                raise RuntimeError(f"Topology import status: {response.status}")
        print(f"RabbitMQ topology imported: {len(topology['queues'])} queues, "
              f"{len(topology['bindings'])} bindings", flush=True)
        break
    except (HTTPError, URLError, TimeoutError) as exc:
        if isinstance(exc, HTTPError) and 400 <= exc.code < 500 and exc.code != 429:
            raise RuntimeError(f"RabbitMQ definitions rejected: HTTP {exc.code}") from exc
        if attempt == 29:
            raise
        time.sleep(2)
