import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import io
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Susu Savings",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <script>
    const removeSidebar = () => {
        const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        const toggle  = window.parent.document.querySelector('[data-testid="collapsedControl"]');
        const header  = window.parent.document.querySelector('[data-testid="stHeader"]');
        if (sidebar) sidebar.remove();
        if (toggle)  toggle.remove();
        if (header)  header.style.display = 'none';
    };
    removeSidebar();
    setTimeout(removeSidebar, 300);
    setTimeout(removeSidebar, 800);
    </script>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    header {visibility: hidden !important; height: 0 !important;}
    #MainMenu {visibility: hidden !important;}
    .stDeployButton {display: none !important;}
    footer {visibility: hidden !important;}
    section[data-testid="stSidebar"] {display: none !important; width: 0 !important;}
    [data-testid="collapsedControl"] {display: none !important; width: 0 !important;}
    [data-testid="stSidebarNav"] {display: none !important;}
    button[kind="header"] {display: none !important;}
    .block-container {padding-top: 1.8rem !important; padding-bottom: 3rem !important; max-width: 780px !important;}
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    .main, .stApp { background-color: #0d1117 !important; }

    .page-header {
        background: linear-gradient(135deg, #1c2a3a 0%, #243447 100%);
        border: 1px solid #2d3f55; border-radius: 14px;
        padding: 22px 26px; margin-bottom: 18px;
    }
    .page-header h1 { font-size: 20px; font-weight: 700; color: #e2e8f0 !important; margin: 0 0 4px 0; letter-spacing: -0.2px; }
    .page-header p { font-size: 12px; color: #4a6080; margin: 0; }

    .metric-strip { display: flex; gap: 10px; margin-bottom: 20px; }
    .metric-chip { flex: 1; background: #161d27; border: 1px solid #1e2d3d; border-radius: 10px; padding: 10px 14px; }
    .metric-chip-label { font-size: 10px; font-weight: 600; color: #3d5a75; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 3px; }
    .metric-chip-value { font-size: 15px; font-weight: 700; color: #38bdf8; }

    .lock-wrap { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; }
    .lock-icon { font-size: 48px; margin-bottom: 16px; }
    .lock-title { font-size: 20px; font-weight: 700; color: #e2e8f0; margin-bottom: 6px; text-align: center; }
    .lock-sub { font-size: 13px; color: #3d5a75; text-align: center; margin-bottom: 28px; }

    .admin-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: #162032; border: 1px solid #1e3a5f;
        border-radius: 20px; padding: 5px 12px;
        font-size: 11px; font-weight: 600; color: #38bdf8; margin-bottom: 20px;
    }

    .section-eyebrow { font-size: 10px; font-weight: 600; color: #3d5a75; text-transform: uppercase; letter-spacing: 0.8px; margin: 26px 0 2px 0; }
    .section-heading { font-size: 16px; font-weight: 700; color: #cbd5e1; margin: 0 0 3px 0; }
    .section-sub { font-size: 12px; color: #3d5a75; margin: 0 0 12px 0; }
    .divider { height: 1px; background: #161d27; margin: 20px 0; }

    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background: #161d27 !important; border: 1px solid #1e2d3d !important;
        color: #e2e8f0 !important; border-radius: 8px !important; font-size: 13px !important;
    }
    .stTextInput label, .stNumberInput label, .stTextArea label,
    .stSelectbox label, .stCheckbox label { color: #64748b !important; font-size: 12px !important; font-weight: 500 !important; }
    .stSelectbox > div > div { background: #161d27 !important; border: 1px solid #1e2d3d !important; color: #e2e8f0 !important; border-radius: 8px !important; }

    .stButton > button {
        background: #1d4ed8 !important; color: white !important; border: none !important;
        border-radius: 8px !important; font-weight: 600 !important; font-size: 13px !important;
        padding: 8px 18px !important; width: 100%;
    }
    .stButton > button:hover { background: #2563eb !important; }
    .stButton > button[kind="secondary"] { background: #161d27 !important; color: #64748b !important; border: 1px solid #1e2d3d !important; }

    .stDownloadButton > button {
        background: #161d27 !important; color: #38bdf8 !important;
        border: 1px solid #1e2d3d !important; border-radius: 8px !important;
        font-size: 13px !important; font-weight: 600 !important;
        padding: 8px 18px !important; width: auto !important;
    }

    .streamlit-expanderHeader {
        background: #161d27 !important; border: 1px solid #1e2d3d !important;
        border-radius: 10px !important; color: #94a3b8 !important;
        font-size: 13px !important; font-weight: 600 !important;
    }
    .streamlit-expanderContent {
        background: #0d1117 !important; border: 1px solid #1e2d3d !important;
        border-top: none !important; border-radius: 0 0 10px 10px !important; padding: 16px !important;
    }

    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #1e2d3d; }
    .stCheckbox { color: #94a3b8 !important; }

    div[data-testid="stSuccess"] { background: #0f2a1a !important; border: 1px solid #14532d !important; border-radius: 8px !important; color: #4ade80 !important; font-size: 13px !important; }
    div[data-testid="stError"] { background: #2a0f0f !important; border: 1px solid #7f1d1d !important; border-radius: 8px !important; color: #f87171 !important; font-size: 13px !important; }

    .footer-note { text-align: center; font-size: 11px; color: #1e2d3d; margin-top: 28px; padding-top: 16px; border-top: 1px solid #161d27; }
    </style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_num(val):
    return f"{int(val):,}" if val == int(val) else f"{val:,.2f}"

def format_date(dt):
    d = dt.day
    sfx = 'th' if 11 <= d <= 13 else {1:'st',2:'nd',3:'rd'}.get(d%10,'th')
    return f"{d}{sfx} {dt.strftime('%b %Y')}"


# ── Google Sheets connection ───────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet  = client.open(st.secrets["sheet"]["name"])
    return sheet

def ensure_worksheet(sheet, title, rows=1, cols=2):
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=rows, cols=cols)

def load_cell(sheet, ws_title, default):
    ws  = ensure_worksheet(sheet, ws_title)
    val = ws.cell(1, 1).value
    if val:
        try:
            return json.loads(val)
        except Exception:
            return default
    return default

def save_cell(sheet, ws_title, value):
    ws = ensure_worksheet(sheet, ws_title)
    ws.update("A1", [[json.dumps(value)]])


def load_all(sheet):
    settings = load_cell(sheet, "settings", {
        "start_date": "2026-08-17",
        "base_monthly": 1000,
        "admin_fee_percentage": 0.0,
        "names_input": "Alice, Bob, Charlie, Diana, Frank, Grace",
    })
    tiers          = load_cell(sheet, "tiers", {})
    payments       = load_cell(sheet, "payments", {})
    payout_status  = load_cell(sheet, "payout_status", {})
    return settings, tiers, payments, payout_status

def save_all(sheet):
    save_cell(sheet, "settings", {
        "start_date":           st.session_state.start_date,
        "base_monthly":         st.session_state.base_monthly,
        "admin_fee_percentage": st.session_state.admin_fee_percentage,
        "names_input":          st.session_state.names_input,
    })
    save_cell(sheet, "tiers",         st.session_state.member_tiers)
    save_cell(sheet, "payments",      st.session_state.payments)
    save_cell(sheet, "payout_status", st.session_state.payout_status)


# ── connect & load ────────────────────────────────────────────────────────────
try:
    gsheet = get_sheet()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    st.stop()

if "initialized" not in st.session_state:
    settings, tiers, payments, payout_status = load_all(gsheet)
    st.session_state.start_date           = settings.get("start_date", "2026-08-17")
    st.session_state.base_monthly         = settings.get("base_monthly", 1000)
    st.session_state.admin_fee_percentage = settings.get("admin_fee_percentage", 0.0)
    st.session_state.names_input          = settings.get("names_input", "Alice, Bob, Charlie, Diana, Frank, Grace")
    st.session_state.member_tiers         = tiers
    st.session_state.payments             = payments
    st.session_state.payout_status        = payout_status
    st.session_state.authenticated        = False
    st.session_state.initialized          = True


# ── auth gate ─────────────────────────────────────────────────────────────────
ADMIN_PW = "Susu2026"

if not st.session_state.authenticated:
    st.markdown("""
        <div class="lock-wrap">
            <div class="lock-icon">🔒</div>
            <div class="lock-title">Susu Savings Dashboard</div>
            <div class="lock-sub">Enter the group passcode to continue</div>
        </div>
    """, unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        pw = st.text_input("Passcode", type="password", label_visibility="collapsed", placeholder="Enter passcode…")
        if st.button("Unlock →"):
            if pw == ADMIN_PW:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect passcode.")
    st.stop()


# ── derive members / dates ────────────────────────────────────────────────────
members     = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("Please enter at least 2 member names in Settings.")
    st.stop()

for m in members:
    if m not in st.session_state.member_tiers:
        st.session_state.member_tiers[m] = st.session_state.base_monthly

total_weeks = num_members * 4

try:
    start_dt = datetime.strptime(st.session_state.start_date, "%Y-%m-%d")
except ValueError:
    st.error("Date format must be YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

if list(st.session_state.payments.keys()) != members:
    st.session_state.payments = {m: {str(w): False for w in range(1, total_weeks+1)} for m in members}

if not st.session_state.payout_status:
    st.session_state.payout_status = {f"Month {i+1}": {"amount_collected": 0.0} for i in range(num_members)}


# ── calculations ──────────────────────────────────────────────────────────────
today = datetime.today()
days_passed          = (today - start_dt).days
current_elapsed_week = max(0, days_passed // 7) + 1 if today >= start_dt else 0
current_elapsed_week = min(current_elapsed_week, total_weeks)

total_cash_collected = sum(
    st.session_state.member_tiers.get(m, st.session_state.base_monthly) / 4.0
    * sum(1 for w in range(1, total_weeks+1) if st.session_state.payments.get(m,{}).get(str(w), False))
    for m in members
)
total_payouts_distributed = sum(
    float(st.session_state.payout_status.get(f"Month {i+1}", {}).get("amount_collected", 0.0))
    for i in range(num_members)
)
total_cash_held = total_cash_collected - total_payouts_distributed


# ── header + metrics ──────────────────────────────────────────────────────────
st.markdown(f"""
    <div class="page-header">
        <h1>💸 Susu Savings Dashboard</h1>
        <p>{num_members} members &nbsp;·&nbsp; Week {current_elapsed_week} of {total_weeks} &nbsp;·&nbsp; Ends {format_date(end_date)}</p>
    </div>
    <div class="metric-strip">
        <div class="metric-chip">
            <div class="metric-chip-label">Cash Held</div>
            <div class="metric-chip-value">GHS {fmt_num(total_cash_held)}</div>
        </div>
        <div class="metric-chip">
            <div class="metric-chip-label">Admin Fee</div>
            <div class="metric-chip-value">{fmt_num(st.session_state.admin_fee_percentage)}%</div>
        </div>
        <div class="metric-chip">
            <div class="metric-chip-label">Current Week</div>
            <div class="metric-chip-value">Wk {current_elapsed_week} / {total_weeks}</div>
        </div>
        <div class="metric-chip">
            <div class="metric-chip-label">End Date</div>
            <div class="metric-chip-value">{format_date(end_date)}</div>
        </div>
    </div>
    <div class="admin-badge">🔓 Admin — logged in</div>
""", unsafe_allow_html=True)


# ── build table data ──────────────────────────────────────────────────────────
schedule_data, wa_payout_rows = [], []
current_date = start_dt
for i in range(num_members):
    month_lbl    = f"Month {i+1}"
    recipient    = members[i]
    payout_date  = current_date + timedelta(weeks=4)
    rec_monthly  = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    gross_pool   = rec_monthly * num_members
    admin_fee_v  = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
    net_pool_amt = gross_pool - admin_fee_v
    collected    = float(st.session_state.payout_status.get(month_lbl, {}).get("amount_collected", 0.0))
    remaining    = max(0.0, net_pool_amt - collected)
    schedule_data.append({
        "Turn": f"Month {i+1}", "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Admin Fee": f"GHS {fmt_num(admin_fee_v)}",
        "Net Pool": f"GHS {fmt_num(net_pool_amt)}",
        "Collected": f"GHS {fmt_num(collected)}",
        "Remaining": f"GHS {fmt_num(remaining)}",
    })
    wa_payout_rows.append({"recipient": recipient, "date": format_date(payout_date), "balance": fmt_num(remaining)})
    current_date = payout_date

contrib_data, wa_contrib_rows = [], []
for member in members:
    m_monthly   = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly    = m_monthly / 4.0
    m_pmts      = st.session_state.payments.get(member, {})
    paid_passed = sum(1 for w in range(1, current_elapsed_week+1) if m_pmts.get(str(w), False))
    owing       = (current_elapsed_week - paid_passed) * m_weekly
    total_paid  = sum(1 for w in range(1, total_weeks+1) if m_pmts.get(str(w), False))
    pct         = int((total_paid / total_weeks) * 100) if total_weeks else 0
    standing    = f"Owing GHS {fmt_num(owing)}" if owing > 0 else "Up to date"
    contrib_data.append({
        "Member": member,
        "Monthly Tier": f"GHS {fmt_num(m_monthly)}",
        "Weekly Target": f"GHS {fmt_num(m_weekly)}",
        "Weeks Paid": f"{total_paid} / {total_weeks}",
        "Progress": f"{pct}%",
        "Status": ("🔴 " if owing > 0 else "🟢 ") + standing,
    })
    wa_contrib_rows.append({"member": member, "standing": standing})


# ── payout schedule ───────────────────────────────────────────────────────────
st.markdown('<p class="section-eyebrow">Rotation</p>', unsafe_allow_html=True)
st.markdown('<p class="section-heading">Payout Schedule</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Dates, fees and pool balance per turn</p>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(schedule_data), use_container_width=True, hide_index=True)

# ── contributions ─────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-eyebrow">Members</p>', unsafe_allow_html=True)
st.markdown('<p class="section-heading">Contributions</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Tiers, progress and payment standing</p>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(contrib_data), use_container_width=True, hide_index=True)

# ── exports ───────────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-eyebrow">Export</p>', unsafe_allow_html=True)
st.markdown('<p class="section-heading">WhatsApp Updates</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Download ready-to-paste messages for the group</p>', unsafe_allow_html=True)

# Weekly update
buf = io.StringIO()
buf.write(f"📌 *WK {current_elapsed_week} UPDATE*\n")
buf.write(f"💰 *Cash at Hand:* GHS {fmt_num(total_cash_held)}\n")
buf.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
buf.write("👥 *MEMBERS*\n")
for r in wa_contrib_rows:
    buf.write(f"{'✅' if 'Up' in r['standing'] else '❌'} *{r['member']}*: {r['standing']}\n")
buf.write("\n🎁 *PAYOUTS*\n")
for r in wa_payout_rows:
    buf.write(f"{r['recipient']} · {r['date']} · GHS {r['balance']}\n")

# Onboarding
ob = io.StringIO()
ob.write("📋 *SUSU GROUP — ONBOARDING DETAILS*\n")
ob.write(f"🗓️ *Start Date:* {format_date(start_dt)}\n")
ob.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
ob.write("👤 *MEMBER DETAILS*\n")
for member in members:
    m_monthly = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly  = m_monthly / 4.0
    ob.write(f"*{member}*\n")
    ob.write(f"  • Monthly Tier: GHS {fmt_num(m_monthly)}\n")
    ob.write(f"  • Weekly Target: GHS {fmt_num(m_weekly)}\n\n")
ob.write("🎁 *PAYOUT SCHEDULE*\n")
cur_date = start_dt
for i in range(num_members):
    recipient    = members[i]
    payout_date  = cur_date + timedelta(weeks=4)
    rec_monthly  = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    gross_pool   = rec_monthly * num_members
    admin_fee_v  = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
    net_pool_amt = gross_pool - admin_fee_v
    ob.write(f"*Month {i+1} — {recipient}*\n")
    ob.write(f"  • Payout Date: {format_date(payout_date)}\n")
    ob.write(f"  • Net Pool: GHS {fmt_num(net_pool_amt)}\n\n")
    cur_date = payout_date

col_dl1, col_dl2 = st.columns(2)
with col_dl1:
    st.download_button(
        label="📥 Weekly Update",
        data=buf.getvalue(),
        file_name=f"Susu_W{current_elapsed_week}.txt",
        mime="text/plain",
    )
with col_dl2:
    st.download_button(
        label="📋 Onboarding Details",
        data=ob.getvalue(),
        file_name="Susu_Onboarding.txt",
        mime="text/plain",
    )


# ── admin panel ───────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

with st.expander("⚙️ Group Settings"):
    c1, c2, c3 = st.columns(3)
    with c1:
        new_start = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    with c2:
        new_base = st.number_input("Base Monthly (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    with c3:
        new_fee = st.number_input("Admin Fee (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    new_names = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
    if st.button("Save Settings", key="save_settings"):
        st.session_state.start_date           = new_start
        st.session_state.base_monthly         = new_base
        st.session_state.admin_fee_percentage = new_fee
        st.session_state.names_input          = new_names
        save_all(gsheet)
        st.success("✓ Settings saved to Google Sheets.")
        st.rerun()

with st.expander("💰 Custom Member Tiers"):
    tier_cols = st.columns(min(num_members, 4))
    new_tiers = {}
    for idx, m in enumerate(members):
        with tier_cols[idx % 4]:
            new_tiers[m] = st.number_input(m, value=float(st.session_state.member_tiers.get(m, st.session_state.base_monthly)), step=50.0, key=f"tier_{m}")
    if st.button("Save Tiers", key="save_tiers"):
        st.session_state.member_tiers = new_tiers
        save_all(gsheet)
        st.success("✓ Tiers saved to Google Sheets.")
        st.rerun()

with st.expander("📝 Record Weekly Payment"):
    pc1, pc2 = st.columns(2)
    with pc1:
        sel_member = st.selectbox("Member", members, key="pay_member")
    with pc2:
        sel_week = st.selectbox("Week", list(range(1, total_weeks+1)), key="pay_week")
    cur_status = st.session_state.payments.get(sel_member, {}).get(str(sel_week), False)
    chk = st.checkbox(f"Mark Week {sel_week} as paid", value=cur_status, key="pay_chk")
    if st.button("Save Payment", key="save_payment"):
        st.session_state.payments[sel_member][str(sel_week)] = chk
        save_all(gsheet)
        st.success(f"✓ Week {sel_week} for {sel_member} saved to Google Sheets.")
        st.rerun()

with st.expander("🎁 Record Payout"):
    month_options = [f"Month {i+1} — {members[i]}" for i in range(num_members)]
    sel_month_lbl = st.selectbox("Payout Turn", month_options, key="payout_month")
    mkey          = sel_month_lbl.split(" —")[0]
    rec_idx       = int(mkey.split(" ")[1]) - 1
    rec_name      = members[rec_idx]
    rec_monthly_v = st.session_state.member_tiers.get(rec_name, st.session_state.base_monthly)
    gross_v       = rec_monthly_v * num_members
    fee_v         = gross_v * (st.session_state.admin_fee_percentage / 100.0)
    net_v         = gross_v - fee_v
    cur_collected = float(st.session_state.payout_status.get(mkey, {}).get("amount_collected", 0.0))
    new_collected = st.number_input(
        f"Amount Collected for {rec_name} (max GHS {fmt_num(net_v)})",
        value=cur_collected, min_value=0.0, max_value=float(net_v), step=50.0, key="payout_amt"
    )
    if st.button("Save Payout", key="save_payout"):
        if mkey not in st.session_state.payout_status:
            st.session_state.payout_status[mkey] = {}
        st.session_state.payout_status[mkey]["amount_collected"] = new_collected
        save_all(gsheet)
        st.success(f"✓ Payout for {rec_name} saved to Google Sheets.")
        st.rerun()


# ── logout ────────────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
if st.button("🔒 Lock Dashboard", key="logout", type="secondary"):
    st.session_state.authenticated = False
    st.rerun()

st.markdown('<div class="footer-note">Data stored in Google Sheets · Secured with passcode</div>', unsafe_allow_html=True)
