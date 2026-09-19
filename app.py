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

# ── design tokens ─────────────────────────────────────────────────────────────
# Petrol-ink canvas, brass accent (money), green for settled, clay for behind.
# Keys are kept stable because inline styles elsewhere in the file read from T.
T = {
    "bg":"#141619",
    "card_bg":"#1B1E22","card_border":"rgba(255,255,255,0.10)",
    "card_shadow":"none",
    "chip_bg":"#1B1E22","chip_border":"rgba(255,255,255,0.10)",
    "status_bg":"transparent","status_border":"rgba(255,255,255,0.10)",
    "sync_color":"#767E86","title_color":"#ECEEF0","sub_color":"#A2AAB2",
    "label_color":"#A2AAB2","sec_title":"#ECEEF0","th_color":"#767E86",
    "td_color":"#CFD4D9","td_border":"rgba(255,255,255,0.07)","th_border":"rgba(255,255,255,0.12)",
    "member_name":"#ECEEF0","input_bg":"#23272C","input_border":"rgba(255,255,255,0.13)",
    "input_color":"#ECEEF0","lock_bg":"#1B1E22","lock_border":"rgba(255,255,255,0.12)",
    "lock_title":"#ECEEF0","lock_sub":"#A2AAB2","exp_bg":"#1B1E22",
    "exp_border":"rgba(255,255,255,0.10)","exp_color":"#CFD4D9","exp_content":"#191B1F",
    "gdiv":"rgba(255,255,255,0.14)","foot_color":"#767E86","foot_border":"rgba(255,255,255,0.08)",
    "btn_bg":"#E8B15C","btn_border":"#E8B15C",
    "btn2_bg":"transparent","btn2_color":"#CFD4D9","btn2_border":"rgba(255,255,255,0.14)",
    "dl_bg":"transparent","dl_border":"rgba(232,177,92,0.40)",
    "log_border":"rgba(255,255,255,0.07)","log_color":"#A2AAB2","log_strong":"#ECEEF0","log_time":"#767E86",
    "ring_track":"rgba(255,255,255,0.10)","bar_bg":"rgba(255,255,255,0.10)",
    "streak_bg":"rgba(232,121,90,0.14)","streak_color":"#E8795A","streak_border":"rgba(232,121,90,0.32)",
}

