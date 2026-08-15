import streamlit as st
from datetime import datetime, timedelta
import json
import os

# Page Configuration
st.set_page_config(
    page_title="Susu Savings", 
    page_icon="💸", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# Modern UI Styling with Clean Cards, Smooth Fonts, and Hidden Streamlit Decor
st.markdown("""
    <style>
    /* Hide Streamlit Header, Main Menu, Deploy Button, and Footer Branding */
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    .stDeployButton {display: none !important;}
    footer {visibility: hidden !important;}
    
    /* Clean Modern Background and Typography */
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    h1, h2, h3 {
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Compact Combined Metric Card with Title Included */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        padding: 16px 18px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }
    .card-title {
        color: #f8fafc;
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 12px;
        text-align: center;
        border-bottom: 1px solid #334155;
        padding-bottom: 8px;
    }
    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-item {
        text-align: center;
        flex: 1;
        border-right: 1px solid #334155;
    }
    .metric-item:last-child {
        border-right: none;
    }
    .metric-label {
        color: #94a3b8;
        font-weight: 500;
        font-size: 11px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .metric-value {
        color: #38bdf8;
        font-size: 16px;
        font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# Helper function for clean number formatting (removes decimals if whole numbers)
def fmt_num(val):
    if val.is_integer():
        return f"{int(val):,}"
    return f"{val:,.2f}"

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
        "admin_fee_percentage": 0.0,
        "names_input": "Alice, Bob, Charlie, Diana, Frank, Grace",
        "member_tiers": {},
        "payments": {},
        "payout_status": {}
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Load saved settings
saved_data = load_data()

# --- ADMIN SECURITY LOGIN IN SIDEBAR ---
st.sidebar.header("Admin Panel")
admin_password_input = st.sidebar.text_input("Admin Passcode", type="password", placeholder="Enter passcode to edit")

ADMIN_SECRET = "Susu2026" 
is_admin = (admin_password_input == ADMIN_SECRET)

if not is_admin:
    st.sidebar.markdown("---")
    st.sidebar.info("View-Only Mode\n\nEnter the correct Admin Passcode above to unlock settings and record updates.")

# Process core group variables from saved file
start_date_str = saved_data["start_date"]
base_monthly = float(saved_data.get("base_monthly_amount", 1000))
admin_fee_percentage = float(saved_data.get("admin_fee_percentage", saved_data.get("admin_fee_amount", 0.0)))
names_input = saved_data["names_input"]

members = [n.strip() for n in names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("Please enter at least 2 participant names in the sidebar.")
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
    admin_fee_percentage = st.sidebar.number_input("Admin Holding Fee per Payout (%)", value=admin_fee_percentage, min_value=0.0, max_value=100.0, step=0.5)
    names_input = st.sidebar.text_area("Participant Names (comma-separated)", value=saved_data["names_input"])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Custom Monthly Tiers per Member")
    updated_tiers = {}
    for m in members:
        current_val = float(member_tiers.get(m, base_monthly))
        updated_tiers[m] = st.sidebar.number_input(f"{m}'s Monthly Contribution (GH₵)", value=current_val, step=50.0, key=f"tier_{m}")
    member_tiers = updated_tiers

total_weeks = num_members * 4  # 4 weeks per month block

try:
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
except ValueError:
    st.error("Incorrect date format. Use YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

# Initialize data states if members changed or file is fresh
payments = saved_data.get("payments", {})
if not payments or list(payments.keys()) != members:
    payments = {m: {str(w): False for w in range(1, total_weeks + 1)} for m in members}

payout_status = saved_data.get("payout_status", {})
if not payout_status:
    payout_status = {f"Month {i+1}": {"amount_collected": 0.0} for i in range(num_members)}

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
            "admin_fee_percentage": admin_fee_percentage,
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

    current_p_info = payout_status.get(month_key, {"amount_collected": 0.0})
    
    recipient_idx = int(month_key.split(" ")[1]) - 1
    recipient_name = members[recipient_idx]
    rec_monthly = member_tiers.get(recipient_name, base_monthly)
    gross_pool = rec_monthly * num_members
    fee_val = gross_pool * (admin_fee_percentage / 100.0)
    net_pool = gross_pool - fee_val

    input_collected = st.sidebar.number_input("Amount Collected (GH₵)", value=float(current_p_info.get("amount_collected", 0.0)), min_value=0.0, max_value=float(net_pool), step=50.0)

    if st.sidebar.button("Save Payout Amounts", type="secondary"):
        if month_key not in payout_status:
            payout_status[month_key] = {}
        payout_status[month_key]["amount_collected"] = input_collected
        
        new_data = {
            "start_date": start_date_str,
            "base_monthly_amount": base_monthly,
            "admin_fee_percentage": admin_fee_percentage,
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
    "admin_fee_percentage": admin_fee_percentage,
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
    p_info = payout_status.get(m_lbl, {"amount_collected": 0.0})
    collected_amt = float(p_info.get("amount_collected", 0.0))
    total_payouts_distributed += collected_amt

total_cash_held = total_cash_collected - total_payouts_distributed

# Main App Header / Expander to open Admin Panel directly on mobile views
with st.expander("⚙️ Admin Panel Access (Tap to Open)", expanded=False):
    st.info("Since mobile browsers hide the top-left sidebar button, use the toggle options below or enter your passcode directly in the sidebar settings if visible.")
    mobile_passcode = st.text_input("Enter Admin Passcode to Unlock", type="password", key="mobile_admin_pass")
    if mobile_passcode == ADMIN_SECRET:
        st.success("Passcode accepted! Scroll down or check your sidebar to edit settings.")

# Compact Combined Metric Card with Title Included Inside
st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">Susu Savings</div>
        <div class="metric-row">
            <div class="metric-item">
                <div class="metric-label">Total Cash Held</div>
                <div class="metric-value">GH₵ {fmt_num(total_cash_held)}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">Admin Fee Rate</div>
                <div class="metric-value">{fmt_num(admin_fee_percentage)}%</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">End Date</div>
                <div class="metric-value">{format_date(end_date)}</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

st.markdown("### Payout")

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
        "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Admin Fee": f"GH₵ {fmt_num(admin_fee_val)} ({fmt_num(admin_fee_percentage)}%)",
        "Total Pool": f"GH₵ {fmt_num(remaining_pool)}",
        "Amount Collected": f"GH₵ {fmt_num(collected_amt)}"
    })
    current_date = payout_date

st.dataframe(schedule, use_container_width=True, hide_index=True)

st.markdown("### Contributions")

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
        status_text = f"Owing GH₵ {fmt_num(owing_amount)}"
    else:
        status_text = "Up to Date"
    
    row = {
        "Member": member, 
        "Monthly Tier": f"GH₵ {fmt_num(m_monthly)}",
        "Weekly Target": f"GH₵ {fmt_num(m_weekly)} / wk",
        "Progress": f"{total_paid_all} / {total_weeks} weeks paid",
        "Status": status_text
    }
    table_data.append(row)

st.dataframe(table_data, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Admin passcode required only in the sidebar for updating logs.")
