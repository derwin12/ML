# utils.py (updated with structure track generation)

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import random
from mutagen.mp3 import MP3
import librosa
import re
from openai import OpenAI

LEMONADE_BASE_URL = os.environ.get("LEMONADE_URL", "http://localhost:8000/api/v1")
LEMONADE_MODEL = os.environ.get("LEMONADE_MODEL", "")

# Maps xLights DisplayAs values to internal category strings
_DISPLAY_AS_MAP = {
    "arches": "arch",
    "single line": "line",
    "tree": "tree",
    "matrix": "matrix",
    "star": "star",
    "spinner": "spinner",
    "sphere": "sphere",
    "icicles": "icicles",
    "wreath": "unknown",
    "custom": "unknown",
    "window frame": "window_frame",
    "snowflake": "snowflake",
    "modelgroup": "group",
}

_TYPE_HINT_RE = re.compile(r'\[T:([^\]]+)\]', re.IGNORECASE)

_NAME_RULES_PATH = os.path.join(os.path.dirname(__file__), "name_category_rules.json")


def _has_pixel_list(val: str) -> bool:
    """True if val looks like a pixel number list (digits/commas/hyphens, no file path chars)."""
    return bool(val) and not any(c in val for c in "\\/") and any(c.isdigit() for c in val)


def _is_singing_prop(model_elem):
    """True if model has a <faceInfo> child with both numeric Mouth-WQ and Eyes-Open pixel lists.
    Requiring both ensures decorative props with incidental face definitions are excluded.
    """
    for child in model_elem:
        if child.tag == "faceInfo":
            mouth = child.attrib.get("Mouth-WQ", "") or ""
            eyes  = child.attrib.get("Eyes-Open", "") or ""
            if _has_pixel_list(mouth) and _has_pixel_list(eyes):
                return True
    return False


_NAME_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "name_exact_overrides.json")

# Categories unsuitable for specific effects.
# Key = effect name as used in place_effect(); value = set of categories that should NOT receive it.
_FLOOD_LINE = frozenset({"flood", "line", "icicles"})
EFFECT_EXCLUDED_CATS: dict = {
    # Pixel-grid effects — bad on 1D strands and point fixtures
    "Galaxy":        _FLOOD_LINE | {"candy_cane"},
    "Kaleidoscope":  _FLOOD_LINE | {"candy_cane"},
    "Fireworks":     _FLOOD_LINE | {"candy_cane"},
    "Plasma":        _FLOOD_LINE,
    "Liquid":        _FLOOD_LINE,
    "Warp":          _FLOOD_LINE,
    "Spirograph":    _FLOOD_LINE,
    "Circles":       _FLOOD_LINE,
    "Morph":         frozenset({"flood"}),
    # SingleStrand only valid on strand-like models
    "SingleStrand":  frozenset({"matrix", "matrix_horizontal", "matrix_column", "matrix_pole",
                                "sphere", "cube", "flood", "star", "snowflake", "spinner",
                                "tree", "mega_tree"}),
    # Fire looks best on tall vertical structures — skip 2D panels and point fixtures
    "Fire":          frozenset({"flood", "matrix", "matrix_horizontal", "matrix_column",
                                "matrix_pole", "snowflake", "star", "spinner", "sphere", "cube"}),
    # Strobe/Lightning should stay off floods (single-channel, no visible flash pattern)
    "Strobe":        frozenset({"flood"}),
    "Lightning":     frozenset({"flood"}),
}


def filter_by_effect(elements: list, effect_name: str, model_categories: dict) -> list:
    """Return elements whose category is not excluded for the given effect."""
    excluded = EFFECT_EXCLUDED_CATS.get(effect_name)
    if not excluded:
        return elements
    return [e for e in elements if model_categories.get(e.attrib.get("name", "")) not in excluded]

