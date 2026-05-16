# kaleidoscope_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_kaleidoscope_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_kaleidoscope_added = 0
    placements = section_effect_placements(6, structure or [], beats or [], min_beats=6, max_beats=20)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(6000, 14000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Kaleidoscope")
        x_offset  = p.get("E_SLIDER_Kaleidoscope_X_Offset", random.randint(-100, 100))
        y_offset  = p.get("E_SLIDER_Kaleidoscope_Y_Offset", random.randint(-100, 100))
        rotation  = p.get("E_SLIDER_Kaleidoscope_Rotation", random.randint(0, 360))
        speed     = p.get("E_SLIDER_Kaleidoscope_Speed", random.randint(0, 50))
        depth     = p.get("E_SLIDER_Kaleidoscope_Depth", random.randint(1, 8))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_SLIDER_Kaleidoscope_X_Offset={x_offset},"
                        f"E_SLIDER_Kaleidoscope_Y_Offset={y_offset},"
                        f"E_SLIDER_Kaleidoscope_Rotation={rotation},"
                        f"E_SLIDER_Kaleidoscope_Speed={speed},"
                        f"E_SLIDER_Kaleidoscope_Depth={depth},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Kaleidoscope", start_time, end_time, palette_id, settings_str, registry)
        num_kaleidoscope_added += 1
    return num_kaleidoscope_added
