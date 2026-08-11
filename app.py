import streamlit as st
from datetime import datetime, timedelta
import json
import os

# Page Configuration
st.set_page_config(
    page_title="Group Savings Tracker", 
    page_icon="💰", 
    layout="centered"
)

# Custom CSS for compact dark metric cards and clean UI design
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
        "start_date": "2026-08-12",
        "weekly_amount": 250,
        "names_input": "Alice, Bob, Charlie, Diana",
        "payments": {}
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Load saved settings
saved_data = load_data()

# App Header
st.title("Group Savings Dashboard")
st.markdown("Track weekly contributions, payout rotations, and live member balances easily.")
st.markdown("---")

# --- ADMIN PANEL ---
st.sidebar.header("⚙️ Admin Controls")
st.sidebar.markdown("Manage group settings and check off weekly collections.")

start_date_str = st.sidebar.text_input("Start Date (YYYY-MM-DD)", value=saved_data["start_date"])
weekly_amount = st.sidebar.number_input("Weekly Contribution (GH₵)", value=float(saved_data["weekly_amount"]))
names_input = st.sidebar.text_area("Participant Names (comma-separated)", value=saved_data["names_input"])

members = [n.strip() for n in names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 4:
    st.error("⚠️ Please enter at least 4 participant names in the sidebar.")
    st.stop()

total_weeks = num_members * num_members

try:
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
except ValueError:
    st.error("⚠️ Incorrect date format. Use YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

# Initialize payment records if members changed or file is fresh
payments = saved_data.get("payments", {})
if not payments or list(payments.keys()) != members:
    payments = {m: {str(w): False for w in range(1, total_weeks + 1)} for m in members}

st.sidebar.markdown("---")
st.sidebar.subheader("Record Payment")
selected_member = st.sidebar.selectbox("Select Member", members)
selected_week = st.sidebar.selectbox("Select Week Number", list(range(1, total_weeks + 1)))

current_status = payments.get(selected_member, {}).get(str(selected_week), False)
payment_status = st.sidebar.checkbox(f"Has {selected_member} paid for Week {selected_week}?", value=current_status)

if st.sidebar.button("Save Payment Status", type="primary"):
    if selected_member not in payments:
        payments[selected_member] = {}
    payments[selected_member][str(selected_week)] = payment_status
    
    # Save everything permanently to disk
    new_data = {
        "start_date": start_date_str,
        "weekly_amount": weekly_amount,
        "names_input": names_input,
        "payments": payments
    }
    save_data(new_data)
    st.sidebar.success("Successfully updated and saved!")

# Auto-save settings if admin changes them
current_settings = {
    "start_date": start_date_str,
    "weekly_amount": weekly_amount,
    "names_input": names_input,
    "payments": payments
}
save_data(current_settings)

# --- CALCULATE CURRENT ELAPSED WEEKS ---
today = datetime.today()
days_passed = (today - start_dt).days
current_elapsed_week = max(0, days_passed // 7) + 1 if today >= start_dt else 0
current_elapsed_week = min(current_elapsed_week, total_weeks)

# Top Metrics Overview
col1, col2, col3 = st.columns(3)
col1.metric("Group Size", f"{num_members} People")
col2.metric("Current Week Reached", f"Week {current_elapsed_week} of {total_weeks}")
col3.metric("Program End Date", format_date(end_date))

st.markdown("")
st.markdown("### 📅 Payout Schedule & Recipients")
st.markdown("This timeline shows when each person collects the complete monthly pool.")

schedule = []
current_date = start_dt
for i in range(num_members):
    recipient = members[i]
    payout_date = current_date + timedelta(weeks=num_members)
    pool_amount = weekly_amount * num_members * num_members
    schedule.append({
        "Month Block": f"Month {i+1}",
        "Recipient": recipient,
        "Cycle Start": format_date(current_date),
        "Payout Date": format_date(payout_date),
        "Total Pool": f"GH₵ {pool_amount:,.2f}"
    })
    current_date = payout_date

st.dataframe(schedule, use_container_width=True, hide_index=True)

st.markdown("### 📊 Member Balances & Weekly Logs")
st.markdown("Real-time view showing arrears based on weeks that have actually passed.")

table_data = []
for member in members:
    member_payments = payments.get(member, {})
    paid_passed_weeks = sum(1 for w in range(1, current_elapsed_week + 1) if member_payments.get(str(w), False))
    unpaid_passed_weeks = current_elapsed_week - paid_passed_weeks
    owing_amount = unpaid_passed_weeks * weekly_amount
    
    total_paid_all = sum(1 for w in range(1, total_weeks + 1) if member_payments.get(str(w), False))
    
    if owing_amount > 0:
        status_text = f"🔴 Owing GH₵ {owing_amount:,.2f}"
    else:
        status_text = "🟢 Up to Date"
    
    row = {
        "Member": member, 
        "Total Paid": f"{total_paid_all} / {total_weeks} weeks", 
        "Account Status": status_text
    }
    for w in range(1, total_weeks + 1):
        row[f"W{w}"] = "Paid" if member_payments.get(str(w), False) else "-"
    table_data.append(row)

st.dataframe(table_data, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("🔒 *Note: This link is view-only for group participants. Only the group administrator can modify payment records via the secure sidebar.*")