def _load_name_category_rules():
    """Load name-based category rules from JSON; fall back to a minimal hardcoded list."""
    try:
        with open(_NAME_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules", [])
        if rules:
            return rules
    except Exception as e:
        print(f"Warning: could not load name_category_rules.json ({e}); using built-in rules.")
    return [
        {"match": "arch",         "category": "arch"},
        {"match": "matrix",       "category": "matrix"},
        {"match": "tree",         "category": "tree"},
        {"match": "flood",        "category": "flood"},
        {"match": "line",         "category": "line"},
    ]


def _load_name_exact_overrides() -> dict:
    """Load exact-name overrides from JSON; returns {} on missing/error."""
    try:
        with open(_NAME_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("overrides", {})
        # Normalise keys to lowercase for case-insensitive lookup
        return {k.lower(): v for k, v in raw.items()}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Warning: could not load name_exact_overrides.json ({e})")
        return {}


class EffectDBRegistry:
    """
    Maintains a deduplicated list of effect settings strings for the xLights EffectDB.
    Each unique settings string gets a 0-based index; Effect elements reference it via ref="N".
    """
    def __init__(self):
        self._entries = []
        self._index = {}

    def get_or_add(self, settings_str: str) -> int:
        if settings_str not in self._index:
            idx = len(self._entries)
            self._entries.append(settings_str)
            self._index[settings_str] = idx
        return self._index[settings_str]

    def write_to_xml(self, effect_db_elem):
        for child in list(effect_db_elem):
            effect_db_elem.remove(child)
        for settings_str in self._entries:
            entry = ET.SubElement(effect_db_elem, "Effect")
            entry.text = settings_str


def place_effect(effect_layer, name: str, start_time: int, end_time: int,
                 palette_id: int, settings_str: str, registry: EffectDBRegistry):
    """Create a self-closing Effect element that references an EffectDB entry."""
    ref_id = registry.get_or_add(settings_str)
    ET.SubElement(effect_layer, "Effect", {
        "ref": str(ref_id),
        "name": name,
        "startTime": str(start_time),
        "endTime": str(end_time),
        "selected": "0",
        "palette": str(palette_id),
    })


def categorize_models(layout_models, layout_groups):
    """
    Returns dict[name -> category_str] for all models and groups.
    Auto-skips image and DMX models ('skip' category).
    Resolution order: [T:*] description hint > DisplayAs mapping > 'unknown'.
    Groups with all same-category members get that category; diverse groups become
    'generic_group' (excluded from effects); the largest group becomes 'everything_group'.
    """
    categories = {}

    # --- Individual models ---
    for m in layout_models:
        name = m.attrib.get("name", "Unnamed")
        desc = m.attrib.get("Description", "") or ""
        display_as = m.attrib.get("DisplayAs", "") or ""
        protocol = m.attrib.get("Protocol", "") or ""

        # Auto-skip inactive, image, and DMX models
        if m.attrib.get("Active", "1") == "0" or display_as.lower() == "image" or protocol.upper() == "DMX":
            categories[name] = "skip"
            continue

        hint = _TYPE_HINT_RE.search(desc)
        if hint:
            categories[name] = hint.group(1).lower()
        elif display_as.lower() == "custom" and _is_singing_prop(m):
            categories[name] = "singing_prop"
        else:
            categories[name] = _DISPLAY_AS_MAP.get(display_as.lower(), "unknown")

        # Single-line models that are floods: 1 node total (NodesPerString=1, NumStrings=1)
        # Also catches older XML that uses parm1 for node count
        if categories[name] == "line":
            try:
                nodes_per_string = int(m.attrib.get("NodesPerString") or m.attrib.get("parm1") or 0)
                num_strings      = int(m.attrib.get("NumStrings") or m.attrib.get("parm2") or 1)
                lights_per_node  = int(m.attrib.get("LightsPerNode") or 1)
                total_nodes = nodes_per_string * num_strings
                if total_nodes == 1 and lights_per_node == 1:
                    categories[name] = "flood"
            except (ValueError, TypeError):
                pass

    # --- Groups ---
    group_members = {}
    for g in layout_groups:
        name = g.attrib.get("name", "Unnamed")
        models_str = g.attrib.get("models", "") or ""
        members = [x.strip() for x in models_str.split(",") if x.strip()]
        group_members[name] = members

    # Everything group = the one with the most members
    everything_group = max(group_members, key=lambda n: len(group_members[n])) if group_members else None

    for g in layout_groups:
        name = g.attrib.get("name", "Unnamed")
        desc = g.attrib.get("Description", "") or ""

        if name == everything_group:
            categories[name] = "everything_group"
            continue

        # [T:*] hint overrides member-based classification
        hint = _TYPE_HINT_RE.search(desc)
        if hint:
            categories[name] = hint.group(1).lower()
            continue

        members = group_members.get(name, [])
        member_cats = {categories.get(m, "unknown") for m in members} - {"unknown"}
        if len(member_cats) == 1:
            categories[name] = member_cats.pop()
        else:
            categories[name] = "generic_group"

    # Secondary pass: resolve remaining unknowns by name keyword (case-insensitive)
    name_rules = _load_name_category_rules()
    resolved_by_name = []
    for name in list(categories.keys()):
        if categories[name] == "unknown":
            name_lower = name.lower()
            for rule in name_rules:
                kw = rule["match"].lower()
                cat = rule["category"]
                exact = rule.get("exact", False)
                matched = (name_lower == kw) if exact else (kw in name_lower)
                if matched:
                    categories[name] = cat
                    resolved_by_name.append(f"{name} → {cat}")
                    break

    # Parent-group inheritance: unknowns inherit category from their parent group(s)
    # Build reverse map: model_name → set of group names it belongs to
    _INHERITABLE = {"unknown", "generic_group"}
    _NON_INHERITABLE = {"unknown", "generic_group", "everything_group", "skip"}
    member_of: dict = {}
    for g in layout_groups:
        gname = g.attrib.get("name", "Unnamed")
        models_str = g.attrib.get("models", "") or ""
        for m in (x.strip() for x in models_str.split(",") if x.strip()):
            member_of.setdefault(m, set()).add(gname)

    resolved_by_parent = []
    for name in list(categories.keys()):
        if categories[name] not in _INHERITABLE:
            continue
        parent_cats = {
            categories[g] for g in member_of.get(name, set())
            if categories.get(g) not in _NON_INHERITABLE
        }
        if len(parent_cats) == 1:
            inherited = parent_cats.pop()
            categories[name] = inherited
            resolved_by_parent.append(f"{name} → {inherited}")

    # Exact-name overrides: user-supplied final word (skips auto-skip models)
    exact_overrides = _load_name_exact_overrides()
    resolved_by_override = []
    for name in list(categories.keys()):
        if categories[name] == "skip":
            continue
        if name.lower() in exact_overrides:
            cat = exact_overrides[name.lower()]
            categories[name] = cat
            resolved_by_override.append(f"{name} → {cat}")

    unknown_names = sorted(n for n, c in categories.items() if c == "unknown")
    if resolved_by_name:
        print(f"Name-resolved ({len(resolved_by_name)}): {', '.join(resolved_by_name)}")
    if resolved_by_parent:
        print(f"Parent-inherited ({len(resolved_by_parent)}): {', '.join(resolved_by_parent)}")
    if resolved_by_override:
        print(f"Exact overrides ({len(resolved_by_override)}): {', '.join(resolved_by_override)}")
    if unknown_names:
        print(f"Still unknown ({len(unknown_names)}): {', '.join(unknown_names)}")

    return categories

def _lemonade_client():
    return OpenAI(base_url=LEMONADE_BASE_URL, api_key="lemonade")

def _get_model() -> str:
    """Return configured model, or auto-discover the first available model from Lemonade."""
    if LEMONADE_MODEL:
        return LEMONADE_MODEL
    client = _lemonade_client()
    models = client.models.list()
    first = models.data[0].id if models.data else None
    if not first:
        raise RuntimeError("No models available on Lemonade server.")
    print(f"Lemonade auto-selected model: {first}")
    return first

def _lemonade_complete(prompt: str) -> str:
    """Send a prompt to Lemonade and return the text response."""
    client = _lemonade_client()
    response = client.chat.completions.create(
        model=_get_model(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content or ""

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
    if level == 0:
        elem.text = "\n  "

def load_structure_map(structure_json_path):
    """Load the xlights_template_structures.json file and pick the Empty Sequence base if possible."""
    if not os.path.isfile(structure_json_path):
        raise FileNotFoundError(f"Structure map not found: {structure_json_path}")

    with open(structure_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Prefer the one named 'Empty Sequence.xsq', else take first entry
    for entry in data:
        if entry["file"].lower().startswith("empty sequence"):
            print(f"Using structure from template: {entry['file']}")
            return entry

    print("No 'Empty Sequence.xsq' found in structure map — using first entry.")
    return data[0] if data else None

def get_audio_duration(audio_path):
    """Get duration of audio file in seconds."""
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    try:
        audio = MP3(audio_path)
        return audio.info.length
    except Exception as e:
        raise ValueError(f"Could not read audio duration: {e}")

def get_eligible_models(layout_models, layout_groups, model_categories=None):
    """
    Returns (eligible_groups, eligible_individuals, everything_group_name).
    Generic groups are excluded; the everything group is returned separately.
    """
    if model_categories is None:
        model_categories = {}

    eligible_groups = []
    eligible_individuals = []
    everything_group_name = None
    inactive_skipped = []

    for m in layout_models:
        model_name = m.attrib.get("name", "Unnamed")
        if m.attrib.get("Active", "1") == "0":
            inactive_skipped.append(model_name)
            continue
        display_as = m.attrib.get("DisplayAs", "").lower()
        protocol = m.attrib.get("Protocol", "").upper()
        layout = m.attrib.get('Layout', '').lower()
        group_check = (layout == 'group' or display_as == 'group')
        if model_categories.get(model_name) in ("skip", "singing_prop"):
            continue
        if (display_as != "image" and
            protocol != "DMX" and
            not model_name.upper().startswith("MH-")):
            if group_check:
                eligible_groups.append(model_name)
            else:
                eligible_individuals.append(model_name)

    for g in layout_groups:
        group_name = g.attrib.get("name", "Unnamed")
        if g.attrib.get("Active", "1") == "0":
            inactive_skipped.append(group_name)
            continue
        if group_name.upper().startswith("MH-"):
            continue
        cat = model_categories.get(group_name, "")
        if cat == "skip":
            continue
        if cat == "everything_group":
            everything_group_name = group_name
        elif cat == "generic_group":
            pass  # excluded from effect placement
        else:
            eligible_groups.append(group_name)

    if inactive_skipped:
        print(f"Inactive models/groups skipped ({len(inactive_skipped)}): {', '.join(sorted(inactive_skipped))}")

    return eligible_groups, eligible_individuals, everything_group_name


def find_singing_props(layout_models):
    """Return dict of model_name -> face_definition_name for all singing prop models.
    Prefers the CustomColors='1' face definition (the colored one); falls back to first valid match.
    """
    result = {}
    for m in layout_models:
        if m.attrib.get("Active", "1") == "0":
            continue
        if m.attrib.get("DisplayAs", "").lower() != "custom":
            continue
        fallback_name = None
        colored_name = None
        for child in m:
            if child.tag != "faceInfo":
                continue
            mouth = child.attrib.get("Mouth-WQ", "") or ""
            eyes  = child.attrib.get("Eyes-Open", "") or ""
            if not (_has_pixel_list(mouth) and _has_pixel_list(eyes)):
                continue
            face_def = child.attrib.get("Name", "Green")
            if fallback_name is None:
                fallback_name = face_def
            if child.attrib.get("CustomColors", "0") == "1":
                colored_name = face_def
        chosen = colored_name or fallback_name
        if chosen:
            result[m.attrib.get("name", "Unnamed")] = chosen
    return result


def sort_models(layout_models, layout_groups):
    all_model_list = []
    for m in layout_models:
        model_name = m.attrib.get("name", "Unnamed")
        display_as = m.attrib.get('DisplayAs', '').lower()
        layout = m.attrib.get('Layout', '').lower()
        is_group = (layout == 'group' or display_as == 'group')
        all_model_list.append((is_group, model_name))

    for g in layout_groups:
        group_name = g.attrib.get("name", "Unnamed")
        all_model_list.append((True, group_name))  # modelGroups are always groups

    # Sort: normal groups first, then "last" groups, then individuals; alphabetical within each
    def sort_key(item):
        is_group, name = item
        if is_group:
            if "last" in name.lower():
                return (1, name)  # "last" groups second
            else:
                return (0, name)  # normal groups first
        else:
            return (2, name)  # individuals last

    all_model_list.sort(key=sort_key)
    sorted_all_model_names = [name for _, name in all_model_list]
    return sorted_all_model_names

def update_metadata(head, seq_type, seq_timing, media_file, song, artist, duration):
    if head is not None:
        seq_dur_elem = head.find("sequenceDuration")
        if seq_dur_elem is not None:
            seq_dur_elem.text = f"{duration:.3f}"

        seq_type_elem = head.find("sequenceType")
        if seq_type_elem is not None:
            seq_type_elem.text = seq_type

        seq_timing_elem = head.find("sequenceTiming")
        if seq_timing_elem is not None:
            seq_timing_elem.text = seq_timing

        media_file_elem = head.find("mediaFile")
        if media_file_elem is not None:
            media_file_elem.text = media_file

        song_elem = head.find("song")
        if song_elem is not None:
            song_elem.text = song

        artist_elem = head.find("artist")
        if artist_elem is not None:
            artist_elem.text = artist

_SHADER_PATH = os.path.join(os.path.dirname(__file__),
                            "training data", "folder 1", "Shaders", "Black Cherry Cosmos.fs")


def add_everything_group_effect(element, seq_duration_ms, color_palettes, registry: "EffectDBRegistry"):
    """Place a Black Cherry Cosmos shader spanning the full sequence on the everything group."""
    effect_layer = element.find("EffectLayer")
    if effect_layer is None:
        effect_layer = ET.SubElement(element, "EffectLayer")

    palette_str = (
        "C_BUTTON_Palette1=#FFFFFF,C_BUTTON_Palette2=#FF0000,C_BUTTON_Palette3=#00FF00,"
        "C_BUTTON_Palette4=#0000FF,C_BUTTON_Palette5=#FFFF00,C_BUTTON_Palette6=#000000,"
        "C_BUTTON_Palette7=#00FFFF,C_BUTTON_Palette8=#FF00FF,"
        "C_CHECKBOXBRIGHTNESSLEVEL=0,C_CHECKBOX_Chroma=0,C_CHECKBOX_MusicSparkles=0,"
        "C_CHECKBOX_Palette1=1,C_CHECKBOX_Palette2=1,C_CHECKBOX_Palette3=0,"
        "C_CHECKBOX_Palette4=0,C_CHECKBOX_Palette5=0,C_CHECKBOX_Palette6=0,"
        "C_CHECKBOX_Palette7=0,C_CHECKBOX_Palette8=0,C_SLIDER_SparkleFrequency=0"
    )
    new_palette = ET.SubElement(color_palettes, "ColorPalette")
    new_palette.text = palette_str
    palette_id = len(color_palettes.findall("ColorPalette")) - 1

    settings_str = (
        f"E_0FILEPICKERCTRL_IFS={_SHADER_PATH},"
        "E_SLIDER_SHADERXYZZY_mouseX=0,E_SLIDER_SHADERXYZZY_mouseY=0,"
        "E_SLIDER_Shader_Speed=100,E_TEXTCTRL_Shader_LeadIn=0,"
        "E_TEXTCTRL_Shader_Offset_X=0,E_TEXTCTRL_Shader_Offset_Y=0,"
        "E_TEXTCTRL_Shader_Zoom=0,T_CHECKBOX_Canvas=0,T_CHECKBOX_LayerMorph=0,"
        "T_CHOICE_LayerMethod=Normal,T_SLIDER_EffectLayerMix=0"
    )
    place_effect(effect_layer, "Shader", 0, seq_duration_ms, palette_id, settings_str, registry)


def _load_audio(audio_path):
    """Load audio file with librosa. Returns (y, sr)."""
    print(f"Loading audio: {audio_path}")
    y, sr = librosa.load(audio_path, sr=None)
    print(f"Audio loaded: {len(y)/sr:.1f}s at {sr}Hz")
    return y, sr


def _add_timing_track(name, markers, labels, display_elem, element_effects, seq_duration_ms):
    """Write a named timing track into DisplayElements and ElementEffects."""
    ET.SubElement(display_elem, "Element", {
        "collapsed": "0", "type": "timing", "name": name,
        "visible": "1", "active": "0"
    })
    elem = ET.SubElement(element_effects, "Element", {"type": "timing", "name": name})
    layer = ET.SubElement(elem, "EffectLayer")
    for i, (t_ms, label) in enumerate(zip(markers, labels)):
        end_ms = markers[i + 1] if i + 1 < len(markers) else seq_duration_ms
        ET.SubElement(layer, "Effect", {
            "label": label,
            "startTime": str(t_ms),
            "endTime": str(end_ms),
        })


def generate_beats_track(y, sr, display_elem, element_effects, seq_duration_ms):
    """Detect beats and write the Beats timing track. Returns beat times as ms list."""
    _, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
    markers = [int(b * 1000) for b in beats]
    labels  = [str((i % 4) + 1) for i in range(len(markers))]
    _add_timing_track("Beats", markers, labels, display_elem, element_effects, seq_duration_ms)
    print(f"Beats track: {len(markers)} beats detected.")
    return markers


def generate_downbeats_track(y, sr, display_elem, element_effects, seq_duration_ms):
    """Write a Downbeats timing track (every 4th beat = bar 1). Returns downbeat ms list."""
    _, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
    downbeats = beats[::4]
    markers = [int(b * 1000) for b in downbeats]
    labels  = [str(i + 1) for i in range(len(markers))]
    _add_timing_track("Downbeats", markers, labels, display_elem, element_effects, seq_duration_ms)
    print(f"Downbeats track: {len(markers)} bars detected.")
    return markers


def generate_onsets_track(y, sr, display_elem, element_effects, seq_duration_ms):
    """Detect note/drum onsets and write the Onsets timing track. Returns onset ms list."""
    onset_times = librosa.onset.onset_detect(y=y, sr=sr, units='time')
    markers = [int(t * 1000) for t in onset_times]
    labels  = [""] * len(markers)
    _add_timing_track("Onsets", markers, labels, display_elem, element_effects, seq_duration_ms)
    print(f"Onsets track: {len(markers)} onsets detected.")
    return markers


def generate_energy_peaks_track(y, sr, display_elem, element_effects, seq_duration_ms):
    """Detect RMS energy peaks and write the Energy Peaks timing track. Returns peak ms list."""
    import numpy as np
    rms = librosa.feature.rms(y=y)[0]
    # Smooth with a 10-frame rolling mean then pick peaks
    kernel = np.ones(10) / 10
    rms_smooth = np.convolve(rms, kernel, mode='same')
    peak_frames = librosa.util.peak_pick(
        rms_smooth,
        pre_max=3, post_max=3,
        pre_avg=5,  post_avg=5,
        delta=float(rms_smooth.mean() * 0.2),
        wait=int(sr / 512 * 0.25),  # ~0.25 s minimum gap between peaks
    )
    peak_times = librosa.frames_to_time(peak_frames, sr=sr)
    markers = [int(t * 1000) for t in peak_times]
    labels  = [""] * len(markers)
    _add_timing_track("Energy Peaks", markers, labels, display_elem, element_effects, seq_duration_ms)
    print(f"Energy Peaks track: {len(markers)} peaks detected.")
    return markers


def generate_stem_tracks(audio_path, display_elem, element_effects, seq_duration_ms,
                         output_dir=None, model="htdemucs_6s"):
    """
    Separate audio into stems with Demucs then build timing tracks for each instrument.
    Drum stem → kick, snare, hihat, toms, cymbal tracks (frequency-filtered onsets).
    Bass, guitar, piano stems → onset tracks.
    Returns dict of track_name -> list[int] ms.
    """
    from stem_separator import separate_stems, extract_drum_onsets, get_stem_onsets

    print("=== Stem separation starting ===")
    stems = separate_stems(audio_path, output_dir=output_dir, model=model)

    all_tracks = {}

    # Drum sub-tracks
    if "drums" in stems and os.path.isfile(stems["drums"]):
        print("Extracting drum sub-tracks...")
        drum_hits = extract_drum_onsets(stems["drums"])
        for drum_name, ms_list in drum_hits.items():
            if ms_list:
                labels = [""] * len(ms_list)
                track_name = drum_name.capitalize()
                _add_timing_track(track_name, ms_list, labels, display_elem, element_effects, seq_duration_ms)
                all_tracks[track_name] = ms_list
                print(f"  {track_name} track: {len(ms_list)} markers")

    # Melodic stems
    for stem in ("bass", "guitar", "piano"):
        if stem in stems and os.path.isfile(stems[stem]):
            print(f"Extracting {stem} onsets...")
            ms_list = get_stem_onsets(stems[stem], stem)
            if ms_list:
                labels = [""] * len(ms_list)
                track_name = stem.capitalize()
                _add_timing_track(track_name, ms_list, labels, display_elem, element_effects, seq_duration_ms)
                all_tracks[track_name] = ms_list
                print(f"  {track_name} track: {len(ms_list)} markers")

    print(f"=== Stem tracks done: {list(all_tracks.keys())} ===")
    return all_tracks


def _fetch_lyrics(song_name: str, artist_name: str, duration_s: float) -> dict:
    """
    Fetch the best-matching lyrics dict from lrclib.net or return {}.

    Strategy:
      1. /api/get with duration — lrclib does its own near-match on duration.
      2. If that fails, /api/search + pick the candidate whose duration is
         closest to ours, provided it is within max(10s, 5% of our duration).
    """
    import urllib.request
    import urllib.parse

    base = "https://lrclib.net/api"
    tolerance = max(10.0, duration_s * 0.05)

    # Step 1: direct fetch with duration hint
    params = urllib.parse.urlencode({
        "artist_name": artist_name,
        "track_name":  song_name,
        "duration":    int(duration_s),
    })
    try:
        req = urllib.request.Request(
            f"{base}/get?{params}",
            headers={"User-Agent": "xlights-ai-generator/1.0 (darylerwin@kulplights.com)"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                data = json.loads(r.read().decode())
                if data and data.get("syncedLyrics"):
                    return data
    except Exception as e:
        print(f"lrclib /get failed: {e}")

    # Step 2: search fallback — pick nearest duration with syncedLyrics
    params = urllib.parse.urlencode({
        "artist_name": artist_name,
        "q":           song_name,
    })
    try:
        req = urllib.request.Request(
            f"{base}/search?{params}",
            headers={"User-Agent": "xlights-ai-generator/1.0 (darylerwin@kulplights.com)"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                results = json.loads(r.read().decode())
                candidates = [x for x in results if x.get("syncedLyrics")]
                if not candidates:
                    candidates = [x for x in results if x.get("plainLyrics")]
                if candidates:
                    best = min(candidates, key=lambda x: abs(x.get("duration", 0) - duration_s))
                    delta = abs(best.get("duration", 0) - duration_s)
                    if delta <= tolerance:
                        print(f"lrclib search matched '{best.get('trackName')}' by "
                              f"'{best.get('artistName')}' ({best.get('duration')}s, "
                              f"Δ{delta:.1f}s from {duration_s:.1f}s)")
                        return best
                    else:
                        print(f"lrclib search: closest match is {delta:.1f}s away "
                              f"(tolerance {tolerance:.1f}s) — skipping.")
    except Exception as e:
        print(f"lrclib /search failed: {e}")

    return {}


def _parse_lrc(synced_lyrics: str) -> list:
    """Parse LRC-format string into sorted list of (time_ms, text) tuples."""
    pattern = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)')
    lines = []
    for raw in synced_lyrics.splitlines():
        m = pattern.match(raw.strip())
        if m:
            minutes, seconds, text = m.group(1), m.group(2), m.group(3).strip()
            time_ms = int(float(minutes) * 60_000 + float(seconds) * 1_000)
            if text:
                lines.append((time_ms, text))
    lines.sort(key=lambda x: x[0])
    return lines


def generate_lyrics_track(song_name: str, artist_name: str, duration_s: float,
                           display_elem, element_effects, seq_duration_ms) -> list:
    """
    Fetch synced lyrics from lrclib.net and write a Lyrics timing track.
    Returns list of (time_ms, line_text) tuples, or [] if not found.
    """
    print(f"Fetching lyrics: '{song_name}' by {artist_name} ({duration_s:.1f}s)…")
    track = _fetch_lyrics(song_name, artist_name, duration_s)
    if not track:
        print("No lyrics found on lrclib.net.")
        return []

    synced = track.get("syncedLyrics") or ""
    if not synced:
        print("Plain lyrics only — no timestamps, skipping Lyrics track.")
        return []

    lines = _parse_lrc(synced)
    if not lines:
        print("syncedLyrics parsed to zero lines — skipping.")
        return []

    markers = [t   for t, _ in lines]
    labels  = [txt for _, txt in lines]
    _add_timing_track("Lyrics", markers, labels, display_elem, element_effects, seq_duration_ms)
    print(f"Lyrics track: {len(lines)} lines "
          f"(matched: '{track.get('trackName')}' by '{track.get('artistName')}', "
          f"{track.get('duration')}s)")
    return lines


def generate_structure_track(audio_path, song_name, artist_name, display_elem, element_effects, seq_duration_ms):
    """
    Generate a song structure timing track using Lemonade based on song name, artist, and audio duration.
    Adds a timing track named 'Structure' to DisplayElements and ElementEffects.
    Returns the structure data as a list of dictionaries with section names and timings.
    """
    # Get audio duration in seconds
    duration = get_audio_duration(audio_path)

    # Create prompt for Lemonade
    prompt = f"""
    You are a music analysis assistant tasked with generating a song structure for a specific song and artist.
    The song is "{song_name}" by {artist_name}, with a duration of {duration:.2f} seconds.
    Generate a timing track named "Structure" that lists the start and end times (in seconds) for each section
    (e.g., Intro, Verse 1, Pre-Chorus, Chorus, Verse 2, Pre-Chorus, Chorus, Bridge, Chorus, Outro).
    Ensure the timings are realistic for a modern pop song with a romantic vibe, including at least 7 sections to capture
    typical pop song complexity. The sections must cover the entire duration without gaps or overlaps.

    Output the response in strict JSON format, ensuring:
    - The 'structure' array contains objects with 'section' (string), 'start' (float, seconds), and 'end' (float, seconds).
    - The sections must start at 0 and end at the song's duration ({duration:.2f} seconds).
    - No gaps or overlaps between sections (end time of one section equals start time of the next).
    - At least 7 sections, but more can be included if appropriate.
    - No trailing commas in the 'structure' array.
    - No inline comments or extra text outside the JSON structure.

    Example:
    ```json
    {{
      "structure": [
        {{"section": "Intro", "start": 0.0, "end": 10.0}},
        {{"section": "Verse 1", "start": 10.0, "end": 40.0}},
        {{"section": "Pre-Chorus", "start": 40.0, "end": 55.0}},
        {{"section": "Chorus", "start": 55.0, "end": 85.0}},
        {{"section": "Verse 2", "start": 85.0, "end": 115.0}},
        {{"section": "Pre-Chorus", "start": 115.0, "end": 130.0}},
        {{"section": "Chorus", "start": 130.0, "end": 160.0}},
        {{"section": "Bridge", "start": 160.0, "end": 185.0}},
        {{"section": "Chorus", "start": 185.0, "end": 215.0}},
        {{"section": "Outro", "start": 215.0, "end": 233.0}}
      ]
    }}
    """
    print(f"Sending structure prompt to Lemonade:\n{prompt}")

    try:
        stdout = _lemonade_complete(prompt)
        print(f"Lemonade structure response: {stdout}")

        # Extract JSON portion
        start_idx = stdout.find('{')
        end_idx = stdout.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            print(f"No valid JSON found in Lemonade structure output: {stdout}. Using fallback structure.")
            # Fallback structure
            structure = [
                {"section": "Intro", "start": 0.0, "end": duration * 0.1},
                {"section": "Verse 1", "start": duration * 0.1, "end": duration * 0.4},
                {"section": "Chorus", "start": duration * 0.4, "end": duration * 0.7},
                {"section": "Verse 2", "start": duration * 0.7, "end": duration * 0.9},
                {"section": "Outro", "start": duration * 0.9, "end": duration}
            ]
        else:
            json_str = stdout[start_idx:end_idx]
            json_str = re.sub(r'//.*?(?=\n|$)', '', json_str)  # Remove comments
            json_str = re.sub(r',\s*\]', r']', json_str)  # Remove trailing comma
            print(f"Fixed structure JSON: {json_str}")
            data = json.loads(json_str)
            structure = data.get('structure', [])

            # Validate shape/types only — timing problems are repaired below
            if not structure or not all(
                isinstance(s, dict) and
                isinstance(s.get('section'), str) and
                isinstance(s.get('start'), (int, float)) and
                isinstance(s.get('end'), (int, float))
                for s in structure
            ):
                print(f"Unparseable structure from Lemonade — using fallback.")
                structure = [
                    {"section": "Intro",   "start": 0.0,           "end": duration * 0.1},
                    {"section": "Verse 1", "start": duration * 0.1, "end": duration * 0.4},
                    {"section": "Chorus",  "start": duration * 0.4, "end": duration * 0.7},
                    {"section": "Verse 2", "start": duration * 0.7, "end": duration * 0.9},
                    {"section": "Outro",   "start": duration * 0.9, "end": duration},
                ]

        # Repair rather than reject — fix whatever Lemonade got wrong
        structure.sort(key=lambda x: x['start'])

        # 1. Anchor first section at 0
        structure[0]['start'] = 0.0

        # 2. Drop sections that start at or beyond the song duration, or are inverted
        before = len(structure)
        structure = [s for s in structure if s['start'] < duration and s['start'] < s['end']]
        if len(structure) < before:
            print(f"Dropped {before - len(structure)} out-of-range/inverted section(s).")

        if not structure:
            print("Structure empty after repair — using fallback.")
            structure = [
                {"section": "Intro",   "start": 0.0,            "end": duration * 0.1},
                {"section": "Verse 1", "start": duration * 0.1,  "end": duration * 0.4},
                {"section": "Chorus",  "start": duration * 0.4,  "end": duration * 0.7},
                {"section": "Verse 2", "start": duration * 0.7,  "end": duration * 0.9},
                {"section": "Outro",   "start": duration * 0.9,  "end": duration},
            ]
        else:
            # 3. Clamp any section end that overshoots the song duration
            for s in structure:
                if s['end'] > duration:
                    s['end'] = duration

            # 4. Stitch: align each section's start to the previous section's end
            #    (fixes both gaps and overlaps in one pass)
            for i in range(1, len(structure)):
                structure[i]['start'] = structure[i - 1]['end']

            # 5. Drop zero-length sections created by stitching
            structure = [s for s in structure if s['start'] < s['end']]

            # 6. Ensure last section reaches exactly the end of the song
            structure[-1]['end'] = duration

        print(f"Structure: {[s['section'] for s in structure]}")

        # Add to DisplayElements
        ET.SubElement(display_elem, "Element", {
            "collapsed": "0",
            "type": "timing",
            "name": "Structure",
            "visible": "1",
            "active": "0"
        })

        # Add to ElementEffects
        structure_effect_elem = ET.SubElement(element_effects, "Element", {
            "type": "timing",
            "name": "Structure"
        })

        effect_layer = ET.SubElement(structure_effect_elem, "EffectLayer")

        for section in structure:
            start_ms = int(section['start'] * 1000)
            end_ms = int(section['end'] * 1000)
            ET.SubElement(effect_layer, "Effect", {
                "label": section['section'],
                "startTime": f"{start_ms}",
                "endTime": f"{end_ms}"
            })

        return structure

    except Exception as e:
        print(f"Lemonade API error for structure track: {e}")
        # Fallback structure
        structure = [
            {"section": "Intro", "start": 0.0, "end": duration * 0.1},
            {"section": "Verse 1", "start": duration * 0.1, "end": duration * 0.4},
            {"section": "Chorus", "start": duration * 0.4, "end": duration * 0.7},
            {"section": "Verse 2", "start": duration * 0.7, "end": duration * 0.9},
            {"section": "Outro", "start": duration * 0.9, "end": duration}
        ]
        # Add to DisplayElements
        ET.SubElement(display_elem, "Element", {
            "collapsed": "0",
            "type": "timing",
            "name": "Structure",
            "visible": "1",
            "active": "0"
        })

        # Add to ElementEffects
        structure_effect_elem = ET.SubElement(element_effects, "Element", {
            "type": "timing",
            "name": "Structure"
        })

        effect_layer = ET.SubElement(structure_effect_elem, "EffectLayer")

        for section in structure:
            start_ms = int(section['start'] * 1000)
            end_ms = int(section['end'] * 1000)
            ET.SubElement(effect_layer, "Effect", {
                "label": section['section'],
                "startTime": f"{start_ms}",
                "endTime": f"{end_ms}"
            })

        return structure

# ---------------------------------------------------------------------------
# Beat helpers
# ---------------------------------------------------------------------------

def beats_ms(beats):
    return [int(b * 1000) for b in beats]

def snap_to_beat(time_ms, beat_times_ms):
    return min(beat_times_ms, key=lambda b: abs(b - time_ms))

def beat_aligned_window(beat_times_ms, min_beats=1, max_beats=8):
    """Pick a random start/end aligned to beat boundaries; return (start_ms, end_ms)."""
    if len(beat_times_ms) < 2:
        return None, None
    available = len(beat_times_ms) - 1
    lo = min(min_beats, available)
    hi = min(max_beats, available)
    if lo > hi:
        lo = hi
    span = random.randint(lo, hi)
    start_idx = random.randint(0, max(0, len(beat_times_ms) - span - 1))
    end_idx = min(start_idx + span, len(beat_times_ms) - 1)
    return beat_times_ms[start_idx], beat_times_ms[end_idx]


# ---------------------------------------------------------------------------
# Structure helpers
# ---------------------------------------------------------------------------

SECTION_INTENSITY = {
    "intro":      0.3,
    "verse":      0.5,
    "pre-chorus": 0.7,
    "chorus":     1.0,
    "bridge":     0.8,
    "outro":      0.3,
    "breakdown":  0.4,
    "drop":       1.0,
}

# Max total effects per model, keyed by category
CATEGORY_EFFECT_BUDGET = {
    "flood":         4,
    "single_strand": 6,
    "line":          8,
    "arch":          10,
    "star":          8,
    "snowflake":     8,
    "cane":          6,
    "cube":          12,
    "matrix":        20,
    "mega_tree":     20,
    "tree_360":      15,
    "spinner":       12,
    "unknown":       8,
}

_CHORUS_INTENSITY_THRESHOLD = 0.9  # chorus=1.0, drop=1.0 qualify; bridge=0.8 does not


class EffectBudget:
    """Tracks how many effects have been placed on each model and enforces per-category caps."""
    def __init__(self, model_categories: dict):
        self._categories = model_categories
        self._counts: dict = {}

    def is_full(self, model_name: str) -> bool:
        cat = self._categories.get(model_name, "unknown")
        budget = CATEGORY_EFFECT_BUDGET.get(cat, 8)
        return self._counts.get(model_name, 0) >= budget

    def charge(self, model_name: str):
        self._counts[model_name] = self._counts.get(model_name, 0) + 1


_active_budget: 'EffectBudget | None' = None


def set_effect_budget(budget):
    global _active_budget
    _active_budget = budget

def section_intensity(section_name: str) -> float:
    key = section_name.lower()
    for k, v in SECTION_INTENSITY.items():
        if k in key:
            return v
    return 0.6

def get_section_for_beat(beat_ms: int, structure: list):
    for sec in structure:
        if int(sec["start"] * 1000) <= beat_ms < int(sec["end"] * 1000):
            return sec
    return None

def beats_for_section(beat_times_ms: list, section: dict) -> list:
    s = int(section["start"] * 1000)
    e = int(section["end"] * 1000)
    return [b for b in beat_times_ms if s <= b < e]


def structure_weighted_beat_window(beat_times_ms: list, structure: list, min_beats=1, max_beats=8):
    """
    Pick a beat-aligned window biased toward high-intensity sections.
    Higher-intensity sections (chorus, drop) are proportionally more likely to be chosen.
    Falls back to uniform random if structure is empty.
    """
    if not beat_times_ms or len(beat_times_ms) < 2:
        return None, None

    if not structure:
        return beat_aligned_window(beat_times_ms, min_beats, max_beats)

    # Build per-section weights proportional to intensity
    weighted_sections = []
    for sec in structure:
        intensity = section_intensity(sec["section"])
        sec_beats = beats_for_section(beat_times_ms, sec)
        if len(sec_beats) >= 2:
            weighted_sections.append((sec, intensity, sec_beats))

    if not weighted_sections:
        return beat_aligned_window(beat_times_ms, min_beats, max_beats)

    weights = [w[1] for w in weighted_sections]
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0.0
    chosen_beats = weighted_sections[-1][2]
    for sec, weight, sec_beats in weighted_sections:
        cumulative += weight
        if r <= cumulative:
            chosen_beats = sec_beats
            break

    if len(chosen_beats) < 2:
        return beat_aligned_window(beat_times_ms, min_beats, max_beats)

    return beat_aligned_window(chosen_beats, min_beats, min(max_beats, len(chosen_beats) - 1))


def section_effect_placements(base_count: int, structure: list, beat_times_ms: list, min_beats: int, max_beats: int) -> list:
    """
    Return a list of (start_ms, end_ms) tuples distributed across sections,
    with count per section scaled by intensity.
    Chorus (1.0) gets base_count effects; intro/outro (0.3) get ~30% of that.
    """
    if not structure or not beat_times_ms:
        return [(None, None)] * base_count

    placements = []
    for sec in structure:
        intensity = section_intensity(sec["section"])
        n = max(1, round(base_count * intensity))
        sec_beats = beats_for_section(beat_times_ms, sec)
        for _ in range(n):
            if len(sec_beats) >= 2:
                start, end = beat_aligned_window(sec_beats, min_beats, min(max_beats, len(sec_beats) - 1))
            else:
                start, end = None, None
            placements.append((start, end))
    return placements


def chorus_only_placements(base_count: int, structure: list, beat_times_ms: list, min_beats: int, max_beats: int) -> list:
    """
    Like section_effect_placements but restricts to high-intensity sections only (chorus/drop).
    Falls back to section_effect_placements if no qualifying sections exist.
    """
    if not structure or not beat_times_ms:
        return [(None, None)] * base_count

    high_sections = [s for s in structure if section_intensity(s["section"]) >= _CHORUS_INTENSITY_THRESHOLD]
    if not high_sections:
        return section_effect_placements(base_count, structure, beat_times_ms, min_beats, max_beats)

    placements = []
    for sec in high_sections:
        n = max(1, round(base_count * section_intensity(sec["section"])))
        sec_beats = beats_for_section(beat_times_ms, sec)
        for _ in range(n):
            if len(sec_beats) >= 2:
                start, end = beat_aligned_window(sec_beats, min_beats, min(max_beats, len(sec_beats) - 1))
            else:
                start, end = None, None
            placements.append((start, end))
    return placements


def filter_beats_vocals_only(beat_times_ms: list, lyrics_lines: list, gap_threshold_s: float = 8.0) -> list:
    """
    Return only beats that fall within gap_threshold_s of a lyric timestamp.
    Suppresses rapid-fire effects during long instrumental gaps.
    Returns the original list if lyrics_lines is empty.
    """
    if not lyrics_lines:
        return beat_times_ms
    import bisect
    lyric_ms = sorted(t for t, _ in lyrics_lines)
    threshold_ms = int(gap_threshold_s * 1000)
    result = []
    for b in beat_times_ms:
        idx = bisect.bisect_left(lyric_ms, b)
        close = False
        for i in (idx - 1, idx):
            if 0 <= i < len(lyric_ms) and abs(b - lyric_ms[i]) <= threshold_ms:
                close = True
                break
        if close:
            result.append(b)
    return result


def alternating_beat_placements(beat_times_ms: list, stride: int = 2, duration_beats: int = 1,
                                structure: list = None) -> list:
    """
    Return (start_ms, end_ms) pairs placing an effect every `stride` beats.
    duration_beats controls how many beats each effect spans.
    When structure is provided, skips beats in low-intensity sections (intensity < 0.4).
    """
    if not beat_times_ms or len(beat_times_ms) < 2:
        return []

    # Build set of low-intensity beat indices to skip
    skip_indices = set()
    if structure:
        low_sections = [s for s in structure if section_intensity(s["section"]) < 0.4]
        for s in low_sections:
            s_ms = int(s["start"] * 1000)
            e_ms = int(s["end"] * 1000)
            for i, b in enumerate(beat_times_ms):
                if s_ms <= b < e_ms:
                    skip_indices.add(i)

    placements = []
    i = 0
    while i < len(beat_times_ms) - 1:
        if i not in skip_indices:
            start_ms = beat_times_ms[i]
            end_idx = min(i + duration_beats, len(beat_times_ms) - 1)
            end_ms = beat_times_ms[end_idx]
            placements.append((start_ms, end_ms))
        i += stride
    return placements


# ---------------------------------------------------------------------------
# Overlap prevention + multi-layer helpers
# ---------------------------------------------------------------------------

def get_occupied_slots(effect_layer) -> list:
    """Return list of (start_ms, end_ms) for all effects in a layer."""
    slots = []
    for effect in effect_layer.findall("Effect"):
        try:
            slots.append((int(effect.get("startTime", 0)), int(effect.get("endTime", 0))))
        except ValueError:
            pass
    return slots


def is_overlapping(start_ms: int, end_ms: int, occupied: list) -> bool:
    """Return True if [start_ms, end_ms) overlaps any interval in occupied."""
    for s, e in occupied:
        if start_ms < e and end_ms > s:
            return True
    return False


def get_or_create_layer(elem, start_ms: int, end_ms: int, max_layers: int = 2):
    """
    Return an EffectLayer on elem that has no conflict with [start_ms, end_ms).
    Tries existing layers first; creates a new one (up to max_layers) if all conflict.
    Returns None if no layer is available or if the model has hit its effect budget.
    """
    model_name = elem.attrib.get("name", "")
    if _active_budget and _active_budget.is_full(model_name):
        return None
    for layer in elem.findall("EffectLayer"):
        if not is_overlapping(start_ms, end_ms, get_occupied_slots(layer)):
            if _active_budget:
                _active_budget.charge(model_name)
            return layer
    if len(elem.findall("EffectLayer")) < max_layers:
        if _active_budget:
            _active_budget.charge(model_name)
        return ET.SubElement(elem, "EffectLayer")
    return None
