"""
SAP Security Notes MCP Server

A standalone Python MCP server that uses Playwright to connect to
https://me.sap.com/securitynotes, authenticates with SAP credentials,
and extracts security notes with date filtering.
"""
import asyncio
import json
import os
import re
from datetime import datetime, date
from typing import Any

from playwright.async_api import async_playwright, Page, Browser
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sap-security-notes")

# Global browser state
_browser: Browser | None = None
_page: Page | None = None


async def _get_authenticated_page() -> Page:
    """Create a fresh authenticated browser page every time.

    We don't reuse globals because each call may run in a different event loop
    (asyncio.to_thread creates a new loop), making old page references invalid.
    """
    global _browser, _page

    # Always create fresh - old references are invalid across event loops
    _page = None
    _browser = None

    username = os.environ.get("SAP_USERNAME", "")
    password = os.environ.get("SAP_PASSWORD", "")
    if not username or not password:
        raise ValueError("SAP_USERNAME and SAP_PASSWORD environment variables required")

    headful = os.environ.get("SAP_HEADFUL", "false").lower() == "true"

    pw = await async_playwright().start()
    _browser = await pw.chromium.launch(headless=not headful)
    context = await _browser.new_context()
    _page = await context.new_page()

    # Navigate to security notes page (will redirect to login)
    await _page.goto("https://me.sap.com/securitynotes", wait_until="networkidle", timeout=60000)

    # Wait for page to settle
    await asyncio.sleep(3)

    # Check if we're on a login page
    current_url = _page.url
    if "authentication" in current_url or "accounts.sap.com" in current_url or "login" in current_url or "saml2" in current_url:
        # Fill login form
        await _login(_page, username, password)

    return _page


async def _login(page: Page, username: str, password: str):
    """Handle SAP login flow."""
    # Wait for username field
    try:
        await page.wait_for_selector('input[name="j_username"], input[name="email"], input[type="email"], #j_username', timeout=15000)
    except Exception:
        # Maybe already past login
        if "securitynotes" in page.url:
            return

    # Try different username field selectors
    for selector in ['input[name="j_username"]', 'input[name="email"]', 'input[type="email"]', '#j_username', '#email']:
        el = await page.query_selector(selector)
        if el:
            await el.fill(username)
            break

    # Try different password field selectors
    for selector in ['input[name="j_password"]', 'input[type="password"]', '#j_password', '#password']:
        el = await page.query_selector(selector)
        if el:
            await el.fill(password)
            break

    # Click Continue/Submit (step 1 - username)
    for selector in ['button[type="submit"]', '#logOnFormSubmit', 'input[type="submit"]']:
        el = await page.query_selector(selector)
        if el:
            await el.click()
            break

    await asyncio.sleep(3)

    # Step 2: password field should now appear
    pwd_field = await page.query_selector('input[type="password"]')
    if pwd_field:
        await pwd_field.fill(password)
        await asyncio.sleep(1)
        for selector in ['button[type="submit"]', '#logOnFormSubmit', 'input[type="submit"]']:
            el = await page.query_selector(selector)
            if el:
                await el.click()
                break

    # Wait for redirect to complete
    await asyncio.sleep(10)

    # If still not on target page, navigate directly
    if "securitynotes" not in page.url:
        await page.goto("https://me.sap.com/securitynotes", timeout=60000)
        await asyncio.sleep(5)


async def _extract_notes_from_page(page: Page, target_month: int = 0, target_year: int = 0) -> list[dict]:
    """Extract security notes from the me.sap.com/securitynotes page table.

    Uses PageDown keyboard scrolling to load all notes via virtual scroll.
    Stops when notes are older than the target month.
    """
    await asyncio.sleep(5)

    # Click on the grid to focus it for keyboard scrolling
    grid = await page.query_selector('[role="grid"]')
    if grid:
        await grid.click()
        await asyncio.sleep(1)

    # Scroll down using PageDown to load all notes
    all_note_numbers = set()
    stable_count = 0

    for _ in range(40):  # Max 40 PageDown presses
        await page.keyboard.press("PageDown")
        await asyncio.sleep(1.5)

        # Count notes visible
        body_text = await page.inner_text('body')
        current_numbers = set(re.findall(r'\b(\d{7})\b', body_text))

        if len(current_numbers) == len(all_note_numbers):
            stable_count += 1
            if stable_count >= 4:
                break
        else:
            stable_count = 0
            all_note_numbers = current_numbers

        # Check if we've gone past the target month (stop early)
        if target_month and target_year:
            lines = body_text.split('\n')
            for line in lines:
                date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', line)
                if date_match:
                    day, month, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                    if year < target_year or (year == target_year and month < target_month):
                        stable_count = 99
                        break
            if stable_count >= 99:
                break

    # Press End key to ensure we've reached the absolute bottom
    await page.keyboard.press("End")
    await asyncio.sleep(2)
    await page.keyboard.press("End")
    await asyncio.sleep(2)

    # Now extract all notes from the page
    body_text = await page.inner_text('body')
    lines = [l.strip() for l in body_text.split('\n') if l.strip()]

    notes = []
    seen = set()
    for line in lines:
        if not re.search(r'\b\d{7}\b', line):
            continue
        parts = line.split('\t')
        if len(parts) < 4:
            continue
        note = _parse_tab_line(parts)
        if note and note["number"] not in seen:
            seen.add(note["number"])
            notes.append(note)

    return notes


