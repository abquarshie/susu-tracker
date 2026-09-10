import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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
""", unsafe_allow_html=True)

# ── HTML helper ───────────────────────────────────────────────────────────────
# Streamlit's Markdown parser treats a blank line followed by a line indented
# 4+ spaces as a code block. This strips leading whitespace from every line so
# multi-line HTML strings render as HTML, never as literal code.
def html(s):
    st.markdown(re.sub(r"\n[ \t]+", "\n", s).strip(), unsafe_allow_html=True)

# ── theme (single dark palette — softened so text stays legible) ─────────────
T = {
    "bg":"linear-gradient(135deg,#161f2f 0%,#1b2536 50%,#172131 100%)",
    "card_bg":"rgba(255,255,255,0.05)","card_border":"rgba(255,255,255,0.09)",
    "card_shadow":"0 4px 20px rgba(0,0,0,0.22),inset 0 1px 0 rgba(255,255,255,0.05)",
    "chip_bg":"rgba(255,255,255,0.06)","chip_border":"rgba(255,255,255,0.10)",
    "status_bg":"rgba(255,255,255,0.03)","status_border":"rgba(255,255,255,0.08)",
    "sync_color":"#94a5bd","title_color":"#f4f7fb","sub_color":"#9db0c7",
    "label_color":"#8cc6ec","sec_title":"#e9eff7","th_color":"#8cc6ec",
    "td_color":"#d2dcea","td_border":"rgba(255,255,255,0.055)","th_border":"rgba(255,255,255,0.09)",
    "member_name":"#f4f7fb","input_bg":"rgba(255,255,255,0.08)","input_border":"rgba(255,255,255,0.14)",
    "input_color":"#eef3f9","lock_bg":"rgba(255,255,255,0.07)","lock_border":"rgba(255,255,255,0.13)",
    "lock_title":"#f4f7fb","lock_sub":"#9db0c7","exp_bg":"rgba(255,255,255,0.05)",
    "exp_border":"rgba(255,255,255,0.10)","exp_color":"#dbe4ef","exp_content":"rgba(255,255,255,0.03)",
    "gdiv":"rgba(86,200,245,0.18)","foot_color":"#7386a0","foot_border":"rgba(255,255,255,0.07)",
    "btn_bg":"rgba(37,99,235,0.85)","btn_border":"rgba(96,165,250,0.45)",
    "btn2_bg":"rgba(255,255,255,0.08)","btn2_color":"#dbe4ef","btn2_border":"rgba(255,255,255,0.14)",
    "dl_bg":"rgba(255,255,255,0.06)","dl_border":"rgba(86,200,245,0.32)",
    "log_border":"rgba(255,255,255,0.06)","log_color":"#b7c4d6","log_strong":"#eef3f9","log_time":"#94a5bd",
    "ring_track":"rgba(255,255,255,0.10)","bar_bg":"rgba(255,255,255,0.12)",
    "streak_bg":"rgba(239,68,68,0.14)","streak_color":"#fca5a5","streak_border":"rgba(239,68,68,0.3)",
}

dl_color = "#56c8f5"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    header{{visibility:hidden!important;height:0!important;}} #MainMenu{{visibility:hidden!important;}}
    .stDeployButton{{display:none!important;}} footer{{visibility:hidden!important;}}
    section[data-testid="stSidebar"]{{display:none!important;width:0!important;}}
    [data-testid="collapsedControl"]{{display:none!important;width:0!important;}}
    [data-testid="stSidebarNav"]{{display:none!important;}} button[kind="header"]{{display:none!important;}}
    .block-container{{padding-top:0!important;padding-bottom:3rem!important;max-width:min(1180px,96vw)!important;padding-left:clamp(12px,2vw,40px)!important;padding-right:clamp(12px,2vw,40px)!important;}}
    html,body,[class*="css"]{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}}
    .main,.stApp{{background:{T['bg']}!important;min-height:100vh;}}
    html{{scroll-behavior:smooth;}}

    .status-dot{{width:7px;height:7px;background:#34d399;border-radius:50%;display:inline-block;margin-right:7px;animation:pulse 2s infinite;}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}

    .lock-outer{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;margin-top:-2rem;}}
    .lock-card{{background:{T['lock_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['lock_border']};border-radius:24px;padding:48px 40px;text-align:center;width:100%;max-width:360px;box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 0 rgba(255,255,255,0.4);}}
    .lock-icon{{font-size:44px;margin-bottom:16px;display:block;}}
    .lock-title{{font-size:22px;font-weight:700;color:{T['lock_title']};margin-bottom:6px;}}
    .lock-sub{{font-size:14px;color:{T['lock_sub']};margin-bottom:0;}}

    /* ── V3 command-centre layout ─────────────────────────────────────────── */
    .v3-status{{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:13px;color:{T['td_color']};
        background:{T['status_bg']};border:1px solid {T['status_border']};border-radius:12px;padding:9px 16px;margin-bottom:14px;}}
    .v3-status strong{{color:#34d399;font-weight:700;}}
    .v3-status-muted{{color:{T['sync_color']};}}

    .v3-header{{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:18px;}}
    .v3-kicker{{font-size:11px;font-weight:700;color:{T['label_color']};letter-spacing:1.4px;text-transform:uppercase;margin-bottom:6px;}}
    .v3-title{{font-size:28px;font-weight:800;color:{T['title_color']};letter-spacing:-0.5px;line-height:1.15;margin:0 0 6px;}}
    .v3-subtitle{{font-size:14px;color:{T['sub_color']};margin:0;}}
    .v3-header-actions{{display:flex;gap:8px;flex-wrap:wrap;}}
    .v3-action{{display:inline-block;font-size:13px;font-weight:600;padding:9px 15px;border-radius:11px;text-decoration:none!important;white-space:nowrap;transition:all 0.18s;}}
    .v3-action.secondary{{background:{T['btn2_bg']};border:1px solid {T['btn2_border']};color:{T['btn2_color']}!important;}}
    .v3-action.primary{{background:rgba(37,99,235,0.9);border:1px solid {T['btn_border']};color:#fff!important;box-shadow:0 2px 10px rgba(29,78,216,0.28);}}
    .v3-action:hover{{transform:translateY(-1px);filter:brightness(1.12);}}

    .v3-kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px;}}
    .v3-kpi{{background:{T['chip_bg']};border:1px solid {T['chip_border']};border-radius:16px;padding:18px 20px;
        box-shadow:0 2px 12px rgba(0,0,0,0.12),inset 0 1px 0 rgba(255,255,255,0.05);min-width:0;}}
    .v3-kpi-primary{{background:linear-gradient(150deg,rgba(56,189,248,0.14),rgba(255,255,255,0.05));border-color:rgba(86,200,245,0.3);}}
    .v3-kpi-label{{font-size:11px;font-weight:700;color:{T['label_color']};letter-spacing:1.1px;margin-bottom:8px;}}
    .v3-kpi-value{{font-size:27px;font-weight:800;color:{T['title_color']};line-height:1.1;letter-spacing:-0.5px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .v3-kpi-value span{{font-size:16px;font-weight:600;color:{T['sub_color']};}}
    .v3-kpi-name{{color:#56c8f5;}}
    .v3-kpi-good{{color:#34d399;}} .v3-kpi-bad{{color:#f87171;}}
    .v3-kpi-meta{{font-size:12px;color:{T['sub_color']};margin-top:7px;line-height:1.45;}}
    .v3-kpi-delta{{font-size:12px;color:{T['sub_color']};margin-top:4px;}}

    .v3-progress{{background:{T['bar_bg']};border-radius:5px;height:5px;overflow:hidden;margin-top:10px;}}
    .v3-progress span{{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#34d399,#56c8f5);transition:width 0.4s ease;}}
    .v3-progress.tall{{height:8px;border-radius:6px;margin-top:6px;}}

    .v3-command-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;align-items:start;}}
    .v3-kpis-2{{grid-template-columns:repeat(2,1fr);}}
    .v3-alert{{background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.3);border-radius:16px;padding:18px 20px;}}
    .v3-alert-top{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;}}
    .v3-alert-top .v3-kicker{{margin-bottom:0;color:#fbbf24;}}
    .v3-alert-amount{{font-size:27px;font-weight:800;color:#fbbf24;line-height:1.1;letter-spacing:-0.5px;}}
    .v3-alert-names{{font-size:13px;color:{T['td_color']};line-height:1.5;margin-top:6px;}}
    .v3-alert-foot{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:12px;
        font-size:12px;color:{T['sub_color']};}}
    .v3-alert-foot a{{font-weight:700;color:#fbbf24!important;text-decoration:none!important;white-space:nowrap;}}
    .v3-alert-clear{{background:rgba(52,211,153,0.08);border-color:rgba(52,211,153,0.28);}}
    .v3-alert-clear .v3-kicker,.v3-alert-clear .v3-alert-amount,.v3-alert-clear .v3-alert-foot a{{color:#34d399!important;}}
    .v3-days.v3-clear{{color:#34d399;background:rgba(52,211,153,0.14);border-color:rgba(52,211,153,0.3);}}

    .v3-next-card{{background:{T['card_bg']};border:1px solid {T['card_border']};border-radius:16px;padding:18px 20px;box-shadow:{T['card_shadow']};}}
    .v3-next-top{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;}}
    .v3-next-top .v3-kicker{{margin-bottom:0;}}
    .v3-days{{font-size:12px;font-weight:700;color:#818cf8;background:rgba(129,140,248,0.14);border:1px solid rgba(129,140,248,0.28);
        border-radius:20px;padding:3px 11px;white-space:nowrap;}}
    .v3-days.v3-urgent{{color:#fbbf24;background:rgba(251,191,36,0.14);border-color:rgba(251,191,36,0.32);}}
    .v3-next-main{{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px;}}
    .v3-recipient{{font-size:23px;font-weight:800;color:{T['title_color']};letter-spacing:-0.4px;}}
    .v3-next-date{{font-size:13px;color:{T['sub_color']};margin-top:2px;}}
    .v3-next-amount{{font-size:21px;font-weight:800;color:#56c8f5;white-space:nowrap;}}
    .v3-funding-row{{display:flex;justify-content:space-between;font-size:12px;color:{T['sub_color']};}}
    .v3-funding-row strong{{color:{T['td_color']};font-weight:700;}}
    .v3-funding-meta{{font-size:12px;color:{T['sub_color']};margin-top:7px;}}

    .v3-section-card{{padding:22px 24px;}}
    .v3-section-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px;flex-wrap:wrap;}}
    .v3-inline-link{{font-size:13px;font-weight:600;color:{dl_color}!important;text-decoration:none!important;white-space:nowrap;}}
    .v3-timeline{{display:flex;gap:6px;margin:2px 0 14px;}}
    .v3-timeline span{{flex:1;height:6px;border-radius:4px;background:{T['bar_bg']};}}
    .v3-timeline span.done{{background:linear-gradient(90deg,#34d399,#56c8f5);}}
    .v3-timeline span.current{{background:#fbbf24;box-shadow:0 0 10px rgba(251,191,36,0.45);}}
    .member-avatar{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;
        background:rgba(86,200,245,0.16);color:#56c8f5;font-size:13px;font-weight:700;margin-right:9px;vertical-align:middle;}}
    .v3-ahead{{color:#34d399;}}

    .glass-card{{background:{T['card_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['card_border']};border-radius:16px;padding:20px 22px;margin-bottom:14px;box-shadow:{T['card_shadow']};}}
    .sec-label{{font-size:11px;font-weight:700;color:{T['label_color']};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
    .sec-title{{font-size:18px;font-weight:700;color:{T['sec_title']};margin:0 0 2px 0;}}
    .sec-sub{{font-size:13px;color:{T['sub_color']};margin:0 0 14px 0;}}
    .cell-sub{{font-size:12px;color:{T['sub_color']};margin-top:2px;}}

    .data-table{{width:100%;border-collapse:collapse;}}
    .data-table th{{font-size:12px;font-weight:600;color:{T['th_color']};text-transform:uppercase;letter-spacing:0.6px;padding:9px 12px;border-bottom:1px solid {T['th_border']};text-align:left;}}
    .data-table td{{font-size:15px;color:{T['td_color']};padding:11px 12px;border-bottom:1px solid {T['td_border']};vertical-align:middle;}}
    .data-table tr:last-child td{{border-bottom:none;}}
    .data-table tr.owing td:first-child{{border-left:2px solid #fbbf24;padding-left:10px;}}
    .data-table tr.ok td:first-child{{border-left:2px solid #34d399;padding-left:10px;}}
    .data-table tr.plain td:first-child{{border-left:2px solid transparent;padding-left:10px;}}
    .cell-name{{font-weight:600;color:{T['member_name']};}}
    .badge-ok{{background:rgba(52,211,153,0.12);color:#34d399;border:1px solid rgba(52,211,153,0.25);border-radius:20px;padding:3px 11px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .badge-owe{{background:rgba(251,191,36,0.12);color:#fbbf24;border:1px solid rgba(251,191,36,0.25);border-radius:20px;padding:3px 11px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .badge-pending{{background:rgba(148,163,184,0.12);color:{T['sub_color']};border:1px solid rgba(148,163,184,0.22);border-radius:20px;padding:3px 11px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .badge-exempt{{background:rgba(148,163,184,0.1);color:{T['sub_color']};border:1px dashed {T['card_border']};border-radius:20px;padding:3px 11px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .streak-badge{{background:{T['streak_bg']};color:{T['streak_color']};border:1px solid {T['streak_border']};border-radius:20px;padding:2px 9px;font-size:12px;font-weight:600;white-space:nowrap;margin-left:6px;}}
    .exit-tag{{font-size:11px;color:{T['sub_color']};font-weight:600;margin-left:6px;text-transform:uppercase;letter-spacing:0.4px;}}
    .days-badge{{display:inline-block;background:rgba(129,140,248,0.12);color:#818cf8;border:1px solid rgba(129,140,248,0.25);border-radius:10px;padding:2px 8px;font-size:12px;font-weight:600;white-space:nowrap;margin-top:4px;}}
    .days-badge.urgent{{background:rgba(251,191,36,0.12);color:#fbbf24;border-color:rgba(251,191,36,0.3);}}
    .diff-line{{font-size:12px;color:{T['td_color']};font-family:ui-monospace,Menlo,monospace;}}
    .pbar-wrap{{margin-top:6px;background:{T['bar_bg']};border-radius:4px;height:4px;overflow:hidden;}}
    .pbar-fill{{height:4px;border-radius:4px;background:linear-gradient(90deg,#34d399,#38bdf8);transition:width 0.4s ease;}}
    .early-eligible{{font-size:12px;color:#34d399;margin-top:3px;font-weight:600;}}

    .log-entry{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid {T['log_border']};}}
    .log-entry:last-child{{border-bottom:none;}}
    .log-dot{{width:8px;height:8px;border-radius:50%;background:#38bdf8;margin-top:6px;flex-shrink:0;}}
    .log-dot-payout{{background:#818cf8;}} .log-dot-setting{{background:#34d399;}}
    .log-text{{font-size:14px;color:{T['log_color']};line-height:1.45;}}
    .log-text strong{{color:{T['log_strong']};font-weight:600;}}
    .log-time{{font-size:12px;color:{T['log_time']};margin-left:auto;white-space:nowrap;padding-left:12px;}}

    .stTextInput input,.stNumberInput input,.stTextArea textarea{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;color:{T['input_color']}!important;border-radius:10px!important;font-size:15px!important;}}
    .stTextInput input:focus,.stNumberInput input:focus{{border-color:rgba(56,189,248,0.4)!important;box-shadow:0 0 0 2px rgba(56,189,248,0.08)!important;}}
    .stTextInput label,.stNumberInput label,.stTextArea label,.stSelectbox label,.stCheckbox label{{color:{T['label_color']}!important;font-size:12px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.5px;}}
    .stSelectbox > div > div{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;color:{T['input_color']}!important;border-radius:10px!important;}}
    div[data-testid="stButton"]{{width:100%!important;}}
    .stButton > button{{background:{T['btn_bg']}!important;backdrop-filter:blur(8px)!important;color:white!important;border:1px solid {T['btn_border']}!important;border-radius:10px!important;font-weight:600!important;font-size:15px!important;padding:10px 20px!important;width:100%;box-shadow:0 2px 8px rgba(29,78,216,0.25)!important;transition:all 0.2s!important;}}
    .stButton > button:hover{{background:rgba(37,99,235,0.95)!important;box-shadow:0 4px 16px rgba(29,78,216,0.4)!important;}}
    .stButton > button[kind="secondary"]{{background:{T['btn2_bg']}!important;color:{T['btn2_color']}!important;border:1px solid {T['btn2_border']}!important;box-shadow:none!important;}}
    div[data-testid="stDownloadButton"],.stDownloadButton{{width:100%!important;}}
    div[data-testid="stDownloadButton"] > button,.stDownloadButton > button{{background:{T['dl_bg']}!important;backdrop-filter:blur(8px)!important;color:{dl_color}!important;border:1px solid {T['dl_border']}!important;border-radius:10px!important;font-size:15px!important;font-weight:600!important;padding:10px 20px!important;width:100%!important;transition:all 0.2s!important;}}
    details[data-testid="stExpander"]{{background:{T['exp_bg']}!important;backdrop-filter:blur(12px)!important;border:1px solid {T['exp_border']}!important;border-radius:12px!important;margin-bottom:8px!important;overflow:hidden;}}
    details[data-testid="stExpander"] summary{{background:transparent!important;padding:13px 16px!important;}}
    details[data-testid="stExpander"] summary,details[data-testid="stExpander"] summary *{{color:{T['sec_title']}!important;font-size:15px!important;font-weight:600!important;}}
    details[data-testid="stExpander"] summary:hover{{color:{dl_color}!important;}}
    details[data-testid="stExpander"] summary svg{{fill:{T['sec_title']}!important;color:{T['sec_title']}!important;}}
    details[data-testid="stExpander"] > div:not(summary){{background:{T['exp_content']}!important;border-top:1px solid {T['exp_border']}!important;padding:18px!important;}}
    details[data-testid="stExpander"] p,details[data-testid="stExpander"] label,details[data-testid="stExpander"] .stCheckbox span{{color:{T['td_color']};}}
    div[data-testid="stSuccess"]{{background:rgba(16,185,129,0.07)!important;border:1px solid rgba(16,185,129,0.2)!important;border-radius:10px!important;color:#34d399!important;font-size:14px!important;}}
    div[data-testid="stError"]{{background:rgba(239,68,68,0.07)!important;border:1px solid rgba(239,68,68,0.2)!important;border-radius:10px!important;color:#f87171!important;font-size:14px!important;}}
    div[data-testid="stWarning"]{{background:rgba(251,191,36,0.07)!important;border:1px solid rgba(251,191,36,0.2)!important;border-radius:10px!important;color:#fbbf24!important;font-size:14px!important;}}
    .stTabs [data-baseweb="tab-list"]{{gap:6px;background:transparent;}}
    .stTabs [data-baseweb="tab"]{{background:{T['btn2_bg']};border:1px solid {T['btn2_border']};border-radius:10px;padding:7px 15px;color:{T['btn2_color']};font-size:13px;font-weight:600;}}
    .stTabs [aria-selected="true"]{{background:{T['dl_bg']}!important;color:{dl_color}!important;border-color:{T['dl_border']}!important;}}
    .stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{{display:none;}}
    div[data-testid="stCode"] pre,div[data-testid="stCodeBlock"] pre{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;border-radius:12px!important;font-size:14px!important;line-height:1.55!important;}}
    div[data-testid="stCode"] code,div[data-testid="stCodeBlock"] code{{color:{T['td_color']}!important;white-space:pre-wrap!important;}}
    .copy-hint{{font-size:13px;color:{T['sub_color']};margin:-6px 0 8px;}}
    .gdivider{{height:1px;background:linear-gradient(90deg,transparent,{T['gdiv']},transparent);margin:22px 0;}}
    .foot{{text-align:center;font-size:12px;color:{T['foot_color']};margin-top:32px;padding-top:20px;border-top:1px solid {T['foot_border']};}}
    .anchor{{position:relative;top:-70px;display:block;height:0;}}

    /* tablets / small laptops */
    @media (min-width:601px) and (max-width:1280px){{
        .v3-title{{font-size:30px;}} .v3-subtitle{{font-size:15px;}}
        .v3-kpis{{grid-template-columns:repeat(2,1fr);}}
        .v3-kpi-value{{font-size:29px;}}
        .v3-kpi-label,.v3-kicker{{font-size:12px;}}
        .v3-kpi-meta,.v3-kpi-delta{{font-size:13px;}}
        .sec-title{{font-size:19px;}} .sec-sub{{font-size:14px;}}
        .data-table th{{font-size:12px;padding:11px 15px;}}
        .data-table td{{font-size:16px;padding:13px 15px;}}
        .v3-recipient{{font-size:25px;}} .v3-next-amount{{font-size:23px;}}
        .v3-action{{font-size:14px;padding:10px 17px;}}
    }}
    /* landscape tablets: reclaim vertical space */
    @media (min-width:601px) and (max-height:820px) and (orientation:landscape){{
        .glass-card,.v3-section-card{{padding:16px 20px;margin-bottom:12px;}}
        .v3-kpi{{padding:14px 16px;}}
        .data-table td{{padding:10px 15px;}}
    }}
    @media (max-width:600px){{
        .block-container{{padding-bottom:3rem!important;padding-left:10px!important;padding-right:10px!important;}}
        .v3-status{{font-size:12px;padding:8px 12px;flex-wrap:wrap;gap:4px;}}
        .v3-header{{flex-direction:column;align-items:stretch;gap:12px;margin-bottom:14px;}}
        .v3-title{{font-size:22px;}} .v3-subtitle{{font-size:12px;line-height:1.45;}}
        .v3-header-actions{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
        .v3-header-actions .v3-action{{text-align:center;padding:11px 8px;font-size:13px;}}
        .v3-header-actions .v3-action.primary{{grid-column:1 / -1;}}
        .v3-kpis{{grid-template-columns:1fr 1fr;gap:8px;}}
        .v3-kpi{{padding:13px 14px;}}
        .v3-kpi-value{{font-size:21px;}}
        .v3-kpi-primary{{grid-column:1 / -1;}}
        .v3-command-grid{{grid-template-columns:1fr;}}
        .v3-alert{{padding:14px 15px;}}
        .v3-alert-amount{{font-size:23px;}}
        .v3-kpis-2{{grid-template-columns:1fr;}}
        .v3-next-main{{flex-direction:column;align-items:flex-start;gap:6px;}}
        .glass-card,.v3-section-card{{padding:14px 12px!important;border-radius:12px!important;}}
        .v3-section-head{{gap:6px;}}
        .sec-title{{font-size:16px!important;}} .sec-sub{{font-size:12px!important;line-height:1.4;}}
        .data-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;}}
        .data-table th,.data-table td{{padding:9px 10px!important;font-size:13px!important;}}
        .member-avatar{{width:24px;height:24px;font-size:12px;margin-right:7px;}}
        /* payout table: hide the columns that can be re-derived */
        .tbl-payout.has-fee th:nth-child(4),.tbl-payout.has-fee td:nth-child(4),
        .tbl-payout.has-fee th:nth-child(6),.tbl-payout.has-fee td:nth-child(6),
        .tbl-payout.no-fee th:nth-child(5),.tbl-payout.no-fee td:nth-child(5){{display:none;}}
        .swipe-hint{{display:block!important;}}
    }}
    .swipe-hint{{display:none;font-size:12px;color:{T['sub_color']};margin:6px 0 0;}}
    </style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def money(x):
    """All GHS amounts pass through here — kills float drift like 4999.999999."""
    return round(float(x)+1e-9, 2)

def fmt_num(val):
    val = money(val)
    return f"{int(val):,}" if val == int(val) else f"{val:,.2f}"

def format_date(dt):
    d = dt.day
    sfx = 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10,'th')
    return f"{d}{sfx} {dt.strftime('%b %Y')}"

GH_TZ = ZoneInfo("Africa/Accra")
SESSION_TIMEOUT_MINUTES = 30

def now_dt():
    return datetime.now(GH_TZ)

def now_str():
    return now_dt().strftime("%d %b %Y %H:%M")

def parse_display_date(txt):
    """Reverse of format_date: '14th Sep 2026' → date. Returns None if unparseable."""
    if not txt: return None
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", str(txt)).strip()
    try:    return datetime.strptime(cleaned, "%d %b %Y").date()
    except Exception: return None

def greeting():
    h = now_dt().hour
    return "Good morning" if h < 12 else ("Good afternoon" if h < 17 else "Good evening")

def new_id(prefix):
    return f"{prefix}-{now_dt().strftime('%Y%m%d%H%M%S')}-{pysecrets.token_hex(3).upper()}"

# Passwords are stored as salted scrypt hashes. The old SHA-256 format is still
# recognised so existing groups can be upgraded automatically on successful login.
def hash_pw(pw):
    if not isinstance(pw, str) or not pw:
        return ""
    salt = pysecrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + salt.hex() + "$" + digest.hex()

def is_scrypt_hash(val):
    return isinstance(val, str) and val.startswith("scrypt$16384$8$1$") and len(val.split("$")) == 6

def is_legacy_sha256(val):
    return isinstance(val,str) and len(val)==64 and all(c in "0123456789abcdef" for c in val)

def check_pw(entered, stored):
    if not isinstance(entered, str) or not entered:
        return False
    if is_scrypt_hash(stored):
        try:
            _, n, r, p, salt_hex, digest_hex = stored.split("$")
            digest = hashlib.scrypt(entered.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                    n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest_hex)))
            return pysecrets.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False
    if is_legacy_sha256(stored):
        return pysecrets.compare_digest(hashlib.sha256(entered.encode("utf-8")).hexdigest(), stored)
    return pysecrets.compare_digest(entered, stored) if isinstance(stored, str) and stored else False

def flash(msg, kind="success"):
    st.session_state.flash = (msg, kind)

def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        msg, kind = f
        st.toast(msg, icon="✅" if kind=="success" else ("⚠️" if kind=="warning" else "ℹ️"))

def wa_block(text, fname, key):
    html('<p class="copy-hint">Tap the copy icon (top-right of the box) and paste into WhatsApp.</p>')
    st.code(text, language=None)
    st.download_button("⬇️ Download .txt", data=text, file_name=fname, mime="text/plain", key=key, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# STORAGE — one JSON blob, one read per load, rev-guarded writes
# ══════════════════════════════════════════════════════════════════════════════
SCOPES     = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
DATA_WS    = "susu_data"
ADMIN_NAME = "Abre"

def bootstrap_admin_password():
    try:
        return str(st.secrets["app"]["admin_passcode"])
    except Exception:
        return ""

BOOTSTRAP_ADMIN_PW = bootstrap_admin_password()
LEGACY_WS = ["settings","tiers","payments","payout_status","history","snapshots","passcode"]

DEFAULT_SETTINGS = {"start_date":"2026-08-17","base_monthly":1000,"admin_fee_percentage":0.0,
                    "names_input":"Alice, Bob, Charlie, Diana, Frank, Grace"}

def blank_blob():
    return {"rev":0,"settings":dict(DEFAULT_SETTINGS),"tiers":{},"payments":{},
            "payout_status":{},"history":[],"snapshots":{},"member_status":{},
            "payment_ledger":[],"payment_transactions":[],"payout_ledger":[],"reconciliations":[],
            "passcode":hash_pw(BOOTSTRAP_ADMIN_PW) if BOOTSTRAP_ADMIN_PW else ""}

@st.cache_resource
def get_sheet():
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(st.secrets["sheet"]["name"])

def ensure_ws(sheet, title):
    try: return sheet.worksheet(title)
    except gspread.WorksheetNotFound: return sheet.add_worksheet(title=title, rows=2, cols=2)

def _read_ws_json(sheet, title, default):
    val = ensure_ws(sheet, title).cell(1,1).value
    if val:
        try: return json.loads(val)
        except Exception: return default
    return default

def _month_keys_to_turn(ps):
    """Older releases keyed payouts Month 1, Month 2… Keep their balances under Turn N."""
    out = {}
    for k, v in (ps or {}).items():
        k = str(k)
        out[f"Turn {k.split(' ',1)[1]}" if k.startswith("Month ") else k] = v
    return out

def migrate_legacy(sheet):
    """One-time: fold the old one-worksheet-per-key layout into a single blob."""
    b = blank_blob()
    existing = {ws.title for ws in sheet.worksheets()}
    if not (set(LEGACY_WS) & existing): return b
    b["settings"]      = _read_ws_json(sheet,"settings",DEFAULT_SETTINGS) if "settings" in existing else dict(DEFAULT_SETTINGS)
    b["tiers"]         = _read_ws_json(sheet,"tiers",{})         if "tiers" in existing else {}
    b["payments"]      = _read_ws_json(sheet,"payments",{})      if "payments" in existing else {}
    b["payout_status"] = _month_keys_to_turn(_read_ws_json(sheet,"payout_status",{}) if "payout_status" in existing else {})
    b["history"]       = _read_ws_json(sheet,"history",[])       if "history" in existing else []
    b["snapshots"]     = _read_ws_json(sheet,"snapshots",{})     if "snapshots" in existing else {}
    b["passcode"]      = _read_ws_json(sheet,"passcode","") if "passcode" in existing else (hash_pw(BOOTSTRAP_ADMIN_PW) if BOOTSTRAP_ADMIN_PW else "")
    b["history"].insert(0,{"type":"setting","text":"Data migrated to single-blob storage","who":"system","time":now_str()})
    return b

def read_blob_fresh(sheet):
    """Uncached — one API read. Used before every write."""
    raw = ensure_ws(sheet, DATA_WS).cell(1,1).value
    if raw:
        try:
            b = json.loads(raw)
            for k,v in blank_blob().items(): b.setdefault(k,v)
            ps = b.get("payout_status", {})
            for k, v in _month_keys_to_turn(ps).items():
                ps.setdefault(k, v)
            b["payout_status"] = ps
            return b
        except Exception: pass
    b = migrate_legacy(sheet)
    ensure_ws(sheet, DATA_WS).update("A1", [[json.dumps(b)]])
    return b

@st.cache_data(ttl=60, show_spinner=False)
def read_blob_cached(_sheet, _bust=0):
    return read_blob_fresh(_sheet)

def write_blob(sheet, blob):
    ensure_ws(sheet, DATA_WS).update("A1", [[json.dumps(blob)]])
    read_blob_cached.clear()

def apply_blob(b):
    s = b.get("settings",DEFAULT_SETTINGS)
    st.session_state.rev                  = b.get("rev",0)
    st.session_state.start_date           = s.get("start_date",DEFAULT_SETTINGS["start_date"])
    st.session_state.base_monthly         = s.get("base_monthly",DEFAULT_SETTINGS["base_monthly"])
    st.session_state.admin_fee_percentage = s.get("admin_fee_percentage",0.0)
    st.session_state.names_input          = s.get("names_input",DEFAULT_SETTINGS["names_input"])
    st.session_state.member_tiers         = b.get("tiers",{})
    st.session_state.payments             = b.get("payments",{})
    st.session_state.payout_status        = b.get("payout_status",{})
    st.session_state.history              = b.get("history",[])
    st.session_state.snapshots            = b.get("snapshots",{})
    st.session_state.member_status        = b.get("member_status",{})
    st.session_state.payment_ledger       = b.get("payment_ledger",[])
    st.session_state.payment_transactions = b.get("payment_transactions",[])
    st.session_state.payout_ledger        = b.get("payout_ledger",[])
    st.session_state.reconciliations      = b.get("reconciliations",[])
    st.session_state.admin_passcode       = b.get("passcode","")
    st.session_state.last_sync            = now_dt()

def reload_state(sheet, fresh=False):
    apply_blob(read_blob_fresh(sheet) if fresh else read_blob_cached(sheet))

def commit(sheet, mutate):
    """Re-read, refuse if someone else wrote since we loaded, else apply + bump rev."""
    current = read_blob_fresh(sheet)
    if current.get("rev",0) != st.session_state.get("rev",0):
        apply_blob(current)
        flash("Someone else updated the group since you loaded this page. Your view has been refreshed — please re-apply your change.","warning")
        return False
    entries = mutate(current) or []
    if isinstance(entries, dict): entries = [entries]
    who = st.session_state.get("admin_name", ADMIN_NAME)
    for e in entries:
        e.setdefault("who", who); e.setdefault("time", now_str())
        current.setdefault("history",[]).insert(0,e)
    current["history"] = current.get("history",[])[:80]
    current["rev"] = current.get("rev",0)+1
    write_blob(sheet, current)
    apply_blob(current)
    return True

def put_settings(b):
    b["settings"] = {"start_date":st.session_state.start_date,"base_monthly":st.session_state.base_monthly,
                     "admin_fee_percentage":st.session_state.admin_fee_percentage,"names_input":st.session_state.names_input}

# ── connect ───────────────────────────────────────────────────────────────────
try:
    gsheet = get_sheet()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}"); st.stop()

if "initialized" not in st.session_state:
    reload_state(gsheet)
    st.session_state.authenticated    = False
    st.session_state.initialized      = True
    st.session_state.confirm_payout   = False
    st.session_state.confirm_settings = False
    st.session_state.admin_name       = ADMIN_NAME
    st.session_state.last_activity    = now_dt()

STALE_MINUTES = 5
if (now_dt()-st.session_state.last_sync).total_seconds() > STALE_MINUTES*60:
    reload_state(gsheet)

show_flash()

# ── session timeout ───────────────────────────────────────────────────────────
if st.session_state.get("authenticated"):
    if (now_dt() - st.session_state.get("last_activity", now_dt())).total_seconds() > SESSION_TIMEOUT_MINUTES*60:
        st.session_state.authenticated = False
        st.session_state.admin_name = ADMIN_NAME
        flash("Session timed out — please unlock again.", "warning")
    else:
        st.session_state.last_activity = now_dt()

# ── auth ──────────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    html("""<div class="lock-outer">
        <div class="lock-card">
            <span class="lock-icon">💸</span>
            <div class="lock-title">Susu Savings</div>
            <div class="lock-sub">Enter your name and passcode to continue</div>
        </div>
    </div>""")
    col_l,col_c,col_r = st.columns([1,2,1])
    with col_c:
        who = st.text_input("n", value=ADMIN_NAME, label_visibility="collapsed", placeholder="Your name (for the activity log)")
        pw  = st.text_input("p", type="password", label_visibility="collapsed", placeholder="Passcode…")
        if st.button("Unlock →"):
            stored = st.session_state.get("admin_passcode", "")
            if not stored and not BOOTSTRAP_ADMIN_PW:
                st.error("No admin passcode is configured. Add app.admin_passcode to Streamlit secrets first.")
                st.stop()
            if not stored and BOOTSTRAP_ADMIN_PW:
                stored = BOOTSTRAP_ADMIN_PW
            if not who.strip():
                st.error("Please enter your name — every change is recorded against it.")
            elif check_pw(pw, stored):
                st.session_state.admin_name    = who.strip()[:40]
                st.session_state.authenticated = True
                st.session_state.last_activity = now_dt()
                # Upgrade plaintext or legacy SHA-256 storage to salted scrypt.
                if not is_scrypt_hash(st.session_state.get("admin_passcode", "")):
                    commit(gsheet, lambda b: (b.__setitem__("passcode", hash_pw(pw)), None)[1])
                st.rerun()
            else:
                st.error("Incorrect passcode.")
    st.stop()

# ── derive ────────────────────────────────────────────────────────────────────
members     = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)
if num_members < 2: st.error("Please enter at least 2 member names."); st.stop()

for m in members:
    st.session_state.member_tiers.setdefault(m, st.session_state.base_monthly)
    st.session_state.member_status.setdefault(m, {"status":"active","exit_week":None})

total_weeks = num_members * 4      # rotation is fixed; exiting a member never shifts dates

try: start_dt = datetime.strptime(st.session_state.start_date, "%Y-%m-%d").replace(tzinfo=GH_TZ)
except ValueError: st.error("Date format must be YYYY-MM-DD."); st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

for m in members:
    st.session_state.payments.setdefault(m, {})
    for w in range(1,total_weeks+1):
        st.session_state.payments[m].setdefault(str(w), False)
for i in range(num_members):
    st.session_state.payout_status.setdefault(f"Turn {i+1}", {})

today                = now_dt()
days_passed          = (today-start_dt).days
current_elapsed_week = min(max(0,days_passed//7)+1 if today>=start_dt else 0, total_weeks)
program_pct          = int(current_elapsed_week/total_weeks*100) if total_weeks else 0
fee_frac             = st.session_state.admin_fee_percentage/100.0

def tier(m):    return st.session_state.member_tiers.get(m,st.session_state.base_monthly)
def weekly(m):  return money(tier(m)/4.0)

def txs_for(m=None, w=None, status="completed"):
    out = []
    for tx in st.session_state.get("payment_transactions",[]):
        if status and tx.get("status","completed") != status: continue
        if m is not None and tx.get("member") != m: continue
        if w is not None and int(tx.get("week",0)) != int(w): continue
        out.append(tx)
    return out

def paid_amount(m, w):
    """Amount banked for one member-week.

    Transactions are the source of truth. Where a week has no transaction at all
    (records made before receipts existed, or via the legacy grid), fall back to
    the checkbox: ticked means the full weekly target was received.
    """
    rows = [tx for tx in st.session_state.get("payment_transactions",[])
            if tx.get("member")==m and int(tx.get("week",0))==int(w)]
    if rows:
        return money(sum(float(tx.get("amount",0) or 0) for tx in rows if tx.get("status","completed")=="completed"))
    return weekly(m) if bool(st.session_state.payments.get(m,{}).get(str(w),False)) else 0.0

def paid(m,w):  return paid_amount(m,w) >= weekly(m)-0.005

def receipt_text(tx):
    return (f"🧾 *SUSU PAYMENT RECEIPT*\n\n"
            f"Member: *{tx.get('member','—')}*\nWeek: *{int(tx.get('week',0)):02d}*\n"
            f"Amount: *GHS {fmt_num(tx.get('amount',0))}*\nMethod: {tx.get('method','—')}\n"
            f"Reference: {tx.get('reference') or '—'}\nDate: {tx.get('date') or now_dt().strftime('%d %b %Y')}\n"
            f"Recorded by: {tx.get('who','—')}\nReceipt ID: {tx.get('id','—')}\n\nThank you for your contribution 🙏")

def payout_receipt_text(p):
    return (f"🧾 *SUSU PAYOUT RECEIPT*\n\nRecipient: *{p.get('recipient','—')}*\nTurn: *{p.get('turn','—')}*\n"
            f"Amount: *GHS {fmt_num(p.get('amount',0))}*\nMethod: {p.get('method','—')}\nReference: {p.get('reference') or '—'}\n"
            f"Date: {p.get('date') or now_dt().strftime('%d %b %Y')}\nRecorded by: {p.get('who','—')}\nReceipt ID: {p.get('id','—')}")

def mstat(m):   return st.session_state.member_status.get(m,{"status":"active","exit_week":None})
def exited(m):  return mstat(m).get("status")=="exited"
def exit_week(m):
    ew = mstat(m).get("exit_week")
    return int(ew) if ew else total_weeks
def liable(m,w):
    """Exited members owe nothing after their exit week."""
    return not (exited(m) and w > exit_week(m))
def liable_total(m):
    return sum(1 for w in range(1,total_weeks+1) if liable(m,w))

def gross_collected_for_turn(i):
    """Contributions banked against turn i (0-based) — its four weeks."""
    return money(sum(paid_amount(m,w) for m in members for w in range(4*i+1,4*i+5)))

# Every money figure below goes through paid_amount so transactions and any
# legacy checkbox records are counted exactly once, on the same basis.
total_cash_collected = money(sum(paid_amount(m,w) for m in members for w in range(1,total_weeks+1)))

def collected_amount(turn_lbl):
    """How much of their payout the recipient has actually collected so far."""
    ps = st.session_state.payout_status.get(turn_lbl,{})
    return money(ps.get("collected", ps.get("disbursed_amount", ps.get("amount_collected",0.0))))

total_payouts_dist    = money(sum(collected_amount(f"Turn {i+1}") for i in range(num_members)))
total_cash_held       = money(total_cash_collected - total_payouts_dist)
total_expected_so_far = money(sum(weekly(m)*sum(1 for w in range(1,current_elapsed_week+1) if liable(m,w)) for m in members))
# due-but-unpaid up to this week — matches the alert banner exactly
collection_gap        = money(sum(max(0.0, sum(weekly(m) for w in range(1,current_elapsed_week+1) if liable(m,w)) -
                                       sum(paid_amount(m,w) for w in range(1,current_elapsed_week+1))) for m in members))
# banked against weeks that are not yet due
paid_ahead            = money(sum(paid_amount(m,w) for m in members
                                  for w in range(current_elapsed_week+1,total_weeks+1)))

next_recipient,next_payout_date,next_net_pool,days_to_payout = None,None,0,0
cur_d = start_dt
for i in range(num_members):
    pd_date = cur_d+timedelta(weeks=4)
    if pd_date >= today:
        next_recipient   = members[i]
        next_payout_date = pd_date
        next_net_pool    = money(tier(members[i])*num_members*(1-fee_frac))
        days_to_payout   = (pd_date-today).days
        break
    cur_d = pd_date

# weekly snapshot so the "vs last week" delta always has a baseline
if current_elapsed_week>0 and str(current_elapsed_week) not in st.session_state.get("snapshots",{}):
    def _snap(b, wk=current_elapsed_week, val=total_cash_held):
        b.setdefault("snapshots",{})[str(wk)] = val; return None
    commit(gsheet, _snap)

# ── contributions ─────────────────────────────────────────────────────────────
def missed_streak(member):
    streak = 0
    for w in range(min(current_elapsed_week, exit_week(member)), 0, -1):
        if not paid(member,w): streak += 1
        else: break
    return streak

contrib_rows, wa_contrib_rows = [], []
for member in members:
    m_weekly    = weekly(member)
    due_weeks   = sum(1 for w in range(1,current_elapsed_week+1) if liable(member,w))
    paid_so_far = money(sum(paid_amount(member,w) for w in range(1,current_elapsed_week+1) if liable(member,w)))
    paid_passed = sum(1 for w in range(1,current_elapsed_week+1) if liable(member,w) and paid(member,w))
    owing       = money(max(0.0, due_weeks*m_weekly - paid_so_far))
    total_paid  = sum(1 for w in range(1,total_weeks+1) if paid(member,w))
    is_out      = exited(member)
    standing    = f"Owing GHS {fmt_num(owing)}" if owing>0 else ("Exited" if is_out else "Up to date")
    streak      = 0 if (is_out and owing<=0) else missed_streak(member)
    contrib_rows.append({"member":member,"m_monthly":tier(member),"m_weekly":m_weekly,"total_paid":total_paid,
                         "paid_due":paid_passed,"due_so_far":due_weeks,"paid_value":paid_so_far,
                         "due_total":liable_total(member),"owing":owing,"standing":standing,"streak":streak,
                         "exited":is_out,"exit_week":mstat(member).get("exit_week")})
    wa_contrib_rows.append({"member":member,"standing":standing,"streak":streak,"exited":is_out})

# Defined outside the loop so the reminder export always has a list, even when
# nobody owes anything.
owing_members = [r for r in wa_contrib_rows if r["standing"].startswith("Owing ")]

# ── payout schedule ───────────────────────────────────────────────────────────
schedule_rows, wa_payout_rows = [], []
cur_d = start_dt
for i in range(num_members):
    turn_lbl     = f"Turn {i+1}"
    recipient    = members[i]
    payout_date  = cur_d+timedelta(weeks=4)
    gross_pool   = money(tier(recipient)*num_members)
    admin_fee_v  = money(gross_pool*fee_frac)
    net_pool_amt = money(gross_pool-admin_fee_v)
    collected    = collected_amount(turn_lbl)                        # taken by the recipient
    remaining    = money(max(0.0, net_pool_amt-collected))           # still owed to them
    pct_c        = int(collected/net_pool_amt*100) if net_pool_amt>0 else 0
    funded       = money(gross_collected_for_turn(i)*(1-fee_frac))   # contributions banked for this turn
    ps           = st.session_state.payout_status.get(turn_lbl,{})
    disbursed    = ps.get("disbursed",False) or (collected >= net_pool_amt-0.005 and collected>0)
    days_away    = (payout_date-today).days if payout_date>=today else None
    early_ok     = (funded >= net_pool_amt-0.005) and remaining>0 and (payout_date >= today)
    schedule_rows.append({"turn":turn_lbl,"recipient":recipient,"date":format_date(payout_date),"payout_date":payout_date,
                          "fee":fmt_num(admin_fee_v),"pool":fmt_num(net_pool_amt),"collected":fmt_num(collected),
                          "remaining":fmt_num(remaining),"remaining_v":remaining,"collected_v":collected,"pct":pct_c,
                          "disbursed":disbursed,"funded":funded,"funded_s":fmt_num(funded),
                          "disb_date":ps.get("disbursed_date",""),
                          "days_away":days_away,"early_ok":early_ok,"net_pool_amt":net_pool_amt,
                          "exited":exited(recipient)})
    wa_payout_rows.append({"recipient":recipient,"date":format_date(payout_date),"balance":fmt_num(remaining),"disbursed":disbursed})
    cur_d = payout_date


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD — command centre
# ══════════════════════════════════════════════════════════════════════════════
sync_ago = int((now_dt()-st.session_state.last_sync).total_seconds()/60)
sync_txt = "just now" if sync_ago < 1 else f"{sync_ago}m ago"

gap_class  = "v3-kpi-bad" if collection_gap > 0 else "v3-kpi-good"
owing_rows = [r for r in contrib_rows if r["owing"] > 0]

next_turn  = next((r for r in schedule_rows if not r["disbursed"]), None)
funded_pct = int(min(next_turn["funded"]/next_turn["net_pool_amt"], 1)*100) if next_turn and next_turn["net_pool_amt"] else 100

prev_snap = st.session_state.get("snapshots", {}).get(str(current_elapsed_week-1))
if prev_snap is not None and current_elapsed_week > 1:
    snap_delta  = money(total_cash_held - float(prev_snap))
    delta_arrow = "↑" if snap_delta >= 0 else "↓"
    delta_color = "#34d399" if snap_delta >= 0 else "#f87171"
    delta_html  = f'<span style="color:{delta_color};font-weight:700">{delta_arrow} GHS {fmt_num(abs(snap_delta))}</span> vs last week'
else:
    delta_html = "First weekly snapshot"

ahead_note = f" · GHS {fmt_num(paid_ahead)} paid ahead" if paid_ahead > 0 else ""

# ── live header ───────────────────────────────────────────────────────────────
html(f"""
<div class="v3-status">
  <div><span class="status-dot"></span><strong>Live</strong><span class="v3-status-muted"> · Synced {sync_txt}</span></div>
  <div class="v3-status-muted">Revision {st.session_state.rev} · {st.session_state.admin_name}</div>
