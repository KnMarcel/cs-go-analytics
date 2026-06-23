"""
heatmap_loader.py
─────────────────
Lädt vorberechnete Heatmap-Bins aus processed/heatmaps/<map>.parquet
und gibt sie als numpy-Array zurück. Gecacht → sofortige Antwort.
"""

import numpy as np
import pandas as pd
import os
import streamlit as st

HEATMAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "processed", "heatmaps")
BINS = 200

# Layer-Namen für die UI
LAYER_MAP = {
    "Schaden – Opfer":     "dmg_vic",
    "Schaden – Schütze":   "dmg_att",
    "Granaten – Einschlag":"nade_land_all",
    "Granaten – Wurf":     "nade_att",
    "CT Schaden – Opfer":  "dmg_vic_ct",
    "T Schaden – Opfer":   "dmg_vic_t",
}

NADE_LAYER_PREFIX = "nade_land_"   # + nade type name


@st.cache_data(show_spinner=False)
def load_heatmap_grid(map_name: str, layer: str) -> np.ndarray:
    """
    Gibt ein (200,200) float32 Array zurück, normalisiert 0–1.
    Gibt None zurück wenn keine Daten vorhanden.
    """
    path = os.path.join(HEATMAP_DIR, f"{map_name}.parquet")
    if not os.path.exists(path):
        return None

    df = pd.read_parquet(path, filters=[("layer", "==", layer)])
    if df.empty:
        return None

    grid = np.zeros((BINS, BINS), dtype=np.float32)
    grid[df["row"].values, df["col"].values] = df["val"].values
    return grid


@st.cache_data(show_spinner=False)
def available_layers(map_name: str) -> list:
    """Gibt alle verfügbaren Layer-Namen für eine Karte zurück."""
    path = os.path.join(HEATMAP_DIR, f"{map_name}.parquet")
    if not os.path.exists(path):
        return []
    df = pd.read_parquet(path, columns=["layer"])
    return sorted(df["layer"].unique().tolist())


@st.cache_data(show_spinner=False)
def available_nade_types(map_name: str) -> list:
    """Gibt alle verfügbaren Granadentypen für eine Karte zurück."""
    layers = available_layers(map_name)
    nades = [l.replace(NADE_LAYER_PREFIX, "")
             for l in layers if l.startswith(NADE_LAYER_PREFIX) and l != "nade_land_all"]
    return sorted(nades)


def is_precomputed(map_name: str) -> bool:
    return os.path.exists(os.path.join(HEATMAP_DIR, f"{map_name}.parquet"))


def get_colorscale(layer: str, nade_type: str = None):
    """Gibt die passende Colorscale für einen Layer zurück."""
    NADE_COLORS = {
        "Smoke":      (136, 146, 164),
        "HE":         (57,  255, 20),
        "Molotov":    (255, 107, 43),
        "Flashbang":  (0,   212, 255),
        "Decoy":      (255, 204, 0),
        "Incendiary": (255, 43,  78),
    }

    if nade_type and nade_type in NADE_COLORS:
        r, g, b = NADE_COLORS[nade_type]
        return [
            [0,   f"rgba({r},{g},{b},0)"],
            [0.3, f"rgba({r},{g},{b},0.45)"],
            [0.7, f"rgba({r},{g},{b},0.82)"],
            [1.0, f"rgba({r},{g},{b},1.0)"],
        ]

    if "ct" in layer:
        return [[0,"rgba(0,0,0,0)"],[0.3,"rgba(0,212,255,0.35)"],
                [0.7,"rgba(0,212,255,0.8)"],[1.0,"rgba(0,212,255,1.0)"]]
    if "_t" in layer and "att" not in layer:
        return [[0,"rgba(0,0,0,0)"],[0.3,"rgba(255,107,43,0.35)"],
                [0.7,"rgba(255,107,43,0.8)"],[1.0,"rgba(255,107,43,1.0)"]]

    # Default: schwarz → cyan → orange → rot → weiß
    return [
        [0,    "rgba(0,0,0,0)"],
        [0.15, "rgba(0,212,255,0.3)"],
        [0.45, "rgba(255,107,43,0.65)"],
        [0.75, "rgba(255,43,78,0.88)"],
        [1.0,  "rgba(255,255,255,1.0)"],
    ]
