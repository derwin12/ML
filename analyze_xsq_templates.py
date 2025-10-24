import os
import json
import xml.etree.ElementTree as ET
from collections import OrderedDict

def describe_xml_structure(element, depth=0):
    """Recursively describe XML structure with tag order and attributes."""
    structure = OrderedDict()
    for child in element:
        tag_name = child.tag
        if tag_name not in structure:
            structure[tag_name] = {
                "attributes": sorted(child.attrib.keys()),
                "children": describe_xml_structure(child, depth + 1)
            }
    return structure

def summarize_structure(xml_path):
    """Return a summarized dictionary of tag order and structure."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        return {
            "file": os.path.basename(xml_path),
            "root_tag": root.tag,
            "attributes": sorted(root.attrib.keys()),
            "structure": describe_xml_structure(root)
        }
    except ET.ParseError as e:
        return {
            "file": os.path.basename(xml_path),
            "error": f"XML parse error: {str(e)}"
        }

def analyze_xsq_templates(template_dir):
    """Scan directory for .xsq files and build a structure summary JSON."""
    summary = []
    for filename in os.listdir(template_dir):
        if filename.lower().endswith(".xsq"):
            full_path = os.path.join(template_dir, filename)
            print(f"Analyzing: {filename}")
            info = summarize_structure(full_path)
            summary.append(info)

    output_json = os.path.join(template_dir, "xlights_template_structures.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Analysis complete.")
    print(f"  Found {len(summary)} template files.")
    print(f"  JSON structure map saved to:\n  {output_json}")
    return output_json

# Example usage
if __name__ == "__main__":
    template_dir = r"C:\Users\daryl\PycharmProjects\ML\training data\templates"
    analyze_xsq_templates(template_dir)
