"""Client that communicates with the SAP Notes MCP server via stdio JSON-RPC."""
import asyncio
import json
import os
import re
import subprocess
import threading
from datetime import datetime
from src.ingestion.parser import ParsedNote


class SAPMCPClient:
    def __init__(
        self,
        node_path: str | None = None,
        server_script_path: str | None = None,
        sap_username: str | None = None,
        sap_password: str | None = None,
    ):
        self.node_path = node_path or os.environ.get(
            "SAP_MCP_NODE_PATH", r"C:\Program Files\nodejs\node.exe"
        )
        self.server_script_path = server_script_path or os.environ.get(
            "SAP_MCP_SERVER_PATH",
            r"C:\Users\asingh775\Claude_Code\sap-mcp-servers\packages\notes\dist\mcp-server.js",
        )
        self.sap_username = sap_username or os.environ.get("SAP_USERNAME", "")
        self.sap_password = sap_password or os.environ.get("SAP_PASSWORD", "")
        self._process = None
        self._request_id = 0

    def _start_process(self):
        if self._process is not None and self._process.poll() is None:
            return

        env = os.environ.copy()
        env["SAP_USERNAME"] = self.sap_username
        env["SAP_PASSWORD"] = self.sap_password
        env["HEADFUL"] = "false"
        env["LOG_LEVEL"] = "error"

        self._process = subprocess.Popen(
            [self.node_path, self.server_script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def _send_and_receive(self, method: str, params: dict) -> dict:
        self._request_id += 1
        msg = json.dumps({
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }) + "\n"

        self._process.stdin.write(msg.encode())
        self._process.stdin.flush()

        # Read lines until we get a JSON response
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed connection")
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded.startswith("{"):
                return json.loads(decoded)

    def _send_notification(self, method: str, params: dict):
        msg = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }) + "\n"
        self._process.stdin.write(msg.encode())
        self._process.stdin.flush()

    def _initialize(self):
        self._start_process()
        self._send_and_receive("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "snap", "version": "1.0"},
        })
        self._send_notification("notifications/initialized", {})

    def _search_sync(self, query: str) -> list[dict]:
        self._initialize()
        response = self._send_and_receive("tools/call", {
            "name": "search",
            "arguments": {"q": query, "lang": "EN"},
        })
        result = response.get("result", {})
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            text = content[0]["text"]
            try:
                data = json.loads(text)
                return data.get("results", [])
            except (json.JSONDecodeError, ValueError):
                pass
            return _parse_search_text(text)
        return []

    async def search(self, query: str) -> list[dict]:
        return await asyncio.to_thread(self._search_sync, query)

    async def fetch_note(self, note_number: str) -> dict:
        def _fetch():
            self._initialize()
            response = self._send_and_receive("tools/call", {
                "name": "fetch",
                "arguments": {"noteNumber": note_number},
            })
            result = response.get("result", {})
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                text = content[0]["text"]
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    return {"raw": text}
            return {}
        return await asyncio.to_thread(_fetch)

    async def fetch_current_month_notes(self) -> list[ParsedNote]:
        """Fetch security notes for the current month using multiple search passes."""
        now = datetime.now()
        month_name = now.strftime("%B")
        year = now.year

        # Use multiple targeted queries to maximize coverage
        # The Coveo API returns max 10 per query, so we cast a wide net
        queries = [
            f"CVE-{year} vulnerability SAP",
            f"security patch {month_name} {year}",
            f"Missing Authorization check SAP {year}",
            f"Cross-Site Scripting XSS SAP {year}",
            f"code injection SAP {year}",
            f"information disclosure SAP {year}",
            f"directory traversal SAP {year}",
            f"remote code execution SAP {year}",
            f"server-side request forgery SAP {year}",
            f"SQL injection SAP {year}",
            f"denial of service vulnerability SAP {year}",
            f"authentication bypass SAP {year}",
            f"privilege escalation SAP {year}",
            f"CVE-{year} SAP NetWeaver",
            f"CVE-{year} SAP S/4HANA",
            f"CVE-{year} SAP Business",
        ]

        all_results = {}
        for query in queries:
            try:
                search_results = await self.search(query)
                for r in search_results:
                    note_id = r.get("id", "")
                    if note_id and note_id not in all_results:
                        all_results[note_id] = r
            except Exception:
                continue

        # Filter to current month and security-relevant notes
        parsed_notes = []
        for result in all_results.values():
            release_date = result.get("releaseDate", "")
            title = result.get("title", "")

            # Must be released in current month
            if not release_date or not _is_current_month(release_date, now):
                continue

            # Must be security-related
            title_lower = title.lower()
            is_security = (
                "cve-" in title_lower
                or "vulnerability" in title_lower
                or "security" in title_lower
                or "injection" in title_lower
                or "cross-site" in title_lower
                or "authorization" in title_lower
                or "traversal" in title_lower
                or "disclosure" in title_lower
                or "bypass" in title_lower
                or "escalation" in title_lower
                or "forgery" in title_lower
                or "denial of service" in title_lower
            )
            # Exclude notes that say "NOT impacting"
            if "not impacting" in title_lower or "not impact" in title_lower:
                continue

            if not is_security:
                continue

            note = _search_result_to_parsed_note(result)
            parsed_notes.append(note)

        return parsed_notes

    async def close(self):
        if self._process and self._process.poll() is None:
            self._process.stdin.close()
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                self._process.kill()


