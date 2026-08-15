import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import io
import json
import os

st.set_page_config(
    page_title="Susu Savings",
    page_icon="💸",
    layout="centered"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    .stDeployButton {display: none !important;}
    footer {visibility: hidden !important;}
    .block-container {padding-top: 1.8rem !important; padding-bottom: 3rem !important;}

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Dark background */
    .main, .stApp { background-color: #0d1117 !important; }

    /* Page header card */
    .page-header {
        background: linear-gradient(135deg, #1c2a3a 0%, #243447 100%);
        border: 1px solid #2d3f55;
        border-radius: 14px;
        padding: 22px 26px;
        margin-bottom: 18px;
    }
    .page-header h1 {
        font-size: 20px;
        font-weight: 700;
        color: #e2e8f0 !important;
        margin: 0 0 4px 0;
        letter-spacing: -0.2px;
    }
    .page-header p {
        font-size: 12px;
        color: #4a6080;
        margin: 0;
    }

    /* Compact metric strip */
    .metric-strip {
        display: flex;
        gap: 10px;
        margin-bottom: 20px;
    }
    .metric-chip {
        flex: 1;
        background: #161d27;
        border: 1px solid #1e2d3d;
        border-radius: 10px;
        padding: 10px 14px;
    }
    .metric-chip-label {
        font-size: 10px;
        font-weight: 600;
        color: #3d5a75;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-bottom: 3px;
    }
    .metric-chip-value {
        font-size: 15px;
        font-weight: 700;
        color: #38bdf8;
    }

    /* Section headers */
    .section-eyebrow {
        font-size: 10px;
        font-weight: 600;
        color: #3d5a75;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin: 26px 0 2px 0;
    }
    .section-heading {
        font-size: 16px;
        font-weight: 700;
        color: #cbd5e1;
        margin: 0 0 3px 0;
    }
    .section-sub {
        font-size: 12px;
        color: #3d5a75;
        margin: 0 0 12px 0;
    }

    /* Divider */
    .divider { height: 1px; background: #161d27; margin: 20px 0; }

    /* Download button */
    .stDownloadButton > button {
        background: #1d4ed8 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
    }
    .stDownloadButton > button:hover {
        background: #2563eb !important;
    }

    /* Info box */
    div[data-testid="stInfo"] {
        background: #161d27 !important;
        border: 1px solid #1e2d3d !important;
        border-radius: 8px !important;
        color: #64748b !important;
        font-size: 13px !important;
    }

    /* Dataframe */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #1e2d3d;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #0d1117 !important; }
    section[data-testid="stSidebar"] * { color: #94a3b8 !important; }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 { color: #e2e8f0 !important; }
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stTextArea textarea {
        background: #161d27 !important;
        border: 1px solid #1e2d3d !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: #1d4ed8 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    section[data-testid="stSidebar"] .stCheckbox label { color: #94a3b8 !important; }

    /* Footer */
    .footer-note {
        text-align: center;
        font-size: 11px;
        color: #1e2d3d;
        margin-top: 28px;
        padding-top: 16px;
        border-top: 1px solid #161d27;
    }
    </style>
""", unsafe_allow_html=True)


def fmt_num(val):
    if val == int(val):
        return f"{int(val):,}"
    return f"{val:,.2f}"

def format_date(dt):
    day = dt.day
    suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return f"{day}{suffix} {dt.strftime('%b %Y')}"


DATA_FILE = "susu_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_data(data_dict):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data_dict, f, indent=4)
    except Exception as e:
        st.error(f"Error saving data: {e}")


saved_state = load_data()

if "initialized" not in st.session_state:
    if saved_state:
        st.session_state.start_date = saved_state.get("start_date", "2026-08-17")
        st.session_state.base_monthly = saved_state.get("base_monthly", 1000)
        st.session_state.admin_fee_percentage = saved_state.get("admin_fee_percentage", 0.0)
        st.session_state.names_input = saved_state.get("names_input", "Alice, Bob, Charlie, Diana, Frank, Grace")
        st.session_state.member_tiers = saved_state.get("member_tiers", {})
        st.session_state.payments = saved_state.get("payments", {})
        st.session_state.payout_status = saved_state.get("payout_status", {})
    else:
        st.session_state.start_date = "2026-08-17"
        st.session_state.base_monthly = 1000
        st.session_state.admin_fee_percentage = 0.0
        st.session_state.names_input = "Alice, Bob, Charlie, Diana, Frank, Grace"
        st.session_state.member_tiers = {}
        st.session_state.payments = {}
        st.session_state.payout_status = {}
    st.session_state.initialized = True

def persist_current_state():
    save_data({
        "start_date": st.session_state.start_date,
        "base_monthly": st.session_state.base_monthly,
        "admin_fee_percentage": st.session_state.admin_fee_percentage,
        "names_input": st.session_state.names_input,
        "member_tiers": st.session_state.member_tiers,
        "payments": st.session_state.payments,
        "payout_status": st.session_state.payout_status
    })


# --- SIDEBAR ---
st.sidebar.header("⚙️ Group Setup & Logs")

with st.sidebar.expander("Group Settings", expanded=False):
    start_date_str = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    base_monthly = st.number_input("Base Monthly Target (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    admin_fee_percentage = st.number_input("Admin Fee per Payout (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    names_input = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
    if st.button("Save Settings"):
        st.session_state.start_date = start_date_str
        st.session_state.base_monthly = base_monthly
        st.session_state.admin_fee_percentage = admin_fee_percentage
        st.session_state.names_input = names_input
        persist_current_state()
        st.rerun()

members = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("Please enter at least 2 participant names.")
    st.stop()

for m in members:
    if m not in st.session_state.member_tiers:
        st.session_state.member_tiers[m] = st.session_state.base_monthly

with st.sidebar.expander("Custom Monthly Tiers", expanded=False):
    updated_tiers = {}
    for m in members:
        current_val = float(st.session_state.member_tiers.get(m, st.session_state.base_monthly))
        updated_tiers[m] = st.number_input(f"{m} (GHS)", value=current_val, step=50.0, key=f"tier_{m}")
    if st.button("Save Tiers"):
        st.session_state.member_tiers = updated_tiers
        persist_current_state()
        st.rerun()

total_weeks = num_members * 4

try:
    start_dt = datetime.strptime(st.session_state.start_date, '%Y-%m-%d')
except ValueError:
    st.error("Date format must be YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

if not st.session_state.payments or list(st.session_state.payments.keys()) != members:
    st.session_state.payments = {m: {str(w): False for w in range(1, total_weeks + 1)} for m in members}

if not st.session_state.payout_status:
    st.session_state.payout_status = {f"Month {i+1}": {"amount_collected": 0.0} for i in range(num_members)}

st.sidebar.markdown("---")
st.sidebar.subheader("Record Weekly Payment")
selected_member = st.sidebar.selectbox("Member", members)
selected_week = st.sidebar.selectbox("Week", list(range(1, total_weeks + 1)))
current_w_status = st.session_state.payments.get(selected_member, {}).get(str(selected_week), False)
weekly_check = st.sidebar.checkbox(f"Week {selected_week} paid?", value=current_w_status)
if st.sidebar.button("Save Payment"):
    st.session_state.payments[selected_member][str(selected_week)] = weekly_check
    persist_current_state()
    st.sidebar.success("✓ Saved")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Record Payout")
month_options = [f"Month {i+1} — {members[i]}" for i in range(num_members)]
selected_month_label = st.sidebar.selectbox("Payout Turn", month_options)
month_key = selected_month_label.split(" —")[0]
current_p_info = st.session_state.payout_status.get(month_key, {"amount_collected": 0.0})
recipient_idx = int(month_key.split(" ")[1]) - 1
recipient_name = members[recipient_idx]
rec_monthly = st.session_state.member_tiers.get(recipient_name, st.session_state.base_monthly)
gross_pool = rec_monthly * num_members
fee_val = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
net_pool = gross_pool - fee_val
input_collected = st.sidebar.number_input("Amount Collected (GHS)", value=float(current_p_info.get("amount_collected", 0.0)), min_value=0.0, max_value=float(net_pool), step=50.0)
if st.sidebar.button("Save Payout"):
    st.session_state.payout_status[month_key]["amount_collected"] = input_collected
    persist_current_state()
    st.sidebar.success("✓ Saved")
    st.rerun()


# --- CALCULATIONS ---
today = datetime.today()
days_passed = (today - start_dt).days
current_elapsed_week = max(0, days_passed // 7) + 1 if today >= start_dt else 0
current_elapsed_week = min(current_elapsed_week, total_weeks)

total_cash_collected = 0.0
for m in members:
    m_monthly = st.session_state.member_tiers.get(m, st.session_state.base_monthly)
    m_weekly = m_monthly / 4.0
    m_payments = st.session_state.payments.get(m, {})
    paid_count = sum(1 for w in range(1, total_weeks + 1) if m_payments.get(str(w), False))
    total_cash_collected += paid_count * m_weekly

total_payouts_distributed = sum(
    float(st.session_state.payout_status.get(f"Month {i+1}", {}).get("amount_collected", 0.0))
    for i in range(num_members)
)
total_cash_held = total_cash_collected - total_payouts_distributed


# --- MAIN VIEW ---
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
""", unsafe_allow_html=True)


# --- BUILD DATA ---
schedule_data = []
whatsapp_payout_rows = []
current_date = start_dt

for i in range(num_members):
    month_lbl = f"Month {i+1}"
    recipient = members[i]
    payout_date = current_date + timedelta(weeks=4)
    rec_monthly = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    gross_pool = rec_monthly * num_members
    admin_fee_val = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
    net_pool_amount = gross_pool - admin_fee_val
    p_info = st.session_state.payout_status.get(month_lbl, {"amount_collected": 0.0})
    collected_amt = float(p_info.get("amount_collected", 0.0))
    remaining_pool = max(0.0, net_pool_amount - collected_amt)

    schedule_data.append({
        "Turn": f"Month {i+1}",
        "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Admin Fee": f"GHS {fmt_num(admin_fee_val)}",
        "Net Pool": f"GHS {fmt_num(net_pool_amount)}",
        "Collected": f"GHS {fmt_num(collected_amt)}",
        "Remaining": f"GHS {fmt_num(remaining_pool)}",
    })
    whatsapp_payout_rows.append({"recipient": recipient, "date": format_date(payout_date), "balance": fmt_num(remaining_pool)})
    current_date = payout_date

contrib_data = []
whatsapp_contrib_rows = []
whatsapp_onboarding_rows = []
for member in members:
    m_monthly = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly = m_monthly / 4.0
    member_payments = st.session_state.payments.get(member, {})
    paid_passed = sum(1 for w in range(1, current_elapsed_week + 1) if member_payments.get(str(w), False))
    unpaid_passed = current_elapsed_week - paid_passed
    owing = unpaid_passed * m_weekly
    total_paid_all = sum(1 for w in range(1, total_weeks + 1) if member_payments.get(str(w), False))
    pct = int((total_paid_all / total_weeks) * 100) if total_weeks > 0 else 0
    status = f"Owing GHS {fmt_num(owing)}" if owing > 0 else "Up to date"

    contrib_data.append({
        "Member": member,
        "Monthly Tier": f"GHS {fmt_num(m_monthly)}",
        "Weekly Target": f"GHS {fmt_num(m_weekly)}",
        "Weeks Paid": f"{total_paid_all} / {total_weeks}",
        "Progress": f"{pct}%",
        "Status": ("🔴 " if owing > 0 else "🟢 ") + status,
    })
    whatsapp_contrib_rows.append({"member": member, "standing": status})
    whatsapp_onboarding_rows.append({
        "member": member,
        "monthly": fmt_num(m_monthly),
        "weekly": fmt_num(m_weekly)
    })


# --- WHATSAPP REPORTS ---
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-eyebrow">Export</p>', unsafe_allow_html=True)
st.markdown('<p class="section-heading">WhatsApp Updates</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Download ready-to-paste messages for onboarding or weekly standing updates</p>', unsafe_allow_html=True)

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    # Onboarding / Beginning Export (Monthly & Weekly Targets)
    onboard_buffer = io.StringIO()
    onboard_buffer.write("🚀 *SUSU SAVINGS - MEMBER TARGETS*\n")
    onboard_buffer.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
    onboard_buffer.write("📋 *CONTRIBUTION TARGETS*\n")
    for row in whatsapp_onboarding_rows:
        onboard_buffer.write(f"• *{row['member']}*: GHS {row['monthly']} / mo (GHS {row['weekly']} / wk)\n")
    
    st.download_button(
        label="📥 Download Onboarding Target Update",
        data=onboard_buffer.getvalue(),
        file_name="Susu_Onboarding_Targets.txt",
        mime="text/plain",
        type="primary"
    )

with col_exp2:
    # Weekly Status Update Export
    report_buffer = io.StringIO()
    report_buffer.write(f"📌 *WK {current_elapsed_week} UPDATE*\n")
    report_buffer.write(f"💰 *Cash at Hand:* GHS {fmt_num(total_cash_held)}\n")
    report_buffer.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
    report_buffer.write("👥 *MEMBERS*\n")
    for row in whatsapp_contrib_rows:
        icon = "❌" if "Owing" in row["standing"] else "✅"
        report_buffer.write(f"{icon} *{row['member']}*: {row['standing']}\n")
    report_buffer.write("\n🎁 *PAYOUTS*\n")
    for prow in whatsapp_payout_rows:
        report_buffer.write(f"{prow['recipient']} {prow['date']} - GHS {prow['balance']}\n")

    st.download_button(
        label="📥 Download Weekly Status Update",
        data=report_buffer.getvalue(),
        file_name=f"Susu_Update_W{current_elapsed_week}.txt",
        mime="text/plain",
        type="secondary"
    )

# --- TABLES ---
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-eyebrow">Rotation</p>', unsafe_allow_html=True)
st.markdown('<p class="section-heading">Payout Schedule</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Dates, fees and remaining pool per turn</p>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(schedule_data), use_container_width=True, hide_index=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-eyebrow">Members</p>', unsafe_allow_html=True)
st.markdown('<p class="section-heading">Contributions</p>', unsafe_allow_html=True)
st.markdown('<p class="section-sub">Tiers, progress and payment standing per member</p>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(contrib_data), use_container_width=True, hide_index=True)

st.markdown('<div class="footer-note">History saved locally · View-only by default</div>', unsafe_allow_html=True)
