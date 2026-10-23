"""Run a synthetic arrival through actual HTTP and the official MCP client.

Both local servers must use the same data directory. No credentials are printed.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def local_origin(value):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise argparse.ArgumentTypeError("Use a loopback HTTP origin without a path.")
    return value.rstrip("/")


async def run(args):
    tokens = json.loads((args.data_dir / "credentials.json").read_text())
    def api(path, body=None):
        request = Request(args.web + path, data=json.dumps(body).encode() if body else None,
                          headers={"Authorization":"Bearer " + tokens["guard"], "Content-Type":"application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    visit = api("/api/visitors", {"visitor":"Demo visitor", "unit":"A-101", "purpose":"MCP end-to-end demonstration"})
    async with httpx.AsyncClient(headers={"Authorization":"Bearer " + tokens["resident"]}) as http:
        async with streamable_http_client(args.mcp + "/mcp", http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                if initialized.protocolVersion < "2025-11-25":
                    raise RuntimeError("Protocol is older than 2025-11-25.")
                tools = await session.list_tools()
                async def call(name, arguments=None):
                    result = await session.call_tool(name, arguments or {})
                    if result.isError:
                        raise RuntimeError("MCP tool returned an error: " + name)
                    return result.structuredContent or json.loads(result.content[0].text)
                listed = await call("list_waiting_visitors")
                if not any(v["id"] == visit["id"] for v in listed["visitors"]):
                    raise RuntimeError("Arrival did not reach resident MCP tools.")
                prepared = await call("prepare_visitor_decision", {"visit_id":visit["id"], "decision":"approved"})
                before = next(v for v in api("/api/state")["visits"] if v["id"] == visit["id"])
                if before["status"] != "pending":
                    raise RuntimeError("Preparation unexpectedly changed the decision.")
                confirmation = {"confirmation_id":prepared["confirmation_id"], "confirmed":True}
                decision = await call("confirm_visitor_decision", confirmation)
                replay = await call("confirm_visitor_decision", confirmation)
                if decision != replay:
                    raise RuntimeError("Confirmation retry changed the result.")
                api("/api/movement", {"id":visit["id"], "action":"check-in"})
                receipt = await call("get_visitor_receipt", {"visit_id":visit["id"]})
                api("/api/movement", {"id":visit["id"], "action":"check-out"})
                if receipt["visit"]["status"] != "checked_in":
                    raise RuntimeError("Guard entry did not reach the MCP receipt.")
                proof = {"checked_at":datetime.now(timezone.utc).isoformat(), "transport":"Streamable HTTP",
                         "protocol_version":initialized.protocolVersion, "sdk_client":"official Python MCP SDK",
                         "tools":[tool.name for tool in tools.tools], "before_confirmation":before["status"],
                         "after_confirmation":decision["status"], "after_guard_entry":receipt["visit"]["status"],
                         "confirmation_retry":"same receipt; no duplicate decision", "vendor_connected":False,
                         "physical_device_connected":False, "browser_rendering_verified":False,
                         "events":[event["event"] for event in receipt["audit"]][::-1]}
                (args.data_dir / "mcp-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
                print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", type=local_origin, default="http://127.0.0.1:8091")
    parser.add_argument("--mcp", type=local_origin, default="http://127.0.0.1:8092")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / ".local")
    asyncio.run(run(parser.parse_args()))
