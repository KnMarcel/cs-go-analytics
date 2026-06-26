import duckdb
import pandas as pd
import os
import streamlit as st

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
MAP_DATA_CSV  = os.path.join(BASE_DIR, "map_data.csv")
HEATMAP_DIR   = os.path.join(PROCESSED_DIR, "heatmaps")

HF_DATASET = "HeadShottt/CS-GO"

# Small files always needed
HF_BASE_FILES = [
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

TABLES = ["dmg", "grenades", "kills"]


def _hf_download(filename):
    from huggingface_hub import hf_hub_download
    local_path = os.path.join(PROCESSED_DIR, filename)
    if os.path.exists(local_path):
        return True
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        hf_hub_download(
            repo_id=HF_DATASET,
            filename=filename,
            repo_type="dataset",
            local_dir=PROCESSED_DIR,
            token=os.environ.get("HF_TOKEN"),
        )
        return True
    except Exception as e:
        st.warning(f"Could not download {filename}: {e}")
        return False


@st.cache_resource(show_spinner=False)
def ensure_base_files():
    """Download small base files (meta, map_data, heatmaps) once."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(HEATMAP_DIR, exist_ok=True)
    missing = [f for f in HF_BASE_FILES
               if not os.path.exists(os.path.join(PROCESSED_DIR, f))]
    if not missing:
        return True
    bar = st.progress(0, text="Downloading base data...")
    for i, f in enumerate(missing):
        bar.progress((i+1)/len(missing), text=f"⬇️ {f}")
        _hf_download(f)
    bar.empty()
    return True


@st.cache_data(show_spinner=False)
def load_map_data(chosen_map: str) -> dict:
    """
    Download and load only the per-map parquet files.
    Each file is ~30-80MB instead of 400MB+.
    Cached per map — switching maps loads new files.
    """
    bar = st.progress(0, text=f"Loading {chosen_map}...")
    result = {}
    for i, table in enumerate(TABLES):
        filename = f"{table}_{chosen_map}.parquet"
        bar.progress((i+1)/len(TABLES), text=f"⬇️ {filename}")
        _hf_download(filename)
        path = os.path.join(PROCESSED_DIR, filename)
        if os.path.exists(path):
            result[table] = pd.read_parquet(path)
            result[table]["map"] = chosen_map
        else:
            result[table] = pd.DataFrame()
    bar.empty()
    return result


class DataLoader:
    def __init__(self):
        self.con = duckdb.connect(database=":memory:")

    def _load_meta(self) -> pd.DataFrame:
        p = os.path.join(PROCESSED_DIR, "meta.parquet")
        return self.con.execute(
            f"SELECT file, map, round, start_seconds, end_seconds, "
            f"winner_side, round_type, ct_eq_val, t_eq_val "
            f"FROM read_parquet('{p}')"
        ).df()

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
        return pd.DataFrame(columns=["map","StartX","StartY","EndX","EndY","ResX","ResY"])

    def load_all(self) -> dict:
        try:
            meta     = self._load_meta()
            map_data = self._load_map_data()
            return {
                "dmg":      pd.DataFrame(),
                "grenades": pd.DataFrame(),
                "kills":    pd.DataFrame(),
                "meta":     meta,
                "map_data": map_data,
            }
        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None
