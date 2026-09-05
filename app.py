import streamlit as st
from datetime import datetime, timedelta
import io
import json
import re
import hashlib
import secrets as pysecrets
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Susu Savings", page_icon="💸", layout="centered", initial_sidebar_state="collapsed")

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
    removeSidebar(); setTimeout(removeSidebar,300); setTimeout(removeSidebar,800);
    </script>
    <script>
    function navTo(id) {
        const el = window.parent.document.getElementById(id);
        if (el) el.scrollIntoView({behavior:'smooth'});
        else window.parent.scrollTo({top: id==='top'?0:99999, behavior:'smooth'});
    }
    </script>
""", unsafe_allow_html=True)

# ── HTML helper ───────────────────────────────────────────────────────────────
# Streamlit's Markdown parser treats a blank line followed by a line indented
# 4+ spaces as a code block. This strips leading whitespace from every line so
# multi-line HTML strings render as HTML, never as literal code.
def html(s):
    st.markdown(re.sub(r"\n[ \t]+", "\n", s).strip(), unsafe_allow_html=True)

# ── theme ─────────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state: st.session_state.dark_mode = True
D = st.session_state.dark_mode

if D:
    T = {
        "bg":"linear-gradient(135deg,#080d1a 0%,#0b1525 50%,#080f1c 100%)",
        "card_bg":"rgba(255,255,255,0.025)","card_border":"rgba(255,255,255,0.06)",
        "card_shadow":"0 4px 20px rgba(0,0,0,0.25),inset 0 1px 0 rgba(255,255,255,0.04)",
        "hero_bg":"rgba(255,255,255,0.03)","hero_border":"rgba(255,255,255,0.07)",
        "chip_bg":"rgba(255,255,255,0.03)","chip_border":"rgba(255,255,255,0.07)",
        "status_bg":"rgba(255,255,255,0.02)","status_border":"rgba(255,255,255,0.05)",
        "sync_color":"#334155","title_color":"#f1f5f9","sub_color":"#334155",
        "label_color":"#1e3a5f","sec_title":"#cbd5e1","th_color":"#1e3a5f",
        "td_color":"#94a3b8","td_border":"rgba(255,255,255,0.03)","th_border":"rgba(255,255,255,0.05)",
        "member_name":"#e2e8f0","input_bg":"rgba(255,255,255,0.04)","input_border":"rgba(255,255,255,0.08)",
        "input_color":"#e2e8f0","lock_bg":"rgba(255,255,255,0.04)","lock_border":"rgba(255,255,255,0.08)",
        "lock_title":"#f1f5f9","lock_sub":"#334155","exp_bg":"rgba(255,255,255,0.025)",
        "exp_border":"rgba(255,255,255,0.06)","exp_color":"#64748b","exp_content":"rgba(255,255,255,0.015)",
        "gdiv":"rgba(56,189,248,0.12)","foot_color":"#0f1f35","foot_border":"rgba(255,255,255,0.03)",
        "btn_bg":"rgba(29,78,216,0.75)","btn_border":"rgba(59,130,246,0.35)",
        "btn2_bg":"rgba(255,255,255,0.03)","btn2_color":"#334155","btn2_border":"rgba(255,255,255,0.07)",
        "dl_bg":"rgba(255,255,255,0.03)","dl_border":"rgba(56,189,248,0.2)",
        "log_border":"rgba(255,255,255,0.03)","log_color":"#64748b","log_strong":"#94a3b8","log_time":"#1e3a5f",
        "toggle_icon":"☀️","toggle_label":"Light mode","ring_track":"rgba(255,255,255,0.06)",
        "bar_bg":"rgba(255,255,255,0.06)","week_upcoming_bg":"rgba(255,255,255,0.04)",
        "member_view_bg":"rgba(56,189,248,0.06)","member_view_border":"rgba(56,189,248,0.15)",
        "streak_bg":"rgba(239,68,68,0.08)","streak_color":"#f87171","streak_border":"rgba(239,68,68,0.2)",
    }
else:
    T = {
        "bg":"linear-gradient(135deg,#e8edf5 0%,#f0f4fa 50%,#eaeff8 100%)",
        "card_bg":"rgba(255,255,255,0.75)","card_border":"rgba(0,0,0,0.07)",
        "card_shadow":"0 4px 20px rgba(0,0,0,0.08),inset 0 1px 0 rgba(255,255,255,0.9)",
        "hero_bg":"rgba(255,255,255,0.7)","hero_border":"rgba(0,0,0,0.08)",
        "chip_bg":"rgba(255,255,255,0.8)","chip_border":"rgba(0,0,0,0.07)",
        "status_bg":"rgba(255,255,255,0.5)","status_border":"rgba(0,0,0,0.07)",
        "sync_color":"#64748b","title_color":"#0f172a","sub_color":"#475569",
        "label_color":"#4f46e5","sec_title":"#0f172a","th_color":"#4f46e5",
        "td_color":"#1e293b","td_border":"rgba(0,0,0,0.04)","th_border":"rgba(0,0,0,0.06)",
        "member_name":"#0f172a","input_bg":"rgba(255,255,255,0.8)","input_border":"rgba(0,0,0,0.1)",
        "input_color":"#0f172a","lock_bg":"rgba(255,255,255,0.8)","lock_border":"rgba(0,0,0,0.08)",
        "lock_title":"#0f172a","lock_sub":"#94a3b8","exp_bg":"rgba(255,255,255,0.7)",
        "exp_border":"rgba(0,0,0,0.07)","exp_color":"#334155","exp_content":"rgba(255,255,255,0.6)",
        "gdiv":"rgba(99,102,241,0.2)","foot_color":"#94a3b8","foot_border":"rgba(0,0,0,0.06)",
        "btn_bg":"rgba(29,78,216,0.9)","btn_border":"rgba(29,78,216,0.4)",
        "btn2_bg":"rgba(0,0,0,0.04)","btn2_color":"#334155","btn2_border":"rgba(0,0,0,0.08)",
        "dl_bg":"rgba(99,102,241,0.06)","dl_border":"rgba(99,102,241,0.3)",
        "log_border":"rgba(0,0,0,0.05)","log_color":"#334155","log_strong":"#0f172a","log_time":"#64748b",
        "toggle_icon":"🌙","toggle_label":"Dark mode","ring_track":"rgba(0,0,0,0.08)",
        "bar_bg":"rgba(0,0,0,0.08)","week_upcoming_bg":"rgba(0,0,0,0.04)",
        "member_view_bg":"rgba(99,102,241,0.05)","member_view_border":"rgba(99,102,241,0.15)",
        "streak_bg":"rgba(239,68,68,0.06)","streak_color":"#dc2626","streak_border":"rgba(239,68,68,0.15)",
    }

dl_color     = "#38bdf8" if D else "#6366f1"
urgent_glow  = "0 0 16px rgba(251,191,36,0.5),0 0 32px rgba(251,191,36,0.2)" if D else "0 0 12px rgba(251,191,36,0.3)"
ring_text_c  = "#38bdf8" if D else "#4f46e5"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    header{{visibility:hidden!important;height:0!important;}} #MainMenu{{visibility:hidden!important;}}
    .stDeployButton{{display:none!important;}} footer{{visibility:hidden!important;}}
    section[data-testid="stSidebar"]{{display:none!important;width:0!important;}}
    [data-testid="collapsedControl"]{{display:none!important;width:0!important;}}
    [data-testid="stSidebarNav"]{{display:none!important;}} button[kind="header"]{{display:none!important;}}
    .block-container{{padding-top:0!important;padding-bottom:4rem!important;max-width:820px!important;}}
    html,body,[class*="css"]{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}}
    .main,.stApp{{background:{T['bg']}!important;min-height:100vh;}}

    .status-bar{{background:{T['status_bg']};border-bottom:1px solid {T['status_border']};padding:8px 0;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;font-size:11px;}}
    .status-dot{{width:6px;height:6px;background:#34d399;border-radius:50%;display:inline-block;margin-right:6px;animation:pulse 2s infinite;}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
    .status-live{{color:#34d399;font-weight:600;}} .status-sync{{color:{T['sync_color']};}}

    .lock-outer{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;margin-top:-2rem;}}
    .lock-card{{background:{T['lock_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['lock_border']};border-radius:24px;padding:48px 40px;text-align:center;width:100%;max-width:360px;box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 0 rgba(255,255,255,0.4);}}
    .lock-icon{{font-size:44px;margin-bottom:16px;display:block;}}
    .lock-title{{font-size:22px;font-weight:700;color:{T['lock_title']};margin-bottom:6px;}}
    .lock-sub{{font-size:13px;color:{T['lock_sub']};margin-bottom:0;}}

    /* Hero with ring */
    .hero{{background:{T['hero_bg']};backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid {T['hero_border']};border-radius:20px;padding:22px 28px;margin-bottom:14px;box-shadow:0 4px 24px rgba(0,0,0,0.1),inset 0 1px 0 rgba(255,255,255,0.3);position:relative;overflow:hidden;display:flex;align-items:center;justify-content:space-between;gap:16px;}}
    .hero::before{{content:'';position:absolute;top:-60px;right:-60px;width:220px;height:220px;background:radial-gradient(circle,rgba(56,189,248,0.08) 0%,transparent 70%);pointer-events:none;}}
    .hero-left{{flex:1;}}
    .hero-title{{font-size:17px;font-weight:700;color:{T['title_color']};margin:0 0 3px 0;letter-spacing:-0.2px;}}
    .hero-sub{{font-size:12px;color:{T['sub_color']};margin:0;}}
    .hero-badge{{display:inline-flex;align-items:center;gap:5px;background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.2);border-radius:20px;padding:4px 10px;font-size:10px;font-weight:600;color:#38bdf8;margin-top:10px;letter-spacing:0.3px;}}

    .member-view-banner{{background:{T['member_view_bg']};border:1px solid {T['member_view_border']};border-radius:14px;padding:14px 20px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;}}
    .member-view-name{{font-size:15px;font-weight:700;color:{T['title_color']};}}
    .member-view-sub{{font-size:11px;color:{T['sub_color']};}}
    .member-view-label{{font-size:10px;font-weight:600;color:{dl_color};text-transform:uppercase;letter-spacing:0.8px;margin-bottom:3px;}}

    .countdown-banner{{background:rgba(99,102,241,0.08);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(99,102,241,0.2);border-radius:14px;padding:16px 22px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 0 20px rgba(99,102,241,0.06);}}
    .countdown-left{{display:flex;flex-direction:column;gap:3px;}}
    .countdown-label{{font-size:10px;font-weight:600;color:#4f46e5;text-transform:uppercase;letter-spacing:0.8px;}}
    .countdown-name{{font-size:15px;font-weight:700;color:{T['title_color']};}}
    .countdown-pool{{font-size:12px;color:{T['sub_color']};}}
    .countdown-right{{text-align:right;}}
    .countdown-days{{font-size:32px;font-weight:800;color:#818cf8;line-height:1;}}
    .countdown-days.urgent{{color:#fbbf24;animation:urgentPulse 1.5s ease-in-out infinite;text-shadow:{urgent_glow};}}
    @keyframes urgentPulse{{0%,100%{{opacity:1}}50%{{opacity:0.7}}}}
    .countdown-days-label{{font-size:10px;color:#4f46e5;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;}}
    .days-badge{{display:inline-block;background:rgba(129,140,248,0.12);color:#818cf8;border:1px solid rgba(129,140,248,0.25);border-radius:10px;padding:1px 7px;font-size:10px;font-weight:600;white-space:nowrap;}}
    .days-badge.urgent{{background:rgba(251,191,36,0.12);color:#fbbf24;border-color:rgba(251,191,36,0.3);}}

    .chip-row{{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;}}
    .chip{{flex:1;min-width:110px;background:{T['chip_bg']};backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid {T['chip_border']};border-radius:14px;padding:14px 16px;box-shadow:0 2px 12px rgba(0,0,0,0.1),inset 0 1px 0 rgba(255,255,255,0.2);}}
    .chip-label{{font-size:10px;font-weight:600;color:{T['label_color']};text-transform:uppercase;letter-spacing:0.7px;margin-bottom:6px;}}
    .chip-value{{font-size:16px;font-weight:700;color:#38bdf8;}}
    .chip-value-green{{font-size:16px;font-weight:700;color:#34d399;}}
    .chip-value-amber{{font-size:16px;font-weight:700;color:#fbbf24;}}
    .chip-value-red{{font-size:16px;font-weight:700;color:#f87171;}}
    @keyframes countUp{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
    .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{animation:countUp 0.6s ease-out;}}
    .chip-sub{{font-size:10px;color:{T['sub_color']};margin-top:3px;}}

    .glass-card{{background:{T['card_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['card_border']};border-radius:16px;padding:20px 22px;margin-bottom:14px;box-shadow:{T['card_shadow']};}}
    .sec-label{{font-size:10px;font-weight:700;color:{T['label_color']};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
    .sec-title{{font-size:15px;font-weight:700;color:{T['sec_title']};margin:0 0 2px 0;}}
    .sec-sub{{font-size:11px;color:{T['sub_color']};margin:0 0 14px 0;}}

    .data-table{{width:100%;border-collapse:collapse;}}
    .data-table th{{font-size:10px;font-weight:600;color:{T['th_color']};text-transform:uppercase;letter-spacing:0.6px;padding:8px 12px;border-bottom:1px solid {T['th_border']};text-align:left;}}
    .data-table td{{font-size:13px;color:{T['td_color']};padding:10px 12px;border-bottom:1px solid {T['td_border']};vertical-align:middle;}}
    .data-table tr:last-child td{{border-bottom:none;}}
    .data-table tr.owing td:first-child{{border-left:2px solid #fbbf24;padding-left:10px;}}
    .data-table tr.ok td:first-child{{border-left:2px solid #34d399;padding-left:10px;}}
    .data-table tr.plain td:first-child{{border-left:2px solid transparent;padding-left:10px;}}
    .cell-name{{font-weight:600;color:{T['member_name']};}}
    .badge-ok{{background:rgba(52,211,153,0.12);color:#34d399;border:1px solid rgba(52,211,153,0.25);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600;white-space:nowrap;}}
    .badge-owe{{background:rgba(251,191,36,0.12);color:#fbbf24;border:1px solid rgba(251,191,36,0.25);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600;white-space:nowrap;}}
    .badge-pending{{background:rgba(148,163,184,0.1);color:#64748b;border:1px solid rgba(148,163,184,0.2);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600;white-space:nowrap;}}
    .streak-badge{{background:{T['streak_bg']};color:{T['streak_color']};border:1px solid {T['streak_border']};border-radius:20px;padding:2px 8px;font-size:10px;font-weight:600;white-space:nowrap;margin-left:6px;}}

    .pbar-wrap{{margin-top:6px;background:{T['bar_bg']};border-radius:4px;height:4px;overflow:hidden;}}
    .pbar-fill{{height:4px;border-radius:4px;background:linear-gradient(90deg,#34d399,#38bdf8);transition:width 0.4s ease;}}
    .early-eligible{{font-size:10px;color:#34d399;margin-top:3px;font-weight:600;}}

    .week-grid{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;}}
    .week-pill{{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;}}
    .week-paid{{background:rgba(52,211,153,0.12);color:#34d399;border:1px solid rgba(52,211,153,0.25);}}
    .week-owe{{background:rgba(251,191,36,0.12);color:#fbbf24;border:1px solid rgba(251,191,36,0.25);}}
    .week-upcoming{{background:{T['week_upcoming_bg']};color:{T['td_color']};border:1px solid {T['card_border']};}}

    .log-entry{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid {T['log_border']};}}
    .log-entry:last-child{{border-bottom:none;}}
    .log-dot{{width:8px;height:8px;border-radius:50%;background:#38bdf8;margin-top:4px;flex-shrink:0;}}
    .log-dot-payout{{background:#818cf8;}} .log-dot-setting{{background:#34d399;}}
    .log-text{{font-size:12px;color:{T['log_color']};line-height:1.4;}}
    .log-text strong{{color:{T['log_strong']};font-weight:600;}}
    .log-time{{font-size:11px;color:{T['log_time']};margin-left:auto;white-space:nowrap;padding-left:12px;}}

    .stTextInput input,.stNumberInput input,.stTextArea textarea{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;color:{T['input_color']}!important;border-radius:10px!important;font-size:13px!important;}}
    .stTextInput input:focus,.stNumberInput input:focus{{border-color:rgba(56,189,248,0.4)!important;box-shadow:0 0 0 2px rgba(56,189,248,0.08)!important;}}
    .stTextInput label,.stNumberInput label,.stTextArea label,.stSelectbox label,.stCheckbox label{{color:{T['label_color']}!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.5px;}}
    .stSelectbox > div > div{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;color:{T['input_color']}!important;border-radius:10px!important;}}
    div[data-testid="stButton"]{{width:100%!important;}}
    .stButton > button{{background:{T['btn_bg']}!important;backdrop-filter:blur(8px)!important;color:white!important;border:1px solid {T['btn_border']}!important;border-radius:10px!important;font-weight:600!important;font-size:13px!important;padding:9px 20px!important;width:100%;box-shadow:0 2px 8px rgba(29,78,216,0.25)!important;transition:all 0.2s!important;}}
    .stButton > button:hover{{background:rgba(37,99,235,0.95)!important;box-shadow:0 4px 16px rgba(29,78,216,0.4)!important;}}
    .stButton > button[kind="secondary"]{{background:{T['btn2_bg']}!important;color:{T['btn2_color']}!important;border:1px solid {T['btn2_border']}!important;box-shadow:none!important;}}
    div[data-testid="stDownloadButton"],.stDownloadButton{{width:100%!important;}}
    div[data-testid="stDownloadButton"] > button,.stDownloadButton > button{{background:{T['dl_bg']}!important;backdrop-filter:blur(8px)!important;color:{dl_color}!important;border:1px solid {T['dl_border']}!important;border-radius:10px!important;font-size:13px!important;font-weight:600!important;padding:9px 20px!important;width:100%!important;transition:all 0.2s!important;}}
    /* Expanders (current Streamlit DOM) */
    details[data-testid="stExpander"]{{background:{T['exp_bg']}!important;backdrop-filter:blur(12px)!important;border:1px solid {T['exp_border']}!important;border-radius:12px!important;margin-bottom:8px!important;overflow:hidden;}}
    details[data-testid="stExpander"] summary{{background:transparent!important;padding:12px 16px!important;}}
    details[data-testid="stExpander"] summary,details[data-testid="stExpander"] summary *{{color:{T['sec_title']}!important;font-size:13px!important;font-weight:600!important;}}
    details[data-testid="stExpander"] summary:hover{{color:{dl_color}!important;}}
    details[data-testid="stExpander"] summary svg{{fill:{T['sec_title']}!important;color:{T['sec_title']}!important;}}
    details[data-testid="stExpander"] > div:not(summary){{background:{T['exp_content']}!important;border-top:1px solid {T['exp_border']}!important;padding:18px!important;}}
    details[data-testid="stExpander"] p,details[data-testid="stExpander"] label,details[data-testid="stExpander"] .stCheckbox span{{color:{T['td_color']};}}
    .streamlit-expanderHeader{{background:{T['exp_bg']}!important;color:{T['sec_title']}!important;font-size:13px!important;font-weight:600!important;border-radius:12px!important;}}
    div[data-testid="stSuccess"]{{background:rgba(16,185,129,0.07)!important;border:1px solid rgba(16,185,129,0.2)!important;border-radius:10px!important;color:#34d399!important;font-size:13px!important;}}
    div[data-testid="stError"]{{background:rgba(239,68,68,0.07)!important;border:1px solid rgba(239,68,68,0.2)!important;border-radius:10px!important;color:#f87171!important;font-size:13px!important;}}
    div[data-testid="stWarning"]{{background:rgba(251,191,36,0.07)!important;border:1px solid rgba(251,191,36,0.2)!important;border-radius:10px!important;color:#fbbf24!important;font-size:13px!important;}}
    .stTabs [data-baseweb="tab-list"]{{gap:6px;background:transparent;}}
    .stTabs [data-baseweb="tab"]{{background:{T['btn2_bg']};border:1px solid {T['btn2_border']};border-radius:10px;padding:6px 14px;color:{T['btn2_color']};font-size:12px;font-weight:600;}}
    .stTabs [aria-selected="true"]{{background:{T['dl_bg']}!important;color:{dl_color}!important;border-color:{T['dl_border']}!important;}}
    .stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{{display:none;}}
    div[data-testid="stCode"] pre,div[data-testid="stCodeBlock"] pre{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;border-radius:12px!important;font-size:12px!important;line-height:1.5!important;}}
    div[data-testid="stCode"] code,div[data-testid="stCodeBlock"] code{{color:{T['td_color']}!important;white-space:pre-wrap!important;}}
    .copy-hint{{font-size:11px;color:{T['sub_color']};margin:-6px 0 8px;}}
    .token-link{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:{dl_color};word-break:break-all;}}
    .gdivider{{height:1px;background:linear-gradient(90deg,transparent,{T['gdiv']},transparent);margin:22px 0;}}
    .foot{{text-align:center;font-size:11px;color:{T['foot_color']};margin-top:32px;padding-top:20px;border-top:1px solid {T['foot_border']};}}
    @media (max-width:600px){{
        .block-container{{padding-bottom:5rem!important;padding-left:12px!important;padding-right:12px!important;}}
        .hero{{padding:14px 16px!important;border-radius:14px!important;margin-bottom:10px!important;flex-direction:column;align-items:flex-start;}}
        .hero-title{{font-size:15px!important;}} .hero-sub{{font-size:11px!important;}}
        .chip-row{{display:grid!important;grid-template-columns:1fr 1fr!important;gap:8px!important;}}
        .chip{{min-width:0!important;padding:10px 12px!important;}}
        .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{font-size:15px!important;}}
        .data-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;}}
        .data-table th,.data-table td{{padding:8px 10px!important;font-size:11px!important;}}
        .glass-card{{padding:14px 14px!important;border-radius:12px!important;}}
        .sec-title{{font-size:14px!important;}}
    }}
    .bottom-nav{{display:none;position:fixed;bottom:0;left:0;right:0;z-index:999;background:{T['card_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-top:1px solid {T['card_border']};padding:8px 0 8px;justify-content:space-around;align-items:center;}}
    @media (max-width:600px){{.bottom-nav{{display:flex!important;}}}}
    .nav-item{{display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;padding:4px 16px;border-radius:10px;text-decoration:none;border:none;background:none;}}
    .nav-icon{{font-size:20px;line-height:1;}}
    .nav-label{{font-size:9px;font-weight:600;color:{T['sub_color']};letter-spacing:0.3px;text-transform:uppercase;}}
    </style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_num(val):
    return f"{int(val):,}" if val == int(val) else f"{val:,.2f}"

def format_date(dt):
    d = dt.day
    sfx = 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10,'th')
    return f"{d}{sfx} {dt.strftime('%b %Y')}"

def now_str():
    return datetime.now().strftime("%d %b %Y %H:%M")

def completion_ring(pct, size=72):
    r    = (size-8)//2
    circ = 2*3.14159*r
    dash = circ*pct/100
    c    = ring_text_c
    tr   = T["ring_track"]
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="flex-shrink:0">'
            f'<circle cx="{size//2}" cy="{size//2}" r="{r}" fill="none" stroke="{tr}" stroke-width="5"/>'
            f'<circle cx="{size//2}" cy="{size//2}" r="{r}" fill="none" stroke="{c}" stroke-width="5" '
            f'stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" transform="rotate(-90 {size//2} {size//2})"/>'
            f'<text x="{size//2}" y="{size//2+4}" text-anchor="middle" font-size="13" font-weight="700" fill="{c}">{pct}%</text>'
            f'</svg>')

# passcode hashing (#7) — stored as sha256 hex; plaintext values already in the
# sheet are accepted once and transparently migrated to a hash.
def hash_pw(pw):
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def is_hashed(val):
    return isinstance(val,str) and len(val)==64 and all(c in "0123456789abcdef" for c in val)

def check_pw(entered, stored):
    return hash_pw(entered)==stored if is_hashed(stored) else entered==stored

# flash messages that survive st.rerun (#5)
def flash(msg, kind="success"):
    st.session_state.flash = (msg, kind)

def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        msg, kind = f
        icon = "✅" if kind=="success" else ("⚠️" if kind=="warning" else "ℹ️")
        st.toast(msg, icon=icon)

# WhatsApp export block: code block (copy button built in) + download (#6)
def wa_block(text, fname, key):
    html('<p class="copy-hint">Tap the copy icon (top-right of the box) and paste into WhatsApp.</p>')
    st.code(text, language=None)
    st.download_button("⬇️ Download .txt", data=text, file_name=fname, mime="text/plain", key=key, use_container_width=True)


# ── Google Sheets ─────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_sheet():
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(st.secrets["sheet"]["name"])

def ensure_ws(sheet, title):
    try: return sheet.worksheet(title)
    except gspread.WorksheetNotFound: return sheet.add_worksheet(title=title, rows=2, cols=2)

def load_cell(sheet, ws_title, default):
    ws  = ensure_ws(sheet, ws_title)
    val = ws.cell(1,1).value
    if val:
        try: return json.loads(val)
        except: return default
    return default

def save_cell(sheet, ws_title, value):
    ensure_ws(sheet, ws_title).update("A1", [[json.dumps(value)]])

DEFAULT_SETTINGS = {"start_date":"2026-08-17","base_monthly":1000,"admin_fee_percentage":0.0,"names_input":"Alice, Bob, Charlie, Diana, Frank, Grace"}
ADMIN_PW = "Susu2026"

def load_all_into_state(sheet):
    """(Re)load everything from the sheet into session state (#4)."""
    settings = load_cell(sheet,"settings",DEFAULT_SETTINGS)
    st.session_state.start_date           = settings.get("start_date",DEFAULT_SETTINGS["start_date"])
    st.session_state.base_monthly         = settings.get("base_monthly",DEFAULT_SETTINGS["base_monthly"])
    st.session_state.admin_fee_percentage = settings.get("admin_fee_percentage",0.0)
    st.session_state.names_input          = settings.get("names_input",DEFAULT_SETTINGS["names_input"])
    st.session_state.member_tiers         = load_cell(sheet,"tiers",{})
    st.session_state.payments             = load_cell(sheet,"payments",{})
    st.session_state.payout_status        = load_cell(sheet,"payout_status",{})
    st.session_state.history              = load_cell(sheet,"history",[])
    st.session_state.snapshots            = load_cell(sheet,"snapshots",{})
    st.session_state.member_tokens        = load_cell(sheet,"tokens",{})
    st.session_state.admin_passcode       = load_cell(sheet,"passcode",ADMIN_PW)
    st.session_state.last_sync            = datetime.now()

def save_all(sheet):
    save_cell(sheet,"settings",{"start_date":st.session_state.start_date,"base_monthly":st.session_state.base_monthly,"admin_fee_percentage":st.session_state.admin_fee_percentage,"names_input":st.session_state.names_input})
    save_cell(sheet,"tiers",st.session_state.member_tiers)
    save_cell(sheet,"payments",st.session_state.payments)
    save_cell(sheet,"payout_status",st.session_state.payout_status)
    st.session_state.last_sync = datetime.now()

def append_log(sheet, entry):
    st.session_state.history.insert(0,entry)
    st.session_state.history = st.session_state.history[:50]
    save_cell(sheet,"history",st.session_state.history)

def save_snapshot(sheet, week, cash_held):
    snaps = st.session_state.get("snapshots",{})
    snaps[str(week)] = round(cash_held,2)
    st.session_state.snapshots = snaps
    save_cell(sheet,"snapshots",snaps)

# ── connect ───────────────────────────────────────────────────────────────────
try:
    gsheet = get_sheet()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}"); st.stop()

