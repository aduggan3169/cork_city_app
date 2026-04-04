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
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "schema.sql")
DB_PATH = os.environ.get(
    "CORK_DB_PATH",
    os.path.join(SCRIPT_DIR, "cork_civic_tracker.db"),
)


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
        # --- Additional positions for richer policy stance cards ---
        (
            "Joe Kavanagh",
            "Social Housing",
            "Mixed",
            "Supports housing development in principle but concerned that emergency declarations and public-only approaches could deter private sector investment.",
            "2025-01-20",
        ),
        (
            "Shane O'Callaghan",
            "Vacant Properties",
            "Oppose",
            "Argues the proposed vacant property levy is premature and could penalise owners undertaking genuine renovation work.",
            "2025-03-12",
        ),
        (
            "Damian Boylan",
            "Climate Action",
            "Mixed",
            "Acknowledges climate concerns but prioritises economic growth and infrastructure investment, including the Northern Ring Road.",
            "2025-03-15",
        ),
        (
            "Garrett Kelleher",
            "Transport",
            "Support",
            "Advocates for major road infrastructure including the Northern Ring Road to improve northside connectivity and economic development.",
            "2025-02-15",
        ),
        (
            "Margaret McDonnell",
            "Climate Action",
            "Neutral",
            "Supports climate action in principle but consistently questions cost implications and whether adequate central government funding will follow.",
            "2025-03-10",
        ),
        (
            "Fiona Kerins",
            "Homelessness",
            "Support",
            "Calls for emergency accommodation capacity to be doubled and for a Housing First approach to be adopted city-wide.",
            "2025-02-18",
        ),
        (
            "Oliver Moran",
            "Climate Action",
            "Support",
            "Frames climate action as inseparable from transport policy, arguing Cork must invest in cycling and public transport over road expansion.",
            "2025-03-08",
        ),
        (
            "Brian McCarthy",
            "Vacant Properties",
            "Support",
            "Argues the vacant property levy threshold should be 6 months, not 12, and revenue should be ring-fenced for social housing.",
            "2025-03-05",
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

    # Build position lookup: (councillor_name, issue_name) → position_id
    pos_rows = conn.execute("""
        SELECT p.id, c.first_name || ' ' || c.last_name, i.name
        FROM positions p
        JOIN councillors c ON p.councillor_id = c.id
        JOIN issues i ON p.issue_id = i.id
    """).fetchall()
    pos_map = {(name, issue): pid for pid, name, issue in pos_rows}

    # --- Sources ---
    sources_data = [
        # News articles — plausible Cork local media URLs
        (
            "https://www.echolive.ie/corknews/cork-councillors-declare-housing-emergency-2025",
            "Cork councillors declare housing emergency",
            "News",
            "2025-01-14",
        ),
        (
            "https://www.irishexaminer.com/news/munster/cork-30kmh-zones-to-expand-across-city",
            "30km/h zones to expand across Cork city",
            "News",
            "2025-01-14",
        ),
        (
            "https://www.echolive.ie/corknews/kerins-calls-for-housing-first-approach-in-cork",
            "SF councillor calls for Housing First approach in Cork",
            "News",
            "2025-02-19",
        ),
        (
            "https://www.irishexaminer.com/news/munster/cork-ring-road-debate-splits-council",
            "Cork Northern Ring Road debate splits council chamber",
            "News",
            "2025-02-11",
        ),
        (
            "https://www.echolive.ie/corknews/vacant-property-levy-cork-council-debate",
            "Vacant property levy debate heats up at Cork City Council",
            "News",
            "2025-03-11",
        ),
        (
            "https://www.echolive.ie/corknews/moran-champions-western-road-cycle-lane",
            "Green councillor champions Western Road cycle lane pilot",
            "News",
            "2025-02-18",
        ),
        (
            "https://www.irishexaminer.com/news/munster/cork-climate-action-plan-binding-targets-proposed",
            "Cork councillors push for binding climate targets",
            "News",
            "2025-03-11",
        ),
        (
            "https://www.echolive.ie/corknews/community-centres-funding-boost-cork-northside",
            "Northside community centres in line for 20% funding boost",
            "News",
            "2025-02-11",
        ),
        (
            "https://www.corkbeo.ie/news/local-news/oflynn-backs-vacant-levy-shorter-threshold",
            "O'Flynn backs vacant levy but wants shorter threshold",
            "News",
            "2025-02-06",
        ),
        (
            "https://www.irishexaminer.com/news/munster/cork-councillor-cahill-parking-cycle-lane-concerns",
            "Cahill raises parking concerns over cycle lane plans",
            "News",
            "2025-03-02",
        ),
        (
            "https://www.echolive.ie/corknews/harmon-pushes-for-mental-health-funding-cork",
            "Labour councillor pushes for youth mental health funding",
            "News",
            "2025-03-11",
        ),
        (
            "https://www.irishexaminer.com/news/munster/boylan-climate-versus-economy-cork-council",
            "Boylan warns against prioritising climate over economic growth",
            "News",
            "2025-03-16",
        ),
        (
            "https://www.echolive.ie/corknews/mccarthy-ban-investment-fund-purchases-cork",
            "PBP councillor calls for ban on fund purchases of Cork homes",
            "News",
            "2025-02-21",
        ),
        # Council minutes
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
        # Press releases
        (
            "https://www.greenparty.ie/cork-climate-action-plan-proposal",
            "Green Party Cork: Climate Action Plan Proposal",
            "Press Release",
            "2025-03-09",
        ),
        (
            "https://www.sinnfein.ie/cork-housing-emergency-motion",
            "Sinn Féin Cork: Housing Emergency Motion",
            "Press Release",
            "2025-01-12",
        ),
    ]

    for url, title, stype, date in sources_data:
        conn.execute(
            "INSERT INTO sources (url, title, source_type, date) VALUES (?, ?, ?, ?)",
            (url, title, stype, date),
        )
    conn.commit()

    # Build full source lookup
    source_rows = conn.execute("SELECT id, title FROM sources").fetchall()
    source_map = {title: sid for sid, title in source_rows}

    # --- Position ↔ Source links ---
    # Maps (councillor_name, issue_name) → list of source titles
    position_source_links = [
        # Fiona Kerins — Social Housing
        ("Fiona Kerins", "Social Housing", [
            "Cork councillors declare housing emergency",
            "Sinn Féin Cork: Housing Emergency Motion",
            "Minutes of Full Council Meeting — January 2025",
        ]),
        # Fiona Kerins — Homelessness
        ("Fiona Kerins", "Homelessness", [
            "SF councillor calls for Housing First approach in Cork",
        ]),
        # Dan Boyle — Climate Action
        ("Dan Boyle", "Climate Action", [
            "Cork councillors push for binding climate targets",
            "Green Party Cork: Climate Action Plan Proposal",
            "Minutes of Full Council Meeting — March 2025",
        ]),
        # Kenneth O'Flynn — Vacant Properties
        ("Kenneth O'Flynn", "Vacant Properties", [
            "O'Flynn backs vacant levy but wants shorter threshold",
        ]),
        # Oliver Moran — Cycling Infrastructure
        ("Oliver Moran", "Cycling Infrastructure", [
            "Green councillor champions Western Road cycle lane pilot",
            "30km/h zones to expand across Cork city",
        ]),
        # Oliver Moran — Climate Action
        ("Oliver Moran", "Climate Action", [
            "Cork councillors push for binding climate targets",
            "Green Party Cork: Climate Action Plan Proposal",
        ]),
        # Tony Fitzgerald — Community Centres
        ("Tony Fitzgerald", "Community Centres", [
            "Northside community centres in line for 20% funding boost",
            "Minutes of Full Council Meeting — February 2025",
        ]),
        # Brian McCarthy — Housing
        ("Brian McCarthy", "Housing", [
            "PBP councillor calls for ban on fund purchases of Cork homes",
            "Cork councillors declare housing emergency",
        ]),
        # Brian McCarthy — Vacant Properties
        ("Brian McCarthy", "Vacant Properties", [
            "Vacant property levy debate heats up at Cork City Council",
            "Minutes of Full Council Meeting — March 2025",
        ]),
        # Des Cahill — Transport (Mixed)
        ("Des Cahill", "Transport", [
            "Cahill raises parking concerns over cycle lane plans",
            "Cork Northern Ring Road debate splits council chamber",
        ]),
        # Laura Harmon — Mental Health
        ("Laura Harmon", "Mental Health", [
            "Labour councillor pushes for youth mental health funding",
        ]),
        # Shane O'Callaghan — Vacant Properties (Oppose)
        ("Shane O'Callaghan", "Vacant Properties", [
            "Vacant property levy debate heats up at Cork City Council",
            "Minutes of Full Council Meeting — March 2025",
        ]),
        # Damian Boylan — Climate Action (Mixed)
        ("Damian Boylan", "Climate Action", [
            "Boylan warns against prioritising climate over economic growth",
            "Cork Northern Ring Road debate splits council chamber",
        ]),
        # Garrett Kelleher — Transport
        ("Garrett Kelleher", "Transport", [
            "Cork Northern Ring Road debate splits council chamber",
        ]),
        # Margaret McDonnell — Climate Action (Neutral)
        ("Margaret McDonnell", "Climate Action", [
            "Cork councillors push for binding climate targets",
            "Minutes of Full Council Meeting — March 2025",
        ]),
    ]

    for cname, issue, src_titles in position_source_links:
        pos_key = (cname, issue)
        if pos_key in pos_map:
            pid = pos_map[pos_key]
            for src_title in src_titles:
                if src_title in source_map:
                    conn.execute(
                        "INSERT OR IGNORE INTO position_sources (position_id, source_id) VALUES (?, ?)",
                        (pid, source_map[src_title]),
                    )
    conn.commit()

    # --- Motion Statements (councillor speaking points from minutes) ---
    # Motion 1: Housing emergency declaration
    m1_title = "Motion to declare a housing emergency in Cork City"
    m1_id = motion_map[m1_title]
    m1_source = source_map.get("Minutes of Full Council Meeting — January 2025")

    statements_data = [
        # Motion 1: Housing emergency
        (councillor_map["Fiona Kerins"], m1_id,
         "Argued that Cork's housing waiting list has grown by 40% in three years and that a formal declaration would unlock emergency planning powers.",
         "We cannot continue to treat this as business as usual when families are sleeping in cars in this city.",
         "Supportive", m1_source),
        (councillor_map["Dan Boyle"], m1_id,
         "Supported the motion but urged that the declaration be tied to specific measurable targets and a 12-month review.",
         None, "Supportive", m1_source),
        (councillor_map["Brian McCarthy"], m1_id,
         "Called for the declaration to include a moratorium on investment fund purchases of residential property within the city boundary.",
         "Declaring an emergency means nothing if we don't address who is buying up the housing stock.",
         "Supportive", m1_source),
        (councillor_map["Joe Kavanagh"], m1_id,
         "Expressed concern that a formal emergency declaration could deter private investment in housing construction.",
         None, "Critical", m1_source),
        (councillor_map["Tony Fitzgerald"], m1_id,
         "Supported the spirit of the motion but questioned whether the council has the legal powers to enforce the measures implied.",
         None, "Neutral", m1_source),
        (councillor_map["Ted Tynan"], m1_id,
         "Backed the motion and called for all council-owned land to be ring-fenced exclusively for social and affordable housing.",
         None, "Supportive", m1_source),

        # Motion 2: 30km/h zone expansion
        (councillor_map["Oliver Moran"], motion_map["Motion to expand the 30km/h zone to all residential areas"],
         "Presented data from the existing 30km/h pilot showing a 23% reduction in pedestrian injuries and argued for city-wide rollout.",
         "The evidence is clear — slower speeds save lives, and residential streets should prioritise people over traffic throughput.",
         "Supportive", m1_source),
        (councillor_map["Laura Harmon"], motion_map["Motion to expand the 30km/h zone to all residential areas"],
         "Spoke about the impact on school safety zones and the need for complementary traffic calming infrastructure.",
         None, "Supportive", m1_source),
        (councillor_map["Des Cahill"], motion_map["Motion to expand the 30km/h zone to all residential areas"],
         "Raised concerns from business owners on the southside about delivery access and the impact on commercial traffic flow.",
         None, "Critical", m1_source),
        (councillor_map["Kenneth O'Flynn"], motion_map["Motion to expand the 30km/h zone to all residential areas"],
         "Suggested a phased approach starting with areas around schools and parks rather than a blanket city-wide change.",
         None, "Neutral", m1_source),

        # Motion 3: Northern Ring Road opposition
        (councillor_map["Dan Boyle"], motion_map["Motion to oppose the proposed Cork Northern Ring Road"],
         "Argued the ring road would induce demand, increase car dependency, and undermine Cork's climate commitments.",
         "You cannot build your way out of congestion. Every new road fills to capacity within a decade.",
         "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Pádraig Rice"], motion_map["Motion to oppose the proposed Cork Northern Ring Road"],
         "Supported opposition and called for the allocated funding to be redirected to BusConnects Cork and light rail feasibility.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Fergal Dennehy"], motion_map["Motion to oppose the proposed Cork Northern Ring Road"],
         "Opposed the motion, arguing the ring road is essential for economic development on the northside and would relieve pressure on the Dunkettle interchange.",
         None, "Critical", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Garrett Kelleher"], motion_map["Motion to oppose the proposed Cork Northern Ring Road"],
         "Argued the ring road would bring jobs and connectivity to underserved areas and that opposing it was short-sighted.",
         None, "Critical", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Damian Boylan"], motion_map["Motion to oppose the proposed Cork Northern Ring Road"],
         "Noted that the ring road has been part of Cork's transport strategy for decades and should not be abandoned without a viable alternative.",
         None, "Critical", source_map.get("Minutes of Full Council Meeting — February 2025")),

        # Motion 4: Community centres funding
        (councillor_map["Tony Fitzgerald"], motion_map["Motion to increase funding for community centres"],
         "Made an impassioned case for northside community centres as the primary social infrastructure for disadvantaged communities.",
         "These centres are where kids do their homework, where elderly people have their only social contact of the week. Twenty percent more funding is the minimum.",
         "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Terry Shannon"], motion_map["Motion to increase funding for community centres"],
         "Seconded the motion and highlighted the disparity in facilities between northside and southside wards.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Michelle Gould"], motion_map["Motion to increase funding for community centres"],
         "Spoke about the role of community centres in addressing anti-social behaviour and providing alternatives for young people.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),

        # Motion 5: Vacant property levy
        (councillor_map["Brian McCarthy"], motion_map["Motion to implement a vacant property levy"],
         "Proposed the levy as a tool to bring vacant properties back into use and argued the 12-month threshold was too generous.",
         "There are over 800 vacant residential properties in this city while people sleep rough. A levy is the least we can do.",
         "Supportive", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Ted Tynan"], motion_map["Motion to implement a vacant property levy"],
         "Supported the levy and called for the revenue to be ring-fenced for social housing acquisition.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Colm Kelleher"], motion_map["Motion to implement a vacant property levy"],
         "Requested deferral to allow for a full economic impact assessment and consultation with property owners.",
         None, "Procedural", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Shane O'Callaghan"], motion_map["Motion to implement a vacant property levy"],
         "Argued the levy could penalise owners of properties undergoing renovation and called for exemptions to be clearly defined.",
         None, "Critical", source_map.get("Minutes of Full Council Meeting — March 2025")),

        # Motion 6: Fast-track social housing
        (councillor_map["Fiona Kerins"], motion_map["Motion to fast-track social housing on council-owned land"],
         "Identified three specific council-owned sites suitable for immediate development and called for a 6-month planning fast-track.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — January 2025")),
        (councillor_map["Joe Lynch"], motion_map["Motion to fast-track social housing on council-owned land"],
         "Supported the motion and called for local labour clauses in all social housing construction contracts.",
         "If we're building homes for the community, the community should be building them.",
         "Supportive", source_map.get("Minutes of Full Council Meeting — January 2025")),
        (councillor_map["Kieran McCarthy"], motion_map["Motion to fast-track social housing on council-owned land"],
         "Expressed support but cautioned against fast-tracking at the expense of proper heritage and environmental assessment.",
         None, "Neutral", source_map.get("Minutes of Full Council Meeting — January 2025")),

        # Motion 7: Western Road cycle lane
        (councillor_map["Oliver Moran"], motion_map["Motion to pilot a protected cycle lane on the Western Road"],
         "Presented the case for Western Road as a key commuter corridor with high cycling potential and poor existing infrastructure.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Honoré Kamegni"], motion_map["Motion to pilot a protected cycle lane on the Western Road"],
         "Highlighted safety data showing Western Road as one of the most dangerous routes for cyclists in the city.",
         "Protected infrastructure is not a luxury — it is the baseline requirement for safe cycling.",
         "Supportive", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Des Cahill"], motion_map["Motion to pilot a protected cycle lane on the Western Road"],
         "Raised concerns about the loss of on-street parking for businesses along Western Road and its impact on trade.",
         None, "Critical", source_map.get("Minutes of Full Council Meeting — February 2025")),
        (councillor_map["Mary Rose Desmond"], motion_map["Motion to pilot a protected cycle lane on the Western Road"],
         "Asked whether a traffic impact study had been conducted and whether alternative routes had been considered.",
         None, "Neutral", source_map.get("Minutes of Full Council Meeting — February 2025")),

        # Motion 8: Climate action plan
        (councillor_map["Dan Boyle"], motion_map["Motion to develop a climate action plan for Cork City"],
         "Led the debate arguing for binding interim targets aligned with national 2030 commitments and specific sectoral goals for transport, buildings, and waste.",
         "A plan without targets is just a wish list. Cork needs binding interim milestones.",
         "Supportive", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Oliver Moran"], motion_map["Motion to develop a climate action plan for Cork City"],
         "Called for the plan to include a dedicated transport decarbonisation strategy and investment in cycling and public transport.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Pádraig Rice"], motion_map["Motion to develop a climate action plan for Cork City"],
         "Emphasised the need for genuine public consultation and warned against a plan developed in isolation by council officials.",
         None, "Supportive", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Margaret McDonnell"], motion_map["Motion to develop a climate action plan for Cork City"],
         "Expressed support in principle but asked about the cost implications and whether additional central government funding would be sought.",
         None, "Neutral", source_map.get("Minutes of Full Council Meeting — March 2025")),
        (councillor_map["Kenneth O'Flynn"], motion_map["Motion to develop a climate action plan for Cork City"],
         "Argued that any climate plan must balance environmental goals with the economic needs of local businesses and avoid excessive regulation.",
         None, "Critical", source_map.get("Minutes of Full Council Meeting — March 2025")),
    ]

    for cid, mid, summary, quote, sentiment, sid in statements_data:
        conn.execute(
            """INSERT INTO motion_statements
               (councillor_id, motion_id, summary, quote, sentiment, source_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cid, mid, summary, quote, sentiment, sid),
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
