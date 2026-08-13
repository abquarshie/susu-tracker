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
        "admin_fee_pct": 0.0,
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
admin_fee_pct = float(saved_data.get("admin_fee_pct", 0.0))
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
    admin_fee_pct = st.sidebar.number_input("Admin Holding Fee (%)", value=admin_fee_pct, min_value=0.0, max_value=20.0, step=0.5)
    names_input = st.sidebar.text_area("Participant Names (comma-separated)", value=saved_data["names_input"])
    
    # Update member tiers configuration if admin wants custom values per person
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
    payout_status = {f"Month {i+1}": {"status": "Waiting / Not Collected", "balance_left": 0.0} for i in range(num_members)}

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
            "admin_fee_pct": admin_fee_pct,
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

    current_p_info = payout_status.get(month_key, {"status": "Waiting / Not Collected", "balance_left": 0.0})
    p_status_choice = st.sidebar.selectbox(
        "Collection Status", 
        ["Waiting / Not Collected", "Partially Collected", "Fully Collected"],
        index=["Waiting / Not Collected", "Partially Collected", "Fully Collected"].index(current_p_info.get("status", "Waiting / Not Collected"))
    )

    # Calculate max pool for this specific member's month block
    recipient_idx = int(month_key.split(" ")[1]) - 1
    recipient_name = members[recipient_idx]
    rec_monthly = member_tiers.get(recipient_name, base_monthly)
    standard_full_pool = base_monthly * num_members
    member_full_pool = rec_monthly * num_members

    p_balance_left = 0.0
    if p_status_choice == "Partially Collected":
        p_balance_left = st.sidebar.number_input("Amount Left Behind (GH₵)", value=float(current_p_info.get("balance_left", 0.0)), min_value=0.0, max_value=float(member_full_pool))

    if st.sidebar.button("Save Payout Status", type="secondary"):
        if month_key not in payout_status:
            payout_status[month_key] = {}
        payout_status[month_key]["status"] = p_status_choice
        payout_status[month_key]["balance_left"] = p_balance_left
        
        new_data = {
            "start_date": start_date_str,
            "base_monthly_amount": base_monthly,
            "admin_fee_pct": admin_fee_pct,
            "names_input": names_input,
            "member_tiers": member_tiers,
            "payments": payments,
            "payout_status": payout_status
        }
        save_data(new_data)
        st.sidebar.success("Payout collection status updated!")

# Auto-save settings state
current_settings = {
    "start_date": start_date_str,
    "base_monthly_amount": base_monthly,
    "admin_fee_pct": admin_fee_pct,
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

# Calculate total cash actually paid in by all members across all weeks so far
total_cash_collected = 0.0
for m in members:
    m_monthly = member_tiers.get(m, base_monthly)
    m_weekly = m_monthly / 4.0
    m_payments = payments.get(m, {})
    paid_count = sum(1 for w in range(1, total_weeks + 1) if m_payments.get(str(w), False))
    total_cash_collected += paid_count * m_weekly

# Subtract payouts that have already been fully or partially taken out of your hands
total_payouts_distributed = 0.0
for i in range(num_members):
    m_lbl = f"Month {i+1}"
    rec_name = members[i]
    rec_monthly = member_tiers.get(rec_name, base_monthly)
    full_pool = rec_monthly * num_members
    
    p_info = payout_status.get(m_lbl, {"status": "Waiting / Not Collected", "balance_left": 0.0})
    stat = p_info.get("status", "Waiting / Not Collected")
    left_amt = p_info.get("balance_left", 0.0)
    
    if stat == "Fully Collected":
        total_payouts_distributed += full_pool
    elif stat == "Partially Collected":
        # Amount given out is full pool minus what's left behind
        total_payouts_distributed += (full_pool - left_amt)

total_cash_held = total_cash_collected - total_payouts_distributed

# Top Metrics Overview
col1, col2, col3 = st.columns(3)
col1.metric("Total Cash Held by Admin", f"GH₵ {total_cash_held:,.2f}")
col2.metric("Group Size", f"{num_members} People")
col3.metric("Program End Date", format_date(end_date))

st.markdown("")
st.markdown("### 📅 Payout Schedule & Recipients")
st.markdown("Tracks proportional monthly pools based on each member's custom contribution tier.")

schedule = []
current_date = start_dt
for i in range(num_members):
    month_lbl = f"Month {i+1}"
    recipient = members[i]
    payout_date = current_date + timedelta(weeks=4)
    
    rec_monthly = member_tiers.get(recipient, base_monthly)
    pool_amount = rec_monthly * num_members
    fee_amount = pool_amount * (admin_fee_pct / 100.0)
    net_pool_amount = pool_amount - fee_amount
    
    p_info = payout_status.get(month_lbl, {"status": "Waiting / Not Collected", "balance_left": 0.0})
    stat = p_info.get("status", "Waiting / Not Collected")
    left_amt = p_info.get("balance_left", 0.0)
    
    if stat == "Fully Collected":
        display_status = "✅ Fully Collected"
    elif stat == "Partially Collected":
        display_status = f"⏳ Partial (GH₵ {left_amt:,.2f} left)"
    else:
        display_status = "⏳ Waiting / Not Collected"
        
    pool_text = f"GH₵ {pool_amount:,.2f}"
    if admin_fee_pct > 0:
        pool_text += f" (Net: {net_pool_amount:,.2f} after {admin_fee_pct}% fee)"

    schedule.append({
        "Month Block": month_lbl,
        "Recipient": recipient,
        "Monthly Tier": f"GH₵ {rec_monthly:,.2f}",
        "Payout Date": format_date(payout_date),
        "Total Pool": pool_text,
        "Collection Status": display_status
    })
    current_date = payout_date

st.dataframe(schedule, use_container_width=True, hide_index=True)

st.markdown("### 📊 Member Balances & Weekly Logs")
st.markdown("Real-time view showing weekly breakdown and arrears based on each member's personal tier.")

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
        "Tier / Wk": f"GH₵ {m_weekly:,.2f}/wk",
        "Total Paid": f"{total_paid_all} / {total_weeks} wks", 
        "Account Status": status_text
    }
    for w in range(1, total_weeks + 1):
        row[f"W{w}"] = "Paid" if member_payments.get(str(w), False) else "-"
    table_data.append(row)

st.dataframe(table_data, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("🔒 *Note: This link is view-only for group participants. Only the group administrator can modify payment records via the secure passcode.*")
