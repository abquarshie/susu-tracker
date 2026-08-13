import streamlit as st
from datetime import datetime, timedelta
import json
import os

# Page Configuration
st.set_page_config(
    page_title="Group Savings Tracker", 
    page_icon="💰", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean layout, compact dark metrics, and mobile sidebar behavior
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    h1, h2, h3 {
        color: #1f2937;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    div[data-testid="stMetric"] {
        background-color: #1f2937 !important;
        border: 1px solid #374151;
        padding: 10px 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetric"] label {
        color: #9ca3af !important;
        font-weight: 600;
        font-size: 13px !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 20px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Helper function for clean date formatting
def format_date(dt):
    day = dt.day
    if 11 <= day <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return f"{day}{suffix} {dt.strftime('%b %Y')}"

# File storage for persistence across relaunches
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
        "admin_fee_amount": 0.0,
        "names_input": "Alice, Bob, Charlie, Diana",
        "member_tiers": {},
        "payments": {},
        "payout_status": {}
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Load saved settings
saved_data = load_data()

# App Header
st.title("Group Savings Dashboard")
st.markdown("Track flexible contributions, total cash held, and payout rotations easily.")
st.markdown("---")

# --- ADMIN SECURITY LOGIN IN SIDEBAR ---
st.sidebar.header("⚙️ Admin Panel")
admin_password_input = st.sidebar.text_input("Admin Passcode", type="password", placeholder="Enter passcode to edit")

ADMIN_SECRET = "Susu2026" 
is_admin = (admin_password_input == ADMIN_SECRET)

if not is_admin:
    st.sidebar.markdown("---")
    st.sidebar.info("🔒 **View-Only Mode**\n\nEnter the correct Admin Passcode above to unlock settings and record payments.")

# Process core group variables from saved file
start_date_str = saved_data["start_date"]
base_monthly = float(saved_data.get("base_monthly_amount", 1000))
admin_fee_amount = float(saved_data.get("admin_fee_amount", 0.0))
names_input = saved_data["names_input"]

members = [n.strip() for n in names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("⚠️ Please enter at least 2 participant names in the sidebar.")
    st.stop()

# Initialize or clean member tiers dictionary
member_tiers = saved_data.get("member_tiers", {})
for m in members:
    if m not in member_tiers:
        member_tiers[m] = base_monthly

if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Edit Group Settings")
    start_date_str = st.sidebar.text_input("Start Date (YYYY-MM-DD)", value=saved_data["start_date"])
    base_monthly = st.sidebar.number_input("Standard Base Monthly Target (GH₵)", value=base_monthly, step=50.0)
    admin_fee_amount = st.sidebar.number_input("Admin Holding Fee per Payout (GH₵)", value=admin_fee_amount, min_value=0.0, step=10.0)
    names_input = st.sidebar.text_area("Participant Names (comma-separated)", value=saved_data["names_input"])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Custom Monthly Tiers per Member")
    updated_tiers = {}
    for m in members:
        current_val = float(member_tiers.get(m, base_monthly))
        updated_tiers[m] = st.sidebar.number_input(f"{m}'s Monthly Contribution (GH₵)", value=current_val, step=50.0, key=f"tier_{m}")
    member_tiers = updated_tiers

total_months = num_members
total_weeks = total_months * 4  # 4 weeks per month block

try:
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
except ValueError:
    st.error("⚠️ Incorrect date format. Use YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

# Initialize data states if members changed or file is fresh
payments = saved_data.get("payments", {})
if not payments or list(payments.keys()) != members:
    payments = {m: {str(w): False for w in range(1, total_weeks + 1)} for m in members}

payout_status = saved_data.get("payout_status", {})
if not payout_status:
    payout_status = {f"Month {i+1}": {"amount_collected": 0.0, "balance_left": 0.0} for i in range(num_members)}

# --- ADMIN ACTIONS (Only shown if password matches) ---
if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Record Weekly Payment")
    selected_member = st.sidebar.selectbox("Select Member", members)
    selected_week = st.sidebar.selectbox("Select Week Number", list(range(1, total_weeks + 1)))

    current_w_status = payments.get(selected_member, {}).get(str(selected_week), False)
    weekly_check = st.sidebar.checkbox(f"Has {selected_member} paid for Week {selected_week}?", value=current_w_status)

    if st.sidebar.button("Save Weekly Payment", type="primary"):
        if selected_member not in payments:
            payments[selected_member] = {}
        payments[selected_member][str(selected_week)] = weekly_check
        
        new_data = {
            "start_date": start_date_str,
            "base_monthly_amount": base_monthly,
            "admin_fee_amount": admin_fee_amount,
            "names_input": names_input,
            "member_tiers": member_tiers,
            "payments": payments,
            "payout_status": payout_status
        }
        save_data(new_data)
        st.sidebar.success("Weekly payment updated!")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Record Payout Collection")
    month_options = [f"Month {i+1} ({members[i]})" for i in range(num_members)]
    selected_month_label = st.sidebar.selectbox("Select Payout Turn", month_options)
    month_key = selected_month_label.split(" (")[0]

    current_p_info = payout_status.get(month_key, {"amount_collected": 0.0, "balance_left": 0.0})
    
    recipient_idx = int(month_key.split(" ")[1]) - 1
    recipient_name = members[recipient_idx]
    rec_monthly = member_tiers.get(recipient_name, base_monthly)
    max_possible_pool = rec_monthly * num_members

    input_collected = st.sidebar.number_input("Amount Collected (GH₵)", value=float(current_p_info.get("amount_collected", 0.0)), min_value=0.0, max_value=float(max_possible_pool), step=50.0)
    input_left = st.sidebar.number_input("Amount Left Behind (GH₵)", value=float(current_p_info.get("balance_left", 0.0)), min_value=0.0, max_value=float(max_possible_pool), step=50.0)

    if st.sidebar.button("Save Payout Amounts", type="secondary"):
        if month_key not in payout_status:
            payout_status[month_key] = {}
        payout_status[month_key]["amount_collected"] = input_collected
        payout_status[month_key]["balance_left"] = input_left
        
        new_data = {
            "start_date": start_date_str,
            "base_monthly_amount": base_monthly,
            "admin_fee_amount": admin_fee_amount,
            "names_input": names_input,
            "member_tiers": member_tiers,
            "payments": payments,
            "payout_status": payout_status
        }
        save_data(new_data)
        st.sidebar.success("Payout amounts updated!")

# Auto-save settings state
current_settings = {
    "start_date": start_date_str,
    "base_monthly_amount": base_monthly,
    "admin_fee_amount": admin_fee_amount,
    "names_input": names_input,
    "member_tiers": member_tiers,
    "payments": payments,
    "payout_status": payout_status
}
save_data(current_settings)

# --- CALCULATE CURRENT ELAPSED WEEKS & TOTAL CASH HELD ---
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

total_payouts_distributed = 0.0
for i in range(num_members):
    m_lbl = f"Month {i+1}"
    p_info = payout_status.get(m_lbl, {"amount_collected": 0.0, "balance_left": 0.0})
    collected_amt = float(p_info.get("amount_collected", 0.0))
    total_payouts_distributed += collected_amt

total_cash_held = total_cash_collected - total_payouts_distributed

# Top Metrics Overview
col1, col2, col3 = st.columns(3)
col1.metric("Total Cash Held", f"GH₵ {total_cash_held:,.2f}")
col2.metric("Group Size", f"{num_members} People")
col3.metric("Program End Date", format_date(end_date))

st.markdown("")
st.markdown("### 📅 Payout")
st.markdown("Tracks payout rotation dates and exact collection amounts.")

schedule = []
current_date = start_dt
for i in range(num_members):
    month_lbl = f"Month {i+1}"
    recipient = members[i]
    payout_date = current_date + timedelta(weeks=4)
    
    rec_monthly = member_tiers.get(recipient, base_monthly)
    pool_amount = rec_monthly * num_members
    
    p_info = payout_status.get(month_lbl, {"amount_collected": 0.0, "balance_left": 0.0})
    collected_amt = float(p_info.get("amount_collected", 0.0))
    left_amt = float(p_info.get("balance_left", 0.0))

    schedule.append({
        "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Total Pool": f"GH₵ {pool_amount:,.2f}",
        "Amount Collected": f"GH₵ {collected_amt:,.2f}",
        "Amount Left": f"GH₵ {left_amt:,.2f}"
    })
    current_date = payout_date

st.dataframe(schedule, use_container_width=True, hide_index=True)

st.markdown("### 📊 Contributions")
st.markdown("Overview of member contribution tiers and payment statuses.")

table_data = []
for member in members:
    m_monthly = member_tiers.get(member, base_monthly)
    m_weekly = m_monthly / 4.0
    
    member_payments = payments.get(member, {})
    paid_passed_weeks = sum(1 for w in range(1, current_elapsed_week + 1) if member_payments.get(str(w), False))
    unpaid_passed_weeks = current_elapsed_week - paid_passed_weeks
    owing_amount = unpaid_passed_weeks * m_weekly
    
    total_paid_all = sum(1 for w in range(1, total_weeks + 1) if member_payments.get(str(w), False))
    
    if owing_amount > 0:
        status_text = f"🔴 Owing GH₵ {owing_amount:,.2f}"
    else:
        status_text = "🟢 Up to Date"
    
    row = {
        "Member": member, 
        "Monthly Tier": f"GH₵ {m_monthly:,.2f}",
        "Weekly Target": f"GH₵ {m_weekly:,.2f} / wk",
        "Progress": f"{total_paid_all} / {total_weeks} weeks paid",
        "Status": status_text
    }
    table_data.append(row)

st.dataframe(table_data, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("🔒 *Note: This dashboard is simplified for participants. Administrative passcode required only in the sidebar for updating records or settings.*")
