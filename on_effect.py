# on_effect.py

import random
from utils import section_effect_placements, alternating_beat_placements, get_or_create_layer, place_effect, section_colors, get_or_create_palette
from param_sampler import sample_params, sample_beat_stride


def _place_on(effect_layer, start_time, end_time, color_palettes, fixed_colors, registry=None, structure=None):
    selected_indices = [1]
    _sc = section_colors(fixed_colors, structure, start_time)
    parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
    for k in selected_indices:
        parts.append(f"C_CHECKBOX_Palette{k}=1")
    palette_id = get_or_create_palette(color_palettes, ",".join(parts))

    p = sample_params("On")
    shimmer = p.get("CHECKBOX_Shimmer", 0)
    settings_str = f"E1=100,E2=100,T1=0,CHECKBOX_Shimmer={shimmer}"
    place_effect(effect_layer, "On", start_time, end_time, palette_id, settings_str, registry)


def add_on_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_ons_added = 0

    # --- Alternating beat pass: 1-2 elements get On effects on every Nth beat ---
    if beats and len(beats) >= 4:
        stride = sample_beat_stride("On")
        num_alt = random.randint(1, min(2, len(eligible_elements)))
        alt_elements = random.sample(eligible_elements, num_alt)
        alt_placements = alternating_beat_placements(beats, stride=stride, duration_beats=1, structure=structure)
        for elem in alt_elements:
            for start_time, end_time in alt_placements:
                effect_layer = get_or_create_layer(elem, start_time, end_time)
                if effect_layer is None:
                    continue
                _place_on(effect_layer, start_time, end_time, color_palettes, fixed_colors, registry, structure)
                num_ons_added += 1

    # --- Sparse pass: section-weighted placement on other elements ---
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=1, max_beats=3)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 2000)
            end_time = start_time + random.randint(1000, 3000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue
        _place_on(effect_layer, start_time, end_time, color_palettes, fixed_colors, registry)
        num_ons_added += 1

    return num_ons_added