def _is_current_month(release_date: str, now: datetime) -> bool:
    try:
        dt = datetime.strptime(release_date, "%Y-%m-%d")
        return dt.year == now.year and dt.month == now.month
    except ValueError:
        pass
    try:
        dt = datetime.strptime(release_date.split("T")[0], "%Y-%m-%d")
        return dt.year == now.year and dt.month == now.month
    except ValueError:
        return False


def _extract_cve(title: str) -> str:
    match = re.search(r'CVE-\d{4}-\d+', title or "")
    return match.group(0) if match else ""


def _normalize_priority(priority: str) -> str:
    if not priority:
        return "medium"
    p = priority.strip().lower()
    if "hot" in p:
        return "hot_news"
    if "high" in p:
        return "high"
    if "low" in p:
        return "low"
    return "medium"


def _search_result_to_parsed_note(result: dict) -> ParsedNote:
    title = result.get("title", "")
    cve = _extract_cve(title)
    component = result.get("component", "")

    return ParsedNote(
        note_number=str(result.get("id", "")),
        title=re.sub(r'\[CVE-\d{4}-\d+\]\s*', '', title).strip(),
        cvss_score=0.0,
        cvss_vector=cve,
        priority=_normalize_priority(result.get("priority", "medium")),
        components=[component] if component else [],
        version_ranges=[],
        release_date=result.get("releaseDate", ""),
        description=result.get("summary", title),
        solution_type="",
        raw_content=result.get("url", ""),
    )


def _parse_search_text(text: str) -> list[dict]:
    """Parse the markdown-formatted search results from SAP MCP server."""
    results = []
    current = None

    for line in text.split("\n"):
        line = line.strip()
        match = re.match(r'\*\*SAP Note (\d+)\*\*', line)
        if match:
            if current:
                results.append(current)
            current = {"id": match.group(1)}
            continue
        if current is None:
            continue
        if line.startswith("Title:"):
            current["title"] = line[6:].strip()
        elif line.startswith("Summary:"):
            current["summary"] = line[8:].strip()
        elif line.startswith("Component:"):
            current["component"] = line[10:].strip()
        elif line.startswith("Release Date:"):
            current["releaseDate"] = line[13:].strip()
        elif line.startswith("URL:"):
            current["url"] = line[4:].strip()
        elif line.startswith("Priority:"):
            current["priority"] = line[9:].strip()

    if current:
        results.append(current)

    return results
