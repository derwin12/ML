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


# ---------------------------------------------------------------------------
# Choreography probability table
# ---------------------------------------------------------------------------

CHOREOGRAPHY_PATH = os.path.join(os.path.dirname(__file__), "choreography_probs.json")

_choreo: dict = {}
_choreo_loaded: bool = False


def _load_choreo():
    global _choreo, _choreo_loaded
    if _choreo_loaded:
        return
    if os.path.isfile(CHOREOGRAPHY_PATH):
        try:
            with open(CHOREOGRAPHY_PATH, encoding="utf-8") as f:
                _choreo = json.load(f)
            print(f"[param_sampler] Loaded choreography probs: {len(_choreo)} categories.")
        except Exception as e:
            print(f"[param_sampler] choreography_probs.json error ({e}) — skipping.")
    _choreo_loaded = True


def get_effect_probability(effect_name: str, category: str) -> float:
    """Return the learned probability (0–1) of effect_name for a given prop category."""
    _load_choreo()
    cat_data = _choreo.get(category)
    if cat_data is None:
        return 0.0
    return cat_data["probs"].get(effect_name, 0.0)


def get_choreography_probs(category: str) -> dict:
    """Return {effect_name: probability} dict for a category, or {} if unknown."""
    _load_choreo()
    cat_data = _choreo.get(category)
    return dict(cat_data["probs"]) if cat_data else {}


def sample_effect_for_category(category: str, allowed_effects: set = None) -> str | None:
    """
    Weighted-random sample an effect name for a prop category.
    Optionally restrict to only effects in allowed_effects.
    Returns None if no data is available.
    """
    _load_choreo()
    cat_data = _choreo.get(category)
    if not cat_data:
        return None
    probs = cat_data["probs"]
    if allowed_effects:
        probs = {k: v for k, v in probs.items() if k in allowed_effects}
    if not probs:
        return None
    total = sum(probs.values())
    r = random.uniform(0, total)
    cumulative = 0.0
    for name, p in probs.items():
        cumulative += p
        if r <= cumulative:
            return name
    return list(probs.keys())[-1]


def available_effects() -> list:
    """Return list of effect names that have training data."""
    _load()
    return sorted(_data.keys())


# ---------------------------------------------------------------------------
# Transition table  (prev_effect, category) → likely next effects
# ---------------------------------------------------------------------------

_transitions: dict = {}
_transitions_built: bool = False


def _build_transitions():
    global _transitions, _transitions_built
    if _transitions_built:
        return
    _load()
    from collections import defaultdict as _dd
    table = _dd(Counter)
    for effect_name, info in _data.items():
        if effect_name.startswith("_"):
            continue
        for obs in info["observations"]:
            prev = obs.get("prev_effect")
            if not prev:
                continue
            if obs.get("layer_index", 0) != 0:
                continue  # primary-layer transitions only
            cat = obs.get("model_type", "unknown")
            table[(prev, cat)][effect_name] += 1
    _transitions = dict(table)
    _transitions_built = True
    total_keys = len(_transitions)
    print(f"[param_sampler] Transition table built: {total_keys} (prev_effect, category) pairs.")


def sample_next_effect(prev_effect: str, category: str,
                       allowed_effects: set = None) -> str | None:
    """Weighted-random sample the effect that most commonly follows prev_effect
    on a prop of the given category.  Falls back to any-category transitions when
    the specific (prev, category) pair has no data."""
    _build_transitions()

    counts = Counter(_transitions.get((prev_effect, category), {}))
    if not counts:
        # broad fallback: pool all categories for this prev_effect
        for (prev, _cat), next_counts in _transitions.items():
            if prev == prev_effect:
                counts.update(next_counts)
    if not counts:
        return None

    if allowed_effects:
        counts = Counter({k: v for k, v in counts.items() if k in allowed_effects})
    if not counts:
        return None

    total = sum(counts.values())
    r = random.uniform(0, total)
    cumulative = 0.0
    for name, cnt in counts.items():
        cumulative += cnt
        if r <= cumulative:
            return name
    return list(counts.keys())[-1]