if "initialized" not in st.session_state:
    load_all_into_state(gsheet)
    st.session_state.authenticated  = False
    st.session_state.initialized    = True
    st.session_state.confirm_payout = False

# auto-refresh a stale session (#4): another admin may have saved since
STALE_MINUTES = 5
if (datetime.now()-st.session_state.last_sync).total_seconds() > STALE_MINUTES*60:
    load_all_into_state(gsheet)

# ── URL param (#3: token-based member view) ───────────────────────────────────
params       = st.query_params
member_token = params.get("m", None)
member_view  = None
if member_token:
    member_view = next((m for m,t in st.session_state.member_tokens.items() if t==member_token), None)
    if member_view is None:
        st.error("This member link is not valid. Please ask the admin for a new link."); st.stop()

show_flash()

# ── auth ──────────────────────────────────────────────────────────────────────
if not member_view and not st.session_state.authenticated:
    html("""<div class="lock-outer">
        <div class="lock-card">
            <span class="lock-icon">💸</span>
            <div class="lock-title">Susu Savings</div>
            <div class="lock-sub">Enter your passcode to continue</div>
        </div>
    </div>""")
    col_l,col_c,col_r = st.columns([1,2,1])
    with col_c:
        pw = st.text_input("p", type="password", label_visibility="collapsed", placeholder="Passcode…")
        if st.button("Unlock →"):
            stored = st.session_state.get("admin_passcode", ADMIN_PW)
            if check_pw(pw, stored):
                if not is_hashed(stored):                       # migrate plaintext → hash
                    st.session_state.admin_passcode = hash_pw(pw)
                    save_cell(gsheet,"passcode",st.session_state.admin_passcode)
                st.session_state.authenticated = True
                st.session_state.last_sync = datetime.now()
                st.rerun()
            else: st.error("Incorrect passcode.")
    st.stop()