</div>
<div class="v3-header">
  <div>
    <div class="v3-kicker">SUSU SAVINGS</div>
    <div class="v3-title">{greeting()}, {st.session_state.admin_name} 👋</div>
    <div class="v3-subtitle">Week {current_elapsed_week} of {total_weeks} · {num_members} members · {format_date(start_dt)} → {format_date(end_date)}</div>
  </div>
  <div class="v3-header-actions">
    <a class="v3-action secondary" href="#section-payments">💳 Record payments</a>
    <a class="v3-action secondary" href="#section-payouts">🎁 Record payout</a>
    <a class="v3-action primary" href="#section-exports">📤 Share update</a>
  </div>
</div>
""")

rfc, _sp = st.columns([1,4])
with rfc:
    if st.button("↻ Refresh", key="refresh_btn", type="secondary"):
        reload_state(gsheet, fresh=True); flash("Refreshed from Google Sheets"); st.rerun()

# ── primary KPIs ──────────────────────────────────────────────────────────────
html(f"""
<div class="v3-kpis v3-kpis-2">
  <div class="v3-kpi v3-kpi-primary">
    <div class="v3-kpi-label">CASH HELD</div>
    <div class="v3-kpi-value">GHS {fmt_num(total_cash_held)}</div>
    <div class="v3-kpi-meta">GHS {fmt_num(total_cash_collected)} collected · GHS {fmt_num(total_payouts_dist)} paid out</div>
    <div class="v3-kpi-delta">{delta_html}</div>
  </div>
  <div class="v3-kpi">
    <div class="v3-kpi-label">THIS WEEK</div>
    <div class="v3-kpi-value">{current_elapsed_week} <span>/ {total_weeks}</span></div>
    <div class="v3-progress"><span style="width:{program_pct}%"></span></div>
    <div class="v3-kpi-meta">{program_pct}% of rotation completed · ends {format_date(end_date)}</div>
  </div>
