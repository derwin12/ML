# analyze_choreography.py
#
# Reads training_data.json (produced by scan_sequences.py) and builds
# choreography_probs.json: a lightweight probability table mapping each
# prop category to the weighted distribution of effect types that human
# sequencers actually place on that prop type.
#
# Layer weighting: layer 0 (primary) = full weight 1.0; layer N = 1/(N+1).
# This reflects that xLights layer 0 is the main visual effect.
#
# Usage: python analyze_choreography.py
# Output: choreography_probs.json (small, committed to git)

import json
import os
from collections import defaultdict

TRAINING_JSON = os.path.join(os.path.dirname(__file__), "training_data.json")
OUTPUT_JSON   = os.path.join(os.path.dirname(__file__), "choreography_probs.json")

# Map normalized scan model_type values (post-fix) → generator category names.
# scan_sequences.py now emits "arch", "line", "tree" etc. matching utils.py categories.
# A source can feed multiple categories (e.g. "tree" feeds both mega_tree and tree_360).
CATEGORY_SOURCES = {
    "mega_tree":     ["tree"],
    "tree_360":      ["tree"],
    "matrix":        ["matrix"],
    "window_frame":  ["window_frame"],
    "arch":          ["arch"],
    "star":          ["star"],
    "snowflake":     ["snowflake", "star"],  # radial like a star
    "spinner":       ["spinner", "matrix"],
    "line":          ["line", "icicles"],
    "flood":         ["flood", "line"],
    "cane":          ["candy_cane", "line"],
    "cube":          ["cube"],
    "single_strand": ["arch", "line"],
    "unknown":       ["tree", "matrix", "star"],  # average of prominent types
}

# Effects that exist in our generator (skip others like "Pictures", "Off", etc.)
KNOWN_EFFECTS = {
    "On", "Bars", "Color Wash", "Shockwave", "Spirals", "Pinwheel",
    "SingleStrand", "Morph", "Fill", "Ripple", "Wave", "Twinkle",
    "Meteors", "Fire", "Shimmer", "Strobe", "Fan", "Galaxy", "Shape",
    "Warp", "Marquee", "Curtain", "Butterfly", "Snowflakes", "Garlands",
    "Spirograph", "Lightning", "Circles", "Kaleidoscope", "Liquid",
    "Plasma", "Fireworks", "Tendril",
}

# Minimum probability to include an effect in the table (filters noise)
MIN_PROB = 0.01


def layer_weight(layer_index: int) -> float:
    """Layer 0 (primary) = 1.0; each deeper layer is half as important."""
    return 1.0 / (layer_index + 1)


def build_table(training_data: dict) -> dict:
    """
    For each source model_type, accumulate weighted effect counts and average durations.
    Layer 0 effects count fully; layer N counts as 1/(N+1).
    Combine counts per category via CATEGORY_SOURCES, normalize to probabilities.
    """
    # raw_counts[model_type][effect_name] = weighted float count
    # raw_durations[model_type][effect_name] = [duration_ms, ...]
    raw_counts:    dict = defaultdict(lambda: defaultdict(float))
    raw_durations: dict = defaultdict(lambda: defaultdict(list))

    for effect_name, info in training_data.items():
        if effect_name.startswith("_"):
            continue  # skip meta keys like _cooccurrence
        if effect_name not in KNOWN_EFFECTS:
            continue
        for obs in info["observations"]:
            mt = obs.get("model_type", "unknown")
            li = obs.get("layer_index", 0)
            weight = layer_weight(li)
            raw_counts[mt][effect_name] += weight
            dur = obs.get("duration_ms", 0)
            if dur > 0:
                raw_durations[mt][effect_name].append(dur)

    result = {}
    for category, sources in CATEGORY_SOURCES.items():
        merged: dict = defaultdict(float)
        merged_dur: dict = defaultdict(list)

        for src in sources:
            for eff, cnt in raw_counts.get(src, {}).items():
                merged[eff] += cnt
            for eff, durs in raw_durations.get(src, {}).items():
                merged_dur[eff].extend(durs)

        total = sum(merged.values())
        if total == 0:
            continue

        probs = {}
        avg_durations = {}
        for eff, cnt in merged.items():
            p = cnt / total
            if p >= MIN_PROB and eff in KNOWN_EFFECTS:
                probs[eff] = round(p, 4)
                durs = merged_dur.get(eff, [])
                avg_durations[eff] = int(sum(durs) / len(durs)) if durs else 1000

        # Renormalize after filtering
        prob_sum = sum(probs.values())
        if prob_sum > 0:
            probs = {k: round(v / prob_sum, 4) for k, v in probs.items()}

        result[category] = {
            "probs":        probs,
            "avg_duration": avg_durations,
            "total_obs":    round(total, 1),
        }

    return result


def main():
    print(f"Reading {TRAINING_JSON}...")
    with open(TRAINING_JSON, encoding="utf-8") as f:
        training_data = json.load(f)

    print("Building choreography probability table (with layer weighting)...")
    table = build_table(training_data)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)
    print(f"Saved: {OUTPUT_JSON}")

    print()
    for cat, data in sorted(table.items()):
        top = sorted(data["probs"].items(), key=lambda x: -x[1])[:5]
        top_str = "  ".join(f"{e}={p:.0%}" for e, p in top)
        print(f"  {cat:<15} ({data['total_obs']:>9.1f} weighted obs)  {top_str}")


if __name__ == "__main__":
    main()
