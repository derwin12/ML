# shape_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

SHAPE_OBJECTS = ["Circle", "Square", "Triangle", "Star", "Pentagon", "Hexagon", "Heart", "Tree"]

def add_shape_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_shape_added = 0
    placements = section_effect_placements(12, structure or [], beats or [], min_beats=4, max_beats=14)
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

        p = sample_params("Shape")
        obj_type        = p.get("E_CHOICE_Shape_ObjectToDraw", random.choice(SHAPE_OBJECTS))
        count           = p.get("E_SLIDER_Shape_Count", random.randint(1, 20))
        lifetime        = p.get("E_SLIDER_Shape_Lifetime", random.randint(1, 100))
        velocity        = p.get("E_SLIDER_Shape_Velocity", random.randint(0, 50))
        size            = p.get("E_SLIDER_Shape_Size", random.randint(1, 50))
        random_movement = p.get("E_CHECKBOX_Shape_RandomMovement", random.choice([0, 1]))
        grow            = p.get("E_CHECKBOX_Shape_Grow", random.choice([0, 1]))
        fade            = p.get("E_CHECKBOX_Shape_Fade", random.choice([0, 1]))
        outline         = p.get("E_CHECKBOX_Shape_Outline", random.choice([0, 1]))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_CHOICE_Shape_ObjectToDraw={obj_type},"
                        f"E_SLIDER_Shape_Count={count},"
                        f"E_SLIDER_Shape_Lifetime={lifetime},"
                        f"E_SLIDER_Shape_Velocity={velocity},"
                        f"E_SLIDER_Shape_Size={size},"
                        f"E_CHECKBOX_Shape_RandomMovement={random_movement},"
                        f"E_CHECKBOX_Shape_Grow={grow},"
                        f"E_CHECKBOX_Shape_Fade={fade},"
                        f"E_CHECKBOX_Shape_Outline={outline},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Shape", start_time, end_time, palette_id, settings_str, registry)
        num_shape_added += 1
    return num_shape_added
