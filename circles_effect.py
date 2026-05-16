# circles_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_circles_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_circles_added = 0
    placements = section_effect_placements(6, structure or [], beats or [], min_beats=4, max_beats=16)
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

        p = sample_params("Circles")
        num_circles  = p.get("E_SLIDER_Circles_Count", random.randint(1, 20))
        speed        = p.get("E_SLIDER_Circles_Speed", random.randint(1, 50))
        size         = p.get("E_SLIDER_Circles_Size", random.randint(1, 50))
        radius       = p.get("E_SLIDER_Circles_Radius", random.randint(1, 100))
        bounce       = p.get("E_CHECKBOX_Circles_Bounce", random.choice([0, 1]))
        filled       = p.get("E_CHECKBOX_Circles_Filled", random.choice([0, 1]))
        random_loc   = p.get("E_CHECKBOX_Circles_Random_m", random.choice([0, 1]))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_SLIDER_Circles_Count={num_circles},"
                        f"E_SLIDER_Circles_Speed={speed},"
                        f"E_SLIDER_Circles_Size={size},"
                        f"E_SLIDER_Circles_Radius={radius},"
                        f"E_CHECKBOX_Circles_Bounce={bounce},"
                        f"E_CHECKBOX_Circles_Filled={filled},"
                        f"E_CHECKBOX_Circles_Random_m={random_loc},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Circles", start_time, end_time, palette_id, settings_str, registry)
        num_circles_added += 1
    return num_circles_added
