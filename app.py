"""
Cork Civic Tracker — Streamlit App
Phase 1: Councillor Tracker
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Cork Civic Tracker",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(APP_DIR, "db")

# ---------------------------------------------------------------------------
# Debug mode — set to True to show diagnostics panel, False for production
# ---------------------------------------------------------------------------
DEBUG = True

# ---------------------------------------------------------------------------
# Database bootstrap — handles both local and Streamlit Cloud
# ---------------------------------------------------------------------------

# Required tables — add new table names here when extending the schema
REQUIRED_TABLES = ["councillors", "motions", "votes", "motion_statements", "declarations"]

# Locally: DB lives in db/. On Streamlit Cloud (or any read-only fs): use /tmp/.
if os.access(DB_DIR, os.W_OK):
    DB_PATH = os.path.join(DB_DIR, "cork_civic_tracker.db")
else:
    DB_PATH = os.path.join("/tmp", "cork_civic_tracker.db")

_debug_log = []


def _log(msg):
    _debug_log.append(msg)


def _db_check():
    """Check which required tables exist. Returns (all_ok, details)."""
    if not os.path.exists(DB_PATH):
        return False, {"status": "DB file does not exist"}
    if os.path.getsize(DB_PATH) == 0:
        return False, {"status": "DB file is empty (0 bytes)"}
    try:
        conn = sqlite3.connect(DB_PATH)
        details = {"status": "file exists", "size": os.path.getsize(DB_PATH)}
        missing = []
        for table in REQUIRED_TABLES:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cursor.fetchone() is None:
                missing.append(table)
        conn.close()
        details["missing_tables"] = missing
        return len(missing) == 0, details
    except Exception as e:
        return False, {"status": f"error: {e}"}


_log(f"DB_PATH: {DB_PATH}")
_log(f"DB_DIR writable: {os.access(DB_DIR, os.W_OK)}")

all_ok, details = _db_check()
_log(f"DB check: ok={all_ok}, {details}")

if not all_ok:
    # Nuke any stale DB and all associated WAL/SHM files
    for suffix in ["", "-journal", "-wal", "-shm"]:
        path = DB_PATH + suffix
        if os.path.exists(path):
            os.remove(path)
            _log(f"Removed: {path}")

    import sys
    os.environ["CORK_DB_PATH"] = DB_PATH
    if DB_DIR not in sys.path:
        sys.path.insert(0, DB_DIR)
    import seed as _seed
    _seed.DB_PATH = DB_PATH
    _seed.SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")
    try:
        _seed.main()
        _log("Seed completed OK")
    except Exception as e:
        _log(f"Seed FAILED: {type(e).__name__}: {e}")

    # Verify
    all_ok2, details2 = _db_check()
    _log(f"Post-seed check: ok={all_ok2}, {details2}")
else:
    _log("DB is up to date — no re-seed needed")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_connection():
    """Return a SQLite connection. No caching — avoids stale connection issues."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=None):
    """Run a query and return a DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params or [])


# ---------------------------------------------------------------------------
# Debug panel (toggle with DEBUG flag above)
# ---------------------------------------------------------------------------
if DEBUG:
    with st.sidebar.expander("Debug", expanded=False):
        for msg in _debug_log:
            st.text(msg)



# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_councillors():
    return query("""
        SELECT c.id, c.first_name, c.last_name,
               c.first_name || ' ' || c.last_name AS full_name,
               p.name AS party, p.short_name AS party_short, p.colour AS party_colour,
               w.name AS ward, c.active, c.photo_url
        FROM councillors c
        JOIN parties p ON c.party_id = p.id
        JOIN wards w ON c.ward_id = w.id
        ORDER BY c.last_name, c.first_name
    """)


@st.cache_data(ttl=300)
def load_votes():
    return query("""
        SELECT v.id, v.councillor_id, v.motion_id, v.vote,
               c.first_name || ' ' || c.last_name AS councillor_name,
               p.short_name AS party_short, p.colour AS party_colour,
               m.title AS motion_title, m.outcome,
               mt.date AS meeting_date, mt.meeting_type
        FROM votes v
        JOIN councillors c ON v.councillor_id = c.id
        JOIN parties p ON c.party_id = p.id
        JOIN motions m ON v.motion_id = m.id
        JOIN meetings mt ON m.meeting_id = mt.id
    """)


@st.cache_data(ttl=300)
def load_motions():
    return query("""
        SELECT m.id, m.title, m.description, m.outcome,
               mt.date AS meeting_date, mt.title AS meeting_title,
               mt.meeting_type,
               cp.first_name || ' ' || cp.last_name AS proposed_by,
               cs.first_name || ' ' || cs.last_name AS seconded_by
        FROM motions m
        JOIN meetings mt ON m.meeting_id = mt.id
        LEFT JOIN councillors cp ON m.proposed_by = cp.id
        LEFT JOIN councillors cs ON m.seconded_by = cs.id
        ORDER BY mt.date DESC
    """)


@st.cache_data(ttl=300)
def load_attendance():
    return query("""
        SELECT a.councillor_id, a.meeting_id, a.present,
               c.first_name || ' ' || c.last_name AS councillor_name,
               p.short_name AS party_short,
               mt.title AS meeting_title, mt.date AS meeting_date
        FROM attendance a
        JOIN councillors c ON a.councillor_id = c.id
        JOIN parties p ON c.party_id = p.id
        JOIN meetings mt ON a.meeting_id = mt.id
    """)


@st.cache_data(ttl=300)
def load_positions():
    return query("""
        SELECT pos.id, pos.councillor_id, pos.stance, pos.summary, pos.quote, pos.date,
               c.first_name || ' ' || c.last_name AS councillor_name,
               p.short_name AS party_short,
               i.name AS issue_name
        FROM positions pos
        JOIN councillors c ON pos.councillor_id = c.id
        JOIN parties p ON c.party_id = p.id
        JOIN issues i ON pos.issue_id = i.id
        ORDER BY pos.date DESC
    """)


@st.cache_data(ttl=300)
def load_motion_issues():
    return query("""
        SELECT mi.motion_id, i.name AS issue_name
        FROM motion_issues mi
        JOIN issues i ON mi.issue_id = i.id
    """)


@st.cache_data(ttl=300)
def load_issues():
    return query("SELECT id, name, parent_id FROM issues")


@st.cache_data(ttl=300)
def load_position_sources():
    """Load sources linked to positions via position_sources join table."""
    return query("""
        SELECT ps.position_id, s.title, s.url, s.source_type, s.date
        FROM position_sources ps
        JOIN sources s ON ps.source_id = s.id
        ORDER BY s.date DESC
    """)


@st.cache_data(ttl=300)
def load_declarations():
    """Load councillor declarations with category names."""
    return query("""
        SELECT d.id, d.councillor_id, d.description, d.date_declared,
               d.date_withdrawn, d.notes,
               dc.name AS category
        FROM declarations d
        JOIN declaration_categories dc ON d.category_id = dc.id
        ORDER BY dc.name, d.date_declared DESC
    """)


@st.cache_data(ttl=300)
def load_motion_statements():
    return query("""
        SELECT ms.id, ms.councillor_id, ms.motion_id,
               ms.summary, ms.quote, ms.sentiment,
               c.first_name || ' ' || c.last_name AS councillor_name,
               p.name AS party, p.short_name AS party_short, p.colour AS party_colour,
               w.name AS ward
        FROM motion_statements ms
        JOIN councillors c ON ms.councillor_id = c.id
        JOIN parties p ON c.party_id = p.id
        JOIN wards w ON c.ward_id = w.id
        ORDER BY p.name, c.last_name
    """)


# ---------------------------------------------------------------------------
# Party colour map
# ---------------------------------------------------------------------------
def get_party_colours(df_councillors):
    """Build a dict mapping party short names to hex colours."""
    return dict(
        zip(df_councillors["party_short"], df_councillors["party_colour"])
    )


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
def sidebar():
    st.sidebar.title("Cork Civic Tracker")
    st.sidebar.caption("Phase 1 — Councillor Tracker")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Councillors", "Motions & Votes"],
        label_visibility="collapsed",
    )
    return page


# ---------------------------------------------------------------------------
# PAGE: Dashboard
# ---------------------------------------------------------------------------
def page_dashboard():
    st.title("Council Overview")
    st.caption("Cork City Council — 31 seats, elected June 2024")

    df_c = load_councillors()
    df_v = load_votes()
    df_a = load_attendance()
    df_m = load_motions()
    colours = get_party_colours(df_c)

    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Councillors", len(df_c))
    col2.metric("Parties", df_c["party_short"].nunique())
    col3.metric("Motions Recorded", len(df_m))
    avg_attendance = df_a["present"].mean() * 100
    col4.metric("Avg Attendance", f"{avg_attendance:.0f}%")

    st.markdown("---")

    # --- Row 1: Party breakdown + Outcome pie ---
    left, right = st.columns(2)

    with left:
        st.subheader("Seats by Party")
        party_counts = (
            df_c.groupby(["party_short", "party_colour"])
            .size()
            .reset_index(name="seats")
            .sort_values("seats", ascending=True)
        )
        fig = px.bar(
            party_counts,
            x="seats",
            y="party_short",
            orientation="h",
            color="party_short",
            color_discrete_map=colours,
            labels={"party_short": "", "seats": "Seats"},
        )
        fig.update_layout(showlegend=False, height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Motion Outcomes")
        outcome_counts = df_m["outcome"].value_counts().reset_index()
        outcome_counts.columns = ["outcome", "count"]
        outcome_colours = {
            "Passed": "#4CAF50",
            "Failed": "#F44336",
            "Deferred": "#FF9800",
            "Withdrawn": "#9E9E9E",
            "Amended": "#2196F3",
        }
        fig2 = px.pie(
            outcome_counts,
            names="outcome",
            values="count",
            color="outcome",
            color_discrete_map=outcome_colours,
        )
        fig2.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # --- Row 2: Voting patterns + Attendance ---
    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Voting Patterns by Party")
        vote_party = (
            df_v.groupby(["party_short", "vote"])
            .size()
            .reset_index(name="count")
        )
        vote_colours = {
            "For": "#4CAF50",
            "Against": "#F44336",
            "Abstained": "#FF9800",
            "Absent": "#9E9E9E",
        }
        fig3 = px.bar(
            vote_party,
            x="party_short",
            y="count",
            color="vote",
            color_discrete_map=vote_colours,
            barmode="group",
            labels={"party_short": "Party", "count": "Votes", "vote": ""},
        )
        fig3.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    with right2:
        st.subheader("Attendance by Ward")
        att_ward = (
            df_a.merge(df_c[["id", "ward"]], left_on="councillor_id", right_on="id")
            .groupby("ward")["present"]
            .mean()
            .reset_index()
        )
        att_ward.columns = ["ward", "attendance_rate"]
        att_ward["attendance_pct"] = att_ward["attendance_rate"] * 100
        att_ward = att_ward.sort_values("attendance_pct", ascending=True)

        fig4 = px.bar(
            att_ward,
            x="attendance_pct",
            y="ward",
            orientation="h",
            labels={"ward": "", "attendance_pct": "Attendance %"},
            color_discrete_sequence=["#2196F3"],
        )
        fig4.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")

    # --- Row 3: Bottom 5 attendance by councillor + Top 5 dissenting councillors ---
    left3, right3 = st.columns(2)

    with left3:
        st.subheader("Lowest Attendance (by Councillor)")
        # Merge attendance with councillor info via councillor_id
        att_merged = df_a[["councillor_id", "present"]].merge(
            df_c[["id", "full_name", "party_short", "party_colour"]].rename(
                columns={"id": "councillor_id"}
            ),
            on="councillor_id",
        )
        att_councillor = (
            att_merged
            .groupby(["full_name", "party_short", "party_colour"])["present"]
            .mean()
            .reset_index()
        )
        att_councillor.columns = ["name", "party", "colour", "attendance_rate"]
        att_councillor["attendance_pct"] = att_councillor["attendance_rate"] * 100
        bottom5 = att_councillor.nsmallest(5, "attendance_pct").sort_values(
            "attendance_pct", ascending=False
        )
        bottom5["label"] = bottom5["name"] + " (" + bottom5["party"] + ")"

        fig5 = px.bar(
            bottom5,
            x="attendance_pct",
            y="label",
            orientation="h",
            color="party",
            color_discrete_map=colours,
            labels={"label": "", "attendance_pct": "Attendance %"},
        )
        fig5.update_layout(
            showlegend=False, height=350, margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig5, use_container_width=True)

    with right3:
        st.subheader("Most Dissenting (Against + Abstained)")
        dissent = (
            df_v[df_v["vote"].isin(["Against", "Abstained"])][["councillor_id", "vote"]]
            .merge(
                df_c[["id", "full_name", "party_short", "party_colour"]].rename(
                    columns={"id": "councillor_id"}
                ),
                on="councillor_id",
            )
        )
        dissent_counts = (
            dissent.groupby(["full_name", "party_short", "party_colour", "vote"])
            .size()
            .reset_index(name="count")
        )

        # Get top 5 by total dissenting votes
        totals = (
            dissent_counts.groupby(["full_name", "party_short", "party_colour"])["count"]
            .sum()
            .reset_index(name="total")
            .nlargest(5, "total")
        )
        top5_names = totals["full_name"].tolist()
        top5_data = dissent_counts[dissent_counts["full_name"].isin(top5_names)]
        top5_data = top5_data.merge(totals[["full_name", "total"]], on="full_name")
        top5_data["label"] = top5_data["full_name"] + " (" + top5_data["party_short"] + ")"
        top5_data = top5_data.sort_values("total", ascending=True)

        vote_colours = {"Against": "#F44336", "Abstained": "#FF9800"}
        fig6 = px.bar(
            top5_data,
            x="count",
            y="label",
            orientation="h",
            color="vote",
            color_discrete_map=vote_colours,
            barmode="stack",
            labels={"label": "", "count": "Votes", "vote": ""},
        )
        fig6.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig6, use_container_width=True)


# ---------------------------------------------------------------------------
# POLICY STANCE HELPERS
# ---------------------------------------------------------------------------

def _get_issue_family(issue_name, df_issues):
    """Get an issue plus its parent and children for broad motion matching."""
    issue_row = df_issues[df_issues["name"] == issue_name]
    if len(issue_row) == 0:
        return {issue_name}

    family = {issue_name}
    issue_id = issue_row.iloc[0]["id"]

    # Add children (sub-issues)
    children = df_issues[df_issues["parent_id"] == issue_id]["name"].tolist()
    family.update(children)

    # Add parent (if this is a sub-issue)
    parent_id = issue_row.iloc[0]["parent_id"]
    if pd.notna(parent_id):
        parent = df_issues[df_issues["id"] == parent_id]
        if len(parent) > 0:
            family.add(parent.iloc[0]["name"])

    return family


def _compute_alignment(stance, vote_counts, total):
    """Compute alignment between a stated position and voting record."""
    if total == 0:
        return "No related votes recorded", "⚪", "#9E9E9E"

    for_pct = vote_counts.get("For", 0) / total * 100
    against_pct = vote_counts.get("Against", 0) / total * 100

    if stance == "Support":
        match_pct = for_pct
    elif stance == "Oppose":
        match_pct = against_pct
    else:
        return "Mixed/neutral stance", "🟡", "#FF9800"

    if match_pct >= 75:
        return "Votes strongly align", "✅", "#4CAF50"
    elif match_pct >= 50:
        return "Votes mostly align", "✅", "#8BC34A"
    elif match_pct >= 25:
        return "Some tension between votes and position", "⚠️", "#FF9800"
    else:
        return "Votes contradict stated position", "❌", "#F44336"


STANCE_ICONS = {"Support": "🟢", "Oppose": "🔴", "Neutral": "⚪", "Mixed": "🟡"}


SOURCE_TYPE_ICONS = {
    "News": "📰",
    "Minutes": "📋",
    "Press Release": "📢",
    "Social Media": "💬",
    "Interview": "🎙️",
    "Other": "📄",
}


def _render_policy_stance_cards(cid, df_pos, df_v, df_mi, df_issues, df_psrc):
    """Render policy stance summary cards for a councillor."""
    c_positions = df_pos[df_pos["councillor_id"] == cid]

    if len(c_positions) == 0:
        st.info("No stated positions recorded for this councillor.")
        return

    c_votes = df_v[df_v["councillor_id"] == cid]

    for _, pos in c_positions.iterrows():
        issue_name = pos["issue_name"]
        issue_family = _get_issue_family(issue_name, df_issues)

        # Find motions tagged with any issue in the family
        related_motion_ids = df_mi[
            df_mi["issue_name"].isin(issue_family)
        ]["motion_id"].unique()

        # This councillor's votes on those motions
        issue_votes = c_votes[c_votes["motion_id"].isin(related_motion_ids)]
        total = len(issue_votes)
        vote_counts = (
            issue_votes["vote"].value_counts().to_dict() if total > 0 else {}
        )

        alignment_label, alignment_icon, alignment_colour = _compute_alignment(
            pos["stance"], vote_counts, total
        )

        # Sources linked to this position
        pos_sources = df_psrc[df_psrc["position_id"] == pos["id"]]

        with st.container(border=True):
            # Header row: issue + stance
            hcol1, hcol2 = st.columns([3, 1])
            with hcol1:
                st.markdown(
                    f"**{issue_name}** — "
                    f"{STANCE_ICONS.get(pos['stance'], '⚪')} {pos['stance']}"
                )
            with hcol2:
                st.markdown(
                    f'<span style="color:{alignment_colour};font-weight:600;">'
                    f"{alignment_icon} {alignment_label}</span>",
                    unsafe_allow_html=True,
                )

            # Position summary + quote if available
            st.markdown(f"> {pos['summary']}")
            if pd.notna(pos.get("quote")) and pos["quote"]:
                st.markdown(f'> *"{pos["quote"]}"*')

            # Media sources
            if len(pos_sources) > 0:
                src_parts = []
                for _, src in pos_sources.iterrows():
                    icon = SOURCE_TYPE_ICONS.get(src["source_type"], "📄")
                    if pd.notna(src["url"]) and src["url"]:
                        src_parts.append(
                            f'{icon} [{src["title"]}]({src["url"]}) '
                            f'— {src["source_type"]}, {src["date"]}'
                        )
                    else:
                        src_parts.append(
                            f'{icon} {src["title"]} '
                            f'— {src["source_type"]}, {src["date"]}'
                        )
                with st.expander(f"Sources ({len(pos_sources)})"):
                    for part in src_parts:
                        st.markdown(part)

            if total > 0:
                # Vote summary
                vote_parts = []
                for v in ["For", "Against", "Abstained", "Absent"]:
                    c = vote_counts.get(v, 0)
                    if c > 0:
                        vote_parts.append(f"{v}: {c}")

                st.markdown(
                    f"**{total} related motion{'s' if total != 1 else ''}** "
                    f"— {' · '.join(vote_parts)}"
                )

                # Motion-level detail
                with st.expander("View related motions"):
                    for _, vr in issue_votes.sort_values(
                        "meeting_date", ascending=False
                    ).iterrows():
                        v_icon = VOTE_ICONS.get(vr["vote"], "⚪")
                        st.markdown(
                            f"{v_icon} **{vr['motion_title']}** "
                            f"— voted _{vr['vote']}_ ({vr['meeting_date']})"
                        )
            else:
                st.caption("No related motions voted on yet.")


# ---------------------------------------------------------------------------
# PAGE: Councillors
# ---------------------------------------------------------------------------
def page_councillors():
    st.title("Councillors")

    df_c = load_councillors()
    df_v = load_votes()
    df_a = load_attendance()
    df_pos = load_positions()
    df_mi = load_motion_issues()
    df_issues = load_issues()
    df_psrc = load_position_sources()
    df_decl = load_declarations()
    colours = get_party_colours(df_c)

    # --- Filters ---
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        ward_filter = st.selectbox(
            "Filter by ward",
            ["All Wards"] + sorted(df_c["ward"].unique().tolist()),
        )
    with filter_col2:
        party_filter = st.selectbox(
            "Filter by party",
            ["All Parties"] + sorted(df_c["party"].unique().tolist()),
        )

    filtered = df_c.copy()
    if ward_filter != "All Wards":
        filtered = filtered[filtered["ward"] == ward_filter]
    if party_filter != "All Parties":
        filtered = filtered[filtered["party"] == party_filter]

    # --- Councillor grid ---
    st.markdown(f"**{len(filtered)} councillor(s)**")

    selected_name = st.selectbox(
        "Select a councillor for detail view",
        filtered["full_name"].tolist(),
    )

    if not selected_name:
        return

    councillor = filtered[filtered["full_name"] == selected_name].iloc[0]
    cid = councillor["id"]

    st.markdown("---")

    # --- Profile header (photo + info) ---
    photo_col, info_col = st.columns([1, 5])
    with photo_col:
        photo_url = councillor.get("photo_url", None)
        if photo_url and str(photo_url) not in ("None", "nan", "") and str(photo_url).startswith("http"):
            st.image(photo_url, width=120)
        else:
            # Fallback: initials avatar via UI Avatars
            initials = f"{councillor['first_name'][0]}{councillor['last_name'][0]}"
            party_colour = councillor["party_colour"].lstrip("#")
            avatar_url = (
                f"https://ui-avatars.com/api/?name={initials}"
                f"&background={party_colour}&color=fff&size=120&bold=true&rounded=true"
            )
            st.image(avatar_url, width=120)
    with info_col:
        st.markdown(f"### {councillor['full_name']}")
        colour_swatch = f'<span style="display:inline-block;width:12px;height:12px;background:{councillor["party_colour"]};border-radius:2px;margin-right:6px;"></span>'
        st.markdown(
            f"{colour_swatch}**{councillor['party']}** ({councillor['party_short']})",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Ward:** {councillor['ward']}")

    # --- Stats row ---
    col2, col3 = st.columns(2)

    # --- Council-wide averages for comparison ---
    avg_attendance = (
        df_a.groupby("councillor_id")["present"].mean().mean() * 100
    )
    # Participation rate: votes cast (excluding Absent) / total votes
    total_votes_per_councillor = df_v.groupby("councillor_id").size()
    active_votes_per_councillor = (
        df_v[df_v["vote"] != "Absent"].groupby("councillor_id").size()
    )
    avg_participation = (
        (active_votes_per_councillor / total_votes_per_councillor).mean() * 100
    )

    # Attendance stats
    c_attendance = df_a[df_a["councillor_id"] == cid]
    if len(c_attendance) > 0:
        att_rate = c_attendance["present"].mean() * 100
        meetings_attended = int(c_attendance["present"].sum())
        total_meetings = len(c_attendance)
    else:
        att_rate = 0
        meetings_attended = 0
        total_meetings = 0

    att_diff = att_rate - avg_attendance

    with col2:
        st.metric("Attendance Rate", f"{att_rate:.0f}%")
        if att_diff > 2:
            st.markdown(
                f'<span style="color:#4CAF50;font-size:0.85em;">▲ {abs(att_diff):.0f}pp above council average ({avg_attendance:.0f}%)</span>',
                unsafe_allow_html=True,
            )
        elif att_diff < -2:
            st.markdown(
                f'<span style="color:#F44336;font-size:0.85em;">▼ {abs(att_diff):.0f}pp below council average ({avg_attendance:.0f}%)</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span style="color:#9E9E9E;font-size:0.85em;">● At council average ({avg_attendance:.0f}%)</span>',
                unsafe_allow_html=True,
            )
        st.caption(f"{meetings_attended}/{total_meetings} meetings")

    # Vote breakdown + participation badge
    c_votes = df_v[df_v["councillor_id"] == cid]
    with col3:
        if len(c_votes) > 0:
            vote_counts = c_votes["vote"].value_counts()
            active_count = len(c_votes[c_votes["vote"] != "Absent"])
            participation_rate = active_count / len(c_votes) * 100
            part_diff = participation_rate - avg_participation

            st.metric("Votes Cast", len(c_votes))

            if part_diff > 2:
                st.markdown(
                    f'<span style="color:#4CAF50;font-size:0.85em;">▲ {participation_rate:.0f}% participation — {abs(part_diff):.0f}pp above avg</span>',
                    unsafe_allow_html=True,
                )
            elif part_diff < -2:
                st.markdown(
                    f'<span style="color:#F44336;font-size:0.85em;">▼ {participation_rate:.0f}% participation — {abs(part_diff):.0f}pp below avg</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<span style="color:#9E9E9E;font-size:0.85em;">● {participation_rate:.0f}% participation — at council average</span>',
                    unsafe_allow_html=True,
                )

            parts = []
            for v in ["For", "Against", "Abstained", "Absent"]:
                count = vote_counts.get(v, 0)
                if count > 0:
                    parts.append(f"{v}: {count}")
            st.caption(" · ".join(parts))

    st.markdown("---")

    # --- Voting record ---
    st.subheader("Voting Record")
    if len(c_votes) > 0:
        vote_display = c_votes[
            ["motion_title", "vote", "outcome", "meeting_date", "meeting_type"]
        ].copy()
        vote_display.columns = ["Motion", "Vote", "Outcome", "Date", "Type"]
        vote_display = vote_display.sort_values("Date", ascending=False)

        def style_vote(val):
            colour_map = {
                "For": "background-color: #C8E6C9",
                "Against": "background-color: #FFCDD2",
                "Abstained": "background-color: #FFE0B2",
                "Absent": "background-color: #E0E0E0",
            }
            return colour_map.get(val, "")

        st.dataframe(
            vote_display.style.map(style_vote, subset=["Vote"]),
            use_container_width=True,
            hide_index=True,
            height=min(400, 35 * len(vote_display) + 38),
        )
    else:
        st.info("No votes recorded for this councillor.")

    # --- Policy Stances ---
    st.subheader("Policy Stances")
    st.caption(
        "Stated positions cross-referenced with voting record on related motions. "
        "Alignment shows whether votes match public statements."
    )
    _render_policy_stance_cards(cid, df_pos, df_v, df_mi, df_issues, df_psrc)

    # --- Register of Interests ---
    st.subheader("Register of Interests")
    st.caption(
        "Declared under the Ethics in Public Office Act. "
        "Active and withdrawn declarations are shown."
    )
    c_decl = df_decl[df_decl["councillor_id"] == cid]

    if len(c_decl) == 0:
        st.info("No declarations on record for this councillor.")
    else:
        CATEGORY_ICONS = {
            "Land & Property": "🏠",
            "Employment & Occupation": "💼",
            "Directorships": "🏢",
            "Shares & Financial Interests": "📈",
            "Contracts with Council": "📝",
            "Gifts & Hospitality": "🎁",
            "Membership of Bodies": "🤝",
            "Consultancy & Advisory": "🔧",
        }

        active = c_decl[c_decl["date_withdrawn"].isna()]
        withdrawn = c_decl[c_decl["date_withdrawn"].notna()]

        # Summary counts by category
        cat_counts = active.groupby("category").size().reset_index(name="count")
        summary_parts = []
        for _, row in cat_counts.iterrows():
            icon = CATEGORY_ICONS.get(row["category"], "📄")
            summary_parts.append(f"{icon} {row['category']}: {row['count']}")
        if summary_parts:
            st.markdown(" · ".join(summary_parts))

        # Active declarations grouped by category
        for category in active["category"].unique():
            cat_decls = active[active["category"] == category]
            icon = CATEGORY_ICONS.get(category, "📄")

            with st.expander(
                f"{icon} {category} ({len(cat_decls)})", expanded=False
            ):
                for _, decl in cat_decls.iterrows():
                    st.markdown(f"**{decl['description']}**")
                    caption_parts = [f"Declared: {decl['date_declared']}"]
                    if pd.notna(decl["notes"]) and decl["notes"]:
                        caption_parts.append(decl["notes"])
                    st.caption(" · ".join(caption_parts))

        # Withdrawn declarations
        if len(withdrawn) > 0:
            with st.expander(
                f"Withdrawn declarations ({len(withdrawn)})", expanded=False
            ):
                for _, decl in withdrawn.iterrows():
                    icon = CATEGORY_ICONS.get(decl["category"], "📄")
                    st.markdown(
                        f"~~{icon} {decl['category']}: {decl['description']}~~"
                    )
                    st.caption(
                        f"Declared: {decl['date_declared']} · "
                        f"Withdrawn: {decl['date_withdrawn']}"
                        + (f" · {decl['notes']}" if pd.notna(decl["notes"]) else "")
                    )


# ---------------------------------------------------------------------------
# PAGE: Motions & Votes
# ---------------------------------------------------------------------------

# Consistent colour maps used across the motions page
VOTE_COLOURS = {
    "For": "#4CAF50",
    "Against": "#F44336",
    "Abstained": "#FF9800",
    "Absent": "#9E9E9E",
}

VOTE_ICONS = {
    "For": "🟢",
    "Against": "🔴",
    "Abstained": "🟡",
    "Absent": "⚪",
}

SENTIMENT_ICONS = {
    "Supportive": "👍",
    "Critical": "👎",
    "Neutral": "➖",
    "Procedural": "📋",
}


def _render_councillor_card(councillor_name, vote, statements, party_colour):
    """Render a single councillor's vote + statements within a party tab."""
    vote_icon = VOTE_ICONS.get(vote, "⚪")
    st.markdown(
        f'{vote_icon} **{councillor_name}** — voted _{vote}_'
    )

    if len(statements) > 0:
        for _, stmt in statements.iterrows():
            sent_icon = SENTIMENT_ICONS.get(stmt["sentiment"], "")
            st.markdown(f"&emsp;{sent_icon} {stmt['summary']}")
            if pd.notna(stmt["quote"]) and stmt["quote"]:
                st.markdown(f'&emsp;&emsp;*"{stmt["quote"]}"*')
    else:
        st.caption("&emsp;No recorded statements on this motion.")


