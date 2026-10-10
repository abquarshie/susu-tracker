"""Susu Savings — rotating-savings group tracker backed by Google Sheets.

Layout of this file
  1. constants, helpers, CSS
  2. storage   (chunked JSON blob, cached worksheet handles, rev-guarded commits)
  3. model     (Group: every derived figure, built once per run from the blob)
  4. mutations (small helpers shared by every money-moving form)
  5. UI        (lock screen, dashboard, exports, group controls)
"""
import hashlib
import html as htmllib
import io
import json
import re
import secrets as pysecrets
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Susu Savings", page_icon="💸", layout="wide",
                   initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# 1. CONSTANTS, HELPERS, CSS
# ══════════════════════════════════════════════════════════════════════════════
GH_TZ               = ZoneInfo("Africa/Accra")
SESSION_TIMEOUT_MIN = 30
STALE_MIN           = 5
MAX_FAILS, LOCK_SEC = 5, 60
SCOPES      = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
DATA_WS     = "susu_data"
BACKUP_WS   = "susu_backups"
BACKUP_KEEP = 30
CHUNK       = 45_000          # Google Sheets caps one cell at 50,000 characters
ADMIN_NAME  = "Abre"
METHODS     = ["Cash", "MoMo", "Bank transfer", "Other"]
LEGACY_WS   = ["settings", "tiers", "payments", "payout_status", "history", "snapshots", "passcode"]
EPS         = 0.005
DEFAULT_SETTINGS = {"start_date": "2026-08-17", "base_monthly": 1000, "admin_fee_percentage": 0.0,
                    "names_input": "Alice, Bob, Charlie, Diana, Frank, Grace"}


def esc(x):
    """Escape anything user-typed before it goes into raw HTML."""
    return htmllib.escape(str(x), quote=True)


def html(s):
    """Render HTML. Leading indentation is stripped so Markdown never turns it into a code block."""
    st.markdown(re.sub(r"\n[ \t]+", "\n", s).strip(), unsafe_allow_html=True)


def money(x):
    return round(float(x or 0) + 1e-9, 2)


def fmt_num(v):
    v = money(v)
    return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"


def format_date(dt):
    d = dt.day
    sfx = "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    return f"{d}{sfx} {dt.strftime('%b %Y')}"


def format_short(dt):
    return f"{dt.day} {dt.strftime('%b')}"


def now_dt():
    return datetime.now(GH_TZ)


def now_str():
    return now_dt().strftime("%d %b %Y %H:%M")


def parse_display_date(txt):
    if not txt:
        return None
    try:
        return datetime.strptime(re.sub(r"(\d+)(st|nd|rd|th)", r"\1", str(txt)).strip(), "%d %b %Y").date()
    except ValueError:
        return None


def greeting():
    h = now_dt().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def new_id(prefix):
    return f"{prefix}-{now_dt():%Y%m%d%H%M%S}-{pysecrets.token_hex(3).upper()}"


def who():
    return st.session_state.get("admin_name", ADMIN_NAME)


# ── passwords: salted scrypt; legacy SHA-256 and plaintext still accepted, then upgraded
def hash_pw(pw):
    salt = pysecrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def is_scrypt_hash(v):
    return isinstance(v, str) and v.startswith("scrypt$16384$8$1$") and len(v.split("$")) == 6


def check_pw(entered, stored):
    if not entered or not isinstance(stored, str) or not stored:
        return False
    if is_scrypt_hash(stored):
        try:
            _, n, r, p, salt, digest = stored.split("$")
            got = hashlib.scrypt(entered.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                                 dklen=len(bytes.fromhex(digest)))
            return pysecrets.compare_digest(got.hex(), digest)
        except Exception:
            return False
    if len(stored) == 64 and all(c in "0123456789abcdef" for c in stored):
        return pysecrets.compare_digest(hashlib.sha256(entered.encode()).hexdigest(), stored)
    return pysecrets.compare_digest(entered, stored)


def flash(msg, kind="success"):
    st.session_state.flash = (msg, kind)


def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        st.toast(f[0], icon={"success": "✅", "warning": "⚠️"}.get(f[1], "ℹ️"))


def wa_block(text, fname, key):
    html('<p class="copy-hint">Tap the copy icon at the top right of the box, then paste into WhatsApp.</p>')
    st.code(text, language=None)
    st.download_button("Download as .txt", data=text, file_name=fname, mime="text/plain", key=key,
                       use_container_width=True)


def bootstrap_pw():
    try:
        return str(st.secrets["app"]["admin_passcode"])
    except Exception:
        return ""


BOOTSTRAP_PW = bootstrap_pw()

# Colours, inputs and menus come from .streamlit/config.toml; this sheet only adds layout and components.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Instrument+Serif&display=swap');
:root{--canvas:#141619;--panel:#1B1E22;--panel-2:#23272C;--line:rgba(255,255,255,.10);--line-soft:rgba(255,255,255,.06);
 --ink:#ECEEF0;--ink-2:#A2AAB2;--ink-3:#767E86;--brass:#E8B15C;--paid:#5BC490;--short:#E8795A;
 --r-sm:8px;--r-md:12px;--r-lg:18px;--ease:cubic-bezier(.4,0,.2,1);--dur:.16s;}
header[data-testid="stHeader"],#MainMenu,footer,.stDeployButton,[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
.block-container{padding:0 clamp(12px,2vw,36px) 3rem!important;max-width:min(1160px,96vw)!important;}
html,body,[class*="css"]{font-family:'Instrument Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased;}
*:focus-visible{outline:2px solid var(--brass);outline-offset:2px;border-radius:4px;}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}
.serif{font-family:'Instrument Serif',Georgia,serif;font-weight:400;}
.note{font-size:13px;color:var(--ink-2);line-height:1.6;margin:4px 0 10px;}
.note b{color:var(--ink);font-weight:600;}

/* lock screen */
.lock-card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);padding:40px 36px;
 max-width:380px;margin:56px auto 12px;}
.lock-card .icon{font-size:34px;display:block;margin-bottom:16px;}
.lock-card h1{font-family:'Instrument Serif',Georgia,serif;font-size:32px;font-weight:400;color:var(--ink);margin:0 0 8px;}
.lock-card p{font-size:14px;color:var(--ink-2);margin:0;line-height:1.5;}

/* top bar + page head */
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:13px;color:var(--ink-2);padding:14px 2px 12px;}
.topbar b{color:var(--ink);font-weight:600;} .topbar .r{color:var(--ink-3);}
.dot{width:6px;height:6px;background:var(--paid);border-radius:50%;display:inline-block;margin-right:8px;animation:pulse 2.4s infinite;}
@keyframes pulse{50%{opacity:.35}}
.pagehead{padding:18px 2px 20px;border-top:1px solid var(--line-soft);}
.pagehead h1{font-family:'Instrument Serif',Georgia,serif;font-size:38px;font-weight:400;color:var(--ink);margin:0 0 8px;line-height:1.08;letter-spacing:-.015em;}
.pagehead p{font-size:14px;color:var(--ink-2);margin:0;} .pagehead b{color:var(--ink);}

/* panels */
.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;margin-bottom:14px;}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);padding:22px 24px;display:flex;flex-direction:column;min-width:0;
 transition:border-color var(--dur) var(--ease);}
.panel:hover{border-color:rgba(255,255,255,.16);}
.label{font-size:13px;color:var(--ink-2);margin:0 0 10px;}
.cash{font-family:'Instrument Serif',Georgia,serif;font-size:40px;line-height:1;color:var(--ink);letter-spacing:-.02em;white-space:nowrap;}
.cash small{font-size:18px;color:var(--ink-2);margin-right:8px;letter-spacing:0;}
.split{display:flex;height:8px;border-radius:99px;overflow:hidden;background:var(--line-soft);margin:16px 0 10px;}
.split i{display:block;height:100%;}
.legend,.key{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12.5px;color:var(--ink-2);}
.legend span,.key span{display:inline-flex;align-items:center;gap:7px;}
.legend i,.key i{width:10px;height:10px;border-radius:3px;display:inline-block;}
.key{color:var(--ink-3);margin:12px 0 2px;}
.spark{width:100%;height:46px;display:block;overflow:visible;margin-top:auto;padding-top:18px;}
.cash-foot{margin-top:14px;padding-top:14px;border-top:1px solid var(--line-soft);display:flex;flex-wrap:wrap;gap:10px 18px;font-size:12.5px;color:var(--ink-2);}
.ok{color:var(--paid);} .warn{color:var(--brass);} .bad{color:var(--short);}
.panel-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;}
.next-name{font-family:'Instrument Serif',Georgia,serif;font-size:27px;color:var(--ink);line-height:1.1;margin-bottom:4px;}
.next-when{font-size:13.5px;color:var(--ink-2);margin-bottom:18px;}
.next-amount{font-size:22px;font-weight:600;color:var(--ink);font-variant-numeric:tabular-nums;}
.chip{font-size:12px;font-weight:600;color:var(--ink-2);border:1px solid var(--line);border-radius:99px;padding:3px 11px;white-space:nowrap;}
.chip.soon{color:var(--brass);border-color:rgba(232,177,92,.4);background:rgba(232,177,92,.1);}
.chip.clear{color:var(--paid);border-color:rgba(91,196,144,.35);background:rgba(91,196,144,.1);}
.fund-row{display:flex;justify-content:space-between;font-size:13px;color:var(--ink-2);margin-top:auto;padding-top:16px;}
.fund-row b{color:var(--ink);}
.meter{height:6px;border-radius:99px;background:var(--line-soft);overflow:hidden;margin-top:8px;}
.meter i{display:block;height:100%;background:var(--brass);border-radius:99px;}
.meter.full i{background:var(--paid);}
.fund-note{font-size:12.5px;color:var(--ink-3);margin-top:8px;line-height:1.45;}

/* rotation rail */
.rail-wrap{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);padding:20px 24px;margin-bottom:26px;}
.rail{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;scroll-snap-type:x proximity;}
.turn{flex:1 0 132px;border-top:2px solid var(--line);padding-top:12px;display:flex;flex-direction:column;scroll-snap-align:start;}
.turn.done{border-top-color:var(--paid);} .turn.now{border-top-color:var(--brass);}
.turn .no{font-size:12px;color:var(--ink-3);margin-bottom:5px;}
.turn .nm{font-size:15px;font-weight:600;color:var(--ink);margin-bottom:3px;}
.turn.upcoming .nm{color:var(--ink-2);font-weight:500;}
.turn .dt{font-size:12.5px;color:var(--ink-3);}
.turn .stt{font-size:12.5px;margin:6px 0 9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink-3);}
.turn.done .stt{color:var(--paid);} .turn.now .stt{color:var(--brass);}
.turn .tm{height:4px;border-radius:99px;background:var(--line-soft);margin-top:auto;overflow:hidden;}
.turn .tm i{display:block;height:100%;background:var(--ink-3);}
.turn.done .tm i{background:var(--paid);} .turn.now .tm i{background:var(--brass);}

