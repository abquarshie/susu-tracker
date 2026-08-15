import streamlit as st
from datetime import datetime, timedelta
import json
import os

# Page Configuration
st.set_page_config(
    page_title="Susu Tracker",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Hide Streamlit chrome */
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    .stDeployButton {display: none !important;}
    footer {visibility: hidden !important;}
    .block-container {padding-top: 2rem !important; padding-bottom: 3rem !important;}

    /* Base — dark mode */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .main {background-color: #0f1117 !important;}
    .stApp {background-color: #0f1117 !important;}

    /* Page title area — lighter, glassy */
    .page-header {
        background: linear-gradient(135deg, #1e293b 0%, #2d3f58 100%);
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 24px 28px;
        margin-bottom: 20px;
        color: white;
    }
    .page-header h1 {
        font-size: 22px;
        font-weight: 700;
        color: #f1f5f9 !important;
        margin: 0 0 4px 0;
        letter-spacing: -0.3px;
    }
    .page-header p {
        font-size: 13px;
        color: #64748b;
        margin: 0;
        font-weight: 400;
    }

    /* Metric cards — compact dark */
    div[data-testid="stMetric"] {
        background: #1e293b !important;
        border: 1px solid #2d3748 !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        box-shadow: none !important;
    }
    div[data-testid="stMetric"] label {
        color: #64748b !important;
        font-weight: 500 !important;
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }

    /* Section headings */
    .section-label {
        font-size: 11px;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin: 24px 0 2px 0;
    }
    .section-title {
        font-size: 18px;
        font-weight: 700;
        color: #e2e8f0;
        margin: 0 0 3px 0;
    }
    .section-subtitle {
        font-size: 12px;
        color: #475569;
        margin: 0 0 14px 0;
    }

    /* Dataframe */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #2d3748;
        box-shadow: none;
    }

    /* Divider */
    .divider {
        height: 1px;
        background: #1e293b;
        margin: 24px 0;
    }

    /* Sidebar — unchanged dark style */
    section[data-testid="stSidebar"] {
        background: #0f172a !important;
    }
    section[data-testid="stSidebar"] * {
        color: #cbd5e1 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #f1f5f9 !important;
    }
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stTextArea textarea {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f1f5f9 !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] .stSelectbox select {
        background: #1e293b !important;
        color: #f1f5f9 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: #3b82f6 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background: #1e293b !important;
        color: #94a3b8 !important;
        border: 1px solid #334155 !important;
    }

    /* Footer */
    .footer-note {
        text-align: center;
        font-size: 12px;
        color: #334155;
        margin-top: 32px;
        padding-top: 20px;
        border-top: 1px solid #1e293b;
    }
    </style>
""", unsafe_allow_html=True)


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
    return {
        "start_date": "2026-08-17",
        "base_monthly_amount": 1000,
        "admin_fee_percentage": 0.0,
        "names_input": "Alice, Bob, Charlie, Diana",
        "member_tiers": {},
        "payments": {},
        "payout_status": {}
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


saved_data = load_data()

# --- SIDEBAR ADMIN ---
st.sidebar.header("⚙️ Admin Panel")
admin_password_input = st.sidebar.text_input("Passcode", type="password", placeholder="Enter to unlock")

ADMIN_SECRET = "Susu2026"
is_admin = (admin_password_input == ADMIN_SECRET)

if not is_admin:
    st.sidebar.markdown("---")
    st.sidebar.info("🔒 **View-Only Mode**\n\nEnter the passcode above to unlock settings and record payments.")

start_date_str = saved_data["start_date"]
base_monthly = float(saved_data.get("base_monthly_amount", 1000))
admin_fee_percentage = float(saved_data.get("admin_fee_percentage", 0.0))
names_input = saved_data["names_input"]

members = [n.strip() for n in names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("⚠️ Please enter at least 2 participant names.")
    st.stop()

member_tiers = saved_data.get("member_tiers", {})
for m in members:
    if m not in member_tiers:
        member_tiers[m] = base_monthly

if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Group Settings")
    start_date_str = st.sidebar.text_input("Start Date (YYYY-MM-DD)", value=saved_data["start_date"])
    base_monthly = st.sidebar.number_input("Base Monthly Target (GH₵)", value=base_monthly, step=50.0)
    admin_fee_percentage = st.sidebar.number_input("Admin Fee per Payout (%)", value=admin_fee_percentage, min_value=0.0, max_value=100.0, step=0.5)
    names_input = st.sidebar.text_area("Members (comma-separated)", value=saved_data["names_input"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("Monthly Tiers")
    updated_tiers = {}
    for m in members:
        current_val = float(member_tiers.get(m, base_monthly))
        updated_tiers[m] = st.sidebar.number_input(f"{m} (GH₵)", value=current_val, step=50.0, key=f"tier_{m}")
    member_tiers = updated_tiers

total_weeks = num_members * 4

try:
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
except ValueError:
    st.error("⚠️ Date format must be YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

payments = saved_data.get("payments", {})
if not payments or list(payments.keys()) != members:
    payments = {m: {str(w): False for w in range(1, total_weeks + 1)} for m in members}

payout_status = saved_data.get("payout_status", {})
if not payout_status:
    payout_status = {f"Month {i+1}": {"amount_collected": 0.0} for i in range(num_members)}

if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Record Payment")
    selected_member = st.sidebar.selectbox("Member", members)
    selected_week = st.sidebar.selectbox("Week", list(range(1, total_weeks + 1)))
    current_w_status = payments.get(selected_member, {}).get(str(selected_week), False)
    weekly_check = st.sidebar.checkbox(f"Week {selected_week} paid?", value=current_w_status)

    if st.sidebar.button("Save Payment", type="primary"):
        if selected_member not in payments:
            payments[selected_member] = {}
        payments[selected_member][str(selected_week)] = weekly_check
        save_data({
            "start_date": start_date_str,
            "base_monthly_amount": base_monthly,
            "admin_fee_percentage": admin_fee_percentage,
            "names_input": names_input,
            "member_tiers": member_tiers,
            "payments": payments,
            "payout_status": payout_status
        })
        st.sidebar.success("✓ Payment saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Record Payout")
    month_options = [f"Month {i+1} — {members[i]}" for i in range(num_members)]
    selected_month_label = st.sidebar.selectbox("Payout Turn", month_options)
    month_key = selected_month_label.split(" —")[0]

    current_p_info = payout_status.get(month_key, {"amount_collected": 0.0})
    recipient_idx = int(month_key.split(" ")[1]) - 1
    recipient_name = members[recipient_idx]
    rec_monthly = member_tiers.get(recipient_name, base_monthly)
    gross_pool = rec_monthly * num_members
    fee_val = gross_pool * (admin_fee_percentage / 100.0)
    net_pool = gross_pool - fee_val

    input_collected = st.sidebar.number_input("Amount Collected (GH₵)", value=float(current_p_info.get("amount_collected", 0.0)), min_value=0.0, max_value=float(net_pool), step=50.0)

    if st.sidebar.button("Save Payout", type="secondary"):
        if month_key not in payout_status:
            payout_status[month_key] = {}
        payout_status[month_key]["amount_collected"] = input_collected
        save_data({
            "start_date": start_date_str,
            "base_monthly_amount": base_monthly,
            "admin_fee_percentage": admin_fee_percentage,
            "names_input": names_input,
            "member_tiers": member_tiers,
            "payments": payments,
            "payout_status": payout_status
        })
        st.sidebar.success("✓ Payout saved")

# Autosave settings
save_data({
    "start_date": start_date_str,
    "base_monthly_amount": base_monthly,
    "admin_fee_percentage": admin_fee_percentage,
    "names_input": names_input,
    "member_tiers": member_tiers,
    "payments": payments,
    "payout_status": payout_status
})

# --- CALCULATIONS ---
today = datetime.today()
days_passed = (today - start_dt).days
current_elapsed_week = max(0, days_passed // 7) + 1 if today >= start_dt else 0
current_elapsed_week = min(current_elapsed_week, total_weeks)

total_cash_collected = 0.0
for m in members:
    m_monthly = member_tiers.get(m, base_monthly)
    m_weekly = m_monthly / 4.0
    m_payments = payments.get(m, {})
    paid_count = sum(1 for w in range(1, total_weeks + 1) if m_payments.get(str(w), False))
    total_cash_collected += paid_count * m_weekly

total_payouts_distributed = sum(
    float(payout_status.get(f"Month {i+1}", {}).get("amount_collected", 0.0))
    for i in range(num_members)
)
total_cash_held = total_cash_collected - total_payouts_distributed

# --- PAGE HEADER ---
st.markdown(f"""
    <div class="page-header">
        <h1>💰 Group Savings Tracker</h1>
        <p>Track contributions, payouts and balances — {num_members} members · ends {format_date(end_date)}</p>
    </div>
""", unsafe_allow_html=True)

# --- METRICS ---
col1, col2, col3 = st.columns(3)
col1.metric("Cash Held", f"GH₵ {total_cash_held:,.2f}")
col2.metric("Admin Fee", f"{admin_fee_percentage}%")
col3.metric("Program Ends", format_date(end_date))

# --- PAYOUT SCHEDULE ---
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-label">Rotation</p>', unsafe_allow_html=True)
st.markdown('<p class="section-title">Payout Schedule</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Dates, admin fee deductions and remaining pool per turn</p>', unsafe_allow_html=True)

schedule = []
current_date = start_dt
for i in range(num_members):
    month_lbl = f"Month {i+1}"
    recipient = members[i]
    payout_date = current_date + timedelta(weeks=4)

    rec_monthly = member_tiers.get(recipient, base_monthly)
    gross_pool = rec_monthly * num_members
    admin_fee_val = gross_pool * (admin_fee_percentage / 100.0)
    net_pool_amount = gross_pool - admin_fee_val

    p_info = payout_status.get(month_lbl, {"amount_collected": 0.0})
    collected_amt = float(p_info.get("amount_collected", 0.0))
    remaining_pool = max(0.0, net_pool_amount - collected_amt)

    schedule.append({
        "Turn": f"Month {i+1}",
        "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Admin Fee": f"GH₵ {admin_fee_val:,.2f}",
        "Net Pool": f"GH₵ {net_pool_amount:,.2f}",
        "Collected": f"GH₵ {collected_amt:,.2f}",
        "Remaining": f"GH₵ {remaining_pool:,.2f}",
    })
    current_date = payout_date

st.dataframe(schedule, use_container_width=True, hide_index=True)

# --- CONTRIBUTIONS ---
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<p class="section-label">Members</p>', unsafe_allow_html=True)
st.markdown('<p class="section-title">Contributions</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Tiers, progress and payment status per member</p>', unsafe_allow_html=True)

table_data = []
for member in members:
    m_monthly = member_tiers.get(member, base_monthly)
    m_weekly = m_monthly / 4.0

    member_payments = payments.get(member, {})
    paid_passed = sum(1 for w in range(1, current_elapsed_week + 1) if member_payments.get(str(w), False))
    unpaid_passed = current_elapsed_week - paid_passed
    owing = unpaid_passed * m_weekly

    total_paid_all = sum(1 for w in range(1, total_weeks + 1) if member_payments.get(str(w), False))
    pct = int((total_paid_all / total_weeks) * 100) if total_weeks > 0 else 0

    status = "🔴 Owing GH₵ {:.2f}".format(owing) if owing > 0 else "🟢 Up to Date"

    table_data.append({
        "Member": member,
        "Monthly Tier": f"GH₵ {m_monthly:,.2f}",
        "Weekly Target": f"GH₵ {m_weekly:,.2f}",
        "Weeks Paid": f"{total_paid_all} / {total_weeks}",
        "Progress": f"{pct}%",
        "Status": status,
    })

st.dataframe(table_data, use_container_width=True, hide_index=True)

st.markdown("""
    <div class="footer-note">
        🔒 View-only by default · Admin passcode required to update records
    </div>
""", unsafe_allow_html=True)
