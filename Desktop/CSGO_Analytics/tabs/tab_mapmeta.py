import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import os
from PIL import Image
from constants import BASE_THEME, NADE_COLORS, get_price
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heatmap_loader import load_heatmap_grid, available_nade_types, get_colorscale, is_precomputed, LAYER_MAP

MAPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maps")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — change anything here, it applies everywhere automatically
# ══════════════════════════════════════════════════════════════════════════════

COLORS = dict(
    ct           = "#4B9FD4",
    t            = "#F4730E",
    kill         = "#C8312A",
    gold         = "#E8C84B",
    green        = "#4CAF50",
    purple       = "#9B6FD4",
    bg           = "#080C10",
    bg2          = "#0D1117",
    bg3          = "#111923",
    border       = "#1C2B3A",
    border2      = "#253545",
    txt          = "#D0D7E0",
    txt2         = "#6B7A8D",
)

RADAR_COLORS = [
    (COLORS["t"],      "rgba(244,115,14,0.13)"),
    (COLORS["ct"],     "rgba(75,159,212,0.11)"),
    (COLORS["green"],  "rgba(76,175,80,0.09)"),
    (COLORS["kill"],   "rgba(200,49,42,0.10)"),
    (COLORS["gold"],   "rgba(232,200,75,0.09)"),
    (COLORS["purple"], "rgba(155,111,212,0.09)"),
]

SETTINGS = dict(
    top_guns         = 6,      # weapons shown in radar
    radar_floor      = 15,     # minimum normalized value (keeps guns off center)
    flash_window_s   = 3,      # seconds after flash that counts as flash-assisted kill
    atff_cap_s       = 115,    # max round length cap for ATFF calculation
    heatmap_opacity  = 0.85,   # heatmap layer opacity over map image
    heatmap_min_val  = 0.015,  # values below this render transparent
    heatmap_rotation = 1,      # np.rot90 k: 0=none 1=90°CCW 2=180° 3=90°CW
    yield_top_n      = 16,     # max weapons shown in yield scatter
    momentum_window  = 5,      # rolling average window for momentum chart (rounds)
)

NADE_LIST = ["Smoke", "Flash", "HE", "Fire", "Decoy"]

NADE_DATA_MAP = {
    "Smoke": ["Smoke"],
    "Flash": ["Flash"],
    "HE":    ["HE"],
    "Fire":  ["Molotov", "Incendiary"],
    "Decoy": ["Decoy"],
}

GUN_TYPES = {"Rifle", "SMG", "Pistol", "Heavy", "Sniper Rifle"}

WP_ALIASES = {
    "Desert Eagle": "Deagle", "weapon_deagle": "Deagle",
    "M4A1-S":       "M4A1",   "AK47":          "AK-47",
    "Galil AR":     "Galil",  "FAMAS":         "Famas",
}

# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

AX = dict(
    gridcolor=COLORS["border"],
    zerolinecolor=COLORS["border"],
    linecolor=COLORS["border"],
)

def pc(fig, h):
    fig.update_layout(height=h)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def sec_label(text):
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)

def theme(**kwargs):
    base = {k: v for k, v in BASE_THEME.items() if k not in ["xaxis","yaxis","margin","colorway"]}
    base.update(kwargs)
    return base

