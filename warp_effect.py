# warp_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

WARP_TYPES = ["water", "ripple", "dissolve", "circle", "drop"]

def add_warp_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_warp_added = 0
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=4, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 8000)
            end_time = start_time + random.randint(4000, 10000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Warp")
        warp_type   = p.get("E_CHOICE_Warp_Type", random.choice(WARP_TYPES))
        x           = p.get("E_SLIDER_Warp_X", random.randint(0, 100))
        y           = p.get("E_SLIDER_Warp_Y", random.randint(0, 100))
        speed       = p.get("E_SLIDER_Warp_Speed", random.randint(1, 50))
        frequency   = p.get("E_SLIDER_Warp_Frequency", random.randint(1, 20))
        cycle_count = p.get("E_CHECKBOX_Warp_Cycle_Count", random.choice([0, 1]))
        direction   = p.get("E_CHOICE_Warp_Direction", random.choice(["inward", "outward"]))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_CHOICE_Warp_Type={warp_type},"
                        f"E_SLIDER_Warp_X={x},"
                        f"E_SLIDER_Warp_Y={y},"
                        f"E_SLIDER_Warp_Speed={speed},"
                        f"E_SLIDER_Warp_Frequency={frequency},"
                        f"E_CHECKBOX_Warp_Cycle_Count={cycle_count},"
                        f"E_CHOICE_Warp_Direction={direction},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Warp", start_time, end_time, palette_id, settings_str, registry)
        num_warp_added += 1
    return num_warp_added
