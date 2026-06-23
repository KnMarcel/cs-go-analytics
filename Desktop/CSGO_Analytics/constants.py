# CS:GO Weapon prices (hardcoded)
WEAPON_PRICES = {
    # Pistols
    "Glock": 200, "USP": 200, "P2000": 200, "P250": 300, "Tec-9": 500,
    "Five-SeveN": 500, "CZ75": 500, "Deagle": 700, "Desert Eagle": 700,
    "Dual Berettas": 300, "R8": 700,
    # SMGs
    "MP9": 1250, "MAC-10": 1050, "MP5": 1500, "MP7": 1700, "UMP-45": 1200,
    "P90": 2350, "PP-Bizon": 1400,
    # Rifles
    "Famas": 2050, "Galil": 1800, "M4A4": 3100, "M4A1": 2900,
    "AK-47": 2700, "AK": 2700, "SG553": 3000, "AUG": 3300,
    "SSG08": 1700, "AWP": 4750, "G3SG1": 5000, "SCAR-20": 5000,
    # Heavy
    "Nova": 1050, "XM1014": 2000, "Sawed-Off": 1100, "MAG-7": 1300,
    "M249": 5200, "Negev": 1700,
    # Misc
    "Knife": 0, "Unknown": 0, "Unkown": 0, "C4": 0,
    "HE": 300, "Smoke": 300, "Flash": 200, "Flashbang": 200,
    "Molotov": 400, "Decoy": 50, "Incendiary": 600,
}

def get_price(wp):
    if not isinstance(wp, str):
        return None
    for key, price in WEAPON_PRICES.items():
        if key.lower() in wp.lower() or wp.lower() in key.lower():
            return price if price > 0 else None
    return None

NADE_COLORS = {
    "Smoke":       "#6B7A8D",   # muted grey-blue
    "HE":          "#4CAF50",   # green
    "Fire":        "#F4730E",   # CS2 orange — Molotov (T) + Incendiary (CT) combined
    "Molotov":     "#F4730E",   # kept for heatmap_loader compat
    "Incendiary":  "#F4730E",   # kept for heatmap_loader compat
    "Flashbang":   "#E8C84B",   # gold
    "Decoy":       "#9B6FD4",   # purple
}

BASE_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(14,18,24,0.0)",
    font=dict(family="Exo 2, sans-serif", color="#8892a4", size=10),
    title_font=dict(family="Rajdhani, sans-serif", color="#e8eaf0", size=13),
    xaxis=dict(gridcolor="#1e2d40", zerolinecolor="#1e2d40", linecolor="#1e2d40"),
    yaxis=dict(gridcolor="#1e2d40", zerolinecolor="#1e2d40", linecolor="#1e2d40"),
    colorway=["#ff6b2b","#00d4ff","#39ff14","#ff2b4e","#ffcc00","#c084fc"],
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9, color="#8892a4"),
                title_text="", bordercolor="rgba(0,0,0,0)"),
)

def mini(fig, h=200, config=None):
    import streamlit as st
    cfg = {"displayModeBar": False, "staticPlot": False}
    if config:
        cfg.update(config)
    fig.update_layout(height=h)
    st.plotly_chart(fig, use_container_width=True, config=cfg)

def panel_label(text):
    import streamlit as st
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)

def kpi_card(label, value, color="#ff6b2b", sub=""):
    import streamlit as st
    border_class = {
        "#ff6b2b": "border-orange", "#00d4ff": "border-cyan",
        "#39ff14": "border-green",  "#ff2b4e": "border-red",
        "#ffcc00": "border-yellow", "#c084fc": "border-purple",
    }.get(color, "border-orange")
    sub_html = f'<div class="panel-sub">{sub}</div>' if sub else ""
    st.markdown(f"""
    <div class="panel {border_class}">
        <div class="panel-label">{label}</div>
        <div class="panel-value" style="color:{color}">{value}</div>
        {sub_html}
    </div>""", unsafe_allow_html=True)