dl_color = "#E8B15C"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Instrument+Serif&display=swap');

    :root{{
      --canvas:#141619; --panel:#1B1E22; --panel-2:#23272C;
      --line:rgba(255,255,255,0.10); --line-soft:rgba(255,255,255,0.06);
      --ink:#ECEEF0; --ink-2:#A2AAB2; --ink-3:#767E86;
      --brass:#E8B15C; --paid:#5BC490; --short:#E8795A;
      --exp-content:#191B1F;
      --r-sm:8px; --r-md:12px; --r-lg:18px;
    }}

    header{{visibility:hidden!important;height:0!important;}} #MainMenu{{visibility:hidden!important;}}
    .stDeployButton{{display:none!important;}} footer{{visibility:hidden!important;}}
    section[data-testid="stSidebar"]{{display:none!important;width:0!important;}}
    [data-testid="collapsedControl"]{{display:none!important;width:0!important;}}
    [data-testid="stSidebarNav"]{{display:none!important;}} button[kind="header"]{{display:none!important;}}
    .block-container{{padding-top:0!important;padding-bottom:3rem!important;max-width:min(1160px,96vw)!important;
        padding-left:clamp(12px,2vw,36px)!important;padding-right:clamp(12px,2vw,36px)!important;}}
    html,body,[class*="css"]{{font-family:'Instrument Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        -webkit-font-smoothing:antialiased;}}
    .main,.stApp{{background:var(--canvas)!important;min-height:100vh;}}
    html{{scroll-behavior:smooth;}}
    *:focus-visible{{outline:2px solid var(--brass);outline-offset:2px;border-radius:4px;}}
    @media (prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important;}}}}

    .num-serif{{font-family:'Instrument Serif',Georgia,serif;font-weight:400;letter-spacing:-0.01em;}}
    .status-dot{{width:6px;height:6px;background:var(--paid);border-radius:50%;display:inline-block;margin-right:8px;
        animation:pulse 2.4s infinite;}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.35}}}}

    /* ── lock screen ──────────────────────────────────────────────────────── */
    .lock-outer{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
        padding:40px 20px;margin-top:-2rem;}}
    .lock-card{{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);
        padding:44px 38px;text-align:left;width:100%;max-width:380px;}}
    .lock-icon{{font-size:34px;margin-bottom:18px;display:block;}}
    .lock-title{{font-family:'Instrument Serif',Georgia,serif;font-size:32px;color:var(--ink);
        margin-bottom:8px;line-height:1.1;}}
    .lock-sub{{font-size:14px;color:var(--ink-2);margin:0;line-height:1.5;}}

    /* ── top bar ──────────────────────────────────────────────────────────── */
    .topbar{{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:13px;
        color:var(--ink-2);border-bottom:1px solid var(--line-soft);padding:14px 2px 12px;}}
    .topbar b{{color:var(--ink);font-weight:600;}}
    .topbar-right{{color:var(--ink-3);}}
    .block-container div[data-testid="stHorizontalBlock"]:first-of-type{{align-items:center;gap:8px;}}

    /* ── page head ────────────────────────────────────────────────────────── */
    .pagehead{{padding:26px 2px 20px;}}
    .pagehead h1{{font-family:'Instrument Serif',Georgia,serif;font-size:38px;font-weight:400;color:var(--ink);
        margin:0 0 8px;line-height:1.08;letter-spacing:-0.015em;}}
    .pagehead p{{font-size:14px;color:var(--ink-2);margin:0;line-height:1.55;}}
    .pagehead p b{{color:var(--ink);font-weight:600;}}

    /* ── hero: cash + next payout ─────────────────────────────────────────── */
    .hero{{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;margin-bottom:14px;align-items:stretch;}}
    .panel{{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);padding:22px 24px;
        display:flex;flex-direction:column;min-width:0;}}
    .panel-label{{font-size:13px;color:var(--ink-2);margin:0 0 10px;}}
    .cash-figure{{font-family:'Instrument Serif',Georgia,serif;font-size:52px;line-height:1;color:var(--ink);
        letter-spacing:-0.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .cash-figure small{{font-size:22px;color:var(--ink-2);margin-right:8px;letter-spacing:0;}}
    .cash-spacer{{margin-top:auto;}}
    .cash-note{{font-size:13px;color:var(--ink-2);margin-top:10px;line-height:1.5;}}
    .cash-note b{{color:var(--ink);font-weight:600;}}

    .split{{display:flex;height:8px;border-radius:99px;overflow:hidden;background:var(--line-soft);margin:16px 0 10px;}}
    .split i{{display:block;height:100%;}}
    .split .seg-held{{background:var(--paid);}}
    .split .seg-out{{background:rgba(232,177,92,0.55);}}
    .legend{{display:flex;flex-wrap:wrap;gap:16px;font-size:12.5px;color:var(--ink-2);}}
    .legend span{{display:inline-flex;align-items:center;gap:7px;}}
    .legend i{{width:8px;height:8px;border-radius:2px;display:inline-block;}}
    .cash-foot{{margin-top:14px;padding-top:14px;border-top:1px solid var(--line-soft);display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;
        font-size:12.5px;color:var(--ink-2);}}
    .recon-ok{{color:var(--paid);}} .recon-off{{color:var(--brass);}}
    .spark{{width:100%;height:46px;display:block;overflow:visible;margin-top:auto;padding-top:18px;}}

    .next-name{{font-family:'Instrument Serif',Georgia,serif;font-size:34px;color:var(--ink);line-height:1.1;
        letter-spacing:-0.015em;margin-bottom:4px;}}
    .next-when{{font-size:13.5px;color:var(--ink-2);margin-bottom:18px;}}
    .next-amount{{font-size:22px;font-weight:600;color:var(--ink);font-variant-numeric:tabular-nums;}}
    .chip{{font-size:12px;font-weight:600;color:var(--ink-2);border:1px solid var(--line);border-radius:99px;
        padding:3px 11px;white-space:nowrap;}}
    .chip-soon{{color:var(--brass);border-color:rgba(232,177,92,0.40);background:rgba(232,177,92,0.10);}}
    .chip-clear{{color:var(--paid);border-color:rgba(91,196,144,0.35);background:rgba(91,196,144,0.10);}}
    .panel-top{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;}}
    .fund-row{{display:flex;justify-content:space-between;align-items:baseline;font-size:13px;color:var(--ink-2);
        margin-top:auto;padding-top:16px;}}
    .meter{{height:6px;border-radius:99px;background:var(--line-soft);overflow:hidden;margin-top:8px;}}
    .meter i{{display:block;height:100%;background:var(--brass);border-radius:99px;}}
    .meter.green i{{background:var(--paid);}}
    .fund-note{{font-size:12.5px;color:var(--ink-3);margin-top:8px;line-height:1.45;}}

    /* ── rotation rail ────────────────────────────────────────────────────── */
    .rail-wrap{{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);
        padding:20px 24px 20px;margin-bottom:26px;}}
    .rail{{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch;}}
    .turn{{flex:1 0 132px;min-width:132px;border-top:2px solid var(--line);padding-top:12px;
        display:flex;flex-direction:column;}}
    .turn.done{{border-top-color:var(--paid);}}
    .turn.now{{border-top-color:var(--brass);}}
    .turn-no{{font-size:12px;color:var(--ink-3);margin-bottom:5px;}}
    .turn-name{{font-size:15px;font-weight:600;color:var(--ink);margin-bottom:3px;}}
    .turn.upcoming .turn-name{{color:var(--ink-2);font-weight:500;}}
    .turn-date{{font-size:12.5px;color:var(--ink-3);}}
    .turn-state{{font-size:12.5px;margin-top:6px;margin-bottom:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .turn-meter{{height:4px;border-radius:99px;background:var(--line-soft);margin-top:auto;overflow:hidden;
        margin-bottom:0;}}
    .turn-meter i{{display:block;height:100%;border-radius:99px;background:var(--ink-3);}}
    .turn.done .turn-meter i{{background:var(--paid);}}
    .turn.now .turn-meter i{{background:var(--brass);}}
    .turn.done .turn-state{{color:var(--paid);}}
    .turn.now .turn-state{{color:var(--brass);}}
    .turn.upcoming .turn-state{{color:var(--ink-3);}}

    /* ── section frame ────────────────────────────────────────────────────── */
    .section{{margin-bottom:28px;}}
    .section-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;
        padding-bottom:12px;border-bottom:1px solid var(--line);margin-bottom:4px;}}
    .section-head h2{{font-size:19px;font-weight:600;color:var(--ink);margin:0 0 4px;letter-spacing:-0.01em;}}
    .section-head p{{font-size:13px;color:var(--ink-2);margin:0;line-height:1.5;}}
    .section-head p b{{color:var(--ink);font-weight:600;}}
    .quiet-link{{font-size:13px;font-weight:600;color:var(--brass)!important;text-decoration:none!important;
        white-space:nowrap;border-bottom:1px solid rgba(232,177,92,0.35);padding-bottom:1px;}}

    /* ── member rows with contribution cards ──────────────────────────────── */
    .mrow{{display:grid;grid-template-columns:minmax(130px,0.6fr) minmax(220px,2fr) minmax(96px,auto);gap:20px;
        align-items:center;padding:14px 2px;border-bottom:1px solid var(--line-soft);}}
    .mrow:last-child{{border-bottom:none;}}
    .mname{{font-size:15px;font-weight:600;color:var(--ink);display:flex;align-items:center;gap:9px;}}
    .mmeta{{font-size:12.5px;color:var(--ink-3);margin-top:3px;}}
    .member-avatar{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
        border-radius:50%;background:rgba(232,177,92,0.14);color:var(--brass);font-size:12px;font-weight:600;
        flex-shrink:0;}}
    .strip{{display:grid;gap:3px;min-width:0;}}
    .wk{{height:17px;border-radius:3px;background:rgba(255,255,255,0.055);}}
    .wk-paid{{background:var(--paid);}}
    .wk-part{{background:rgba(91,196,144,0.42);}}
    .wk-owed{{background:rgba(232,121,90,0.10);box-shadow:inset 0 0 0 1px rgba(232,121,90,0.55);}}
    .wk-exempt{{background:transparent;box-shadow:inset 0 0 0 1px var(--line-soft);}}
    .wk-turnend{{margin-right:6px;}}
    .wk-now{{outline:1.5px solid var(--brass);outline-offset:1.5px;}}
    .key{{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:12.5px;color:var(--ink-3);margin:12px 0 2px;}}
    .key span{{display:inline-flex;align-items:center;gap:7px;}}
    .key i{{width:13px;height:13px;border-radius:3px;display:inline-block;}}
    .scale{{display:grid;gap:3px;min-width:0;}}
    .scale span{{font-size:11.5px;color:var(--ink-3);border-left:1px solid var(--line);padding-left:6px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .scale span.on{{color:var(--brass);border-left-color:rgba(232,177,92,0.55);}}
    .mrow-head{{padding-bottom:8px;border-bottom:1px solid var(--line);}}
    .mstat{{display:flex;flex-direction:column;align-items:flex-end;gap:6px;text-align:right;}}
    .exit-tag{{font-size:11.5px;color:var(--ink-3);font-weight:500;margin-left:7px;}}

    .badge-ok{{color:var(--paid);font-size:13px;font-weight:600;white-space:nowrap;}}
    .badge-owe{{color:var(--short);font-size:13px;font-weight:600;white-space:nowrap;
        font-variant-numeric:tabular-nums;}}
    .badge-pending{{color:var(--ink-3);font-size:13px;font-weight:500;white-space:nowrap;}}
    .badge-exempt{{color:var(--ink-3);font-size:13px;font-weight:500;white-space:nowrap;}}
    .streak-badge{{background:{T['streak_bg']};color:{T['streak_color']};border:1px solid {T['streak_border']};
        border-radius:99px;padding:1px 8px;font-size:11.5px;font-weight:600;white-space:nowrap;}}

    .owing-strip{{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;padding:14px 18px;
        font-size:13.5px;color:var(--ink-2);border-radius:var(--r-md);margin:16px 0 6px;
        background:rgba(232,121,90,0.09);border:1px solid rgba(232,121,90,0.26);}}
    .owing-strip b{{color:var(--short);font-weight:600;font-size:18px;font-variant-numeric:tabular-nums;}}
    .owing-clear{{background:rgba(91,196,144,0.06);border-color:rgba(91,196,144,0.20);}}

    /* ── tables ───────────────────────────────────────────────────────────── */
    .data-table{{width:100%;border-collapse:collapse;}}
    .data-table th{{font-size:12.5px;font-weight:500;color:var(--ink-3);padding:12px 12px 10px;
        border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;}}
    .data-table td{{font-size:14.5px;color:{T['td_color']};padding:13px 12px;border-bottom:1px solid var(--line-soft);
        vertical-align:middle;font-variant-numeric:tabular-nums;}}
    .data-table tr:last-child td{{border-bottom:none;}}
    .data-table .num,.data-table th.num{{text-align:right;}}
    .cell-name{{font-weight:600;color:var(--ink);}}
    .cell-sub{{font-size:12px;color:var(--ink-3);margin-top:3px;}}
    .num .cell-sub{{text-align:right;}}
    .days-badge{{display:inline-block;color:var(--ink-3);font-size:12px;margin-top:3px;}}
    .days-badge.urgent{{color:var(--brass);}}
    .diff-line{{font-size:12.5px;color:var(--ink-2);}}
    .pbar-wrap{{margin-top:7px;background:var(--line-soft);border-radius:99px;height:4px;overflow:hidden;}}
    .pbar-fill{{height:4px;border-radius:99px;background:var(--paid);}}
    .early-eligible{{font-size:12px;color:var(--paid);margin-top:4px;text-align:right;}}

    /* ── activity log ─────────────────────────────────────────────────────── */
    .log-entry{{display:flex;align-items:flex-start;gap:12px;padding:11px 0;border-bottom:1px solid var(--line-soft);}}
    .log-entry:last-child{{border-bottom:none;}}
    .log-dot{{width:6px;height:6px;border-radius:50%;background:var(--brass);margin-top:7px;flex-shrink:0;}}
    .log-dot-payout{{background:var(--ink-2);}} .log-dot-setting{{background:var(--paid);}}
    .log-text{{font-size:14px;color:{T['log_color']};line-height:1.5;}}
    .log-text strong{{color:var(--ink);font-weight:600;}}
    .log-time{{font-size:12px;color:var(--ink-3);margin-left:auto;white-space:nowrap;padding-left:12px;}}

    .sec-label{{font-size:13px;color:var(--ink-2);margin-bottom:4px;}}
    .sec-title{{font-size:19px;font-weight:600;color:var(--ink);margin:0 0 4px;letter-spacing:-0.01em;}}
    .sec-sub{{font-size:13px;color:var(--ink-2);margin:0 0 12px;line-height:1.5;}}

    /* ── Streamlit controls ───────────────────────────────────────────────── */
    .stTextInput input,.stNumberInput input,.stTextArea textarea{{background:var(--panel-2)!important;
        border:1px solid var(--line)!important;color:var(--ink)!important;border-radius:var(--r-sm)!important;
        font-size:15px!important;}}
    .stTextInput input:focus,.stNumberInput input:focus,.stTextArea textarea:focus{{
        border-color:rgba(232,177,92,0.55)!important;box-shadow:0 0 0 3px rgba(232,177,92,0.12)!important;}}
    .stTextInput label,.stNumberInput label,.stTextArea label,.stSelectbox label,.stDateInput label,
    .stCheckbox label{{color:var(--ink-2)!important;font-size:13px!important;font-weight:500!important;
        text-transform:none!important;letter-spacing:0!important;}}
    .stSelectbox > div > div,.stDateInput > div > div{{background:var(--panel-2)!important;
        border:1px solid var(--line)!important;color:var(--ink)!important;border-radius:var(--r-sm)!important;}}
    div[data-testid="stButton"]{{width:100%!important;}}
    .block-container div[data-testid="stHorizontalBlock"]:first-of-type button{{padding:9px 0!important;
        font-size:16px!important;}}
    .stButton > button{{background:var(--brass)!important;color:#17191C!important;border:1px solid var(--brass)!important;
        border-radius:var(--r-sm)!important;font-weight:600!important;font-size:15px!important;padding:10px 20px!important;
        width:100%;box-shadow:none!important;transition:filter 0.15s ease!important;}}
    .stButton > button:hover{{filter:brightness(1.08);}}
    .stButton > button[kind="secondary"]{{background:transparent!important;color:var(--ink-2)!important;
        border:1px solid var(--line)!important;}}
    .stButton > button[kind="secondary"]:hover{{color:var(--ink)!important;border-color:var(--ink-3)!important;
        filter:none;}}
    div[data-testid="stDownloadButton"],.stDownloadButton{{width:100%!important;}}
    div[data-testid="stDownloadButton"] > button,.stDownloadButton > button{{background:transparent!important;
        color:{dl_color}!important;border:1px solid {T['dl_border']}!important;border-radius:var(--r-sm)!important;
        font-size:15px!important;font-weight:600!important;padding:10px 20px!important;width:100%!important;}}
    div[data-testid="stDownloadButton"] > button:hover{{background:rgba(232,177,92,0.08)!important;}}
    details[data-testid="stExpander"]{{background:var(--panel)!important;border:1px solid var(--line)!important;
        border-radius:var(--r-md)!important;margin-bottom:10px!important;overflow:hidden;}}
    details[data-testid="stExpander"] summary{{background:transparent!important;padding:14px 18px!important;}}
    details[data-testid="stExpander"] summary,details[data-testid="stExpander"] summary *{{color:var(--ink)!important;
        font-size:15px!important;font-weight:600!important;}}
    details[data-testid="stExpander"] summary:hover{{color:{dl_color}!important;}}
    details[data-testid="stExpander"] summary svg{{fill:var(--ink-2)!important;color:var(--ink-2)!important;}}
    details[data-testid="stExpander"] > div:not(summary){{background:var(--exp-content,#191B1F)!important;
        border-top:1px solid var(--line)!important;padding:20px 18px!important;}}
    details[data-testid="stExpander"] p,details[data-testid="stExpander"] label,
    details[data-testid="stExpander"] .stCheckbox span{{color:{T['td_color']};}}
    div[data-testid="stSuccess"]{{background:rgba(91,196,144,0.08)!important;border:1px solid rgba(91,196,144,0.28)!important;
        border-radius:var(--r-sm)!important;color:var(--paid)!important;font-size:14px!important;}}
    div[data-testid="stError"]{{background:rgba(232,121,90,0.08)!important;border:1px solid rgba(232,121,90,0.28)!important;
        border-radius:var(--r-sm)!important;color:var(--short)!important;font-size:14px!important;}}
    div[data-testid="stWarning"]{{background:rgba(232,177,92,0.08)!important;border:1px solid rgba(232,177,92,0.30)!important;
        border-radius:var(--r-sm)!important;color:var(--brass)!important;font-size:14px!important;}}
    div[data-testid="stInfo"]{{background:rgba(255,255,255,0.05)!important;border:1px solid var(--line)!important;
        border-radius:var(--r-sm)!important;color:var(--ink-2)!important;font-size:14px!important;}}
    div[data-testid="stMetricValue"]{{color:var(--ink)!important;font-size:24px!important;}}
    div[data-testid="stMetricLabel"] p{{color:var(--ink-2)!important;font-size:13px!important;}}
    .stTabs [data-baseweb="tab-list"]{{gap:4px;background:transparent;border-bottom:1px solid var(--line);}}
    .stTabs [data-baseweb="tab"]{{background:transparent;border:none;border-radius:0;padding:10px 4px;margin-right:18px;
        color:var(--ink-2);font-size:14px;font-weight:500;}}
    .stTabs [aria-selected="true"]{{color:var(--ink)!important;box-shadow:inset 0 -2px 0 var(--brass);font-weight:600;}}
    .stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{{display:none;}}
    div[data-testid="stCode"] pre,div[data-testid="stCodeBlock"] pre{{background:var(--panel-2)!important;
        border:1px solid var(--line)!important;border-radius:var(--r-md)!important;font-size:13.5px!important;
        line-height:1.6!important;}}
    div[data-testid="stCode"] code,div[data-testid="stCodeBlock"] code{{color:{T['td_color']}!important;
        white-space:pre-wrap!important;}}
    hr{{border-color:var(--line-soft)!important;}}
    .copy-hint{{font-size:13px;color:var(--ink-2);margin:-4px 0 8px;}}
    .gdivider{{height:1px;background:var(--line-soft);margin:30px 0 20px;}}
    .foot{{text-align:center;font-size:12.5px;color:var(--ink-3);margin-top:28px;padding-top:20px;
        border-top:1px solid var(--line-soft);}}
    .anchor{{position:relative;top:-70px;display:block;height:0;}}
    .swipe-hint{{display:none;font-size:12.5px;color:var(--ink-3);margin:8px 0 0;}}

    /* ── responsive ───────────────────────────────────────────────────────── */
    @media (max-width:900px){{
        .hero{{grid-template-columns:1fr;}}
    }}
    @media (max-width:700px){{
        .mrow{{grid-template-columns:1fr auto;gap:12px;padding:16px 2px;}}
        .mstat{{grid-row:1;grid-column:2;}}
        .strip,.scale{{grid-row:2;grid-column:1 / -1;}}
    }}
    @media (max-width:600px){{
        .block-container{{padding-left:12px!important;padding-right:12px!important;}}
        .topbar{{font-size:12px;flex-wrap:wrap;gap:4px;padding-top:12px;}}
        .pagehead{{padding:20px 2px 16px;}}
        .pagehead h1{{font-size:29px;}}
        .pagehead p{{font-size:13px;}}
        .panel{{padding:18px 16px;}}
        .cash-figure{{font-size:40px;}} .cash-figure small{{font-size:18px;}}
        .next-name{{font-size:27px;}}
        .rail-wrap{{padding:16px 16px 18px;}}
        .turn{{flex:0 0 118px;min-width:118px;}}
        .section-head h2{{font-size:17px;}}
        .wk{{height:15px;}}
        .scale-date{{display:none;}}
        .scale span{{padding-left:5px;}}
        .key{{gap:6px 14px;}}
        .data-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;}}
        .data-table th,.data-table td{{padding:10px 10px!important;font-size:13.5px!important;}}
        .tbl-payout.has-fee th:nth-child(4),.tbl-payout.has-fee td:nth-child(4),
        .tbl-payout.has-fee th:nth-child(6),.tbl-payout.has-fee td:nth-child(6),
        .tbl-payout.no-fee th:nth-child(5),.tbl-payout.no-fee td:nth-child(5){{display:none;}}
        .swipe-hint{{display:block!important;}}
    }}
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

def format_short(dt):
    return f"{dt.day} {dt.strftime('%b')}"

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
    html('<p class="copy-hint">Tap the copy icon at the top right of the box, then paste into WhatsApp.</p>')
    st.code(text, language=None)
    st.download_button("Download as .txt", data=text, file_name=fname, mime="text/plain", key=key,
                       use_container_width=True)


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

BACKUP_WS    = "susu_backups"
BACKUP_KEEP  = 30

def write_backup(sheet, blob):
    """Append a timestamped copy of the blob and keep the last BACKUP_KEEP rows.
    Best-effort: a backup failure must never block the actual save."""
    try:
        ws = ensure_ws(sheet, BACKUP_WS)
        ws.append_row([now_str(), blob.get("rev",0), json.dumps(blob)], value_input_option="RAW")
        rows = len(ws.col_values(1))
        if rows > BACKUP_KEEP:
            ws.delete_rows(1, rows-BACKUP_KEEP)
    except Exception:
        pass

def write_blob(sheet, blob):
    ensure_ws(sheet, DATA_WS).update("A1", [[json.dumps(blob)]])
    write_backup(sheet, blob)
    read_blob_cached.clear()

def list_backups(sheet):
    """[(row_number, when, rev)] newest first — content is fetched on demand."""
    try:
        ws   = ensure_ws(sheet, BACKUP_WS)
        vals = ws.get_all_values()
        return [(i+1, r[0], r[1]) for i,r in enumerate(vals) if len(r) >= 3][::-1]
    except Exception:
        return []

def read_backup(sheet, row_no):
    try:
        raw = ensure_ws(sheet, BACKUP_WS).cell(row_no, 3).value
        return json.loads(raw) if raw else None
    except Exception:
        return None

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
            <div class="lock-sub">Enter your name and the group passcode. Every change you make is signed with your name.</div>
        </div>
    </div>""")
    col_l,col_c,col_r = st.columns([1,2,1])
    with col_c:
        who = st.text_input("n", value=ADMIN_NAME, label_visibility="collapsed", placeholder="Your name")
        pw  = st.text_input("p", type="password", label_visibility="collapsed", placeholder="Passcode")
        if st.button("Unlock"):
            stored = st.session_state.get("admin_passcode", "")
            if not stored and not BOOTSTRAP_ADMIN_PW:
                st.error("No admin passcode is configured. Add app.admin_passcode to Streamlit secrets first.")
                st.stop()
            if not stored and BOOTSTRAP_ADMIN_PW:
                stored = BOOTSTRAP_ADMIN_PW
            if not who.strip():
                st.error("Enter your name — every change is recorded against it.")
            elif check_pw(pw, stored):
                st.session_state.admin_name    = who.strip()[:40]
                st.session_state.authenticated = True
                st.session_state.last_activity = now_dt()
                # Upgrade plaintext or legacy SHA-256 storage to salted scrypt.
                if not is_scrypt_hash(st.session_state.get("admin_passcode", "")):
                    commit(gsheet, lambda b: (b.__setitem__("passcode", hash_pw(pw)), None)[1])
                st.rerun()
            else:
                st.error("That passcode is not correct.")
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
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
sync_ago = int((now_dt()-st.session_state.last_sync).total_seconds()/60)
sync_txt = "just now" if sync_ago < 1 else f"{sync_ago} min ago"

owing_rows = [r for r in contrib_rows if r["owing"] > 0]
next_turn  = next((r for r in schedule_rows if not r["disbursed"]), None)
funded_pct = int(min(next_turn["funded"]/next_turn["net_pool_amt"], 1)*100) if next_turn and next_turn["net_pool_amt"] else 100

# last cash count
last_recon = (st.session_state.get("reconciliations") or [None])[0]
if last_recon:
    _rd   = parse_display_date(last_recon.get("date","")[:12])
    _days = (today.date()-_rd).days if _rd else None
    _when = ("today" if _days == 0 else f"{_days} days ago") if _days is not None else last_recon.get("date","")
    _diff = money(last_recon.get("difference",0))
    if abs(_diff) < 0.005:
        recon_line = f'<span class="recon-ok">Counted {_when}, matched exactly</span>'
    else:
        _word = "over" if _diff > 0 else "short"
        recon_line = f'<span class="recon-off">Last count was GHS {fmt_num(abs(_diff))} {_word}, {_when}</span>'
else:
    recon_line = '<span class="recon-off">Cash has never been counted against this balance</span>'

# week-on-week movement
prev_snap = st.session_state.get("snapshots", {}).get(str(current_elapsed_week-1))
if prev_snap is not None and current_elapsed_week > 1:
    snap_delta  = money(total_cash_held - float(prev_snap))
    delta_color = "var(--paid)" if snap_delta >= 0 else "var(--short)"
    delta_word  = "up" if snap_delta >= 0 else "down"
    delta_html  = (f'<span style="color:{delta_color};font-weight:600">{delta_word} GHS {fmt_num(abs(snap_delta))}</span>'
                   f' since last week')
else:
    delta_html = "First week on record"

# cash trend — last 8 weekly snapshots, current week included
snaps_all = dict(st.session_state.get("snapshots", {}) or {})
snaps_all[str(current_elapsed_week)] = total_cash_held
hist = [(int(w), money(v)) for w, v in snaps_all.items() if str(w).isdigit() and int(w) <= current_elapsed_week]
hist.sort()
hist = hist[-8:]
if len(hist) >= 2:
    vals   = [v for _, v in hist]
    lo, hi = min(vals), max(vals)
    span   = (hi-lo) or 1
    w_px, h_px = 300, 46
    step   = w_px/(len(vals)-1)
    pts    = " ".join(f"{i*step:.1f},{h_px-2-((v-lo)/span)*(h_px-6):.1f}" for i, v in enumerate(vals))
    last_x = (len(vals)-1)*step
    last_y = h_px-2-((vals[-1]-lo)/span)*(h_px-6)
    spark_html = (f'<svg class="spark" viewBox="0 0 {w_px} {h_px}" preserveAspectRatio="none" aria-hidden="true">'
                  f'<polyline points="{pts}" fill="none" stroke="rgba(232,177,92,0.85)" stroke-width="1.6" '
                  f'stroke-linecap="round" stroke-linejoin="round"/>'
                  f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.6" fill="#5BC490"/></svg>')
else:
    spark_html = ""

# ── top bar ───────────────────────────────────────────────────────────────────
sb1, sb2 = st.columns([6,1])
with sb1:
    html(f"""<div class="topbar">
      <div><span class="status-dot"></span><b>Live</b> &nbsp;Synced {sync_txt}</div>
      <div class="topbar-right">Signed in as {st.session_state.admin_name}, revision {st.session_state.rev}</div>
    </div>""")
with sb2:
    if st.button("Refresh", key="refresh_btn", type="secondary", help="Reload from Google Sheets"):
        reload_state(gsheet, fresh=True); flash("Refreshed from Google Sheets"); st.rerun()

html(f"""
<div class="pagehead">
  <h1>{greeting()}, {st.session_state.admin_name}</h1>
  <p>Week <b>{current_elapsed_week}</b> of {total_weeks} with {num_members} members. The cycle runs
     {format_date(start_dt)} to {format_date(end_date)}.</p>
</div>
""")

# ── cash in hand + next payout ────────────────────────────────────────────────
if total_cash_collected > 0:
    held_pct = max(0, min(100, int(total_cash_held/total_cash_collected*100)))
else:
    held_pct = 0
out_pct = 100-held_pct

cash_panel = f"""
<div class="panel">
  <p class="panel-label">Cash in hand</p>
  <div class="cash-figure"><small>GHS</small>{fmt_num(total_cash_held)}</div>
  <div class="split">
    <i class="seg-held" style="width:{held_pct}%"></i><i class="seg-out" style="width:{out_pct}%"></i>
  </div>
  <div class="legend">
    <span><i style="background:var(--paid)"></i>Held GHS {fmt_num(total_cash_held)}</span>
    <span><i style="background:rgba(232,177,92,0.55)"></i>Paid out GHS {fmt_num(total_payouts_dist)}</span>
    <span>Collected GHS {fmt_num(total_cash_collected)}</span>
  </div>
  {spark_html or '<div class="cash-spacer"></div>'}
  <div class="cash-foot">
    <span>{delta_html}</span>
    <span>{recon_line}</span>
  </div>
</div>
"""

if next_turn:
    gap_to_fund = money(max(0.0, next_turn["net_pool_amt"] - next_turn["funded"]))
    if gap_to_fund <= 0:
        fund_note = f"GHS {next_turn['funded_s']} banked — the full pool is ready to pay"
    elif next_turn["days_away"] is None or next_turn["days_away"] <= 0:
        fund_note = (f"GHS {next_turn['funded_s']} banked, GHS {fmt_num(gap_to_fund)} short with the date already here")
    else:
        weeks_left = max(1, -(-next_turn["days_away"]//7))
        rate       = money(gap_to_fund/weeks_left)
        fund_note  = (f"GHS {fmt_num(gap_to_fund)} short. Collecting GHS {fmt_num(rate)} a week for the next "
                      f"{weeks_left} week{'s' if weeks_left > 1 else ''} closes it in time.")
    if next_turn["days_away"] is None:
        days_label, chip_cls = "past due", "chip-soon"
    elif next_turn["days_away"] == 0:
        days_label, chip_cls = "today", "chip-soon"
    else:
        days_label = f"in {next_turn['days_away']} days"
        chip_cls   = "chip-soon" if next_turn["days_away"] <= 7 else ""
    next_panel = f"""
    <div class="panel">
      <div class="panel-top"><p class="panel-label" style="margin:0">Next payout</p>
        <span class="chip {chip_cls}">{days_label}</span></div>
      <div class="next-name">{next_turn['recipient']}</div>
      <div class="next-when">{next_turn['date']}, closing {next_turn['turn'].lower()}</div>
      <div class="next-amount">GHS {next_turn['pool']}</div>
      <div class="fund-row"><span>Pool funded</span><b style="color:var(--ink)">{funded_pct}%</b></div>
      <div class="meter{' green' if funded_pct >= 100 else ''}"><i style="width:{funded_pct}%"></i></div>
      <div class="fund-note">{fund_note}</div>
    </div>
    """
else:
    next_panel = """
    <div class="panel">
      <div class="panel-top"><p class="panel-label" style="margin:0">Rotation</p>
        <span class="chip chip-clear">complete</span></div>
      <div class="next-name">Everyone has been paid</div>
      <div class="next-when">Every turn in this cycle has been collected in full.</div>
    </div>
    """

html(f'<div class="hero">{cash_panel}{next_panel}</div>')

# ── rotation rail ─────────────────────────────────────────────────────────────
rail = ""
for r in schedule_rows:
    pct = int(min(r["funded"]/r["net_pool_amt"], 1)*100) if r["net_pool_amt"] else 0
    if r["disbursed"]:
        cls, state, bar = "done", "Collected in full", 100
    elif r is next_turn:
        cls, bar = "now", pct
        state = (f"GHS {r['remaining']} still to collect" if r["collected_v"] > 0
                 else f"{pct}% of GHS {r['pool']}")
    else:
        cls, bar = "upcoming", pct
        state = (f"{pct}% of GHS {r['pool']}" if r["funded"] > 0 else f"GHS {r['pool']} to raise")
    rail += (f'<div class="turn {cls}"><div class="turn-no">{r["turn"]}</div>'
             f'<div class="turn-name">{r["recipient"]}</div>'
             f'<div class="turn-date">{format_short(r["payout_date"])}</div>'
             f'<div class="turn-state">{state}</div>'
             f'<div class="turn-meter"><i style="width:{bar}%"></i></div></div>')

turns_done = sum(1 for r in schedule_rows if r["disbursed"])
html(f"""
<div class="rail-wrap">
  <div class="section-head" style="border:none;padding-bottom:0;margin-bottom:16px">
    <div><h2>The rotation</h2>
      <p>{turns_done} of {num_members} turns collected. Each turn runs four weeks and the order never shifts.</p></div>
  </div>
  <div class="rail">{rail}</div>
</div>
""")

# ── members and their contribution cards ──────────────────────────────────────
def week_cell(m, w):
    amt   = paid_amount(m, w)
    tgt   = weekly(m)
    extra = " wk-turnend" if w % 4 == 0 and w != total_weeks else ""
    extra += " wk-now" if w == current_elapsed_week else ""
    if not liable(m, w) and amt <= 0:
        return f'<i class="wk wk-exempt{extra}" title="Week {w}: not owed"></i>'
    if amt >= tgt-0.005:
        return f'<i class="wk wk-paid{extra}" title="Week {w}: paid GHS {fmt_num(amt)}"></i>'
    if amt > 0:
        return f'<i class="wk wk-part{extra}" title="Week {w}: part paid, GHS {fmt_num(amt)} of {fmt_num(tgt)}"></i>'
    if w <= current_elapsed_week:
        return f'<i class="wk wk-owed{extra}" title="Week {w}: not paid"></i>'
    return f'<i class="wk{extra}" title="Week {w}: not due yet"></i>'

rows_html = ""
for r in contrib_rows:
    m = r["member"]
    if r["owing"] > 0:
        status = f'<span class="badge-owe">GHS {fmt_num(r["owing"])}</span>'
    elif r["exited"]:
        status = '<span class="badge-exempt">Left the group</span>'
    else:
        status = '<span class="badge-ok">Up to date</span>'
    streak_html = f'<span class="streak-badge">{r["streak"]} weeks behind</span>' if r["streak"] >= 2 else ""
    exit_tag    = f'<span class="exit-tag">left week {r["exit_week"]}</span>' if r["exited"] and r["exit_week"] else ""
    ahead       = r["total_paid"] - r["paid_due"]
    meta        = f'GHS {fmt_num(r["m_weekly"])} a week'
    if ahead > 0: meta += f', {ahead} week{"s" if ahead > 1 else ""} ahead'
    strip = "".join(week_cell(m, w) for w in range(1, total_weeks+1))
    rows_html += (
        f'<div class="mrow">'
        f'<div><div class="mname"><span class="member-avatar">{m[0].upper()}</span>{m}{exit_tag}</div>'
        f'<div class="mmeta">{meta}</div></div>'
        f'<div class="strip" style="grid-template-columns:repeat({total_weeks},1fr)">{strip}</div>'
        f'<div class="mstat">{status}{streak_html}</div>'
        f'</div>'
    )

if owing_rows:
    names = ", ".join(f"{r['member']} GHS {fmt_num(r['owing'])}" for r in owing_rows[:4])
    if len(owing_rows) > 4:
        names += f" and {len(owing_rows)-4} more"
    owing_strip = (f'<div class="owing-strip"><b>GHS {fmt_num(collection_gap)}</b> outstanding to the end of week '
                   f'{current_elapsed_week} — {names}.</div>')
else:
    owing_strip = (f'<div class="owing-strip owing-clear">Nothing outstanding. Everyone has paid up to week '
                   f'{current_elapsed_week}.</div>')
if paid_ahead > 0:
    owing_strip = owing_strip[:-6] + f'<span>GHS {fmt_num(paid_ahead)} has been paid ahead.</span></div>'

key_row = ('<div class="key">'
           '<span><i style="background:var(--paid)"></i>Paid in full</span>'
           '<span><i style="background:rgba(91,196,144,0.42)"></i>Part paid</span>'
           '<span><i style="background:rgba(232,121,90,0.10);box-shadow:inset 0 0 0 1px rgba(232,121,90,0.55)"></i>Owed</span>'
           '<span><i style="background:rgba(255,255,255,0.055)"></i>Not due yet</span>'
           '<span><i style="box-shadow:inset 0 0 0 1px rgba(255,255,255,0.10)"></i>Not owed</span>'
           '<span><i style="outline:1.5px solid var(--brass);outline-offset:1px"></i>This week</span>'
           '</div>')

cur_turn_idx = (current_elapsed_week-1)//4 if current_elapsed_week else -1
scale = "".join(
    f'<span class="{"on" if i == cur_turn_idx else ""}">T{i+1}'
    f'<span class="scale-date"> pays {format_short(schedule_rows[i]["payout_date"])}</span></span>'
    for i in range(num_members))
scale_row = (f'<div class="mrow mrow-head"><div></div>'
             f'<div class="scale" style="grid-template-columns:repeat({num_members},1fr)">{scale}</div>'
             f'<div></div></div>')

html(f"""
<div class="section">
  <div class="section-head">
    <div><h2>Members</h2>
      <p>Each block is one week of the cycle, running left to right.</p></div>
    <a class="quiet-link" href="#section-payments">Itemised entry</a>
  </div>
  {owing_strip}
  {key_row}
  {scale_row}
  {rows_html}
</div>
""")

html('<span class="anchor" id="section-week"></span>')
with st.expander(f"Record week {max(1,current_elapsed_week):02d} payments", expanded=True):
    st.caption("Tick everyone who has paid for a week and save once. Each tick writes a real payment "
               "with a receipt, and unticking reverses it.")
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
                html(f'<div style="font-size:13px;color:{T["sub_color"]};padding:9px 0">{m} — not owed</div>')
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
        st.warning("These members will be marked unpaid for week %02d and their payments reversed:\n\n" % bw
                   + "\n".join(f"• {m}" for m in removes))
        uc1,uc2 = st.columns(2)
        with uc1:
            if st.button("Confirm and save", key="bulk_confirm_yes"):
                save_bulk(adds, removes)
        with uc2:
            if st.button("Cancel", key="bulk_confirm_no", type="secondary"):
                st.session_state.bulk_confirm = False; st.rerun()
    else:
        if st.button(f"Save week {bw:02d} payments", key="bulk_save"):
            if not adds and not removes:
                flash("No changes to save","info"); st.rerun()
            elif removes:
                st.session_state.bulk_confirm = True; st.rerun()
            else:
                save_bulk(adds, removes)

# ── payout schedule ───────────────────────────────────────────────────────────
show_fee     = fee_frac > 0
fee_col_head = '<th class="num">Admin fee</th>' if show_fee else ""
fee_cls      = "has-fee" if show_fee else "no-fee"
def fee_cell(r): return f'<td class="num">GHS {r["fee"]}</td>' if show_fee else ""

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
        status_badge = '<span class="badge-pending">Not yet due</span>'
    if r["days_away"] is not None:
        urg = "urgent" if r["days_away"] <= 7 else ""
        days_cell = f'<div><span class="days-badge {urg}">{r["days_away"]} days away</span></div>'
    else:
        days_cell = '<div class="cell-sub">Passed</div>'
    early_note = '<div class="early-eligible">Fully funded</div>' if r["early_ok"] else ""
    exit_tag   = '<span class="exit-tag">left the group</span>' if r["exited"] else ""
    pay_rows_html += (
        f'<tr>'
        f'<td><span class="cell-name">{r["turn"]}</span></td>'
        f'<td>{r["recipient"]}{exit_tag}</td>'
        f'<td>{r["date"]}{days_cell}</td>' + fee_cell(r) +
        f'<td class="num">GHS {r["pool"]}{early_note}<div class="pbar-wrap"><div class="pbar-fill" style="width:{bar_pct}%"></div></div></td>'
        f'<td class="num">GHS {r["collected"]}</td><td class="num">GHS {r["remaining"]}</td><td>{status_badge}</td></tr>'
    )

html(f"""
<div class="section">
  <div class="section-head">
    <div><h2>Payout schedule</h2>
      <p>Collected is what the recipient has taken. Remaining is what the group still owes them.</p></div>
    <a class="quiet-link" href="#section-payouts">Record a payout</a>
  </div>
  <table class="data-table tbl-payout {fee_cls}">
    <thead><tr><th>Turn</th><th>Recipient</th><th>Date</th>{fee_col_head}<th class="num">Net pool</th><th class="num">Collected</th><th class="num">Remaining</th><th>Status</th></tr></thead>
    <tbody>{pay_rows_html}</tbody>
  </table>
  <p class="swipe-hint">Swipe sideways for the full breakdown.</p>
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
<div class="section">
  <div class="section-head">
    <div><h2>Share with the group</h2>
      <p>Ready-to-send WhatsApp messages, built from the figures above.</p></div>
  </div>
</div>""")
t1,t2,t3,t4 = st.tabs(["Weekly update","Reminder","Onboarding","History"])
with t1: wa_block(buf.getvalue(), f"Susu_W{current_elapsed_week}.txt", "dl_weekly")
with t2: wa_block(rem.getvalue(), f"Susu_Reminder_W{current_elapsed_week}.txt", "dl_rem")
with t3: wa_block(ob.getvalue(),  "Susu_Onboarding.txt", "dl_ob")
with t4: wa_block(ch.getvalue(),  f"Susu_History_W{current_elapsed_week}.txt", "dl_hist")

# ── admin panel ───────────────────────────────────────────────────────────────
html('<span class="anchor" id="section-admin"></span>'
     '<div class="section" style="margin-top:30px">'
     '<div class="section-head"><div><h2>Group controls</h2>'
     '<p>Record money in and out, then manage settings and tools.</p></div></div></div>')

tab_money, tab_settings, tab_tools = st.tabs(["Money", "Settings", "Tools"])

with tab_money:
    html('<span class="anchor" id="section-payments"></span>')
    with st.expander("Record a payment", expanded=True):
        st.caption("Partial, late, multiple and corrected payments are all supported.")
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
        with pm5: pay_ref  = st.text_input("Reference or note", key="tx_reference", placeholder="MoMo ref, bank ref, or cash note")
        with pm6: pay_date = st.date_input("Payment date", value=today.date(), key="tx_date")
        html(f'<div style="font-size:13px;color:{T["sub_color"]};margin:4px 0 10px">Weekly target is '
             f'<strong style="color:{T["sec_title"]}">GHS {fmt_num(target)}</strong>. Already recorded for week '
             f'{int(pay_week):02d}: <strong style="color:{T["sec_title"]}">GHS {fmt_num(already)}</strong>.</div>')
        if st.button("Save payment", key="save_transaction"):
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

    with st.expander("Recent payment receipts"):
        tx_rows = st.session_state.get("payment_transactions",[])[:10]
        if not tx_rows:
            st.info("Receipts appear here once you record a payment.")
        for tx in tx_rows:
            reversed_tag = " · reversed" if tx.get("status") != "completed" else ""
            st.markdown(f"**{tx.get('member','—')} · Week {int(tx.get('week',0)):02d} · "
                        f"GHS {fmt_num(tx.get('amount',0))}**{reversed_tag} · {tx.get('method','—')} · {tx.get('date','')}")
            wa_block(receipt_text(tx), f"Receipt_{tx.get('id','payment')}.txt", f"receipt_{tx.get('id','payment')}")
            if tx.get("status","completed") == "completed":
                st.caption("To reverse or correct this, use Undo or correct a record below. A reason is required.")
            st.divider()

    html('<span class="anchor" id="section-payouts"></span>')
    with st.expander("Record a payout"):
        turn_options = [f"{r['turn']} — {r['recipient']}" for r in schedule_rows]
        sel_turn_lbl = st.selectbox("Payout turn", turn_options, key="payout_turn")
        sr           = schedule_rows[turn_options.index(sel_turn_lbl)]
        tkey         = sr["turn"]; rec_name = sr["recipient"]
        html(f"""<div style="font-size:14px;color:{T['td_color']};line-height:1.8;margin-bottom:8px">
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
        with po4: payout_ref    = st.text_input("Payout reference or note", key="payout_reference",
                                                placeholder="MoMo ref, bank ref, or cash note")
        coll_dt    = datetime.combine(coll_date, datetime.min.time(), tzinfo=GH_TZ)
        delta_out  = money(new_amt - sr["collected_v"])          # only the change leaves the box
        cash_after = money(total_cash_held - delta_out)
        st.caption(f"Balance still owed to {rec_name} after this entry: GHS {fmt_num(money(sr['net_pool_amt']-new_amt))}"
                   + (" — fully collected" if new_amt >= sr["net_pool_amt"]-0.005 else "")
                   + f" · Group cash after: GHS {fmt_num(cash_after)}")
        overdraw = cash_after < -0.005
        if overdraw:
            st.error(f"The group only holds GHS {fmt_num(total_cash_held)}. Paying out GHS {fmt_num(delta_out)} now "
                     f"would leave it GHS {fmt_num(abs(cash_after))} short. Record the outstanding weekly payments first, "
                     f"or enter a smaller amount.")
            st.session_state.confirm_payout = False
        if not st.session_state.get("confirm_payout",False):
            if st.button("Save payout", key="save_payout_btn", disabled=overdraw):
                st.session_state.confirm_payout=True; st.rerun()
        else:
            st.warning(f"Confirm: {rec_name} ({tkey}) has collected GHS {fmt_num(new_amt)} of GHS {sr['pool']} "
                       f"as at {format_date(coll_dt)}?")
            cc1,cc2 = st.columns(2)
            with cc1:
                if st.button("Yes, save it", key="confirm_yes"):
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
                if st.button("Cancel", key="confirm_no", type="secondary"):
                    st.session_state.confirm_payout=False; st.rerun()

    with st.expander("Recent payout receipts"):
        pl = st.session_state.get("payout_ledger",[])[:6]
        if not pl:
            st.info("Record a payout to generate its receipt.")
        for p in pl:
            rev = " · reversed" if p.get("status","active") == "reversed" else ""
            st.markdown(f"**{p.get('recipient','—')} · {p.get('turn','—')} · GHS {fmt_num(p.get('amount',0))}**{rev} · "
                        f"{p.get('method','—')} · {p.get('date','')}")
            wa_block(payout_receipt_text(p), f"Payout_{p.get('id','receipt')}.txt", f"payoutrcpt_{p.get('id','receipt')}")
            st.divider()

    with st.expander("Undo or correct a record"):
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
                if st.button("Save correction", key="confirm_payment_correction"):
                    if not reason.strip():
                        st.error("Enter a reason.")
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
                st.warning("Only reverse a payout that was recorded in error. The amount is added back to group cash.")
                reason_p = st.text_input("Reason", key="payout_correction_reason", placeholder="Why is this payout being reversed?")
                if st.button("Reverse this payout", key="confirm_payout_correction"):
                    if not reason_p.strip():
                        st.error("Enter a reason.")
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
    with st.expander("Group settings"):
        c1,c2,c3 = st.columns(3)
        with c1: new_start = st.text_input("Start date (YYYY-MM-DD)", value=st.session_state.start_date)
        with c2: new_base  = st.number_input("Base monthly (GHS)", value=float(st.session_state.base_monthly), step=50.0)
        with c3: new_fee   = st.number_input("Admin fee (%)", value=float(st.session_state.admin_fee_percentage),
                                             min_value=0.0, max_value=100.0, step=0.5)
        new_names = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
        html(f'<p style="font-size:13px;color:{T["sub_color"]}">Payment records are kept when you add or reorder members. '
             f'To remove someone mid-cycle use Member status below — deleting the name here shifts every payout date.</p>')

        def save_settings(vals, changes):
            st.session_state.start_date           = vals["start"]
            st.session_state.base_monthly         = vals["base"]
            st.session_state.admin_fee_percentage = vals["fee"]
            st.session_state.names_input          = vals["names"]
            def _m(b):
                put_settings(b)
                return {"type":"setting","text":"Group settings updated","detail":changes}
            if commit(gsheet,_m): flash("Settings saved")

        if st.button("Save settings", key="save_settings"):
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
            st.warning("This changes the cycle structure (" + ", ".join(pending.get("structural", [])) +
                       "). Payment history is preserved, but payout dates or the rotation order can move. "
                       "Confirm only if that is intended.")
            sc1,sc2 = st.columns(2)
            with sc1:
                if st.button("Confirm change", key="confirm_settings_yes"):
                    st.session_state.confirm_settings = False
                    p = st.session_state.pop("pending_settings", None)
                    if p: save_settings(p["vals"], p["changes"])
                    st.rerun()
            with sc2:
                if st.button("Cancel", key="confirm_settings_no", type="secondary"):
                    st.session_state.pop("pending_settings", None)
                    st.session_state.confirm_settings = False
                    st.rerun()

    with st.expander("Custom member tiers"):
        tier_cols = st.columns(min(num_members,4))
        new_tiers = {}
        for idx,m in enumerate(members):
            with tier_cols[idx%4]:
                new_tiers[m] = st.number_input(m, value=float(tier(m)), step=50.0, key=f"tier_{m}")
        if st.button("Save tiers", key="save_tiers"):
            diffs = [f"{m}: GHS {fmt_num(tier(m))} → GHS {fmt_num(v)}" for m,v in new_tiers.items() if float(v)!=float(tier(m))]
            def _m(b):
                b.setdefault("tiers",{}).update({k:float(v) for k,v in new_tiers.items()})
                return {"type":"setting","text":f"Member tiers updated ({len(diffs)} changed)","detail":diffs} if diffs else None
            if commit(gsheet,_m): flash("Tiers saved" if diffs else "No tier changes")
            st.rerun()

    with st.expander("Member status"):
        html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:8px">Mark a member as exited instead of '
             f'deleting them. Their history and rotation slot stay intact; they simply stop owing from the exit week onward.</p>')
        ms1,ms2,ms3 = st.columns([2,1,1])
        with ms1: sm = st.selectbox("Member", members, key="status_member", label_visibility="collapsed")
        with ms2: new_status = st.selectbox("Status", ["active","exited"], index=0 if not exited(sm) else 1,
                                            key="status_val", label_visibility="collapsed")
        with ms3: new_exit_wk = st.number_input("Exit week", min_value=1, max_value=total_weeks,
                                                value=int(mstat(sm).get("exit_week") or max(1,current_elapsed_week)),
                                                step=1, key="status_week", label_visibility="collapsed")
        if st.button("Save member status", key="save_status"):
            before = mstat(sm)
            after  = {"status":new_status,"exit_week":int(new_exit_wk) if new_status=="exited" else None}
            def _m(b):
                b.setdefault("member_status",{})[sm] = after
                if before==after: return None
                txt = f"{sm} marked exited from week {new_exit_wk}" if new_status=="exited" else f"{sm} reinstated as active"
                return {"type":"setting","text":txt,"detail":[f"{sm}: {before.get('status')} → {after['status']}"]}
            if commit(gsheet,_m): flash("Member status saved")
            st.rerun()

    with st.expander("Change passcode"):
        html(f'<p style="font-size:13px;color:{T["sub_color"]};margin-bottom:8px">Enter the current passcode to confirm, '
             f'then set a new one. Passcodes are stored as salted scrypt hashes.</p>')
        cp1,cp2,cp3 = st.columns(3)
        with cp1: old_pw  = st.text_input("Current passcode", type="password", key="old_pw")
        with cp2: new_pw1 = st.text_input("New passcode", type="password", key="new_pw1")
        with cp3: new_pw2 = st.text_input("Confirm new passcode", type="password", key="new_pw2")
        if st.button("Update passcode", key="update_pw"):
            stored_pw = st.session_state.get("admin_passcode", "")
            if not check_pw(old_pw, stored_pw): st.error("The current passcode is not correct.")
            elif len(new_pw1) < 8: st.error("The new passcode must be at least 8 characters.")
            elif new_pw1 != new_pw2: st.error("The two new passcodes do not match.")
            else:
                def _m(b):
                    b["passcode"] = hash_pw(new_pw1)
                    return {"type":"setting","text":"Passcode changed"}
                if commit(gsheet,_m): flash("Passcode updated")
                st.rerun()