# ── derive ────────────────────────────────────────────────────────────────────
members     = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)
if num_members < 2: st.error("Please enter at least 2 member names."); st.stop()

for m in members:
    st.session_state.member_tiers.setdefault(m, st.session_state.base_monthly)

total_weeks = num_members * 4

try: start_dt = datetime.strptime(st.session_state.start_date, "%Y-%m-%d")
except ValueError: st.error("Date format must be YYYY-MM-DD."); st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

# #1: merge instead of reset — existing ticks survive member list edits
for m in members:
    st.session_state.payments.setdefault(m, {})
    for w in range(1,total_weeks+1):
        st.session_state.payments[m].setdefault(str(w), False)
for i in range(num_members):
    st.session_state.payout_status.setdefault(f"Month {i+1}", {})

# #3: ensure every member has a token (admin only — member view must not write)
if not member_view:
    tok_changed = False
    for m in members:
        if not st.session_state.member_tokens.get(m):
            st.session_state.member_tokens[m] = pysecrets.token_urlsafe(6); tok_changed = True
    if tok_changed: save_cell(gsheet,"tokens",st.session_state.member_tokens)

today                = datetime.today()
days_passed          = (today-start_dt).days
current_elapsed_week = min(max(0,days_passed//7)+1 if today>=start_dt else 0, total_weeks)
program_pct          = int(current_elapsed_week/total_weeks*100) if total_weeks else 0
fee_frac             = st.session_state.admin_fee_percentage/100.0

def tier(m):   return st.session_state.member_tiers.get(m,st.session_state.base_monthly)
def weekly(m): return tier(m)/4.0
def paid(m,w): return bool(st.session_state.payments.get(m,{}).get(str(w),False))

# #2: single source of truth — collections are derived from the weekly ticks
def gross_collected_for_month(i):        # i is 0-based month index → weeks 4i+1..4i+4
    return sum(weekly(m) for m in members for w in range(4*i+1,4*i+5) if paid(m,w))

total_cash_collected = sum(weekly(m) for m in members for w in range(1,total_weeks+1) if paid(m,w))

def disbursed_amount(month_lbl):
    ps = st.session_state.payout_status.get(month_lbl,{})
    if not ps.get("disbursed",False): return 0.0
    # backward compat: older records only had amount_collected
    return float(ps.get("disbursed_amount", ps.get("amount_collected",0.0)))

total_payouts_dist = sum(disbursed_amount(f"Month {i+1}") for i in range(num_members))
total_cash_held    = total_cash_collected - total_payouts_dist

total_expected_so_far = sum(weekly(m)*current_elapsed_week for m in members)
collection_gap        = total_expected_so_far - total_cash_collected

next_recipient,next_payout_date,next_net_pool,days_to_payout = None,None,0,0
cur_d = start_dt
for i in range(num_members):
    pd_date = cur_d+timedelta(weeks=4)
    if pd_date >= today:
        next_recipient   = members[i]
        next_payout_date = pd_date
        next_net_pool    = tier(members[i])*num_members*(1-fee_frac)
        days_to_payout   = (pd_date-today).days
        break
    cur_d = pd_date

# #7: make sure the current week always has a snapshot (admin only)
if not member_view and current_elapsed_week>0 and str(current_elapsed_week) not in st.session_state.get("snapshots",{}):
    save_snapshot(gsheet,current_elapsed_week,total_cash_held)

# ── streak & contrib calc ─────────────────────────────────────────────────────
def missed_streak(member):
    streak = 0
    for w in range(current_elapsed_week, 0, -1):
        if not paid(member,w): streak += 1
        else: break
    return streak

contrib_rows, wa_contrib_rows = [], []
for member in members:
    m_monthly   = tier(member)
    m_weekly    = weekly(member)
    paid_passed = sum(1 for w in range(1,current_elapsed_week+1) if paid(member,w))
    owing       = (current_elapsed_week-paid_passed)*m_weekly
    total_paid  = sum(1 for w in range(1,total_weeks+1) if paid(member,w))
    standing    = f"Owing GHS {fmt_num(owing)}" if owing>0 else "Up to date"
    streak      = missed_streak(member)
    contrib_rows.append({"member":member,"m_monthly":m_monthly,"m_weekly":m_weekly,"total_paid":total_paid,"owing":owing,"standing":standing,"streak":streak})
    wa_contrib_rows.append({"member":member,"standing":standing,"streak":streak})

# ── payout schedule calc ──────────────────────────────────────────────────────
schedule_rows, wa_payout_rows = [], []
cur_d = start_dt
for i in range(num_members):
    month_lbl    = f"Month {i+1}"
    recipient    = members[i]
    payout_date  = cur_d+timedelta(weeks=4)
    gross_pool   = tier(recipient)*num_members
    admin_fee_v  = gross_pool*fee_frac
    net_pool_amt = gross_pool-admin_fee_v
    gross_col    = gross_collected_for_month(i)
    net_col      = gross_col*(1-fee_frac)
    remaining    = max(0.0,net_pool_amt-net_col)
    pct_c        = int(net_col/net_pool_amt*100) if net_pool_amt>0 else 0
    ps           = st.session_state.payout_status.get(month_lbl,{})
    disbursed    = ps.get("disbursed",False)
    disb_amt     = disbursed_amount(month_lbl)
    days_away    = (payout_date-today).days if payout_date>=today else None
    early_ok     = (net_col >= net_pool_amt-0.005) and not disbursed and (payout_date >= today)
    schedule_rows.append({"turn":month_lbl,"recipient":recipient,"date":format_date(payout_date),"payout_date":payout_date,"fee":fmt_num(admin_fee_v),"pool":fmt_num(net_pool_amt),"collected":fmt_num(net_col),"remaining":fmt_num(remaining),"pct":pct_c,"disbursed":disbursed,"disb_amt":disb_amt,"disb_date":ps.get("disbursed_date",""),"days_away":days_away,"early_ok":early_ok,"net_pool_amt":net_pool_amt,"net_col":net_col})
    wa_payout_rows.append({"recipient":recipient,"date":format_date(payout_date),"balance":fmt_num(remaining),"disbursed":disbursed})
    cur_d = payout_date


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER SELF-VIEW
# ══════════════════════════════════════════════════════════════════════════════
if member_view:
    mr = next(r for r in contrib_rows if r["member"]==member_view)

    sync_ago = int((datetime.now()-st.session_state.last_sync).total_seconds()/60)
    sync_txt = "just now" if sync_ago<1 else f"{sync_ago}m ago"
    html(f"""
        <div class="status-bar"><span><span class="status-dot"></span><span class="status-live">Live</span></span><span class="status-sync">Synced {sync_txt} &nbsp;·&nbsp; Google Sheets</span></div>
        <div class="hero"><div class="hero-left">
            <div class="hero-title">💸 Susu Savings — Member View</div>
            <div class="hero-sub">{format_date(start_dt)} → {format_date(end_date)}</div>
        </div>{completion_ring(program_pct)}</div>
        <div class="member-view-banner">
            <div>
                <div class="member-view-label">Your Account</div>
                <div class="member-view-name">{member_view}</div>
                <div class="member-view-sub">GHS {fmt_num(mr['m_monthly'])}/month &nbsp;·&nbsp; GHS {fmt_num(mr['m_weekly'])}/week</div>
            </div>
            <div style="text-align:right">
                <div class="{'badge-owe' if mr['owing']>0 else 'badge-ok'}">{mr['standing']}</div>
                <div style="font-size:11px;color:{T['sub_color']};margin-top:6px">{mr['total_paid']} / {total_weeks} weeks paid</div>
            </div>
        </div>
    """)

    pills = ""
    for w in range(1,total_weeks+1):
        p      = paid(member_view,w)
        future = w>current_elapsed_week
        cls    = "week-paid" if p else ("week-upcoming" if future else "week-owe")
        icon   = "✅" if p else ("⏳" if future else "❌")
        pills += f'<span class="week-pill {cls}">{icon} Wk {w}</span>'

    html(f"""<div class="glass-card">
        <p class="sec-label">Payment Tracker</p><p class="sec-title">Your Weekly History</p>
        <p class="sec-sub">✅ Paid &nbsp;·&nbsp; ❌ Owing &nbsp;·&nbsp; ⏳ Upcoming</p>
        <div class="week-grid">{pills}</div></div>""")

    if next_recipient:
        urgent_cls = "urgent" if days_to_payout<=7 else ""
        html(f"""<div class="countdown-banner">
            <div class="countdown-left"><div class="countdown-label">Next Group Payout</div>
                <div class="countdown-name">{next_recipient}</div>
                <div class="countdown-pool">GHS {fmt_num(next_net_pool)} &nbsp;·&nbsp; {format_date(next_payout_date)}</div>
            </div>
            <div class="countdown-right"><div class="countdown-days {urgent_cls}">{days_to_payout}</div>
                <div class="countdown-days-label">days away</div></div>
        </div>""")

    ind = io.StringIO()
    ind.write(f"👋 Hi *{member_view}*!\n\n")
    ind.write(f"📊 *YOUR SUSU UPDATE — WK {current_elapsed_week}*\n")
    ind.write(f"💰 Monthly Tier: GHS {fmt_num(mr['m_monthly'])} · Weekly: GHS {fmt_num(mr['m_weekly'])}\n")
    ind.write(f"📋 Status: *{mr['standing']}*\n")
    ind.write(f"✅ Weeks Paid: {mr['total_paid']} / {total_weeks}\n\n")
    ind.write("📅 *WEEKLY BREAKDOWN*\n")
    for w in range(1,total_weeks+1):
        p     = paid(member_view,w)
        icon  = "✅" if p else ("⏳" if w>current_elapsed_week else "❌")
        label = "Paid" if p else ("Upcoming" if w>current_elapsed_week else "Owing")
        ind.write(f"  Wk {w:02d}: {icon} {label}\n")
    if next_recipient:
        ind.write(f"\n🎁 Next payout: *{next_recipient}* on *{format_date(next_payout_date)}*\n")
    ind.write("\nThank you! 🙏")

    html('<div class="glass-card"><p class="sec-label">Share</p><p class="sec-title">My Update</p><p class="sec-sub">Copy and paste into WhatsApp</p></div>')
    wa_block(ind.getvalue(), f"{member_view}_W{current_elapsed_week}.txt", "dl_member")

    html(f'<div class="foot">Read-only view · {member_view} · Susu Savings</div>')
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
sync_ago = int((datetime.now()-st.session_state.last_sync).total_seconds()/60)
sync_txt = "just now" if sync_ago<1 else f"{sync_ago}m ago"
sb_col,rf_col,tg_col = st.columns([3,1,1])
with sb_col:
    html(f"""<div class="status-bar"><span><span class="status-dot"></span><span class="status-live">Live</span></span><span class="status-sync">Synced {sync_txt} &nbsp;·&nbsp; Google Sheets</span></div>""")
with rf_col:
    if st.button("↻ Refresh", key="refresh_btn", type="secondary"):
        load_all_into_state(gsheet); flash("Refreshed from Google Sheets"); st.rerun()
with tg_col:
    if st.button(f"{T['toggle_icon']} {T['toggle_label']}", key="theme_toggle", type="secondary"):
        st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()

html(f"""
    <div class="hero">
        <div class="hero-left">
            <div class="hero-title">💸 Susu Savings Dashboard</div>
            <div class="hero-sub">{num_members} members &nbsp;·&nbsp; {format_date(start_dt)} → {format_date(end_date)}</div>
            <div class="hero-badge">🔓 &nbsp;Admin session active</div>
        </div>
        {completion_ring(program_pct)}
    </div>
""")

# Chips
gap_class  = "chip-value-red" if collection_gap>0 else "chip-value-green"
gap_label  = f"−GHS {fmt_num(collection_gap)}" if collection_gap>0 else "On track"
snaps      = st.session_state.get("snapshots",{})
prev_snap  = snaps.get(str(current_elapsed_week-1), None)
if prev_snap is not None and current_elapsed_week>1:
    snap_delta = total_cash_held-float(prev_snap)
    d_arrow    = "↑" if snap_delta>=0 else "↓"
    d_color    = "#34d399" if snap_delta>=0 else "#f87171"
    delta_html = f'<div style="font-size:10px;color:{d_color};margin-top:3px;font-weight:600">{d_arrow} GHS {fmt_num(abs(snap_delta))} vs last week</div>'
else:
    delta_html = f'<div style="font-size:10px;color:{T["sub_color"]};margin-top:3px;">No prior snapshot yet</div>'

html(f"""
    <div class="chip-row">
        <div class="chip"><div class="chip-label">Cash Held</div><div class="chip-value">GHS {fmt_num(total_cash_held)}</div>{delta_html}</div>
        <div class="chip"><div class="chip-label">Week</div><div class="chip-value">{current_elapsed_week} / {total_weeks}</div></div>
        <div class="chip"><div class="chip-label">Next Payout</div><div class="chip-value-amber">{days_to_payout} days</div></div>
        <div class="chip"><div class="chip-label">Collection</div><div class="{gap_class}">{gap_label}</div><div class="chip-sub">Expected GHS {fmt_num(total_expected_so_far)}</div></div>
    </div>
""")

# ── contributions card ────────────────────────────────────────────────────────
rows_html = ""
for r in contrib_rows:
    is_owing  = r["owing"]>0
    row_class = "owing" if is_owing else "ok"
    badge     = f'<span class="badge-owe">Owing GHS {fmt_num(r["owing"])}</span>' if is_owing else '<span class="badge-ok">Up to date</span>'
    streak_html = f'<span class="streak-badge">🔴 {r["streak"]}wk streak</span>' if r["streak"]>=2 else ""
    rows_html += (f'<tr class="{row_class}">'
                  f'<td><span class="cell-name">{r["member"]}</span></td>'
                  f'<td>GHS {fmt_num(r["m_monthly"])}</td><td>GHS {fmt_num(r["m_weekly"])}</td>'
                  f'<td>{r["total_paid"]} / {total_weeks}</td>'
                  f'<td>{badge}{streak_html}</td></tr>')

html(f"""<div class="glass-card">
    <div id="section-payments"></div><p class="sec-label">Members</p>
    <p class="sec-title">Contributions</p>
    <p class="sec-sub">Weekly targets and payment standing · 🔴 streak = consecutive missed weeks</p>
    <table class="data-table">
        <thead><tr><th>Member</th><th>Monthly</th><th>Weekly</th><th>Weeks Paid</th><th>Status</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table></div>""")

# ── payout schedule card ──────────────────────────────────────────────────────
pay_rows_html = ""
for r in schedule_rows:
    bar_pct = min(r['pct'],100)
    if r['disbursed']:
        status_badge = f'<span class="badge-ok">✅ Paid GHS {fmt_num(r["disb_amt"])}</span>'
        if r['disb_date']: status_badge += f'<div style="font-size:10px;color:{T["sub_color"]};margin-top:3px">{r["disb_date"]}</div>'
    else:
        status_badge = '<span class="badge-pending">⏳ Pending</span>'
    if r['days_away'] is not None:
        urg = "urgent" if r['days_away']<=7 else ""
        days_cell = f'<div style="margin-top:4px"><span class="days-badge {urg}">{r["days_away"]}d away</span></div>'
    else:
        days_cell = f'<div style="margin-top:4px;font-size:10px;color:{T["sub_color"]}">Past</div>'
    early_note = '<div class="early-eligible">⚡ Pool fully collected — eligible for early payout</div>' if r['early_ok'] else ""
    pay_rows_html += (f'<tr class="plain">'
                      f'<td><span class="cell-name">{r["turn"]}</span></td>'
                      f'<td>{r["recipient"]}</td>'
                      f'<td>{r["date"]}{days_cell}</td>'
                      f'<td>GHS {r["fee"]}</td>'
                      f'<td>GHS {r["pool"]}{early_note}'
                      f'<div class="pbar-wrap"><div class="pbar-fill" style="width:{bar_pct}%"></div></div></td>'
                      f'<td>GHS {r["collected"]}</td>'
                      f'<td>GHS {r["remaining"]}</td>'
                      f'<td>{status_badge}</td></tr>')

html(f"""<div class="glass-card">
    <div id="section-payouts"></div><p class="sec-label">Rotation</p>
    <p class="sec-title">Payout Schedule</p>
    <p class="sec-sub">Collected is calculated from weekly payments · ⚡ early payout eligible when pool is full</p>
    <table class="data-table">
        <thead><tr><th>Turn</th><th>Recipient</th><th>Date</th><th>Admin Fee</th><th>Net Pool</th><th>Collected</th><th>Remaining</th><th>Status</th></tr></thead>
        <tbody>{pay_rows_html}</tbody>
    </table></div>""")

# ── exports (#6) ──────────────────────────────────────────────────────────────
buf = io.StringIO()
buf.write(f"📌 *WK {current_elapsed_week} UPDATE*\n")
buf.write(f"💰 *Cash at Hand:* GHS {fmt_num(total_cash_held)}\n")
buf.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
buf.write("👥 *MEMBERS*\n")
for r in wa_contrib_rows:
    streak_note = f" · 🔴 {r['streak']}wk streak" if r['streak']>=2 else ""
    buf.write(f"{'✅' if 'Up' in r['standing'] else '❌'} *{r['member']}*: {r['standing']}{streak_note}\n")
buf.write("\n🎁 *PAYOUTS*\n")
for r in wa_payout_rows:
    tag = " ✅ paid" if r['disbursed'] else f" · GHS {r['balance']} to go"
    buf.write(f"{r['recipient']} · {r['date']}{tag}\n")

owing_members = [r for r in wa_contrib_rows if "Owing" in r["standing"]]
rem = io.StringIO()
rem.write(f"🔔 *SUSU PAYMENT REMINDER — WK {current_elapsed_week}*\n\n")
if owing_members:
    rem.write("The following members have outstanding payments:\n\n")
    for r in owing_members:
        streak_note = f" (🔴 {r['streak']} weeks in a row)" if r['streak']>=2 else ""
        rem.write(f"❌ *{r['member']}*: {r['standing']}{streak_note}\n")
    if next_recipient:
        rem.write(f"\nPlease make payment as soon as possible.\nNext payout: *{next_recipient}* on *{format_date(next_payout_date)}*\n")
    rem.write("Thank you 🙏")
else:
    rem.write("✅ All members are up to date! Great work everyone 🎉")

ob = io.StringIO()
ob.write("📋 *SUSU GROUP — ONBOARDING DETAILS*\n")
ob.write(f"🗓️ *Start Date:* {format_date(start_dt)}\n")
ob.write(f"🏁 *End Date:* {format_date(end_date)}\n")
ob.write(f"👥 *Members:* {num_members} · *Cycle:* {total_weeks} weeks\n\n")
ob.write("ℹ️ *HOW IT WORKS*\n")
ob.write("• Contributions are weekly. Each \"month\" in the schedule is exactly 4 weeks, so payout dates are fixed by week count and may not fall on the same calendar date each month.\n")
if fee_frac>0: ob.write(f"• An admin fee of {fmt_num(st.session_state.admin_fee_percentage)}% is deducted from each payout.\n")
ob.write("• Each member has a private link to check their own standing.\n\n")
ob.write("👤 *MEMBER DETAILS*\n")
for r in contrib_rows:
    ob.write(f"*{r['member']}*\n  • Monthly Tier: GHS {fmt_num(r['m_monthly'])}\n  • Weekly Target: GHS {fmt_num(r['m_weekly'])}\n\n")
ob.write("🎁 *PAYOUT SCHEDULE*\n")
for r in schedule_rows:
    ob.write(f"*{r['turn']} — {r['recipient']}*\n  • Payout Date: {r['date']}\n  • Net Pool: GHS {r['pool']}\n\n")

ch = io.StringIO()
ch.write(f"📊 *CONTRIBUTION HISTORY — WK {current_elapsed_week}*\n")
ch.write(f"🗓️ *Period:* {format_date(start_dt)} → {format_date(end_date)}\n\n")
for member in members:
    ch.write(f"👤 *{member}* (GHS {fmt_num(weekly(member))}/wk)\n")
    for w in range(1,total_weeks+1):
        p     = paid(member,w)
        icon  = "✅" if p else ("⏳" if w>current_elapsed_week else "❌")
        label = "Paid" if p else ("Upcoming" if w>current_elapsed_week else "Owing")
        ch.write(f"  Wk {w:02d}: {icon} {label}\n")
    ch.write("\n")

html(f"""<div class="glass-card">
    <div id="section-exports"></div><p class="sec-label">Export</p>
    <p class="sec-title">WhatsApp Messages</p>
    <p class="sec-sub">Ready-to-paste updates for the group chat</p></div>""")
t1,t2,t3,t4 = st.tabs(["📥 Weekly Update","🔔 Reminder","📋 Onboarding","📊 History"])
with t1: wa_block(buf.getvalue(), f"Susu_W{current_elapsed_week}.txt", "dl_weekly")
with t2: wa_block(rem.getvalue(), f"Susu_Reminder_W{current_elapsed_week}.txt", "dl_rem")
with t3: wa_block(ob.getvalue(),  "Susu_Onboarding.txt", "dl_ob")
with t4: wa_block(ch.getvalue(),  f"Susu_History_W{current_elapsed_week}.txt", "dl_hist")

# ── admin panel ───────────────────────────────────────────────────────────────
html('<div id="section-admin"></div><p class="sec-label" style="margin-top:24px">Admin</p><p class="sec-title">Group Controls</p><p class="sec-sub">Update settings, record payments and payouts</p>')

with st.expander("⚙️  Group Settings"):
    c1,c2,c3 = st.columns(3)
    with c1: new_start = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    with c2: new_base  = st.number_input("Base Monthly (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    with c3: new_fee   = st.number_input("Admin Fee (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    new_names = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
    html(f'<p style="font-size:11px;color:{T["sub_color"]}">Existing payment records are kept when you add or reorder members. Renaming a member starts them fresh, so fix typos before the first payment is recorded.</p>')
    if st.button("Save Settings", key="save_settings"):
        try: datetime.strptime(new_start,"%Y-%m-%d")
        except ValueError: st.error("Date format must be YYYY-MM-DD."); st.stop()
        st.session_state.start_date=new_start; st.session_state.base_monthly=new_base
        st.session_state.admin_fee_percentage=new_fee; st.session_state.names_input=new_names
        save_all(gsheet)
        append_log(gsheet,{"type":"setting","text":"Group settings updated","time":now_str()})
        flash("Settings saved"); st.rerun()

with st.expander("💰  Custom Member Tiers"):
    tier_cols = st.columns(min(num_members,4))
    new_tiers = {}
    for idx,m in enumerate(members):
        with tier_cols[idx%4]:
            new_tiers[m] = st.number_input(m, value=float(tier(m)), step=50.0, key=f"tier_{m}")
    if st.button("Save Tiers", key="save_tiers"):
        st.session_state.member_tiers.update(new_tiers); save_all(gsheet)
        append_log(gsheet,{"type":"setting","text":"Member tiers updated","time":now_str()})
        flash("Tiers saved"); st.rerun()

with st.expander("📝  Bulk Payment Entry"):
    html(f'<p style="font-size:12px;color:{T["sub_color"]};margin-bottom:4px">Current week: <strong style="color:{T["sec_title"]}">Week {current_elapsed_week}</strong> of {total_weeks}. W* = current week.</p>')
    bulk_payments = {}
    for member in members:
        html(f'<div style="font-size:12px;font-weight:600;color:{T["td_color"]};margin:10px 0 6px">{member}</div>')
        cols = st.columns(min(total_weeks,8))
        week_vals = {}
        for w in range(1,total_weeks+1):
            with cols[(w-1)%8]:
                label = f"W{w}*" if w==current_elapsed_week else f"W{w}"
                week_vals[str(w)] = st.checkbox(label, value=paid(member,w), key=f"bulk_{member}_{w}")
        bulk_payments[member] = week_vals
    if st.button("Save All Payments", key="bulk_save"):
        already_paid_warnings = []
        for mbr,wv in bulk_payments.items():
            for wk,ticked in wv.items():
                if not ticked and paid(mbr,int(wk)):
                    already_paid_warnings.append(f"{mbr} — Week {wk} (was paid, now unticked)")
        if already_paid_warnings and not st.session_state.get("bulk_confirm_overwrite",False):
            st.warning("⚠️ The following weeks will be marked as **unpaid** — confirm?\n\n" + "\n".join(f"• {w}" for w in already_paid_warnings))
            oc1,oc2 = st.columns(2)
            with oc1:
                if st.button("✓ Confirm save", key="bulk_confirm_yes"):
                    st.session_state.bulk_confirm_overwrite=True; st.rerun()
            with oc2:
                if st.button("✗ Cancel", key="bulk_confirm_no", type="secondary"): st.rerun()
        else:
            st.session_state.bulk_confirm_overwrite=False
            for mbr,wv in bulk_payments.items():           # merge, never replace (#1)
                st.session_state.payments.setdefault(mbr,{}).update(wv)
            save_all(gsheet)
            total_checked = sum(sum(1 for v in wv.values() if v) for wv in bulk_payments.values())
            append_log(gsheet,{"type":"payment","text":f"Bulk payment update — {total_checked} weeks marked paid","time":now_str()})
            new_held = sum(weekly(m) for m in members for w in range(1,total_weeks+1) if paid(m,w)) - total_payouts_dist
            save_snapshot(gsheet,current_elapsed_week,new_held)
            flash("All payments saved"); st.rerun()

with st.expander("🎁  Record Payout"):
    month_options = [f"{r['turn']} — {r['recipient']}" for r in schedule_rows]
    sel_month_lbl = st.selectbox("Payout Turn", month_options, key="payout_month")
    sr        = schedule_rows[month_options.index(sel_month_lbl)]
    mkey      = sr["turn"]; rec_name = sr["recipient"]
    html(f"""<div style="font-size:12px;color:{T['td_color']};line-height:1.7;margin-bottom:8px">
        Net pool: <strong style="color:{T['sec_title']}">GHS {sr['pool']}</strong> &nbsp;·&nbsp;
        Collected so far (from weekly ticks): <strong style="color:{T['sec_title']}">GHS {sr['collected']}</strong> &nbsp;·&nbsp;
        Remaining: <strong style="color:{T['sec_title']}">GHS {sr['remaining']}</strong></div>""")
    if sr["remaining"] != "0" and not sr["disbursed"]:
        st.warning(f"Pool is not yet fully collected. Record missing weeks in Bulk Payment Entry first, or disburse a partial amount.")
    default_amt   = sr["disb_amt"] if sr["disbursed"] else min(sr["net_col"], sr["net_pool_amt"])
    new_amt       = st.number_input(f"Amount handed to {rec_name} (GHS)", value=float(round(default_amt,2)), min_value=0.0, max_value=float(sr["net_pool_amt"]), step=50.0, key="payout_amt")
    new_disbursed = st.checkbox("Mark as disbursed ✅", value=sr["disbursed"], key="payout_disbursed")
    if not st.session_state.get("confirm_payout",False):
        if st.button("Save Payout", key="save_payout_btn"):
            st.session_state.confirm_payout=True; st.rerun()
    else:
        verb = "Record disbursement of" if new_disbursed else "Clear disbursement for"
        st.warning(f"⚠️ Confirm: {verb} GHS {fmt_num(new_amt)} — {rec_name} ({mkey})?")
        cc1,cc2 = st.columns(2)
        with cc1:
            if st.button("✓ Yes, confirm", key="confirm_yes"):
                ps = st.session_state.payout_status.setdefault(mkey,{})
                ps.pop("amount_collected", None)            # legacy field — collections are now derived
                ps["disbursed"] = new_disbursed
                ps["disbursed_amount"] = new_amt if new_disbursed else 0.0
                ps["disbursed_date"] = now_str() if new_disbursed else ""
                save_all(gsheet)
                txt = f"{mkey} payout disbursed to {rec_name} — GHS {fmt_num(new_amt)}" if new_disbursed else f"{mkey} disbursement cleared for {rec_name}"
                append_log(gsheet,{"type":"payout","text":txt,"time":now_str()})
                new_dist = sum(disbursed_amount(f"Month {i+1}") for i in range(num_members))
                save_snapshot(gsheet,current_elapsed_week,total_cash_collected-new_dist)
                st.session_state.confirm_payout=False
                flash(f"Payout for {rec_name} saved"); st.rerun()
        with cc2:
            if st.button("✗ Cancel", key="confirm_no", type="secondary"):
                st.session_state.confirm_payout=False; st.rerun()

with st.expander("🔗  Member Links"):
    try:    base_url = st.context.url.split("?")[0]
    except Exception: base_url = ""
    html(f'<p style="font-size:12px;color:{T["sub_color"]};margin-bottom:10px">Each member gets a private link. Anyone with the link can see that member\'s standing, so share each link only with its owner.{"" if base_url else " Prefix each code with your app URL."}</p>')
    link_rows = ""
    for m in members:
        tok  = st.session_state.member_tokens.get(m,"")
        link = f"{base_url}?m={tok}" if base_url else f"?m={tok}"
        link_rows += f'<tr class="plain"><td><span class="cell-name">{m}</span></td><td><span class="token-link">{link}</span></td></tr>'
    html(f'<table class="data-table"><thead><tr><th>Member</th><th>Private link</th></tr></thead><tbody>{link_rows}</tbody></table>')
    lk1,lk2 = st.columns([2,1])
    with lk1: regen_member = st.selectbox("Regenerate link for", members, key="regen_member", label_visibility="collapsed")
    with lk2:
        if st.button("↻ New link", key="regen_btn", type="secondary"):
            st.session_state.member_tokens[regen_member] = pysecrets.token_urlsafe(6)
            save_cell(gsheet,"tokens",st.session_state.member_tokens)
            append_log(gsheet,{"type":"setting","text":f"Member link regenerated for {regen_member}","time":now_str()})
            flash(f"New link generated for {regen_member}"); st.rerun()

with st.expander("🔑  Change Passcode"):
    html(f'<p style="font-size:12px;color:{T["sub_color"]};margin-bottom:8px">Enter current passcode to confirm, then set a new one. Passcodes are stored hashed.</p>')
    cp1,cp2,cp3 = st.columns(3)
    with cp1: old_pw  = st.text_input("Current Passcode", type="password", key="old_pw")
    with cp2: new_pw1 = st.text_input("New Passcode", type="password", key="new_pw1")
    with cp3: new_pw2 = st.text_input("Confirm New Passcode", type="password", key="new_pw2")
    if st.button("Update Passcode", key="update_pw"):
        stored_pw = st.session_state.get("admin_passcode",ADMIN_PW)
        if not check_pw(old_pw, stored_pw): st.error("Current passcode is incorrect.")
        elif len(new_pw1) < 6: st.error("New passcode must be at least 6 characters.")
        elif new_pw1!=new_pw2: st.error("New passcodes do not match.")
        else:
            st.session_state.admin_passcode=hash_pw(new_pw1)
            save_cell(gsheet,"passcode",st.session_state.admin_passcode)
            append_log(gsheet,{"type":"setting","text":"Passcode changed","time":now_str()})
            flash("Passcode updated"); st.rerun()

if st.session_state.history:
    with st.expander("🕒  Activity Log"):
        dot_map = {"payment":"log-dot","payout":"log-dot log-dot-payout","setting":"log-dot log-dot-setting"}
        log_html = ""
        for entry in st.session_state.history[:20]:
            dot_class = dot_map.get(entry.get("type","payment"),"log-dot")
            log_html += (f'<div class="log-entry"><div class="{dot_class}"></div>'
                         f'<div class="log-text"><strong>{entry.get("text","—")}</strong></div>'
                         f'<div class="log-time">{entry.get("time","")}</div></div>')
        html(log_html)

html('<div class="gdivider"></div>')
if st.button("🔒  Lock Dashboard", key="logout", type="secondary"):
    st.session_state.authenticated=False; st.rerun()

html(f'''<div class="bottom-nav">
    <button class="nav-item" onclick="navTo('top')"><span class="nav-icon">🏠</span><span class="nav-label">Home</span></button>
    <button class="nav-item" onclick="navTo('section-payments')"><span class="nav-icon">👥</span><span class="nav-label">Members</span></button>
    <button class="nav-item" onclick="navTo('section-payouts')"><span class="nav-icon">🎁</span><span class="nav-label">Payouts</span></button>
    <button class="nav-item" onclick="navTo('section-exports')"><span class="nav-icon">📤</span><span class="nav-label">Export</span></button>
    <button class="nav-item" onclick="navTo('section-admin')"><span class="nav-icon">⚙️</span><span class="nav-label">Admin</span></button>
</div>''')
html('<div class="foot">Backed by Google Sheets · Secured with passcode</div>')
