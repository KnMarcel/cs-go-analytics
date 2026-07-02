"""
tab_mapmeta.py — v3 Live Linked Dashboard
Serves pre-aggregated JSON once, renders entirely in JS.
Zero Python roundtrips after initial load.
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import os
import json
from constants import BASE_THEME, NADE_COLORS, get_price

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "processed", "dashboard")
MAPS_DIR      = os.path.join(BASE_DIR, "maps")
MAPS_GITHUB   = "https://raw.githubusercontent.com/KnMarcel/cs-go-analytics/main/Desktop/CSGO_Analytics/maps"


@st.cache_data(show_spinner=False)
def load_dashboard_json(map_name: str) -> dict:
    p = os.path.join(DASHBOARD_DIR, f"{map_name}.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def get_map_img_url(map_name: str) -> str:
    local = os.path.join(MAPS_DIR, f"{map_name}.png")
    if os.path.exists(local):
        import base64
        with open(local,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    return f"{MAPS_GITHUB}/{map_name}.png"


def render(data: dict, chosen_map: str):
    payload = load_dashboard_json(chosen_map)

    if payload is None:
        st.warning(f"No dashboard data for {chosen_map}. Run precompute_dashboard.py first.")
        st.info("```bash\npython precompute_dashboard.py\n```")
        return

    map_img_url = get_map_img_url(chosen_map)
    payload["map_img"] = map_img_url

    json_str = json.dumps(payload, separators=(",",":"))

    html = build_dashboard_html(json_str, chosen_map)
    components.html(html, height=900, scrolling=False)


def build_dashboard_html(json_str: str, chosen_map: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Share+Tech+Mono&family=Barlow:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#080C10;--bg2:#0D1117;--bg3:#111923;--bg4:#1A2535;
  --orange:#F4730E;--ct:#4B9FD4;--kill:#C8312A;--gold:#E8C84B;
  --green:#4CAF50;--purple:#9B6FD4;
  --txt:#D0D7E0;--txt2:#6B7A8D;--border:#1C2B3A;--border2:#253545;
}}
html,body{{background:var(--bg);color:var(--txt);font-family:'Barlow',sans-serif;height:100%;overflow:hidden}}
body{{display:flex;flex-direction:column;height:900px}}

/* ── FILTER BAR ── */
#filter-bar{{
  background:var(--bg2);border-bottom:1px solid var(--border);
  padding:6px 12px;display:flex;align-items:center;gap:8px;flex-shrink:0;flex-wrap:wrap;
}}
.filter-group{{display:flex;align-items:center;gap:4px}}
.filter-label{{
  font-family:'Share Tech Mono',monospace;font-size:0.55rem;
  letter-spacing:0.12em;color:var(--txt2);text-transform:uppercase;white-space:nowrap;
}}
select{{
  background:var(--bg3);border:1px solid var(--border2);
  border-left:2px solid var(--orange);color:var(--txt);
  font-family:'Barlow Condensed',sans-serif;font-size:0.8rem;
  padding:3px 6px;border-radius:0;cursor:pointer;outline:none;
}}
select:focus{{border-color:var(--orange)}}
.filter-sep{{width:1px;height:20px;background:var(--border);margin:0 4px}}

/* ── MAIN LAYOUT ── */
#main{{display:grid;grid-template-columns:200px 1fr 200px;gap:0;flex:1;overflow:hidden}}

/* ── LEFT PANEL ── */
#left{{
  background:var(--bg2);border-right:1px solid var(--border);
  overflow-y:auto;display:flex;flex-direction:column;gap:0;
}}
.panel{{padding:10px 12px;border-bottom:1px solid var(--border)}}
.panel-title{{
  font-family:'Barlow Condensed',sans-serif;font-size:0.65rem;font-weight:700;
  letter-spacing:0.2em;text-transform:uppercase;color:var(--orange);
  border-left:2px solid var(--orange);padding-left:6px;margin-bottom:8px;
}}

/* RADAR */
#radar-wrap{{position:relative;width:100%;aspect-ratio:1}}
#radarChart{{width:100%!important;height:100%!important}}

/* WEAPON BARS */
.wp-bar-row{{margin-bottom:6px;cursor:pointer;padding:3px 4px;border-radius:2px;transition:background 0.15s}}
.wp-bar-row:hover,.wp-bar-row.active{{background:var(--bg4)}}
.wp-bar-header{{display:flex;justify-content:space-between;margin-bottom:2px}}
.wp-name{{font-family:'Share Tech Mono',monospace;font-size:0.6rem;color:var(--txt)}}
.wp-val{{font-family:'Share Tech Mono',monospace;font-size:0.6rem;color:var(--txt2)}}
.wp-bar-bg{{height:3px;background:var(--border);border-radius:2px;overflow:hidden}}
.wp-bar-fill{{height:100%;border-radius:2px;transition:width 0.6s cubic-bezier(0.4,0,0.2,1)}}

/* ── CENTER PANEL ── */
#center{{position:relative;overflow:hidden;background:var(--bg)}}
#map-canvas{{position:absolute;inset:0;width:100%;height:100%}}
#heat-canvas{{position:absolute;inset:0;width:100%;height:100%;opacity:0.85;transition:opacity 0.3s}}

/* ── RIGHT PANEL ── */
#right{{
  background:var(--bg2);border-left:1px solid var(--border);
  overflow-y:auto;display:flex;flex-direction:column;
}}

/* KPI CARDS */
.kpi-card{{
  padding:8px 12px;border-bottom:1px solid var(--border);
  display:flex;flex-direction:column;
}}
.kpi-label{{font-family:'Share Tech Mono',monospace;font-size:0.5rem;letter-spacing:0.15em;color:var(--txt2);text-transform:uppercase;margin-bottom:2px}}
.kpi-value{{font-family:'Barlow Condensed',sans-serif;font-size:1.8rem;font-weight:700;line-height:1}}

/* HITBOX */
.hb-row{{display:flex;align-items:center;gap:6px;margin-bottom:5px}}
.hb-zone{{font-family:'Share Tech Mono',monospace;font-size:0.55rem;color:var(--txt2);width:52px;flex-shrink:0}}
.hb-bar-bg{{flex:1;height:4px;background:var(--border);border-radius:2px;overflow:hidden}}
.hb-bar-fill{{height:100%;border-radius:2px;transition:width 0.6s cubic-bezier(0.4,0,0.2,1)}}
.hb-pct{{font-family:'Share Tech Mono',monospace;font-size:0.55rem;color:var(--txt2);width:28px;text-align:right}}

/* MOMENTUM */
#momentum-wrap{{position:relative;height:90px;padding:2px}}
#momentumChart{{width:100%!important;height:100%!important}}

/* ATFF STRIP */
#atff-strip{{padding:8px 12px;border-bottom:1px solid var(--border)}}
.atff-track{{position:relative;height:4px;background:var(--border);border-radius:2px;margin:6px 0 2px}}
.atff-fill{{position:absolute;top:0;height:100%;background:linear-gradient(to right,var(--kill),var(--green));border-radius:2px}}
.atff-marker{{
  position:absolute;top:-4px;width:2px;height:12px;
  background:var(--orange);transform:translateX(-50%);
  transition:left 0.5s cubic-bezier(0.4,0,0.2,1);
}}
.atff-marker::after{{
  content:attr(data-label);position:absolute;top:-14px;left:50%;transform:translateX(-50%);
  font-family:'Share Tech Mono',monospace;font-size:0.5rem;color:var(--orange);white-space:nowrap;
}}
.atff-labels{{display:flex;justify-content:space-between;font-family:'Share Tech Mono',monospace;font-size:0.48rem;color:var(--txt2)}}

/* FLASH */
.flash-value{{font-family:'Barlow Condensed',sans-serif;font-size:2.4rem;font-weight:700;color:var(--gold);line-height:1}}

/* Transition animations */
.fade-in{{animation:fadeIn 0.3s ease}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}

/* Layer toggle pills */
.layer-pills{{display:flex;gap:4px;flex-wrap:wrap;padding:8px 12px;border-bottom:1px solid var(--border)}}
.pill{{
  font-family:'Share Tech Mono',monospace;font-size:0.5rem;letter-spacing:0.08em;
  padding:3px 7px;border:1px solid var(--border2);border-radius:2px;cursor:pointer;
  color:var(--txt2);background:transparent;transition:all 0.15s;text-transform:uppercase;
}}
.pill:hover{{border-color:var(--orange);color:var(--orange)}}
.pill.active{{background:var(--orange);border-color:var(--orange);color:#fff}}

/* Round range slider */
#round-range-wrap{{display:flex;align-items:center;gap:6px}}
input[type=range]{{
  -webkit-appearance:none;flex:1;height:3px;background:var(--border);
  outline:none;border-radius:2px;accent-color:var(--orange);
}}
input[type=range]::-webkit-slider-thumb{{
  -webkit-appearance:none;width:12px;height:12px;
  border-radius:50%;background:var(--orange);cursor:pointer;
}}
.round-val{{font-family:'Share Tech Mono',monospace;font-size:0.55rem;color:var(--txt2);min-width:20px}}
</style>
</head>
<body>
<h2 class="sr-only" style="position:absolute;left:-9999px">CS:GO Map Analytics Dashboard — {chosen_map}</h2>

<!-- FILTER BAR -->
<div id="filter-bar">
  <div class="filter-group">
    <span class="filter-label">Layer</span>
    <select id="sel-layer">
      <option value="dmg_vic">Damage — Victim</option>
      <option value="dmg_att">Damage — Attacker</option>
      <option value="nade_land_all">Nades — Landed</option>
      <option value="nade_thrown_all">Nades — Thrown</option>
    </select>
  </div>
  <div class="filter-sep"></div>
  <div class="filter-group">
    <span class="filter-label">Nade</span>
    <select id="sel-nade">
      <option value="all">All</option>
      <option value="Smoke">Smoke</option>
      <option value="Flash">Flash</option>
      <option value="HE">HE</option>
      <option value="Fire">Fire</option>
      <option value="Decoy">Decoy</option>
    </select>
  </div>
  <div class="filter-sep"></div>
  <div class="filter-group">
    <span class="filter-label">Side</span>
    <select id="sel-side">
      <option value="all">All</option>
      <option value="ct">CT</option>
      <option value="t">T</option>
    </select>
  </div>
  <div class="filter-sep"></div>
  <div class="filter-group">
    <span class="filter-label">Weapon</span>
    <select id="sel-weapon">
      <option value="all">All weapons</option>
    </select>
  </div>
  <div class="filter-sep"></div>
  <div class="filter-group" style="flex:1;min-width:120px">
    <span class="filter-label">Rounds</span>
    <div id="round-range-wrap">
      <span class="round-val" id="round-min-label">1</span>
      <input type="range" id="round-min" min="1" max="30" value="1" step="1">
      <input type="range" id="round-max" min="1" max="30" value="30" step="1">
      <span class="round-val" id="round-max-label">30</span>
    </div>
  </div>
</div>

<!-- MAIN 3-COL -->
<div id="main">

  <!-- LEFT -->
  <div id="left">
    <div class="panel">
      <div class="panel-title">Weapon Profile</div>
      <div id="radar-wrap"><canvas id="radarChart"></canvas></div>
    </div>
    <div class="panel">
      <div class="panel-title">Hit Distribution</div>
      <div id="weapon-bars"></div>
    </div>
    <div class="panel">
      <div class="panel-title">Hitbox</div>
      <div id="hitbox-bars"></div>
    </div>
  </div>

  <!-- CENTER MAP -->
  <div id="center">
    <canvas id="map-canvas"></canvas>
    <canvas id="heat-canvas"></canvas>
  </div>

  <!-- RIGHT -->
  <div id="right">
    <div id="atff-strip">
      <div class="panel-title" style="margin-bottom:4px">Time to First Frag</div>
      <div class="atff-track">
        <div class="atff-fill" style="width:100%"></div>
        <div class="atff-marker" id="atff-marker" data-label="0s"></div>
      </div>
      <div class="atff-labels">
        <span id="atff-min"></span><span id="atff-cur" style="color:var(--orange)"></span><span id="atff-max"></span>
      </div>
    </div>

    <div class="kpi-card">
      <div class="kpi-label">Kills recorded</div>
      <div class="kpi-value" id="kpi-kills" style="color:var(--kill)">—</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Flash → Kill (3s)</div>
      <div class="kpi-value" id="kpi-flash" style="color:var(--gold)">—</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Nades thrown</div>
      <div class="kpi-value" id="kpi-nades" style="color:var(--ct)">—</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg DMG / hit</div>
      <div class="kpi-value" id="kpi-dmg" style="color:var(--orange)">—</div>
    </div>

    <div class="panel">
      <div class="panel-title">CT vs T — Utility</div>
      <div style="position:relative;height:100px">
        <canvas id="utilChart"></canvas>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">Map Momentum</div>
      <div id="momentum-wrap">
        <canvas id="momentumChart"></canvas>
      </div>
    </div>
  </div>

</div>

<script>
const DATA = {json_str};
const BINS = DATA.heatmaps[Object.keys(DATA.heatmaps)[0]]?.bins || 100;

// ── COLOR SCHEME ────────────────────────────────────────────────────────────
const C = {{
  orange:'#F4730E',ct:'#4B9FD4',kill:'#C8312A',gold:'#E8C84B',
  green:'#4CAF50',purple:'#9B6FD4',txt:'#D0D7E0',txt2:'#6B7A8D',
  border:'#1C2B3A',bg3:'#111923',bg:'#080C10',
}};

const RADAR_COLORS = [
  [C.orange,'rgba(244,115,14,0.15)'],[C.ct,'rgba(75,159,212,0.12)'],
  [C.green,'rgba(76,175,80,0.10)'],[C.kill,'rgba(200,49,42,0.10)'],
  [C.gold,'rgba(232,200,75,0.09)'],[C.purple,'rgba(155,111,212,0.09)'],
];

const NADE_COLORS = {{
  Smoke:'#6B7A8D',Flash:'#E8C84B',HE:'#4CAF50',
  Fire:'#F4730E',Decoy:'#9B6FD4',all:'#F4730E',
}};

const HEATMAP_COLORS = {{
  dmg_vic:   [[0,'rgba(0,0,0,0)'],[0.2,'rgba(75,159,212,0.3)'],[0.5,'rgba(244,115,14,0.7)'],[0.8,'rgba(200,49,42,0.9)'],[1,'rgba(255,255,255,1)']],
  dmg_att:   [[0,'rgba(0,0,0,0)'],[0.2,'rgba(75,159,212,0.3)'],[0.5,'rgba(244,115,14,0.7)'],[0.8,'rgba(200,49,42,0.9)'],[1,'rgba(255,255,255,1)']],
  dmg_vic_ct:[[0,'rgba(0,0,0,0)'],[0.3,'rgba(75,159,212,0.4)'],[0.7,'rgba(75,159,212,0.85)'],[1,'rgba(75,159,212,1)']],
  dmg_vic_t: [[0,'rgba(0,0,0,0)'],[0.3,'rgba(244,115,14,0.4)'],[0.7,'rgba(244,115,14,0.85)'],[1,'rgba(244,115,14,1)']],
  nade_land: [[0,'rgba(0,0,0,0)'],[0.2,'rgba(232,200,75,0.3)'],[0.6,'rgba(232,200,75,0.8)'],[1,'rgba(232,200,75,1)']],
  nade_thrown:[[0,'rgba(0,0,0,0)'],[0.2,'rgba(155,111,212,0.3)'],[0.6,'rgba(155,111,212,0.8)'],[1,'rgba(155,111,212,1)']],
  default:   [[0,'rgba(0,0,0,0)'],[0.2,'rgba(75,159,212,0.3)'],[0.5,'rgba(244,115,14,0.7)'],[0.8,'rgba(200,49,42,0.9)'],[1,'rgba(255,255,255,1)']],
}};

// ── STATE ───────────────────────────────────────────────────────────────────
const state = {{
  layer: 'dmg_vic', nade: 'all', side: 'all',
  weapon: 'all', roundMin: 1, roundMax: 30,
  activeWp: null,
}};

// ── CHART INSTANCES ─────────────────────────────────────────────────────────
let radarChart, utilChart, momentumChart;

// ── CANVAS SETUP ────────────────────────────────────────────────────────────
const mapCanvas  = document.getElementById('map-canvas');
const heatCanvas = document.getElementById('heat-canvas');
const mapCtx     = mapCanvas.getContext('2d');
const heatCtx    = heatCanvas.getContext('2d');

function resizeCanvases(){{
  const c = document.getElementById('center');
  const w = c.clientWidth, h = c.clientHeight;
  [mapCanvas,heatCanvas].forEach(cv=>{{cv.width=w;cv.height=h;}});
  drawMapImage();
  drawHeatmap();
}}

// ── MAP IMAGE ────────────────────────────────────────────────────────────────
const mapImg = new Image();
mapImg.crossOrigin = 'anonymous';
mapImg.src = DATA.map_img;
mapImg.onload = () => {{ drawMapImage(); drawHeatmap(); }};

function drawMapImage(){{
  const w = mapCanvas.width, h = mapCanvas.height;
  mapCtx.clearRect(0,0,w,h);
  if(!mapImg.complete || mapImg.naturalWidth===0) return;
  // Remove black background
  const offscreen = document.createElement('canvas');
  offscreen.width = mapImg.naturalWidth;
  offscreen.height = mapImg.naturalHeight;
  const octx = offscreen.getContext('2d');
  octx.drawImage(mapImg,0,0);
  const id = octx.getImageData(0,0,offscreen.width,offscreen.height);
  const d = id.data;
  for(let i=0;i<d.length;i+=4){{
    if(d[i]<30 && d[i+1]<30 && d[i+2]<30) d[i+3]=0;
  }}
  octx.putImageData(id,0,0);
  mapCtx.drawImage(offscreen,0,0,w,h);
}}

// ── HEATMAP RENDER ──────────────────────────────────────────────────────────
function getLayerKey(){{
  const l = state.layer;
  const n = state.nade !== 'all' ? state.nade : null;
  const s = state.side !== 'all' ? state.side : null;

  // Weapon kill positions
  if(state.activeWp){{
    const k = 'kills_'+state.activeWp.replace(/-/g,'').replace(/ /g,'_').replace(/[/]/g,'');
    if(DATA.heatmaps[k]) return k;
  }}

  let key = l;
  if(n && l.startsWith('nade')){{
    const base = l.includes('land') ? 'nade_land' : 'nade_thrown';
    key = `${{base}}_${{n}}`;
    if(s) key += `_${{s}}`;
  }} else if(s && l.startsWith('dmg')){{
    key = `${{l}}_${{s}}`;
  }}
  return DATA.heatmaps[key] ? key : l;
}}

function getColorScale(layerKey){{
  if(layerKey.includes('_ct')) return HEATMAP_COLORS.dmg_vic_ct;
  if(layerKey.includes('_t') && !layerKey.includes('att')) return HEATMAP_COLORS.dmg_vic_t;
  if(layerKey.includes('land')) return HEATMAP_COLORS.nade_land;
  if(layerKey.includes('thrown')) return HEATMAP_COLORS.nade_thrown;
  if(layerKey.startsWith('dmg')) return HEATMAP_COLORS.dmg_vic;
  return HEATMAP_COLORS.default;
}}

function interpColor(cs, t){{
  for(let i=0;i<cs.length-1;i++){{
    if(t>=cs[i][0] && t<=cs[i+1][0]){{
      const a=(t-cs[i][0])/(cs[i+1][0]-cs[i][0]);
      return blendColors(cs[i][1],cs[i+1][1],a);
    }}
  }}
  return cs[cs.length-1][1];
}}

function blendColors(c1,c2,t){{
  const p=(s)=>{{
    const m=s.match(/[0-9.]+/g).map(Number);
    return m;
  }};
  const a=p(c1),b=p(c2);
  const r=a.map((v,i)=>v+(b[i]-v)*t);
  return c1.includes('rgba')?`rgba(${{r[0].toFixed(0)}},${{r[1].toFixed(0)}},${{r[2].toFixed(0)}},${{r[3].toFixed(2)}})`:
         `rgb(${{r[0].toFixed(0)}},${{r[1].toFixed(0)}},${{r[2].toFixed(0)}})`;
}}

let heatmapAnimId = null;
let currentHeatGrid = null;
let targetHeatGrid  = null;
let animProgress    = 1;

function drawHeatmap(){{
  const w = heatCanvas.width, h = heatCanvas.height;
  heatCtx.clearRect(0,0,w,h);
  const grid = currentHeatGrid;
  if(!grid) return;

  const cs = getColorScale(getLayerKey());
  const bins = grid.bins||BINS;
  const cw = w/bins, ch = h/bins;

  for(let i=0;i<grid.r.length;i++){{
    const v = grid.v[i]/255;
    if(v<0.02) continue;
    const color = interpColor(cs,v);
    heatCtx.fillStyle = color;
    heatCtx.fillRect(grid.c[i]*cw, grid.r[i]*ch, cw+1, ch+1);
  }}
}}

function animateToHeatmap(newKey){{
  const newGrid = DATA.heatmaps[newKey] || null;
  if(heatmapAnimId) cancelAnimationFrame(heatmapAnimId);

  // Smooth fade out → swap → fade in via canvas alpha
  let alpha = 1;
  function fadeOut(){{
    alpha -= 0.12;
    heatCanvas.style.opacity = Math.max(0,alpha).toFixed(2);
    if(alpha>0){{ heatmapAnimId=requestAnimationFrame(fadeOut); }}
    else{{
      currentHeatGrid = newGrid;
      drawHeatmap();
      fadeIn();
    }}
  }}
  function fadeIn(){{
    alpha += 0.12;
    heatCanvas.style.opacity = Math.min(0.85,alpha).toFixed(2);
    if(alpha<0.85){{ heatmapAnimId=requestAnimationFrame(fadeIn); }}
  }}
  fadeOut();
}}

// ── RADAR CHART ─────────────────────────────────────────────────────────────
function initRadar(){{
  const weapons = DATA.weapons;
  if(!weapons || !weapons.length) return;

  const axes = ['hs','dmg','pen','leth','range','vol'];
  const labels = ['HS%','DMG/Hit','Armor Pen','Lethality','Range','Volume'];
  const FLOOR = 15;

  // Normalize per axis
  const norm = axes.map(ax=>{{
    const vals = weapons.map(w=>w[ax]||0);
    const mn=Math.min(...vals), mx=Math.max(...vals);
    return weapons.map(v=>mx>mn?FLOOR+(((v[ax]||0)-mn)/(mx-mn))*(100-FLOOR):FLOOR);
  }});

  const datasets = weapons.map((w,i)=>{{
    const [lc,fc]=RADAR_COLORS[i%RADAR_COLORS.length];
    const vals = axes.map((_,ai)=>norm[ai][i]);
    return {{
      label:w.wp,
      data:[...vals,vals[0]],
      borderColor:lc,backgroundColor:fc,
      borderWidth:1.5,pointRadius:0,
    }};
  }});

  if(radarChart) radarChart.destroy();
  radarChart = new Chart(document.getElementById('radarChart'),{{
    type:'radar',
    data:{{labels:[...labels,labels[0]],datasets}},
    options:{{
      responsive:true,maintainAspectRatio:true,
      animation:{{duration:600,easing:'easeInOutQuart'}},
      plugins:{{legend:{{display:false}}}},
      scales:{{r:{{
        min:0,max:100,
        grid:{{color:C.border}},
        ticks:{{display:false}},
        pointLabels:{{
          color:C.txt2,
          font:{{family:'Share Tech Mono',size:8}},
        }},
      }}}},
    }},
  }});

  // Weapon selector
  const sel = document.getElementById('sel-weapon');
  weapons.forEach(w=>{{
    const o=document.createElement('option');
    o.value=w.wp;o.textContent=w.wp;
    sel.appendChild(o);
  }});

  // Weapon hit bars
  const max = Math.max(...weapons.map(w=>w.hits||0));
  const wrap = document.getElementById('weapon-bars');
  weapons.forEach((w,i)=>{{
    const [lc]=RADAR_COLORS[i%RADAR_COLORS.length];
    const pct = max>0?((w.hits||0)/max*100).toFixed(0):0;
    const div=document.createElement('div');
    div.className='wp-bar-row';
    div.dataset.wp=w.wp;
    div.innerHTML=`
      <div class="wp-bar-header">
        <span class="wp-name">${{w.wp}}</span>
        <span class="wp-val">${{(w.hits||0).toLocaleString()}}</span>
      </div>
      <div class="wp-bar-bg"><div class="wp-bar-fill" style="width:0;background:${{lc}}" data-pct="${{pct}}%"></div></div>`;
    div.addEventListener('click',()=>onWeaponClick(w.wp,div));
    wrap.appendChild(div);
  }});
  setTimeout(()=>wrap.querySelectorAll('.wp-bar-fill').forEach(el=>{{el.style.width=el.dataset.pct}}),100);
}}

function onWeaponClick(wp, el){{
  const isActive = state.activeWp===wp;
  state.activeWp = isActive?null:wp;
  document.querySelectorAll('.wp-bar-row').forEach(r=>r.classList.remove('active'));
  if(!isActive) el.classList.add('active');
  update();
}}

// ── HITBOX BARS ─────────────────────────────────────────────────────────────
function initHitbox(){{
  const hb = DATA.hitbox||{{}};
  const order=['Head','Chest','Stomach','Arms','Legs','Generic'];
  const colors={{Head:C.kill,Chest:C.orange,Stomach:'#C88A2A',Arms:C.txt2,Legs:C.border,Generic:'#253545'}};
  const wrap=document.getElementById('hitbox-bars');
  const max=Math.max(...Object.values(hb));
  order.forEach(zone=>{{
    const pct=hb[zone]||0;
    const col=colors[zone]||C.txt2;
    const div=document.createElement('div');
    div.className='hb-row';
    div.innerHTML=`
      <span class="hb-zone">${{zone}}</span>
      <div class="hb-bar-bg"><div class="hb-bar-fill" style="width:0;background:${{col}}" data-pct="${{max>0?(pct/max*100).toFixed(0):0}}%"></div></div>
      <span class="hb-pct">${{pct}}%</span>`;
    wrap.appendChild(div);
  }});
  setTimeout(()=>wrap.querySelectorAll('.hb-bar-fill').forEach(el=>{{el.style.width=el.dataset.pct}}),200);
}}

// ── UTILITY CHART ────────────────────────────────────────────────────────────
function initUtilChart(){{
  const kpis=DATA.nade_kpis||{{}};
  const nades=Object.keys(kpis).filter(k=>k!=='undefined');
  if(!nades.length) return;

  if(utilChart) utilChart.destroy();
  utilChart=new Chart(document.getElementById('utilChart'),{{
    type:'bar',
    data:{{
      labels:nades,
      datasets:[
        {{label:'CT',data:nades.map(n=>kpis[n]?.ct||0),backgroundColor:C.ct,borderRadius:2}},
        {{label:'T', data:nades.map(n=>kpis[n]?.t||0), backgroundColor:C.orange,borderRadius:2}},
      ]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      animation:{{duration:500}},
      plugins:{{legend:{{display:false}}}},
      scales:{{
        x:{{ticks:{{color:C.txt2,font:{{family:'Share Tech Mono',size:8}}}},grid:{{color:C.border}}}},
        y:{{ticks:{{color:C.txt2,font:{{family:'Share Tech Mono',size:8}}}},grid:{{color:C.border}}}},
      }},
    }},
  }});
}}

// ── MOMENTUM CHART ────────────────────────────────────────────────────────────
function initMomentumChart(){{
  const mom=DATA.momentum||[];
  if(!mom.length) return;

  const rounds=mom.map(r=>r.round);
  const deltas=mom.map(r=>r.delta||0);

  if(momentumChart) momentumChart.destroy();
  momentumChart=new Chart(document.getElementById('momentumChart'),{{
    type:'line',
    data:{{
      labels:rounds,
      datasets:[
        {{label:'CT+',data:deltas.map(v=>Math.max(0,v)),fill:true,
          backgroundColor:'rgba(75,159,212,0.15)',borderColor:C.ct,
          borderWidth:1.5,tension:0.4,pointRadius:0}},
        {{label:'T+',data:deltas.map(v=>Math.min(0,v)),fill:true,
          backgroundColor:'rgba(244,115,14,0.15)',borderColor:C.orange,
          borderWidth:1.5,tension:0.4,pointRadius:0}},
      ]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      animation:{{duration:600}},
      plugins:{{legend:{{display:false}}}},
      scales:{{
        x:{{ticks:{{color:C.txt2,font:{{size:8}}}},grid:{{color:C.border}}}},
        y:{{ticks:{{color:C.txt2,font:{{size:8}}}},grid:{{color:C.border}}}},
      }},
    }},
  }});
}}

// ── ATFF STRIP ───────────────────────────────────────────────────────────────
function updateAtff(){{
  const all=DATA.atff_all||{{}};
  const vals=Object.values(all);
  if(!vals.length) return;
  const mn=Math.min(...vals), mx=Math.max(...vals);
  const cur=DATA.atff_map||mn;
  const pct=((cur-mn)/(mx-mn+0.001)*100).toFixed(1);
  document.getElementById('atff-marker').style.left=pct+'%';
  document.getElementById('atff-marker').dataset.label=cur.toFixed(1)+'s';
  document.getElementById('atff-min').textContent=mn.toFixed(1)+'s';
  document.getElementById('atff-max').textContent=mx.toFixed(1)+'s';
  document.getElementById('atff-cur').textContent=cur.toFixed(1)+'s';
}}

// ── KPI UPDATES ───────────────────────────────────────────────────────────────
function animateNumber(el, target, suffix='', decimals=0){{
  const start=parseFloat(el.textContent)||0;
  const dur=400,fps=30,steps=dur/1000*fps;
  let i=0;
  const tick=()=>{{
    i++;
    const v=start+(target-start)*(i/steps);
    el.textContent=(decimals?v.toFixed(decimals):Math.round(v)).toLocaleString()+suffix;
    if(i<steps) requestAnimationFrame(tick);
    else el.textContent=(decimals?target.toFixed(decimals):Math.round(target)).toLocaleString()+suffix;
  }};
  requestAnimationFrame(tick);
}}

function updateKpis(){{
  const m=DATA.meta||{{}};
  animateNumber(document.getElementById('kpi-kills'), m.n_kills||0);
  animateNumber(document.getElementById('kpi-flash'), DATA.flash_eff||0, '%', 1);
  const nk=DATA.nade_kpis||{{}};
  const sel=state.nade==='all'?Object.values(nk).reduce((s,v)=>s+(v.total||0),0):(nk[state.nade]?.total||0);
  animateNumber(document.getElementById('kpi-nades'), sel);
  const wp=DATA.weapons||[];
  const avgDmg=state.weapon==='all'
    ? (wp.length?wp.reduce((s,w)=>s+(w.dmg||0),0)/wp.length:0)
    : (wp.find(w=>w.wp===state.weapon)?.dmg||0);
  animateNumber(document.getElementById('kpi-dmg'), avgDmg, '', 1);
}}

// ── MAIN UPDATE ──────────────────────────────────────────────────────────────
function update(){{
  const key=getLayerKey();
  animateToHeatmap(key);
  updateKpis();
}}

// ── EVENT LISTENERS ──────────────────────────────────────────────────────────
document.getElementById('sel-layer').addEventListener('change',e=>{{state.layer=e.target.value;update();}});
document.getElementById('sel-nade').addEventListener('change',e=>{{state.nade=e.target.value;update();}});
document.getElementById('sel-side').addEventListener('change',e=>{{state.side=e.target.value;update();}});
document.getElementById('sel-weapon').addEventListener('change',e=>{{
  state.weapon=e.target.value;
  state.activeWp=e.target.value==='all'?null:e.target.value;
  update();
}});
document.getElementById('round-min').addEventListener('input',e=>{{
  state.roundMin=+e.target.value;
  document.getElementById('round-min-label').textContent=e.target.value;
}});
document.getElementById('round-max').addEventListener('input',e=>{{
  state.roundMax=+e.target.value;
  document.getElementById('round-max-label').textContent=e.target.value;
}});

window.addEventListener('resize',resizeCanvases);

// ── INIT ─────────────────────────────────────────────────────────────────────
function init(){{
  resizeCanvases();
  initRadar();
  initHitbox();
  initUtilChart();
  initMomentumChart();
  updateAtff();
  currentHeatGrid=DATA.heatmaps[state.layer]||null;
  drawHeatmap();
  updateKpis();
}}

// Wait for fonts
document.fonts.ready.then(init);
</script>
</body>
</html>"""
