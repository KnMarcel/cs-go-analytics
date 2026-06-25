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

# Only columns used by the dashboard
DMG_COLS      = "file, round, seconds, att_side, hp_dmg, arm_dmg, hitbox, wp, wp_type, att_pos_x, att_pos_y, vic_pos_x, vic_pos_y"
GRENADES_COLS = "file, round, seconds, att_side, vic_side, hp_dmg, arm_dmg, nade, att_pos_x, att_pos_y, nade_land_x, nade_land_y"
KILLS_COLS    = "file, round, seconds, att_side, vic_side, wp, wp_type, ct_alive, t_alive"
META_COLS     = "file, map, round, start_seconds, end_seconds, winner_side, round_type, ct_eq_val, t_eq_val"


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
                token=os.environ.get("HF_TOKEN"),
                filename=f,
                repo_type="dataset",
                local_dir=PROCESSED_DIR,
            )
        except Exception as e:
            st.warning(f"Could not download {f}: {e}")
    bar.empty()
    return True


class DataLoader:
    def __init__(self):
        self.con = duckdb.connect(database=":memory:")
        self._meta = None
        self._map_data = None

    def _path(self, filename):
        return os.path.join(PROCESSED_DIR, filename)

    def _load_meta(self) -> pd.DataFrame:
        """Load meta once — it's small (6MB) and needed for map list + file lookup."""
        if self._meta is not None:
            return self._meta
        p = self._path("meta.parquet")
        self._meta = self.con.execute(
            f"SELECT {META_COLS} FROM read_parquet('{p}')"
        ).df()
        return self._meta

    def _load_map_data(self) -> pd.DataFrame:
        if self._map_data is not None:
            return self._map_data
        if os.path.exists(MAP_DATA_CSV):
            df = pd.read_csv(MAP_DATA_CSV, index_col=0)
            df.index.name = "map"
            self._map_data = df.reset_index()
            return self._map_data
        alt = self._path("map_data.parquet")
        if os.path.exists(alt):
            df = self.con.execute(f"SELECT * FROM read_parquet('{alt}')").df()
            if "column0" in df.columns:
                df = df.rename(columns={"column0": "map"})
            self._map_data = df
            return self._map_data
        st.warning("⚠️ map_data not found!")
        return pd.DataFrame(columns=["map","StartX","StartY","EndX","EndY","ResX","ResY"])

    @st.cache_data(show_spinner=False)
    def load_for_map(_self, chosen_map: str) -> dict:
        """
        Load only the rows for the selected map.
        Uses DuckDB JOIN to filter at read time — never loads full 10M row tables.
        RAM usage: ~150-300MB instead of ~3GB.
        """
        meta     = _self._load_meta()
        map_data = _self._load_map_data()

        # Get file list for this map
        map_files = meta[meta["map"] == chosen_map]["file"].unique().tolist()
        if not map_files:
            st.warning(f"No data found for map: {chosen_map}")
            return {"dmg": pd.DataFrame(), "grenades": pd.DataFrame(),
                    "kills": pd.DataFrame(), "meta": pd.DataFrame(),
                    "map_data": map_data}

        # Build SQL IN clause
        file_list = ", ".join([f"'{f}'" for f in map_files])

        dmg_path      = _self._path("dmg.parquet")
        grenades_path = _self._path("grenades.parquet")
        kills_path    = _self._path("kills.parquet")

        dmg = _self.con.execute(
            f"SELECT {DMG_COLS} FROM read_parquet('{dmg_path}') WHERE file IN ({file_list})"
        ).df()

        grenades = _self.con.execute(
            f"SELECT {GRENADES_COLS} FROM read_parquet('{grenades_path}') WHERE file IN ({file_list})"
        ).df()

        kills = _self.con.execute(
            f"SELECT {KILLS_COLS} FROM read_parquet('{kills_path}') WHERE file IN ({file_list})"
        ).df()

        meta_map = meta[meta["map"] == chosen_map].copy()

        # Add map column
        dmg["map"]      = chosen_map
        grenades["map"] = chosen_map
        kills["map"]    = chosen_map

        return {
            "dmg":      dmg,
            "grenades": grenades,
            "kills":    kills,
            "meta":     meta_map,
            "map_data": map_data,
        }

    def load_all(self) -> dict:
        """
        Returns lightweight dict with meta + map_data only.
        Full data is loaded per-map via load_for_map().
        """
        try:
            meta     = self._load_meta()
            map_data = self._load_map_data()
            return {
                "dmg":      pd.DataFrame(),  # loaded per map
                "grenades": pd.DataFrame(),  # loaded per map
                "kills":    pd.DataFrame(),  # loaded per map
                "meta":     meta,
                "map_data": map_data,
                "_loader":  self,            # pass loader for per-map loading
            }
        except Exception as e:
            st.error(f"Error loading data: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None
