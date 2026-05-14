# curtain_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

CURTAIN_EDGES = ["left", "right", "center", "top", "bottom"]
CURTAIN_EFFECTS = ["open", "close", "open then close", "close then open"]

def add_curtain_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_curtain_added = 0
    placements = section_effect_placements(8, structure or [], beats or [], min_beats=4, max_beats=14)
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

        p = sample_params("Curtain")
        edge     = p.get("E_CHOICE_Curtain_Edge", random.choice(CURTAIN_EDGES))
        effect_t = p.get("E_CHOICE_Curtain_Effect", random.choice(CURTAIN_EFFECTS))
        speed    = p.get("E_SLIDER_Curtain_Speed", random.randint(1, 50))
        swag     = p.get("E_SLIDER_Curtain_Swag", random.randint(0, 20))
        repeat   = p.get("E_CHECKBOX_Curtain_Repeat", random.choice([0, 1]))

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

        settings_str = (f"E_CHOICE_Curtain_Edge={edge},"
                        f"E_CHOICE_Curtain_Effect={effect_t},"
                        f"E_SLIDER_Curtain_Speed={speed},"
                        f"E_SLIDER_Curtain_Swag={swag},"
                        f"E_CHECKBOX_Curtain_Repeat={repeat},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Curtain", start_time, end_time, palette_id, settings_str, registry)
        num_curtain_added += 1
    return num_curtain_added