with tab_tools:
    with st.expander("Member profile"):
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

    with st.expander("Cash reconciliation"):
        html(f'<div style="font-size:14px;color:{T["td_color"]};line-height:1.8">System cash held: '
             f'<strong style="color:{T["sec_title"]}">GHS {fmt_num(total_cash_held)}</strong><br>'
             f'Enter the physical cash plus verified mobile or bank balance actually held by the group.</div>')
        actual_cash = st.number_input("Actual cash or account balance (GHS)", min_value=0.0,
                                      value=float(total_cash_held), step=10.0, key="recon_actual")
        recon_diff = money(actual_cash - total_cash_held)
        if abs(recon_diff) < 0.005: st.success("Reconciled — the actual balance matches the system.")
        elif recon_diff > 0:        st.warning(f"GHS {fmt_num(recon_diff)} more than the system balance.")
        else:                       st.error(f"GHS {fmt_num(abs(recon_diff))} less than the system balance.")
        recon_note = st.text_input("Reconciliation note", key="recon_note", placeholder="e.g. Cash counted and MoMo balance checked")
        if st.button("Save reconciliation", key="save_recon"):
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
                col  = "#5BC490" if abs(diff)<0.005 else ("#E8B15C" if diff>0 else "#E8795A")
                rec_html += (f'<div class="log-entry"><div class="log-dot log-dot-setting"></div>'
                             f'<div class="log-text"><strong>Actual GHS {fmt_num(rec.get("actual",0))} vs system '
                             f'GHS {fmt_num(rec.get("system",0))}</strong>'
                             f'<div class="diff-line" style="color:{col}">difference GHS {fmt_num(diff)}'
                             f'{" · " + rec.get("note","") if rec.get("note") else ""}</div></div>'
                             f'<div class="log-time">{rec.get("date","")}</div></div>')
            html(rec_html)

    with st.expander("Convert legacy weeks"):
        st.caption("Weeks recorded as a plain tick, before receipts existed, count towards the totals but have no "
                   "transaction behind them. Converting writes one transaction per week so every cedi has a record.")
        legacy_pairs = []
        for m in members:
            for w in range(1, total_weeks+1):
                if st.session_state.payments.get(m,{}).get(str(w), False) and not [
                        t for t in st.session_state.get("payment_transactions",[])
                        if t.get("member")==m and int(t.get("week",0))==w]:
                    legacy_pairs.append((m, w, weekly(m)))
        if not legacy_pairs:
            st.success("Nothing to convert — every paid week already has a transaction.")
        else:
            total_legacy = money(sum(a for _,_,a in legacy_pairs))
            by_member = {}
            for m,w,a in legacy_pairs: by_member.setdefault(m,[]).append(w)
            html(f'<div style="font-size:14px;color:{T["td_color"]};line-height:1.7">'
                 f'<strong style="color:{T["sec_title"]}">{len(legacy_pairs)} week(s)</strong> · '
                 f'GHS {fmt_num(total_legacy)} across '
                 + ", ".join(f"{m} ({len(ws)})" for m,ws in by_member.items()) + '</div>')
            conv_method = st.selectbox("Record these as", ["Cash","MoMo","Bank transfer","Other"], key="convert_method")
            st.caption("Totals do not change — each week is already counted. This only attaches a transaction to it.")
            if st.button("Convert to transactions", key="convert_legacy"):
                who_now = st.session_state.get("admin_name", ADMIN_NAME)
                def _m(b, pairs=legacy_pairs, method=conv_method, who_now=who_now):
                    for m, w, amt in pairs:
                        tx = {"id":new_id("PAY"),"member":m,"week":int(w),"amount":money(amt),
                              "date":"","time":now_str(),"method":method,
                              "reference":"Converted from week grid","status":"completed","who":who_now}
                        b.setdefault("payment_transactions",[]).insert(0, tx)
                    detail = [f"{m} Wk {int(w):02d}: GHS {fmt_num(a)}" for m,w,a in pairs[:12]]
                    if len(pairs) > 12: detail.append(f"…and {len(pairs)-12} more")
                    return {"type":"payment",
                            "text":f"Converted {len(pairs)} legacy week(s) to transactions",
                            "detail":detail}
                if commit(gsheet,_m): flash(f"{len(legacy_pairs)} week(s) converted")
                st.rerun()

    with st.expander("Backups"):
        st.caption(f"A copy of the whole group record is saved to the {BACKUP_WS} worksheet on every change. "
                   f"The last {BACKUP_KEEP} are kept.")
        if st.button("Load backup list", key="load_backups"):
            st.session_state.backup_list = list_backups(gsheet)
            st.rerun()
        blist = st.session_state.get("backup_list")
        if blist is None:
            st.info("Load the backup list to read it from Google Sheets.")
        elif not blist:
            st.warning("No backups yet — the next save will create the first one.")
        else:
            labels = [f"{when}  ·  rev {rev}" for _, when, rev in blist]
            bidx = st.selectbox("Restore point", range(len(blist)), format_func=lambda n: labels[n], key="backup_pick")
            row_no, when, rev = blist[bidx]
            st.warning(f"Restoring replaces the current record (rev {st.session_state.rev}) with the one saved at "
                       f"{when}. Anything recorded since will be lost. The current state is itself backed up first.")
            confirm_txt = st.text_input('Type RESTORE to confirm', key="restore_confirm")
            if st.button("Restore this backup", key="do_restore"):
                if confirm_txt.strip().upper() != "RESTORE":
                    st.error("Type RESTORE in the box to confirm.")
                else:
                    old = read_blob_fresh(gsheet)
                    snap = read_backup(gsheet, row_no)
                    if not snap:
                        st.error("That backup could not be read.")
                    else:
                        write_backup(gsheet, old)               # keep what we are replacing
                        snap["rev"] = old.get("rev",0) + 1
                        snap.setdefault("history",[]).insert(0, {
                            "type":"setting","who":st.session_state.get("admin_name",ADMIN_NAME),
                            "time":now_str(),"text":f"Restored backup from {when} (rev {rev})",
                            "detail":[f"replaced rev {old.get('rev',0)}"]})
                        write_blob(gsheet, snap)
                        apply_blob(snap)
                        st.session_state.pop("backup_list", None)
                        flash("Backup restored","warning")
                        st.rerun()

    with st.expander("Payment audit"):
        ledger = st.session_state.get("payment_ledger", [])
        if not ledger:
            st.info("Payment audit entries appear here once money is recorded.")
        else:
            led_html = ""
            for entry in ledger[:30]:
                act    = entry.get("action","paid")
                action = {"paid":"Paid","reversed":"Reversed","corrected":"Corrected"}.get(act, act.title())
                dot    = "log-dot" if act == "paid" else "log-dot log-dot-payout"
                extra  = " · ".join(x for x in [entry.get("method",""), entry.get("reference",""), entry.get("reason","")] if x)
                led_html += (f'<div class="log-entry"><div class="{dot}"></div>'
                             f'<div class="log-text"><strong>{entry.get("member","—")} · Week {int(entry.get("week",0)):02d} · '
                             f'GHS {fmt_num(entry.get("amount",0))}</strong>'
                             f'<div class="diff-line">{action} by {entry.get("who","")}{" · " + extra if extra else ""}</div></div>'
                             f'<div class="log-time">{entry.get("time","")}</div></div>')
            html(led_html)

    if st.session_state.history:
        with st.expander("Activity log"):
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
if st.button("Lock dashboard", key="logout", type="secondary"):
    st.session_state.authenticated=False; st.session_state.admin_name=ADMIN_NAME
    st.session_state.last_activity=now_dt(); st.rerun()

html('<div class="foot">Susu Savings · Backed by Google Sheets · Secured with a passcode</div>')
