import duckdb
import pandas as pd
import os
import streamlit as st

# ── Pfad-Konfiguration ────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
MAPS_DIR      = os.path.join(BASE_DIR, "maps")
MAP_DATA_CSV  = os.path.join(BASE_DIR, "map_data.csv")
HEATMAP_DIR   = os.path.join(PROCESSED_DIR, "heatmaps")

# ── Hugging Face Config ───────────────────────────────────────────────────────
HF_DATASET  = "HeadShottt/CS-GO"
HF_BASE_URL = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main"

# All files to download from HF if not present locally
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


def _download_file(relative_path: str, status_text) -> bool:
    """Download a single file from Hugging Face if not present locally."""
    local_path = os.path.join(PROCESSED_DIR, relative_path)
    if os.path.exists(local_path):
        return True

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    url = f"{HF_BASE_URL}/{relative_path}"
    try:
        import urllib.request
        urllib.request.urlretrieve(url, local_path)
        return True
    except Exception as e:
        st.warning(f"Could not download {relative_path}: {e}")
        return False


@st.cache_resource(show_spinner=False)
def ensure_data_files():
    """
    Check all required parquet files exist locally.
    Download missing ones from Hugging Face.
    Cached — only runs once per session.
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(HEATMAP_DIR, exist_ok=True)

    missing = [f for f in HF_FILES
               if not os.path.exists(os.path.join(PROCESSED_DIR, f))]

    if not missing:
        return True

    total = len(missing)
    bar   = st.progress(0, text=f"Downloading data (0/{total})...")
    for i, f in enumerate(missing):
        bar.progress((i + 1) / total, text=f"⬇️  {f}  ({i+1}/{total})")
        _download_file(f, f)
    bar.empty()
    return True


class DataLoader:
    def __init__(self):
        self.con = duckdb.connect(database=":memory:")

    def _load_parquet_group(self, key: str) -> pd.DataFrame:
        files = PARQUET_FILES[key]
        paths = [os.path.join(PROCESSED_DIR, f) for f in files
                 if os.path.exists(os.path.join(PROCESSED_DIR, f))]
        if not paths:
            st.warning(f"No files found for '{key}'")
            return pd.DataFrame()
        path_list = ", ".join([f"'{p}'" for p in paths])
        return self.con.execute(f"SELECT * FROM read_parquet([{path_list}])").df()

    def _load_map_data(self) -> pd.DataFrame:
        if os.path.exists(MAP_DATA_CSV):
            df = pd.read_csv(MAP_DATA_CSV, index_col=0)
            df.index.name = "map"
            return df.reset_index()
        alt = os.path.join(PROCESSED_DIR, "map_data.parquet")
        if os.path.exists(alt):
            df = self.con.execute(f"SELECT * FROM read_parquet('{alt}')").df()
            if "column0" in df.columns:
                df = df.rename(columns={"column0": "map"})
            return df
        st.warning("map_data not found!")
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
                if not kills.empty and "map" not in kills.columns:
                    kills = kills.merge(file_map, on="file", how="left")
                if not dmg.empty and "map" not in dmg.columns:
                    dmg = dmg.merge(file_map, on="file", how="left")
                if not grenades.empty and "map" not in grenades.columns:
                    grenades = grenades.merge(file_map, on="file", how="left")

            return {"dmg": dmg, "grenades": grenades,
                    "kills": kills, "meta": meta, "map_data": map_data}

        except Exception as e:
            st.error(f"Error loading data: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None
