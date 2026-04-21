# scan_sequences.py
# Scans .xsq files in a folder (top level only) and extracts effect parameters
# into training_data.json for use by param_sampler.py during generation.

import os
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

XSQ_FOLDER = r"E:\2023\ShowFolder3D"
LAYOUT_XML  = r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\xlights_rgbeffects.xml"
OUTPUT_JSON = r"C:\Users\daryl\PycharmProjects\ML\training_data.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_settings(text: str) -> dict:
    """Parse 'Key=Value;Key=Value' settings text into a dict."""
    result = {}
    if not text:
        return result
    for part in text.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            # Try to coerce to int or float
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


def load_model_types(layout_xml: str) -> dict:
    """Return {model_name_lower: display_as} from xlights_rgbeffects.xml."""
    model_types = {}
    if not os.path.isfile(layout_xml):
        return model_types
    try:
        root = ET.parse(layout_xml).getroot()
        for m in root.findall(".//model"):
            name = m.get("name", "").strip().lower()
            display_as = m.get("DisplayAs", "unknown").lower()
            model_types[name] = display_as
        for g in root.findall(".//modelGroup"):
            name = g.get("name", "").strip().lower()
            model_types[name] = "group"
    except ET.ParseError:
        pass
    return model_types


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
    """
    Return (beat_index, beat_span) for an effect given the beats list.
    beat_index: index of the nearest beat to start_ms (-1 if no beats).
    beat_span: number of beats the effect covers (rounded, minimum 1).
    """
    if not beats:
        return -1, 1
    diffs = [abs(start_ms - b) for b in beats]
    idx = diffs.index(min(diffs))
    if len(beats) > 1:
        avg_beat_ms = (beats[-1] - beats[0]) / (len(beats) - 1)
    else:
        avg_beat_ms = 500
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


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan_folder(folder: str, layout_xml: str) -> dict:
    model_types = load_model_types(layout_xml)

    # {effect_name: [observation, ...]}
    # observation = {params, duration_ms, model_type, section}
    data = defaultdict(list)
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

        for elem in root.findall(".//Element[@type='Model']") + root.findall(".//Element"):
            if elem.get("type") in ("timing", None) and elem.get("type") != "Model":
                # Skip timing tracks and elements without a Model type
                if elem.get("type") != "Model":
                    continue

            model_name  = elem.get("name", "").strip()
            model_type  = model_types.get(model_name.lower(), "unknown")

            for layer in elem.findall("EffectLayer"):
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

                # Compute beat stride between consecutive same-name effects on this layer
                # stride = number of beats between consecutive effect starts (1=every beat, 2=every other, etc.)
                stride_by_name = defaultdict(list)
                if avg_beat_ms > 0:
                    prev_by_name = {}
                    for ename, sms, ems, _ in sorted(layer_effects, key=lambda x: x[1]):
                        if ename in prev_by_name:
                            gap_ms = sms - prev_by_name[ename]
                            stride = max(1, round(gap_ms / avg_beat_ms))
                            stride_by_name[ename].append(stride)
                        prev_by_name[ename] = sms

                for effect_name, start_ms, end_ms, effect in layer_effects:
                    duration_ms = end_ms - start_ms

                    # Get params — inline Settings child preferred, fall back to EffectDB ref
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

                    # Strip palette/color button keys — they're per-sequence, not portable
                    params = {k: v for k, v in params.items()
                              if not k.startswith("C_BUTTON") and not k.startswith("C_CHECKBOX_Palette")}

                    beat_idx, beat_span = beat_index_and_span(start_ms, end_ms, beats)
                    strides = stride_by_name.get(effect_name, [])
                    beat_stride = round(sum(strides) / len(strides)) if strides else 1

                    data[effect_name].append({
                        "params":       params,
                        "duration_ms":  duration_ms,
                        "model_type":   model_type,
                        "section":      section_for_time(start_ms, sections),
                        "beat_span":    beat_span,
                        "beat_stride":  beat_stride,
                        "source":       filename,
                    })

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
        summary[effect_name] = {
            "count":        len(observations),
            "observations": observations,
        }
        durations = [o["duration_ms"] for o in observations]
        summary[effect_name]["duration_stats"] = {
            "min": min(durations),
            "max": max(durations),
            "mean": int(sum(durations) / len(durations)),
        }

    return summary


def main():
    print(f"Scanning: {XSQ_FOLDER}")
    data = scan_folder(XSQ_FOLDER, LAYOUT_XML)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved {len(data)} effect types to {OUTPUT_JSON}")
    for name, info in sorted(data.items(), key=lambda x: -x[1]["count"]):
        print(f"  {name:<25} {info['count']:>5} observations")


if __name__ == "__main__":
    main()