</div>
""")

# ── alert + next payout ───────────────────────────────────────────────────────
# collections card — the outstanding figure lives here now, with the names
if owing_rows:
    who_owes = ", ".join(f"{r['member']} · GHS {fmt_num(r['owing'])}" for r in owing_rows[:4])
    if len(owing_rows) > 4:
        who_owes += f" +{len(owing_rows)-4} more"
    alert_html = f"""
    <div class="v3-alert">
      <div class="v3-alert-top">
        <span class="v3-kicker">OUTSTANDING</span>
        <span class="v3-days v3-urgent">{len(owing_rows)} behind</span>
      </div>
      <div class="v3-alert-amount">GHS {fmt_num(collection_gap)}</div>
      <div class="v3-alert-names">{who_owes}</div>
      <div class="v3-alert-foot">
        <span>{('GHS ' + fmt_num(paid_ahead) + ' paid ahead') if paid_ahead > 0 else 'Due to week ' + str(current_elapsed_week)}</span>
        <a href="#section-exports">Send reminder →</a>
      </div>
    </div>
    """
else:
    alert_html = f"""
    <div class="v3-alert v3-alert-clear">
      <div class="v3-alert-top">
        <span class="v3-kicker">COLLECTIONS</span>
        <span class="v3-days v3-clear">all paid</span>
      </div>
      <div class="v3-alert-amount">GHS 0</div>
      <div class="v3-alert-names">Every member is up to date for week {current_elapsed_week}.</div>
      <div class="v3-alert-foot">
        <span>{('GHS ' + fmt_num(paid_ahead) + ' paid ahead') if paid_ahead > 0 else 'Nothing outstanding'}</span>
        <a href="#section-exports">Share update →</a>
      </div>
    </div>
    """

# next payout card — the only place the rotation's next turn is stated
if next_turn:
    gap_to_fund    = money(max(0.0, next_turn["net_pool_amt"] - next_turn["funded"]))
    shortfall_note = f" · GHS {fmt_num(gap_to_fund)} short" if gap_to_fund > 0 else " · fully funded"
    if next_turn["days_away"] is None:
        days_label, urgency = "past due", "v3-urgent"
    else:
        days_label = "today" if next_turn["days_away"] == 0 else f"in {next_turn['days_away']} days"
        urgency    = "v3-urgent" if next_turn["days_away"] <= 7 else ""
    next_card = f"""
    <div class="v3-next-card">
      <div class="v3-next-top"><span class="v3-kicker">NEXT PAYOUT</span><span class="v3-days {urgency}">{days_label}</span></div>
      <div class="v3-next-main">
        <div><div class="v3-recipient">{next_turn['recipient']}</div><div class="v3-next-date">{next_turn['date']} · {next_turn['turn']}</div></div>
        <div class="v3-next-amount">GHS {next_turn['pool']}</div>
      </div>
      <div class="v3-funding-row"><span>Turn funding</span><strong>{funded_pct}%</strong></div>
      <div class="v3-progress tall"><span style="width:{funded_pct}%"></span></div>
      <div class="v3-funding-meta">GHS {next_turn['funded_s']} banked of GHS {next_turn['pool']} required{shortfall_note}</div>
    </div>
    """
else:
    next_card = ('<div class="v3-next-card"><div class="v3-kicker">ROTATION</div>'
                 '<div class="v3-recipient">Cycle complete 🎉</div>'
                 '<div class="v3-next-date">Every turn has been collected.</div></div>')

html(f"""<div class="v3-command-grid">{alert_html}{next_card}</div>""")

# ── member standing ───────────────────────────────────────────────────────────
def ahead_cell(r):
    n = r["total_paid"] - r["paid_due"]
    return f'<div class="cell-sub v3-ahead">+{n} wk ahead</div>' if n > 0 else ""

rows_html = ""
for r in contrib_rows:
    is_owing  = r["owing"] > 0
    row_class = "owing" if is_owing else ("plain" if r["exited"] else "ok")
    if is_owing:
        badge = f'<span class="badge-owe">GHS {fmt_num(r["owing"])}</span>'
    elif r["exited"]:
        badge = '<span class="badge-exempt">Exited</span>'
    else:
        badge = '<span class="badge-ok">Paid</span>'
    streak_html = f'<span class="streak-badge">🔴 {r["streak"]}wk</span>' if r["streak"] >= 2 else ""
    exit_tag    = f'<span class="exit-tag">left wk {r["exit_week"]}</span>' if r["exited"] and r["exit_week"] else ""
    rows_html += (
        f'<tr class="{row_class}">'
        f'<td><span class="member-avatar">{r["member"][0].upper()}</span><span class="cell-name">{r["member"]}</span>{exit_tag}</td>'
        f'<td>GHS {fmt_num(r["m_weekly"])}</td>'
        f'<td>{r["paid_due"]} / {r["due_so_far"]}{ahead_cell(r)}</td>'
        f'<td>{badge}{streak_html}</td></tr>'
    )

timeline_html = "".join(
    f'<span class="{"done" if r["disbursed"] else ("current" if r is next_turn else "")}"></span>'
    for r in schedule_rows)

html(f"""
<div class="glass-card v3-section-card">
  <div class="v3-section-head">
    <div><div class="sec-label">PAYMENT STATUS</div><div class="sec-title">Members this week</div><div class="sec-sub">Who is paid, who is behind, and who is ahead.</div></div>
    <a class="v3-inline-link" href="#section-payments">Manage payments →</a>
  </div>
  <table class="data-table tbl-contrib">
    <thead><tr><th>Member</th><th>Weekly target</th><th>Paid / Due</th><th>Status</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
