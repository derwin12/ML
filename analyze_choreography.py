# analyze_choreography.py
#
# Reads training_data.json (produced by scan_sequences.py) and builds
# choreography_probs.json: a probability table mapping each prop category
# to the weighted distribution of effect types, both globally and per section.
#
# Output structure:
#   {category: {
#     "global":  {probs, avg_duration, total_obs},
#     "chorus":  {probs, avg_duration, total_obs},
#     "verse":   {probs, avg_duration, total_obs},
#     "intro":   {probs, avg_duration, total_obs},
#     "outro":   {probs, avg_duration, total_obs},
#     "bridge":  {probs, avg_duration, total_obs},
#     "pre_chorus": {probs, avg_duration, total_obs},
#   }}
#
# Layer weighting: layer 0 (primary) = 1.0; layer N = 1/(N+1).
#
# Usage: python analyze_choreography.py

import json
import os
from collections import defaultdict

TRAINING_JSON = os.path.join(os.path.dirname(__file__), "training_data.json")
OUTPUT_JSON   = os.path.join(os.path.dirname(__file__), "choreography_probs.json")

CATEGORY_SOURCES = {
    "mega_tree":     ["tree"],
    "tree_360":      ["tree"],
    "matrix":        ["matrix"],
    "window_frame":  ["window_frame"],
    "arch":          ["arch"],
    "star":          ["star"],
    "snowflake":     ["snowflake", "star"],
    "spinner":       ["spinner", "matrix"],
    "line":          ["line", "icicles"],
    "flood":         ["flood", "line"],
    "cane":          ["candy_cane", "line"],
    "cube":          ["cube"],
    "single_strand": ["arch", "line"],
    "unknown":       ["tree", "matrix", "star"],
}

KNOWN_EFFECTS = {
    "On", "Bars", "Color Wash", "Shockwave", "Spirals", "Pinwheel",
    "SingleStrand", "Morph", "Fill", "Ripple", "Wave", "Twinkle",
    "Meteors", "Fire", "Shimmer", "Strobe", "Fan", "Galaxy", "Shape",
    "Warp", "Marquee", "Curtain", "Butterfly", "Snowflakes", "Garlands",
    "Spirograph", "Lightning", "Circles", "Kaleidoscope", "Liquid",
    "Plasma", "Fireworks", "Tendril", "VU Meter",
}

# Canonical section types — normalized from free-text labels
SECTION_TYPES = ["chorus", "verse", "intro", "outro", "bridge", "pre_chorus"]

MIN_PROB       = 0.01
MIN_SECTION_OBS = 10   # minimum weighted obs to emit a per-section bucket


def normalize_section(label: str) -> str:
    """Map free-text section labels to a canonical type."""
    l = label.lower().strip()
    if any(w in l for w in ("chorus", "drop", "hook", "refrain")):
        return "chorus"
    if "verse" in l:
        return "verse"
    if "intro" in l or "opening" in l:
        return "intro"
    if any(w in l for w in ("outro", "ending", "coda", "fade")):
        return "outro"
    if "bridge" in l or "interlude" in l:
        return "bridge"
    if "pre" in l:
        return "pre_chorus"
    return "unknown"


def layer_weight(layer_index: int) -> float:
    return 1.0 / (layer_index + 1)


def _empty_accum():
    return {"counts": defaultdict(float), "durations": defaultdict(list)}


def _finalize(accum: dict, min_obs: float = MIN_PROB) -> dict | None:
    """Convert raw counts → normalized probs. Returns None if insufficient data."""
    counts = accum["counts"]
    durs   = accum["durations"]
    total  = sum(counts.values())
    if total < 1:
        return None

    probs = {}
    avg_durations = {}
    for eff, cnt in counts.items():
        p = cnt / total
        if p >= MIN_PROB and eff in KNOWN_EFFECTS:
            probs[eff] = round(p, 4)
            d = durs.get(eff, [])
            avg_durations[eff] = int(sum(d) / len(d)) if d else 1000

    prob_sum = sum(probs.values())
    if prob_sum == 0:
        return None
    probs = {k: round(v / prob_sum, 4) for k, v in probs.items()}

    return {"probs": probs, "avg_duration": avg_durations, "total_obs": round(total, 1)}


def build_table(training_data: dict) -> dict:
    # raw[model_type][section_type] = {counts, durations}
    # section_type is one of SECTION_TYPES or "global"
    raw: dict = defaultdict(lambda: defaultdict(_empty_accum))

    for effect_name, info in training_data.items():
        if effect_name.startswith("_"):
            continue
        if effect_name not in KNOWN_EFFECTS:
            continue
        for obs in info["observations"]:
            mt     = obs.get("model_type", "unknown")
            li     = obs.get("layer_index", 0)
            w      = layer_weight(li)
            dur    = obs.get("duration_ms", 0)
            sec    = normalize_section(obs.get("section", ""))

            raw[mt]["global"]["counts"][effect_name] += w
            if dur > 0:
                raw[mt]["global"]["durations"][effect_name].append(dur)

            if sec != "unknown":
                raw[mt][sec]["counts"][effect_name] += w
                if dur > 0:
                    raw[mt][sec]["durations"][effect_name].append(dur)

    result = {}
    for category, sources in CATEGORY_SOURCES.items():
        cat_entry = {}

        for bucket in ["global"] + SECTION_TYPES:
            merged = _empty_accum()
            for src in sources:
                src_bucket = raw.get(src, {}).get(bucket, {})
                for eff, cnt in src_bucket.get("counts", {}).items():
                    merged["counts"][eff] += cnt
                for eff, durs in src_bucket.get("durations", {}).items():
                    merged["durations"][eff].extend(durs)

            min_req = 1 if bucket == "global" else MIN_SECTION_OBS
            total = sum(merged["counts"].values())
            if total < min_req:
                continue

            finalized = _finalize(merged)
            if finalized:
                cat_entry[bucket] = finalized

        if "global" in cat_entry:
            result[category] = cat_entry

    return result


def main():
    print(f"Reading {TRAINING_JSON}...")
    with open(TRAINING_JSON, encoding="utf-8") as f:
        training_data = json.load(f)

    print("Building section-aware choreography probability table...")
    table = build_table(training_data)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)
    print(f"Saved: {OUTPUT_JSON}")

    print()
    for cat, data in sorted(table.items()):
        sections_present = [s for s in ["global"] + SECTION_TYPES if s in data]
        top = sorted(data["global"]["probs"].items(), key=lambda x: -x[1])[:4]
        top_str = "  ".join(f"{e}={p:.0%}" for e, p in top)
        print(f"  {cat:<15} sections={sections_present}  global top: {top_str}")


if __name__ == "__main__":
    main()