/* sections */
.section{margin-bottom:28px;}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;padding-bottom:12px;border-bottom:1px solid var(--line);margin-bottom:4px;}
.section-head h2{font-size:19px;font-weight:600;color:var(--ink);margin:0 0 4px;letter-spacing:-.01em;}
.section-head p{font-size:13px;color:var(--ink-2);margin:0;}
.quiet-link{font-size:13px;font-weight:600;color:var(--brass)!important;text-decoration:none!important;border-bottom:1px solid rgba(232,177,92,.35);}
.anchor{position:relative;top:-70px;display:block;height:0;}

/* member strips */
.mrow{display:grid;grid-template-columns:minmax(130px,.6fr) minmax(220px,2fr) minmax(96px,auto);gap:20px;align-items:center;
 padding:14px 10px;margin:0 -10px;border-bottom:1px solid var(--line-soft);border-radius:var(--r-sm);}
.mrow:hover{background:rgba(255,255,255,.025);}
.mrow.head{padding-bottom:8px;border-bottom:1px solid var(--line);} .mrow.head:hover{background:none;}
.mname{font-size:15px;font-weight:600;color:var(--ink);display:flex;align-items:center;gap:9px;}
.avatar{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;
 background:rgba(232,177,92,.14);color:var(--brass);font-size:12px;font-weight:600;flex-shrink:0;}
