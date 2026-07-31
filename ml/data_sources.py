"""Dataset discovery for TerraMind.

Per SRD section 7, the build process locates datasets rather than requiring a
manually-specified path. This module is the single resolver used by every
training entry point so that central and edge training always read the same
files from the same place.

Search order (first directory that actually contains the requested file wins):

    1. $TERRAMIND_DATA_DIR              explicit override
    2. <root>/TerraMind_Datasets        current layout
    3. <root>/dataset before sowing     legacy advisor layout
    4. <root>/dataset during growth     legacy growth-stage layout
    5. <root>/data, <root>/datasets     conventional fallbacks

Resolution is per-file, not per-directory, so a split layout (advisor data in
one folder, growth data in another) resolves correctly without configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_CANDIDATE_DIRS: List[Path] = [
    PROJECT_ROOT / "TerraMind_Datasets",
    PROJECT_ROOT / "dataset before sowing",
    PROJECT_ROOT / "dataset during growth",
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "datasets",
]

# Filenames that differ between call sites. Any spelling resolves to whichever
# variant is present on disk.
_ALIASES = {
    "crop_production.csv.xlsx": ["crop_production.csv.xlsx", "crop_production_.csv.xlsx"],
    "crop_production_.csv.xlsx": ["crop_production.csv.xlsx", "crop_production_.csv.xlsx"],
}


def _search_dirs() -> Iterable[Path]:
    env = os.getenv("TERRAMIND_DATA_DIR")
    if env:
        yield Path(env)
    yield from _CANDIDATE_DIRS


def find_dataset(filename: str, required: bool = False) -> Optional[Path]:
    """Return the path to ``filename``, or None if it is not present anywhere.

    Set ``required=True`` to raise FileNotFoundError with the full search list
    instead of returning None.
    """
    names = _ALIASES.get(filename, [filename])
    for directory in _search_dirs():
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return candidate

    if required:
        searched = "\n  ".join(str(d) for d in _search_dirs())
        raise FileNotFoundError(
            f"Dataset '{filename}' not found. Searched:\n  {searched}\n"
            f"Set TERRAMIND_DATA_DIR to override."
        )
    return None


def dataset_dir() -> Path:
    """Return the directory holding the bulk of the datasets.

    Used for logging and for code that still wants a directory handle. Falls
    back to the first candidate so callers always get a usable Path.
    """
    for directory in _search_dirs():
        if directory.exists() and any(directory.iterdir()):
            return directory
    return _CANDIDATE_DIRS[0]


# ── Named accessors: one per dataset the Advisor consumes ──────────────────
# Keeping these as functions (not module-level constants) means a dataset that
# appears after import time is still picked up.

def crop_dataset() -> Optional[Path]:
    """Crop Recommender + Federated AdvisorNet training data."""
    return find_dataset("crop_dataset_rebuilt.csv")


def irrigation_dataset() -> Optional[Path]:
    """Sunlight / irrigation-type / irrigation-need training data."""
    return find_dataset("irrigation_prediction.csv")


def crop_production_xlsx() -> Optional[Path]:
    """Yield Predictor primary source."""
    return find_dataset("crop_production.csv.xlsx")


def india_agri_csv() -> Optional[Path]:
    """Yield Predictor secondary source (district-level, has State/District)."""
    return find_dataset("India Agriculture Crop Production.csv")


def icrisat_main() -> Optional[Path]:
    """District Intelligence: 80-column area/production/yield triplets."""
    return find_dataset("ICRISAT-District Level Data.csv")


def icrisat_source() -> Optional[Path]:
    """District Intelligence + Irrigation Prior: canal/tank/tubewell areas."""
    return find_dataset("ICRISAT-District Level Data Source.csv")


def icrisat_irrigation() -> Optional[Path]:
    """District Intelligence + Irrigation Prior: per-crop irrigated area."""
    return find_dataset("ICRISAT-District Level Data Irrigation.csv")


def fertilizer_dataset() -> Optional[Path]:
    """Growth Stage Monitor training data (outside the Advisor refactor)."""
    return find_dataset("fertilizer_giant_training_dataset.csv")


def availability_report() -> dict:
    """Map each known dataset to its resolved path or None. Used by the data audit."""
    return {
        "crop_dataset_rebuilt.csv": crop_dataset(),
        "irrigation_prediction.csv": irrigation_dataset(),
        "crop_production.csv.xlsx": crop_production_xlsx(),
        "India Agriculture Crop Production.csv": india_agri_csv(),
        "ICRISAT-District Level Data.csv": icrisat_main(),
        "ICRISAT-District Level Data Source.csv": icrisat_source(),
        "ICRISAT-District Level Data Irrigation.csv": icrisat_irrigation(),
        "fertilizer_giant_training_dataset.csv": fertilizer_dataset(),
    }


if __name__ == "__main__":
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Dataset dir  : {dataset_dir()}")
    print()
    for name, path in availability_report().items():
        print(f"  {'OK ' if path else 'MISS'}  {name}")
