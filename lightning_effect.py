# lightning_effect.py

import xml.etree.ElementTree as ET
import random
from utils import chorus_only_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_lightning_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_lightning_added = 0
    placements = chorus_only_placements(6, structure or [], beats or [], min_beats=3, max_beats=10)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 6000)
            end_time = start_time + random.randint(3000, 8000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Lightning")
        num_bolts    = p.get("E_SLIDER_Lightning_Number", random.randint(1, 10))
        bold         = p.get("E_SLIDER_Lightning_Bold", random.randint(1, 10))
        top_x        = p.get("E_SLIDER_Lightning_TopX", random.randint(0, 100))
        top_y        = p.get("E_SLIDER_Lightning_TopY", random.randint(0, 100))
        bot_x        = p.get("E_SLIDER_Lightning_BotX", random.randint(0, 100))
        bot_y        = p.get("E_SLIDER_Lightning_BotY", random.randint(0, 100))
        forked       = p.get("E_CHECKBOX_Lightning_Forked", random.choice([0, 1]))
        drift        = p.get("E_SLIDER_Lightning_Drift", random.randint(1, 50))

        num_colors = random.randint(2, 3)
        selected_indices = random.sample(range(1, 9), num_colors)
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"E_SLIDER_Lightning_Number={num_bolts},"
                        f"E_SLIDER_Lightning_Bold={bold},"
                        f"E_SLIDER_Lightning_TopX={top_x},"
                        f"E_SLIDER_Lightning_TopY={top_y},"
                        f"E_SLIDER_Lightning_BotX={bot_x},"
                        f"E_SLIDER_Lightning_BotY={bot_y},"
                        f"E_CHECKBOX_Lightning_Forked={forked},"
                        f"E_SLIDER_Lightning_Drift={drift},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Lightning", start_time, end_time, palette_id, settings_str, registry)
        num_lightning_added += 1
    return num_lightning_added
