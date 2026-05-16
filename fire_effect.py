# fire_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_fire_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    placements = section_effect_placements(6, structure or [], beats or [], min_beats=4, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 5000)
            end_time = start_time + random.randint(3000, 10000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Fire")
        height    = p.get("E_SLIDER_Fire_Height", random.randint(10, 100))
        hue_shift = p.get("E_SLIDER_Fire_HueShift", random.randint(0, 360))
        palette   = p.get("E_CHOICE_Fire_Palette", random.choice(["Normal", "Blue", "Green", "Purple", "White"]))
        grow_with_music = p.get("E_CHECKBOX_Fire_GrowWithMusic", random.choice([0, 1]))

        # Fire uses its own internal palette, but we still register one for consistency
        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")

        palette_id = get_or_create_palette(color_palettes, ",".join(parts))

        settings_str = (
            f"E_SLIDER_Fire_Height={height},"
            f"E_SLIDER_Fire_HueShift={hue_shift},"
            f"E_CHOICE_Fire_Palette={palette},"
            f"E_CHECKBOX_Fire_GrowWithMusic={grow_with_music},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "Fire", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
