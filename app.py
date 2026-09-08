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
""", unsafe_allow_html=True)

# ── HTML helper ───────────────────────────────────────────────────────────────
# Streamlit's Markdown parser treats a blank line followed by a line indented
# 4+ spaces as a code block. This strips leading whitespace from every line so
# multi-line HTML strings render as HTML, never as literal code.
def html(s):
    st.markdown(re.sub(r"\n[ \t]+", "\n", s).strip(), unsafe_allow_html=True)

# ── theme ─────────────────────────────────────────────────────────────────────
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

dl_color     = "#56c8f5"
urgent_glow  = "0 0 16px rgba(251,191,36,0.45),0 0 32px rgba(251,191,36,0.18)"
ring_text_c  = "#56c8f5"

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

    .status-bar{{background:{T['status_bg']};border-bottom:1px solid {T['status_border']};padding:8px 0;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;font-size:12px;}}
    .status-dot{{width:6px;height:6px;background:#34d399;border-radius:50%;display:inline-block;margin-right:6px;animation:pulse 2s infinite;}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
    .status-live{{color:#34d399;font-weight:600;}} .status-sync{{color:{T['sync_color']};}}

    .lock-outer{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;margin-top:-2rem;}}
    .lock-card{{background:{T['lock_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['lock_border']};border-radius:24px;padding:48px 40px;text-align:center;width:100%;max-width:360px;box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 0 rgba(255,255,255,0.4);}}
    .lock-icon{{font-size:44px;margin-bottom:16px;display:block;}}
    .lock-title{{font-size:22px;font-weight:700;color:{T['lock_title']};margin-bottom:6px;}}
    .lock-sub{{font-size:13px;color:{T['lock_sub']};margin-bottom:0;}}

    .topline{{margin-bottom:12px;}}
    .topline-title{{font-size:24px;font-weight:700;color:{T['title_color']};letter-spacing:-0.3px;margin:0 0 2px;}}
    .topline-sub{{font-size:13px;color:{T['sub_color']};margin:0;}}

    .alert-bar{{background:rgba(251,191,36,0.09);border:1px solid rgba(251,191,36,0.28);border-radius:14px;padding:12px 16px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;}}
    .alert-title{{font-size:16px;font-weight:700;color:#fbbf24;}}
    .alert-sub{{font-size:13px;color:{T['td_color']};margin-top:3px;line-height:1.4;}}
    .alert-cta{{font-size:13px;font-weight:600;color:#fbbf24;white-space:nowrap;opacity:0.85;}}
    .chip-calc{{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:{T['sub_color']};margin-top:3px;}}
    .chip-calc span:last-child{{font-variant-numeric:tabular-nums;color:{T['td_color']};}}
    .cell-sub{{font-size:12px;color:{T['sub_color']};margin-top:2px;}}

    .days-badge{{display:inline-block;background:rgba(129,140,248,0.12);color:#818cf8;border:1px solid rgba(129,140,248,0.25);border-radius:10px;padding:2px 8px;font-size:12px;font-weight:600;white-space:nowrap;}}
    .days-badge.urgent{{background:rgba(251,191,36,0.12);color:#fbbf24;border-color:rgba(251,191,36,0.3);}}

    .chip-row{{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;}}
    .chip{{flex:1;min-width:110px;background:{T['chip_bg']};backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid {T['chip_border']};border-radius:14px;padding:14px 16px;box-shadow:0 2px 12px rgba(0,0,0,0.1),inset 0 1px 0 rgba(255,255,255,0.2);}}
    .chip-label{{font-size:12px;font-weight:600;color:{T['label_color']};text-transform:uppercase;letter-spacing:0.7px;margin-bottom:6px;}}
    .chip-value{{font-size:21px;font-weight:700;color:#38bdf8;}}
    .chip-value-green{{font-size:21px;font-weight:700;color:#34d399;}}
    .chip-value-amber{{font-size:21px;font-weight:700;color:#fbbf24;}}
    .chip-value-red{{font-size:21px;font-weight:700;color:#f87171;}}
    @keyframes countUp{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
    .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{animation:countUp 0.6s ease-out;}}
    .chip-sub{{font-size:12px;color:{T['sub_color']};margin-top:3px;}}

    .glass-card{{background:{T['card_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['card_border']};border-radius:16px;padding:20px 22px;margin-bottom:14px;box-shadow:{T['card_shadow']};}}
    .sec-label{{font-size:11px;font-weight:700;color:{T['label_color']};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
    .sec-title{{font-size:18px;font-weight:700;color:{T['sec_title']};margin:0 0 2px 0;}}
    .sec-sub{{font-size:13px;color:{T['sub_color']};margin:0 0 14px 0;}}

    .data-table{{width:100%;border-collapse:collapse;}}
    .data-table th{{font-size:12px;font-weight:600;color:{T['th_color']};text-transform:uppercase;letter-spacing:0.6px;padding:8px 12px;border-bottom:1px solid {T['th_border']};text-align:left;}}
    .data-table td{{font-size:15px;color:{T['td_color']};padding:10px 12px;border-bottom:1px solid {T['td_border']};vertical-align:middle;}}
    .data-table tr:last-child td{{border-bottom:none;}}
    .data-table tr.owing td:first-child{{border-left:2px solid #fbbf24;padding-left:10px;}}
    .data-table tr.ok td:first-child{{border-left:2px solid #34d399;padding-left:10px;}}
    .data-table tr.plain td:first-child{{border-left:2px solid transparent;padding-left:10px;}}
    .cell-name{{font-weight:600;color:{T['member_name']};}}
    .badge-ok{{background:rgba(52,211,153,0.12);color:#34d399;border:1px solid rgba(52,211,153,0.25);border-radius:20px;padding:2px 10px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .badge-owe{{background:rgba(251,191,36,0.12);color:#fbbf24;border:1px solid rgba(251,191,36,0.25);border-radius:20px;padding:2px 10px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .badge-pending{{background:rgba(148,163,184,0.1);color:#64748b;border:1px solid rgba(148,163,184,0.2);border-radius:20px;padding:2px 10px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .streak-badge{{background:{T['streak_bg']};color:{T['streak_color']};border:1px solid {T['streak_border']};border-radius:20px;padding:2px 9px;font-size:12px;font-weight:600;white-space:nowrap;margin-left:6px;}}

    .badge-exempt{{background:rgba(148,163,184,0.1);color:{T['sub_color']};border:1px dashed {T['card_border']};border-radius:20px;padding:2px 10px;font-size:13px;font-weight:600;white-space:nowrap;}}
    .exit-tag{{font-size:11px;color:{T['sub_color']};font-weight:600;margin-left:6px;text-transform:uppercase;letter-spacing:0.4px;}}
    .diff-line{{font-size:12px;color:{T['td_color']};font-family:ui-monospace,Menlo,monospace;}}
    .pbar-wrap{{margin-top:6px;background:{T['bar_bg']};border-radius:4px;height:4px;overflow:hidden;}}
    .pbar-fill{{height:4px;border-radius:4px;background:linear-gradient(90deg,#34d399,#38bdf8);transition:width 0.4s ease;}}
    .early-eligible{{font-size:12px;color:#34d399;margin-top:3px;font-weight:600;}}


    .log-entry{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid {T['log_border']};}}
    .log-entry:last-child{{border-bottom:none;}}
    .log-dot{{width:8px;height:8px;border-radius:50%;background:#38bdf8;margin-top:4px;flex-shrink:0;}}
    .log-dot-payout{{background:#818cf8;}} .log-dot-setting{{background:#34d399;}}
    .log-text{{font-size:14px;color:{T['log_color']};line-height:1.4;}}
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
    /* Expanders (current Streamlit DOM) */
    details[data-testid="stExpander"]{{background:{T['exp_bg']}!important;backdrop-filter:blur(12px)!important;border:1px solid {T['exp_border']}!important;border-radius:12px!important;margin-bottom:8px!important;overflow:hidden;}}
    details[data-testid="stExpander"] summary{{background:transparent!important;padding:12px 16px!important;}}
    details[data-testid="stExpander"] summary,details[data-testid="stExpander"] summary *{{color:{T['sec_title']}!important;font-size:15px!important;font-weight:600!important;}}
    details[data-testid="stExpander"] summary:hover{{color:{dl_color}!important;}}
    details[data-testid="stExpander"] summary svg{{fill:{T['sec_title']}!important;color:{T['sec_title']}!important;}}
    details[data-testid="stExpander"] > div:not(summary){{background:{T['exp_content']}!important;border-top:1px solid {T['exp_border']}!important;padding:18px!important;}}
    details[data-testid="stExpander"] p,details[data-testid="stExpander"] label,details[data-testid="stExpander"] .stCheckbox span{{color:{T['td_color']};}}
    .streamlit-expanderHeader{{background:{T['exp_bg']}!important;color:{T['sec_title']}!important;font-size:13px!important;font-weight:600!important;border-radius:12px!important;}}
    div[data-testid="stSuccess"]{{background:rgba(16,185,129,0.07)!important;border:1px solid rgba(16,185,129,0.2)!important;border-radius:10px!important;color:#34d399!important;font-size:14px!important;}}
    div[data-testid="stError"]{{background:rgba(239,68,68,0.07)!important;border:1px solid rgba(239,68,68,0.2)!important;border-radius:10px!important;color:#f87171!important;font-size:14px!important;}}
    div[data-testid="stWarning"]{{background:rgba(251,191,36,0.07)!important;border:1px solid rgba(251,191,36,0.2)!important;border-radius:10px!important;color:#fbbf24!important;font-size:14px!important;}}
    .stTabs [data-baseweb="tab-list"]{{gap:6px;background:transparent;}}
    .stTabs [data-baseweb="tab"]{{background:{T['btn2_bg']};border:1px solid {T['btn2_border']};border-radius:10px;padding:6px 14px;color:{T['btn2_color']};font-size:12px;font-weight:600;}}
    .stTabs [aria-selected="true"]{{background:{T['dl_bg']}!important;color:{dl_color}!important;border-color:{T['dl_border']}!important;}}
    .stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{{display:none;}}
    div[data-testid="stCode"] pre,div[data-testid="stCodeBlock"] pre{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;border-radius:12px!important;font-size:14px!important;line-height:1.55!important;}}
    div[data-testid="stCode"] code,div[data-testid="stCodeBlock"] code{{color:{T['td_color']}!important;white-space:pre-wrap!important;}}
    .copy-hint{{font-size:13px;color:{T['sub_color']};margin:-6px 0 8px;}}
    .gdivider{{height:1px;background:linear-gradient(90deg,transparent,{T['gdiv']},transparent);margin:22px 0;}}
    .foot{{text-align:center;font-size:12px;color:{T['foot_color']};margin-top:32px;padding-top:20px;border-top:1px solid {T['foot_border']};}}
    @media (max-width:600px){{
        .block-container{{padding-bottom:3rem!important;padding-left:10px!important;padding-right:10px!important;}}
        /* header row: keep Refresh + theme side by side instead of stacking */
        .block-container div[data-testid="stHorizontalBlock"]:first-of-type{{flex-wrap:nowrap!important;gap:8px!important;}}
        .block-container div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stColumn"]{{min-width:0!important;flex:1 1 0!important;}}
        .block-container div[data-testid="stHorizontalBlock"]:first-of-type button{{padding:7px 8px!important;font-size:12px!important;white-space:nowrap;}}
        .status-bar{{margin-bottom:10px!important;padding:6px 0!important;}}
        .topline-title{{font-size:20px!important;}} .topline-sub{{font-size:12px!important;line-height:1.4;}}
        .alert-bar{{flex-direction:column;align-items:flex-start!important;padding:10px 12px!important;}}
        .alert-cta{{display:none;}}
        .chip-row{{display:grid!important;grid-template-columns:1fr 1fr!important;gap:8px!important;}}
        .chip{{min-width:0!important;padding:10px 12px!important;}}
        .chip-row .chip:last-child:nth-child(odd){{grid-column:1 / -1;}}
        .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{font-size:18px!important;}}
        .glass-card{{padding:14px 12px!important;border-radius:12px!important;}}
        .sec-title{{font-size:16px!important;}}
        .sec-sub{{font-size:12px!important;line-height:1.35;}}
        .data-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;}}
        .data-table th,.data-table td{{padding:9px 10px!important;font-size:13px!important;}}
        /* trim low-value columns so the important ones fit without scrolling */
        .tbl-contrib th:nth-child(2),.tbl-contrib td:nth-child(2){{display:none;}}
        .tbl-payout.has-fee th:nth-child(4),.tbl-payout.has-fee td:nth-child(4),
        .tbl-payout.has-fee th:nth-child(6),.tbl-payout.has-fee td:nth-child(6),
        .tbl-payout.no-fee th:nth-child(5),.tbl-payout.no-fee td:nth-child(5){{display:none;}}
        .swipe-hint{{display:block!important;}}
    }}
    /* tablets and small laptops — the phone sizes read far too small here */
    @media (min-width:601px) and (max-width:1280px){{
        .topline-title{{font-size:26px;}} .topline-sub{{font-size:14px;}}
        .chip{{padding:16px 18px;}}
        .chip-label{{font-size:12px;}} .chip-sub,.chip-calc{{font-size:13px;}}
        .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{font-size:23px;}}
        .glass-card{{padding:22px 24px;}}
        .sec-title{{font-size:19px;}} .sec-sub{{font-size:14px;}} .sec-label{{font-size:12px;}}
        .data-table th{{font-size:12px;padding:11px 15px;}}
        .data-table td{{font-size:16px;padding:13px 15px;}}
        .alert-title{{font-size:17px;}} .alert-sub{{font-size:14px;}}
        .badge-ok,.badge-owe,.badge-pending,.badge-exempt{{font-size:12px;padding:3px 12px;}}
        div[data-testid="stCode"] pre,div[data-testid="stCodeBlock"] pre{{font-size:13px!important;}}
        details[data-testid="stExpander"] summary,details[data-testid="stExpander"] summary *{{font-size:14px!important;}}
        .stButton > button,.stDownloadButton > button{{font-size:14px!important;padding:10px 22px!important;}}
    }}
    /* landscape tablets: reclaim vertical space */
    @media (min-width:601px) and (max-height:820px) and (orientation:landscape){{
        .glass-card{{padding:16px 20px;margin-bottom:12px;}}
        .chip{{padding:12px 16px;}}
        .topline{{margin-bottom:10px;}}
        .data-table td{{padding:9px 14px;}}
    }}
    .swipe-hint{{display:none;font-size:12px;color:{T['sub_color']};margin:6px 0 0;}}
    </style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def money(x):
    """All GHS amounts pass through here (#6) — kills float drift like 4999.999999."""
    return round(float(x)+1e-9, 2)

def fmt_num(val):
    val = money(val)
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

def hash_pw(pw):
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def is_hashed(val):
    return isinstance(val,str) and len(val)==64 and all(c in "0123456789abcdef" for c in val)

def check_pw(entered, stored):
    return hash_pw(entered)==stored if is_hashed(stored) else entered==stored

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
# STORAGE — one JSON blob, one read per load (#2), rev-guarded writes (#1)
# ══════════════════════════════════════════════════════════════════════════════
SCOPES    = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
DATA_WS   = "susu_data"
ADMIN_PW  = "Susu2026"
ADMIN_NAME = "Abre"          # default name shown on the unlock screen / activity log
LEGACY_WS = ["settings","tiers","payments","payout_status","history","snapshots","passcode"]

DEFAULT_SETTINGS = {"start_date":"2026-08-17","base_monthly":1000,"admin_fee_percentage":0.0,
                    "names_input":"Alice, Bob, Charlie, Diana, Frank, Grace"}

def blank_blob():
    return {"rev":0,"settings":dict(DEFAULT_SETTINGS),"tiers":{},"payments":{},
            "payout_status":{},"history":[],"snapshots":{},"member_status":{},"passcode":ADMIN_PW}

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

def migrate_legacy(sheet):
    """One-time: fold the old one-worksheet-per-key layout into a single blob."""
    b = blank_blob()
    existing = {ws.title for ws in sheet.worksheets()}
    if not (set(LEGACY_WS) & existing): return b
    b["settings"]      = _read_ws_json(sheet,"settings",DEFAULT_SETTINGS) if "settings" in existing else dict(DEFAULT_SETTINGS)
    b["tiers"]         = _read_ws_json(sheet,"tiers",{})         if "tiers" in existing else {}
    b["payments"]      = _read_ws_json(sheet,"payments",{})      if "payments" in existing else {}
    b["payout_status"] = _read_ws_json(sheet,"payout_status",{}) if "payout_status" in existing else {}
    b["history"]       = _read_ws_json(sheet,"history",[])       if "history" in existing else []
    b["snapshots"]     = _read_ws_json(sheet,"snapshots",{})     if "snapshots" in existing else {}
    b["passcode"]      = _read_ws_json(sheet,"passcode",ADMIN_PW) if "passcode" in existing else ADMIN_PW
    b["history"].insert(0,{"type":"setting","text":"Data migrated to single-blob storage","who":"system","time":now_str()})
    return b

def read_blob_fresh(sheet):
    """Uncached — one API read. Used before every write."""
    raw = ensure_ws(sheet, DATA_WS).cell(1,1).value
    if raw:
        try:
            b = json.loads(raw)
            for k,v in blank_blob().items(): b.setdefault(k,v)
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
    st.session_state.admin_passcode       = b.get("passcode",ADMIN_PW)
    st.session_state.last_sync            = datetime.now()

def reload_state(sheet, fresh=False):
    apply_blob(read_blob_fresh(sheet) if fresh else read_blob_cached(sheet))

def commit(sheet, mutate):
    """Re-read, refuse if someone else wrote since we loaded (#1), else apply+bump rev."""
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
    st.session_state.authenticated  = False
    st.session_state.initialized    = True
    st.session_state.confirm_payout = False
    st.session_state.admin_name     = ADMIN_NAME

STALE_MINUTES = 5
if (datetime.now()-st.session_state.last_sync).total_seconds() > STALE_MINUTES*60:
    reload_state(gsheet)

show_flash()

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
            stored = st.session_state.get("admin_passcode", ADMIN_PW)
            if not who.strip():
                st.error("Please enter your name — every change is recorded against it.")
            elif check_pw(pw, stored):
                st.session_state.admin_name    = who.strip()[:40]
                st.session_state.authenticated = True
                if not is_hashed(stored):
                    commit(gsheet, lambda b: (b.__setitem__("passcode", hash_pw(pw)), None)[1])
                st.rerun()
            else: st.error("Incorrect passcode.")
    st.stop()

# ── derive ────────────────────────────────────────────────────────────────────
members     = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)
if num_members < 2: st.error("Please enter at least 2 member names."); st.stop()

