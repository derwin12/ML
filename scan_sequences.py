# scan_sequences.py
# Scans .xsq files in a folder (top level only) and extracts effect parameters
# into training_data.json for use by param_sampler.py during generation.

import os
import json
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from itertools import combinations

XSQ_FOLDER = r"E:\2023\ShowFolder3D"
LAYOUT_XML  = r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\xlights_rgbeffects.xml"
OUTPUT_JSON = r"C:\Users\daryl\PycharmProjects\ML\training_data.json"

# Map xLights DisplayAs values to generator category names (matches utils.py)
_DISPLAY_AS_TO_CATEGORY = {
    "arches":       "arch",
    "single line":  "line",
    "tree":         "tree",
    "matrix":       "matrix",
    "star":         "star",
    "spinner":      "spinner",
    "sphere":       "sphere",
    "icicles":      "icicles",
    "window frame": "window_frame",
    "snowflake":    "snowflake",
    "wreath":       "unknown",
    "custom":       "unknown",
    "modelgroup":   "group",
    "poly line":    "line",
    "candy canes":  "candy_cane",
    "cube":         "cube",
}

# Categories excluded from co-occurrence analysis (not real prop types)
_SKIP_COOC_CATS = {"group", "unknown", "skip"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_settings(text: str) -> dict:
    """Parse 'Key=Value,Key=Value' settings text into a dict (xLights uses comma delimiter)."""
    result = {}
    if not text:
        return result
    for part in text.split(","):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass
            if k:
                result[k] = v
    return result


def _is_flood(model_elem) -> bool:
    """Single-node Single Line = flood/par-can."""
    if model_elem.get("DisplayAs", "").lower() != "single line":
        return False
    try:
        nps = int(model_elem.get("NodesPerString", model_elem.get("parm1", 0)))
        ns  = int(model_elem.get("NumStrings",    model_elem.get("parm2", 1)))
        lpn = int(model_elem.get("LightsPerNode", 1))
    except (ValueError, TypeError):
        return False
    return nps * ns == 1 and lpn == 1


def load_model_categories(layout_xml: str) -> dict:
    """Return {model_name_lower: category} using the same logic as utils.categorize_models
    so [T:*] description hints, flood promotion, and group classification all match generation."""
    if not os.path.isfile(layout_xml):
        return {}
    try:
        from utils import categorize_models
        root = ET.parse(layout_xml).getroot()
        layout_models = root.findall(".//model")
        layout_groups = root.findall(".//modelGroup")
        cats = categorize_models(layout_models, layout_groups)
        return {k.lower(): v for k, v in cats.items()}
    except Exception as e:
        print(f"[load_model_categories] falling back to DisplayAs map: {e}")
        cats = {}
        try:
            root = ET.parse(layout_xml).getroot()
            for m in root.findall(".//model"):
                if m.get("ShadowModelFor"):
                    continue
                name = m.get("name", "").strip().lower()
                da = m.get("DisplayAs", "unknown").lower()
                cats[name] = "flood" if _is_flood(m) else _DISPLAY_AS_TO_CATEGORY.get(da, "unknown")
            for g in root.findall(".//modelGroup"):
                name = g.get("name", "").strip().lower()
                cats[name] = "group"
        except ET.ParseError:
            pass
        return cats


def extract_effect_db(root) -> list:
    """Extract EffectDB entries as parsed param dicts (for ref-based effects)."""
    effect_db = []
    for eff in root.findall(".//EffectDB/Effect"):
        effect_db.append(parse_settings(eff.text or ""))
    return effect_db


def extract_beats(root) -> list:
    """Return sorted list of beat start times (ms) from the Beats timing track, or []."""
    for elem in root.findall(".//Element[@type='timing']"):
        if elem.get("name", "").lower() == "beats":
            times = []
            for effect in elem.findall(".//Effect"):
                try:
                    times.append(int(effect.get("startTime", 0)))
                except ValueError:
                    pass
            return sorted(times)
    return []


def beat_index_and_span(start_ms: int, end_ms: int, beats: list):
    """Return (beat_index, beat_span) for an effect given the beats list."""
    if not beats:
        return -1, 1
    diffs = [abs(start_ms - b) for b in beats]
    idx = diffs.index(min(diffs))
    avg_beat_ms = (beats[-1] - beats[0]) / (len(beats) - 1) if len(beats) > 1 else 500
    span = max(1, round((end_ms - start_ms) / avg_beat_ms))
    return idx, span


def extract_structure(root) -> list:
    """Return structure sections [{section, start_ms, end_ms}] if a Structure timing track exists."""
    sections = []
    for elem in root.findall(".//Element[@type='timing']"):
        if elem.get("name", "").lower() == "structure":
            for effect in elem.findall(".//Effect"):
                try:
                    sections.append({
                        "section": effect.get("label", ""),
                        "start_ms": int(effect.get("startTime", 0)),
                        "end_ms":   int(effect.get("endTime", 0)),
                    })
                except ValueError:
                    pass
    return sections


def section_for_time(start_ms: int, sections: list) -> str:
    """Return the section name that contains start_ms, or 'unknown'."""
    for s in sections:
        if s["start_ms"] <= start_ms < s["end_ms"]:
            return s["section"]
    return "unknown"


def section_position(start_ms: int, sections: list) -> float:
    """Return 0.0–1.0 position within the containing section (0=section start, 1=end).
    Returns 0.5 if no section contains start_ms."""
    for s in sections:
        if s["start_ms"] <= start_ms < s["end_ms"]:
            duration = s["end_ms"] - s["start_ms"]
            if duration > 0:
                return round((start_ms - s["start_ms"]) / duration, 3)
    return 0.5


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan_folder(folder: str, layout_xml: str) -> dict:
    model_categories = load_model_categories(layout_xml)

    # {effect_name: [observation, ...]}
    data = defaultdict(list)

    # Co-occurrence: "cat:effect+cat:effect" -> count
    cooccurrence: Counter = Counter()

    files_processed = 0
    errors = []

    xsq_files = [
        f for f in os.listdir(folder)
        if f.lower().endswith(".xsq") and os.path.isfile(os.path.join(folder, f))
    ]
    print(f"Found {len(xsq_files)} .xsq files in {folder}")

    for filename in xsq_files:
        filepath = os.path.join(folder, filename)
        try:
            root = ET.parse(filepath).getroot()
        except ET.ParseError as e:
            errors.append(f"{filename}: {e}")
            continue

        effect_db = extract_effect_db(root)
        sections  = extract_structure(root)
        beats     = extract_beats(root)

        avg_beat_ms = 0
        if len(beats) > 1:
            avg_beat_ms = (beats[-1] - beats[0]) / (len(beats) - 1)

        # All effects in this file for co-occurrence: (start_ms, end_ms, category, effect_name)
        file_effects: list = []

        for elem in root.findall(".//Element[@type='timing']"):
            pass  # skip timing elements in main loop below

        model_elems = root.findall(".//Element[@type='Model']")
        # Fallback: some XSQs use Element without explicit type
        if not model_elems:
            model_elems = [e for e in root.findall(".//Element")
                           if e.get("type") not in ("timing", None) or e.get("type") == "Model"]

        for elem in model_elems:
            if elem.get("type") == "timing":
                continue

            model_name = elem.get("name", "").strip()
            category   = model_categories.get(model_name.lower(), "unknown")

            for layer_idx, layer in enumerate(elem.findall("EffectLayer")):
                # Collect and sort all effects on this layer
                layer_effects = []
                for effect in layer.findall("Effect"):
                    effect_name = effect.get("name", "").strip()
                    if not effect_name:
                        continue
                    try:
                        start_ms = int(effect.get("startTime", 0))
                        end_ms   = int(effect.get("endTime", 0))
                    except ValueError:
                        continue
                    if end_ms - start_ms <= 0:
                        continue
                    layer_effects.append((effect_name, start_ms, end_ms, effect))
                layer_effects.sort(key=lambda x: x[1])

                # Beat stride per effect name on this layer
                stride_by_name: dict = defaultdict(list)
                if avg_beat_ms > 0:
                    prev_by_name: dict = {}
                    for ename, sms, ems, _ in layer_effects:
                        if ename in prev_by_name:
                            gap_ms = sms - prev_by_name[ename]
                            stride_by_name[ename].append(max(1, round(gap_ms / avg_beat_ms)))
                        prev_by_name[ename] = sms

                for i, (effect_name, start_ms, end_ms, effect) in enumerate(layer_effects):
                    duration_ms = end_ms - start_ms

                    # Params: inline Settings child preferred, fall back to EffectDB ref
                    params = {}
                    settings_elem = effect.find("Settings")
                    if settings_elem is not None and settings_elem.text:
                        params = parse_settings(settings_elem.text)
                    else:
                        ref = effect.get("ref")
                        if ref is not None:
                            try:
                                params = effect_db[int(ref)]
                            except (IndexError, ValueError):
                                pass

                    # Strip palette/color button keys — per-sequence, not portable
                    params = {k: v for k, v in params.items()
                              if not k.startswith("C_BUTTON") and not k.startswith("C_CHECKBOX_Palette")}

                    # Extract render style and layer blend from params (keep in params too)
                    render_style = str(params.get("B_CHOICE_BufferStyle", "Default"))
                    layer_blend  = str(params.get("T_CHOICE_LayerMethod", "Normal"))

                    beat_idx, beat_span = beat_index_and_span(start_ms, end_ms, beats)
                    strides = stride_by_name.get(effect_name, [])
                    beat_stride = round(sum(strides) / len(strides)) if strides else 1

                    prev_eff = layer_effects[i - 1][0] if i > 0 else None
                    next_eff = layer_effects[i + 1][0] if i < len(layer_effects) - 1 else None

                    data[effect_name].append({
                        "params":           params,
                        "duration_ms":      duration_ms,
                        "model_type":       category,
                        "section":          section_for_time(start_ms, sections),
                        "section_position": section_position(start_ms, sections),
                        "beat_span":        beat_span,
                        "beat_stride":      beat_stride,
                        "layer_index":      layer_idx,
                        "render_style":     render_style,
                        "layer_blend":      layer_blend,
                        "prev_effect":      prev_eff,
                        "next_effect":      next_eff,
                        "source":           filename,
                    })

                    # Collect for co-occurrence (only layer 0 = primary effects)
                    if layer_idx == 0 and category not in _SKIP_COOC_CATS:
                        file_effects.append((start_ms, end_ms, category, effect_name))

        # --- Co-occurrence pass: sample at beats (or every 500ms if no beats) ---
        if file_effects:
            max_end = max(e[1] for e in file_effects)
            sample_times = beats if beats else list(range(0, max_end, 500))
            for t in sample_times:
                active = [(cat, eff) for (sms, ems, cat, eff) in file_effects if sms <= t < ems]
                for (cat_a, eff_a), (cat_b, eff_b) in combinations(active, 2):
                    if cat_a != cat_b:
                        key = "+".join(sorted([f"{cat_a}:{eff_a}", f"{cat_b}:{eff_b}"]))
                        cooccurrence[key] += 1

        files_processed += 1
        if files_processed % 10 == 0:
            print(f"  Processed {files_processed}/{len(xsq_files)} files...")

    print(f"\nDone. {files_processed} files processed, {len(errors)} errors.")
    if errors:
        for e in errors[:5]:
            print(f"  Error: {e}")

    # Build summary stats per effect
    summary = {}
    for effect_name, observations in data.items():
        durations = [o["duration_ms"] for o in observations]
        summary[effect_name] = {
            "count":        len(observations),
            "observations": observations,
            "duration_stats": {
                "min":  min(durations),
                "max":  max(durations),
                "mean": int(sum(durations) / len(durations)),
            },
        }

    # Top co-occurrence pairs (keep all, sorted by count descending)
    summary["_cooccurrence"] = dict(cooccurrence.most_common())

    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scan .xsq files and build training_data.json")
    parser.add_argument("--folder", default=XSQ_FOLDER,
                        help=f"Folder to scan (default: {XSQ_FOLDER})")
    args = parser.parse_args()

    folder = args.folder
    print(f"Scanning: {folder}")
    data = scan_folder(folder, LAYOUT_XML)

    # Separate _cooccurrence for display before writing
    cooc = data.pop("_cooccurrence", {})
    effect_data = data

    output = dict(effect_data)
    output["_cooccurrence"] = cooc

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    effect_count = sum(v["count"] for v in effect_data.values())
    print(f"\nSaved {len(effect_data)} effect types, {effect_count:,} observations → {OUTPUT_JSON}")
    print(f"Co-occurrence pairs: {len(cooc):,}")
    print()
    for name, info in sorted(effect_data.items(), key=lambda x: -x[1]["count"]):
        print(f"  {name:<25} {info['count']:>7,} observations")


if __name__ == "__main__":
    main()