def _parse_tab_line(parts: list[str]) -> dict | None:
    """Parse a tab-separated line from the SAP security notes page.

    Expected format (tab-separated):
    Component | Number | Title | CVSS Score | CVSS Vector | Category | Priority | Released On ...
    """
    note = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 7-digit note number
        if re.match(r'^\d{7,10}$', part):
            note["number"] = part
        # CVSS score (number <= 10)
        elif re.match(r'^\d+\.?\d*$', part):
            try:
                val = float(part)
                if 0 < val <= 10:
                    note["cvss_score"] = str(val)
            except ValueError:
                pass
        # CVSS vector
        elif "CVSS:" in part or "AV:" in part:
            note["cvss_vector"] = part
        # Priority
        elif part in ("HotNews", "Correction with high priority", "Correction with medium priority", "Correction with low priority"):
            note["priority"] = part
        # Date pattern (various formats)
        elif re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', part):
            note.setdefault("released_on", part)
        elif re.match(r'\d{4}-\d{2}-\d{2}', part):
            note.setdefault("released_on", part)
        # Component code (XX-XX or XX-XX-XX pattern)
        elif re.match(r'^[A-Z]{2,}(-[A-Z0-9]{2,})+$', part):
            note["component"] = part
        # Category
        elif part in ("Program error", "Documentation error", "Implementation error"):
            note["category"] = part
        # Title (long text with CVE or vulnerability keywords)
        elif len(part) > 20 and not note.get("title"):
            note["title"] = part

    if note.get("number") and note.get("title"):
        return note
    return None


async def _fetch_note_detail_fast(page: Page, note_number: str) -> dict:
    """Fetch detail for a single note reusing an already-authenticated page.

    Navigates to the note URL, waits for content with a short timeout,
    and extracts software components + support packages.
    Returns partial detail dict (never raises).
    """
    detail = {"software_components": [], "support_packages": []}
    try:
        url = f"https://me.sap.com/notes/{note_number}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Wait for meaningful content - try multiple markers
        found = False
        for marker in ['text=Software Components', 'text=Support Package', 'text=Symptom']:
            try:
                await page.wait_for_selector(marker, timeout=5000)
                found = True
                break
            except Exception:
                continue

        if not found:
            await asyncio.sleep(2)

        body_text = await page.inner_text('body')
        parsed = _parse_note_detail_page(body_text, note_number)
        detail["software_components"] = parsed.get("software_components", [])
        detail["support_packages"] = parsed.get("support_packages", [])
        detail["sections"] = parsed.get("sections", [])
    except Exception:
        pass
    return detail


@mcp.tool()
async def fetch_security_notes(month: int | None = None, year: int | None = None, include_details: bool = True) -> str:
    """
    Fetch SAP Security Notes from me.sap.com/securitynotes.

    Navigates to the SAP Security Notes page, applies date filters,
    and extracts all notes for the specified month. When include_details
    is True (default), also fetches software components and support
    packages for each note using the same browser session.

    Args:
        month: Month number (1-12). Defaults to current month.
        year: Year (e.g., 2026). Defaults to current year.
        include_details: Whether to fetch per-note details. Defaults to True.

    Returns:
        JSON string with the list of security notes found.
    """
    now = datetime.now()
    target_month = month or now.month
    target_year = year or now.year

    try:
        page = await _get_authenticated_page()

        # Navigate to security notes page if not already there
        if "securitynotes" not in page.url:
            await page.goto("https://me.sap.com/securitynotes", timeout=60000)
            await asyncio.sleep(5)

        # Extract notes (scrolling until we pass target month)
        all_notes = await _extract_notes_from_page(page, target_month, target_year)

        # Filter to target month only
        notes = []
        for n in all_notes:
            released = n.get("released_on", "")
            if _matches_month(released, target_month, target_year):
                notes.append(n)

        # Enrich each note with details (same browser session, no extra login)
        if include_details and notes:
            for i, note in enumerate(notes):
                detail = await _fetch_note_detail_fast(page, note["number"])
                note["software_components"] = detail["software_components"]
                note["support_packages"] = detail["support_packages"]
                note["sections"] = detail.get("sections", [])

        return json.dumps({
            "status": "ok",
            "month": target_month,
            "year": target_year,
            "count": len(notes),
            "notes": notes,
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "month": target_month,
            "year": target_year,
        })


def _matches_month(released_on: str, target_month: int, target_year: int) -> bool:
    """Check if a release date string matches the target month/year."""
    if not released_on:
        return False
    # Handle DD.MM.YYYY format
    match = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', released_on)
    if match:
        month = int(match.group(2))
        year = int(match.group(3))
        return month == target_month and year == target_year
    # Handle YYYY-MM-DD format
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})', released_on)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        return month == target_month and year == target_year
    return False


