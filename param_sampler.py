# param_sampler.py
# Loads training_data.json and provides sample_params(effect_name)
# used by effect modules during generation.

import json
import os
import random
from collections import defaultdict

TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), "training_data.json")

_data: dict = {}
_loaded: bool = False


def _load():
    global _data, _loaded
    if _loaded:
        return
    if os.path.isfile(TRAINING_DATA_PATH):
        try:
            with open(TRAINING_DATA_PATH, "r", encoding="utf-8") as f:
                _data = json.load(f)
            total = sum(v["count"] for v in _data.values())
            print(f"[param_sampler] Loaded training data: {len(_data)} effect types, {total} observations.")
        except (json.JSONDecodeError, Exception) as e:
            print(f"[param_sampler] training_data.json is corrupt ({e}) — using fallback random params.")
            _data = {}
    else:
        print(f"[param_sampler] No training_data.json found — using fallback random params.")
    _loaded = True


def sample_params(effect_name: str, model_type: str = None, section: str = None) -> dict:
    """
    Return a param dict sampled from real observations for effect_name.
    Optionally filter by model_type and/or section if enough data exists.
    Returns an empty dict if no training data is available — callers fall back to defaults.
    """
    _load()

    if effect_name not in _data:
        return {}

    observations = _data[effect_name]["observations"]
    if not observations:
        return {}

    # Try to filter by section first (most specific), fall back to all observations
    filtered = observations
    if section:
        sec_obs = [o for o in observations if section.lower() in o.get("section", "").lower()]
        if len(sec_obs) >= 5:
            filtered = sec_obs

    # Further filter by model_type if enough data remains
    if model_type:
        type_obs = [o for o in filtered if o.get("model_type", "") == model_type]
        if len(type_obs) >= 5:
            filtered = type_obs

    observation = random.choice(filtered)
    return dict(observation.get("params", {}))


def sample_duration(effect_name: str, fallback_min: int = 3000, fallback_max: int = 10000) -> int:
    """Return a duration_ms sampled from real observations, or a random fallback."""
    _load()

    if effect_name not in _data:
        return random.randint(fallback_min, fallback_max)

    observations = _data[effect_name]["observations"]
    if not observations:
        return random.randint(fallback_min, fallback_max)

    return random.choice(observations)["duration_ms"]


def sample_beat_stride(effect_name: str, model_type: str = None) -> int:
    """
    Return a beat stride sampled from real observations (1 = every beat, 2 = every other, etc.).
    Falls back to 2 if no data or beat_stride field not present.
    """
    _load()

    if effect_name not in _data:
        return 2

    observations = _data[effect_name]["observations"]
    pool = observations
    if model_type:
        typed = [o for o in observations if o.get("model_type", "") == model_type]
        if len(typed) >= 5:
            pool = typed

    strides = [o["beat_stride"] for o in pool if "beat_stride" in o and 1 <= o["beat_stride"] <= 8]
    if not strides:
        return 2

    return random.choice(strides)


def has_data(effect_name: str) -> bool:
    """Return True if training data exists for this effect type."""
    _load()
    return effect_name in _data and _data[effect_name]["count"] > 0


def available_effects() -> list:
    """Return list of effect names that have training data."""
    _load()
    return sorted(_data.keys())
