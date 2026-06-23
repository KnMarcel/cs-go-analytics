import streamlit as st

st.set_page_config(
    page_title="CS:GO Map Meta",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&family=Exo+2:wght@300;400;600&display=swap');

:root {
    --bg:        #0a0c0f;
    --bg2:       #0f1318;
    --bg3:       #141920;
    --bg4:       #1a2030;
    --orange:    #ff6b2b;
    --cyan:      #00d4ff;
    --green:     #39ff14;
    --red:       #ff2b4e;
    --yellow:    #ffcc00;
    --purple:    #c084fc;
    --txt:       #e8eaf0;
    --txt2:      #8892a4;
    --border:    #1e2d40;
}

html, body, [class*="css"] { font-family:'Exo 2',sans-serif; background:var(--bg); color:var(--txt); }
.stApp { background:var(--bg); }

/* Hide sidebar toggle & default padding */
section[data-testid="stSidebar"] { display:none; }
.block-container { padding:0.6rem 1rem 1rem 1rem !important; max-width:100% !important; }

/* Scrollbar */
::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-track { background:var(--bg); }
::-webkit-scrollbar-thumb { background:var(--orange); border-radius:2px; }

/* Selectbox */
.stSelectbox>div>div { background:var(--bg3)!important; border:1px solid var(--border)!important;
    color:var(--txt)!important; border-radius:2px!important; font-family:'Exo 2',sans-serif!important; }

/* Remove plotly default white bg */
.js-plotly-plot .plotly { background:transparent!important; }

/* Panel card */
.panel {
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 10px 12px;
    margin-bottom: 8px;
    position: relative;
    overflow: hidden;
}
.panel::before {
    content:'';
    position:absolute; top:0; left:0; right:0; bottom:0;
    background:linear-gradient(135deg, rgba(255,107,43,0.04) 0%, transparent 60%);
    pointer-events:none;
}
.panel-cyan::before  { background:linear-gradient(135deg,rgba(0,212,255,0.04) 0%,transparent 60%); }
.panel-green::before { background:linear-gradient(135deg,rgba(57,255,20,0.04) 0%,transparent 60%); }
.panel-red::before   { background:linear-gradient(135deg,rgba(255,43,78,0.04) 0%,transparent 60%); }

.panel-label {
    font-family:'Share Tech Mono',monospace;
    font-size:0.6rem; letter-spacing:0.15em;
    text-transform:uppercase; color:var(--txt2);
    margin-bottom:4px;
}
.panel-value {
    font-family:'Rajdhani',sans-serif;
    font-size:1.9rem; font-weight:700; line-height:1;
}
.panel-sub {
    font-family:'Share Tech Mono',monospace;
    font-size:0.58rem; color:var(--txt2); margin-top:2px;
}
.border-orange { border-top:2px solid var(--orange); }
.border-cyan   { border-top:2px solid var(--cyan); }
.border-green  { border-top:2px solid var(--green); }
.border-red    { border-top:2px solid var(--red); }
.border-yellow { border-top:2px solid var(--yellow); }
.border-purple { border-top:2px solid var(--purple); }

.section-label {
    font-family:'Share Tech Mono',monospace;
    font-size:0.62rem; letter-spacing:0.18em;
    text-transform:uppercase; color:var(--orange);
    border-left:2px solid var(--orange);
    padding-left:6px; margin:6px 0 8px 0;
}

/* Dashboard header */
.dash-header {
    font-family:'Rajdhani',sans-serif; font-weight:700;
    font-size:1.6rem; letter-spacing:0.18em; text-transform:uppercase;
    background:linear-gradient(90deg,var(--orange),var(--cyan));
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; display:inline-block;
}
.dash-sub {
    font-family:'Share Tech Mono',monospace; color:var(--txt2);
    font-size:0.65rem; letter-spacing:0.2em; margin-left:12px;
}

/* Map watermark */
.map-watermark {
    font-family:'Rajdhani',sans-serif; font-weight:700;
    font-size:5rem; color:rgba(255,107,43,0.05);
    position:absolute; bottom:10px; right:10px;
    letter-spacing:0.1em; text-transform:uppercase;
    pointer-events:none; user-select:none;
}
</style>
""", unsafe_allow_html=True)

from data_loader import DataLoader, ensure_data_files
from tabs import tab_mapmeta

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading data...")
def load():
    ensure_data_files()  # download from HF if not local
    return DataLoader().load_all()

data = load()
if data is None:
    st.error("Failed to load data.")
    st.stop()

# ── Header + Map selector ─────────────────────────────────────────────────────
h1, h2 = st.columns([3, 1])
with h1:
    st.markdown('<span class="dash-header">⬡ CS:GO Map Intelligence</span>'
                '<span class="dash-sub">// map-wide tactical analysis</span>',
                unsafe_allow_html=True)

map_data = data["map_data"]
available_maps = sorted(map_data["map"].tolist()) if not map_data.empty else []

with h2:
    chosen_map = st.selectbox("", available_maps,
                              label_visibility="collapsed", key="global_map")

st.markdown("<hr style='border-color:#1e2d40;margin:6px 0 10px 0'>", unsafe_allow_html=True)

# ── Render single dashboard ───────────────────────────────────────────────────
tab_mapmeta.render(data, chosen_map)