def page_motions():
    st.title("Motions & Votes")

    df_m = load_motions()
    df_v = load_votes()
    df_mi = load_motion_issues()
    df_ms = load_motion_statements()
    df_c = load_councillors()
    colours = get_party_colours(df_c)

    # Determine party display order (by seat count descending)
    party_order = (
        df_c.groupby("party_short")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)["party_short"]
        .tolist()
    )

    # --- Motion list ---
    for idx, motion in df_m.iterrows():
        outcome_icon = {
            "Passed": "🟢",
            "Failed": "🔴",
            "Deferred": "🟡",
            "Withdrawn": "⚪",
            "Amended": "🔵",
        }.get(motion["outcome"], "⚪")

        with st.expander(
            f"{outcome_icon} {motion['title']}  —  {motion['meeting_date']}"
        ):
            # --- Motion header ---
            st.markdown(f"**{motion['outcome']}** · {motion['meeting_type']}")
            st.markdown(motion["description"])

            meta_parts = []
            if pd.notna(motion["proposed_by"]):
                meta_parts.append(f"**Proposed by:** {motion['proposed_by']}")
            if pd.notna(motion["seconded_by"]):
                meta_parts.append(f"**Seconded by:** {motion['seconded_by']}")
            if meta_parts:
                st.markdown(" · ".join(meta_parts))

            # Issues
            motion_issues = df_mi[df_mi["motion_id"] == motion["id"]]
            if len(motion_issues) > 0:
                tags = ", ".join(motion_issues["issue_name"].tolist())
                st.caption(f"Issues: {tags}")

            st.markdown("---")

            # --- Vote summary metrics ---
            m_votes = df_v[df_v["motion_id"] == motion["id"]]
            m_statements = df_ms[df_ms["motion_id"] == motion["id"]]

            if len(m_votes) > 0:
                vote_summary = m_votes["vote"].value_counts()

                # Party-level vote chart
                party_votes = (
                    m_votes.groupby(["party_short", "vote"])
                    .size()
                    .reset_index(name="count")
                )
                fig = px.bar(
                    party_votes,
                    x="party_short",
                    y="count",
                    color="vote",
                    color_discrete_map=VOTE_COLOURS,
                    barmode="stack",
                    labels={
                        "party_short": "Party",
                        "count": "Votes",
                        "vote": "",
                    },
                )
                fig.update_layout(
                    height=250, margin=dict(l=0, r=0, t=10, b=0)
                )
                st.plotly_chart(fig, use_container_width=True)

                # --- Vote filter buttons ---
                # Use a unique key per motion to avoid Streamlit widget ID clashes
                motion_key = f"motion_{motion['id']}"

                filter_cols = st.columns(5)
                vote_categories = ["All", "For", "Against", "Abstained", "Absent"]
                vote_filter_colours = {
                    "All": "primary",
                    "For": "primary",
                    "Against": "primary",
                    "Abstained": "primary",
                    "Absent": "secondary",
                }

                # Session state for this motion's filter
                state_key = f"vote_filter_{motion_key}"
                if state_key not in st.session_state:
                    st.session_state[state_key] = "All"

                for i, cat in enumerate(vote_categories):
                    count = vote_summary.get(cat, len(m_votes)) if cat != "All" else len(m_votes)
                    label = f"{VOTE_ICONS.get(cat, '📋')} {cat} ({count})"
                    with filter_cols[i]:
                        if st.button(
                            label,
                            key=f"{motion_key}_{cat}",
                            use_container_width=True,
                            type="primary" if st.session_state[state_key] == cat else "secondary",
                        ):
                            st.session_state[state_key] = cat
                            st.rerun()

                active_filter = st.session_state[state_key]

                # Apply filter
                if active_filter == "All":
                    filtered_votes = m_votes
                else:
                    filtered_votes = m_votes[m_votes["vote"] == active_filter]

                st.markdown("---")

                if len(filtered_votes) == 0:
                    st.info(f"No councillors voted _{active_filter}_ on this motion.")
                else:
                    # --- Two views: filtered councillor list OR party tabs ---
                    if active_filter != "All":
                        # Filtered view: alphabetical list of councillors with that vote
                        st.markdown(f"**Councillors who voted _{active_filter}_ ({len(filtered_votes)})**")
                        for _, voter in filtered_votes.sort_values("councillor_name").iterrows():
                            c_stmts = m_statements[
                                m_statements["councillor_id"] == voter["councillor_id"]
                            ]
                            colour_dot = f'<span style="display:inline-block;width:10px;height:10px;background:{voter["party_colour"]};border-radius:50%;margin-right:6px;"></span>'
                            st.markdown(
                                f"{colour_dot}**{voter['councillor_name']}** ({voter['party_short']})",
                                unsafe_allow_html=True,
                            )
                            if len(c_stmts) > 0:
                                for _, stmt in c_stmts.iterrows():
                                    sent_icon = SENTIMENT_ICONS.get(stmt["sentiment"], "")
                                    st.markdown(f"&emsp;{sent_icon} {stmt['summary']}")
                                    if pd.notna(stmt["quote"]) and stmt["quote"]:
                                        st.markdown(f'&emsp;&emsp;*"{stmt["quote"]}"*')
                            st.markdown("")
                    else:
                        # Default view: party tabs
                        st.markdown("**Councillor Statements by Party**")
                        motion_parties = [p for p in party_order if p in m_votes["party_short"].values]

                        if motion_parties:
                            tabs = st.tabs(motion_parties)

                            for tab, party_short in zip(tabs, motion_parties):
                                with tab:
                                    party_votes_df = filtered_votes[
                                        filtered_votes["party_short"] == party_short
                                    ].sort_values("councillor_name")

                                    for _, voter in party_votes_df.iterrows():
                                        c_statements = m_statements[
                                            m_statements["councillor_id"] == voter["councillor_id"]
                                        ]
                                        _render_councillor_card(
                                            voter["councillor_name"],
                                            voter["vote"],
                                            c_statements,
                                            voter["party_colour"],
                                        )
                                        st.markdown("")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    page = sidebar()

    if page == "Dashboard":
        page_dashboard()
    elif page == "Councillors":
        page_councillors()
    elif page == "Motions & Votes":
        page_motions()


if __name__ == "__main__":
    main()
