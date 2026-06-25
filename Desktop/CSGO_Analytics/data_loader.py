import duckdb
import pandas as pd
import os
import streamlit as st

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
MAPS_DIR      = os.path.join(BASE_DIR, "maps")
MAP_DATA_CSV  = os.path.join(BASE_DIR, "map_data.csv")
HEATMAP_DIR   = os.path.join(PROCESSED_DIR, "heatmaps")

HF_DATASET = "HeadShottt/CS-GO"

HF_FILES = [
    "dmg.parquet",
    "grenades.parquet",
    "kills.parquet",
    "meta.parquet",
    "map_data.parquet",
    "heatmaps/de_cache.parquet",
    "heatmaps/de_cbble.parquet",
    "heatmaps/de_dust2.parquet",
    "heatmaps/de_inferno.parquet",
    "heatmaps/de_mirage.parquet",
    "heatmaps/de_overpass.parquet",
    "heatmaps/de_train.parquet",
]

PARQUET_FILES = {
    "dmg":      ["dmg.parquet"],
    "grenades": ["grenades.parquet"],
    "kills":    ["kills.parquet"],
    "meta":     ["meta.parquet"],
}

# Only load columns used by the dashboard — reduces RAM by ~70%
COLUMNS = {
    "dmg": "file, round, seconds, att_side, hp_dmg, arm_dmg, hitbox, wp, wp_type, att_pos_x, att_pos_y, vic_pos_x, vic_pos_y",
    "grenades": "file, round, seconds, att_side, vic_side, hp_dmg, arm_dmg, nade, att_pos_x, att_pos_y, nade_land_x, nade_land_y",
    "kills": "file, round, seconds, att_side, vic_side, wp, wp_type, ct_alive, t_alive",
    "meta": "file, map, round, start_seconds, end_seconds, winner_side, round_type, ct_eq_val, t_eq_val",
}


@st.cache_resource(show_spinner=False)
def ensure_data_files():
    """Download missing files from Hugging Face. Runs once per session."""
    from huggingface_hub import hf_hub_download
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(HEATMAP_DIR, exist_ok=True)

    missing = [f for f in HF_FILES
               if not os.path.exists(os.path.join(PROCESSED_DIR, f))]
    if not missing:
        return True

    total = len(missing)
    bar = st.progress(0, text=f"Downloading data (0/{total})...")
    for i, f in enumerate(missing):
        bar.progress((i + 1) / total, text=f"⬇️ {f} ({i+1}/{total})")
        try:
            hf_hub_download(
                repo_id=HF_DATASET,
                filename=f,
                repo_type="dataset",
                local_dir=PROCESSED_DIR,
            )
        except Exception as e:
            st.warning(f"Could not download {f}: {e}")
    bar.empty()
    return True


# ── Alles unten ist identisch mit der Original-Version ───────────────────────

class DataLoader:
    def __init__(self):
        self.con = duckdb.connect(database=":memory:")

    def _load_parquet_group(self, key: str) -> pd.DataFrame:
        files = PARQUET_FILES[key]
        paths = []
        for f in files:
            full = os.path.join(PROCESSED_DIR, f)
            if os.path.exists(full):
                paths.append(full)
            else:
                st.warning(f"⚠️ Datei nicht gefunden: {full}")

        if not paths:
            st.warning(f"⚠️ Keine Dateien für '{key}' gefunden. Gesucht in: {PROCESSED_DIR}")
            return pd.DataFrame()

        path_list = ", ".join([f"'{p}'" for p in paths])
        cols = COLUMNS.get(key, "*")
        query = f"SELECT {cols} FROM read_parquet([{path_list}])"
        return self.con.execute(query).df()

    def _load_map_data(self) -> pd.DataFrame:
        if os.path.exists(MAP_DATA_CSV):
            df = pd.read_csv(MAP_DATA_CSV, index_col=0)
            df.index.name = "map"
            return df.reset_index()
        alt_parquet = os.path.join(PROCESSED_DIR, "map_data.parquet")
        if os.path.exists(alt_parquet):
            df = self.con.execute(f"SELECT * FROM read_parquet('{alt_parquet}')").df()
            if "column0" in df.columns:
                df = df.rename(columns={"column0": "map"})
            return df
        alt_csv = os.path.join(PROCESSED_DIR, "map_data.csv")
        if os.path.exists(alt_csv):
            df = pd.read_csv(alt_csv, index_col=0)
            df.index.name = "map"
            return df.reset_index()
        st.warning("⚠️ map_data.csv nicht gefunden!")
        return pd.DataFrame(columns=["map","StartX","StartY","EndX","EndY","ResX","ResY"])

    def load_all(self) -> dict:
        try:
            dmg      = self._load_parquet_group("dmg")
            grenades = self._load_parquet_group("grenades")
            kills    = self._load_parquet_group("kills")
            meta     = self._load_parquet_group("meta")
            map_data = self._load_map_data()

            if not meta.empty and "map" in meta.columns and "file" in meta.columns:
                file_map = meta[["file","map"]].drop_duplicates()
                if not kills.empty and "map" not in kills.columns and "file" in kills.columns:
                    kills = kills.merge(file_map, on="file", how="left")
                if not dmg.empty and "map" not in dmg.columns and "file" in dmg.columns:
                    dmg = dmg.merge(file_map, on="file", how="left")
                if not grenades.empty and "map" not in grenades.columns and "file" in grenades.columns:
                    grenades = grenades.merge(file_map, on="file", how="left")

            return {
                "dmg":      dmg,
                "grenades": grenades,
                "kills":    kills,
                "meta":     meta,
                "map_data": map_data,
            }

        except Exception as e:
            st.error(f"Fehler beim Laden der Daten: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None
