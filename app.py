import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import io

# Page Configuration
st.set_page_config(
    page_title="Susu Savings", 
    page_icon="💸", 
    layout="centered"
)

# Modern UI Styling
st.markdown("""
    <style>
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    .stDeployButton {display: none !important;}
    footer {visibility: hidden !important;}
    
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    h1, h2, h3 {
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
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

# Helper function for clean number formatting
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

# --- INITIALIZE SESSION STATE ---
if "initialized" not in st.session_state:
    st.session_state.start_date = "2026-08-17"
    st.session_state.base_monthly = 1000
    st.session_state.admin_fee_percentage = 0.0
    st.session_state.names_input = "Alice, Bob, Charlie, Diana, Frank, Grace"
    st.session_state.member_tiers = {}
    st.session_state.payments = {}
    st.session_state.payout_status = {}
    st.session_state.initialized = True

# --- APP SIDEBAR (Group Management & Weekly Logging) ---
st.sidebar.header("Group Setup & Logs")

with st.sidebar.expander("Group Settings", expanded=False):
    start_date_str = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    base_monthly = st.number_input("Standard Base Monthly Target (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    admin_fee_percentage = st.number_input("Admin Holding Fee per Payout (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    names_input = st.text_area("Participant Names (comma-separated)", value=st.session_state.names_input)
    
    if st.button("Save Settings"):
        st.session_state.start_date = start_date_str
        st.session_state.base_monthly = base_monthly
        st.session_state.admin_fee_percentage = admin_fee_percentage
        st.session_state.names_input = names_input
        st.rerun()

members = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("Please enter at least 2 participant names in the sidebar settings.")
    st.stop()

for m in members:
    if m not in st.session_state.member_tiers:
        st.session_state.member_tiers[m] = st.session_state.base_monthly

with st.sidebar.expander("Custom Monthly Tiers", expanded=False):
    updated_tiers = {}
    for m in members:
        current_val = float(st.session_state.member_tiers.get(m, st.session_state.base_monthly))
        updated_tiers[m] = st.number_input(f"{m}'s Monthly (GHS)", value=current_val, step=50.0, key=f"tier_{m}")
    if st.button("Save Tiers"):
        st.session_state.member_tiers = updated_tiers
        st.rerun()

total_weeks = num_members * 4

try:
    start_dt = datetime.strptime(st.session_state.start_date, '%Y-%m-%d')
except ValueError:
    st.error("Incorrect date format. Use YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

if not st.session_state.payments or list(st.session_state.payments.keys()) != members:
    st.session_state.payments = {m: {str(w): False for w in range(1, total_weeks + 1)} for m in members}

if not st.session_state.payout_status:
    st.session_state.payout_status = {f"Month {i+1}": {"amount_collected": 0.0} for i in range(num_members)}

# --- LOGGING ACTIONS IN SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.subheader("Record Weekly Payment")
selected_member = st.sidebar.selectbox("Select Member", members)
selected_week = st.sidebar.selectbox("Select Week Number", list(range(1, total_weeks + 1)))

current_w_status = st.session_state.payments.get(selected_member, {}).get(str(selected_week), False)
weekly_check = st.sidebar.checkbox(f"Has {selected_member} paid for Week {selected_week}?", value=current_w_status)

if st.sidebar.button("Save Weekly Payment"):
    st.session_state.payments[selected_member][str(selected_week)] = weekly_check
    st.sidebar.success("Saved!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Record Payout Collection")
month_options = [f"Month {i+1} ({members[i]})" for i in range(num_members)]
selected_month_label = st.sidebar.selectbox("Select Payout Turn", month_options)
month_key = selected_month_label.split(" (")[0]

current_p_info = st.session_state.payout_status.get(month_key, {"amount_collected": 0.0})
recipient_idx = int(month_key.split(" ")[1]) - 1
recipient_name = members[recipient_idx]
rec_monthly = st.session_state.member_tiers.get(recipient_name, st.session_state.base_monthly)
gross_pool = rec_monthly * num_members
fee_val = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
net_pool = gross_pool - fee_val

input_collected = st.sidebar.number_input("Amount Collected (GHS)", value=float(current_p_info.get("amount_collected", 0.0)), min_value=0.0, max_value=float(net_pool), step=50.0)

if st.sidebar.button("Save Payout Amounts"):
    st.session_state.payout_status[month_key]["amount_collected"] = input_collected
    st.sidebar.success("Saved!")
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

total_payouts_distributed = 0.0
for i in range(num_members):
    m_lbl = f"Month {i+1}"
    p_info = st.session_state.payout_status.get(m_lbl, {"amount_collected": 0.0})
    total_payouts_distributed += float(p_info.get("amount_collected", 0.0))

total_cash_held = total_cash_collected - total_payouts_distributed

# --- MAIN DASHBOARD VIEW ---
st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">Susu Savings Dashboard</div>
        <div class="metric-row">
            <div class="metric-item">
                <div class="metric-label">Total Cash Held</div>
                <div class="metric-value">GHS {fmt_num(total_cash_held)}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">Admin Fee Rate</div>
                <div class="metric-value">{fmt_num(st.session_state.admin_fee_percentage)}%</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">End Date</div>
                <div class="metric-value">{format_date(end_date)}</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Build table records and text report data
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
        "Recipient": recipient,
        "Payout Date": format_date(payout_date),
        "Admin Fee": f"GHS {fmt_num(admin_fee_val)}",
        "Total Pool": f"GHS {fmt_num(remaining_pool)}",
        "Amount Collected": f"GHS {fmt_num(collected_amt)}"
    })
    
    whatsapp_payout_rows.append({
        "recipient": recipient,
        "date": format_date(payout_date),
        "balance": fmt_num(remaining_pool)
    })
    
    current_date = payout_date

contrib_data = []
whatsapp_contrib_rows = []
for member in members:
    m_monthly = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly = m_monthly / 4.0
    member_payments = st.session_state.payments.get(member, {})
    
    paid_passed_weeks = sum(1 for w in range(1, current_elapsed_week + 1) if member_payments.get(str(w), False))
    unpaid_passed_weeks = current_elapsed_week - paid_passed_weeks
    owing_amount = unpaid_passed_weeks * m_weekly
    total_paid_all = sum(1 for w in range(1, total_weeks + 1) if member_payments.get(str(w), False))
    
    if owing_amount > 0:
        standing_text = f"Owing GHS {fmt_num(owing_amount)}"
    else:
        standing_text = "Up to date"
    
    contrib_data.append({
        "Member": member, 
        "Monthly Tier": f"GHS {fmt_num(m_monthly)}",
        "Weekly Target": f"GHS {fmt_num(m_weekly)} / wk",
        "Progress": f"{total_paid_all} / {total_weeks} weeks paid",
        "Status": standing_text
    })
    
    whatsapp_contrib_rows.append({
        "member": member,
        "standing": standing_text
    })

df_sched = pd.DataFrame(schedule_data)
df_contrib = pd.DataFrame(contrib_data)

# --- SIMPLIFIED EMOJI WHATSAPP TEXT REPORT DOWNLOAD ---
st.markdown("### Weekly Standings Text Report")
st.info("Download the simplified text update for WhatsApp with clear 'Up to date' or 'Owing' member statuses.")

report_buffer = io.StringIO()
report_buffer.write(f"📌 *WK {current_elapsed_week} UPDATE*\n")
report_buffer.write(f"💰 *Cash at Hand:* GHS {fmt_num(total_cash_held)}\n\n")

report_buffer.write("👥 *MEMBERS*\n")
for row in whatsapp_contrib_rows:
    icon = "📌" if "Owing" in row["standing"] else "✅"
    report_buffer.write(f"{icon} *{row['member']}*: {row['standing']}\n")

report_buffer.write("\n🎁 *PAYOUTS*\n")
for prow in whatsapp_payout_rows:
    report_buffer.write(f"• *{prow['recipient']}* ({prow['date']}) ➔ GHS {prow['balance']}\n")

st.download_button(
    label="📥 Download Simple WhatsApp Update",
    data=report_buffer.getvalue(),
    file_name=f"Susu_Update_W{current_elapsed_week}.txt",
    mime="text/plain",
    type="primary"
)

# --- DISPLAY TABLES ---
st.markdown("### Payout")
st.dataframe(df_sched, use_container_width=True, hide_index=True)

st.markdown("### Contributions")
st.dataframe(df_contrib, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Running completely offline in local memory session. No passcode required.")
