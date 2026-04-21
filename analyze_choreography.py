# analyze_choreography.py
#
# Reads training_data.json (produced by scan_sequences.py) and builds
# choreography_probs.json: a lightweight probability table mapping each
# prop category to the weighted distribution of effect types that human
# sequencers actually place on that prop type.
#
# Usage: python analyze_choreography.py
# Output: choreography_probs.json (small, committed to git)

import json
import os
from collections import Counter, defaultdict

TRAINING_JSON = os.path.join(os.path.dirname(__file__), "training_data.json")
OUTPUT_JSON   = os.path.join(os.path.dirname(__file__), "choreography_probs.json")

# Map training_data model_type values → one or more of our category names.
# A model_type can feed multiple categories (e.g. "tree" → both mega_tree and tree_360).
CATEGORY_SOURCES = {
    "mega_tree":     ["tree"],
    "tree_360":      ["tree"],
    "matrix":        ["matrix", "window frame"],
    "arch":          ["arches", "wreath"],
    "star":          ["star"],
    "snowflake":     ["star"],       # radial like a star
    "spinner":       ["matrix"],     # similar 2-D surface
    "line":          ["single line", "icicles", "poly line"],
    "flood":         ["single line"],
    "cane":          ["poly line", "single line"],
    "cube":          ["cube"],
    "single_strand": ["arches", "single line"],   # sequential strings
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


def build_table(training_data: dict) -> dict:
    """
    For each source model_type, accumulate effect counts and average durations.
    Then combine counts per category via CATEGORY_SOURCES, normalize to probabilities.
    """
    # raw_counts[model_type][effect_name] = count
    # raw_durations[model_type][effect_name] = [duration_ms, ...]
    raw_counts:    dict = defaultdict(Counter)
    raw_durations: dict = defaultdict(lambda: defaultdict(list))

    for effect_name, info in training_data.items():
        if effect_name not in KNOWN_EFFECTS:
            continue
        for obs in info["observations"]:
            mt = obs.get("model_type", "unknown")
            raw_counts[mt][effect_name] += 1
            dur = obs.get("duration_ms", 0)
            if dur > 0:
                raw_durations[mt][effect_name].append(dur)

    result = {}
    for category, sources in CATEGORY_SOURCES.items():
        merged: Counter = Counter()
        merged_dur: dict = defaultdict(list)

        for src in sources:
            merged.update(raw_counts.get(src, {}))
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
            "total_obs":    total,
        }

    return result


def main():
    print(f"Reading {TRAINING_JSON}...")
    with open(TRAINING_JSON, encoding="utf-8") as f:
        training_data = json.load(f)

    print("Building choreography probability table...")
    table = build_table(training_data)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)
    print(f"Saved: {OUTPUT_JSON}")

    print()
    for cat, data in sorted(table.items()):
        top = sorted(data["probs"].items(), key=lambda x: -x[1])[:5]
        top_str = "  ".join(f"{e}={p:.0%}" for e, p in top)
        print(f"  {cat:<15} ({data['total_obs']:>7} obs)  {top_str}")


if __name__ == "__main__":
    main()