""")

# ── payout rotation ───────────────────────────────────────────────────────────
show_fee     = fee_frac > 0
fee_col_head = "<th>Admin Fee</th>" if show_fee else ""
fee_cls      = "has-fee" if show_fee else "no-fee"
def fee_cell(r): return f'<td>GHS {r["fee"]}</td>' if show_fee else ""

pay_rows_html = ""
for r in schedule_rows:
    bar_pct = min(r["pct"], 100)
    if r["disbursed"]:
        status_badge = '<span class="badge-ok">Collected</span>'
        if r["disb_date"]:
            status_badge += f'<div class="cell-sub">{r["disb_date"]}</div>'
    elif r["collected_v"] > 0:
        status_badge = '<span class="badge-owe">Part collected</span>'
    else:
        status_badge = '<span class="badge-pending">Upcoming</span>'
    if r["days_away"] is not None:
        urg = "urgent" if r["days_away"] <= 7 else ""
        days_cell = f'<div><span class="days-badge {urg}">{r["days_away"]}d away</span></div>'
    else:
        days_cell = '<div class="cell-sub">Past</div>'
    early_note = '<div class="early-eligible">Fully funded</div>' if r["early_ok"] else ""
    exit_tag   = '<span class="exit-tag">exited</span>' if r["exited"] else ""
    pay_rows_html += (
        f'<tr class="plain">'
        f'<td><span class="cell-name">{r["turn"]}</span></td>'
        f'<td>{r["recipient"]}{exit_tag}</td>'
        f'<td>{r["date"]}{days_cell}</td>' + fee_cell(r) +
        f'<td>GHS {r["pool"]}{early_note}<div class="pbar-wrap"><div class="pbar-fill" style="width:{bar_pct}%"></div></div></td>'
        f'<td>GHS {r["collected"]}</td><td>GHS {r["remaining"]}</td><td>{status_badge}</td></tr>'
    )

html(f"""
<div class="glass-card v3-section-card">
  <div class="v3-section-head">
    <div><div class="sec-label">ROTATION</div><div class="sec-title">Payout schedule</div><div class="sec-sub">Four-week turns · collected is what the recipient has taken, remaining is what they are still owed.</div></div>
    <a class="v3-inline-link" href="#section-payouts">Manage payouts →</a>
  </div>
  <div class="v3-timeline">{timeline_html}</div>
  <table class="data-table tbl-payout {fee_cls}">
    <thead><tr><th>Turn</th><th>Recipient</th><th>Date</th>{fee_col_head}<th>Net Pool</th><th>Collected</th><th>Remaining</th><th>Status</th></tr></thead>
    <tbody>{pay_rows_html}</tbody>
  </table>
  <p class="swipe-hint">Swipe sideways for the full payout breakdown.</p>