def kpi_block(label, value, color, border_side="top"):
    border_css = f"border-{border_side}:2px solid {color}"
    st.markdown(f"""
    <div style="background:{COLORS['bg3']};border:1px solid {COLORS['border']};
                {border_css};padding:9px 12px;margin-bottom:5px;text-align:center">
      <div style="font-family:Share Tech Mono,monospace;font-size:0.55rem;
                  color:{COLORS['txt2']};letter-spacing:0.12em">{label}</div>
      <div style="font-family:Barlow Condensed,sans-serif;font-size:2.1rem;
                  font-weight:700;color:{color};line-height:1.1">{value}</div>
    </div>""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_map_img(map_name):
    p = os.path.join(MAPS_DIR, f"{map_name}.png")
    if not os.path.exists(p):
        return None
    img = Image.open(p).convert("RGBA")
    arr = np.array(img)
    black = (arr[:,:,0] < 30) & (arr[:,:,1] < 30) & (arr[:,:,2] < 30)
    arr[black, 3] = 0
    return Image.fromarray(arr)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION RENDERERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def calc_all_map_atff(_dmg: pd.DataFrame) -> pd.DataFrame:
    if _dmg.empty or "map" not in _dmg.columns or "seconds" not in _dmg.columns:
        return pd.DataFrame(columns=["map","atff"])
    rows = []
    for map_name, group in _dmg[_dmg["hp_dmg"] > 0].groupby("map"):
        first = group.groupby(["file","round"])["seconds"].min()
        first = first[first < SETTINGS["atff_cap_s"]]
        if len(first) > 0:
            rows.append(dict(map=map_name, atff=float(first.mean())))
    return pd.DataFrame(rows).sort_values("atff").reset_index(drop=True)


def render_atff_strip(all_atff: pd.DataFrame, chosen_map: str, current_atff: float):
    if all_atff.empty:
        st.caption("No ATFF data")
        return
    mn  = all_atff["atff"].min()
    mx  = all_atff["atff"].max()
    rng = mx - mn if mx > mn else 1.0
    fig = go.Figure()
    fig.add_shape(type="rect", x0=mn, x1=mx, y0=0.3, y1=0.7,
                  fillcolor=COLORS["bg3"], line_color=COLORS["border"], line_width=1)
    mid = mn + rng / 2
    fig.add_shape(type="rect", x0=mn,  x1=mid, y0=0.3, y1=0.7,
                  fillcolor="rgba(200,49,42,0.18)", line_width=0)
    fig.add_shape(type="rect", x0=mid, x1=mx,  y0=0.3, y1=0.7,
                  fillcolor="rgba(76,175,80,0.10)", line_width=0)
    for _, row in all_atff.iterrows():
        is_current = row["map"] == chosen_map
        fig.add_shape(type="line",
                      x0=row["atff"], x1=row["atff"], y0=0.28, y1=0.72,
                      line=dict(color=COLORS["t"] if is_current else COLORS["border2"],
                                width=2 if is_current else 1))
        fig.add_annotation(
            x=row["atff"], y=0.22, text=row["map"].replace("de_",""),
            showarrow=False, textangle=-40,
            font=dict(size=7, color=COLORS["t"] if is_current else COLORS["txt2"],
                      family="Share Tech Mono"),
            xanchor="right",
        )
    fig.add_trace(go.Scatter(
        x=[current_atff], y=[0.85], mode="markers+text",
        marker=dict(symbol="triangle-down", size=14, color=COLORS["t"],
                    line=dict(color=COLORS["bg"], width=1)),
        text=[f"{current_atff:.1f}s"], textposition="top center",
        textfont=dict(size=9, color=COLORS["t"], family="Barlow Condensed"),
        hovertemplate=f"<b>{chosen_map}</b><br>ATFF: {current_atff:.1f}s<extra></extra>",
        showlegend=False,
    ))
    skip = {"xaxis", "yaxis", "legend", "plot_bgcolor", "paper_bgcolor"}
    fig.update_layout(
        **{k: v for k, v in theme().items() if k not in skip},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=28, b=36),
        xaxis=dict(range=[mn - rng*0.05, mx + rng*0.05],
                   showgrid=False, zeroline=False, showticklabels=False,
                   linecolor=COLORS["border"]),
        yaxis=dict(range=[0, 1.1], showgrid=False, zeroline=False, showticklabels=False),
        title=dict(text="TIME TO FIRST FRAG — all maps",
                   font=dict(family="Share Tech Mono", color=COLORS["txt2"], size=8),
                   x=0, xanchor="left", pad=dict(l=4)),
    )
    pc(fig, 105)


def render_momentum(D: pd.DataFrame):
    sec_label("Map Momentum — CT vs T Rolling DMG Delta")
    if D.empty or "round" not in D.columns or "att_side" not in D.columns:
        return
    rd = (D.groupby(["round","att_side"])["hp_dmg"]
           .sum().unstack(fill_value=0).reset_index())
    ct = "CounterTerrorist"; t = "Terrorist"
    if ct not in rd.columns or t not in rd.columns:
        return
    rd["delta"]   = rd[ct] - rd[t]
    rd["rolling"] = rd["delta"].rolling(SETTINGS["momentum_window"], min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rd["round"], y=rd["rolling"].clip(lower=0),
        fill="tozeroy", fillcolor="rgba(75,159,212,0.15)",
        line=dict(color=COLORS["ct"], width=1.5, shape="spline"), name="CT+",
    ))
    fig.add_trace(go.Scatter(
        x=rd["round"], y=rd["rolling"].clip(upper=0),
        fill="tozeroy", fillcolor="rgba(244,115,14,0.15)",
        line=dict(color=COLORS["t"], width=1.5, shape="spline"), name="T+",
    ))
    fig.add_hline(y=0, line_color=COLORS["border2"], line_width=1)
    fig.update_layout(**theme(), margin=dict(l=6, r=6, t=8, b=6),
                      showlegend=False,
                      xaxis=dict(**AX, title="Round"),
                      yaxis=dict(**AX, title="DMG Δ"))
    pc(fig, 105)


def render_lethality(dmg_per_kill: float, hits_per_kill: float, nk: int):
    st.markdown(f"""
    <div style="text-align:center;padding:6px 0 0 0">
      <div style="font-family:Share Tech Mono,monospace;font-size:0.56rem;
                  color:{COLORS['txt2']};letter-spacing:0.15em;text-transform:uppercase">
        Lethality Index</div>
      <div style="font-family:Barlow Condensed,sans-serif;font-size:2.6rem;
                  font-weight:700;color:{COLORS['kill']};line-height:1">
        {dmg_per_kill:.0f}
        <span style="font-size:0.9rem;color:{COLORS['txt2']}"> hp/kill</span></div>
      <div style="font-family:Share Tech Mono,monospace;font-size:0.5rem;
                  color:{COLORS['txt2']};margin-top:2px">avg damage to secure a kill</div>
      <div style="font-family:Barlow Condensed,sans-serif;font-size:1.6rem;
                  font-weight:600;color:{COLORS['t']};margin-top:5px;line-height:1">
        {hits_per_kill:.1f}
        <span style="font-size:0.65rem;color:{COLORS['txt2']}"> hits/kill</span></div>
      <div style="font-family:Share Tech Mono,monospace;font-size:0.48rem;color:{COLORS['txt2']}">
        {nk:,} kills recorded</div>
    </div>""", unsafe_allow_html=True)


def render_weapon_radar(D_guns: pd.DataFrame, K: pd.DataFrame, M: pd.DataFrame):
    sec_label(f"Weapon Profile — Top {SETTINGS['top_guns']}")
    if D_guns.empty or "wp" not in D_guns.columns:
        return
    top_n = D_guns["wp"].value_counts().head(SETTINGS["top_guns"]).index.tolist()
    rows  = []
    for wp_name in top_n:
        sub  = D_guns[D_guns["wp"] == wp_name]
        hits = len(sub)
        if hits == 0:
            continue
        hs_pct = (sub["hitbox"] == "Head").sum() / hits * 100 if "hitbox" in sub.columns else 0.0
        avg_hp = float(sub["hp_dmg"].mean())
        pen    = float((sub["arm_dmg"] / (sub["hp_dmg"] + sub["arm_dmg"])
                        .replace(0, np.nan)).mean() * 100) if "arm_dmg" in sub.columns else 0.0
        wp_kills  = len(K[K["wp"] == wp_name]) if "wp" in K.columns else 0
        lethality = (1 / (hits / wp_kills)) * 100 if wp_kills > 0 else 0.0
        if all(c in sub.columns for c in ["att_pos_x","att_pos_y","vic_pos_x","vic_pos_y"]):
            coords = sub[["att_pos_x","att_pos_y","vic_pos_x","vic_pos_y"]].dropna()
            avg_range = float(np.sqrt(
                (coords["att_pos_x"] - coords["vic_pos_x"])**2 +
                (coords["att_pos_y"] - coords["vic_pos_y"])**2
            ).mean()) if len(coords) > 0 else 0.0
        else:
            avg_range = 0.0
        volume = hits / max(len(M), 1)
        rows.append(dict(wp=wp_name, hs_pct=hs_pct, avg_hp=avg_hp, pen=pen,
                         lethality=lethality, avg_range=avg_range, volume=volume))
    if not rows:
        return
    axes   = ["hs_pct","avg_hp","pen","lethality","avg_range","volume"]
    labels = ["HS%","DMG/Hit","Armor Pen","Lethality","Range","Volume"]
    FLOOR  = SETTINGS["radar_floor"]
    stats  = pd.DataFrame(rows).set_index("wp")
    norm   = stats[axes].copy()
    for ax in axes:
        mn, mx = norm[ax].min(), norm[ax].max()
        norm[ax] = FLOOR + (norm[ax] - mn) / (mx - mn + 1e-9) * (100 - FLOOR)
    fig = go.Figure()
    for i, wp_name in enumerate(norm.index):
        vals = [round(norm.loc[wp_name, ax], 1) for ax in axes]
        raw  = [stats.loc[wp_name, ax] for ax in axes]
        lc, fc = RADAR_COLORS[i % len(RADAR_COLORS)]
        ht = "<br>".join(f"{labels[j]}: {raw[j]:.1f}" for j in range(len(axes)))
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=labels + [labels[0]],
            fill="toself", line=dict(color=lc, width=2), fillcolor=fc,
            name=wp_name,
            hovertemplate=f"<b>{wp_name}</b><br>{ht}<extra></extra>",
        ))
    fig.update_layout(
        **{k: v for k, v in theme().items() if k != "legend"},
        margin=dict(l=10, r=10, t=10, b=10),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor=COLORS["border"],
                            tickfont=dict(size=7, color=COLORS["txt2"]),
                            range=[0, 100],
                            tickvals=[FLOOR, 50, 75, 100],
                            ticktext=["▼","50","75","100"]),
            angularaxis=dict(gridcolor=COLORS["border"],
                             tickfont=dict(size=9, color=COLORS["txt"],
                                           family="Share Tech Mono")),
        ),
        showlegend=True,
        legend=dict(bgcolor=COLORS["bg2"], bordercolor=COLORS["border"],
                    borderwidth=1, font=dict(size=9, color=COLORS["txt"],
                    family="Share Tech Mono"),
                    x=0.5, xanchor="center", y=-0.08, orientation="h"),
    )
    pc(fig, 265)


def render_weapon_yield(D: pd.DataFrame):
    sec_label("Weapon Yield")
    if D.empty or "wp" not in D.columns or "hp_dmg" not in D.columns:
        return
    wa = D.groupby("wp").agg(avg_dmg=("hp_dmg","mean"), count=("hp_dmg","count")).reset_index()
    wa["wp_lookup"] = wa["wp"].replace(WP_ALIASES)
    wa["price"]     = wa["wp_lookup"].apply(get_price)
    wa = wa.dropna(subset=["price"])
    wa = wa[wa["price"] > 0]
    top   = wa.nlargest(SETTINGS["yield_top_n"], "count")
    sizes = np.clip(np.sqrt(top["count"]) / np.sqrt(top["count"].max()) * 30 + 6, 6, 36)
    fig = go.Figure(go.Scatter(
        x=top["avg_dmg"], y=top["price"],
        mode="markers+text",
        marker=dict(size=sizes, color=top["avg_dmg"],
                    colorscale=[[0, COLORS["bg2"]],[0.5, COLORS["ct"]],[1, COLORS["kill"]]],
                    showscale=False, opacity=0.9,
                    line=dict(color=COLORS["bg"], width=1)),
        text=top["wp"], textposition="top center",
        textfont=dict(size=8, color=COLORS["txt2"]),
        hovertemplate="<b>%{text}</b><br>Avg DMG: %{x:.1f}<br>Cost: $%{y}<extra></extra>",
    ))
    fig.update_layout(**theme(), margin=dict(l=6, r=6, t=10, b=6),
                      xaxis=dict(**AX, title="Avg Damage"),
                      yaxis=dict(**AX, title="Cost ($)"))
    pc(fig, 210)


def render_heatmap(chosen_map: str, rx: float, ry: float):
    LAYER_OPTIONS = {
        "Damage":            "dmg_vic",
        "Grenades — Landed": "nade_land_all",
        "Grenades — Thrown": "nade_att",
    }
    SIDE_OPTIONS = {
        "All": None,
        "CT":  "ct",
        "T":   "t",
    }
    hc1, hc2 = st.columns(2)
    with hc1:
        hm_label = st.selectbox("Layer", list(LAYER_OPTIONS.keys()), key="hm_type")
    with hc2:
        hm_side_label = st.selectbox("Side", list(SIDE_OPTIONS.keys()), key="hm_side")

    base_layer  = LAYER_OPTIONS[hm_label]
    side_suffix = SIDE_OPTIONS[hm_side_label]

    if hm_label == "Damage" and side_suffix:
        layer_key = f"dmg_vic_{side_suffix}"
    else:
        layer_key = base_layer

    nade_filter = None
    if base_layer == "nade_land_all":
        nade_types = available_nade_types(chosen_map)
        if nade_types:
            sel = st.selectbox("Grenade Type", ["All"] + nade_types, key="hm_nade")
            if sel != "All":
                layer_key   = f"nade_land_{sel}"
                nade_filter = sel

    fig_map = go.Figure()
    img = load_map_img(chosen_map)
    if img:
        fig_map.add_layout_image(dict(
            source=img, xref="x", yref="y",
            x=0, y=ry, sizex=rx, sizey=ry,
            xanchor="left", yanchor="top",
            sizing="stretch", opacity=1.0, layer="below",
        ))

    def add_layer(lk, nt=None):
        grid = load_heatmap_grid(chosen_map, lk)
        if grid is None:
            return
        # Rotate heatmap grid — adjust heatmap_rotation in SETTINGS
        if SETTINGS["heatmap_rotation"] != 0:
            grid = np.rot90(grid, k=SETTINGS["heatmap_rotation"])
        fig_map.add_trace(go.Heatmap(
            z=np.where(grid > SETTINGS["heatmap_min_val"], grid, np.nan),
            x0=0, dx=rx/200, y0=0, dy=ry/200,
            colorscale=get_colorscale(lk, nt), showscale=False,
            hoverinfo="skip", opacity=SETTINGS["heatmap_opacity"], zsmooth="best",
        ))

    if not is_precomputed(chosen_map):
        st.warning("⚠️ Heatmaps not precomputed — run: python precompute_heatmaps.py")
    else:
        add_layer(layer_key, nade_filter)

    fig_map.add_annotation(
        text=chosen_map.upper(), xref="paper", yref="paper",
        x=0.97, y=0.03, showarrow=False, xanchor="right",
        font=dict(family="Barlow Condensed", size=28, color="rgba(244,115,14,0.07)"),
    )
    fig_map.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0,rx], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(range=[0,ry], showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
    )
    pc(fig_map, 450)
    st.markdown(
        f'<span style="font-family:Share Tech Mono,monospace;color:{COLORS["green"]};'
        f'font-size:0.6rem">▶ {hm_label} · {hm_side_label}'
        f'{(" · " + nade_filter) if nade_filter else ""}</span>',
        unsafe_allow_html=True,
    )


def calc_flash_effectiveness(G: pd.DataFrame, K: pd.DataFrame, M: pd.DataFrame) -> float:
    if G.empty or K.empty or M.empty:
        return 0.0
    if "seconds" not in G.columns or "seconds" not in K.columns:
        return 0.0
    if "start_seconds" not in M.columns:
        return 0.0
    round_start = M[["file","round","start_seconds"]].drop_duplicates()
    fl = G[G["nade"] == "Flash"][["file","round","seconds"]].copy()
    fl = fl.merge(round_start, on=["file","round"], how="left")
    fl["fs"] = fl["seconds"] - fl["start_seconds"]
    fl = fl[["file","round","fs"]].dropna()
    if len(fl) == 0:
        return 0.0
    K_idx = K[["file","round","seconds"]].copy()
    K_idx["kill_idx"] = range(len(K_idx))
    mg = K_idx.merge(fl, on=["file","round"], how="inner")
    mg["dt"] = mg["seconds"] - mg["fs"]
    valid = mg[(mg["dt"] >= 0) & (mg["dt"] <= SETTINGS["flash_window_s"])]
    return valid["kill_idx"].nunique() / len(fl) * 100


# ══════════════════════════════════════════════════════════════════════════════
# RENDER ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render(data: dict, chosen_map: str):
    map_data = data["map_data"]

    if chosen_map not in map_data["map"].values:
        st.warning(f"No map_data for {chosen_map}")
        return

    mr = map_data[map_data["map"] == chosen_map].iloc[0]
    rx = float(mr["ResX"]); ry = float(mr["ResY"])

    def mf(df):
        return df[df["map"] == chosen_map].copy() if "map" in df.columns else df.copy()

    D = mf(data["dmg"]); G = mf(data["grenades"])
    K = mf(data["kills"]); M = mf(data["meta"])

    D_guns = D[D["wp_type"].isin(GUN_TYPES)] if "wp_type" in D.columns else D

    nk            = len(K)
    dmg_per_kill  = D["hp_dmg"].sum()       / nk if nk > 0 and "hp_dmg" in D.columns else 0.0
    hits_per_kill = len(D[D["hp_dmg"] > 0]) / nk if nk > 0 and "hp_dmg" in D.columns else 0.0
    atff = 0.0
    if not D.empty and "seconds" in D.columns and "hp_dmg" in D.columns:
        first = D[D["hp_dmg"] > 0].groupby(["file","round"])["seconds"].min()
        first = first[first < SETTINGS["atff_cap_s"]]
        atff  = float(first.mean()) if len(first) > 0 else 0.0
    all_atff = calc_all_map_atff(data["dmg"])
    fe = calc_flash_effectiveness(G, K, M)

    # ══════════════════════════════════════════════════════════════════════════
    # TOP ROW — ATFF Strip | Map Momentum | Lethality Index
    # ══════════════════════════════════════════════════════════════════════════
    tl, tm, tr = st.columns([1.3, 2.4, 0.9], gap="small")
    with tl: render_atff_strip(all_atff, chosen_map, atff)
    with tm: render_momentum(D)
    with tr: render_lethality(dmg_per_kill, hits_per_kill, nk)

    st.markdown(f"<hr style='border-color:{COLORS['border']};margin:5px 0 7px 0'>",
                unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN 3-COLUMN LAYOUT
    # ══════════════════════════════════════════════════════════════════════════
    left, mid, right = st.columns([1, 2.3, 1], gap="small")

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN — Weapon Profile Radar | Weapon Yield Scatter
    # ══════════════════════════════════════════════════════════════════════════
    with left:
        render_weapon_radar(D_guns, K, M)
        render_weapon_yield(D)

    # ══════════════════════════════════════════════════════════════════════════
    # CENTER COLUMN — Heatmap Controls | Map Heatmap
    # ══════════════════════════════════════════════════════════════════════════
    with mid:
        render_heatmap(chosen_map, rx, ry)

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN — Utility Effectiveness | CT vs T Bar | Flash Effectiveness
    # ══════════════════════════════════════════════════════════════════════════
    with right:
        sec_label("Utility Effectiveness")
        sel = st.selectbox("Grenade Type", NADE_LIST, key="nade_sel")
        nc  = NADE_COLORS.get(sel, COLORS["t"])

        if not G.empty and "nade" in G.columns:
            G_norm = G.copy()
            G_norm["nade"] = G_norm["nade"].replace({"Molotov":"Fire","Incendiary":"Fire"})
            gn      = G_norm[G_norm["nade"] == sel]
            thrown  = len(gn)
            dmg_tot = int(gn["hp_dmg"].sum())    if "hp_dmg" in gn.columns else 0
            avg_dmg = float(gn["hp_dmg"].mean()) if "hp_dmg" in gn.columns and thrown > 0 else 0.0
            for label, fmt in [
                ("THROWN",          f"{thrown:,}"),
                ("TOTAL DAMAGE",    f"{dmg_tot:,}"),
                ("AVG DMG / THROW", f"{avg_dmg:.1f}"),
            ]:
                kpi_block(label, fmt, nc)

        sec_label("All Utility — CT vs T")
        if not G.empty and "nade" in G.columns and "att_side" in G.columns:
            G_bar = G.copy()
            G_bar["nade"] = G_bar["nade"].replace({"Molotov":"Fire","Incendiary":"Fire"})
            nd  = G_bar.groupby(["nade","att_side"]).size().reset_index(name="n")
            fig = px.bar(nd, x="nade", y="n", color="att_side", barmode="group",
                         color_discrete_map={"CounterTerrorist": COLORS["ct"],
                                             "Terrorist":        COLORS["t"]})
            fig.update_layout(**theme(), showlegend=False,
                              margin=dict(l=4, r=4, t=6, b=4),
                              xaxis=dict(**AX, title="", tickangle=-30,
                                         tickfont=dict(size=8, color=COLORS["txt2"])),
                              yaxis=dict(**AX, title=""))
            pc(fig, 150)

        sec_label("Flash Effectiveness")
        st.markdown(
            f'<div style="background:{COLORS["bg3"]};border:1px solid {COLORS["border"]};'
            f'border-left:3px solid {COLORS["gold"]};padding:8px 12px;'
            f'display:flex;align-items:center;justify-content:space-between;margin-top:4px">'
            f'<span style="font-family:Share Tech Mono,monospace;font-size:0.58rem;'
            f'color:{COLORS["txt2"]}">FLASH → KILL ({SETTINGS["flash_window_s"]}s)</span>'
            f'<span style="font-family:Barlow Condensed,sans-serif;font-size:1.7rem;'
            f'font-weight:700;color:{COLORS["gold"]}">{fe:.1f}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