for m in members:
    st.session_state.member_tiers.setdefault(m, st.session_state.base_monthly)
    st.session_state.member_status.setdefault(m, {"status":"active","exit_week":None})

total_weeks = num_members * 4      # rotation is fixed; exiting a member never shifts dates (#7)

try: start_dt = datetime.strptime(st.session_state.start_date, "%Y-%m-%d")
except ValueError: st.error("Date format must be YYYY-MM-DD."); st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

for m in members:
    st.session_state.payments.setdefault(m, {})
    for w in range(1,total_weeks+1):
        st.session_state.payments[m].setdefault(str(w), False)
for i in range(num_members):
    st.session_state.payout_status.setdefault(f"Month {i+1}", {})

today                = datetime.today()
days_passed          = (today-start_dt).days
current_elapsed_week = min(max(0,days_passed//7)+1 if today>=start_dt else 0, total_weeks)
program_pct          = int(current_elapsed_week/total_weeks*100) if total_weeks else 0
fee_frac             = st.session_state.admin_fee_percentage/100.0

def tier(m):    return st.session_state.member_tiers.get(m,st.session_state.base_monthly)
def weekly(m):  return money(tier(m)/4.0)
def paid(m,w):  return bool(st.session_state.payments.get(m,{}).get(str(w),False))
def mstat(m):   return st.session_state.member_status.get(m,{"status":"active","exit_week":None})
def exited(m):  return mstat(m).get("status")=="exited"
def exit_week(m):
    ew = mstat(m).get("exit_week")
    return int(ew) if ew else total_weeks
def liable(m,w):
    """Exited members owe nothing after their exit week (#7)."""
    return not (exited(m) and w > exit_week(m))
def liable_total(m):
    return sum(1 for w in range(1,total_weeks+1) if liable(m,w))

# #2 collections derived from ticks
def gross_collected_for_month(i):
    return money(sum(weekly(m) for m in members for w in range(4*i+1,4*i+5) if paid(m,w)))

total_cash_collected = money(sum(weekly(m) for m in members for w in range(1,total_weeks+1) if paid(m,w)))

def collected_amount(month_lbl):
    """How much of their payout the recipient has actually collected so far.
    Partial collections are normal; keys from older versions are still honoured."""
    ps = st.session_state.payout_status.get(month_lbl,{})
    return money(ps.get("collected", ps.get("disbursed_amount", ps.get("amount_collected",0.0))))

total_payouts_dist    = money(sum(collected_amount(f"Month {i+1}") for i in range(num_members)))
total_cash_held       = money(total_cash_collected - total_payouts_dist)
total_expected_so_far = money(sum(weekly(m)*sum(1 for w in range(1,current_elapsed_week+1) if liable(m,w)) for m in members))
# money due-but-unpaid up to this week — matches the owing banner exactly
collection_gap        = money(sum(weekly(m) for m in members
                                  for w in range(1,current_elapsed_week+1)
                                  if liable(m,w) and not paid(m,w)))
# weeks ticked beyond the current week — cash in hand, but not yet "due"
paid_ahead            = money(sum(weekly(m) for m in members
                                  for w in range(current_elapsed_week+1,total_weeks+1) if paid(m,w)))

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
    paid_passed = sum(1 for w in range(1,current_elapsed_week+1) if liable(member,w) and paid(member,w))
    owing       = money((due_weeks-paid_passed)*m_weekly)
    total_paid  = sum(1 for w in range(1,total_weeks+1) if paid(member,w))
    is_out      = exited(member)
    standing    = f"Owing GHS {fmt_num(owing)}" if owing>0 else ("Exited" if is_out else "Up to date")
    streak      = 0 if (is_out and owing<=0) else missed_streak(member)
    contrib_rows.append({"member":member,"m_monthly":tier(member),"m_weekly":m_weekly,"total_paid":total_paid,
                         "paid_due":paid_passed,"due_so_far":due_weeks,
                         "due_total":liable_total(member),"owing":owing,"standing":standing,"streak":streak,
                         "exited":is_out,"exit_week":mstat(member).get("exit_week")})
    wa_contrib_rows.append({"member":member,"standing":standing,"streak":streak,"exited":is_out})

# ── payout schedule ───────────────────────────────────────────────────────────
schedule_rows, wa_payout_rows = [], []
cur_d = start_dt
for i in range(num_members):
    month_lbl    = f"Month {i+1}"
    recipient    = members[i]
    payout_date  = cur_d+timedelta(weeks=4)
    gross_pool   = money(tier(recipient)*num_members)
    admin_fee_v  = money(gross_pool*fee_frac)
    net_pool_amt = money(gross_pool-admin_fee_v)
    collected    = collected_amount(month_lbl)                     # paid out to the recipient
    remaining    = money(max(0.0, net_pool_amt-collected))          # still owed to the recipient
    pct_c        = int(collected/net_pool_amt*100) if net_pool_amt>0 else 0
    funded       = money(gross_collected_for_month(i)*(1-fee_frac)) # contributions banked for this turn
    ps           = st.session_state.payout_status.get(month_lbl,{})
    disbursed    = ps.get("disbursed",False) or (collected >= net_pool_amt-0.005 and collected>0)
    days_away    = (payout_date-today).days if payout_date>=today else None
    early_ok     = (funded >= net_pool_amt-0.005) and remaining>0 and (payout_date >= today)
    schedule_rows.append({"turn":month_lbl,"recipient":recipient,"date":format_date(payout_date),"payout_date":payout_date,
                          "fee":fmt_num(admin_fee_v),"pool":fmt_num(net_pool_amt),"collected":fmt_num(collected),
                          "remaining":fmt_num(remaining),"remaining_v":remaining,"collected_v":collected,"pct":pct_c,
                          "disbursed":disbursed,"funded":funded,"funded_s":fmt_num(funded),
                          "disb_date":ps.get("disbursed_date",""),
                          "days_away":days_away,"early_ok":early_ok,"net_pool_amt":net_pool_amt,
                          "exited":exited(recipient)})
    wa_payout_rows.append({"recipient":recipient,"date":format_date(payout_date),"balance":fmt_num(remaining),"disbursed":disbursed})
    cur_d = payout_date


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
sync_ago = int((datetime.now()-st.session_state.last_sync).total_seconds()/60)
sync_txt = "just now" if sync_ago<1 else f"{sync_ago}m ago"
html(f"""<div class="status-bar"><span><span class="status-dot"></span><span class="status-live">Live</span></span><span class="status-sync">Synced {sync_txt} &nbsp;·&nbsp; rev {st.session_state.rev}</span></div>""")
rf_col,_sp = st.columns([1,3])
with rf_col:
    if st.button("↻ Refresh", key="refresh_btn", type="secondary"):
        reload_state(gsheet, fresh=True); flash("Refreshed from Google Sheets"); st.rerun()

gap_class  = "chip-value-red" if collection_gap>0 else "chip-value-green"
gap_label  = f"−GHS {fmt_num(collection_gap)}" if collection_gap>0 else "On track"

# fourth chip: funding progress on the turn that pays out next
next_turn = next((r for r in schedule_rows if not r["disbursed"]), None)
if next_turn:
    funded_pct  = int(min(next_turn["funded"]/next_turn["net_pool_amt"],1)*100) if next_turn["net_pool_amt"] else 0
    fund_class  = "chip-value-green" if funded_pct>=100 else "chip-value"
    fund_main   = f'<div class="{fund_class}">{funded_pct}% funded</div>'
    fund_sub    = (f'<div class="chip-calc"><span>{next_turn["turn"].replace("Month","Turn")} pool</span>'
                   f'<span>{next_turn["funded_s"]} / {next_turn["pool"]}</span></div>'
                   f'<div class="pbar-wrap" style="margin-top:5px"><div class="pbar-fill" style="width:{min(funded_pct,100)}%"></div></div>')
else:
    fund_main, fund_sub = '<div class="chip-value-green">All paid out</div>', '<div class="chip-sub">Cycle complete</div>'

# (2) don't show a negative zero before any payout has been taken
payouts_line = (f'<div class="chip-calc"><span>Payouts collected</span><span>−{fmt_num(total_payouts_dist)}</span></div>'
                if total_payouts_dist>0 else
                '<div class="chip-calc"><span>Payouts collected</span><span>None yet</span></div>')
ahead_line   = (f'<div class="chip-sub" style="color:#34d399">+GHS {fmt_num(paid_ahead)} paid ahead</div>'
                if paid_ahead>0 else "")
prev_snap  = st.session_state.get("snapshots",{}).get(str(current_elapsed_week-1))
if prev_snap is not None and current_elapsed_week>1:
    snap_delta = money(total_cash_held-float(prev_snap))
    d_arrow    = "\u2191" if snap_delta>=0 else "\u2193"
    d_color    = "#34d399" if snap_delta>=0 else "#f87171"
    delta_html = f'<div class="chip-sub" style="color:{d_color};font-weight:600">{d_arrow} GHS {fmt_num(abs(snap_delta))} vs last week</div>'
else:
    delta_html = '<div class="chip-sub">No prior snapshot yet</div>'

# next payout chip names the recipient
if next_recipient:
    urgent_cls  = "chip-value-amber" if days_to_payout<=7 else "chip-value"
    payout_main = f'<div class="{urgent_cls}">{next_recipient}</div>'
    payout_sub  = f'<div class="chip-sub">{format_date(next_payout_date)} \u00b7 in {days_to_payout}d \u00b7 GHS {fmt_num(next_net_pool)}</div>'
else:
    payout_main, payout_sub = '<div class="chip-value">\u2014</div>', '<div class="chip-sub">Cycle complete</div>'

# cycle progress lives inside the Week chip
week_bar = f'<div class="pbar-wrap" style="margin-top:7px"><div class="pbar-fill" style="width:{program_pct}%"></div></div><div class="chip-sub">{program_pct}% of cycle</div>'

html(f"""
    <div class="topline">
        <div class="topline-title">💸 Susu Savings</div>
        <div class="topline-sub">{num_members} members &nbsp;·&nbsp; {format_date(start_dt)} → {format_date(end_date)} &nbsp;·&nbsp; 🔓 {st.session_state.admin_name}</div>
    </div>
""")

html(f"""
    <div class="chip-row">
        <div class="chip"><div class="chip-label">Cash Held</div><div class="chip-value">GHS {fmt_num(total_cash_held)}</div>
            <div class="chip-calc"><span>Contributions in</span><span>{fmt_num(total_cash_collected)}</span></div>
            {payouts_line}
            {delta_html}</div>
        <div class="chip"><div class="chip-label">Week</div><div class="chip-value">{current_elapsed_week} / {total_weeks}</div>{week_bar}</div>
        <div class="chip"><div class="chip-label">Next Payout</div>{payout_main}{payout_sub}</div>
        <div class="chip"><div class="chip-label">Due this week</div><div class="{gap_class}">{gap_label}</div><div class="chip-calc"><span>Expected to date</span><span>{fmt_num(total_expected_so_far)}</span></div>{ahead_line}</div>
        <div class="chip"><div class="chip-label">Next Pool</div>{fund_main}{fund_sub}</div>
    </div>
""")

# (4) owing banner — only when someone is behind
owing_now = [r for r in contrib_rows if r["owing"]>0]
if owing_now:
    total_owed = money(sum(r["owing"] for r in owing_now))
    who_owes   = ", ".join(f'{r["member"]} (GHS {fmt_num(r["owing"])})' for r in owing_now[:4])
    if len(owing_now)>4: who_owes += f' +{len(owing_now)-4} more'
    html(f"""<div class="alert-bar">
        <div><div class="alert-title">⚠️ {len(owing_now)} member{"s" if len(owing_now)>1 else ""} owing GHS {fmt_num(total_owed)}</div>
        <div class="alert-sub">{who_owes}</div></div>
        <div class="alert-cta">Send the Reminder ↓</div></div>""")

def ahead_cell(r):
    """Only worth a second line when the member has paid beyond this week."""
    n = r["total_paid"] - r["paid_due"]
    return f'<div class="cell-sub" style="color:#34d399">+{n} wk ahead</div>' if n>0 else ""

rows_html = ""
for r in contrib_rows:
    is_owing  = r["owing"]>0
    row_class = "owing" if is_owing else ("plain" if r["exited"] else "ok")
    if is_owing:      badge = f'<span class="badge-owe">Owing GHS {fmt_num(r["owing"])}</span>'
    elif r["exited"]: badge = '<span class="badge-exempt">Exited</span>'
    else:             badge = '<span class="badge-ok">Up to date</span>'
    streak_html = f'<span class="streak-badge">🔴 {r["streak"]}wk streak</span>' if r["streak"]>=2 else ""
    exit_tag    = f'<span class="exit-tag">left wk {r["exit_week"]}</span>' if r["exited"] and r["exit_week"] else ""
    rows_html += (f'<tr class="{row_class}">'
                  f'<td><span class="cell-name">{r["member"]}</span>{exit_tag}</td>'
                  f'<td>GHS {fmt_num(r["m_monthly"])}</td><td>GHS {fmt_num(r["m_weekly"])}</td>'
                  f'<td>{r["paid_due"]} / {r["due_so_far"]}{ahead_cell(r)}</td>'
                  f'<td>{badge}{streak_html}</td></tr>')

html(f"""<div class="glass-card">
    <div id="section-payments"></div><p class="sec-label">Members</p>
    <p class="sec-title">Contributions</p>
    <p class="sec-sub">Week {current_elapsed_week} standing</p>
    <table class="data-table tbl-contrib">
        <thead><tr><th>Member</th><th>Monthly</th><th>Weekly</th><th>Paid / Due</th><th>Status</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table><p class="swipe-hint">Swipe the table sideways for monthly tiers.</p></div>""")

show_fee      = fee_frac > 0
fee_col_head  = "<th>Admin Fee</th>" if show_fee else ""
fee_cls       = "has-fee" if show_fee else "no-fee"
def fee_cell(r): return f'<td>GHS {r["fee"]}</td>' if show_fee else ""

pay_rows_html = ""
for r in schedule_rows:
    bar_pct = min(r['pct'],100)
    if r['disbursed']:
        status_badge = '<span class="badge-ok">✅ Fully collected</span>'
        if r['disb_date']: status_badge += f'<div style="font-size:13px;color:{T["sub_color"]};margin-top:3px">{r["disb_date"]}</div>'
    elif r['collected_v'] > 0:
        status_badge = f'<span class="badge-owe">◐ Part collected</span>'
    else:
        status_badge = '<span class="badge-pending">⏳ Not collected</span>'
    if r['days_away'] is not None:
        urg = "urgent" if r['days_away']<=7 else ""
        days_cell = f'<div style="margin-top:4px"><span class="days-badge {urg}">{r["days_away"]}d away</span></div>'
    else:
        days_cell = f'<div style="margin-top:4px;font-size:12px;color:{T["sub_color"]}">Past</div>'
    early_note = '<div class="early-eligible">⚡ Fully funded — ready to pay out</div>' if r['early_ok'] else ""
    exit_tag   = '<span class="exit-tag">exited</span>' if r['exited'] else ""
    pay_rows_html += (f'<tr class="plain">'
                      f'<td><span class="cell-name">{r["turn"].replace("Month","Turn")}</span></td>'
                      f'<td>{r["recipient"]}{exit_tag}</td>'
                      f'<td>{r["date"]}{days_cell}</td>'
                      + fee_cell(r) +
                      f'<td>GHS {r["pool"]}{early_note}'
                      f'<div class="pbar-wrap"><div class="pbar-fill" style="width:{bar_pct}%"></div></div></td>'
                      f'<td>GHS {r["collected"]}</td>'
                      f'<td>GHS {r["remaining"]}</td>'
                      f'<td>{status_badge}</td></tr>')

html(f"""<div class="glass-card">
    <div id="section-payouts"></div><p class="sec-label">Rotation</p>
    <p class="sec-title">Payout Schedule</p>
    <p class="sec-sub">Collected = amount the recipient has taken · Remaining = still owed to them</p>
    <table class="data-table tbl-payout {fee_cls}">
        <thead><tr><th>Turn</th><th>Recipient</th><th>Date</th>{fee_col_head}<th>Net Pool</th><th>Collected</th><th>Remaining</th><th>Status</th></tr></thead>
        <tbody>{pay_rows_html}</tbody>
    </table><p class="swipe-hint">Swipe the table sideways for the full breakdown.</p></div>""")

# ── exports ───────────────────────────────────────────────────────────────────
buf = io.StringIO()
buf.write(f"📌 *WK {current_elapsed_week} UPDATE*\n")
buf.write(f"💰 *Cash at Hand:* GHS {fmt_num(total_cash_held)}\n")
buf.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
buf.write("👥 *MEMBERS*\n")
for r in wa_contrib_rows:
    if r["exited"] and "Owing" not in r["standing"]:
        buf.write(f"⚪ *{r['member']}*: Exited\n"); continue
    streak_note = f" · 🔴 {r['streak']}wk streak" if r['streak']>=2 else ""
    buf.write(f"{'✅' if 'Up' in r['standing'] else '❌'} *{r['member']}*: {r['standing']}{streak_note}\n")
buf.write("\n🎁 *PAYOUTS*\n")
for r in wa_payout_rows:
    tag = " ✅ collected" if r['disbursed'] else f" · GHS {r['balance']} still to collect"
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
ob.write("• The admin shares a weekly update in this group chat.\n\n")
ob.write("👤 *MEMBER DETAILS*\n")
for r in contrib_rows:
    if r["exited"]: continue
    ob.write(f"*{r['member']}*\n  • Monthly Tier: GHS {fmt_num(r['m_monthly'])}\n  • Weekly Target: GHS {fmt_num(r['m_weekly'])}\n\n")
ob.write("🎁 *PAYOUT SCHEDULE*\n")
for r in schedule_rows:
    ob.write(f"*{r['turn'].replace('Month','Turn')} — {r['recipient']}*\n  • Payout Date: {r['date']}\n  • Net Pool: GHS {r['pool']}\n\n")

ch = io.StringIO()
ch.write(f"📊 *CONTRIBUTION HISTORY — WK {current_elapsed_week}*\n")
ch.write(f"🗓️ *Period:* {format_date(start_dt)} → {format_date(end_date)}\n\n")
for member in members:
    tag = " (exited)" if exited(member) else ""
    ch.write(f"👤 *{member}*{tag} (GHS {fmt_num(weekly(member))}/wk)\n")
    for w in range(1,total_weeks+1):
        if not liable(member,w) and not paid(member,w):
            ch.write(f"  Wk {w:02d}: ⚪ Exempt\n"); continue
        p     = paid(member,w)
        icon  = "✅" if p else ("⏳" if w>current_elapsed_week else "❌")
        label = "Paid" if p else ("Upcoming" if w>current_elapsed_week else "Owing")
        ch.write(f"  Wk {w:02d}: {icon} {label}\n")
    ch.write("\n")

html(f"""<div class="glass-card">
    <div id="section-exports"></div><p class="sec-label">Export</p>
    <p class="sec-title">WhatsApp Messages</p>
    <p class="sec-sub">Copy and paste into the group chat</p></div>""")
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
    html(f'<p style="font-size:13px;color:{T["sub_color"]}">Payment records are kept when you add or reorder members. To remove someone mid-cycle use Member Status below — deleting the name here shifts every payout date.</p>')
    if st.button("Save Settings", key="save_settings"):
        try: datetime.strptime(new_start,"%Y-%m-%d")
        except ValueError: st.error("Date format must be YYYY-MM-DD."); st.stop()
        changes = []
        if new_start != st.session_state.start_date: changes.append(f"start date {st.session_state.start_date} → {new_start}")
        if float(new_base) != float(st.session_state.base_monthly): changes.append(f"base monthly {fmt_num(st.session_state.base_monthly)} → {fmt_num(new_base)}")
        if float(new_fee) != float(st.session_state.admin_fee_percentage): changes.append(f"admin fee {st.session_state.admin_fee_percentage}% → {new_fee}%")
        if new_names.strip() != st.session_state.names_input.strip(): changes.append("member list edited")
        st.session_state.start_date=new_start; st.session_state.base_monthly=new_base
        st.session_state.admin_fee_percentage=new_fee; st.session_state.names_input=new_names
        def _m(b):
            put_settings(b)
            return {"type":"setting","text":"Group settings updated","detail":changes}
        if commit(gsheet,_m): flash("Settings saved")
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
    html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:8px">Mark a member as exited instead of deleting them. Their history and rotation slot stay intact; they simply stop owing from the exit week onward.</p>')
    ms1,ms2,ms3 = st.columns([2,1,1])
    with ms1: sm = st.selectbox("Member", members, key="status_member", label_visibility="collapsed")
    with ms2: new_status = st.selectbox("Status", ["active","exited"], index=0 if not exited(sm) else 1, key="status_val", label_visibility="collapsed")
    with ms3: new_exit_wk = st.number_input("Exit week", min_value=1, max_value=total_weeks, value=int(mstat(sm).get("exit_week") or max(1,current_elapsed_week)), step=1, key="status_week", label_visibility="collapsed")
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

with st.expander("📝  Bulk Payment Entry"):
    show_all = st.toggle("Show all weeks", value=False, key="show_all_weeks",
                         help="Off = record just the current week (fast on a phone). On = full grid.")
    week_range = list(range(1,total_weeks+1)) if show_all else [current_elapsed_week] if current_elapsed_week>0 else []
    if not week_range:
        st.info("The cycle has not started yet.")
    else:
        html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:4px">Current week: <strong style="color:{T["sec_title"]}">Week {current_elapsed_week}</strong> of {total_weeks}{" · showing this week only" if not show_all else ""}.</p>')
        entered = {}
        if show_all:
            for member in members:
                html(f'<div style="font-size:14px;font-weight:600;color:{T["td_color"]};margin:10px 0 6px">{member}{" (exited)" if exited(member) else ""}</div>')
                cols = st.columns(8)
                vals = {}
                for w in week_range:
                    with cols[(w-1)%8]:
                        if not liable(member,w) and not paid(member,w):
                            html(f'<div style="font-size:13px;color:{T["sub_color"]};padding:6px 0">W{w} —</div>'); continue
                        label = f"W{w}*" if w==current_elapsed_week else f"W{w}"
                        vals[str(w)] = st.checkbox(label, value=paid(member,w), key=f"bulk_{member}_{w}")
                entered[member] = vals
        else:
            w = current_elapsed_week
            cols = st.columns(2)
            for idx,member in enumerate(members):
                with cols[idx%2]:
                    if not liable(member,w) and not paid(member,w):
                        html(f'<div style="font-size:13px;color:{T["sub_color"]};padding:8px 0">{member} — exempt</div>'); entered[member]={}; continue
                    entered[member] = {str(w): st.checkbox(f"{member} · GHS {fmt_num(weekly(member))}", value=paid(member,w), key=f"wk_{member}_{w}")}

        if st.button("Save Payments", key="bulk_save"):
            diffs, unticks = [], []
            for mbr,vals in entered.items():
                for wk,ticked in vals.items():
                    was = paid(mbr,int(wk))
                    if ticked!=was:
                        diffs.append(f"{mbr} Wk {int(wk):02d}: {'unpaid → PAID' if ticked else 'PAID → unpaid'} (GHS {fmt_num(weekly(mbr))})")
                        if was: unticks.append(f"{mbr} — Week {wk}")
            if not diffs:
                flash("No changes to save","info"); st.rerun()
            elif unticks and not st.session_state.get("bulk_confirm_overwrite",False):
                st.warning("⚠️ These weeks will be marked **unpaid** — confirm?\n\n" + "\n".join(f"• {u}" for u in unticks))
                oc1,oc2 = st.columns(2)
                with oc1:
                    if st.button("✓ Confirm save", key="bulk_confirm_yes"):
                        st.session_state.bulk_confirm_overwrite=True; st.rerun()
                with oc2:
                    if st.button("✗ Cancel", key="bulk_confirm_no", type="secondary"): st.rerun()
            else:
                st.session_state.bulk_confirm_overwrite=False
                def _m(b):
                    for mbr,vals in entered.items():
                        b.setdefault("payments",{}).setdefault(mbr,{}).update(vals)
                    held = money(sum(money(b["tiers"].get(m,b["settings"]["base_monthly"])/4.0)
                                     for m in members for w in range(1,total_weeks+1)
                                     if b["payments"].get(m,{}).get(str(w),False)) - total_payouts_dist)
                    b.setdefault("snapshots",{})[str(current_elapsed_week)] = held
                    return {"type":"payment","text":f"Payments updated — {len(diffs)} change(s)","detail":diffs}
                if commit(gsheet,_m): flash(f"{len(diffs)} payment change(s) saved")
                st.rerun()

with st.expander("🎁  Record Payout"):
    month_options = [f"{r['turn'].replace('Month','Turn')} — {r['recipient']}" for r in schedule_rows]
    sel_month_lbl = st.selectbox("Payout Turn", month_options, key="payout_month")
    sr        = schedule_rows[month_options.index(sel_month_lbl)]
    mkey      = sr["turn"]; rec_name = sr["recipient"]
    html(f"""<div style="font-size:14px;color:{T['td_color']};line-height:1.7;margin-bottom:8px">
        Net pool due to {rec_name}: <strong style="color:{T['sec_title']}">GHS {sr['pool']}</strong> &nbsp;·&nbsp;
        Collected so far: <strong style="color:{T['sec_title']}">GHS {sr['collected']}</strong> &nbsp;·&nbsp;
        Still owed: <strong style="color:{T['sec_title']}">GHS {sr['remaining']}</strong><br>
        Contributions banked for this turn: <strong style="color:{T['sec_title']}">GHS {sr['funded_s']}</strong></div>""")
    if sr["funded"] < sr["net_pool_amt"]-0.005 and sr["remaining_v"] > 0:
        st.warning(f"Only GHS {sr['funded_s']} of the GHS {sr['pool']} pool has been contributed so far. Paying the full amount now draws on the group's other cash.")
    pc1,pc2 = st.columns(2)
    with pc1:
        new_amt = st.number_input(f"Total collected by {rec_name} (GHS)", value=float(sr["collected_v"]),
                                  min_value=0.0, max_value=float(sr["net_pool_amt"]), step=50.0, key="payout_amt",
                                  help="Running total, not just today's instalment.")
    with pc2:
        try:    default_dd = datetime.strptime(sr["disb_date"][:11].strip(), "%d %b %Y").date() if sr["disb_date"] else today.date()
        except Exception: default_dd = today.date()
        coll_date = st.date_input("Date collected", value=default_dd, key="payout_date_in")
    # cash effect of this entry: only the *change* in collected leaves the box
    delta_out  = money(new_amt - sr["collected_v"])
    cash_after = money(total_cash_held - delta_out)
    st.caption(f"Balance still owed to {rec_name} after this entry: GHS {fmt_num(money(sr['net_pool_amt']-new_amt))}"
               + (" — fully collected ✅" if new_amt >= sr["net_pool_amt"]-0.005 else "")
               + f" · Group cash after: GHS {fmt_num(cash_after)}")
    overdraw = cash_after < -0.005
    if overdraw:
        st.error(f"❌ The group only holds GHS {fmt_num(total_cash_held)}. Paying out GHS {fmt_num(delta_out)} now would leave it GHS {fmt_num(abs(cash_after))} short. Record the outstanding weekly payments first, or enter a smaller amount.")
        st.session_state.confirm_payout = False
    if not st.session_state.get("confirm_payout",False):
        if st.button("Save Payout", key="save_payout_btn", disabled=overdraw):
            st.session_state.confirm_payout=True; st.rerun()
    else:
        st.warning(f"⚠️ Confirm: {rec_name} ({mkey.replace('Month','Turn')}) has collected GHS {fmt_num(new_amt)} of GHS {sr['pool']} as at {format_date(datetime.combine(coll_date, datetime.min.time()))}?")
        cc1,cc2 = st.columns(2)
        with cc1:
            if st.button("✓ Yes, confirm", key="confirm_yes"):
                def _m(b):
                    ps = b.setdefault("payout_status",{}).setdefault(mkey,{})
                    before = money(ps.get("collected", ps.get("disbursed_amount", ps.get("amount_collected",0.0))))
                    if money(total_cash_held - money(new_amt-before)) < -0.005:
                        raise ValueError("would overdraw the group")
                    ps.pop("amount_collected", None); ps.pop("disbursed_amount", None)
                    full = money(new_amt) >= sr["net_pool_amt"]-0.005 and new_amt>0
                    ps["collected"]      = money(new_amt)
                    ps["disbursed"]      = full
                    ps["disbursed_date"] = format_date(datetime.combine(coll_date, datetime.min.time())) if new_amt>0 else ""
                    detail = [f"{mkey} collected: GHS {fmt_num(before)} → GHS {fmt_num(new_amt)}",
                              f"balance owed to {rec_name}: GHS {fmt_num(money(sr['net_pool_amt']-new_amt))}",
                              f"date: {ps['disbursed_date'] or '—'}"]
                    txt = (f"{mkey} fully collected by {rec_name} — GHS {fmt_num(new_amt)}" if full
                           else f"{mkey} part collected by {rec_name} — GHS {fmt_num(new_amt)} of GHS {sr['pool']}")
                    return {"type":"payout","text":txt,"detail":detail}
                try:
                    ok = commit(gsheet,_m)
                except ValueError:
                    ok = False; flash("Save cancelled — that payout would overdraw the group's cash.","warning")
                st.session_state.confirm_payout=False
                if ok: flash(f"Payout for {rec_name} saved")
                st.rerun()
        with cc2:
            if st.button("✗ Cancel", key="confirm_no", type="secondary"):
                st.session_state.confirm_payout=False; st.rerun()

with st.expander("🔑  Change Passcode"):
    html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:8px">Enter the current passcode to confirm, then set a new one. Passcodes are stored hashed.</p>')
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
            def _m(b):
                b["passcode"] = hash_pw(new_pw1)
                return {"type":"setting","text":"Passcode changed"}
            if commit(gsheet,_m): flash("Passcode updated")
            st.rerun()

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
            log_html += (f'<div class="log-entry"><div class="{dot_class}"></div>'
                         f'<div class="log-text"><strong>{entry.get("text","—")}</strong>'
                         f'{f"<div style=\"font-size:12px\">by {who}</div>" if who else ""}{det_html}</div>'
                         f'<div class="log-time">{entry.get("time","")}</div></div>')
        html(log_html)

html('<div class="gdivider"></div>')
if st.button("🔒  Lock Dashboard", key="logout", type="secondary"):
    st.session_state.authenticated=False; st.session_state.admin_name=ADMIN_NAME; st.rerun()

html('<div class="foot">Backed by Google Sheets · Secured with passcode</div>')