@mcp.tool()
async def get_note_detail(note_number: str) -> str:
    """
    Get detailed information for a specific SAP Security Note including
    support package patches and software component details.

    Args:
        note_number: The SAP Note number (e.g., "3727078")

    Returns:
        JSON string with the note details including support packages and components.
    """
    try:
        page = await _get_authenticated_page()
        url = f"https://me.sap.com/notes/{note_number}"
        await page.goto(url, timeout=60000)
        await asyncio.sleep(8)

        # Extract full page text
        body_text = await page.inner_text('body')

        # Parse structured sections
        detail = _parse_note_detail_page(body_text, note_number)
        detail["url"] = url

        return json.dumps(detail, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "note_number": note_number,
        })


def _parse_note_detail_page(text: str, note_number: str) -> dict:
    """Parse the note detail page text to extract structured data."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Known section headers on SAP note detail pages
    SECTION_HEADERS = {
        "Symptom", "Other Terms", "Reason and Prerequisites", "Solution",
        "Workaround", "CVSS", "Validity", "Support Packages", "Support Package Patches",
        "Software Components", "Correction Instructions", "References",
        "Attached SAP Notes",
    }

    detail = {
        "status": "ok",
        "note_number": note_number,
        "title": "",
        "component": "",
        "priority": "",
        "category": "",
        "released_on": "",
        "software_components": [],
        "support_packages": [],
        "symptom": "",
        "reason": "",
        "solution": "",
        "other_terms": "",
        "workaround": "",
        "sections": [],
        "content_raw": "",
    }

    # State machine to parse sections
    current_section = ""
    section_content = []

    for i, line in enumerate(lines):
        # Detect section headers
        if line in SECTION_HEADERS:
            # Save previous section
            if current_section and section_content:
                _save_section(detail, current_section, section_content)
            current_section = line
            section_content = []
            continue

        # Collect section content
        if current_section:
            section_content.append(line)

        # Extract top-level fields
        if not current_section:
            if "CVE-" in line and not detail["title"]:
                detail["title"] = line
            elif re.match(r'^[A-Z]{2,}(-[A-Z0-9]{2,})+$', line) and not detail["component"]:
                detail["component"] = line
            elif line in ("HotNews", "Correction with high priority",
                         "Correction with medium priority", "Correction with low priority"):
                detail["priority"] = line

    # Save last section
    if current_section and section_content:
        _save_section(detail, current_section, section_content)

    # Store trimmed raw content
    detail["content_raw"] = '\n'.join(lines[:200])

    return detail


def _save_section(detail: dict, section: str, content: list[str]):
    """Save parsed section content to the detail dict."""
    joined = '\n'.join(content)

    # Text sections — store full content and add to ordered sections list
    TEXT_SECTIONS = {"Symptom", "Other Terms", "Reason and Prerequisites", "Solution", "Workaround"}
    if section in TEXT_SECTIONS:
        # Trim content at CVSS line (sometimes appears mid-section)
        trimmed = []
        for line in content:
            if line.startswith("CVSS") or line.startswith("cvss"):
                break
            trimmed.append(line)
        joined = '\n'.join(trimmed)
        if section == "Symptom":
            detail["symptom"] = joined
        elif section == "Reason and Prerequisites":
            detail["reason"] = joined
        elif section == "Solution":
            detail["solution"] = joined
        elif section == "Other Terms":
            detail["other_terms"] = joined
        elif section == "Workaround":
            detail["workaround"] = joined
        # Add to ordered sections list for display
        if joined.strip():
            detail["sections"].append({"heading": section, "text": joined})
        return

    if section in ("Support Packages", "Support Package Patches"):
        skip_words = {"attributes", "available languages", "description", "software component version", "patch level", "url"}
        for line in content:
            if line.strip().lower() in skip_words:
                continue
            parts = line.split('\t')
            if len(parts) >= 2 and re.search(r'[A-Z_]{3,}', parts[0]):
                detail["support_packages"].append({
                    "software_component": parts[0].strip(),
                    "patch_level": parts[1].strip() if len(parts) > 1 else "",
                    "sp_level": parts[2].strip() if len(parts) > 2 else "",
                })
            elif re.search(r'[A-Z_]{3,}\s+\d', line):
                detail["support_packages"].append({"raw": line.strip()})
    elif section == "Software Components":
        skip_words = {"software component", "from", "to", "release"}
        for line in content:
            if line.strip().lower() in skip_words:
                continue
            parts = line.split('\t')
            if len(parts) >= 2 and re.search(r'[A-Z_]{3,}', parts[0]):
                detail["software_components"].append({
                    "component": parts[0].strip(),
                    "from_version": parts[1].strip() if len(parts) > 1 else "",
                    "to_version": parts[2].strip() if len(parts) > 2 else "",
                })
            elif re.search(r'[A-Z_]{3,}', line):
                detail["software_components"].append({"raw": line.strip()})


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
