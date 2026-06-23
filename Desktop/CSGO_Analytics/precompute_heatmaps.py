"""
precompute_heatmaps.py
──────────────────────
Einmalig ausführen: python precompute_heatmaps.py

Liest alle Parquet-Rohdaten, berechnet 200×200 Bin-Grids pro Karte
und speichert sie als kompakte Parquet-Dateien in processed/heatmaps/.

Danach lädt die App die Heatmaps in <100ms statt sie live zu berechnen.
"""

import duckdb
import pandas as pd
import numpy as np
import os
import time

# ── Pfade ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
HEATMAP_DIR   = os.path.join(PROCESSED_DIR, "heatmaps")
MAP_DATA_CSV  = os.path.join(BASE_DIR, "map_data.csv")

BINS = 200  # Grid-Auflösung

os.makedirs(HEATMAP_DIR, exist_ok=True)

# ── DuckDB Verbindung ─────────────────────────────────────────────────────────
con = duckdb.connect()

def load_parquet(filename):
    path = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(path):
        print(f"  ⚠ Nicht gefunden: {path}")
        return pd.DataFrame()
    return con.execute(f"SELECT * FROM read_parquet('{path}')").df()

# ── Kartendaten laden ─────────────────────────────────────────────────────────
print("Loading map data...")
map_data_path = os.path.join(PROCESSED_DIR, "map_data.parquet")
if os.path.exists(map_data_path):
    map_data = con.execute(f"SELECT * FROM read_parquet('{map_data_path}')").df()
    if "column0" in map_data.columns:
        map_data = map_data.rename(columns={"column0": "map"})
elif os.path.exists(MAP_DATA_CSV):
    map_data = pd.read_csv(MAP_DATA_CSV, index_col=0)
    map_data.index.name = "map"
    map_data = map_data.reset_index()
else:
    print("❌ map_data nicht gefunden!")
    exit(1)

print(f"  {len(map_data)} Karten: {map_data['map'].tolist()}")

# ── Rohdaten laden ────────────────────────────────────────────────────────────
print("\nLoading raw data (one-time)...")
t0 = time.time()

dmg      = load_parquet("dmg.parquet")
grenades = load_parquet("grenades.parquet")
meta     = load_parquet("meta.parquet")

print(f"  dmg:      {len(dmg):,} Zeilen")
print(f"  grenades: {len(grenades):,} Zeilen")
print(f"  meta:     {len(meta):,} Zeilen")
print(f"  Loaded in {time.time()-t0:.1f}s")

# map-Spalte per JOIN ergänzen falls nötig
if "map" not in dmg.columns and "file" in dmg.columns and "map" in meta.columns:
    file_map = meta[["file","map"]].drop_duplicates()
    dmg      = dmg.merge(file_map, on="file", how="left")
    grenades = grenades.merge(file_map, on="file", how="left")
    print("  map column added via JOIN")

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────
def world_to_bin(series_x, series_y, mr, bins=BINS):
    """Maps world coords to bin indices, rotated 90° clockwise to match map image."""
    sx, sy = float(mr["StartX"]), float(mr["StartY"])
    ex, ey = float(mr["EndX"]),   float(mr["EndY"])
    # Normalized 0..1
    nx = ((series_x - sx) / (ex - sx)).clip(0, 1)
    ny = ((series_y - sy) / (ey - sy)).clip(0, 1)
    # 90° clockwise rotation: col = (1-ny)*bins, row = nx*bins
    col = ((1 - ny) * (bins - 1)).clip(0, bins-1).astype(int)
    row = (nx * (bins - 1)).clip(0, bins-1).astype(int)
    return col, row  # col=x-axis, row=y-axis in grid[row,col]

def compute_grid(df, xcol, ycol, mr, bins=BINS):
    """Computes a bins×bins count grid from coordinate columns."""
    valid = df[[xcol, ycol]].dropna()
    valid = valid[(valid[xcol] != 0) | (valid[ycol] != 0)]
    if valid.empty:
        return np.zeros((bins, bins), dtype=np.float32)
    col, row = world_to_bin(valid[xcol], valid[ycol], mr, bins)
    grid = np.zeros((bins, bins), dtype=np.float32)
    np.add.at(grid, (row, col), 1)  # grid[row, col]
    return grid

