"""
Cork Civic Tracker — Seed Script
Populates the database with real Cork City Council 2024 data
and sample motions/votes/positions for demo purposes.
"""
import sqlite3
import os
import random
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "cork_civic_tracker.db")
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "schema.sql")


def init_db():
    """Create database and apply schema."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    return conn


def seed_parties(conn):
    """Insert political parties."""
    parties = [
        ("Fianna Fáil", "FF", "#66BB66"),
        ("Fine Gael", "#0047AB", "#0047AB"),  # fix below
        ("Sinn Féin", "SF", "#326760"),
        ("Labour Party", "LAB", "#CC0000"),
        ("Green Party", "GP", "#009A49"),
        ("Social Democrats", "SD", "#7C2C8C"),
        ("Workers' Party", "WP", "#D71920"),
        ("Solidarity–PBP", "SOL-PBP", "#E5005B"),
        ("Independent Ireland", "II", "#FFA500"),
        ("Independent", "IND", "#808080"),
    ]
    # Fix Fine Gael entry
    parties[1] = ("Fine Gael", "FG", "#0047AB")

    conn.executemany(
        "INSERT OR IGNORE INTO parties (name, short_name, colour) VALUES (?, ?, ?)",
        parties,
    )
    conn.commit()

    # Build lookup
    rows = conn.execute("SELECT id, short_name FROM parties").fetchall()
    return {short: pid for pid, short in rows}


def seed_wards(conn):
    """Insert Local Electoral Areas (LEAs)."""
    wards = [
        ("Cork City North East", 6),
        ("Cork City North West", 6),
        ("Cork City South Central", 6),
        ("Cork City South East", 6),
        ("Cork City South West", 7),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO wards (name, seats) VALUES (?, ?)", wards
    )
    conn.commit()

    rows = conn.execute("SELECT id, name FROM wards").fetchall()
    return {name: wid for wid, name in rows}


def seed_issues(conn):
    """Insert issue taxonomy."""
    # Top-level issues
    top_issues = [
        "Housing",
        "Transport",
        "Environment",
        "Health",
        "Education",
        "Economy",
        "Community",
        "Planning",
        "Culture",
        "Public Safety",
    ]
    for name in top_issues:
        conn.execute("INSERT OR IGNORE INTO issues (name) VALUES (?)", (name,))
    conn.commit()

    # Get parent IDs
    rows = conn.execute("SELECT id, name FROM issues").fetchall()
    parent_map = {name: iid for iid, name in rows}

    # Sub-issues
    sub_issues = [
        ("Social Housing", "Housing"),
        ("Homelessness", "Housing"),
        ("Rental Market", "Housing"),
        ("Vacant Properties", "Housing"),
        ("Public Transport", "Transport"),
        ("Cycling Infrastructure", "Transport"),
        ("Road Safety", "Transport"),
        ("Parking", "Transport"),
        ("Climate Action", "Environment"),
        ("Waste Management", "Environment"),
        ("Water Quality", "Environment"),
        ("Flood Prevention", "Environment"),
        ("Primary Care", "Health"),
        ("Mental Health", "Health"),
        ("Regeneration", "Economy"),
        ("Small Business", "Economy"),
        ("Tourism", "Economy"),
        ("Community Centres", "Community"),
        ("Sports Facilities", "Community"),
        ("Anti-Social Behaviour", "Public Safety"),
        ("Zoning", "Planning"),
        ("Heritage", "Culture"),
        ("Arts Funding", "Culture"),
    ]
    for name, parent in sub_issues:
        conn.execute(
            "INSERT OR IGNORE INTO issues (name, parent_id) VALUES (?, ?)",
            (name, parent_map[parent]),
        )
    conn.commit()

    rows = conn.execute("SELECT id, name FROM issues").fetchall()
    return {name: iid for iid, name in rows}


def seed_councillors(conn, party_map, ward_map):
    """Insert all 31 Cork City councillors elected in 2024."""
    councillors = [
        # Cork City North East (6 seats)
        ("Kenneth", "O'Flynn", "II", "Cork City North East"),
        ("John", "Maher", "LAB", "Cork City North East"),
        ("Joe", "Kavanagh", "FG", "Cork City North East"),
        ("Margaret", "McDonnell", "FF", "Cork City North East"),
        ("Ted", "Tynan", "WP", "Cork City North East"),
        ("Oliver", "Moran", "GP", "Cork City North East"),
        # Cork City North West (6 seats)
        ("Tony", "Fitzgerald", "FF", "Cork City North West"),
        ("Damian", "Boylan", "FG", "Cork City North West"),
        ("John", "Sheehan", "FF", "Cork City North West"),
        ("Ken", "Collins", "SF", "Cork City North West"),
        ("Michelle", "Gould", "SF", "Cork City North West"),
        ("Brian", "McCarthy", "SOL-PBP", "Cork City North West"),
        # Cork City South Central (6 seats)
        ("Shane", "O'Callaghan", "FG", "Cork City South Central"),
        ("Seán", "Martin", "FF", "Cork City South Central"),
        ("Dan", "Boyle", "GP", "Cork City South Central"),
        ("Pádraig", "Rice", "SD", "Cork City South Central"),
        ("Fiona", "Kerins", "SF", "Cork City South Central"),
        ("Paudie", "Dineen", "IND", "Cork City South Central"),
        # Cork City South East (6 seats)
        ("Terry", "Shannon", "FF", "Cork City South East"),
        ("Kieran", "McCarthy", "IND", "Cork City South East"),
        ("Mary Rose", "Desmond", "FF", "Cork City South East"),
        ("Des", "Cahill", "FG", "Cork City South East"),
        ("Honoré", "Kamegni", "GP", "Cork City South East"),
        ("Peter", "Horgan", "LAB", "Cork City South East"),
        # Cork City South West (7 seats)
        ("Fergal", "Dennehy", "FF", "Cork City South West"),
        ("Colm", "Kelleher", "FF", "Cork City South West"),
        ("Garrett", "Kelleher", "FG", "Cork City South West"),
        ("Joe", "Lynch", "SF", "Cork City South West"),
        ("Laura", "Harmon", "LAB", "Cork City South West"),
        ("Terry", "Coleman", "FF", "Cork City South West"),
        ("Albert", "Deasy", "IND", "Cork City South West"),
    ]

    for first, last, party_short, ward_name in councillors:
        conn.execute(
            """INSERT OR IGNORE INTO councillors
               (first_name, last_name, party_id, ward_id)
               VALUES (?, ?, ?, ?)""",
            (first, last, party_map[party_short], ward_map[ward_name]),
        )
    conn.commit()

    rows = conn.execute(
        "SELECT id, first_name, last_name FROM councillors"
    ).fetchall()
    return {f"{first} {last}": cid for cid, first, last in rows}


def seed_sample_data(conn, councillor_map, issue_map):
    """Insert sample meetings, motions, votes, positions, and sources for demo."""
    random.seed(42)

    # --- Meetings ---
    meetings = [
        ("Full Council Meeting — January 2025", "2025-01-13", "Full Council"),
        ("Full Council Meeting — February 2025", "2025-02-10", "Full Council"),
        ("Full Council Meeting — March 2025", "2025-03-10", "Full Council"),
        ("Housing SPC Meeting — January 2025", "2025-01-20", "SPC"),
        ("Transport SPC Meeting — February 2025", "2025-02-17", "SPC"),
        ("Environment SPC Meeting — March 2025", "2025-03-17", "SPC"),
    ]
    for title, date, mtype in meetings:
        conn.execute(
            "INSERT INTO meetings (title, date, meeting_type) VALUES (?, ?, ?)",
            (title, date, mtype),
        )
    conn.commit()

    meeting_rows = conn.execute("SELECT id, title FROM meetings").fetchall()
    meeting_map = {title: mid for mid, title in meeting_rows}

    # --- Motions ---
    councillor_ids = list(councillor_map.values())
    motions_data = [
        (
            "Full Council Meeting — January 2025",
            "Motion to declare a housing emergency in Cork City",
            "Calls on Cork City Council to formally declare a housing emergency.",
            "Fiona Kerins",
            "Dan Boyle",
            "Passed",
            ["Housing", "Social Housing", "Homelessness"],
        ),
        (
            "Full Council Meeting — January 2025",
            "Motion to expand the 30km/h zone to all residential areas",
            "Proposes extending the 30km/h speed limit to cover all residential streets.",
            "Oliver Moran",
            "Laura Harmon",
            "Passed",
            ["Transport", "Road Safety"],
        ),
        (
            "Full Council Meeting — February 2025",
            "Motion to oppose the proposed Cork Northern Ring Road",
            "Objects to the proposed Northern Ring Road on environmental and community grounds.",
            "Dan Boyle",
            "Pádraig Rice",
            "Failed",
            ["Transport", "Environment", "Planning"],
        ),
        (
            "Full Council Meeting — February 2025",
            "Motion to increase funding for community centres",
            "Requests a 20% increase in annual funding for community centres across all wards.",
            "Tony Fitzgerald",
            "Terry Shannon",
            "Passed",
            ["Community", "Community Centres"],
        ),
        (
            "Full Council Meeting — March 2025",
            "Motion to implement a vacant property levy",
            "Proposes a levy on properties vacant for more than 12 months within the city boundary.",
            "Brian McCarthy",
            "Ted Tynan",
            "Deferred",
            ["Housing", "Vacant Properties", "Economy"],
        ),
        (
            "Housing SPC Meeting — January 2025",
            "Motion to fast-track social housing on council-owned land",
            "Directs the Housing Directorate to identify council-owned land suitable for social housing.",
            "Fiona Kerins",
            "Joe Lynch",
            "Passed",
            ["Housing", "Social Housing"],
        ),
        (
            "Transport SPC Meeting — February 2025",
            "Motion to pilot a protected cycle lane on the Western Road",
            "Proposes a 6-month trial of a protected cycle lane on Western Road.",
            "Oliver Moran",
            "Honoré Kamegni",
            "Passed",
            ["Transport", "Cycling Infrastructure"],
        ),
        (
            "Environment SPC Meeting — March 2025",
            "Motion to develop a climate action plan for Cork City",
            "Calls for a comprehensive climate action plan with binding interim targets.",
            "Dan Boyle",
            "Oliver Moran",
            "Passed",
            ["Environment", "Climate Action"],
        ),
    ]

    for meeting_title, title, desc, proposer, seconder, outcome, issues in motions_data:
        conn.execute(
            """INSERT INTO motions (meeting_id, title, description, proposed_by, seconded_by, outcome)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                meeting_map[meeting_title],
                title,
                desc,
                councillor_map.get(proposer),
                councillor_map.get(seconder),
                outcome,
            ),
        )
    conn.commit()

    motion_rows = conn.execute("SELECT id, title FROM motions").fetchall()
    motion_map = {title: mid for mid, title in motion_rows}

    # Link motions to issues
    for _, title, _, _, _, _, issues in motions_data:
        mid = motion_map[title]
        for issue_name in issues:
            if issue_name in issue_map:
                conn.execute(
                    "INSERT OR IGNORE INTO motion_issues (motion_id, issue_id) VALUES (?, ?)",
                    (mid, issue_map[issue_name]),
                )
    conn.commit()

    # --- Votes ---
    vote_options = ["For", "Against", "Abstained", "Absent"]

    for motion_title, mid in motion_map.items():
        for cname, cid in councillor_map.items():
            # Weight votes based on outcome to make data plausible
            motion_info = next(
                (m for m in motions_data if m[1] == motion_title), None
            )
            if motion_info:
                outcome = motion_info[5]
                if outcome == "Passed":
                    weights = [0.6, 0.2, 0.1, 0.1]
                elif outcome == "Failed":
                    weights = [0.3, 0.45, 0.15, 0.1]
                elif outcome == "Deferred":
                    weights = [0.3, 0.25, 0.35, 0.1]
                else:
                    weights = [0.25, 0.25, 0.25, 0.25]
            else:
                weights = [0.25, 0.25, 0.25, 0.25]

            vote = random.choices(vote_options, weights=weights, k=1)[0]
            conn.execute(
                "INSERT OR IGNORE INTO votes (councillor_id, motion_id, vote) VALUES (?, ?, ?)",
                (cid, mid, vote),
            )
    conn.commit()

    # --- Attendance ---
    for meeting_title, mid in meeting_map.items():
        for cid in councillor_ids:
            present = 1 if random.random() < 0.85 else 0
            conn.execute(
                "INSERT OR IGNORE INTO attendance (councillor_id, meeting_id, present) VALUES (?, ?, ?)",
                (cid, mid, present),
            )
    conn.commit()

    # --- Sample Positions ---
    positions_data = [
        (
            "Fiona Kerins",
            "Social Housing",
            "Support",
            "Strongly advocates for accelerated social housing construction on council-owned land.",
            "2025-01-15",
        ),
        (
            "Dan Boyle",
            "Climate Action",
            "Support",
            "Calls for binding climate targets at local authority level, citing Cork's flood vulnerability.",
            "2025-01-22",
        ),
        (
            "Kenneth O'Flynn",
            "Vacant Properties",
            "Support",
            "Supports a vacant property levy but argues the threshold should be 6 months, not 12.",
            "2025-02-05",
        ),
        (
            "Oliver Moran",
            "Cycling Infrastructure",
            "Support",
            "Champions protected cycle lanes as essential transport infrastructure, not an amenity.",
            "2025-02-12",
        ),
        (
            "Tony Fitzgerald",
            "Community Centres",
            "Support",
            "Argues community centres are the backbone of northside community life and need sustained investment.",
            "2025-01-28",
        ),
        (
            "Brian McCarthy",
            "Housing",
            "Support",
            "Calls for a complete ban on investment fund purchases of residential property in Cork.",
            "2025-02-20",
        ),
        (
            "Des Cahill",
            "Transport",
            "Mixed",
            "Supports road improvements but expressed concern about cycle lane impacts on parking for businesses.",
            "2025-03-01",
        ),
        (
            "Fergal Dennehy",
            "Regeneration",
            "Support",
            "Backs the Docklands regeneration plan and argues it will bring jobs to the southside.",
            "2025-03-05",
        ),
        (
            "Pádraig Rice",
            "Public Transport",
            "Support",
            "Advocates for the BusConnects Cork project with stronger community consultation.",
            "2025-02-25",
        ),
        (
            "Laura Harmon",
            "Mental Health",
            "Support",
            "Pushes for dedicated mental health services funding at council level, particularly for young people.",
            "2025-03-10",
        ),
    ]

    for cname, issue, stance, summary, date in positions_data:
        if cname in councillor_map and issue in issue_map:
            conn.execute(
                """INSERT INTO positions (councillor_id, issue_id, stance, summary, date)
                   VALUES (?, ?, ?, ?, ?)""",
                (councillor_map[cname], issue_map[issue], stance, summary, date),
            )
    conn.commit()

    # --- Sources ---
    sources_data = [
        (
            "https://www.echolive.ie/example/housing-emergency-2025",
            "Cork councillors declare housing emergency",
            "News",
            "2025-01-14",
        ),
        (
            "https://www.irishexaminer.com/example/30kmh-zone",
            "30km/h zones to expand across Cork city",
            "News",
            "2025-01-14",
        ),
        (
            None,
            "Minutes of Full Council Meeting — January 2025",
            "Minutes",
            "2025-01-13",
        ),
        (
            None,
            "Minutes of Full Council Meeting — February 2025",
            "Minutes",
            "2025-02-10",
        ),
        (
            None,
            "Minutes of Full Council Meeting — March 2025",
            "Minutes",
            "2025-03-10",
        ),
    ]

    for url, title, stype, date in sources_data:
        conn.execute(
            "INSERT INTO sources (url, title, source_type, date) VALUES (?, ?, ?, ?)",
            (url, title, stype, date),
        )
    conn.commit()


def main():
    """Run the full seed process."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")

    conn = init_db()
    print("Schema applied.")

    party_map = seed_parties(conn)
    print(f"Parties seeded: {len(party_map)}")

    ward_map = seed_wards(conn)
    print(f"Wards seeded: {len(ward_map)}")

    issue_map = seed_issues(conn)
    print(f"Issues seeded: {len(issue_map)}")

    councillor_map = seed_councillors(conn, party_map, ward_map)
    print(f"Councillors seeded: {len(councillor_map)}")

    seed_sample_data(conn, councillor_map, issue_map)
    print("Sample motions, votes, positions, and sources seeded.")

    conn.close()
    print(f"\nDatabase ready at: {DB_PATH}")


if __name__ == "__main__":
    main()
