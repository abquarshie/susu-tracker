import streamlit as st
from datetime import datetime, timedelta

# Page Configuration
st.set_page_config(
    page_title="Group Savings Tracker", 
    page_icon="💰", 
    layout="centered"
)

# Custom CSS for a clean, modern UI design
st.markdown("""
    <style>
    /* Main background and font styling */
    .main {
        background-color: #f8f9fa;
    }
    h1, h2, h3 {
        color: #1f2937;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetric"] label {
        color: #4b5563 !important;
        font-weight: 600;
    }
    /* Tables styling */
    dataframe, table {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# App Header
st.title("💰 Group Savings Dashboard")
st.markdown("Track weekly contributions, payout rotations, and live member balances easily.")
st.markdown("---")

# --- ADMIN PANEL (Sidebar for you to control the data) ---
st.sidebar.header("⚙️ Admin Controls")
st.sidebar.markdown("Manage group settings and check off weekly collections.")

start_date_str = st.sidebar.text_input("Start Date (YYYY-MM-DD)", value="2026-08-12")
weekly_amount = st.sidebar.number_input("Weekly Contribution (GH₵)", value=250)
names_input = st.sidebar.text_area("Participant Names (comma-separated)", value="Alice, Bob, Charlie, Diana")

# Process group details
members = [n.strip() for n in names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 4:
    st.error("⚠️ Please enter at least 4 participant names in the sidebar.")
    st.stop()

total_weeks = num_members * num_members

try:
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
except ValueError:
    st.error("⚠️ Incorrect date format. Use YYYY-MM-DD.")
    st.stop()

end_date = start_date + timedelta(weeks=total_weeks)

# --- SIMULATED PAYMENT STATE ---
if 'payments' not in st.session_state or st.session_state.get('last_members') != members:
    st.session_state.payments = {m: {w: False for w in range(1, total_weeks + 1)} for m in members}
    st.session_state.last_members = members

st.sidebar.markdown("---")
st.sidebar.subheader("Record Payment")
selected_member = st.sidebar.selectbox("Select Member", members)
selected_week = st.sidebar.selectbox("Select Week Number", list(range(1, total_weeks + 1)))
payment_status = st.sidebar.checkbox(f"Has {selected_member} paid for Week {selected_week}?", value=st.session_state.payments[selected_member][selected_week])

if st.sidebar.button("Save Payment Status", type="primary"):
    st.session_state.payments[selected_member][selected_week] = payment_status
    st.sidebar.success("Successfully updated!")

# --- MAIN DASHBOARD VIEW ---

# Top Metrics Overview
col1, col2, col3 = st.columns(3)
col1.metric("Group Size", f"{num_members} People")
col2.metric("Total Duration", f"{total_weeks} Weeks")
col3.metric("Program End Date", end_date.strftime('%b %d, %Y'))

st.markdown("")
st.markdown("### 📅 Payout Schedule & Recipients")
st.markdown("This timeline shows when each person collects the complete monthly pool.")

schedule = []
current_date = start_date
for i in range(num_members):
    recipient = members[i]
    payout_date = current_date + timedelta(weeks=num_members)
    pool_amount = weekly_amount * num_members * num_members
    schedule.append({
        "Month Block": f"Month {i+1}",
        "Recipient": recipient,
        "Cycle Start": current_date.strftime('%Y-%m-%d'),
        "Payout Date": payout_date.strftime('%Y-%m-%d'),
        "Total Pool": f"GH₵{pool_amount:,.2f}"
    })
    current_date = payout_date

st.table(schedule)

st.markdown("### 📊 Member Balances & Weekly Logs")
st.markdown("Real-time view of who has paid and who has outstanding balances.")

table_data = []
for member in members:
    paid_weeks = sum(1 for w in range(1, total_weeks + 1) if st.session_state.payments[member][w])
    expected_total = total_weeks * weekly_amount
    paid_amount = paid_weeks * weekly_amount
    owing_amount = expected_total - paid_amount
    
    status_text = "🟢 Fully Paid" if owing_amount == 0 else f"🔴 Owing GH₵{owing_amount:,.2f}"
    
    row = {
        "Member": member, 
        "Progress": f"{paid_weeks} / {total_weeks} weeks", 
        "Account Status": status_text
    }
    for w in range(1, total_weeks + 1):
        row[f"W{w}"] = "Paid" if st.session_state.payments[member][w] else "-"
    table_data.append(row)

st.dataframe(table_data, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("🔒 *Note: This link is view-only for group participants. Only the group administrator can modify payment records via the secure sidebar.*")
