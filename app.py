import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import io

# Page Configuration
st.set_page_config(
    page_title="Susu Weekly Update", 
    page_icon="💸", 
    layout="centered"
)

# Modern UI Styling with clean mobile text output encoding fix
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
        font-size: 15px;
        font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# Helper function for clean number formatting (standard text instead of symbols that break on mobile)
def fmt_num(val):
    if val.is_integer():
        return f"{int(val):,}"
    return f"{val:,.2f}"

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

# --- SIDEBAR: SIMPLE CONFIG & WEEKLY LOGGING ---
st.sidebar.header("Weekly Manager")

with st.sidebar.expander("Group Setup", expanded=False):
    start_date_str = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    base_monthly = st.number_input("Standard Monthly Target (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    admin_fee_percentage = st.number_input("Admin Fee (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    names_input = st.text_area("Names (comma-separated)", value=st.session_state.names_input)
    
    if st.button("Update Setup"):
        st.session_state.start_date = start_date_str
        st.session_state.base_monthly = base_monthly
        st.session_state.admin_fee_percentage = admin_fee_percentage
        st.session_state.names_input = names_input
        st.rerun()

members = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)

if num_members < 2:
    st.error("Please enter at least 2 names.")
    st.stop()

for m in members:
    if m not in st.session_state.member_tiers:
        st.session_state.member_tiers[m] = st.session_state.base_monthly

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

# Weekly Check-in Logger
st.sidebar.markdown("---")
st.sidebar.subheader("Tick Off Weekly Payment")
selected_member = st.sidebar.selectbox("Select Member", members)
selected_week = st.sidebar.selectbox("Select Week Number", list(range(1, total_weeks + 1)))

current_w_status = st.session_state.payments.get(selected_member, {}).get(str(selected_week), False)
weekly_check = st.sidebar.checkbox(f"Has {selected_member} paid for Week {selected_week}?", value=current_w_status)

if st.sidebar.button("Save Payment Status"):
    st.session_state.payments[selected_member][str(selected_week)] = weekly_check
    st.sidebar.success("Saved!")
    st.rerun()

# --- CALCULATE CURRENT WEEK & STANDINGS ---
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

# Determine who is collecting this week or currently active based on dates
current_active_collector = "None (Between cycles)"
current_payout_pool_amount = 0.0
current_cycle_month_label = ""

cycle_date = start_dt
for i in range(num_members):
    payout_date = cycle_date + timedelta(weeks=4)
    if cycle_date <= today <= payout_date:
        current_active_collector = members[i]
        current_cycle_month_label = f"Month {i+1}"
        rec_monthly = st.session_state.member_tiers.get(current_active_collector, st.session_state.base_monthly)
        gross_pool = rec_monthly * num_members
        fee_val = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
        current_payout_pool_amount = gross_pool - fee_val
        break
    cycle_date = payout_date

# --- SIMPLIFIED DASHBOARD VIEW ---
st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">Weekly Susu Update (Week {current_elapsed_week})</div>
        <div class="metric-row">
            <div class="metric-item">
                <div class="metric-label">Total Cash at Hand</div>
                <div class="metric-value">GHS {fmt_num(total_cash_held)}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">Collecting This Month</div>
                <div class="metric-value">{current_active_collector}</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Build simple clean lists for who paid/owing this week
st.markdown("### 📋 This Week's Standing Summary")

summary_rows = []
for member in members:
    m_monthly = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly = m_monthly / 4.0
    member_payments = st.session_state.payments.get(member, {})
    
    # Check current week status
    paid_this_week = member_payments.get(str(current_elapsed_week), False) if current_elapsed_week > 0 else False
    
    # Check overall owing
    paid_passed_weeks = sum(1 for w in range(1, current_elapsed_week + 1) if member_payments.get(str(w), False))
    unpaid_passed_weeks = current_elapsed_week - paid_passed_weeks
    owing_amount = unpaid_passed_weeks * m_weekly
    
    if paid_this_week:
        week_status = "Paid This Week"
    else:
        week_status = "Not Paid Yet"
        
    debt_status = f"Owing GHS {fmt_num(owing_amount)}" if owing_amount > 0 else "Fully Up to Date"
    
    summary_rows.append({
        "Member": member,
        "Week Status": week_status,
        "Account Standing": debt_status
    })

df_summary = pd.DataFrame(summary_rows)
st.dataframe(df_summary, use_container_width=True, hide_index=True)

# --- CLEAN TEXT REPORT FOR EASY SHARING (WhatsApp / SMS / Print) ---
st.markdown("### 📥 Get Simple Weekly Text Update")
st.info("Download this short text update. It contains only who paid, who is owing, who is collecting, and total cash at hand—perfect for sharing directly on WhatsApp with members.")

text_report = f"""--- SUSU WEEKLY UPDATE (WEEK {current_elapsed_week}) ---
Date: {datetime.today().strftime('%Y-%m-%d')}
Total Cash at Hand: GHS {fmt_num(total_cash_held)}
Current Collector: {current_active_collector}

--- MEMBER STATUS ---
"""
for row in summary_rows:
    text_report += f"- {row['Member']}: {row['Week Status']} | {row['Account Standing']}\n"

st.download_button(
    label="Download Simple Text Update (WhatsApp Ready)",
    data=text_report,
    file_name=f"Susu_Simple_Update_Week_{current_elapsed_week}.txt",
    mime="text/plain",
    type="primary"
)

st.markdown("---")
st.caption("Running offline in local memory. Simple mobile-friendly view.")
