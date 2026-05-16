# arch_effect.py
#
# Beat-synchronized SingleStrand effects for arch groups.
# Modelled on pro choreography analysis:
#   - SingleStrand only (no rotation of effect types)
#   - Direction alternates in pairs: L,L,R,R,L,L,R,R...
#   - Arches are SILENT in inactive sections (intro, bridge, outro, breakdown)
#     and only fire during active sections (verse, chorus, drop, pre-chorus)
#   - All effects land on a single layer, seamless back-to-back

from utils import get_or_create_layer, place_effect, section_colors, get_or_create_palette

# Sections where arches play; all others are silent
_ACTIVE_SECTIONS = {"verse", "chorus", "drop", "pre-chorus", "pre_chorus"}

# Direction pair cycle: L,L,R,R,L,L,R,R...
_DIRECTION_PAIRS = ["Left", "Left", "Right", "Right"]


def _palette_str(color1, color2):
    parts = [f"C_BUTTON_Palette{i+1}=#000000" for i in range(8)]
    parts[0] = f"C_BUTTON_Palette1={color1}"
    parts[1] = f"C_BUTTON_Palette2={color2}"
    parts.append("C_CHECKBOX_Palette1=1")
    parts.append("C_CHECKBOX_Palette2=1")
    return ",".join(parts)


def _place_single_strand(effect_layer, start_ms, end_ms, direction, palette_id, registry):
    settings = (
        f"E_CHOICE_SingleStrand_Direction={direction},"
        f"E_SLIDER_SingleStrand_Lights=25,"
        f"E_SLIDER_SingleStrand_Number=1,"
        f"E_SLIDER_SingleStrand_Speed=10,"
        f"E_SLIDER_SingleStrand_Width=1,"
        f"E1=100,E2=100"
    )
    place_effect(effect_layer, "SingleStrand", start_ms, end_ms, palette_id, settings, registry)


def _section_name(structure, time_ms):
    if not structure:
        return "verse"  # no structure = treat as active
    t_s = time_ms / 1000.0
    for sec in structure:
        if sec["start"] <= t_s < sec["end"]:
            return sec["section"].lower()
    return "unknown"


def _is_active_section(structure, time_ms):
    """Return True if the beat at time_ms falls in an active section for arches."""
    name = _section_name(structure, time_ms)
    return any(active in name for active in _ACTIVE_SECTIONS)


def add_arch_effects(arch_group_elements, seq_duration_ms, color_palettes,
                     fixed_colors, beats, structure=None, registry=None):
    """
    Place beat-synchronized SingleStrand effects on arch group elements only.

    arch_group_elements: list of ElementEffects <Element> nodes whose
                         model_category is 'arch' AND are groups.
    beats: list of beat timestamps in ms.
    """
    if not arch_group_elements or not beats:
        return 0

    num_added = 0
    pair_len = len(_DIRECTION_PAIRS)

    for elem in arch_group_elements:
        pair_idx = 0  # counts only placed effects, driving the L,L,R,R cycle

        for i, beat_ms in enumerate(beats):
            end_ms = beats[i + 1] if i + 1 < len(beats) else seq_duration_ms

            if not _is_active_section(structure, beat_ms):
                continue  # arch is silent in this section

            layer = get_or_create_layer(elem, beat_ms, end_ms,
                                        max_layers=2, skip_budget=True)
            if layer is None:
                continue

            sc = section_colors(fixed_colors, structure, beat_ms)
            c1 = sc[0]
            c2 = sc[1] if len(sc) > 1 else sc[0]
            palette_id = get_or_create_palette(color_palettes, _palette_str(c1, c2))

            direction = _DIRECTION_PAIRS[pair_idx % pair_len]
            pair_idx += 1

            _place_single_strand(layer, beat_ms, end_ms,
                                  direction, palette_id, registry)
            num_added += 1

    return num_added