def smooth_and_normalize(grid):
    """Gaussian smoothing + Normalisierung auf 0–1."""
    from scipy.ndimage import gaussian_filter
    g = gaussian_filter(grid.astype(np.float32), sigma=2.5)
    mx = g.max()
    if mx > 0:
        g = g / mx
    return g

def grid_to_df(grid, layer_name):
    """Speichert ein 200×200 Grid als flaches DataFrame (sparse: nur >0)."""
    rows, cols = np.where(grid > 0.001)
    vals = grid[rows, cols]
    return pd.DataFrame({"row": rows.astype(np.uint8),
                          "col": cols.astype(np.uint8),
                          "val": vals.astype(np.float32),
                          "layer": layer_name})

# ── Pro Karte berechnen ───────────────────────────────────────────────────────
print(f"\nComputing {BINS}×{BINS} heatmap bins per map...\n")
total_start = time.time()

for _, mr in map_data.iterrows():
    map_name = mr["map"]
    out_path = os.path.join(HEATMAP_DIR, f"{map_name}.parquet")

    if os.path.exists(out_path):
        print(f"  ✓ {map_name} — already exists, skipping")
        continue

    t1 = time.time()
    print(f"  ⚙ {map_name}...", end=" ", flush=True)

    dm = dmg[dmg["map"] == map_name]      if "map" in dmg.columns      else dmg
    gr = grenades[grenades["map"] == map_name] if "map" in grenades.columns else grenades

    layers = []

    # Schaden – Opfer-Position
    g = smooth_and_normalize(compute_grid(dm, "vic_pos_x", "vic_pos_y", mr))
    layers.append(grid_to_df(g, "dmg_vic"))

    # Schaden – Schützen-Position
    g = smooth_and_normalize(compute_grid(dm, "att_pos_x", "att_pos_y", mr))
    layers.append(grid_to_df(g, "dmg_att"))

    # Granaten – Einschlag (gesamt + pro Typ)
    if not gr.empty and "nade_land_x" in gr.columns:
        g = smooth_and_normalize(compute_grid(gr, "nade_land_x", "nade_land_y", mr))
        layers.append(grid_to_df(g, "nade_land_all"))

        if "nade" in gr.columns:
            # Molotov (T) and Incendiary (CT) are the same consumable — merge into "Fire"
            gr_named = gr.copy()
            gr_named["nade"] = gr_named["nade"].replace({"Molotov": "Fire", "Incendiary": "Fire"})
            for nade_type in gr_named["nade"].dropna().unique():
                sub = gr_named[gr_named["nade"] == nade_type]
                g = smooth_and_normalize(compute_grid(sub, "nade_land_x", "nade_land_y", mr))
                layers.append(grid_to_df(g, f"nade_land_{nade_type}"))

    # Granaten – Wurf-Position
    if not gr.empty and "att_pos_x" in gr.columns:
        g = smooth_and_normalize(compute_grid(gr, "att_pos_x", "att_pos_y", mr))
        layers.append(grid_to_df(g, "nade_att"))

    # CT / T separat für Schaden
    for side, label in [("CounterTerrorist","ct"), ("Terrorist","t")]:
        if "att_side" in dm.columns:
            sub = dm[dm["att_side"] == side]
            g = smooth_and_normalize(compute_grid(sub, "vic_pos_x", "vic_pos_y", mr))
            layers.append(grid_to_df(g, f"dmg_vic_{label}"))

    if not layers:
        print("no data")
        continue

    result = pd.concat(layers, ignore_index=True)
    result.to_parquet(out_path, index=False, compression="snappy")

    elapsed = time.time() - t1
    size_kb = os.path.getsize(out_path) / 1024
    print(f"{elapsed:.1f}s → {size_kb:.0f} KB ({len(result):,} Einträge, {result['layer'].nunique()} Layer)")

print(f"\n✅ Done in {time.time()-total_start:.1f}s")
print(f"📁 Saved to: {HEATMAP_DIR}")
print("\nAvailable layers per map:")
for _, mr in map_data.iterrows():
    p = os.path.join(HEATMAP_DIR, f"{mr['map']}.parquet")
    if os.path.exists(p):
        df = pd.read_parquet(p)
        print(f"  {mr['map']}: {sorted(df['layer'].unique().tolist())}")
