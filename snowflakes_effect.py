# snowflakes_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_snowflakes_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_snowflakes_added = 0
    placements = section_effect_placements(8, structure or [], beats or [], min_beats=5, max_beats=20)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(5000, 12000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Snowflakes")
        max_flakes   = p.get("E_SLIDER_Snowflakes_Count", random.randint(1, 30))
        speed        = p.get("E_SLIDER_Snowflakes_Speed", random.randint(1, 50))
        flake_type   = p.get("E_SLIDER_Snowflakes_Type", random.randint(0, 5))
        direction    = p.get("E_CHOICE_Snowflakes_Direction", random.choice(["Down", "Up", "Left", "Right", "Unused"]))
        accumulate   = p.get("E_CHECKBOX_Snowflakes_Accumulate", random.choice([0, 1]))
        falling      = p.get("E_CHECKBOX_Snowflakes_Falling", random.choice([0, 1]))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_SLIDER_Snowflakes_Count={max_flakes},"
                        f"E_SLIDER_Snowflakes_Speed={speed},"
                        f"E_SLIDER_Snowflakes_Type={flake_type},"
                        f"E_CHOICE_Snowflakes_Direction={direction},"
                        f"E_CHECKBOX_Snowflakes_Accumulate={accumulate},"
                        f"E_CHECKBOX_Snowflakes_Falling={falling},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Snowflakes", start_time, end_time, palette_id, settings_str, registry)
        num_snowflakes_added += 1
    return num_snowflakes_added