</div>
""")

# ── exports ───────────────────────────────────────────────────────────────────
buf = io.StringIO()
buf.write(f"📌 *SUSU WEEK {current_elapsed_week} UPDATE*\n💰 *Cash held:* GHS {fmt_num(total_cash_held)}\n"
          f"📥 *Collected:* GHS {fmt_num(total_cash_collected)}\n🎁 *Paid out:* GHS {fmt_num(total_payouts_dist)}\n"
          f"🏁 *Cycle:* Week {current_elapsed_week} of {total_weeks}\n\n")
buf.write("👥 *MEMBER STANDING*\n")
for r in wa_contrib_rows:
    if r["exited"] and not r["standing"].startswith("Owing "):
        buf.write(f"⚪ *{r['member']}*: Exited\n"); continue
    streak_note = f" · 🔴 {r['streak']} weeks behind" if r['streak']>=2 else ""
    buf.write(f"{'✅' if r['standing']=='Up to date' else '❌'} *{r['member']}*: {r['standing']}{streak_note}\n")
buf.write("\n🎁 *PAYOUTS*\n")
for r in wa_payout_rows:
    tag = " · ✅ fully collected" if r['disbursed'] else f" · GHS {r['balance']} remaining"
    buf.write(f"*{r['recipient']}* · {r['date']}{tag}\n")
if next_recipient:
    buf.write(f"\n➡️ *Next payout:* {next_recipient} on {format_date(next_payout_date)}\n")
buf.write("\nThank you everyone for keeping the susu on track 🙏")

rem = io.StringIO()
rem.write(f"🔔 *SUSU PAYMENT REMINDER — WEEK {current_elapsed_week}*\n\n")
if owing_members:
    rem.write("Hi everyone 👋 A quick reminder for members with outstanding contributions:\n\n")
    for r in owing_members:
        rem.write(f"• ❌ *{r['member']}*: {r['standing']}\n")
    if next_recipient:
        rem.write(f"\nPlease settle your outstanding amount when you can so we can keep the next payout on schedule.\n"
                  f"🎁 *Next payout:* {next_recipient} · {format_date(next_payout_date)}\n")
    rem.write("\nThank you 🙏")
else:
    rem.write("✅ *Everyone is up to date this week!* 🎉\n\nThank you all for staying on track 🙏")

ob = io.StringIO()
ob.write("📋 *SUSU GROUP — ONBOARDING DETAILS*\n\n")
ob.write(f"🗓️ *Start:* {format_date(start_dt)}\n🏁 *End:* {format_date(end_date)}\n"
         f"👥 *Members:* {num_members}\n🔄 *Cycle:* {total_weeks} weeks\n\n")
ob.write("ℹ️ *HOW IT WORKS*\n• Contributions are weekly.\n• Each turn lasts exactly 4 weeks.\n"
         "• Payout dates are fixed by the rotation schedule.\n")
if fee_frac>0:
    ob.write(f"• An admin fee of {fmt_num(st.session_state.admin_fee_percentage)}% is deducted from each payout.\n")
ob.write("\n👤 *MEMBER TARGETS*\n")
for r in contrib_rows:
    if not r["exited"]:
        ob.write(f"*{r['member']}* — GHS {fmt_num(r['m_weekly'])}/week\n")
ob.write("\n🎁 *PAYOUT SCHEDULE*\n")
for r in schedule_rows:
    ob.write(f"*{r['turn']} — {r['recipient']}* · {r['date']} · GHS {r['pool']}\n")

ch = io.StringIO()
ch.write(f"📊 *SUSU CONTRIBUTION HISTORY — WEEK {current_elapsed_week}*\n"
         f"🗓️ *Period:* {format_date(start_dt)} → {format_date(end_date)}\n\n")
for member in members:
    tag = " (exited)" if exited(member) else ""
    ch.write(f"👤 *{member}*{tag} · GHS {fmt_num(weekly(member))}/wk\n")
    for w in range(1,total_weeks+1):
        amt = paid_amount(member,w)
        if not liable(member,w) and amt<=0:
            ch.write(f"  Wk {w:02d}: ⚪ Exempt\n"); continue
        if paid(member,w):
            ch.write(f"  Wk {w:02d}: ✅ Paid\n")
        elif amt > 0:
            ch.write(f"  Wk {w:02d}: 🟡 Partial · GHS {fmt_num(amt)} of {fmt_num(weekly(member))}\n")
        else:
            ch.write(f"  Wk {w:02d}: {'⏳ Upcoming' if w>current_elapsed_week else '❌ Owing'}\n")
    ch.write("\n")

html("""<span class="anchor" id="section-exports"></span>
<div class="glass-card v3-section-card">
  <div class="sec-label">EXPORT</div><div class="sec-title">WhatsApp messages</div>
  <div class="sec-sub">Ready-to-send updates, reminders, onboarding details and contribution history.</div></div>""")
t1,t2,t3,t4 = st.tabs(["📥 Weekly Update","🔔 Reminder","📋 Onboarding","📊 History"])
with t1: wa_block(buf.getvalue(), f"Susu_W{current_elapsed_week}.txt", "dl_weekly")
with t2: wa_block(rem.getvalue(), f"Susu_Reminder_W{current_elapsed_week}.txt", "dl_rem")
with t3: wa_block(ob.getvalue(),  "Susu_Onboarding.txt", "dl_ob")
with t4: wa_block(ch.getvalue(),  f"Susu_History_W{current_elapsed_week}.txt", "dl_hist")

# ── admin panel ───────────────────────────────────────────────────────────────
html('<span class="anchor" id="section-admin"></span>'
     '<div class="sec-label" style="margin-top:24px">ADMIN</div>'
     '<div class="sec-title">Group controls</div>'
     '<div class="sec-sub">Record money in and out, then manage settings and tools.</div>')

tab_money, tab_settings, tab_tools = st.tabs(["💰 Money", "⚙️ Settings", "🛠️ Tools"])

with tab_money:
    html('<span class="anchor" id="section-payments"></span>')
    with st.expander("💳  Record Payment", expanded=True):
        st.caption("Record the payment as received. Partial, late, multiple and corrected payments are all supported.")
        pm1,pm2 = st.columns(2)
        with pm1: pay_member = st.selectbox("Member", members, key="tx_member")
        with pm2: pay_week   = st.number_input("Week", min_value=1, max_value=total_weeks,
                                               value=max(1,current_elapsed_week), step=1, key="tx_week")
        target  = weekly(pay_member)
        already = paid_amount(pay_member, int(pay_week))
        default_amt = money(max(0.0, target-already)) if already < target else target
        pm3,pm4 = st.columns(2)
        with pm3: pay_amount = st.number_input("Amount received (GHS)", min_value=0.0,
                                               value=float(default_amt), step=10.0, key="tx_amount")
        with pm4: pay_method = st.selectbox("Payment method", ["Cash","MoMo","Bank transfer","Other"], key="tx_method")
        pm5,pm6 = st.columns(2)
        with pm5: pay_ref  = st.text_input("Reference / note", key="tx_reference", placeholder="MoMo ref, bank ref, or cash note")
        with pm6: pay_date = st.date_input("Payment date", value=today.date(), key="tx_date")
        html(f'<div style="font-size:13px;color:{T["sub_color"]};margin:4px 0 10px">Weekly target: '
             f'<strong style="color:{T["sec_title"]}">GHS {fmt_num(target)}</strong> · Already recorded for Week '
             f'{int(pay_week):02d}: <strong style="color:{T["sec_title"]}">GHS {fmt_num(already)}</strong></div>')
        if st.button("Save Payment", key="save_transaction"):
            if pay_amount <= 0:
                st.error("Enter an amount greater than zero.")
            else:
                tx = {"id":new_id("PAY"),"member":pay_member,"week":int(pay_week),"amount":money(pay_amount),
                      "date":pay_date.strftime("%d %b %Y"),"time":now_str(),"method":pay_method,
                      "reference":pay_ref.strip(),"status":"completed",
                      "who":st.session_state.get("admin_name",ADMIN_NAME)}
                def _m(b, tx=tx, target=target):
                    b.setdefault("payment_transactions",[]).insert(0, tx)
                    banked = money(sum(float(x.get("amount",0) or 0) for x in b["payment_transactions"]
                                       if x.get("member")==tx["member"] and int(x.get("week",0))==tx["week"]
                                       and x.get("status","completed")=="completed"))
                    b.setdefault("payments",{}).setdefault(tx["member"],{})[str(tx["week"])] = banked >= target-0.005
                    b.setdefault("payment_ledger",[]).insert(0,{"member":tx["member"],"week":tx["week"],
                        "amount":tx["amount"],"action":"paid","time":tx["time"],"who":tx["who"],
                        "reference":tx["reference"],"method":tx["method"]})
                    b["payment_ledger"] = b["payment_ledger"][:500]
                    return {"type":"payment",
                            "text":f"Payment received — {tx['member']} · Week {tx['week']:02d} · GHS {fmt_num(tx['amount'])}",
                            "detail":[f"method: {tx['method']}", f"reference: {tx['reference'] or '—'}",
                                      f"banked for the week: GHS {fmt_num(banked)} of {fmt_num(target)}",
                                      f"receipt: {tx['id']}"]}
                if commit(gsheet,_m): flash(f"Payment saved for {pay_member}")
                st.rerun()

    with st.expander("🧾  Recent Payment Receipts"):
        tx_rows = st.session_state.get("payment_transactions",[])[:10]
        if not tx_rows:
            st.info("No payment receipts yet.")
        for tx in tx_rows:
            reversed_tag = " · ↩︎ REVERSED" if tx.get("status") != "completed" else ""
            st.markdown(f"**{tx.get('member','—')} · Week {int(tx.get('week',0)):02d} · "
                        f"GHS {fmt_num(tx.get('amount',0))}**{reversed_tag} · {tx.get('method','—')} · {tx.get('date','')}")
            wa_block(receipt_text(tx), f"Receipt_{tx.get('id','payment')}.txt", f"receipt_{tx.get('id','payment')}")
            if tx.get("status","completed") == "completed":
                st.caption("To reverse or correct this, use Undo / Correct a Record below — a reason is required.")
            st.divider()

    with st.expander("⚡  Bulk Payment Entry", expanded=True):
        st.caption("Tick everyone who has paid for a week and save once. Each tick writes a real payment "
                   "(with a receipt); unticking reverses it. Fastest way to run the weekly collection.")
        bc1,bc2,bc3 = st.columns([1,1,1])
        with bc1: bulk_week   = st.number_input("Week", min_value=1, max_value=total_weeks,
                                                value=max(1,current_elapsed_week), step=1, key="bulk_week")
        with bc2: bulk_method = st.selectbox("Method for new ticks", ["Cash","MoMo","Bank transfer","Other"], key="bulk_method")
        with bc3: bulk_date   = st.date_input("Payment date", value=today.date(), key="bulk_date")
        bw = int(bulk_week)

        ticks, rows_meta = {}, {}
        cols = st.columns(2)
        for idx, m in enumerate(members):
            already = paid_amount(m, bw)
            target  = weekly(m)
            rows_meta[m] = {"already":already, "target":target, "was":paid(m,bw)}
            with cols[idx % 2]:
                if not liable(m,bw) and already <= 0:
                    html(f'<div style="font-size:13px;color:{T["sub_color"]};padding:9px 0">{m} — exempt</div>')
                    continue
                part = f" · GHS {fmt_num(already)} banked" if 0 < already < target else ""
                ticks[m] = st.checkbox(f"{m} · GHS {fmt_num(target)}{part}",
                                       value=rows_meta[m]["was"], key=f"bulk_{bw}_{m}")

        adds    = [(m, money(rows_meta[m]["target"]-rows_meta[m]["already"]))
                   for m,t in ticks.items() if t and not rows_meta[m]["was"]]
        removes = [m for m,t in ticks.items() if not t and rows_meta[m]["was"]]
        if adds or removes:
            summary = []
            if adds:    summary.append(f"{len(adds)} to record (GHS {fmt_num(sum(a for _,a in adds))})")
            if removes: summary.append(f"{len(removes)} to reverse")
            st.caption(" · ".join(summary))

        def save_bulk(adds, removes):
            who_now = st.session_state.get("admin_name", ADMIN_NAME)
            bdate   = bulk_date.strftime("%d %b %Y")
            def _m(b, adds=adds, removes=removes, bw=bw, who_now=who_now, bdate=bdate, method=bulk_method):
                detail, touched = [], set()
                for m, amt in adds:
                    if amt <= 0: continue
                    tx = {"id":new_id("PAY"),"member":m,"week":bw,"amount":money(amt),"date":bdate,
                          "time":now_str(),"method":method,"reference":"Bulk entry",
                          "status":"completed","who":who_now}
                    b.setdefault("payment_transactions",[]).insert(0, tx)
                    b.setdefault("payment_ledger",[]).insert(0,{"member":m,"week":bw,"amount":tx["amount"],
                        "action":"paid","time":tx["time"],"who":who_now,"reference":"Bulk entry","method":method})
                    detail.append(f"{m} Wk {bw:02d}: recorded GHS {fmt_num(amt)}")
                    touched.add(m)
                for m in removes:
                    reversed_any = 0.0
                    for row in b.get("payment_transactions",[]):
                        if row.get("member")==m and int(row.get("week",0))==bw and row.get("status","completed")=="completed":
                            row["status"]="reversed"; row["reversed_at"]=now_str()
                            row["reversed_by"]=who_now; row["reversal_reason"]="Bulk untick"
                            reversed_any += money(row.get("amount",0))
                    if reversed_any:
                        b.setdefault("payment_ledger",[]).insert(0,{"member":m,"week":bw,"amount":money(reversed_any),
                            "action":"reversed","time":now_str(),"who":who_now,
                            "reference":"Bulk untick","method":"","reason":"Bulk untick"})
                        detail.append(f"{m} Wk {bw:02d}: reversed GHS {fmt_num(reversed_any)}")
                    else:
                        detail.append(f"{m} Wk {bw:02d}: earlier tick cleared")
                    touched.add(m)
                for m in touched:
                    banked = money(sum(float(x.get("amount",0) or 0) for x in b.get("payment_transactions",[])
                                       if x.get("member")==m and int(x.get("week",0))==bw
                                       and x.get("status","completed")=="completed"))
                    tgt = money(b.get("tiers",{}).get(m, b["settings"]["base_monthly"])/4.0)
                    b.setdefault("payments",{}).setdefault(m,{})[str(bw)] = banked >= tgt-0.005
                b["payment_ledger"] = b.get("payment_ledger",[])[:500]
                return {"type":"payment",
                        "text":f"Week {bw:02d} bulk entry — {len(adds)} recorded, {len(removes)} reversed",
                        "detail":detail}
            if commit(gsheet,_m): flash(f"Week {bw:02d} saved")
            st.session_state.bulk_confirm = False
            st.rerun()

        if st.session_state.get("bulk_confirm") and removes:
            st.warning("⚠️ These members will be marked unpaid for Week %02d and their payments reversed:\n\n" % bw
                       + "\n".join(f"• {m}" for m in removes))
            uc1,uc2 = st.columns(2)
            with uc1:
                if st.button("✓ Confirm and save", key="bulk_confirm_yes"):
                    save_bulk(adds, removes)
            with uc2:
                if st.button("✗ Cancel", key="bulk_confirm_no", type="secondary"):
                    st.session_state.bulk_confirm = False; st.rerun()
        else:
            if st.button(f"Save Week {bw:02d} Payments", key="bulk_save"):
                if not adds and not removes:
                    flash("No changes to save","info"); st.rerun()
                elif removes:
                    st.session_state.bulk_confirm = True; st.rerun()
                else:
                    save_bulk(adds, removes)

    html('<span class="anchor" id="section-payouts"></span>')
    with st.expander("🎁  Record Payout"):
        turn_options = [f"{r['turn']} — {r['recipient']}" for r in schedule_rows]
        sel_turn_lbl = st.selectbox("Payout Turn", turn_options, key="payout_turn")
        sr           = schedule_rows[turn_options.index(sel_turn_lbl)]
        tkey         = sr["turn"]; rec_name = sr["recipient"]
        html(f"""<div style="font-size:14px;color:{T['td_color']};line-height:1.7;margin-bottom:8px">
            Net pool due to {rec_name}: <strong style="color:{T['sec_title']}">GHS {sr['pool']}</strong> &nbsp;·&nbsp;
            Collected so far: <strong style="color:{T['sec_title']}">GHS {sr['collected']}</strong> &nbsp;·&nbsp;
            Still owed: <strong style="color:{T['sec_title']}">GHS {sr['remaining']}</strong><br>
            Contributions banked for this turn: <strong style="color:{T['sec_title']}">GHS {sr['funded_s']}</strong></div>""")
        if sr["funded"] < sr["net_pool_amt"]-0.005 and sr["remaining_v"] > 0:
            st.warning(f"Only GHS {sr['funded_s']} of the GHS {sr['pool']} pool has been contributed so far. "
                       f"Paying the full amount now draws on the group's other cash.")
        po1,po2 = st.columns(2)
        with po1:
            new_amt = st.number_input(f"Total collected by {rec_name} (GHS)", value=float(sr["collected_v"]),
                                      min_value=0.0, max_value=float(sr["net_pool_amt"]), step=50.0, key="payout_amt",
                                      help="Running total, not just today's instalment.")
        with po2:
            coll_date = st.date_input("Date collected", value=parse_display_date(sr["disb_date"]) or today.date(),
                                      key="payout_date_in")
        po3,po4 = st.columns(2)
        with po3: payout_method = st.selectbox("Payout method", ["Cash","MoMo","Bank transfer","Other"], key="payout_method")
        with po4: payout_ref    = st.text_input("Payout reference / note", key="payout_reference",
                                                placeholder="MoMo ref, bank ref, or cash note")
        coll_dt    = datetime.combine(coll_date, datetime.min.time(), tzinfo=GH_TZ)
        delta_out  = money(new_amt - sr["collected_v"])          # only the change leaves the box
        cash_after = money(total_cash_held - delta_out)
        st.caption(f"Balance still owed to {rec_name} after this entry: GHS {fmt_num(money(sr['net_pool_amt']-new_amt))}"
                   + (" — fully collected ✅" if new_amt >= sr["net_pool_amt"]-0.005 else "")
                   + f" · Group cash after: GHS {fmt_num(cash_after)}")
        overdraw = cash_after < -0.005
        if overdraw:
            st.error(f"❌ The group only holds GHS {fmt_num(total_cash_held)}. Paying out GHS {fmt_num(delta_out)} now "
                     f"would leave it GHS {fmt_num(abs(cash_after))} short. Record the outstanding weekly payments first, "
                     f"or enter a smaller amount.")
            st.session_state.confirm_payout = False
        if not st.session_state.get("confirm_payout",False):
            if st.button("Save Payout", key="save_payout_btn", disabled=overdraw):
                st.session_state.confirm_payout=True; st.rerun()
        else:
            st.warning(f"⚠️ Confirm: {rec_name} ({tkey}) has collected GHS {fmt_num(new_amt)} of GHS {sr['pool']} "
                       f"as at {format_date(coll_dt)}?")
            cc1,cc2 = st.columns(2)
            with cc1:
                if st.button("✓ Yes, confirm", key="confirm_yes"):
                    def _m(b):
                        ps = b.setdefault("payout_status",{}).setdefault(tkey,{})
                        before = money(ps.get("collected", ps.get("disbursed_amount", ps.get("amount_collected",0.0))))
                        if money(total_cash_held - money(new_amt-before)) < -0.005:
                            raise ValueError("would overdraw the group")
                        ps.pop("amount_collected", None); ps.pop("disbursed_amount", None)
                        full = money(new_amt) >= sr["net_pool_amt"]-0.005 and new_amt > 0
                        ps["collected"]      = money(new_amt)
                        ps["disbursed"]      = full
                        ps["disbursed_date"] = format_date(coll_dt) if new_amt > 0 else ""
                        if delta_out > 0:
                            ptx = {"id":new_id("PAYOUT"),"turn":tkey,"recipient":rec_name,"amount":money(delta_out),
                                   "date":format_date(coll_dt),"method":payout_method,"reference":payout_ref.strip(),
                                   "who":st.session_state.get("admin_name",ADMIN_NAME),"time":now_str()}
                            b.setdefault("payout_ledger",[]).insert(0, ptx)
                            b["payout_ledger"] = b["payout_ledger"][:500]
                        detail = [f"{tkey} collected: GHS {fmt_num(before)} → GHS {fmt_num(new_amt)}",
                                  f"balance owed to {rec_name}: GHS {fmt_num(money(sr['net_pool_amt']-new_amt))}",
                                  f"method: {payout_method}", f"date: {ps['disbursed_date'] or '—'}"]
                        txt = (f"{tkey} fully collected by {rec_name} — GHS {fmt_num(new_amt)}" if full
                               else f"{tkey} part collected by {rec_name} — GHS {fmt_num(new_amt)} of GHS {sr['pool']}")
                        return {"type":"payout","text":txt,"detail":detail}
                    try:
                        ok = commit(gsheet,_m)
                    except ValueError:
                        ok = False; flash("Save cancelled — that payout would overdraw the group's cash.","warning")
                    st.session_state.confirm_payout = False
                    if ok:
                        # commit() already refreshed session state — no extra sheet read needed
                        led = st.session_state.get("payout_ledger",[])
                        if led: st.session_state.last_payout_receipt = payout_receipt_text(led[0])
                        flash(f"Payout for {rec_name} saved")
                    st.rerun()
            with cc2:
                if st.button("✗ Cancel", key="confirm_no", type="secondary"):
                    st.session_state.confirm_payout=False; st.rerun()

    with st.expander("🧾  Recent Payout Receipts"):
        pl = st.session_state.get("payout_ledger",[])[:6]
        if not pl:
            st.info("Record a payout to generate its receipt.")
        for p in pl:
            rev = " · ↩︎ REVERSED" if p.get("status","active") == "reversed" else ""
            st.markdown(f"**{p.get('recipient','—')} · {p.get('turn','—')} · GHS {fmt_num(p.get('amount',0))}**{rev} · "
                        f"{p.get('method','—')} · {p.get('date','')}")
            wa_block(payout_receipt_text(p), f"Payout_{p.get('id','receipt')}.txt", f"payoutrcpt_{p.get('id','receipt')}")
            st.divider()

    with st.expander("↩️  Undo / Correct a Record"):
        st.caption("The original record is kept and marked, never deleted. A reason is required and goes into the audit trail.")
        kind = st.selectbox("Record type", ["Payment","Payout"], key="correction_kind")

        if kind == "Payment":
            active_txs = [t for t in st.session_state.get("payment_transactions",[])
                          if t.get("status","completed") == "completed"]
            if not active_txs:
                st.info("No active payment records to correct.")
            else:
                labels = [f"{t.get('member')} · Wk {int(t.get('week',0)):02d} · GHS {fmt_num(t.get('amount',0))} · {t.get('date','')}"
                          for t in active_txs]
                idx = st.selectbox("Select payment", range(len(active_txs)),
                                   format_func=lambda n: labels[n], key="correction_payment")
                sel = active_txs[idx]; rid = sel.get("id")
                action = st.radio("Action", ["Reverse","Correct amount"], horizontal=True, key="payment_correction_action")
                new_amount = (st.number_input("Correct amount (GHS)", min_value=0.0,
                                              value=float(sel.get("amount",0) or 0), step=10.0, key="correct_amount")
                              if action == "Correct amount" else None)
                reason = st.text_input("Reason", key="correction_reason", placeholder="Why is this being corrected?")
                if st.button("Confirm correction", key="confirm_payment_correction"):
                    if not reason.strip():
                        st.error("Please enter a reason.")
                    else:
                        who_now = st.session_state.get("admin_name", ADMIN_NAME)
                        def _m(b, rid=rid, action=action, new_amount=new_amount, reason=reason.strip(), who_now=who_now):
                            for row in b.get("payment_transactions",[]):
                                if row.get("id") != rid or row.get("status","completed") != "completed":
                                    continue
                                mbr, wk = row.get("member"), int(row.get("week",0))
                                old = money(row.get("amount",0))
                                if action == "Reverse":
                                    row["status"]          = "reversed"
                                    row["reversed_at"]     = now_str()
                                    row["reversed_by"]     = who_now
                                    row["reversal_reason"] = reason
                                    led_action, led_amt = "reversed", old
                                    text = f"Payment reversed — {mbr} · Week {wk:02d} · GHS {fmt_num(old)}"
                                else:
                                    row["amount"]            = money(new_amount)
                                    row["corrected_at"]      = now_str()
                                    row["corrected_by"]      = who_now
                                    row["correction_reason"] = reason
                                    led_action, led_amt = "corrected", money(new_amount)
                                    text = f"Payment corrected — {mbr} · Week {wk:02d} · GHS {fmt_num(old)} → GHS {fmt_num(new_amount)}"
                                # keep the week flag in step with what is actually banked
                                banked = money(sum(float(x.get("amount",0) or 0) for x in b["payment_transactions"]
                                                   if x.get("member")==mbr and int(x.get("week",0))==wk
                                                   and x.get("status","completed")=="completed"))
                                tgt = money(b.get("tiers",{}).get(mbr, b["settings"]["base_monthly"])/4.0)
                                b.setdefault("payments",{}).setdefault(mbr,{})[str(wk)] = banked >= tgt-0.005
                                b.setdefault("payment_ledger",[]).insert(0,{"member":mbr,"week":wk,"amount":led_amt,
                                    "action":led_action,"time":now_str(),"who":who_now,
                                    "reference":row.get("reference",""),"method":row.get("method",""),"reason":reason})
                                b["payment_ledger"] = b["payment_ledger"][:500]
                                return {"type":"payment","text":text,
                                        "detail":[f"receipt: {rid}", f"reason: {reason}",
                                                  f"still banked for the week: GHS {fmt_num(banked)}"]}
                            return None
                        if commit(gsheet,_m): flash("Correction saved","warning")
                        st.rerun()

        else:
            pools = {r["turn"]: r["net_pool_amt"] for r in schedule_rows}
            active_pos = [p for p in st.session_state.get("payout_ledger",[])
                          if p.get("status","active") != "reversed"]
            if not active_pos:
                st.info("No active payout records to reverse.")
            else:
                labels = [f"{p.get('recipient')} · {p.get('turn')} · GHS {fmt_num(p.get('amount',0))} · {p.get('date','')}"
                          for p in active_pos]
                idx = st.selectbox("Select payout", range(len(active_pos)),
                                   format_func=lambda n: labels[n], key="correction_payout")
                selp = active_pos[idx]; pid = selp.get("id")
                st.warning("Only reverse a payout that was recorded in error — the amount is added back to group cash.")
                reason_p = st.text_input("Reason", key="payout_correction_reason", placeholder="Why is this payout being reversed?")
                if st.button("Confirm payout reversal", key="confirm_payout_correction"):
                    if not reason_p.strip():
                        st.error("Please enter a reason.")
                    else:
                        who_now = st.session_state.get("admin_name", ADMIN_NAME)
                        def _m(b, pid=pid, reason=reason_p.strip(), who_now=who_now, pools=pools):
                            for p in b.get("payout_ledger",[]):
                                if p.get("id") != pid or p.get("status","active") == "reversed":
                                    continue
                                p["status"]          = "reversed"
                                p["reversed_at"]     = now_str()
                                p["reversed_by"]     = who_now
                                p["reversal_reason"] = reason
                                turn, amt = p.get("turn"), money(p.get("amount",0))
                                ps  = b.setdefault("payout_status",{}).setdefault(turn,{})
                                cur = money(ps.get("collected", ps.get("disbursed_amount", ps.get("amount_collected",0.0))))
                                new = money(max(0.0, cur-amt))
                                net = money(pools.get(turn,0))
                                ps["collected"] = new
                                ps["disbursed"] = new > 0 and new >= net-0.005
                                if new <= 0: ps["disbursed_date"] = ""
                                return {"type":"payout",
                                        "text":f"Payout reversed — {p.get('recipient')} · {turn} · GHS {fmt_num(amt)}",
                                        "detail":[f"receipt: {pid}", f"reason: {reason}",
                                                  f"{turn} collected: GHS {fmt_num(cur)} → GHS {fmt_num(new)}"]}
                            return None
                        if commit(gsheet,_m): flash("Payout reversed","warning")
                        st.rerun()

with tab_settings:
    with st.expander("⚙️  Group Settings"):
        c1,c2,c3 = st.columns(3)
        with c1: new_start = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
        with c2: new_base  = st.number_input("Base Monthly (GHS)", value=float(st.session_state.base_monthly), step=50.0)
        with c3: new_fee   = st.number_input("Admin Fee (%)", value=float(st.session_state.admin_fee_percentage),
                                             min_value=0.0, max_value=100.0, step=0.5)
        new_names = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
        html(f'<p style="font-size:13px;color:{T["sub_color"]}">Payment records are kept when you add or reorder members. '
             f'To remove someone mid-cycle use Member Status below — deleting the name here shifts every payout date.</p>')

        def save_settings(vals, changes):
            st.session_state.start_date           = vals["start"]
            st.session_state.base_monthly         = vals["base"]
            st.session_state.admin_fee_percentage = vals["fee"]
            st.session_state.names_input          = vals["names"]
            def _m(b):
                put_settings(b)
                return {"type":"setting","text":"Group settings updated","detail":changes}
            if commit(gsheet,_m): flash("Settings saved")

        if st.button("Save Settings", key="save_settings"):
            try: datetime.strptime(new_start,"%Y-%m-%d")
            except ValueError: st.error("Date format must be YYYY-MM-DD."); st.stop()
            changes, structural = [], []
            if new_start != st.session_state.start_date:
                changes.append(f"start date {st.session_state.start_date} → {new_start}"); structural.append("start date")
            if float(new_base) != float(st.session_state.base_monthly):
                changes.append(f"base monthly {fmt_num(st.session_state.base_monthly)} → {fmt_num(new_base)}")
            if float(new_fee) != float(st.session_state.admin_fee_percentage):
                changes.append(f"admin fee {st.session_state.admin_fee_percentage}% → {new_fee}%")
            if new_names.strip() != st.session_state.names_input.strip():
                changes.append("member list edited"); structural.append("member list")
            vals = {"start":new_start,"base":float(new_base),"fee":float(new_fee),"names":new_names}
            if not changes:
                flash("No setting changes","info")
            elif structural:
                st.session_state.pending_settings = {"vals":vals,"changes":changes,"structural":structural}
                st.session_state.confirm_settings = True
            else:
                save_settings(vals, changes)
            st.rerun()

        if st.session_state.get("confirm_settings"):
            pending = st.session_state.get("pending_settings", {})
            st.warning("⚠️ This changes the cycle structure (" + ", ".join(pending.get("structural", [])) +
                       "). Payment history is preserved, but payout dates or the rotation order can move. "
                       "Confirm only if that is intended.")
            sc1,sc2 = st.columns(2)
            with sc1:
                if st.button("✓ Confirm change", key="confirm_settings_yes"):
                    st.session_state.confirm_settings = False
                    p = st.session_state.pop("pending_settings", None)
                    if p: save_settings(p["vals"], p["changes"])
                    st.rerun()
            with sc2:
                if st.button("✗ Cancel", key="confirm_settings_no", type="secondary"):
                    st.session_state.pop("pending_settings", None)
                    st.session_state.confirm_settings = False
                    st.rerun()

    with st.expander("💰  Custom Member Tiers"):
        tier_cols = st.columns(min(num_members,4))
        new_tiers = {}
        for idx,m in enumerate(members):
            with tier_cols[idx%4]:
                new_tiers[m] = st.number_input(m, value=float(tier(m)), step=50.0, key=f"tier_{m}")
        if st.button("Save Tiers", key="save_tiers"):
            diffs = [f"{m}: GHS {fmt_num(tier(m))} → GHS {fmt_num(v)}" for m,v in new_tiers.items() if float(v)!=float(tier(m))]
            def _m(b):
                b.setdefault("tiers",{}).update({k:float(v) for k,v in new_tiers.items()})
                return {"type":"setting","text":f"Member tiers updated ({len(diffs)} changed)","detail":diffs} if diffs else None
            if commit(gsheet,_m): flash("Tiers saved" if diffs else "No tier changes")
            st.rerun()

    with st.expander("👤  Member Status"):
        html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:8px">Mark a member as exited instead of '
             f'deleting them. Their history and rotation slot stay intact; they simply stop owing from the exit week onward.</p>')
        ms1,ms2,ms3 = st.columns([2,1,1])
        with ms1: sm = st.selectbox("Member", members, key="status_member", label_visibility="collapsed")
        with ms2: new_status = st.selectbox("Status", ["active","exited"], index=0 if not exited(sm) else 1,
                                            key="status_val", label_visibility="collapsed")
        with ms3: new_exit_wk = st.number_input("Exit week", min_value=1, max_value=total_weeks,
                                                value=int(mstat(sm).get("exit_week") or max(1,current_elapsed_week)),
                                                step=1, key="status_week", label_visibility="collapsed")
        if st.button("Save Member Status", key="save_status"):
            before = mstat(sm)
            after  = {"status":new_status,"exit_week":int(new_exit_wk) if new_status=="exited" else None}
            def _m(b):
                b.setdefault("member_status",{})[sm] = after
                if before==after: return None
                txt = f"{sm} marked exited from week {new_exit_wk}" if new_status=="exited" else f"{sm} reinstated as active"
                return {"type":"setting","text":txt,"detail":[f"{sm}: {before.get('status')} → {after['status']}"]}
            if commit(gsheet,_m): flash("Member status saved")
            st.rerun()

    with st.expander("🔑  Change Passcode"):
        html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:8px">Enter the current passcode to confirm, '
             f'then set a new one. Passcodes are stored as salted scrypt hashes.</p>')
        cp1,cp2,cp3 = st.columns(3)
        with cp1: old_pw  = st.text_input("Current Passcode", type="password", key="old_pw")
        with cp2: new_pw1 = st.text_input("New Passcode", type="password", key="new_pw1")
        with cp3: new_pw2 = st.text_input("Confirm New Passcode", type="password", key="new_pw2")
        if st.button("Update Passcode", key="update_pw"):
            stored_pw = st.session_state.get("admin_passcode", "")
            if not check_pw(old_pw, stored_pw): st.error("Current passcode is incorrect.")
            elif len(new_pw1) < 8: st.error("New passcode must be at least 8 characters.")
            elif new_pw1 != new_pw2: st.error("New passcodes do not match.")
            else:
                def _m(b):
                    b["passcode"] = hash_pw(new_pw1)
                    return {"type":"setting","text":"Passcode changed"}
                if commit(gsheet,_m): flash("Passcode updated")
                st.rerun()

with tab_tools:
    with st.expander("👤  Member Profile"):
        profile_member = st.selectbox("Member", members, key="profile_member")
        prow  = next(r for r in contrib_rows if r["member"]==profile_member)
        banked_total = money(sum(paid_amount(profile_member,w) for w in range(1,total_weeks+1)))
        mp1,mp2,mp3 = st.columns(3)
        mp1.metric("Weekly target", f"GHS {fmt_num(weekly(profile_member))}")
        mp2.metric("Banked to date", f"GHS {fmt_num(banked_total)}")
        mp3.metric("Outstanding", f"GHS {fmt_num(prow['owing'])}")
        profile_txs = txs_for(profile_member)
        if profile_txs:
            for tx in profile_txs[:20]:
                st.markdown(f"**Week {int(tx.get('week',0)):02d} · GHS {fmt_num(tx.get('amount',0))}** · "
                            f"{tx.get('method','—')} · {tx.get('date','')} · {tx.get('reference') or 'no reference'}")
        else:
            st.info("No itemised transactions for this member yet — any amounts above come from the legacy week grid.")

    with st.expander("🧮  Cash Reconciliation"):
        html(f'<div style="font-size:14px;color:{T["td_color"]};line-height:1.8">System cash held: '
             f'<strong style="color:{T["sec_title"]}">GHS {fmt_num(total_cash_held)}</strong><br>'
             f'Enter the physical cash plus verified mobile/bank balance actually held by the group.</div>')
        actual_cash = st.number_input("Actual cash / account balance (GHS)", min_value=0.0,
                                      value=float(total_cash_held), step=10.0, key="recon_actual")
        recon_diff = money(actual_cash - total_cash_held)
        if abs(recon_diff) < 0.005: st.success("Reconciled — actual balance matches the system.")
        elif recon_diff > 0:        st.warning(f"GHS {fmt_num(recon_diff)} more than the system balance.")
        else:                       st.error(f"GHS {fmt_num(abs(recon_diff))} less than the system balance.")
        recon_note = st.text_input("Reconciliation note", key="recon_note", placeholder="e.g. Cash counted + MoMo balance checked")
        if st.button("Save Reconciliation", key="save_recon"):
            def _m(b):
                rec = {"date":now_str(),"actual":money(actual_cash),"system":money(total_cash_held),
                       "difference":money(recon_diff),"note":recon_note.strip(),
                       "who":st.session_state.get("admin_name",ADMIN_NAME)}
                b.setdefault("reconciliations",[]).insert(0, rec)
                b["reconciliations"] = b["reconciliations"][:100]
                return {"type":"setting",
                        "text":f"Cash reconciled — actual GHS {fmt_num(actual_cash)} vs system GHS {fmt_num(total_cash_held)}",
                        "detail":[f"difference: GHS {fmt_num(recon_diff)}", f"note: {recon_note.strip() or '—'}"]}
            if commit(gsheet,_m): flash("Reconciliation recorded")
            st.rerun()
        recs = st.session_state.get("reconciliations",[])[:5]
        if recs:
            rec_html = ""
            for rec in recs:
                diff = money(rec.get("difference",0))
                col  = "#34d399" if abs(diff)<0.005 else ("#fbbf24" if diff>0 else "#f87171")
                rec_html += (f'<div class="log-entry"><div class="log-dot log-dot-setting"></div>'
                             f'<div class="log-text"><strong>Actual GHS {fmt_num(rec.get("actual",0))} vs system '
                             f'GHS {fmt_num(rec.get("system",0))}</strong>'
                             f'<div class="diff-line" style="color:{col}">difference GHS {fmt_num(diff)}'
                             f'{" · " + rec.get("note","") if rec.get("note") else ""}</div></div>'
                             f'<div class="log-time">{rec.get("date","")}</div></div>')
            html(rec_html)

    with st.expander("🧾  Payment Audit"):
        ledger = st.session_state.get("payment_ledger", [])
        if not ledger:
            st.info("No payment audit entries yet.")
        else:
            led_html = ""
            for entry in ledger[:30]:
                act    = entry.get("action","paid")
                action = {"paid":"PAID","reversed":"REVERSED","corrected":"CORRECTED"}.get(act, act.upper())
                dot    = "log-dot" if act == "paid" else "log-dot log-dot-payout"
                extra  = " · ".join(x for x in [entry.get("method",""), entry.get("reference",""), entry.get("reason","")] if x)
                led_html += (f'<div class="log-entry"><div class="{dot}"></div>'
                             f'<div class="log-text"><strong>{entry.get("member","—")} · Week {int(entry.get("week",0)):02d} · '
                             f'GHS {fmt_num(entry.get("amount",0))}</strong>'
                             f'<div class="diff-line">{action} · by {entry.get("who","")}{" · " + extra if extra else ""}</div></div>'
                             f'<div class="log-time">{entry.get("time","")}</div></div>')
            html(led_html)

    if st.session_state.history:
        with st.expander("🕒  Activity Log"):
            dot_map = {"payment":"log-dot","payout":"log-dot log-dot-payout","setting":"log-dot log-dot-setting"}
            log_html = ""
            for entry in st.session_state.history[:25]:
                dot_class = dot_map.get(entry.get("type","payment"),"log-dot")
                who       = entry.get("who","")
                detail    = entry.get("detail") or []
                det_html  = "".join(f'<div class="diff-line">• {d}</div>' for d in detail[:12])
                if len(detail)>12: det_html += f'<div class="diff-line">• …and {len(detail)-12} more</div>'
                who_html  = f'<div class="diff-line">by {who}</div>' if who else ""
                log_html += (f'<div class="log-entry"><div class="{dot_class}"></div>'
                             f'<div class="log-text"><strong>{entry.get("text","—")}</strong>'
                             f'{who_html}{det_html}</div>'
                             f'<div class="log-time">{entry.get("time","")}</div></div>')
            html(log_html)

html('<div class="gdivider"></div>')
if st.button("🔒  Lock Dashboard", key="logout", type="secondary"):
    st.session_state.authenticated=False; st.session_state.admin_name=ADMIN_NAME
    st.session_state.last_activity=now_dt(); st.rerun()

html('<div class="foot">Susu Savings · Backed by Google Sheets · Secured with passcode</div>')
