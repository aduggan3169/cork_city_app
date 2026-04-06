"""
Cork Civic Tracker — Minutes Ingestion Script
==============================================

Scrapes Cork City Council's full council meeting minutes (PDF),
extracts attendance, motions, and votes, and writes to SQLite.

Run locally (not on Streamlit Cloud) — needs network access to corkcity.ie.

Usage:
    # First run: discover all available minutes and ingest
    python scripts/ingest_minutes.py

    # Ingest a specific PDF by URL
    python scripts/ingest_minutes.py --url https://www.corkcity.ie/media/.../minutes-council-meeting-DD-MM-YY.pdf

    # Ingest from a local PDF file (useful for testing)
    python scripts/ingest_minutes.py --file /path/to/minutes.pdf

    # Dry run — parse and show extracted data without writing to DB
    python scripts/ingest_minutes.py --dry-run

    # Re-discover PDF links from the council website
    python scripts/ingest_minutes.py --discover

Requirements:
    pip install requests beautifulsoup4 pdfplumber
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    import pdfplumber
except ImportError:
    sys.exit("Missing dependency: pip install pdfplumber")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency: pip install beautifulsoup4")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_DIR = os.path.join(PROJECT_DIR, "db")
DB_PATH = os.environ.get(
    "CORK_DB_PATH",
    os.path.join(DB_DIR, "cork_civic_tracker.db"),
)

MINUTES_INDEX_URL = (
    "https://www.corkcity.ie/en/council-services/councillors-and-democracy/"
    "meetings-of-the-city-council/full-council-meetings/"
    "full-council-meetings-minutes/"
)

# Known year sub-pages (corkcity.ie uses different path patterns across years)
MINUTES_YEAR_URLS = [
    MINUTES_INDEX_URL + "2025-1/",
    MINUTES_INDEX_URL + "2025/",
    MINUTES_INDEX_URL + "2024/",
    MINUTES_INDEX_URL + "2024-1/",
]

# Cache directory for downloaded PDFs
CACHE_DIR = os.path.join(SCRIPT_DIR, ".pdf_cache")

# Standard patterns in Irish local authority minutes
# Cork City Council format (based on known PDF naming and Irish LA conventions):
#   - Title: "MINUTES OF ORDINARY MEETING OF CORK CITY COUNCIL"
#   - Attendance: "I dLáthair/Present:" followed by councillor list
#   - Apologies: "Leithscéalta/Apologies:" or just "Apologies:"
#   - Motions: "Proposed by Cllr X", "Seconded by Cllr Y"
#   - Votes: "Resolved" / roll call if demanded

ATTENDANCE_PATTERNS = [
    # Bilingual Irish/English headers
    r"(?:I\s+dL[áa]thair\s*/?\s*)?Present\s*[:\-–]",
    r"Present\s*[:\-–]",
    r"Comhairleoir[ií]\s*/?\s*Councillors?\s*Present",
]

APOLOGIES_PATTERNS = [
    r"(?:Leithsc[ée]alta\s*/?\s*)?Apologies\s*[:\-–]",
    r"Apologies\s*[:\-–]",
]

MOTION_PATTERNS = [
    # "Proposed by Cllr X" / "Seconded by Cllr Y"
    r"Proposed\s+by\s+(?:Cllr\.?\s+)?(.+?)(?:\s+and\s+[Ss]econded|\s*$)",
    r"Seconded\s+by\s+(?:Cllr\.?\s+)?(.+?)(?:\s*\.|$)",
]

RESOLUTION_PATTERNS = [
    r"(?:It\s+was\s+)?[Rr]esolved\s*[:\-–]?\s*(.+)",
    r"(?:It\s+was\s+)?[Aa]greed\s*[:\-–]?\s*(.+)",
    r"The\s+motion\s+was\s+(?:carried|defeated|deferred|withdrawn)",
]


# ---------------------------------------------------------------------------
# PDF Discovery
# ---------------------------------------------------------------------------
def discover_pdf_urls():
    """Scrape the Cork City Council minutes pages to find PDF links."""
    pdf_urls = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "CorkCivicTracker/1.0 (civic data research)"
    })

    urls_to_check = MINUTES_YEAR_URLS + [MINUTES_INDEX_URL]

    for page_url in urls_to_check:
        try:
            resp = session.get(page_url, timeout=30)
            if resp.status_code != 200:
                print(f"  SKIP {page_url} — HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Match minutes PDF links
                if "minutes" in href.lower() and href.lower().endswith(".pdf"):
                    # Normalise to absolute URL
                    if href.startswith("/"):
                        href = "https://www.corkcity.ie" + href
                    elif not href.startswith("http"):
                        continue
                    if href not in pdf_urls:
                        pdf_urls.append(href)
                        print(f"  Found: {href}")

        except requests.RequestException as e:
            print(f"  ERROR fetching {page_url}: {e}")

    # Also check the media folder page
    try:
        media_url = "https://www.corkcity.ie/en/media-folder/councillors-democracy/meetings-and-minutes/"
        resp = session.get(media_url, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "minutes" in href.lower() and href.lower().endswith(".pdf"):
                    if href.startswith("/"):
                        href = "https://www.corkcity.ie" + href
                    if href not in pdf_urls:
                        pdf_urls.append(href)
                        print(f"  Found: {href}")
    except requests.RequestException:
        pass

    return sorted(set(pdf_urls))


# ---------------------------------------------------------------------------
# PDF Download & Cache
# ---------------------------------------------------------------------------
def download_pdf(url):
    """Download a PDF and cache it locally. Returns local file path."""
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Derive filename from URL
    filename = url.split("/")[-1]
    if not filename.endswith(".pdf"):
        filename += ".pdf"
    local_path = os.path.join(CACHE_DIR, filename)

    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        print(f"  Using cached: {local_path}")
        return local_path

    print(f"  Downloading: {url}")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(resp.content)
    print(f"  Saved: {local_path} ({len(resp.content):,} bytes)")
    return local_path


# ---------------------------------------------------------------------------
# PDF Parsing
# ---------------------------------------------------------------------------
def extract_text_from_pdf(pdf_path):
    """Extract full text from a PDF, page by page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def parse_meeting_date(text, filename=None):
    """Extract the meeting date from the minutes header or filename."""
    # Try from filename first (most reliable)
    # Pattern: minutes-council-meeting-DD-MM-YY.pdf
    if filename:
        match = re.search(r"(\d{2})-(\d{2})-(\d{2,4})", filename)
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = "20" + year
            try:
                return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Try from text header
    # "HELD ON MONDAY 14th APRIL 2025"
    date_pattern = r"HELD\s+ON\s+\w+\s+(\d{1,2})\w*\s+(\w+)\s+(\d{4})"
    match = re.search(date_pattern, text, re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        try:
            dt = datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def parse_meeting_type(text):
    """Determine the meeting type from the title."""
    text_upper = text[:500].upper()
    if "SPECIAL" in text_upper:
        return "Special"
    if "ANNUAL" in text_upper:
        return "Annual"
    if "BUDGET" in text_upper:
        return "Budget"
    if "EXTRAORDINARY" in text_upper:
        return "Extraordinary"
    return "Full Council"


def parse_attendance(text):
    """Extract lists of present and absent councillors."""
    present = []
    apologies = []

    # Find the attendance section
    # Look for "Present:" or "I dLáthair/Present:" section
    for pattern in ATTENDANCE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = match.end()
            # Find the end of the attendance section (next major heading)
            # Usually ends at "Apologies:", an item number, or a section header
            end_match = re.search(
                r"(?:Leithsc[ée]alta|Apologies|^\d+\.|^[A-Z][A-Z\s]{10,})",
                text[start:start + 3000],
                re.MULTILINE | re.IGNORECASE,
            )
            end = start + (end_match.start() if end_match else 2000)
            present_text = text[start:end]

            # Extract councillor names
            # Patterns: "Cllr. John Smith", "Cllr John Smith", "Comhairleoir John Smith"
            names = re.findall(
                r"(?:Cllr\.?\s+|Comhairleoir\s+)([A-ZÁÉÍÓÚáéíóú][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚáéíóú]['\-]?[A-Za-záéíóú]+)+)",
                present_text,
            )
            if names:
                present = [n.strip() for n in names]
            else:
                # Fallback: try comma/newline separated names
                lines = present_text.strip().split("\n")
                for line in lines:
                    line = line.strip().strip(",").strip()
                    line = re.sub(r"^(?:Cllr\.?\s*)", "", line).strip()
                    if line and len(line) > 3 and not line[0].isdigit():
                        present.append(line)
            break

    # Find apologies section
    for pattern in APOLOGIES_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = match.end()
            end_match = re.search(
                r"(?:^\d+\.|^[A-Z][A-Z\s]{10,}|Lord Mayor|Confirmation)",
                text[start:start + 2000],
                re.MULTILINE,
            )
            end = start + (end_match.start() if end_match else 1000)
            apologies_text = text[start:end]

            names = re.findall(
                r"(?:Cllr\.?\s+|Comhairleoir\s+)([A-ZÁÉÍÓÚáéíóú][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚáéíóú]['\-]?[A-Za-záéíóú]+)+)",
                apologies_text,
            )
            if names:
                apologies = [n.strip() for n in names]
            break

    return present, apologies


def parse_motions(text):
    """Extract motions from the minutes text."""
    motions = []

    # Split into numbered items or sections
    # Irish council minutes typically use numbered items: "1.", "2.", etc.
    # or "Item No. 1", "Item No. 2"
    sections = re.split(r"\n(?=\d+\.?\s+[A-Z])", text)

    for section in sections:
        motion_data = {}

        # Check if this section contains a motion
        has_proposed = re.search(r"[Pp]roposed\s+by", section)
        has_resolved = re.search(
            r"[Rr]esolved|[Aa]greed|motion\s+was\s+(?:carried|defeated|deferred|withdrawn)",
            section,
        )

        if not (has_proposed or has_resolved):
            continue

        # Extract title — first substantial line of the section
        lines = section.strip().split("\n")
        title_line = lines[0].strip() if lines else ""
        # Remove item numbering
        title_line = re.sub(r"^\d+\.?\s*", "", title_line).strip()
        if title_line:
            motion_data["title"] = title_line[:200]

        # Full section text as description
        motion_data["description"] = section.strip()[:2000]

        # Proposed by
        proposed_match = re.search(
            r"[Pp]roposed\s+by\s+(?:Cllr\.?\s+)?([A-ZÁÉÍÓÚa-záéíóú][A-Za-záéíóú'\-\s]+?)(?:\s+and\s+|\s*,|\s*\n|\s*$)",
            section,
        )
        if proposed_match:
            motion_data["proposed_by"] = proposed_match.group(1).strip()

        # Seconded by
        seconded_match = re.search(
            r"[Ss]econded\s+by\s+(?:Cllr\.?\s+)?([A-ZÁÉÍÓÚa-záéíóú][A-Za-záéíóú'\-\s]+?)(?:\s*\.|\s*,|\s*\n|\s*$)",
            section,
        )
        if seconded_match:
            motion_data["seconded_by"] = seconded_match.group(1).strip()

        # Outcome
        if re.search(r"motion\s+was\s+carried|[Rr]esolved|[Aa]greed", section):
            motion_data["outcome"] = "Passed"
        elif re.search(r"motion\s+was\s+defeated|rejected|not\s+carried", section):
            motion_data["outcome"] = "Failed"
        elif re.search(r"deferred|adjourned", section, re.IGNORECASE):
            motion_data["outcome"] = "Deferred"
        elif re.search(r"withdrawn|withdrew", section, re.IGNORECASE):
            motion_data["outcome"] = "Withdrawn"
        elif re.search(r"amended", section, re.IGNORECASE):
            motion_data["outcome"] = "Amended"
        else:
            motion_data["outcome"] = "Passed"  # Default for resolved

        # Roll call votes (if any — these are rare in Irish councils)
        vote_for = []
        vote_against = []
        roll_call_match = re.search(
            r"(?:roll\s+call|recorded\s+vote|vot[ée]|Vóta)",
            section,
            re.IGNORECASE,
        )
        if roll_call_match:
            # Look for "For:" / "Against:" sections
            for_match = re.search(
                r"(?:For|I bhFábhar)\s*[:\-–]\s*(.+?)(?:Against|In Aghaidh|$)",
                section[roll_call_match.start():],
                re.DOTALL | re.IGNORECASE,
            )
            if for_match:
                vote_for = re.findall(
                    r"(?:Cllr\.?\s+)?([A-ZÁÉÍÓÚáéíóú][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚáéíóú]['\-]?[A-Za-záéíóú]+)+)",
                    for_match.group(1),
                )

            against_match = re.search(
                r"(?:Against|In Aghaidh)\s*[:\-–]\s*(.+?)(?:Abstain|Staon|$)",
                section[roll_call_match.start():],
                re.DOTALL | re.IGNORECASE,
            )
            if against_match:
                vote_against = re.findall(
                    r"(?:Cllr\.?\s+)?([A-ZÁÉÍÓÚáéíóú][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚáéíóú]['\-]?[A-Za-záéíóú]+)+)",
                    against_match.group(1),
                )

        motion_data["vote_for"] = vote_for
        motion_data["vote_against"] = vote_against

        if motion_data.get("title"):
            motions.append(motion_data)

    return motions


def parse_minutes(pdf_path):
    """Parse a full council minutes PDF. Returns structured data dict."""
    filename = os.path.basename(pdf_path)
    print(f"\nParsing: {filename}")

    text = extract_text_from_pdf(pdf_path)
    if not text:
        print("  WARNING: No text extracted from PDF")
        return None

    meeting_date = parse_meeting_date(text, filename)
    meeting_type = parse_meeting_type(text)
    present, apologies = parse_attendance(text)
    motions = parse_motions(text)

    result = {
        "filename": filename,
        "pdf_path": pdf_path,
        "meeting_date": meeting_date,
        "meeting_type": meeting_type,
        "title": f"{meeting_type} Meeting — {meeting_date or 'Unknown Date'}",
        "present": present,
        "apologies": apologies,
        "motions": motions,
        "raw_text_length": len(text),
    }

    print(f"  Date: {meeting_date}")
    print(f"  Type: {meeting_type}")
    print(f"  Present: {len(present)} councillors")
    print(f"  Apologies: {len(apologies)} councillors")
    print(f"  Motions found: {len(motions)}")
    for i, m in enumerate(motions):
        proposed = m.get("proposed_by", "?")
        outcome = m.get("outcome", "?")
        votes = f" (For:{len(m['vote_for'])}, Against:{len(m['vote_against'])})" if m.get("vote_for") or m.get("vote_against") else ""
        print(f"    {i+1}. {m['title'][:80]}... — {outcome} (by {proposed}){votes}")

    return result


# ---------------------------------------------------------------------------
# Councillor Name Matching
# ---------------------------------------------------------------------------
def build_councillor_lookup(conn):
    """Build a fuzzy lookup from name variants to councillor IDs."""
    rows = conn.execute(
        "SELECT id, first_name, last_name FROM councillors"
    ).fetchall()

    lookup = {}
    for cid, first, last in rows:
        full = f"{first} {last}"
        # Exact full name
        lookup[full.lower()] = cid
        # Last name only (risky but useful for common patterns)
        lookup[last.lower()] = cid
        # "F. Last" pattern
        lookup[f"{first[0]}. {last}".lower()] = cid
        # Handle Ó/O' variants
        if last.startswith("O'"):
            lookup[f"{first} O{last[2:]}".lower()] = cid
            lookup[f"O{last[2:]}".lower()] = cid

    return lookup


def match_councillor(name, lookup):
    """Try to match a councillor name to a DB ID."""
    name_clean = name.strip()

    # Try exact match
    if name_clean.lower() in lookup:
        return lookup[name_clean.lower()]

    # Try without "Cllr." prefix
    name_clean = re.sub(r"^Cllr\.?\s*", "", name_clean).strip()
    if name_clean.lower() in lookup:
        return lookup[name_clean.lower()]

    # Try last name only
    parts = name_clean.split()
    if parts:
        last = parts[-1]
        if last.lower() in lookup:
            return lookup[last.lower()]

    return None


# ---------------------------------------------------------------------------
# Database Writing
# ---------------------------------------------------------------------------
def get_or_create_meeting(conn, meeting_data):
    """Insert a meeting if it doesn't exist. Returns meeting ID."""
    date = meeting_data["meeting_date"]
    if not date:
        return None

    # Check if meeting already exists for this date
    existing = conn.execute(
        "SELECT id FROM meetings WHERE date = ?", (date,)
    ).fetchone()
    if existing:
        print(f"  Meeting {date} already exists (id={existing[0]})")
        return existing[0]

    title = meeting_data["title"]
    mtype = meeting_data["meeting_type"]
    url = meeting_data.get("pdf_url")

    conn.execute(
        "INSERT INTO meetings (title, date, meeting_type, minutes_url) VALUES (?, ?, ?, ?)",
        (title, date, mtype, url),
    )
    conn.commit()
    mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"  Created meeting: {title} (id={mid})")
    return mid


