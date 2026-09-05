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
    .block-container {padding-top: 2rem !important; padding-bottom: 4rem !important; max-width: 800px !important;}

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    /* Frosted glass background */
    .main, .stApp {
        background: linear-gradient(135deg, #0a0f1e 0%, #0d1829 50%, #0a1520 100%) !important;
        min-height: 100vh;
    }

    /* Lock screen */
    .lock-outer {
        min-height: 80vh;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        padding: 40px 20px;
    }
    .lock-card {
        background: rgba(255,255,255,0.04);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px;
        padding: 48px 40px;
        text-align: center;
        width: 100%;
        max-width: 360px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06);
    }
    .lock-icon { font-size: 44px; margin-bottom: 16px; display: block; }
    .lock-title { font-size: 22px; font-weight: 700; color: #f1f5f9; margin-bottom: 6px; }
    .lock-sub { font-size: 13px; color: #475569; margin-bottom: 0; }

    /* Hero header */
    .hero {
        background: rgba(255,255,255,0.03);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05);
        position: relative;
        overflow: hidden;
    }
    .hero::before {
        content: '';
        position: absolute;
        top: -60px; right: -60px;
        width: 200px; height: 200px;
        background: radial-gradient(circle, rgba(56,189,248,0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-title {
        font-size: 22px; font-weight: 700;
        color: #f1f5f9; margin: 0 0 4px 0;
        letter-spacing: -0.3px;
    }
    .hero-sub { font-size: 12px; color: #334155; margin: 0; }
    .hero-badge {
        display: inline-flex; align-items: center; gap: 5px;
        background: rgba(56,189,248,0.1);
        border: 1px solid rgba(56,189,248,0.2);
        border-radius: 20px; padding: 4px 10px;
        font-size: 10px; font-weight: 600;
        color: #38bdf8; margin-top: 12px;
        letter-spacing: 0.3px;
    }

    /* Metric chips */
    .chip-row { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .chip {
        flex: 1; min-width: 120px;
        background: rgba(255,255,255,0.03);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.04);
        transition: border-color 0.2s;
    }
    .chip:hover { border-color: rgba(56,189,248,0.2); }
    .chip-label {
        font-size: 10px; font-weight: 600; color: #334155;
        text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 6px;
    }
    .chip-value { font-size: 16px; font-weight: 700; color: #38bdf8; }
    .chip-value-green { font-size: 16px; font-weight: 700; color: #34d399; }
    .chip-value-amber { font-size: 16px; font-weight: 700; color: #fbbf24; }

    /* Glass card wrapper */
    .glass-card {
        background: rgba(255,255,255,0.03);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 16px;
        padding: 20px 22px;
        margin-bottom: 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.04);
    }

    /* Section labels */
    .sec-label {
        font-size: 10px; font-weight: 700; color: #1e3a5f;
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;
    }
    .sec-title { font-size: 15px; font-weight: 700; color: #cbd5e1; margin: 0 0 2px 0; }
    .sec-sub { font-size: 11px; color: #334155; margin: 0 0 14px 0; }

    /* Glow divider */
    .gdivider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(56,189,248,0.15), transparent);
        margin: 22px 0;
    }

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        color: #e2e8f0 !important;
        border-radius: 10px !important;
        font-size: 13px !important;
        backdrop-filter: blur(8px) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
        border-color: rgba(56,189,248,0.4) !important;
        box-shadow: 0 0 0 2px rgba(56,189,248,0.08) !important;
    }
    .stTextInput label, .stNumberInput label, .stTextArea label,
    .stSelectbox label, .stCheckbox label {
        color: #475569 !important; font-size: 11px !important; font-weight: 600 !important;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        color: #e2e8f0 !important; border-radius: 10px !important;
    }

    /* Buttons */
    .stButton > button {
        background: rgba(29,78,216,0.8) !important;
        backdrop-filter: blur(8px) !important;
        color: white !important; border: 1px solid rgba(59,130,246,0.4) !important;
        border-radius: 10px !important; font-weight: 600 !important;
        font-size: 13px !important; padding: 9px 20px !important;
        width: 100%; transition: all 0.2s !important;
        box-shadow: 0 2px 8px rgba(29,78,216,0.3) !important;
    }
    .stButton > button:hover {
        background: rgba(37,99,235,0.9) !important;
        box-shadow: 0 4px 16px rgba(29,78,216,0.5) !important;
    }
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.03) !important;
        color: #475569 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        box-shadow: none !important;
    }

    /* Download buttons */
    .stDownloadButton > button {
        background: rgba(255,255,255,0.04) !important;
        backdrop-filter: blur(8px) !important;
        color: #38bdf8 !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        border-radius: 10px !important; font-size: 13px !important;
        font-weight: 600 !important; padding: 9px 20px !important;
        width: 100% !important;
        box-shadow: 0 0 12px rgba(56,189,248,0.05) !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton > button:hover {
        border-color: rgba(56,189,248,0.4) !important;
        box-shadow: 0 0 20px rgba(56,189,248,0.12) !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.03) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 12px !important;
        color: #94a3b8 !important;
        font-size: 13px !important; font-weight: 600 !important;
        transition: border-color 0.2s !important;
    }
    .streamlit-expanderHeader:hover { border-color: rgba(56,189,248,0.2) !important; }
    .streamlit-expanderContent {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        padding: 18px !important;
        backdrop-filter: blur(12px) !important;
    }

    /* Dataframe */
    div[data-testid="stDataFrame"] {
        border-radius: 12px; overflow: hidden;
        border: 1px solid rgba(255,255,255,0.07);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        backdrop-filter: blur(8px);
    }

    /* Alerts */
    div[data-testid="stSuccess"] {
        background: rgba(16,185,129,0.08) !important;
        border: 1px solid rgba(16,185,129,0.2) !important;
        border-radius: 10px !important; color: #34d399 !important;
        font-size: 13px !important; backdrop-filter: blur(8px) !important;
    }
    div[data-testid="stError"] {
        background: rgba(239,68,68,0.08) !important;
        border: 1px solid rgba(239,68,68,0.2) !important;
        border-radius: 10px !important; color: #f87171 !important;
        font-size: 13px !important; backdrop-filter: blur(8px) !important;
    }

    /* Footer */
    .foot {
        text-align: center; font-size: 11px; color: #1e293b;
        margin-top: 32px; padding-top: 20px;
        border-top: 1px solid rgba(255,255,255,0.04);
    }
    </style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_num(val):
    return f"{int(val):,}" if val == int(val) else f"{val:,.2f}"

def format_date(dt):
    d = dt.day
    sfx = 'th' if 11 <= d <= 13 else {1:'st',2:'nd',3:'rd'}.get(d%10,'th')
    return f"{d}{sfx} {dt.strftime('%b %Y')}"


# ── Google Sheets ─────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_sheet():
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(st.secrets["sheet"]["name"])

def ensure_ws(sheet, title):
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=1, cols=2)

def load_cell(sheet, ws_title, default):
    ws  = ensure_ws(sheet, ws_title)
    val = ws.cell(1, 1).value
    if val:
        try: return json.loads(val)
        except: return default
    return default

def save_cell(sheet, ws_title, value):
    ensure_ws(sheet, ws_title).update("A1", [[json.dumps(value)]])

def load_all(sheet):
    settings = load_cell(sheet, "settings", {
        "start_date": "2026-08-17", "base_monthly": 1000,
        "admin_fee_percentage": 0.0,
        "names_input": "Alice, Bob, Charlie, Diana, Frank, Grace",
    })
    return (
        settings,
        load_cell(sheet, "tiers", {}),
        load_cell(sheet, "payments", {}),
        load_cell(sheet, "payout_status", {}),
    )

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


# ── connect ───────────────────────────────────────────────────────────────────
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
    st.markdown('<div class="lock-outer">', unsafe_allow_html=True)
    st.markdown("""
        <div class="lock-card">
            <span class="lock-icon">💸</span>
            <div class="lock-title">Susu Savings</div>
            <div class="lock-sub">Enter your passcode to continue</div>
        </div>
    """, unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        pw = st.text_input("p", type="password", label_visibility="collapsed", placeholder="Passcode…")
        if st.button("Unlock →"):
            if pw == ADMIN_PW:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect passcode.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# ── derive ────────────────────────────────────────────────────────────────────
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

today                = datetime.today()
days_passed          = (today - start_dt).days
current_elapsed_week = min(max(0, days_passed // 7) + 1 if today >= start_dt else 0, total_weeks)

total_cash_collected = sum(
    st.session_state.member_tiers.get(m, st.session_state.base_monthly) / 4.0
    * sum(1 for w in range(1, total_weeks+1) if st.session_state.payments.get(m,{}).get(str(w), False))
    for m in members
)
total_payouts_dist = sum(
    float(st.session_state.payout_status.get(f"Month {i+1}", {}).get("amount_collected", 0.0))
    for i in range(num_members)
)
total_cash_held = total_cash_collected - total_payouts_dist

members_owing = sum(
    1 for member in members
    if (current_elapsed_week - sum(
        1 for w in range(1, current_elapsed_week+1)
        if st.session_state.payments.get(member,{}).get(str(w), False)
    )) > 0
)


# ── hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
    <div class="hero">
        <div class="hero-title">💸 Susu Savings Dashboard</div>
        <div class="hero-sub">{num_members} members · {format_date(start_dt)} → {format_date(end_date)}</div>
        <div class="hero-badge">🔓 &nbsp;Admin session active</div>
    </div>
    <div class="chip-row">
        <div class="chip">
            <div class="chip-label">Cash Held</div>
            <div class="chip-value">GHS {fmt_num(total_cash_held)}</div>
        </div>
        <div class="chip">
            <div class="chip-label">Week</div>
            <div class="chip-value">{current_elapsed_week} / {total_weeks}</div>
        </div>
        <div class="chip">
            <div class="chip-label">Owing</div>
            <div class="chip-value-amber">{members_owing} member{'s' if members_owing != 1 else ''}</div>
        </div>
        <div class="chip">
            <div class="chip-label">Admin Fee</div>
            <div class="chip-value-green">{fmt_num(st.session_state.admin_fee_percentage)}%</div>
        </div>
    </div>
""", unsafe_allow_html=True)


# ── build data ────────────────────────────────────────────────────────────────
schedule_data, wa_payout_rows = [], []
cur_date = start_dt
for i in range(num_members):
    month_lbl    = f"Month {i+1}"
    recipient    = members[i]
    payout_date  = cur_date + timedelta(weeks=4)
    rec_monthly  = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    gross_pool   = rec_monthly * num_members
    admin_fee_v  = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
    net_pool_amt = gross_pool - admin_fee_v
    collected    = float(st.session_state.payout_status.get(month_lbl, {}).get("amount_collected", 0.0))
    remaining    = max(0.0, net_pool_amt - collected)
    is_next      = (i == current_elapsed_week // 4)
    schedule_data.append({
        "Turn": f"Month {i+1}", "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Admin Fee": f"GHS {fmt_num(admin_fee_v)}",
        "Net Pool": f"GHS {fmt_num(net_pool_amt)}",
        "Collected": f"GHS {fmt_num(collected)}",
        "Remaining": f"GHS {fmt_num(remaining)}",
    })
    wa_payout_rows.append({"recipient": recipient, "date": format_date(payout_date), "balance": fmt_num(remaining)})
    cur_date = payout_date

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


# ── contributions ─────────────────────────────────────────────────────────────
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<p class="sec-label">Members</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-title">Contributions</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-sub">Weekly targets, progress and payment standing</p>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(contrib_data), use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)


# ── payout schedule ───────────────────────────────────────────────────────────
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<p class="sec-label">Rotation</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-title">Payout Schedule</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-sub">Dates, admin fees and pool balance per turn</p>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(schedule_data), use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)


# ── exports ───────────────────────────────────────────────────────────────────
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
ob_date = start_dt
for i in range(num_members):
    recipient    = members[i]
    payout_date  = ob_date + timedelta(weeks=4)
    rec_monthly  = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    net_pool_amt = (rec_monthly * num_members) * (1 - st.session_state.admin_fee_percentage / 100.0)
    ob.write(f"*Month {i+1} — {recipient}*\n")
    ob.write(f"  • Payout Date: {format_date(payout_date)}\n")
    ob.write(f"  • Net Pool: GHS {fmt_num(net_pool_amt)}\n\n")
    ob_date = payout_date

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<p class="sec-label">Export</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-title">WhatsApp Messages</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-sub">Ready-to-paste updates for the group chat</p>', unsafe_allow_html=True)
col_dl1, col_dl2 = st.columns(2)
with col_dl1:
    st.download_button("📥  Weekly Update", data=buf.getvalue(), file_name=f"Susu_W{current_elapsed_week}.txt", mime="text/plain")
with col_dl2:
    st.download_button("📋  Onboarding Details", data=ob.getvalue(), file_name="Susu_Onboarding.txt", mime="text/plain")
st.markdown('</div>', unsafe_allow_html=True)


# ── admin panel ───────────────────────────────────────────────────────────────
st.markdown('<p class="sec-label" style="margin-top:24px">Admin</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-title">Group Controls</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-sub">Update settings, record payments and payouts</p>', unsafe_allow_html=True)

with st.expander("⚙️  Group Settings"):
    c1, c2, c3 = st.columns(3)
    with c1: new_start = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    with c2: new_base  = st.number_input("Base Monthly (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    with c3: new_fee   = st.number_input("Admin Fee (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    new_names = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
    if st.button("Save Settings", key="save_settings"):
        st.session_state.start_date           = new_start
        st.session_state.base_monthly         = new_base
        st.session_state.admin_fee_percentage = new_fee
        st.session_state.names_input          = new_names
        save_all(gsheet)
        st.success("✓ Settings saved.")
        st.rerun()

with st.expander("💰  Custom Member Tiers"):
    tier_cols = st.columns(min(num_members, 4))
    new_tiers = {}
    for idx, m in enumerate(members):
        with tier_cols[idx % 4]:
            new_tiers[m] = st.number_input(m, value=float(st.session_state.member_tiers.get(m, st.session_state.base_monthly)), step=50.0, key=f"tier_{m}")
    if st.button("Save Tiers", key="save_tiers"):
        st.session_state.member_tiers = new_tiers
        save_all(gsheet)
        st.success("✓ Tiers saved.")
        st.rerun()

with st.expander("📝  Record Weekly Payment"):
    pc1, pc2 = st.columns(2)
    with pc1: sel_member = st.selectbox("Member", members, key="pay_member")
    with pc2: sel_week   = st.selectbox("Week", list(range(1, total_weeks+1)), key="pay_week")
    cur_status = st.session_state.payments.get(sel_member, {}).get(str(sel_week), False)
    chk = st.checkbox(f"Mark Week {sel_week} as paid", value=cur_status, key="pay_chk")
    if st.button("Save Payment", key="save_payment"):
        st.session_state.payments[sel_member][str(sel_week)] = chk
        save_all(gsheet)
        st.success(f"✓ Week {sel_week} for {sel_member} saved.")
        st.rerun()

with st.expander("🎁  Record Payout"):
    month_options = [f"Month {i+1} — {members[i]}" for i in range(num_members)]
    sel_month_lbl = st.selectbox("Payout Turn", month_options, key="payout_month")
    mkey          = sel_month_lbl.split(" —")[0]
    rec_idx       = int(mkey.split(" ")[1]) - 1
    rec_name      = members[rec_idx]
    rec_monthly_v = st.session_state.member_tiers.get(rec_name, st.session_state.base_monthly)
    net_v         = rec_monthly_v * num_members * (1 - st.session_state.admin_fee_percentage / 100.0)
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
        st.success(f"✓ Payout for {rec_name} saved.")
        st.rerun()

# ── logout ────────────────────────────────────────────────────────────────────
st.markdown('<div class="gdivider"></div>', unsafe_allow_html=True)
if st.button("🔒  Lock Dashboard", key="logout", type="secondary"):
    st.session_state.authenticated = False
    st.rerun()

st.markdown('<div class="foot">Backed by Google Sheets · Secured with passcode</div>', unsafe_allow_html=True)
