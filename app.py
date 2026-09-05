import streamlit as st
from datetime import datetime, timedelta
import io
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Susu Savings",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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
    removeSidebar();
    setTimeout(removeSidebar, 300);
    setTimeout(removeSidebar, 800);
    </script>
    <script>
    // Web Share API helper
    function shareText(text, title) {
        if (navigator.share) {
            navigator.share({ title: title, text: text })
                .catch(e => console.log('Share cancelled'));
        } else {
            navigator.clipboard.writeText(text)
                .then(() => alert('Copied to clipboard!'))
                .catch(() => alert('Copy not supported — please copy manually'));
        }
    }
    // Copy to clipboard helper for member links
    function copyLink(url) {
        navigator.clipboard.writeText(url)
            .then(() => alert('Link copied!'))
            .catch(() => alert(url));
    }
    // Smooth scroll to section
    function navTo(id) {
        const el = window.parent.document.getElementById(id);
        if (el) el.scrollIntoView({behavior:'smooth'});
        else window.parent.scrollTo({top: id === 'top' ? 0 : 99999, behavior:'smooth'});
    }
    </script>
""", unsafe_allow_html=True)

# ── theme init ────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
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
        "bulk_bg":"rgba(255,255,255,0.02)","bar_bg":"rgba(255,255,255,0.06)",
        "member_view_bg":"rgba(56,189,248,0.06)","member_view_border":"rgba(56,189,248,0.15)",
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
        "bulk_bg":"rgba(0,0,0,0.03)","bar_bg":"rgba(0,0,0,0.08)",
        "member_view_bg":"rgba(99,102,241,0.05)","member_view_border":"rgba(99,102,241,0.15)",
    }

dl_color = "#38bdf8" if D else "#6366f1"
urgent_glow = "0 0 16px rgba(251,191,36,0.5),0 0 32px rgba(251,191,36,0.2)" if D else "0 0 12px rgba(251,191,36,0.3)"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    header{{visibility:hidden!important;height:0!important;}}
    #MainMenu{{visibility:hidden!important;}}
    .stDeployButton{{display:none!important;}}
    footer{{visibility:hidden!important;}}
    section[data-testid="stSidebar"]{{display:none!important;width:0!important;}}
    [data-testid="collapsedControl"]{{display:none!important;width:0!important;}}
    [data-testid="stSidebarNav"]{{display:none!important;}}
    button[kind="header"]{{display:none!important;}}
    .block-container{{padding-top:0!important;padding-bottom:4rem!important;max-width:820px!important;}}
    html,body,[class*="css"]{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}}
    .main,.stApp{{background:{T['bg']}!important;min-height:100vh;}}

    .status-bar{{background:{T['status_bg']};border-bottom:1px solid {T['status_border']};padding:8px 0;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;font-size:11px;}}
    .status-dot{{width:6px;height:6px;background:#34d399;border-radius:50%;display:inline-block;margin-right:6px;animation:pulse 2s infinite;}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
    .status-live{{color:#34d399;font-weight:600;}}
    .status-sync{{color:{T['sync_color']};}}

    .lock-outer{{min-height:80vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;}}
    .lock-card{{background:{T['lock_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid {T['lock_border']};border-radius:24px;padding:48px 40px;text-align:center;width:100%;max-width:360px;box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 0 rgba(255,255,255,0.4);}}
    .lock-icon{{font-size:44px;margin-bottom:16px;display:block;}}
    .lock-title{{font-size:22px;font-weight:700;color:{T['lock_title']};margin-bottom:6px;}}
    .lock-sub{{font-size:13px;color:{T['lock_sub']};margin-bottom:0;}}

    .hero{{background:{T['hero_bg']};backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid {T['hero_border']};border-radius:20px;padding:22px 28px;margin-bottom:14px;box-shadow:0 4px 24px rgba(0,0,0,0.1),inset 0 1px 0 rgba(255,255,255,0.3);position:relative;overflow:hidden;}}
    .hero::before{{content:'';position:absolute;top:-60px;right:-60px;width:220px;height:220px;background:radial-gradient(circle,rgba(56,189,248,0.08) 0%,transparent 70%);pointer-events:none;}}
    .hero::after{{content:'';position:absolute;bottom:-40px;left:-40px;width:160px;height:160px;background:radial-gradient(circle,rgba(99,102,241,0.06) 0%,transparent 70%);pointer-events:none;}}
    .hero-title{{font-size:17px;font-weight:700;color:{T['title_color']};margin:0 0 3px 0;letter-spacing:-0.2px;}}
    .hero-sub{{font-size:12px;color:{T['sub_color']};margin:0;}}
    .hero-badge{{display:inline-flex;align-items:center;gap:5px;background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.2);border-radius:20px;padding:4px 10px;font-size:10px;font-weight:600;color:#38bdf8;margin-top:10px;letter-spacing:0.3px;}}

    /* Member view banner */
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

    .chip-row{{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;}}
    .chip{{flex:1;min-width:110px;background:{T['chip_bg']};backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid {T['chip_border']};border-radius:14px;padding:14px 16px;box-shadow:0 2px 12px rgba(0,0,0,0.1),inset 0 1px 0 rgba(255,255,255,0.2);transition:border-color 0.2s,box-shadow 0.2s;}}
    .chip-label{{font-size:10px;font-weight:600;color:{T['label_color']};text-transform:uppercase;letter-spacing:0.7px;margin-bottom:6px;}}
    .chip-value{{font-size:16px;font-weight:700;color:#38bdf8;}}
    .chip-value-green{{font-size:16px;font-weight:700;color:#34d399;}}
    .chip-value-amber{{font-size:16px;font-weight:700;color:#fbbf24;}}
    .chip-value-red{{font-size:16px;font-weight:700;color:#f87171;}}
    @keyframes countUp{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
    .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{animation:countUp 0.6s ease-out;}}

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

    /* Payout progress bar */
    .pbar-wrap{{margin-top:6px;background:{T['bar_bg']};border-radius:4px;height:4px;overflow:hidden;}}
    .pbar-fill{{height:4px;border-radius:4px;background:linear-gradient(90deg,#34d399,#38bdf8);transition:width 0.4s ease;}}

    /* Collected vs expected chip */
    .chip-sub{{font-size:10px;color:{T['sub_color']};margin-top:3px;}}

    /* Member self-view week grid */
    .week-grid{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;}}
    .week-pill{{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;}}
    .week-paid{{background:rgba(52,211,153,0.12);color:#34d399;border:1px solid rgba(52,211,153,0.25);}}
    .week-owe{{background:rgba(251,191,36,0.12);color:#fbbf24;border:1px solid rgba(251,191,36,0.25);}}
    .week-upcoming{{background:rgba(255,255,255,0.04);color:{T['td_color']};border:1px solid {T['card_border']};}}

    .log-entry{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid {T['log_border']};}}
    .log-entry:last-child{{border-bottom:none;}}
    .log-dot{{width:8px;height:8px;border-radius:50%;background:#38bdf8;margin-top:4px;flex-shrink:0;}}
    .log-dot-payout{{background:#818cf8;}}
    .log-dot-setting{{background:#34d399;}}
    .log-text{{font-size:12px;color:{T['log_color']};line-height:1.4;}}
    .log-text strong{{color:{T['log_strong']};font-weight:600;}}
    .log-time{{font-size:11px;color:{T['log_time']};margin-left:auto;white-space:nowrap;padding-left:12px;}}

    .stTextInput input,.stNumberInput input,.stTextArea textarea{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;color:{T['input_color']}!important;border-radius:10px!important;font-size:13px!important;}}
    .stTextInput input:focus,.stNumberInput input:focus{{border-color:rgba(56,189,248,0.4)!important;box-shadow:0 0 0 2px rgba(56,189,248,0.08)!important;}}
    .stTextInput label,.stNumberInput label,.stTextArea label,.stSelectbox label,.stCheckbox label{{color:{T['label_color']}!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.5px;}}
    .stSelectbox > div > div{{background:{T['input_bg']}!important;border:1px solid {T['input_border']}!important;color:{T['input_color']}!important;border-radius:10px!important;}}

    .stButton > button{{background:{T['btn_bg']}!important;backdrop-filter:blur(8px)!important;color:white!important;border:1px solid {T['btn_border']}!important;border-radius:10px!important;font-weight:600!important;font-size:13px!important;padding:9px 20px!important;width:100%;box-shadow:0 2px 8px rgba(29,78,216,0.25)!important;transition:all 0.2s!important;}}
    .stButton > button:hover{{background:rgba(37,99,235,0.95)!important;box-shadow:0 4px 16px rgba(29,78,216,0.4)!important;}}
    .stButton > button[kind="secondary"]{{background:{T['btn2_bg']}!important;color:{T['btn2_color']}!important;border:1px solid {T['btn2_border']}!important;box-shadow:none!important;}}
    .stDownloadButton > button{{background:{T['dl_bg']}!important;backdrop-filter:blur(8px)!important;color:{dl_color}!important;border:1px solid {T['dl_border']}!important;border-radius:10px!important;font-size:13px!important;font-weight:600!important;padding:9px 20px!important;width:100%!important;transition:all 0.2s!important;}}

    .streamlit-expanderHeader{{background:{T['exp_bg']}!important;backdrop-filter:blur(12px)!important;border:1px solid {T['exp_border']}!important;border-radius:12px!important;color:{T['exp_color']}!important;font-size:13px!important;font-weight:600!important;transition:border-color 0.2s!important;}}
    .streamlit-expanderContent{{background:{T['exp_content']}!important;border:1px solid {T['exp_border']}!important;border-top:none!important;border-radius:0 0 12px 12px!important;padding:18px!important;backdrop-filter:blur(12px)!important;}}

    div[data-testid="stSuccess"]{{background:rgba(16,185,129,0.07)!important;border:1px solid rgba(16,185,129,0.2)!important;border-radius:10px!important;color:#34d399!important;font-size:13px!important;}}
    div[data-testid="stError"]{{background:rgba(239,68,68,0.07)!important;border:1px solid rgba(239,68,68,0.2)!important;border-radius:10px!important;color:#f87171!important;font-size:13px!important;}}
    div[data-testid="stWarning"]{{background:rgba(251,191,36,0.07)!important;border:1px solid rgba(251,191,36,0.2)!important;border-radius:10px!important;color:#fbbf24!important;font-size:13px!important;}}

    .gdivider{{height:1px;background:linear-gradient(90deg,transparent,{T['gdiv']},transparent);margin:22px 0;}}
    .foot{{text-align:center;font-size:11px;color:{T['foot_color']};margin-top:32px;padding-top:20px;border-top:1px solid {T['foot_border']};}}
    @media (max-width:600px){{
        .block-container{{padding-bottom:5rem!important;padding-left:12px!important;padding-right:12px!important;}}
        .hero{{padding:14px 16px!important;border-radius:14px!important;margin-bottom:10px!important;}}
        .hero-title{{font-size:15px!important;}}
        .hero-sub{{font-size:11px!important;}}
        .chip-row{{display:grid!important;grid-template-columns:1fr 1fr!important;gap:8px!important;}}
        .chip{{min-width:0!important;padding:10px 12px!important;}}
        .chip-value,.chip-value-green,.chip-value-amber,.chip-value-red{{font-size:15px!important;}}
        .data-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;}}
        .data-table th,.data-table td{{padding:8px 10px!important;font-size:11px!important;}}
        .glass-card{{padding:14px 14px!important;border-radius:12px!important;}}
        .sec-title{{font-size:14px!important;}}
    }}
    .bottom-nav{{
        display:none;
        position:fixed;bottom:0;left:0;right:0;z-index:999;
        background:{T['card_bg']};backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
        border-top:1px solid {T['card_border']};
        padding:8px 0 8px;
        justify-content:space-around;align-items:center;
    }}
    @media (max-width:600px){{.bottom-nav{{display:flex!important;}}}}
    .nav-item{{display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;padding:4px 16px;border-radius:10px;text-decoration:none;border:none;background:none;}}
    .nav-icon{{font-size:20px;line-height:1;}}
    .nav-label{{font-size:9px;font-weight:600;color:{T['sub_color']};letter-spacing:0.3px;text-transform:uppercase;}}
    .link-pill{{display:flex;align-items:center;justify-content:space-between;background:{T['card_bg']};border:1px solid {T['card_border']};border-radius:12px;padding:10px 14px;margin-bottom:8px;gap:10px;}}
    .link-pill-name{{font-size:13px;font-weight:600;color:{T['member_name']};}}
    .link-pill-url{{font-size:10px;color:{T['sub_color']};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;}}
    .copy-btn{{background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.2);color:#38bdf8;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;flex-shrink:0;}}
    </style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_num(val):
    return f"{int(val):,}" if val == int(val) else f"{val:,.2f}"

def format_date(dt):
    d = dt.day
    sfx = 'th' if 11 <= d <= 13 else {1:'st',2:'nd',3:'rd'}.get(d%10,'th')
    return f"{d}{sfx} {dt.strftime('%b %Y')}"


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

def load_all(sheet):
    settings = load_cell(sheet, "settings", {
        "start_date":"2026-08-17","base_monthly":1000,
        "admin_fee_percentage":0.0,"names_input":"Alice, Bob, Charlie, Diana, Frank, Grace",
    })
    return settings, load_cell(sheet,"tiers",{}), load_cell(sheet,"payments",{}), load_cell(sheet,"payout_status",{}), load_cell(sheet,"history",[])

def save_all(sheet):
    save_cell(sheet,"settings",{"start_date":st.session_state.start_date,"base_monthly":st.session_state.base_monthly,"admin_fee_percentage":st.session_state.admin_fee_percentage,"names_input":st.session_state.names_input})
    save_cell(sheet,"tiers",st.session_state.member_tiers)
    save_cell(sheet,"payments",st.session_state.payments)
    save_cell(sheet,"payout_status",st.session_state.payout_status)

def append_log(sheet, entry):
    st.session_state.history.insert(0, entry)
    st.session_state.history = st.session_state.history[:50]
    save_cell(sheet,"history",st.session_state.history)


# ── connect ───────────────────────────────────────────────────────────────────
try:
    gsheet = get_sheet()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    st.stop()

if "initialized" not in st.session_state:
    settings, tiers, payments, payout_status, history = load_all(gsheet)
    st.session_state.start_date           = settings.get("start_date","2026-08-17")
    st.session_state.base_monthly         = settings.get("base_monthly",1000)
    st.session_state.admin_fee_percentage = settings.get("admin_fee_percentage",0.0)
    st.session_state.names_input          = settings.get("names_input","Alice, Bob, Charlie, Diana, Frank, Grace")
    st.session_state.member_tiers         = tiers
    st.session_state.payments             = payments
    st.session_state.payout_status        = payout_status
    st.session_state.history              = history
    st.session_state.authenticated        = False
    st.session_state.initialized          = True
    st.session_state.last_sync            = datetime.now()
    st.session_state.confirm_payout       = False


# ── URL param — member self-view ──────────────────────────────────────────────
params       = st.query_params
member_view  = params.get("member", None)
is_admin_url = not bool(member_view)


# ── auth ──────────────────────────────────────────────────────────────────────
ADMIN_PW = "Susu2026"

if not member_view and not st.session_state.authenticated:
    st.markdown('<div class="lock-outer">', unsafe_allow_html=True)
    st.markdown("""
        <div class="lock-card">
            <span class="lock-icon">💸</span>
            <div class="lock-title">Susu Savings</div>
            <div class="lock-sub">Enter your passcode to continue</div>
        </div>
    """, unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1,2,1])
    with col_c:
        pw = st.text_input("p", type="password", label_visibility="collapsed", placeholder="Passcode…")
        if st.button("Unlock →"):
            if pw == ADMIN_PW:
                st.session_state.authenticated = True
                st.session_state.last_sync = datetime.now()
                st.rerun()
            else:
                st.error("Incorrect passcode.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# ── derive ────────────────────────────────────────────────────────────────────
members     = [n.strip() for n in st.session_state.names_input.split(",") if n.strip()]
num_members = len(members)
if num_members < 2:
    st.error("Please enter at least 2 member names in Settings.")
    st.stop()

for m in members:
    if m not in st.session_state.member_tiers:
        st.session_state.member_tiers[m] = st.session_state.base_monthly

total_weeks = num_members * 4

try:
    start_dt = datetime.strptime(st.session_state.start_date, "%Y-%m-%d")
except ValueError:
    st.error("Date format must be YYYY-MM-DD.")
    st.stop()

end_date = start_dt + timedelta(weeks=total_weeks)

if list(st.session_state.payments.keys()) != members:
    st.session_state.payments = {m: {str(w): False for w in range(1, total_weeks+1)} for m in members}
if not st.session_state.payout_status:
    st.session_state.payout_status = {f"Month {i+1}": {"amount_collected":0.0} for i in range(num_members)}

today                = datetime.today()
days_passed          = (today - start_dt).days
current_elapsed_week = min(max(0, days_passed//7)+1 if today >= start_dt else 0, total_weeks)

total_cash_collected = sum(
    st.session_state.member_tiers.get(m, st.session_state.base_monthly) / 4.0
    * sum(1 for w in range(1, total_weeks+1) if st.session_state.payments.get(m,{}).get(str(w), False))
    for m in members
)
total_payouts_dist = sum(
    float(st.session_state.payout_status.get(f"Month {i+1}",{}).get("amount_collected",0.0))
    for i in range(num_members)
)
total_cash_held = total_cash_collected - total_payouts_dist

# Expected vs collected
total_expected_so_far = sum(
    st.session_state.member_tiers.get(m, st.session_state.base_monthly) / 4.0 * current_elapsed_week
    for m in members
)
collection_gap = total_expected_so_far - total_cash_collected

next_recipient, next_payout_date, next_net_pool, days_to_payout = None, None, 0, 0
cur_d = start_dt
for i in range(num_members):
    pd_date = cur_d + timedelta(weeks=4)
    if pd_date >= today:
        next_recipient   = members[i]
        next_payout_date = pd_date
        rm               = st.session_state.member_tiers.get(members[i], st.session_state.base_monthly)
        next_net_pool    = rm * num_members * (1 - st.session_state.admin_fee_percentage/100.0)
        days_to_payout   = (pd_date - today).days
        break
    cur_d = pd_date

members_owing = sum(
    1 for m in members
    if (current_elapsed_week - sum(
        1 for w in range(1, current_elapsed_week+1)
        if st.session_state.payments.get(m,{}).get(str(w), False)
    )) > 0
)


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER SELF-VIEW (read-only, no passcode)
# ══════════════════════════════════════════════════════════════════════════════
if member_view:
    if member_view not in members:
        st.error(f"Member '{member_view}' not found in this group.")
        st.stop()

    m_monthly   = st.session_state.member_tiers.get(member_view, st.session_state.base_monthly)
    m_weekly    = m_monthly / 4.0
    m_pmts      = st.session_state.payments.get(member_view, {})
    paid_passed = sum(1 for w in range(1, current_elapsed_week+1) if m_pmts.get(str(w), False))
    total_paid  = sum(1 for w in range(1, total_weeks+1) if m_pmts.get(str(w), False))
    owing_weeks = current_elapsed_week - paid_passed
    owing_amt   = owing_weeks * m_weekly
    standing    = f"Owing GHS {fmt_num(owing_amt)}" if owing_amt > 0 else "Up to date"

    # Status bar (no theme toggle for member view)
    sync_ago = int((datetime.now() - st.session_state.last_sync).total_seconds() / 60)
    sync_txt = "just now" if sync_ago < 1 else f"{sync_ago}m ago"
    st.markdown(f"""
        <div class="status-bar">
            <span><span class="status-dot"></span><span class="status-live">Live</span></span>
            <span class="status-sync">Synced {sync_txt} &nbsp;·&nbsp; Google Sheets</span>
        </div>
        <div class="hero">
            <div class="hero-title">💸 Susu Savings — Member View</div>
            <div class="hero-sub">{format_date(start_dt)} → {format_date(end_date)}</div>
        </div>
        <div class="member-view-banner">
            <div>
                <div class="member-view-label">Your Account</div>
                <div class="member-view-name">{member_view}</div>
                <div class="member-view-sub">GHS {fmt_num(m_monthly)}/month &nbsp;·&nbsp; GHS {fmt_num(m_weekly)}/week</div>
            </div>
            <div style="text-align:right">
                <div class="{'badge-owe' if owing_amt > 0 else 'badge-ok'}">{standing}</div>
                <div style="font-size:11px;color:{T['sub_color']};margin-top:6px">{total_paid} / {total_weeks} weeks paid</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Week-by-week grid
    pills = ""
    for w in range(1, total_weeks+1):
        paid    = m_pmts.get(str(w), False)
        future  = w > current_elapsed_week
        cls     = "week-paid" if paid else ("week-upcoming" if future else "week-owe")
        icon    = "✅" if paid else ("⏳" if future else "❌")
        pills  += f'<span class="week-pill {cls}">{icon} Wk {w}</span>'

    st.markdown(f"""
        <div class="glass-card">
            <p class="sec-label">Payment Tracker</p>
            <p class="sec-title">Your Weekly History</p>
            <p class="sec-sub">✅ Paid &nbsp;·&nbsp; ❌ Owing &nbsp;·&nbsp; ⏳ Upcoming</p>
            <div class="week-grid">{pills}</div>
        </div>
    """, unsafe_allow_html=True)

    # Next payout info
    if next_recipient:
        urgent_cls = "urgent" if days_to_payout <= 7 else ""
        st.markdown(f"""
            <div class="countdown-banner">
                <div class="countdown-left">
                    <div class="countdown-label">Next Group Payout</div>
                    <div class="countdown-name">{next_recipient}</div>
                    <div class="countdown-pool">GHS {fmt_num(next_net_pool)} &nbsp;·&nbsp; {format_date(next_payout_date)}</div>
                </div>
                <div class="countdown-right">
                    <div class="countdown-days {urgent_cls}">{days_to_payout}</div>
                    <div class="countdown-days-label">days away</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<div class="foot">Read-only view · {member_view} · Susu Savings</div>', unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

# status bar + theme toggle
sync_ago = int((datetime.now() - st.session_state.last_sync).total_seconds() / 60)
sync_txt = "just now" if sync_ago < 1 else f"{sync_ago}m ago"
sb_col, tg_col = st.columns([4,1])
with sb_col:
    st.markdown(f"""
        <div class="status-bar">
            <span><span class="status-dot"></span><span class="status-live">Live</span></span>
            <span class="status-sync">Synced {sync_txt} &nbsp;·&nbsp; Google Sheets</span>
        </div>
    """, unsafe_allow_html=True)
with tg_col:
    st.markdown("<div style='padding-top:2px'>", unsafe_allow_html=True)
    if st.button(f"{T['toggle_icon']} {T['toggle_label']}", key="theme_toggle", type="secondary"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# hero
st.markdown(f"""
    <div class="hero">
        <div class="hero-title">💸 Susu Savings Dashboard</div>
        <div class="hero-sub">{num_members} members &nbsp;·&nbsp; {format_date(start_dt)} → {format_date(end_date)}</div>
        <div class="hero-badge">🔓 &nbsp;Admin session active</div>
    </div>
""", unsafe_allow_html=True)



# chips — 4th chip: total collected vs expected
gap_class   = "chip-value-red" if collection_gap > 0 else "chip-value-green"
gap_label   = f"−GHS {fmt_num(collection_gap)}" if collection_gap > 0 else "On track"
st.markdown(f"""
    <div class="chip-row">
        <div class="chip"><div class="chip-label">Cash Held</div><div class="chip-value">GHS {fmt_num(total_cash_held)}</div></div>
        <div class="chip"><div class="chip-label">Week</div><div class="chip-value">{current_elapsed_week} / {total_weeks}</div></div>
        <div class="chip"><div class="chip-label">Next Payout</div><div class="chip-value-amber">{days_to_payout} days</div></div>
        <div class="chip">
            <div class="chip-label">Collection</div>
            <div class="{gap_class}">{gap_label}</div>
            <div class="chip-sub">Expected GHS {fmt_num(total_expected_so_far)}</div>
        </div>
    </div>
""", unsafe_allow_html=True)


# ── build data ────────────────────────────────────────────────────────────────
schedule_rows, wa_payout_rows = [], []
cur_d = start_dt
for i in range(num_members):
    month_lbl    = f"Month {i+1}"
    recipient    = members[i]
    payout_date  = cur_d + timedelta(weeks=4)
    rec_monthly  = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    gross_pool   = rec_monthly * num_members
    admin_fee_v  = gross_pool * (st.session_state.admin_fee_percentage / 100.0)
    net_pool_amt = gross_pool - admin_fee_v
    collected    = float(st.session_state.payout_status.get(month_lbl,{}).get("amount_collected",0.0))
    remaining    = max(0.0, net_pool_amt - collected)
    pct_collected = int((collected / net_pool_amt * 100)) if net_pool_amt > 0 else 0
    schedule_rows.append({"turn":f"Month {i+1}","recipient":recipient,"date":format_date(payout_date),"fee":fmt_num(admin_fee_v),"pool":fmt_num(net_pool_amt),"collected":fmt_num(collected),"remaining":fmt_num(remaining),"pct":pct_collected})
    wa_payout_rows.append({"recipient":recipient,"date":format_date(payout_date),"balance":fmt_num(remaining)})
    cur_d = payout_date

contrib_rows, wa_contrib_rows = [], []
for member in members:
    m_monthly   = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly    = m_monthly / 4.0
    m_pmts      = st.session_state.payments.get(member, {})
    paid_passed = sum(1 for w in range(1, current_elapsed_week+1) if m_pmts.get(str(w), False))
    owing       = (current_elapsed_week - paid_passed) * m_weekly
    total_paid  = sum(1 for w in range(1, total_weeks+1) if m_pmts.get(str(w), False))
    standing    = f"Owing GHS {fmt_num(owing)}" if owing > 0 else "Up to date"
    contrib_rows.append({"member":member,"m_monthly":m_monthly,"m_weekly":m_weekly,"total_paid":total_paid,"owing":owing,"standing":standing})
    wa_contrib_rows.append({"member":member,"standing":standing})


# ── contributions card ────────────────────────────────────────────────────────
rows_html = ""
for r in contrib_rows:
    is_owing  = r["owing"] > 0
    row_class = "owing" if is_owing else "ok"
    badge     = f'<span class="badge-owe">Owing GHS {fmt_num(r["owing"])}</span>' if is_owing else '<span class="badge-ok">Up to date</span>'
    rows_html += f"""<tr class="{row_class}">
        <td><span class="cell-name">{r['member']}</span></td>
        <td>GHS {fmt_num(r['m_monthly'])}</td>
        <td>GHS {fmt_num(r['m_weekly'])}</td>
        <td>{r['total_paid']} / {total_weeks}</td>
        <td>{badge}</td>
    </tr>"""

st.markdown(f"""
    <div class="glass-card">
        <div id="section-payments"></div><p class="sec-label">Members</p>
        <p class="sec-title">Contributions</p>
        <p class="sec-sub">Weekly targets and payment standing</p>
        <table class="data-table">
            <thead><tr><th>Member</th><th>Monthly</th><th>Weekly</th><th>Weeks Paid</th><th>Status</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
""", unsafe_allow_html=True)


# ── payout schedule card with progress bars ───────────────────────────────────
pay_rows_html = ""
for r in schedule_rows:
    bar_pct = min(r['pct'], 100)
    pay_rows_html += f"""<tr class="plain">
        <td><span class="cell-name">{r['turn']}</span></td>
        <td>{r['recipient']}</td>
        <td>{r['date']}</td>
        <td>GHS {r['fee']}</td>
        <td>
            GHS {r['pool']}
            <div class="pbar-wrap"><div class="pbar-fill" style="width:{bar_pct}%"></div></div>
        </td>
        <td>GHS {r['collected']}</td>
        <td>GHS {r['remaining']}</td>
    </tr>"""

st.markdown(f"""
    <div class="glass-card">
        <div id="section-payouts"></div><p class="sec-label">Rotation</p>
        <p class="sec-title">Payout Schedule</p>
        <p class="sec-sub">Dates, fees and collection progress per turn</p>
        <table class="data-table">
            <thead><tr><th>Turn</th><th>Recipient</th><th>Date</th><th>Admin Fee</th><th>Net Pool</th><th>Collected</th><th>Remaining</th></tr></thead>
            <tbody>{pay_rows_html}</tbody>
        </table>
    </div>
""", unsafe_allow_html=True)





# ── exports ───────────────────────────────────────────────────────────────────
# Weekly update
buf = io.StringIO()
buf.write(f"📌 *WK {current_elapsed_week} UPDATE*\n")
buf.write(f"💰 *Cash at Hand:* GHS {fmt_num(total_cash_held)}\n")
buf.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
buf.write("👥 *MEMBERS*\n")
for r in wa_contrib_rows:
    buf.write(f"{'✅' if 'Up' in r['standing'] else '❌'} *{r['member']}*: {r['standing']}\n")
buf.write("\n🎁 *PAYOUTS*\n")
for r in wa_payout_rows:
    buf.write(f"{r['recipient']} · {r['date']} · GHS {r['balance']}\n")

# Reminder — only owing members
owing_members = [r for r in wa_contrib_rows if "Owing" in r["standing"]]
rem = io.StringIO()
rem.write(f"🔔 *SUSU PAYMENT REMINDER — WK {current_elapsed_week}*\n\n")
if owing_members:
    rem.write("The following members have outstanding payments:\n\n")
    for r in owing_members:
        rem.write(f"❌ *{r['member']}*: {r['standing']}\n")
    rem.write(f"\nPlease make payment as soon as possible.\nNext payout: *{next_recipient}* on *{format_date(next_payout_date)}*\nThank you 🙏")
else:
    rem.write("✅ All members are up to date! Great work everyone 🎉")

# Onboarding
ob = io.StringIO()
ob.write("📋 *SUSU GROUP — ONBOARDING DETAILS*\n")
ob.write(f"🗓️ *Start Date:* {format_date(start_dt)}\n")
ob.write(f"🏁 *End Date:* {format_date(end_date)}\n\n")
ob.write("👤 *MEMBER DETAILS*\n")
for r in contrib_rows:
    ob.write(f"*{r['member']}*\n  • Monthly Tier: GHS {fmt_num(r['m_monthly'])}\n  • Weekly Target: GHS {fmt_num(r['m_weekly'])}\n\n")
ob.write("🎁 *PAYOUT SCHEDULE*\n")
ob_date = start_dt
for i in range(num_members):
    recipient   = members[i]
    payout_date = ob_date + timedelta(weeks=4)
    rm          = st.session_state.member_tiers.get(recipient, st.session_state.base_monthly)
    net         = rm * num_members * (1 - st.session_state.admin_fee_percentage/100.0)
    ob.write(f"*Month {i+1} — {recipient}*\n  • Payout Date: {format_date(payout_date)}\n  • Net Pool: GHS {fmt_num(net)}\n\n")
    ob_date = payout_date

# Contribution history
ch = io.StringIO()
ch.write(f"📊 *CONTRIBUTION HISTORY — WK {current_elapsed_week}*\n")
ch.write(f"🗓️ *Period:* {format_date(start_dt)} → {format_date(end_date)}\n\n")
for member in members:
    m_monthly = st.session_state.member_tiers.get(member, st.session_state.base_monthly)
    m_weekly  = m_monthly / 4.0
    m_pmts    = st.session_state.payments.get(member, {})
    ch.write(f"👤 *{member}* (GHS {fmt_num(m_weekly)}/wk)\n")
    for w in range(1, total_weeks + 1):
        paid  = m_pmts.get(str(w), False)
        icon  = "✅" if paid else ("⏳" if w > current_elapsed_week else "❌")
        label = "Paid" if paid else ("Upcoming" if w > current_elapsed_week else "Owing")
        ch.write(f"  Wk {w:02d}: {icon} {label}\n")
    ch.write("\n")

st.markdown(f"""
    <div class="glass-card">
        <div id="section-exports"></div><p class="sec-label">Export</p>
        <p class="sec-title">WhatsApp Messages</p>
        <p class="sec-sub">Ready-to-paste updates for the group chat</p>
    </div>
""", unsafe_allow_html=True)
dl_r1c1, dl_r1c2 = st.columns(2)
dl_r2c1, dl_r2c2 = st.columns(2)
with dl_r1c1: st.download_button("📥 Weekly Update",  data=buf.getvalue(), file_name=f"Susu_W{current_elapsed_week}.txt", mime="text/plain")
with dl_r1c2: st.download_button("🔔 Reminder",       data=rem.getvalue(), file_name=f"Susu_Reminder_W{current_elapsed_week}.txt", mime="text/plain")
with dl_r2c1: st.download_button("📋 Onboarding",     data=ob.getvalue(),  file_name="Susu_Onboarding.txt", mime="text/plain")
with dl_r2c2: st.download_button("📊 History",        data=ch.getvalue(),  file_name=f"Susu_History_W{current_elapsed_week}.txt", mime="text/plain")


# ── admin panel ───────────────────────────────────────────────────────────────
# section-admin anchor
st.markdown('<div id="section-admin"></div>', unsafe_allow_html=True)
st.markdown(f'<p class="sec-label" style="margin-top:24px">Admin</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-title">Group Controls</p>', unsafe_allow_html=True)
st.markdown('<p class="sec-sub">Update settings, record payments and payouts</p>', unsafe_allow_html=True)

with st.expander("⚙️  Group Settings"):
    c1,c2,c3 = st.columns(3)
    with c1: new_start = st.text_input("Start Date (YYYY-MM-DD)", value=st.session_state.start_date)
    with c2: new_base  = st.number_input("Base Monthly (GHS)", value=float(st.session_state.base_monthly), step=50.0)
    with c3: new_fee   = st.number_input("Admin Fee (%)", value=float(st.session_state.admin_fee_percentage), min_value=0.0, max_value=100.0, step=0.5)
    new_names = st.text_area("Members (comma-separated)", value=st.session_state.names_input)
    if st.button("Save Settings", key="save_settings"):
        st.session_state.start_date=new_start; st.session_state.base_monthly=new_base
        st.session_state.admin_fee_percentage=new_fee; st.session_state.names_input=new_names
        save_all(gsheet)
        append_log(gsheet,{"type":"setting","text":"Group settings updated","time":datetime.now().strftime("%d %b %Y %H:%M")})
        st.session_state.last_sync=datetime.now()
        st.success("✓ Settings saved."); st.rerun()

with st.expander("💰  Custom Member Tiers"):
    tier_cols = st.columns(min(num_members,4))
    new_tiers = {}
    for idx,m in enumerate(members):
        with tier_cols[idx%4]:
            new_tiers[m] = st.number_input(m, value=float(st.session_state.member_tiers.get(m, st.session_state.base_monthly)), step=50.0, key=f"tier_{m}")
    if st.button("Save Tiers", key="save_tiers"):
        st.session_state.member_tiers=new_tiers; save_all(gsheet)
        append_log(gsheet,{"type":"setting","text":"Member tiers updated","time":datetime.now().strftime("%d %b %Y %H:%M")})
        st.session_state.last_sync=datetime.now()
        st.success("✓ Tiers saved."); st.rerun()

with st.expander("📝  Bulk Payment Entry"):
    st.markdown(f'<p style="font-size:12px;color:{T["sub_color"]};margin-bottom:4px">Current week: <strong style="color:{T["sec_title"]}">Week {current_elapsed_week}</strong> of {total_weeks}. Check all weeks paid for each member then save once.</p>', unsafe_allow_html=True)
    bulk_payments = {}
    for member in members:
        m_pmts = st.session_state.payments.get(member, {})
        st.markdown(f'<div style="font-size:12px;font-weight:600;color:{T["td_color"]};margin:10px 0 6px">{member}</div>', unsafe_allow_html=True)
        cols = st.columns(min(total_weeks, 8))
        week_vals = {}
        for w in range(1, total_weeks+1):
            with cols[(w-1) % 8]:
                is_cur = w == current_elapsed_week
                label  = f"W{w}*" if is_cur else f"W{w}"
                week_vals[str(w)] = st.checkbox(label, value=m_pmts.get(str(w), False), key=f"bulk_{member}_{w}")
        bulk_payments[member] = week_vals
    if st.button("Save All Payments", key="bulk_save"):
        st.session_state.payments = bulk_payments
        save_all(gsheet)
        total_checked = sum(sum(1 for v in wv.values() if v) for wv in bulk_payments.values())
        append_log(gsheet,{"type":"payment","text":f"Bulk payment update — {total_checked} weeks marked paid","time":datetime.now().strftime("%d %b %Y %H:%M")})
        st.session_state.last_sync=datetime.now()
        st.success("✓ All payments saved."); st.rerun()

with st.expander("🎁  Record Payout"):
    month_options = [f"Month {i+1} — {members[i]}" for i in range(num_members)]
    sel_month_lbl = st.selectbox("Payout Turn", month_options, key="payout_month")
    mkey      = sel_month_lbl.split(" —")[0]
    rec_idx   = int(mkey.split(" ")[1]) - 1
    rec_name  = members[rec_idx]
    rec_m     = st.session_state.member_tiers.get(rec_name, st.session_state.base_monthly)
    net_v     = rec_m * num_members * (1 - st.session_state.admin_fee_percentage/100.0)
    cur_col   = float(st.session_state.payout_status.get(mkey,{}).get("amount_collected",0.0))
    new_col   = st.number_input(f"Amount Collected for {rec_name} (max GHS {fmt_num(net_v)})", value=cur_col, min_value=0.0, max_value=float(net_v), step=50.0, key="payout_amt")

    # ── confirmation dialog (feature 6) ──────────────────────────────────────
    if not st.session_state.get("confirm_payout", False):
        if st.button("Save Payout", key="save_payout_btn"):
            st.session_state.confirm_payout = True
            st.rerun()
    else:
        st.warning(f"⚠️ Confirm: Record GHS {fmt_num(new_col)} payout for {rec_name} ({mkey})?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✓ Yes, confirm", key="confirm_yes"):
                if mkey not in st.session_state.payout_status: st.session_state.payout_status[mkey]={}
                st.session_state.payout_status[mkey]["amount_collected"]=new_col
                save_all(gsheet)
                append_log(gsheet,{"type":"payout","text":f"{mkey} payout recorded for {rec_name} — GHS {fmt_num(new_col)}","time":datetime.now().strftime("%d %b %Y %H:%M")})
                st.session_state.last_sync=datetime.now()
                st.session_state.confirm_payout=False
                st.success(f"✓ Payout for {rec_name} saved."); st.rerun()
        with cc2:
            if st.button("✗ Cancel", key="confirm_no", type="secondary"):
                st.session_state.confirm_payout=False
                st.rerun()

if st.session_state.history:
    with st.expander("🕒  Activity Log"):
        dot_map = {"payment":"log-dot","payout":"log-dot log-dot-payout","setting":"log-dot log-dot-setting"}
        log_html = ""
        for entry in st.session_state.history[:20]:
            dot_class = dot_map.get(entry.get("type","payment"),"log-dot")
            log_html += f"""<div class="log-entry">
                <div class="{dot_class}"></div>
                <div class="log-text"><strong>{entry.get('text','—')}</strong></div>
                <div class="log-time">{entry.get('time','')}</div>
            </div>"""
        st.markdown(log_html, unsafe_allow_html=True)

# ── logout ────────────────────────────────────────────────────────────────────
st.markdown('<div class="gdivider"></div>', unsafe_allow_html=True)
if st.button("🔒  Lock Dashboard", key="logout", type="secondary"):
    st.session_state.authenticated = False
    st.rerun()

# Bottom navigation bar
st.markdown(f'''
    <div class="bottom-nav">
        <button class="nav-item" onclick="navTo(\'top\')"><span class="nav-icon">🏠</span><span class="nav-label">Home</span></button>
        <button class="nav-item" onclick="navTo(\'section-payments\')"><span class="nav-icon">👥</span><span class="nav-label">Members</span></button>
        <button class="nav-item" onclick="navTo(\'section-payouts\')"><span class="nav-icon">🎁</span><span class="nav-label">Payouts</span></button>
        <button class="nav-item" onclick="navTo(\'section-exports\')"><span class="nav-icon">📤</span><span class="nav-label">Export</span></button>
        <button class="nav-item" onclick="navTo(\'section-admin\')"><span class="nav-icon">⚙️</span><span class="nav-label">Admin</span></button>
    </div>
''', unsafe_allow_html=True)
st.markdown('<div class="foot">Backed by Google Sheets · Secured with passcode</div>', unsafe_allow_html=True)