.mmeta{font-size:12.5px;color:var(--ink-3);margin-top:3px;}
.strip,.scale{display:grid;gap:3px;min-width:0;}
.wk{height:17px;border-radius:3px;background:rgba(255,255,255,.055);}
.wk.paid{background:var(--paid);} .wk.part{background:rgba(91,196,144,.42);}
.wk.owed{background:rgba(232,121,90,.1);box-shadow:inset 0 0 0 1px rgba(232,121,90,.55);}
.wk.exempt{background:transparent;box-shadow:inset 0 0 0 1px var(--line-soft);}
.wk.end{margin-right:6px;} .wk.now{outline:1.5px solid var(--brass);outline-offset:1.5px;}
.scale span{font-size:11.5px;color:var(--ink-3);border-left:1px solid var(--line);padding-left:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.scale span.on{color:var(--brass);border-left-color:rgba(232,177,92,.55);}
.mstat{display:flex;flex-direction:column;align-items:flex-end;gap:6px;}
.tag{font-size:11.5px;color:var(--ink-3);font-weight:500;margin-left:7px;}
.b-ok,.b-owe,.b-dim{font-size:13px;font-weight:600;white-space:nowrap;font-variant-numeric:tabular-nums;}
.b-ok{color:var(--paid);} .b-owe{color:var(--short);} .b-dim{color:var(--ink-3);font-weight:500;}
.streak{background:rgba(232,121,90,.14);color:var(--short);border:1px solid rgba(232,121,90,.32);border-radius:99px;padding:1px 8px;font-size:11.5px;font-weight:600;}
.owing{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;padding:14px 18px;font-size:13.5px;color:var(--ink-2);
 border-radius:var(--r-md);margin:16px 0 6px;background:rgba(232,121,90,.09);border:1px solid rgba(232,121,90,.26);}
.owing b{color:var(--short);font-size:18px;font-variant-numeric:tabular-nums;}
.owing.clear{background:rgba(91,196,144,.06);border-color:rgba(91,196,144,.2);}

/* tables */
.data-table{width:100%;border-collapse:collapse;}
.data-table th{font-size:12.5px;font-weight:500;color:var(--ink-3);padding:12px 12px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;}
.data-table td{font-size:14.5px;color:#CFD4D9;padding:13px 12px;border-bottom:1px solid var(--line-soft);vertical-align:middle;font-variant-numeric:tabular-nums;}
.data-table tr:last-child td{border-bottom:none;}
.data-table tbody tr:hover{background:rgba(255,255,255,.025);}
.data-table .num{text-align:right;}
.cell-name{font-weight:600;color:var(--ink);} .cell-sub{font-size:12px;color:var(--ink-3);margin-top:3px;}
.days{color:var(--ink-3);font-size:12px;} .days.urgent{color:var(--brass);}
.pbar{margin-top:7px;background:var(--line-soft);border-radius:99px;height:4px;overflow:hidden;}
.pbar i{display:block;height:4px;background:var(--paid);}
.funded{font-size:12px;color:var(--paid);margin-top:4px;}
.swipe-hint{display:none;font-size:12.5px;color:var(--ink-3);margin:8px 0 0;}

/* activity log */
.log{display:flex;align-items:flex-start;gap:12px;padding:11px 0;border-bottom:1px solid var(--line-soft);}
.log:last-child{border-bottom:none;}
.log .d{width:6px;height:6px;border-radius:50%;background:var(--brass);margin-top:7px;flex-shrink:0;}
.log .d.payout{background:var(--ink-2);} .log .d.setting{background:var(--paid);}
.log .t{font-size:14px;color:var(--ink-2);line-height:1.5;} .log .t strong{color:var(--ink);}
.log .w{font-size:12px;color:var(--ink-3);margin-left:auto;white-space:nowrap;padding-left:12px;}
.sub{font-size:12.5px;color:var(--ink-2);}
.copy-hint{font-size:13px;color:var(--ink-2);margin:-4px 0 8px;}
.foot{text-align:center;font-size:12.5px;color:var(--ink-3);margin-top:28px;padding-top:20px;border-top:1px solid var(--line-soft);}

/* Streamlit components */
.stButton>button,.stFormSubmitButton>button{border-radius:var(--r-sm)!important;font-weight:600!important;padding:10px 20px!important;
 transition:filter var(--dur) var(--ease),transform var(--dur) var(--ease)!important;}
.stButton>button[kind="primary"],.stFormSubmitButton>button{color:#17191C!important;}
.stButton>button:active,.stFormSubmitButton>button:active{transform:scale(.98);}
div[data-testid="stDownloadButton"]>button{background:transparent!important;color:var(--brass)!important;border:1px solid rgba(232,177,92,.4)!important;border-radius:var(--r-sm)!important;font-weight:600!important;}
div[data-testid="stForm"]{border:none!important;padding:0!important;}
details[data-testid="stExpander"]{background:var(--panel)!important;border:1px solid var(--line)!important;border-radius:var(--r-md)!important;margin-bottom:10px!important;}
details[data-testid="stExpander"] summary{padding:14px 18px!important;}
details[data-testid="stExpander"] summary p{font-size:15px!important;font-weight:600!important;}
.stTabs [data-baseweb="tab"]{padding:10px 4px;margin-right:18px;font-size:14px;}
.stTabs [aria-selected="true"]{font-weight:600;}

@media (max-width:900px){.hero{grid-template-columns:1fr;}}
@media (max-width:700px){.mrow{grid-template-columns:1fr auto;gap:12px;}.mstat{grid-row:1;grid-column:2;}.strip,.scale{grid-row:2;grid-column:1/-1;}}
@media (max-width:600px){
 .pagehead h1{font-size:29px;} .panel{padding:18px 16px;} .cash{font-size:32px;} .next-name{font-size:22px;}
 .rail-wrap{padding:16px;} .turn{flex:0 0 118px;} .wk{height:15px;} .scale .dt{display:none;}
 .data-table{display:block;overflow-x:auto;white-space:nowrap;}
 .data-table th,.data-table td{padding:10px!important;font-size:13.5px!important;}
 .tbl-payout .hide-sm{display:none;} .swipe-hint{display:block;}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. STORAGE — one JSON blob split across column A, rev-guarded writes
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    return gspread.authorize(creds).open(st.secrets["sheet"]["name"])


@st.cache_resource
def get_ws(title):
    """Worksheet handles are cached: sheet.worksheet() is itself an API call."""
    sh = get_sheet()
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=20, cols=26)


def blank_blob():
    return {"rev": 0, "settings": dict(DEFAULT_SETTINGS), "tiers": {}, "payments": {}, "payout_status": {},
            "history": [], "snapshots": {}, "member_status": {}, "payment_ledger": [],
            "payment_transactions": [], "payout_ledger": [], "reconciliations": [], "passcode": ""}


def _month_keys_to_turn(ps):
    return {(f"Turn {k.split(' ', 1)[1]}" if str(k).startswith("Month ") else str(k)): v for k, v in (ps or {}).items()}


def _normalise(b):
    for k, v in blank_blob().items():
        b.setdefault(k, v)
    for k, v in DEFAULT_SETTINGS.items():
        b["settings"].setdefault(k, v)
    b["payout_status"] = {**_month_keys_to_turn(b["payout_status"]), **b["payout_status"]}
    return b


def _dumps(b):
    return json.dumps(b, separators=(",", ":"), ensure_ascii=False)


def _chunks(raw):
    return [raw[i:i + CHUNK] for i in range(0, len(raw), CHUNK)] or [""]


def migrate_legacy():
    """One-time: fold the old one-worksheet-per-key layout into a single blob."""
    sh, b = get_sheet(), blank_blob()
    existing = {ws.title for ws in sh.worksheets()}

    def rd(title, default):
        if title not in existing:
            return default
        try:
            return json.loads(sh.worksheet(title).acell("A1").value or "")
        except Exception:
            return default

    if set(LEGACY_WS) & existing:
        for key in ("settings", "tiers", "payments", "history", "snapshots"):
            b[key] = rd(key, b[key])
        b["payout_status"] = _month_keys_to_turn(rd("payout_status", {}))
        b["passcode"] = rd("passcode", "")
        b["history"].insert(0, {"type": "setting", "text": "Data migrated to single-blob storage",
                                "who": "system", "time": now_str()})
    if not b["passcode"] and BOOTSTRAP_PW:
        b["passcode"] = hash_pw(BOOTSTRAP_PW)
    return _normalise(b)


def read_blob_fresh():
    """Uncached read. Chunks run down column A until the first empty cell."""
    parts = []
    for v in get_ws(DATA_WS).col_values(1):
        if not v:
            break
        parts.append(v)
    if not parts:
        b = migrate_legacy()
        write_blob(b)
        return b
    try:
        return _normalise(json.loads("".join(parts)))
    except json.JSONDecodeError:
        # Never overwrite data we cannot read — that would wipe the group.
        st.error(f"The group record in '{DATA_WS}' could not be read. Nothing has been changed. "
                 f"Restore a copy from the '{BACKUP_WS}' worksheet, then reload.")
        st.stop()


@st.cache_data(ttl=60, show_spinner=False)
def read_blob_cached():
    return read_blob_fresh()


def write_blob(b):
    chunks = _chunks(_dumps(b))
    ws = get_ws(DATA_WS)
    need = len(chunks) + 1
    if ws.row_count < need:
        ws.add_rows(need - ws.row_count)
    # one trailing blank marks the end, so stale chunks beyond it are ignored on read
    ws.update(range_name=f"A1:A{need}", values=[[c] for c in chunks] + [[""]], value_input_option="RAW")
    write_backup(b)
    read_blob_cached.clear()


def write_backup(b):
    """Best-effort snapshot; trimming runs every 10th revision to save API calls."""
    try:
        chunks = _chunks(_dumps(b))
        ws = get_ws(BACKUP_WS)
        if ws.col_count < len(chunks) + 2:
            ws.add_cols(len(chunks) + 2 - ws.col_count)
        ws.append_row([now_str(), b.get("rev", 0), *chunks], value_input_option="RAW")
        if b.get("rev", 0) % 10 == 0:
            n = len(ws.col_values(1))
            if n > BACKUP_KEEP:
                ws.delete_rows(1, n - BACKUP_KEEP)
    except Exception:
        pass


def list_backups():
    """[(row, when, rev)] newest first. Reads only columns A:B, not the blobs."""
    try:
        vals = get_ws(BACKUP_WS).get("A:B")
        return [(i + 1, r[0], r[1]) for i, r in enumerate(vals) if len(r) >= 2][::-1]
    except Exception:
        return []


def read_backup(row_no):
    try:
        return json.loads("".join(get_ws(BACKUP_WS).row_values(row_no)[2:]))
    except Exception:
        return None


def blob():
    return st.session_state.blob


def apply_blob(b):
    st.session_state.blob = b
    st.session_state.last_sync = now_dt()


def commit(mutate):
    """Re-read; refuse if someone else wrote since we loaded; else apply, log, bump rev, write."""
    current = read_blob_fresh()
    if current.get("rev", 0) != blob().get("rev", 0):
        apply_blob(current)
        flash("Someone else updated the group since you loaded this page. Your view has been refreshed. "
              "Please re-apply your change.", "warning")
        return False
    entries = mutate(current) or []
    for e in [entries] if isinstance(entries, dict) else entries:
        e.setdefault("who", who())
        e.setdefault("time", now_str())
        current["history"].insert(0, e)
    current["history"] = current["history"][:80]
    current["rev"] = current.get("rev", 0) + 1
    write_blob(current)
    apply_blob(current)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 3. MODEL — every derived figure, computed once per run
# ══════════════════════════════════════════════════════════════════════════════
def ps_collected(ps):
    """Amount a recipient has taken for a turn (older releases used other key names)."""
    return money(ps.get("collected", ps.get("disbursed_amount", ps.get("amount_collected", 0.0))))


class Group:
    def __init__(self, b, today):
        s = b["settings"]
        self.b, self.today = b, today
        self.members = [n.strip() for n in str(s["names_input"]).split(",") if n.strip()]
        self.n = len(self.members)
        self.weeks = self.n * 4                       # fixed rotation: exits never shift dates
        self.base = float(s["base_monthly"])
        self.fee_pct = float(s["admin_fee_percentage"])
        self.fee = self.fee_pct / 100
        self.start = datetime.strptime(s["start_date"], "%Y-%m-%d").replace(tzinfo=GH_TZ)
        self.end = self.start + timedelta(weeks=self.weeks)
        self.week = 0 if today < self.start else min((today - self.start).days // 7 + 1, self.weeks)
        self.tiers = b.get("tiers", {})
        self.status = b.get("member_status", {})

        # Index transactions once: every lookup below is O(1) instead of a scan of the whole list.
        self.txs = defaultdict(list)
        for tx in b.get("payment_transactions", []):
            self.txs[(tx.get("member"), int(tx.get("week", 0) or 0))].append(tx)
        grid = b.get("payments", {})
        self.amt = {}
        for m in self.members:
            wk = self.weekly(m)
            for w in range(1, self.weeks + 1):
                rows = self.txs.get((m, w))
                if rows:   # transactions are the source of truth
                    self.amt[m, w] = money(sum(float(t.get("amount", 0) or 0) for t in rows
                                               if t.get("status", "completed") == "completed"))
                else:      # legacy tick with no transaction = full weekly target
                    self.amt[m, w] = wk if grid.get(m, {}).get(str(w)) else 0.0

        self.collected = money(sum(self.amt.values()))
        self.paid_out = money(sum(self.turn_collected(f"Turn {i + 1}") for i in range(self.n)))
        self.cash_held = money(self.collected - self.paid_out)
        self.paid_ahead = money(sum(v for (m, w), v in self.amt.items() if w > self.week))
        self.rows = [self._member_row(m) for m in self.members]
        self.gap = money(sum(r["owing"] for r in self.rows))
        self.schedule = [self._turn_row(i, m) for i, m in enumerate(self.members)]
        self.next_turn = next((r for r in self.schedule if not r["done"]), None)
        self.next_by_date = next((r for r in self.schedule if r["date"] >= today), None)

    # lookups
    def tier(self, m):        return float(self.tiers.get(m, self.base))
    def weekly(self, m):      return money(self.tier(m) / 4)
    def paid_amount(self, m, w): return self.amt.get((m, w), 0.0)
    def paid(self, m, w):     return self.paid_amount(m, w) >= self.weekly(m) - EPS
    def exited(self, m):      return self.status.get(m, {}).get("status") == "exited"
    def exit_week(self, m):
        ew = self.status.get(m, {}).get("exit_week")
        return int(ew) if ew else self.weeks
    def liable(self, m, w):   return not (self.exited(m) and w > self.exit_week(m))
    def turn_collected(self, lbl): return ps_collected(self.b["payout_status"].get(lbl, {}))

    def _member_row(self, m):
        wk = self.weekly(m)
        due = [w for w in range(1, self.week + 1) if self.liable(m, w)]
        paid_so_far = money(sum(self.amt[m, w] for w in due))
        owing = money(max(0.0, len(due) * wk - paid_so_far))
        ex = self.exited(m)
        streak = 0
        if not (ex and owing <= 0):
            for w in range(min(self.week, self.exit_week(m)), 0, -1):
                if self.paid(m, w):
                    break
                streak += 1
        total_paid = sum(1 for w in range(1, self.weeks + 1) if self.paid(m, w))
        paid_due = sum(1 for w in due if self.paid(m, w))
        standing = f"Owing GHS {fmt_num(owing)}" if owing > 0 else ("Exited" if ex else "Up to date")
        return {"member": m, "weekly": wk, "owing": owing, "streak": streak, "exited": ex,
                "exit_week": self.status.get(m, {}).get("exit_week"), "ahead": total_paid - paid_due,
                "standing": standing}

    def _turn_row(self, i, m):
        lbl = f"Turn {i + 1}"
        date = self.start + timedelta(weeks=4 * (i + 1))
        gross = money(self.tier(m) * self.n)
        fee = money(gross * self.fee)
        net = money(gross - fee)
        col = self.turn_collected(lbl)
        funded = money(sum(self.amt[x, w] for x in self.members for w in range(4 * i + 1, 4 * i + 5)) * (1 - self.fee))
        ps = self.b["payout_status"].get(lbl, {})
        rem = money(max(0.0, net - col))
        return {"turn": lbl, "recipient": m, "date": date, "date_s": format_date(date), "fee": fee, "net": net,
                "collected": col, "remaining": rem, "funded": funded,
                "pct_funded": int(min(funded / net, 1) * 100) if net else 0,
                "pct_collected": int(min(col / net, 1) * 100) if net else 0,
                "done": bool(ps.get("disbursed")) or (col > 0 and col >= net - EPS),
                "disb_date": ps.get("disbursed_date", ""),
                "days": (date - self.today).days if date >= self.today else None,
                "early_ok": funded >= net - EPS and rem > 0 and date >= self.today,
                "exited": self.exited(m)}


# ══════════════════════════════════════════════════════════════════════════════
# 4. MUTATION HELPERS — shared by every form that moves money
# ══════════════════════════════════════════════════════════════════════════════
def _sync_week_flag(b, m, w):
    """Keep the legacy week tick in step with what is actually banked. Returns the banked amount."""
    banked = money(sum(float(t.get("amount", 0) or 0) for t in b["payment_transactions"]
                       if t.get("member") == m and int(t.get("week", 0) or 0) == w
                       and t.get("status", "completed") == "completed"))
    target = money(float(b["tiers"].get(m, b["settings"]["base_monthly"])) / 4)
    b["payments"].setdefault(m, {})[str(w)] = banked >= target - EPS
    return banked


def _ledger(b, **entry):
    entry.setdefault("time", now_str())
    b["payment_ledger"].insert(0, entry)
    b["payment_ledger"] = b["payment_ledger"][:500]


def add_payment(b, m, w, amount, method, reference, date, by):
    tx = {"id": new_id("PAY"), "member": m, "week": w, "amount": money(amount), "date": date,
          "time": now_str(), "method": method, "reference": reference, "status": "completed", "who": by}
    b["payment_transactions"].insert(0, tx)
    _ledger(b, member=m, week=w, amount=tx["amount"], action="paid", who=by, reference=reference, method=method)
    return tx, _sync_week_flag(b, m, w)


def _mark_reversed(row, by, reason):
    row.update(status="reversed", reversed_at=now_str(), reversed_by=by, reversal_reason=reason)


def reverse_week(b, m, w, by, reason):
    total = 0.0
    for t in b["payment_transactions"]:
        if t.get("member") == m and int(t.get("week", 0) or 0) == w and t.get("status", "completed") == "completed":
            _mark_reversed(t, by, reason)
            total += money(t.get("amount", 0))
    if total:
        _ledger(b, member=m, week=w, amount=money(total), action="reversed", who=by,
                reference=reason, method="", reason=reason)
    _sync_week_flag(b, m, w)
    return money(total)


def receipt_text(tx):
    return (f"🧾 *SUSU PAYMENT RECEIPT*\n\nMember: *{tx.get('member', '—')}*\nWeek: *{int(tx.get('week', 0)):02d}*\n"
            f"Amount: *GHS {fmt_num(tx.get('amount', 0))}*\nMethod: {tx.get('method', '—')}\n"
            f"Reference: {tx.get('reference') or '—'}\nDate: {tx.get('date') or '—'}\n"
            f"Recorded by: {tx.get('who', '—')}\nReceipt ID: {tx.get('id', '—')}\n\nThank you for your contribution 🙏")


def payout_receipt_text(p):
    return (f"🧾 *SUSU PAYOUT RECEIPT*\n\nRecipient: *{p.get('recipient', '—')}*\nTurn: *{p.get('turn', '—')}*\n"
            f"Amount: *GHS {fmt_num(p.get('amount', 0))}*\nMethod: {p.get('method', '—')}\n"
            f"Reference: {p.get('reference') or '—'}\nDate: {p.get('date') or '—'}\n"
            f"Recorded by: {p.get('who', '—')}\nReceipt ID: {p.get('id', '—')}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. UI
# ══════════════════════════════════════════════════════════════════════════════
try:
    get_sheet()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    st.stop()

if "blob" not in st.session_state:
    apply_blob(read_blob_cached())
    st.session_state.update(authenticated=False, admin_name=ADMIN_NAME, last_activity=now_dt(),
                            fails=0, locked_until=None)
elif (now_dt() - st.session_state.last_sync).total_seconds() > STALE_MIN * 60:
    apply_blob(read_blob_cached())

show_flash()

if st.session_state.authenticated:
    if (now_dt() - st.session_state.last_activity).total_seconds() > SESSION_TIMEOUT_MIN * 60:
        st.session_state.update(authenticated=False, admin_name=ADMIN_NAME)
        flash("Session timed out. Please unlock again.", "warning")
        st.rerun()
    st.session_state.last_activity = now_dt()

# ── lock screen ───────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    html("""<div class="lock-card"><span class="icon">💸</span><h1>Susu Savings</h1>
         <p>Enter your name and the group passcode. Every change you make is signed with your name.</p></div>""")
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        with st.form("unlock", border=False):
            name = st.text_input("Your name", placeholder="Your name", label_visibility="collapsed")
            pw = st.text_input("Passcode", type="password", placeholder="Passcode", label_visibility="collapsed")
            go = st.form_submit_button("Unlock", use_container_width=True, type="primary")
        if go:
            lock = st.session_state.locked_until
            stored = blob().get("passcode") or BOOTSTRAP_PW
            if lock and now_dt() < lock:
                st.error(f"Too many attempts. Try again in {int((lock - now_dt()).total_seconds())} seconds.")
            elif not stored:
                st.error("No admin passcode is configured. Add app.admin_passcode to Streamlit secrets first.")
            elif not name.strip():
                st.error("Enter your name. Every change is recorded against it.")
            elif check_pw(pw, stored):
                st.session_state.update(authenticated=True, admin_name=name.strip()[:40],
                                        last_activity=now_dt(), fails=0, locked_until=None)
                if not is_scrypt_hash(blob().get("passcode", "")):
                    commit(lambda b: b.__setitem__("passcode", hash_pw(pw)))
                st.rerun()
            else:
                st.session_state.fails += 1
                if st.session_state.fails >= MAX_FAILS:
                    st.session_state.update(fails=0, locked_until=now_dt() + timedelta(seconds=LOCK_SEC))
                st.error("That passcode is not correct.")
    st.stop()

# ── model ─────────────────────────────────────────────────────────────────────
try:
    g = Group(blob(), now_dt())
except ValueError:
    st.error("The start date in settings must be YYYY-MM-DD.")
    st.stop()
if g.n < 2:
    st.error("Please enter at least 2 member names.")
    st.stop()

if g.week > 0 and str(g.week) not in blob()["snapshots"]:
    def _snap(b, wk=g.week, val=g.cash_held):
        b["snapshots"][str(wk)] = val
    commit(_snap)

# ── top bar + page head ───────────────────────────────────────────────────────
sync_ago = int((now_dt() - st.session_state.last_sync).total_seconds() / 60)
c_bar, c_btn = st.columns([6, 1], vertical_alignment="center")
with c_bar:
    html(f"""<div class="topbar"><div><span class="dot"></span><b>Live</b> &nbsp;Synced
         {'just now' if sync_ago < 1 else f'{sync_ago} min ago'}</div>
         <div class="r">Signed in as {esc(who())}, revision {blob()['rev']}</div></div>""")
with c_btn:
    if st.button("Refresh", help="Reload from Google Sheets", use_container_width=True):
        read_blob_cached.clear()
        apply_blob(read_blob_fresh())
        flash("Refreshed from Google Sheets")
        st.rerun()

html(f"""<div class="pagehead"><h1>{greeting()}, {esc(who())}</h1>
     <p>Week <b>{g.week}</b> of {g.weeks} with {g.n} members. The cycle runs
     {format_date(g.start)} to {format_date(g.end)}.</p></div>""")


# ── hero ──────────────────────────────────────────────────────────────────────
def recon_line():
    recs = blob().get("reconciliations") or []
    if not recs:
        return '<span class="warn">Cash has never been counted against this balance</span>'
    rec = recs[0]
    rd = parse_display_date(rec.get("date", "")[:11])
    days = (g.today.date() - rd).days if rd else None
    when = ("today" if days == 0 else f"{days} days ago") if days is not None else esc(rec.get("date", ""))
    diff = money(rec.get("difference", 0))
    if abs(diff) < EPS:
        return f'<span class="ok">Counted {when}, matched exactly</span>'
    return f'<span class="warn">Last count was GHS {fmt_num(abs(diff))} {"over" if diff > 0 else "short"}, {when}</span>'


def sparkline():
    snaps = {**blob().get("snapshots", {}), str(g.week): g.cash_held}
    pts = sorted((int(w), money(v)) for w, v in snaps.items() if str(w).isdigit() and int(w) <= g.week)[-8:]
    if len(pts) < 2:
        return ""
    vals = [v for _, v in pts]
    lo, span = min(vals), (max(vals) - min(vals)) or 1
    W, H = 300, 46
    step = W / (len(vals) - 1)
    ys = [H - 2 - (v - lo) / span * (H - 6) for v in vals]
    poly = " ".join(f"{i * step:.1f},{y:.1f}" for i, y in enumerate(ys))
    return (f'<svg class="spark" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{poly}" fill="none" stroke="rgba(232,177,92,.85)" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{(len(vals) - 1) * step:.1f}" cy="{ys[-1]:.1f}" r="2.6" fill="#5BC490"/></svg>')


prev = blob().get("snapshots", {}).get(str(g.week - 1))
if prev is not None and g.week > 1:
    d = money(g.cash_held - float(prev))
    delta_html = (f'<span class="{"ok" if d >= 0 else "bad"}" style="font-weight:600">'
                  f'{"up" if d >= 0 else "down"} GHS {fmt_num(abs(d))}</span> since last week')
else:
    delta_html = "First week on record"

held_pct = max(0, min(100, int(g.cash_held / g.collected * 100))) if g.collected > 0 else 0
cash_panel = f"""<div class="panel"><p class="label">Cash in hand</p>
  <div class="cash"><small>GHS</small>{fmt_num(g.cash_held)}</div>
  <div class="split"><i style="width:{held_pct}%;background:var(--paid)"></i>
    <i style="width:{100 - held_pct}%;background:rgba(232,177,92,.55)"></i></div>
  <div class="legend"><span><i style="background:var(--paid)"></i>Held GHS {fmt_num(g.cash_held)}</span>
    <span><i style="background:rgba(232,177,92,.55)"></i>Paid out GHS {fmt_num(g.paid_out)}</span>
    <span>Collected GHS {fmt_num(g.collected)}</span></div>
  {sparkline() or '<div style="margin-top:auto"></div>'}
  <div class="cash-foot"><span>{delta_html}</span><span>{recon_line()}</span></div></div>"""

nt = g.next_turn
if nt:
    short = money(max(0.0, nt["net"] - nt["funded"]))
    if short <= 0:
        fund_note = f"GHS {fmt_num(nt['funded'])} banked. The full pool is ready to pay."
    elif not nt["days"]:
        fund_note = f"GHS {fmt_num(nt['funded'])} banked, GHS {fmt_num(short)} short with the date already here."
    else:
        wl = max(1, -(-nt["days"] // 7))
        fund_note = (f"GHS {fmt_num(short)} short. Collecting GHS {fmt_num(short / wl)} a week for the next "
                     f"{wl} week{'s' if wl > 1 else ''} closes it in time.")
    days_label = "past due" if nt["days"] is None else "today" if nt["days"] == 0 else f"in {nt['days']} days"
    chip = "soon" if nt["days"] is None or nt["days"] <= 7 else ""
    next_panel = f"""<div class="panel"><div class="panel-top"><p class="label" style="margin:0">Next payout</p>
      <span class="chip {chip}">{days_label}</span></div>
      <div class="next-name">{esc(nt['recipient'])}</div>
      <div class="next-when">{nt['date_s']}, closing {nt['turn'].lower()}</div>
      <div class="next-amount">GHS {fmt_num(nt['net'])}</div>
      <div class="fund-row"><span>Pool funded</span><b>{nt['pct_funded']}%</b></div>
      <div class="meter{' full' if nt['pct_funded'] >= 100 else ''}"><i style="width:{nt['pct_funded']}%"></i></div>
      <div class="fund-note">{fund_note}</div></div>"""
else:
    next_panel = """<div class="panel"><div class="panel-top"><p class="label" style="margin:0">Rotation</p>
      <span class="chip clear">complete</span></div><div class="next-name">Everyone has been paid</div>
      <div class="next-when">Every turn in this cycle has been collected in full.</div></div>"""

html(f'<div class="hero">{cash_panel}{next_panel}</div>')

# ── rotation rail ─────────────────────────────────────────────────────────────
rail = []
for r in g.schedule:
    if r["done"]:
        cls, state, bar = "done", "Collected in full", 100
    elif r is nt:
        cls, bar = "now", r["pct_funded"]
        state = (f"GHS {fmt_num(r['remaining'])} still to collect" if r["collected"] > 0
                 else f"{r['pct_funded']}% of GHS {fmt_num(r['net'])}")
    else:
        cls, bar = "upcoming", r["pct_funded"]
        state = f"{r['pct_funded']}% of GHS {fmt_num(r['net'])}" if r["funded"] > 0 else f"GHS {fmt_num(r['net'])} to raise"
    rail.append(f'<div class="turn {cls}"><div class="no">{r["turn"]}</div><div class="nm">{esc(r["recipient"])}</div>'
                f'<div class="dt">{format_short(r["date"])}</div><div class="stt">{state}</div>'
                f'<div class="tm"><i style="width:{bar}%"></i></div></div>')
html(f"""<div class="rail-wrap"><div class="section-head" style="border:none;padding-bottom:0;margin-bottom:16px">
     <div><h2>The rotation</h2><p>{sum(r['done'] for r in g.schedule)} of {g.n} turns collected.
     Each turn runs four weeks and the order never shifts.</p></div></div>
     <div class="rail">{''.join(rail)}</div></div>""")


# ── members ───────────────────────────────────────────────────────────────────
def week_cell(m, w):
    amt, tgt = g.paid_amount(m, w), g.weekly(m)
    extra = (" end" if w % 4 == 0 and w != g.weeks else "") + (" now" if w == g.week else "")
    if not g.liable(m, w) and amt <= 0:
        cls, tip = "exempt", "not owed"
    elif amt >= tgt - EPS:
        cls, tip = "paid", f"paid GHS {fmt_num(amt)}"
    elif amt > 0:
        cls, tip = "part", f"part paid, GHS {fmt_num(amt)} of {fmt_num(tgt)}"
    elif w <= g.week:
        cls, tip = "owed", "not paid"
    else:
        cls, tip = "", "not due yet"
    return f'<i class="wk {cls}{extra}" title="Week {w}: {tip}"></i>'


rows_html = []
for r in g.rows:
    m = r["member"]
    status = (f'<span class="b-owe">GHS {fmt_num(r["owing"])}</span>' if r["owing"] > 0
              else '<span class="b-dim">Left the group</span>' if r["exited"]
              else '<span class="b-ok">Up to date</span>')
    streak = f'<span class="streak">{r["streak"]} weeks behind</span>' if r["streak"] >= 2 else ""
    tag = f'<span class="tag">left week {r["exit_week"]}</span>' if r["exited"] and r["exit_week"] else ""
    meta = f'GHS {fmt_num(r["weekly"])} a week' + (f', {r["ahead"]} week{"s" if r["ahead"] > 1 else ""} ahead' if r["ahead"] > 0 else "")
    strip = "".join(week_cell(m, w) for w in range(1, g.weeks + 1))
    rows_html.append(f'<div class="mrow"><div><div class="mname"><span class="avatar">{esc(m[0].upper())}</span>{esc(m)}{tag}</div>'
                     f'<div class="mmeta">{meta}</div></div>'
                     f'<div class="strip" style="grid-template-columns:repeat({g.weeks},1fr)">{strip}</div>'
                     f'<div class="mstat">{status}{streak}</div></div>')

owing_rows = [r for r in g.rows if r["owing"] > 0]
ahead_note = f'<span>GHS {fmt_num(g.paid_ahead)} has been paid ahead.</span>' if g.paid_ahead > 0 else ""
if owing_rows:
    names = ", ".join(f"{esc(r['member'])} GHS {fmt_num(r['owing'])}" for r in owing_rows[:4])
    if len(owing_rows) > 4:
        names += f" and {len(owing_rows) - 4} more"
    owing_strip = (f'<div class="owing"><b>GHS {fmt_num(g.gap)}</b> outstanding to the end of week {g.week}: '
                   f'{names}.{ahead_note}</div>')
else:
    owing_strip = f'<div class="owing clear">Nothing outstanding. Everyone has paid up to week {g.week}.{ahead_note}</div>'

cur_turn = (g.week - 1) // 4 if g.week else -1
scale = "".join(f'<span class="{"on" if i == cur_turn else ""}">T{i + 1}<span class="dt"> pays {format_short(r["date"])}</span></span>'
                for i, r in enumerate(g.schedule))
html(f"""<div class="section"><div class="section-head"><div><h2>Members</h2>
     <p>Each block is one week of the cycle, running left to right.</p></div>
     <a class="quiet-link" href="#section-payments">Itemised entry</a></div>
     {owing_strip}
     <div class="key"><span><i style="background:var(--paid)"></i>Paid in full</span>
     <span><i style="background:rgba(91,196,144,.42)"></i>Part paid</span>
     <span><i style="background:rgba(232,121,90,.1);box-shadow:inset 0 0 0 1px rgba(232,121,90,.55)"></i>Owed</span>
     <span><i style="background:rgba(255,255,255,.055)"></i>Not due yet</span>
     <span><i style="box-shadow:inset 0 0 0 1px rgba(255,255,255,.1)"></i>Not owed</span>
     <span><i style="outline:1.5px solid var(--brass);outline-offset:1px"></i>This week</span></div>
     <div class="mrow head"><div></div><div class="scale" style="grid-template-columns:repeat({g.n},1fr)">{scale}</div><div></div></div>
     {''.join(rows_html)}</div>""")


# ── weekly bulk entry ─────────────────────────────────────────────────────────
def save_bulk(wk, adds, removes, method, pdate):
    by, d = who(), pdate.strftime("%d %b %Y")

    def _m(b):
        detail = []
        for m, amt in adds:
            if amt > 0:
                add_payment(b, m, wk, amt, method, "Bulk entry", d, by)
                detail.append(f"{m} Wk {wk:02d}: recorded GHS {fmt_num(amt)}")
        for m in removes:
            amt = reverse_week(b, m, wk, by, "Bulk untick")
            detail.append(f"{m} Wk {wk:02d}: " + (f"reversed GHS {fmt_num(amt)}" if amt else "earlier tick cleared"))
        return {"type": "payment", "text": f"Week {wk:02d} bulk entry: {len(adds)} recorded, {len(removes)} reversed",
                "detail": detail}

    if commit(_m):
        flash(f"Week {wk:02d} saved")
    st.rerun()


@st.dialog("Reverse payments?")
def confirm_bulk(wk, adds, removes, method, pdate):
    st.write(f"These members will be marked unpaid for week {wk:02d} and their payments reversed:")
    st.markdown("\n".join(f"- {m}" for m in removes))
    c1, c2 = st.columns(2)
    if c1.button("Confirm and save", type="primary", use_container_width=True):
        save_bulk(wk, adds, removes, method, pdate)
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


html('<span class="anchor" id="section-week"></span>')
with st.expander(f"Record week {max(1, g.week):02d} payments", expanded=True):
    st.caption("Tick everyone who has paid and save once. Each tick writes a payment with a receipt; "
               "unticking reverses it.")
    c1, c2, c3 = st.columns(3)
    bw = int(c1.number_input("Week", 1, g.weeks, max(1, g.week), key="bulk_week"))
    b_method = c2.selectbox("Method for new ticks", METHODS, key="bulk_method")
    b_date = c3.date_input("Payment date", g.today.date(), key="bulk_date")
    with st.form(f"bulk_form_{bw}", border=False):
        ticks, cols = {}, st.columns(2)
        for i, m in enumerate(g.members):
            have, tgt = g.paid_amount(m, bw), g.weekly(m)
            with cols[i % 2]:
                if not g.liable(m, bw) and have <= 0:
                    html(f'<div class="note">{esc(m)}: not owed</div>')
                    continue
                part = f" · GHS {fmt_num(have)} banked" if 0 < have < tgt else ""
                ticks[m] = st.checkbox(f"{m} · GHS {fmt_num(tgt)}{part}", value=g.paid(m, bw), key=f"bulk_{bw}_{m}")
        submitted = st.form_submit_button(f"Save week {bw:02d} payments", type="primary", use_container_width=True)
    if submitted:
        adds = [(m, money(g.weekly(m) - g.paid_amount(m, bw))) for m, t in ticks.items() if t and not g.paid(m, bw)]
        removes = [m for m, t in ticks.items() if not t and g.paid(m, bw)]
        if removes:
            confirm_bulk(bw, adds, removes, b_method, b_date)
        elif adds:
            save_bulk(bw, adds, removes, b_method, b_date)
        else:
            st.toast("No changes to save", icon="ℹ️")

# ── payout schedule ───────────────────────────────────────────────────────────
show_fee = g.fee > 0
trs = []
for r in g.schedule:
    if r["done"]:
        badge = '<span class="b-ok">Collected</span>' + (f'<div class="cell-sub">{r["disb_date"]}</div>' if r["disb_date"] else "")
    elif r["collected"] > 0:
        badge = '<span class="b-owe">Part collected</span>'
    else:
        badge = '<span class="b-dim">Not yet due</span>'
    days = (f'<div class="days{" urgent" if r["days"] <= 7 else ""}">{r["days"]} days away</div>'
            if r["days"] is not None else '<div class="cell-sub">Passed</div>')
    trs.append(
        f'<tr><td><span class="cell-name">{r["turn"]}</span></td>'
        f'<td>{esc(r["recipient"])}{"<span class=tag>left the group</span>" if r["exited"] else ""}</td>'
        f'<td>{r["date_s"]}{days}</td>'
        + (f'<td class="num hide-sm">GHS {fmt_num(r["fee"])}</td>' if show_fee else "")
        + f'<td class="num">GHS {fmt_num(r["net"])}{"<div class=funded>Fully funded</div>" if r["early_ok"] else ""}'
          f'<div class="pbar"><i style="width:{r["pct_collected"]}%"></i></div></td>'
          f'<td class="num hide-sm">GHS {fmt_num(r["collected"])}</td><td class="num">GHS {fmt_num(r["remaining"])}</td>'
          f'<td>{badge}</td></tr>')
html(f"""<div class="section"><div class="section-head"><div><h2>Payout schedule</h2>
     <p>Collected is what the recipient has taken. Remaining is what the group still owes them.</p></div>
     <a class="quiet-link" href="#section-payouts">Record a payout</a></div>
     <table class="data-table tbl-payout"><thead><tr><th>Turn</th><th>Recipient</th><th>Date</th>
     {'<th class="num hide-sm">Admin fee</th>' if show_fee else ''}<th class="num">Net pool</th>
     <th class="num hide-sm">Collected</th><th class="num">Remaining</th><th>Status</th></tr></thead>
     <tbody>{''.join(trs)}</tbody></table>
     <p class="swipe-hint">Swipe sideways for the full breakdown.</p></div>""")


# ── WhatsApp exports ──────────────────────────────────────────────────────────
def export_weekly():
    out = [f"📌 *SUSU WEEK {g.week} UPDATE*", f"💰 *Cash held:* GHS {fmt_num(g.cash_held)}",
           f"📥 *Collected:* GHS {fmt_num(g.collected)}", f"🎁 *Paid out:* GHS {fmt_num(g.paid_out)}",
           f"🏁 *Cycle:* Week {g.week} of {g.weeks}", "", "👥 *MEMBER STANDING*"]
    for r in g.rows:
        if r["exited"] and r["owing"] <= 0:
            out.append(f"⚪ *{r['member']}*: Exited")
            continue
        streak = f" · 🔴 {r['streak']} weeks behind" if r["streak"] >= 2 else ""
        out.append(f"{'✅' if r['owing'] <= 0 else '❌'} *{r['member']}*: {r['standing']}{streak}")
    out += ["", "🎁 *PAYOUTS*"]
    out += [f"*{r['recipient']}* · {r['date_s']}" + (" · ✅ fully collected" if r["done"]
            else f" · GHS {fmt_num(r['remaining'])} remaining") for r in g.schedule]
    if g.next_by_date:
        out += ["", f"➡️ *Next payout:* {g.next_by_date['recipient']} on {g.next_by_date['date_s']}"]
    out += ["", "Thank you everyone for keeping the susu on track 🙏"]
    return "\n".join(out)


def export_reminder():
    head = f"🔔 *SUSU PAYMENT REMINDER — WEEK {g.week}*\n\n"
    if not owing_rows:
        return head + "✅ *Everyone is up to date this week!* 🎉\n\nThank you all for staying on track 🙏"
    body = "Hi everyone 👋 A quick reminder for members with outstanding contributions:\n\n"
    body += "\n".join(f"• ❌ *{r['member']}*: {r['standing']}" for r in owing_rows)
    if g.next_by_date:
        body += (f"\n\nPlease settle your outstanding amount when you can so we can keep the next payout on schedule.\n"
                 f"🎁 *Next payout:* {g.next_by_date['recipient']} · {g.next_by_date['date_s']}")
    return head + body + "\n\nThank you 🙏"


def export_onboarding():
    out = ["📋 *SUSU GROUP — ONBOARDING DETAILS*", "", f"🗓️ *Start:* {format_date(g.start)}",
           f"🏁 *End:* {format_date(g.end)}", f"👥 *Members:* {g.n}", f"🔄 *Cycle:* {g.weeks} weeks", "",
           "ℹ️ *HOW IT WORKS*", "• Contributions are weekly.", "• Each turn lasts exactly 4 weeks.",
           "• Payout dates are fixed by the rotation schedule."]
    if g.fee:
        out.append(f"• An admin fee of {fmt_num(g.fee_pct)}% is deducted from each payout.")
    out += ["", "👤 *MEMBER TARGETS*"] + [f"*{r['member']}* — GHS {fmt_num(r['weekly'])}/week" for r in g.rows if not r["exited"]]
    out += ["", "🎁 *PAYOUT SCHEDULE*"] + [f"*{r['turn']} — {r['recipient']}* · {r['date_s']} · GHS {fmt_num(r['net'])}"
                                           for r in g.schedule]
    return "\n".join(out)


def export_history():
    out = [f"📊 *SUSU CONTRIBUTION HISTORY — WEEK {g.week}*",
           f"🗓️ *Period:* {format_date(g.start)} → {format_date(g.end)}", ""]
    for m in g.members:
        out.append(f"👤 *{m}*{' (exited)' if g.exited(m) else ''} · GHS {fmt_num(g.weekly(m))}/wk")
        for w in range(1, g.weeks + 1):
            amt = g.paid_amount(m, w)
            if not g.liable(m, w) and amt <= 0:
                s = "⚪ Exempt"
            elif g.paid(m, w):
                s = "✅ Paid"
            elif amt > 0:
                s = f"🟡 Partial · GHS {fmt_num(amt)} of {fmt_num(g.weekly(m))}"
            else:
                s = "⏳ Upcoming" if w > g.week else "❌ Owing"
            out.append(f"  Wk {w:02d}: {s}")
        out.append("")
    return "\n".join(out)


html("""<div class="section" style="margin-bottom:8px"><div class="section-head"><div><h2>Share with the group</h2>
     <p>Ready-to-send WhatsApp messages, built from the figures above.</p></div></div></div>""")
t1, t2, t3, t4 = st.tabs(["Weekly update", "Reminder", "Onboarding", "History"])
with t1: wa_block(export_weekly(), f"Susu_W{g.week}.txt", "dl_weekly")
with t2: wa_block(export_reminder(), f"Susu_Reminder_W{g.week}.txt", "dl_rem")
with t3: wa_block(export_onboarding(), "Susu_Onboarding.txt", "dl_ob")
with t4: wa_block(export_history(), f"Susu_History_W{g.week}.txt", "dl_hist")


# ── group controls ────────────────────────────────────────────────────────────
def save_payout(r, new_amt, coll_date, method, ref):
    tkey, rec, net = r["turn"], r["recipient"], r["net"]
    dstr = format_date(coll_date) if new_amt > 0 else ""
    by = who()

    def _m(b):
        ps = b["payout_status"].setdefault(tkey, {})
        before = ps_collected(ps)
        delta = money(new_amt - before)
        if money(Group(b, now_dt()).cash_held - delta) < -EPS:   # checked against the fresh record
            raise ValueError("would overdraw the group")
        ps.pop("amount_collected", None)
        ps.pop("disbursed_amount", None)
        full = new_amt > 0 and money(new_amt) >= net - EPS
        ps.update(collected=money(new_amt), disbursed=full, disbursed_date=dstr)
        if delta > 0:
            b["payout_ledger"].insert(0, {"id": new_id("PAYOUT"), "turn": tkey, "recipient": rec, "amount": delta,
                                          "date": dstr, "method": method, "reference": ref, "who": by, "time": now_str()})
            b["payout_ledger"] = b["payout_ledger"][:500]
        text = (f"{tkey} fully collected by {rec}: GHS {fmt_num(new_amt)}" if full
                else f"{tkey} part collected by {rec}: GHS {fmt_num(new_amt)} of GHS {fmt_num(net)}")
        return {"type": "payout", "text": text,
                "detail": [f"{tkey} collected: GHS {fmt_num(before)} → GHS {fmt_num(new_amt)}",
                           f"balance owed to {rec}: GHS {fmt_num(net - new_amt)}",
                           f"method: {method}", f"date: {dstr or '—'}"]}

    try:
        if commit(_m):
            flash(f"Payout for {rec} saved")
    except ValueError:
        flash("Save cancelled. That payout would overdraw the group's cash.", "warning")
    st.rerun()


@st.dialog("Confirm payout")
def confirm_payout(r, new_amt, coll_date, method, ref):
    st.write(f"**{r['recipient']}** ({r['turn']}) has collected **GHS {fmt_num(new_amt)}** of "
             f"GHS {fmt_num(r['net'])} as at {format_date(coll_date)}.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, save it", type="primary", use_container_width=True):
        save_payout(r, new_amt, coll_date, method, ref)
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def save_settings(vals, changes):
    def _m(b):
        b["settings"] = dict(vals)
        return {"type": "setting", "text": "Group settings updated", "detail": changes}
    if commit(_m):
        flash("Settings saved")
    st.rerun()


@st.dialog("Change the cycle structure?")
def confirm_settings(vals, changes, structural):
    st.write(f"This changes {', '.join(structural)}. Payment history is kept, but payout dates or the rotation "
             f"order can move. Confirm only if that is intended.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm change", type="primary", use_container_width=True):
        save_settings(vals, changes)
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Restore backup")
def confirm_restore(row_no, when, rev):
    st.warning(f"Restoring replaces the current record (rev {blob()['rev']}) with the one saved at {when}. "
               f"Anything recorded since will be lost. The current state is backed up first.")
    txt = st.text_input("Type RESTORE to confirm")
    if st.button("Restore this backup", type="primary", use_container_width=True):
        if txt.strip().upper() != "RESTORE":
            st.error("Type RESTORE in the box to confirm.")
            return
        snap = read_backup(row_no)
        if not snap or str(snap.get("rev")) != str(rev):
            st.error("That backup could not be read, or the list is out of date. Reload the list and try again.")
            return
        old = read_blob_fresh()
        write_backup(old)
        snap = _normalise(snap)
        snap["rev"] = old.get("rev", 0) + 1
        snap["history"].insert(0, {"type": "setting", "who": who(), "time": now_str(),
                                   "text": f"Restored backup from {when} (rev {rev})",
                                   "detail": [f"replaced rev {old.get('rev', 0)}"]})
        write_blob(snap)
        apply_blob(snap)
        st.session_state.pop("backup_list", None)
        flash("Backup restored", "warning")
        st.rerun()


def log_html(entries, dot_of, title_of, sub_of):
    return "".join(f'<div class="log"><div class="d {dot_of(e)}"></div><div class="t"><strong>{esc(title_of(e))}</strong>'
                   f'{"".join(f"<div class=sub>{esc(s)}</div>" for s in sub_of(e))}</div>'
                   f'<div class="w">{esc(e.get("time", e.get("date", "")))}</div></div>' for e in entries)


html('<span class="anchor" id="section-admin"></span><div class="section" style="margin:30px 0 8px">'
     '<div class="section-head"><div><h2>Group controls</h2>'
     '<p>Record money in and out, then manage settings and tools.</p></div></div></div>')
tab_money, tab_settings, tab_tools = st.tabs(["Money", "Settings", "Tools"])

with tab_money:
    html('<span class="anchor" id="section-payments"></span>')
    with st.expander("Record a payment", expanded=True):
        st.caption("Partial, late, multiple and corrected payments are all supported.")
        c1, c2 = st.columns(2)
        pm = c1.selectbox("Member", g.members, key="tx_member")
        pw_ = int(c2.number_input("Week", 1, g.weeks, max(1, g.week), key="tx_week"))
        target, already = g.weekly(pm), g.paid_amount(pm, pw_)
        html(f'<div class="note">Weekly target is <b>GHS {fmt_num(target)}</b>. Already recorded for week '
             f'{pw_:02d}: <b>GHS {fmt_num(already)}</b>.</div>')
        with st.form(f"pay_form_{pm}_{pw_}", border=False, clear_on_submit=True):
            c3, c4 = st.columns(2)
            amount = c3.number_input("Amount received (GHS)", min_value=0.0, step=10.0,
                                     value=float(money(target - already) if already < target else target))
            method = c4.selectbox("Payment method", METHODS)
            c5, c6 = st.columns(2)
            ref = c5.text_input("Reference or note", placeholder="MoMo ref, bank ref, or cash note")
            pdate = c6.date_input("Payment date", g.today.date())
            ok = st.form_submit_button("Save payment", type="primary", use_container_width=True)
        if ok:
            if amount <= 0:
                st.error("Enter an amount greater than zero.")
            else:
                def _m(b, m=pm, w=pw_, a=amount, meth=method, rf=ref.strip(), d=pdate.strftime("%d %b %Y")):
                    tx, banked = add_payment(b, m, w, a, meth, rf, d, who())
                    return {"type": "payment", "text": f"Payment received: {m} · Week {w:02d} · GHS {fmt_num(a)}",
                            "detail": [f"method: {meth}", f"reference: {rf or '—'}",
                                       f"banked for the week: GHS {fmt_num(banked)} of {fmt_num(target)}",
                                       f"receipt: {tx['id']}"]}
                if commit(_m):
                    flash(f"Payment saved for {pm}")
                st.rerun()

    with st.expander("Payment receipts"):
        txs = blob()["payment_transactions"][:15]
        if not txs:
            st.info("Receipts appear here once you record a payment.")
        else:
            i = st.selectbox("Receipt", range(len(txs)), key="rcpt_pick", format_func=lambda n: (
                f"{txs[n].get('member')} · Wk {int(txs[n].get('week', 0)):02d} · GHS {fmt_num(txs[n].get('amount', 0))} · "
                f"{txs[n].get('date', '')}" + (" · reversed" if txs[n].get("status") != "completed" else "")))
            wa_block(receipt_text(txs[i]), f"Receipt_{txs[i].get('id')}.txt", "dl_receipt")

    html('<span class="anchor" id="section-payouts"></span>')
    with st.expander("Record a payout"):
        labels = [f"{r['turn']} — {r['recipient']}" for r in g.schedule]
        sr = g.schedule[st.selectbox("Payout turn", range(len(labels)), format_func=labels.__getitem__, key="po_turn")]
        html(f'<div class="note">Net pool due to {esc(sr["recipient"])}: <b>GHS {fmt_num(sr["net"])}</b> · '
             f'Collected so far: <b>GHS {fmt_num(sr["collected"])}</b> · Still owed: <b>GHS {fmt_num(sr["remaining"])}</b><br>'
             f'Contributions banked for this turn: <b>GHS {fmt_num(sr["funded"])}</b> · '
             f'Group cash held: <b>GHS {fmt_num(g.cash_held)}</b></div>')
        if sr["funded"] < sr["net"] - EPS and sr["remaining"] > 0:
            st.warning(f"Only GHS {fmt_num(sr['funded'])} of the GHS {fmt_num(sr['net'])} pool has been contributed. "
                       f"Paying the full amount now draws on the group's other cash.")
        with st.form(f"po_form_{sr['turn']}", border=False):
            c1, c2 = st.columns(2)
            new_amt = c1.number_input(f"Total collected by {sr['recipient']} (GHS)", min_value=0.0,
                                      max_value=float(sr["net"]), value=float(sr["collected"]), step=50.0,
                                      help="Running total, not just today's instalment.")
            coll_date = c2.date_input("Date collected", parse_display_date(sr["disb_date"]) or g.today.date())
            c3, c4 = st.columns(2)
            po_method = c3.selectbox("Payout method", METHODS)
            po_ref = c4.text_input("Payout reference or note", placeholder="MoMo ref, bank ref, or cash note")
            go = st.form_submit_button("Save payout", type="primary", use_container_width=True)
        if go:
            cash_after = money(g.cash_held - (new_amt - sr["collected"]))
            if abs(new_amt - sr["collected"]) < EPS:
                st.toast("No change to save", icon="ℹ️")
            elif cash_after < -EPS:
                st.error(f"The group only holds GHS {fmt_num(g.cash_held)}. This would leave it "
                         f"GHS {fmt_num(-cash_after)} short. Record outstanding payments first, or enter a smaller amount.")
            else:
                confirm_payout(sr, money(new_amt), coll_date, po_method, po_ref.strip())

    with st.expander("Payout receipts"):
        pl = blob()["payout_ledger"][:15]
        if not pl:
            st.info("Record a payout to generate its receipt.")
        else:
            i = st.selectbox("Receipt", range(len(pl)), key="po_rcpt_pick", format_func=lambda n: (
                f"{pl[n].get('recipient')} · {pl[n].get('turn')} · GHS {fmt_num(pl[n].get('amount', 0))} · {pl[n].get('date', '')}"
                + (" · reversed" if pl[n].get("status") == "reversed" else "")))
            wa_block(payout_receipt_text(pl[i]), f"Payout_{pl[i].get('id')}.txt", "dl_po_receipt")

    with st.expander("Undo or correct a record"):
        st.caption("The original record is kept and marked, never deleted. A reason is required and goes into the audit trail.")
        kind = st.segmented_control("Record type", ["Payment", "Payout"], default="Payment", key="corr_kind")
        if kind == "Payment":
            active = [t for t in blob()["payment_transactions"] if t.get("status", "completed") == "completed"]
            if not active:
                st.info("No active payment records to correct.")
            else:
                with st.form("corr_pay", border=False):
                    idx = st.selectbox("Payment", range(len(active)), format_func=lambda n: (
                        f"{active[n].get('member')} · Wk {int(active[n].get('week', 0)):02d} · "
                        f"GHS {fmt_num(active[n].get('amount', 0))} · {active[n].get('date', '')}"))
                    action = st.radio("Action", ["Reverse", "Correct amount"], horizontal=True)
                    new_amount = st.number_input("Correct amount (GHS), used only for Correct amount", min_value=0.0, step=10.0)
                    reason = st.text_input("Reason", placeholder="Why is this being corrected?")
                    ok = st.form_submit_button("Save correction", type="primary", use_container_width=True)
                if ok:
                    if not reason.strip():
                        st.error("Enter a reason.")
                    else:
                        def _m(b, rid=active[idx]["id"], action=action, new=money(new_amount), reason=reason.strip(), by=who()):
                            row = next((t for t in b["payment_transactions"]
                                        if t.get("id") == rid and t.get("status", "completed") == "completed"), None)
                            if not row:
                                return None
                            m, w, old = row["member"], int(row["week"]), money(row.get("amount", 0))
                            if action == "Reverse":
                                _mark_reversed(row, by, reason)
                                act, amt, text = "reversed", old, f"Payment reversed: {m} · Week {w:02d} · GHS {fmt_num(old)}"
                            else:
                                row.update(amount=new, corrected_at=now_str(), corrected_by=by, correction_reason=reason)
                                act, amt, text = "corrected", new, f"Payment corrected: {m} · Week {w:02d} · GHS {fmt_num(old)} → GHS {fmt_num(new)}"
                            banked = _sync_week_flag(b, m, w)
                            _ledger(b, member=m, week=w, amount=amt, action=act, who=by,
                                    reference=row.get("reference", ""), method=row.get("method", ""), reason=reason)
                            return {"type": "payment", "text": text,
                                    "detail": [f"receipt: {rid}", f"reason: {reason}",
                                               f"still banked for the week: GHS {fmt_num(banked)}"]}
                        if commit(_m):
                            flash("Correction saved", "warning")
                        st.rerun()
        elif kind == "Payout":
            active = [p for p in blob()["payout_ledger"] if p.get("status", "active") != "reversed"]
            if not active:
                st.info("No active payout records to reverse.")
            else:
                st.warning("Only reverse a payout recorded in error. The amount is added back to group cash.")
                with st.form("corr_po", border=False):
                    idx = st.selectbox("Payout", range(len(active)), format_func=lambda n: (
                        f"{active[n].get('recipient')} · {active[n].get('turn')} · "
                        f"GHS {fmt_num(active[n].get('amount', 0))} · {active[n].get('date', '')}"))
                    reason = st.text_input("Reason", placeholder="Why is this payout being reversed?")
                    ok = st.form_submit_button("Reverse this payout", type="primary", use_container_width=True)
                if ok:
                    if not reason.strip():
                        st.error("Enter a reason.")
                    else:
                        pools = {r["turn"]: r["net"] for r in g.schedule}

                        def _m(b, pid=active[idx]["id"], reason=reason.strip(), by=who()):
                            p = next((x for x in b["payout_ledger"]
                                      if x.get("id") == pid and x.get("status", "active") != "reversed"), None)
                            if not p:
                                return None
                            _mark_reversed(p, by, reason)
                            turn, amt = p.get("turn"), money(p.get("amount", 0))
                            ps = b["payout_status"].setdefault(turn, {})
                            cur = ps_collected(ps)
                            new = money(max(0.0, cur - amt))
                            ps.update(collected=new, disbursed=new > 0 and new >= pools.get(turn, 0) - EPS)
                            if new <= 0:
                                ps["disbursed_date"] = ""
                            return {"type": "payout", "text": f"Payout reversed: {p.get('recipient')} · {turn} · GHS {fmt_num(amt)}",
                                    "detail": [f"receipt: {pid}", f"reason: {reason}",
                                               f"{turn} collected: GHS {fmt_num(cur)} → GHS {fmt_num(new)}"]}
                        if commit(_m):
                            flash("Payout reversed", "warning")
                        st.rerun()

with tab_settings:
    s = blob()["settings"]
    with st.expander("Group settings"):
        with st.form("settings_form", border=False):
            c1, c2, c3 = st.columns(3)
            new_start = c1.text_input("Start date (YYYY-MM-DD)", value=s["start_date"])
            new_base = c2.number_input("Base monthly (GHS)", value=float(s["base_monthly"]), step=50.0)
            new_fee = c3.number_input("Admin fee (%)", value=float(s["admin_fee_percentage"]), min_value=0.0,
                                      max_value=100.0, step=0.5)
            new_names = st.text_area("Members (comma-separated)", value=s["names_input"])
            html('<p class="note">Payment records are kept when you add or reorder members. To remove someone '
                 'mid-cycle use Member status; deleting the name here shifts every payout date.</p>')
            ok = st.form_submit_button("Save settings", type="primary", use_container_width=True)
        if ok:
            try:
                datetime.strptime(new_start, "%Y-%m-%d")
            except ValueError:
                st.error("Date format must be YYYY-MM-DD.")
            else:
                changes, structural = [], []
                if new_start != s["start_date"]:
                    changes.append(f"start date {s['start_date']} → {new_start}")
                    structural.append("the start date")
                if float(new_base) != float(s["base_monthly"]):
                    changes.append(f"base monthly {fmt_num(s['base_monthly'])} → {fmt_num(new_base)}")
                if float(new_fee) != float(s["admin_fee_percentage"]):
                    changes.append(f"admin fee {s['admin_fee_percentage']}% → {new_fee}%")
                if new_names.strip() != str(s["names_input"]).strip():
                    changes.append("member list edited")
                    structural.append("the member list")
                vals = {"start_date": new_start, "base_monthly": float(new_base),
                        "admin_fee_percentage": float(new_fee), "names_input": new_names}
                if not changes:
                    st.toast("No setting changes", icon="ℹ️")
                elif structural:
                    confirm_settings(vals, changes, structural)
                else:
                    save_settings(vals, changes)

    with st.expander("Custom member tiers"):
        with st.form("tiers_form", border=False):
            cols, new_tiers = st.columns(min(g.n, 4)), {}
            for i, m in enumerate(g.members):
                new_tiers[m] = cols[i % 4].number_input(m, value=g.tier(m), step=50.0, key=f"tier_{m}")
            ok = st.form_submit_button("Save tiers", type="primary", use_container_width=True)
        if ok:
            diffs = [f"{m}: GHS {fmt_num(g.tier(m))} → GHS {fmt_num(v)}" for m, v in new_tiers.items() if float(v) != g.tier(m)]
            if not diffs:
                st.toast("No tier changes", icon="ℹ️")
            else:
                def _m(b):
                    b["tiers"].update({k: float(v) for k, v in new_tiers.items()})
                    return {"type": "setting", "text": f"Member tiers updated ({len(diffs)} changed)", "detail": diffs}
                if commit(_m):
                    flash("Tiers saved")
                st.rerun()

    with st.expander("Member status"):
        html('<p class="note">Mark a member as exited instead of deleting them. Their history and rotation slot stay; '
             'they stop owing from the exit week onward.</p>')
        sm = st.selectbox("Member", g.members, key="status_member")
        with st.form(f"status_form_{sm}", border=False):
            c1, c2 = st.columns(2)
            new_status = c1.selectbox("Status", ["active", "exited"], index=int(g.exited(sm)))
            new_exit = c2.number_input("Exit week", 1, g.weeks,
                                       int(g.status.get(sm, {}).get("exit_week") or max(1, g.week)))
            ok = st.form_submit_button("Save member status", type="primary", use_container_width=True)
        if ok:
            before = g.status.get(sm, {"status": "active", "exit_week": None})
            after = {"status": new_status, "exit_week": int(new_exit) if new_status == "exited" else None}
            if before == after:
                st.toast("No change", icon="ℹ️")
            else:
                def _m(b):
                    b["member_status"][sm] = after
                    txt = f"{sm} marked exited from week {new_exit}" if new_status == "exited" else f"{sm} reinstated as active"
                    return {"type": "setting", "text": txt,
                            "detail": [f"{sm}: {before.get('status', 'active')} → {after['status']}"]}
                if commit(_m):
                    flash("Member status saved")
                st.rerun()

    with st.expander("Change passcode"):
        with st.form("pw_form", border=False, clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            old_pw = c1.text_input("Current passcode", type="password")
            pw1 = c2.text_input("New passcode", type="password")
            pw2 = c3.text_input("Confirm new passcode", type="password")
            ok = st.form_submit_button("Update passcode", type="primary", use_container_width=True)
        if ok:
            if not check_pw(old_pw, blob().get("passcode") or BOOTSTRAP_PW):
                st.error("The current passcode is not correct.")
            elif len(pw1) < 8:
                st.error("The new passcode must be at least 8 characters.")
            elif pw1 != pw2:
                st.error("The two new passcodes do not match.")
            else:
                if commit(lambda b: (b.__setitem__("passcode", hash_pw(pw1)), {"type": "setting", "text": "Passcode changed"})[1]):
                    flash("Passcode updated")
                st.rerun()

with tab_tools:
    with st.expander("Member profile"):
        pm = st.selectbox("Member", g.members, key="profile_member")
        prow = next(r for r in g.rows if r["member"] == pm)
        c1, c2, c3 = st.columns(3)
        c1.metric("Weekly target", f"GHS {fmt_num(g.weekly(pm))}")
        c2.metric("Banked to date", f"GHS {fmt_num(sum(g.paid_amount(pm, w) for w in range(1, g.weeks + 1)))}")
        c3.metric("Outstanding", f"GHS {fmt_num(prow['owing'])}")
        ptxs = [t for t in blob()["payment_transactions"] if t.get("member") == pm][:20]
        if ptxs:
            for t in ptxs:
                st.markdown(f"**Week {int(t.get('week', 0)):02d} · GHS {fmt_num(t.get('amount', 0))}** · "
                            f"{t.get('method', '—')} · {t.get('date', '')} · {t.get('reference') or 'no reference'}"
                            + (" · *reversed*" if t.get("status") != "completed" else ""))
        else:
            st.info("No itemised transactions yet. Any amounts above come from the legacy week grid.")

    with st.expander("Cash reconciliation"):
        html(f'<div class="note">System cash held: <b>GHS {fmt_num(g.cash_held)}</b>. Enter the physical cash plus '
             f'verified MoMo or bank balance actually held by the group.</div>')
        actual = st.number_input("Actual cash or account balance (GHS)", min_value=0.0, value=float(g.cash_held),
                                 step=10.0, key=f"recon_actual_{blob()['rev']}")
        diff = money(actual - g.cash_held)
        if abs(diff) < EPS:
            st.success("Reconciled. The actual balance matches the system.")
        elif diff > 0:
            st.warning(f"GHS {fmt_num(diff)} more than the system balance.")
        else:
            st.error(f"GHS {fmt_num(-diff)} less than the system balance.")
        note = st.text_input("Reconciliation note", key="recon_note", placeholder="e.g. Cash counted and MoMo balance checked")
        if st.button("Save reconciliation", type="primary", key="save_recon"):
            def _m(b):
                b["reconciliations"].insert(0, {"date": now_str(), "actual": money(actual), "system": g.cash_held,
                                                "difference": diff, "note": note.strip(), "who": who()})
                b["reconciliations"] = b["reconciliations"][:100]
                return {"type": "setting", "text": f"Cash reconciled: actual GHS {fmt_num(actual)} vs system GHS {fmt_num(g.cash_held)}",
                        "detail": [f"difference: GHS {fmt_num(diff)}", f"note: {note.strip() or '—'}"]}
            if commit(_m):
                flash("Reconciliation recorded")
            st.rerun()
        recs = blob()["reconciliations"][:5]
        if recs:
            html(log_html(recs, lambda e: "setting",
                          lambda e: f"Actual GHS {fmt_num(e.get('actual', 0))} vs system GHS {fmt_num(e.get('system', 0))}",
                          lambda e: [f"difference GHS {fmt_num(e.get('difference', 0))}" + (f" · {e['note']}" if e.get("note") else "")]))

    with st.expander("Convert legacy weeks"):
        st.caption("Weeks recorded as a plain tick, before receipts existed, count towards the totals but have no "
                   "transaction behind them. Converting writes one transaction per week so every cedi has a record.")
        legacy = [(m, w, g.weekly(m)) for m in g.members for w in range(1, g.weeks + 1)
                  if blob()["payments"].get(m, {}).get(str(w)) and not g.txs.get((m, w))]
        if not legacy:
            st.success("Nothing to convert. Every paid week already has a transaction.")
        else:
            per = defaultdict(int)
            for m, _, _ in legacy:
                per[m] += 1
            html(f'<div class="note"><b>{len(legacy)} week(s)</b> · GHS {fmt_num(sum(a for *_, a in legacy))} across '
                 + ", ".join(f"{esc(m)} ({c})" for m, c in per.items()) + "</div>")
            conv_method = st.selectbox("Record these as", METHODS, key="convert_method")
            if st.button("Convert to transactions", type="primary", key="convert_legacy"):
                def _m(b, pairs=legacy, method=conv_method, by=who()):
                    for m, w, amt in pairs:
                        b["payment_transactions"].insert(0, {"id": new_id("PAY"), "member": m, "week": w, "amount": money(amt),
                                                             "date": "", "time": now_str(), "method": method,
                                                             "reference": "Converted from week grid", "status": "completed",
                                                             "who": by})
                    detail = [f"{m} Wk {w:02d}: GHS {fmt_num(a)}" for m, w, a in pairs[:12]]
                    if len(pairs) > 12:
                        detail.append(f"…and {len(pairs) - 12} more")
                    return {"type": "payment", "text": f"Converted {len(pairs)} legacy week(s) to transactions", "detail": detail}
                if commit(_m):
                    flash(f"{len(legacy)} week(s) converted")
                st.rerun()

    with st.expander("Backups"):
        st.caption(f"A copy of the whole group record is saved to the {BACKUP_WS} worksheet on every change. "
                   f"Roughly the last {BACKUP_KEEP} are kept.")
        if st.button("Load backup list", key="load_backups"):
            st.session_state.backup_list = list_backups()
        bl = st.session_state.get("backup_list")
        if bl is None:
            st.info("Load the backup list to read it from Google Sheets.")
        elif not bl:
            st.warning("No backups yet. The next save will create the first one.")
        else:
            bi = st.selectbox("Restore point", range(len(bl)), key="backup_pick",
                              format_func=lambda n: f"{bl[n][1]}  ·  rev {bl[n][2]}")
            if st.button("Restore this backup…", key="do_restore"):
                confirm_restore(*bl[bi])

    with st.expander("Payment audit"):
        led = blob()["payment_ledger"][:30]
        if not led:
            st.info("Payment audit entries appear here once money is recorded.")
        else:
            html(log_html(led, lambda e: "" if e.get("action", "paid") == "paid" else "payout",
                          lambda e: f"{e.get('member', '—')} · Week {int(e.get('week', 0)):02d} · GHS {fmt_num(e.get('amount', 0))}",
                          lambda e: [f"{e.get('action', 'paid').title()} by {e.get('who', '')}"
                                     + "".join(f" · {x}" for x in (e.get("method"), e.get("reference"), e.get("reason")) if x)]))

    if blob()["history"]:
        with st.expander("Activity log"):
            html(log_html(blob()["history"][:25], lambda e: {"payout": "payout", "setting": "setting"}.get(e.get("type"), ""),
                          lambda e: e.get("text", "—"),
                          lambda e: ([f"by {e['who']}"] if e.get("who") else []) + [f"• {d}" for d in (e.get("detail") or [])[:12]]))

html('<div style="height:24px"></div>')
if st.button("Lock dashboard", key="logout"):
    st.session_state.update(authenticated=False, admin_name=ADMIN_NAME)
    st.rerun()
html('<div class="foot">Susu Savings · Backed by Google Sheets · Secured with a passcode</div>')
