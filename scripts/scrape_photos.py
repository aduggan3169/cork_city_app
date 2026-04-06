"""
Cork Civic Tracker — Councillor Photo Scraper

Scrapes councillor profile photos from corkcity.ie and updates
the photo_url column in the local SQLite database.

Usage:
    python scripts/scrape_photos.py              # scrape and update DB
    python scripts/scrape_photos.py --dry-run    # show what would be updated
    python scripts/scrape_photos.py --list       # list current photo_url values

Requires: requests, beautifulsoup4  (pip install requests beautifulsoup4)
"""

import argparse
import os
import re
import sqlite3
import sys
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get(
    "CORK_DB_PATH",
    os.path.join(SCRIPT_DIR, "..", "db", "cork_civic_tracker.db"),
)

BASE_URL = "https://www.corkcity.ie"
COUNCILLORS_INDEX = (
    f"{BASE_URL}/en/council-services/councillors-and-democracy/meet-your-councillors/"
)

# Mapping of DB name → known corkcity.ie URL slug where the standard
# slug pattern (lowercase, hyphenated) doesn't match.
# Add overrides here if the scraper misses someone.
SLUG_OVERRIDES = {
    # "Peter Horgan": "p-j-hourican",  # example if needed
}


def get_councillors(conn):
    """Fetch all councillors from the database."""
    rows = conn.execute(
        "SELECT id, first_name, last_name, photo_url FROM councillors ORDER BY last_name"
    ).fetchall()
    return [
        {"id": r[0], "first_name": r[1], "last_name": r[2], "photo_url": r[3]}
        for r in rows
    ]


def build_slug(first_name, last_name):
    """Build a URL slug from councillor name.

    e.g. "Seán" "Martin" → "sean-martin"
    Handles fadas, O' prefixes, Mary Rose → mary-rose, etc.
    """
    full = f"{first_name} {last_name}".lower()
    # Remove fadas
    fada_map = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    full = full.translate(fada_map)
    # Replace O' with o (e.g. O'Flynn → oflynn or o-flynn)
    full = full.replace("'", "")
    full = full.replace("'", "")
    # Replace spaces and non-alpha with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", full).strip("-")
    return slug


def scrape_index_page(session):
    """Scrape the councillor index page to find all profile links.

    Returns dict of lowercase_name → profile_url
    """
    print(f"Fetching index: {COUNCILLORS_INDEX}")
    resp = session.get(COUNCILLORS_INDEX, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    profiles = {}
    # Look for links within the councillor listing
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/meet-your-councillors/" in href and href != COUNCILLORS_INDEX:
            # Extract name from link text
            name_text = a_tag.get_text(strip=True)
            if name_text and len(name_text) > 2:
                full_url = urljoin(BASE_URL, href)
                profiles[name_text.lower()] = full_url

    print(f"  Found {len(profiles)} councillor profile links")
    return profiles


def scrape_photo_from_profile(session, profile_url):
    """Scrape a councillor's profile page for their photo URL.

    Returns the photo URL string or None.
    """
    try:
        resp = session.get(profile_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Error fetching {profile_url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Strategy 1: Look for img tags in the main content area
    # Cork City Council typically uses a content div with the councillor photo
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "").lower()

        # Skip icons, logos, generic images
        if any(skip in src.lower() for skip in [
            "logo", "icon", "banner", "footer", "header",
            "cookie", "social", "twitter", "facebook",
            "linkedin", "youtube", "instagram", "search",
            "arrow", "chevron", "close", "menu", "crest",
        ]):
            continue

        # Look for images in the media folder or content area
        if "/media/" in src or "/media-folder/" in src:
            full_url = urljoin(BASE_URL, src)
            return full_url

    # Strategy 2: Look for Open Graph image meta tag
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        return urljoin(BASE_URL, og_img["content"])

    return None


def find_profile_url(councillor, index_profiles, session):
    """Try to find a councillor's profile URL using multiple strategies."""
    first = councillor["first_name"]
    last = councillor["last_name"]
    full_name = f"{first} {last}"

    # Check for manual override
    if full_name in SLUG_OVERRIDES:
        slug = SLUG_OVERRIDES[full_name]
        return f"{COUNCILLORS_INDEX}{slug}/"

    # Strategy 1: Match against scraped index page links
    name_lower = full_name.lower()
    fada_map = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    name_normalised = name_lower.translate(fada_map).replace("'", "").replace("'", "")

    for index_name, url in index_profiles.items():
        index_normalised = index_name.translate(fada_map).replace("'", "").replace("'", "")
        if index_normalised == name_normalised:
            return url
        # Partial match: last name appears in the index entry
        if last.lower().translate(fada_map) in index_normalised:
            # Check first name initial too
            if index_normalised.startswith(first[0].lower()):
                return url

    # Strategy 2: Construct URL from slug
    slug = build_slug(first, last)
    candidate_urls = [
        f"{COUNCILLORS_INDEX}{slug}/",
        f"{COUNCILLORS_INDEX}{slug}.html",
    ]
    for url in candidate_urls:
        try:
            resp = session.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                return url
        except Exception:
            continue

    return None


def main():
    parser = argparse.ArgumentParser(description="Scrape councillor photos from corkcity.ie")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
    parser.add_argument("--list", action="store_true", help="List current photo_url values and exit")
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    councillors = get_councillors(conn)

    if args.list:
        print(f"\n{'Name':<25} {'Photo URL'}")
        print("-" * 80)
        for c in councillors:
            name = f"{c['first_name']} {c['last_name']}"
            url = c["photo_url"] or "(none)"
            print(f"{name:<25} {url}")
        conn.close()
        return

    session = requests.Session()
    session.headers.update({
        "User-Agent": "CorkCivicTracker/1.0 (civic data project; contact: aduggan316@gmail.com)"
    })

    # Step 1: Scrape the index page
    print("\n=== Cork Civic Tracker — Photo Scraper ===\n")
    index_profiles = scrape_index_page(session)

    # Step 2: For each councillor, find their profile and scrape the photo
    updates = []
    not_found = []

    for c in councillors:
        name = f"{c['first_name']} {c['last_name']}"
        print(f"\n[{name}]")

        profile_url = find_profile_url(c, index_profiles, session)
        if not profile_url:
            print(f"  ✗ Could not find profile page")
            not_found.append(name)
            continue

        print(f"  Profile: {profile_url}")
        photo_url = scrape_photo_from_profile(session, profile_url)

        if photo_url:
            print(f"  ✓ Photo: {photo_url}")
            updates.append((photo_url, c["id"]))
        else:
            print(f"  ✗ No photo found on profile page")
            not_found.append(name)

    # Step 3: Update the database
    print(f"\n{'=' * 60}")
    print(f"Found photos for {len(updates)}/{len(councillors)} councillors")

    if not_found:
        print(f"\nMissing photos for:")
        for name in not_found:
            print(f"  - {name}")

    if updates and not args.dry_run:
        conn.executemany(
            "UPDATE councillors SET photo_url = ? WHERE id = ?",
            updates,
        )
        conn.commit()
        print(f"\n✓ Updated {len(updates)} photo URLs in database")
    elif updates and args.dry_run:
        print(f"\n[DRY RUN] Would update {len(updates)} photo URLs")
    else:
        print("\nNo updates to make.")

    conn.close()


if __name__ == "__main__":
    main()
