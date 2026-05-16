# strobe_effect.py

import random
from utils import chorus_only_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_strobe_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    # Strobe is high-energy — use a higher base count so choruses get plenty
    placements = chorus_only_placements(8, structure or [], beats or [], min_beats=1, max_beats=4)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 2000)
            end_time = start_time + random.randint(500, 3000)
        if random.random() < 0.5 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Strobe")
        duty_cycle = p.get("E_SLIDER_Strobe_Duty_Cycle", random.randint(10, 50))
        frequency  = p.get("E_SLIDER_Strobe_Freq", random.randint(1, 30))

        selected_indices = [1]
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")

        palette_id = get_or_create_palette(color_palettes, ",".join(parts))

        settings_str = (
            f"E_SLIDER_Strobe_Duty_Cycle={duty_cycle},"
            f"E_SLIDER_Strobe_Freq={frequency},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "Strobe", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
