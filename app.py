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
# Database bootstrap — handles both local and Streamlit Cloud
# ---------------------------------------------------------------------------

# Locally: DB lives in db/. On Streamlit Cloud (or any read-only fs): use /tmp/.
if os.access(DB_DIR, os.W_OK):
    DB_PATH = os.path.join(DB_DIR, "cork_civic_tracker.db")
else:
    DB_PATH = os.path.join("/tmp", "cork_civic_tracker.db")


def _db_has_tables():
    """Check whether the database has all required tables."""
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        required = ["councillors", "motion_statements"]
        for table in required:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cursor.fetchone() is None:
                conn.close()
                return False
        conn.close()
        return True
    except Exception:
        return False


if not _db_has_tables():
    # Remove stale DB so seed recreates it with the full schema
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    import sys
    os.environ["CORK_DB_PATH"] = DB_PATH
    sys.path.insert(0, DB_DIR)
    import seed as _seed
    _seed.DB_PATH = DB_PATH
    _seed.SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")
    _seed.main()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
@st.cache_resource
def get_connection():
    """Return a cached SQLite connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=None):
    """Run a query and return a DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params or [])



# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_councillors():
    return query("""
        SELECT c.id, c.first_name, c.last_name,
               c.first_name || ' ' || c.last_name AS full_name,
               p.name AS party, p.short_name AS party_short, p.colour AS party_colour,
               w.name AS ward, c.active
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


# ---------------------------------------------------------------------------
# PAGE: Councillors
# ---------------------------------------------------------------------------
def page_councillors():
    st.title("Councillors")

    df_c = load_councillors()
    df_v = load_votes()
    df_a = load_attendance()
    df_pos = load_positions()
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

    # --- Profile header ---
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        st.markdown(f"### {councillor['full_name']}")
        colour_swatch = f'<span style="display:inline-block;width:12px;height:12px;background:{councillor["party_colour"]};border-radius:2px;margin-right:6px;"></span>'
        st.markdown(
            f"{colour_swatch}**{councillor['party']}** ({councillor['party_short']})",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Ward:** {councillor['ward']}")

    # Attendance stats
    c_attendance = df_a[df_a["councillor_id"] == cid]
    if len(c_attendance) > 0:
        att_rate = c_attendance["present"].mean() * 100
        meetings_attended = c_attendance["present"].sum()
        total_meetings = len(c_attendance)
    else:
        att_rate = 0
        meetings_attended = 0
        total_meetings = 0

    with col2:
        st.metric("Attendance Rate", f"{att_rate:.0f}%")
        st.caption(f"{meetings_attended}/{total_meetings} meetings")

    # Vote breakdown
    c_votes = df_v[df_v["councillor_id"] == cid]
    with col3:
        if len(c_votes) > 0:
            vote_counts = c_votes["vote"].value_counts()
            st.metric("Votes Cast", len(c_votes))
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

    # --- Stated Positions ---
    st.subheader("Stated Positions")
    c_positions = df_pos[df_pos["councillor_id"] == cid]
    if len(c_positions) > 0:
        for _, pos in c_positions.iterrows():
            stance_icon = {
                "Support": "🟢",
                "Oppose": "🔴",
                "Neutral": "⚪",
                "Mixed": "🟡",
            }.get(pos["stance"], "⚪")

            st.markdown(
                f"**{stance_icon} {pos['issue_name']}** — _{pos['stance']}_"
            )
            st.markdown(f"> {pos['summary']}")
            st.caption(f"Date: {pos['date']}")
    else:
        st.info("No stated positions recorded for this councillor.")


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
            if len(m_votes) > 0:
                vote_summary = m_votes["vote"].value_counts()
                cols = st.columns(4)
                for i, v in enumerate(["For", "Against", "Abstained", "Absent"]):
                    cols[i].metric(v, vote_summary.get(v, 0))

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

            st.markdown("---")

            # --- Party tabs with councillor statements ---
            st.markdown("**Councillor Statements by Party**")

            m_statements = df_ms[df_ms["motion_id"] == motion["id"]]

            # Only show tabs for parties that have councillors who voted on this motion
            motion_parties = [p for p in party_order if p in m_votes["party_short"].values]

            if motion_parties:
                tabs = st.tabs(motion_parties)

                for tab, party_short in zip(tabs, motion_parties):
                    with tab:
                        # Get all councillors from this party who voted on this motion
                        party_votes_df = m_votes[m_votes["party_short"] == party_short].sort_values("councillor_name")

                        for _, voter in party_votes_df.iterrows():
                            # Get statements for this councillor on this motion
                            c_statements = m_statements[
                                m_statements["councillor_id"] == voter["councillor_id"]
                            ]

                            _render_councillor_card(
                                voter["councillor_name"],
                                voter["vote"],
                                c_statements,
                                voter["party_colour"],
                            )
                            st.markdown("")  # spacing between councillors


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