def write_attendance(conn, meeting_id, present_names, apology_names, councillor_lookup):
    """Write attendance records for a meeting."""
    # Check if attendance already recorded for this meeting
    existing = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE meeting_id = ?", (meeting_id,)
    ).fetchone()[0]
    if existing > 0:
        print(f"  Attendance already recorded for meeting {meeting_id} ({existing} records)")
        return

    written = 0
    unmatched = []

    for name in present_names:
        cid = match_councillor(name, councillor_lookup)
        if cid:
            conn.execute(
                "INSERT OR IGNORE INTO attendance (councillor_id, meeting_id, present) VALUES (?, ?, 1)",
                (cid, meeting_id),
            )
            written += 1
        else:
            unmatched.append(name)

    for name in apology_names:
        cid = match_councillor(name, councillor_lookup)
        if cid:
            conn.execute(
                "INSERT OR IGNORE INTO attendance (councillor_id, meeting_id, present) VALUES (?, ?, 0)",
                (cid, meeting_id),
            )
            written += 1
        else:
            unmatched.append(name)

    conn.commit()
    print(f"  Wrote {written} attendance records")
    if unmatched:
        print(f"  UNMATCHED names: {unmatched}")


def write_motions(conn, meeting_id, motions_data, councillor_lookup):
    """Write motions and any recorded votes."""
    written_motions = 0
    written_votes = 0

    for motion in motions_data:
        title = motion.get("title", "Untitled motion")

        # Check if this motion already exists
        existing = conn.execute(
            "SELECT id FROM motions WHERE meeting_id = ? AND title = ?",
            (meeting_id, title),
        ).fetchone()
        if existing:
            continue

        proposed_id = None
        if motion.get("proposed_by"):
            proposed_id = match_councillor(motion["proposed_by"], councillor_lookup)

        seconded_id = None
        if motion.get("seconded_by"):
            seconded_id = match_councillor(motion["seconded_by"], councillor_lookup)

        conn.execute(
            """INSERT INTO motions (meeting_id, title, description, proposed_by, seconded_by, outcome)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                meeting_id,
                title,
                motion.get("description", ""),
                proposed_id,
                seconded_id,
                motion.get("outcome", "Passed"),
            ),
        )
        motion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        written_motions += 1

        # Write roll call votes if recorded
        for name in motion.get("vote_for", []):
            cid = match_councillor(name, councillor_lookup)
            if cid:
                conn.execute(
                    "INSERT OR IGNORE INTO votes (councillor_id, motion_id, vote) VALUES (?, ?, 'For')",
                    (cid, motion_id),
                )
                written_votes += 1

        for name in motion.get("vote_against", []):
            cid = match_councillor(name, councillor_lookup)
            if cid:
                conn.execute(
                    "INSERT OR IGNORE INTO votes (councillor_id, motion_id, vote) VALUES (?, ?, 'Against')",
                    (cid, motion_id),
                )
                written_votes += 1

    conn.commit()
    print(f"  Wrote {written_motions} motions, {written_votes} votes")


def ingest_to_db(parsed_data, pdf_url=None):
    """Write parsed minutes data to the database."""
    if not parsed_data or not parsed_data.get("meeting_date"):
        print("  SKIP: No meeting date extracted — cannot write to DB")
        return

    if pdf_url:
        parsed_data["pdf_url"] = pdf_url

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    councillor_lookup = build_councillor_lookup(conn)

    meeting_id = get_or_create_meeting(conn, parsed_data)
    if not meeting_id:
        print("  SKIP: Could not create meeting record")
        conn.close()
        return

    write_attendance(
        conn, meeting_id,
        parsed_data["present"],
        parsed_data["apologies"],
        councillor_lookup,
    )

    write_motions(conn, meeting_id, parsed_data["motions"], councillor_lookup)

    # Also create a source record for the minutes
    if pdf_url:
        existing_source = conn.execute(
            "SELECT id FROM sources WHERE url = ?", (pdf_url,)
        ).fetchone()
        if not existing_source:
            conn.execute(
                "INSERT INTO sources (url, title, source_type, date) VALUES (?, ?, 'Minutes', ?)",
                (pdf_url, f"Minutes — {parsed_data['title']}", parsed_data["meeting_date"]),
            )
            conn.commit()

    conn.close()
    print(f"  Done — ingested into {DB_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Cork Civic Tracker — Ingest council meeting minutes"
    )
    parser.add_argument(
        "--url", help="URL of a specific minutes PDF to ingest"
    )
    parser.add_argument(
        "--file", help="Path to a local minutes PDF to ingest"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display data without writing to DB",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Only discover PDF URLs (don't download or parse)",
    )
    parser.add_argument(
        "--output-json",
        help="Write parsed data to a JSON file (useful for debugging)",
    )

    args = parser.parse_args()

    print("Cork Civic Tracker — Minutes Ingestion")
    print("=" * 50)
    print(f"DB: {DB_PATH}")
    print()

    if args.discover:
        print("Discovering PDF URLs...")
        urls = discover_pdf_urls()
        print(f"\nFound {len(urls)} minutes PDFs:")
        for url in urls:
            print(f"  {url}")
        return

    if args.file:
        # Parse a local PDF
        parsed = parse_minutes(args.file)
        if parsed and not args.dry_run:
            ingest_to_db(parsed)
        if parsed and args.output_json:
            # Serialise for inspection
            out = {k: v for k, v in parsed.items() if k != "pdf_path"}
            with open(args.output_json, "w") as f:
                json.dump(out, f, indent=2, default=str)
            print(f"\nJSON output: {args.output_json}")
        return

    if args.url:
        # Download and parse a specific URL
        pdf_path = download_pdf(args.url)
        parsed = parse_minutes(pdf_path)
        if parsed and not args.dry_run:
            ingest_to_db(parsed, pdf_url=args.url)
        if parsed and args.output_json:
            out = {k: v for k, v in parsed.items() if k != "pdf_path"}
            with open(args.output_json, "w") as f:
                json.dump(out, f, indent=2, default=str)
            print(f"\nJSON output: {args.output_json}")
        return

    # Default: discover all PDFs and ingest them
    print("Step 1: Discovering PDF URLs...")
    urls = discover_pdf_urls()
    if not urls:
        print("No PDF URLs found. Try --url to ingest a specific PDF.")
        return

    print(f"\nStep 2: Downloading and parsing {len(urls)} PDFs...")
    all_parsed = []

    for url in urls:
        try:
            pdf_path = download_pdf(url)
            parsed = parse_minutes(pdf_path)
            if parsed:
                all_parsed.append((url, parsed))
                if not args.dry_run:
                    ingest_to_db(parsed, pdf_url=url)
        except Exception as e:
            print(f"  ERROR processing {url}: {e}")

    print(f"\nDone. Processed {len(all_parsed)}/{len(urls)} PDFs.")

    if args.output_json:
        out = []
        for url, parsed in all_parsed:
            item = {k: v for k, v in parsed.items() if k != "pdf_path"}
            item["url"] = url
            out.append(item)
        with open(args.output_json, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"JSON output: {args.output_json}")


if __name__ == "__main__":
    main()
