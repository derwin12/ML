"""compare_sequences.py

Compare a generated .xsq against a professional .xsq for the same song.
Reports per-(section, category) effect distribution differences so the
training data / choreography_probs.json can be tuned to close the gap.

Usage:
    python compare_sequences.py <pro.xsq> <generated.xsq> [--layout xlights_rgbeffects.xml]

Output:
    • Effect distribution table per (section, category)
    • Top divergences (where pro and generated disagree most)
    • Section density comparison (effects per minute)
    • Optional: --suggest  prints weight adjustments for choreography_probs.json
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from scan_sequences import (
    extract_effect_db,
    extract_structure,
    extract_beats,
    load_model_categories,
    parse_settings,
    section_for_time,
)

_LAYOUT_DEFAULT = os.path.join(
    os.path.dirname(__file__), "training data", "folder 1", "xlights_rgbeffects.xml"
)

# Categories that carry no useful signal
_SKIP_CATS = {"skip", "unknown", "group", "everything_group", "generic_group"}

# Effects to ignore in both sequences (e.g. debug overlays)
_SKIP_EFFECTS = {"Text"}


# ---------------------------------------------------------------------------
# Per-file scan
# ---------------------------------------------------------------------------

def scan_xsq(path: str, model_categories: dict) -> dict:
    """
    Scan a single .xsq and return observations bucketed by (section, category).

    Returns:
        {
          (section, category): Counter({effect_name: count}),
          ...
        }
    Also populates:
        _meta["duration_ms"]      — total sequence duration (ms)
        _meta["section_density"]  — {section: effect_count} (layer-0 only)
    """
    root = ET.parse(path).getroot()
    effect_db = extract_effect_db(root)
    sections  = extract_structure(root)

    # Try to determine total duration from head/sequenceDuration
    duration_ms = 0
    head = root.find(".//head") or root.find(".//Head")
    if head is not None:
        dur_elem = head.find("sequenceDuration")
        if dur_elem is not None and dur_elem.text:
            try:
                duration_ms = int(float(dur_elem.text) * 1000)
            except ValueError:
                pass

    buckets: dict = defaultdict(Counter)            # (section, cat) -> Counter(effect)
    section_density: dict = defaultdict(int)        # section -> effect count (layer 0)

    model_elems = root.findall(".//Element[@type='Model']")
    if not model_elems:
        model_elems = [e for e in root.findall(".//Element")
                       if e.get("type") not in ("timing",)]

    for elem in model_elems:
        if elem.get("type") == "timing":
            continue

        model_name = elem.get("name", "").strip()
        category   = model_categories.get(model_name.lower(), "unknown")
        if category in _SKIP_CATS:
            continue

        for layer_idx, layer in enumerate(elem.findall("EffectLayer")):
            for effect in layer.findall("Effect"):
                effect_name = effect.get("name", "").strip()
                if not effect_name or effect_name.lower() in ("", "timing"):
                    continue
                if effect_name in _SKIP_EFFECTS:
                    continue
                try:
                    start_ms = int(effect.get("startTime", 0))
                    end_ms   = int(effect.get("endTime",   0))
                except ValueError:
                    continue
                if end_ms - start_ms <= 0:
                    continue

                section = section_for_time(start_ms, sections)
                key     = (section, category)
                buckets[key][effect_name] += 1

                if layer_idx == 0:
                    section_density[section] += 1

    return {
        "buckets":         dict(buckets),
        "section_density": dict(section_density),
        "duration_ms":     duration_ms,
        "sections":        sections,
    }


# ---------------------------------------------------------------------------
# Comparison + reporting
# ---------------------------------------------------------------------------

def _top_n(counter: Counter, n: int = 5) -> list:
    return counter.most_common(n)


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "  0%"
    return f"{100 * count / total:4.0f}%"


def compare(pro: dict, gen: dict, top_n: int = 5) -> list:
    """
    Return a list of divergence records sorted by Jensen-Shannon-like distance.
    Each record: {section, category, pro_top, gen_top, divergence_score}
    """
    all_keys = set(pro["buckets"]) | set(gen["buckets"])
    records  = []

    for key in sorted(all_keys):
        section, category = key
        pro_ctr = pro["buckets"].get(key, Counter())
        gen_ctr = gen["buckets"].get(key, Counter())

        all_effects = set(pro_ctr) | set(gen_ctr)
        pro_total   = sum(pro_ctr.values()) or 1
        gen_total   = sum(gen_ctr.values()) or 1

        # L1 distance on normalised distributions
        score = sum(
            abs(pro_ctr.get(e, 0) / pro_total - gen_ctr.get(e, 0) / gen_total)
            for e in all_effects
        ) / 2  # 0 = identical, 1 = completely different

        records.append({
            "section":    section,
            "category":   category,
            "pro_top":    _top_n(pro_ctr, top_n),
            "gen_top":    _top_n(gen_ctr, top_n),
            "pro_total":  sum(pro_ctr.values()),
            "gen_total":  sum(gen_ctr.values()),
            "divergence": round(score, 3),
        })

    records.sort(key=lambda r: -r["divergence"])
    return records


def print_report(pro_path: str, gen_path: str, records: list,
                 pro_meta: dict, gen_meta: dict, top_n: int = 5):
    print("=" * 72)
    print("SEQUENCE COMPARISON REPORT")
    print(f"  PRO : {os.path.basename(pro_path)}")
    print(f"  GEN : {os.path.basename(gen_path)}")
    print("=" * 72)

    # Section density table
    all_sections = sorted(
        set(pro_meta["section_density"]) | set(gen_meta["section_density"])
    )
    if all_sections:
        print("\nSECTION DENSITY  (primary-layer effects per section)")
        print(f"  {'Section':<20} {'Pro':>6}  {'Gen':>6}  {'Ratio':>6}")
        print(f"  {'-'*20} {'---':>6}  {'---':>6}  {'-----':>6}")
        for sec in all_sections:
            p = pro_meta["section_density"].get(sec, 0)
            g = gen_meta["section_density"].get(sec, 0)
            ratio = f"{g/p:.2f}x" if p else "  —"
            print(f"  {sec:<20} {p:>6}  {g:>6}  {ratio:>6}")

    # Per-bucket diff (sorted by divergence, show top 20)
    print(f"\nEFFECT DISTRIBUTION  (top {top_n} effects per bucket, sorted by divergence)")
    shown = 0
    for r in records:
        if shown >= 20:
            break
        if r["divergence"] < 0.05:
            break  # ignore near-identical buckets
        print(f"\n  [{r['section'].upper()}] {r['category']}  "
              f"(divergence={r['divergence']:.2f}, "
              f"pro={r['pro_total']} effects, gen={r['gen_total']} effects)")

        # Align pro and gen side-by-side
        max_rows = max(len(r["pro_top"]), len(r["gen_top"]))
        print(f"    {'PRO':<30} {'GEN':<30}")
        print(f"    {'-'*30} {'-'*30}")
        for i in range(max_rows):
            p_name, p_cnt = r["pro_top"][i] if i < len(r["pro_top"]) else ("", 0)
            g_name, g_cnt = r["gen_top"][i] if i < len(r["gen_top"]) else ("", 0)
            p_str = f"{p_name:<22} {_pct(p_cnt, r['pro_total'])}" if p_name else ""
            g_str = f"{g_name:<22} {_pct(g_cnt, r['gen_total'])}" if g_name else ""
            print(f"    {p_str:<30} {g_str:<30}")
        shown += 1

    if shown == 0:
        print("\n  No significant divergences found (all buckets < 5% apart).")

    print("\n" + "=" * 72)


def suggest_weights(records: list, current_probs_path: str | None = None):
    """Print suggested weight adjustments for choreography_probs.json."""
    if current_probs_path and os.path.isfile(current_probs_path):
        with open(current_probs_path, encoding="utf-8") as f:
            probs = json.load(f)
    else:
        probs = {}

    print("\nSUGGESTED choreography_probs.json ADJUSTMENTS")
    print("  (increase weights toward pro distribution; changes > 5pp shown)")
    print(f"  {'Section':<18} {'Category':<18} {'Effect':<22} {'Change':>10}")
    print(f"  {'-'*18} {'-'*18} {'-'*22} {'-'*10}")

    for r in records:
        if r["divergence"] < 0.10:
            continue
        sec, cat = r["section"], r["category"]
        pro_total = r["pro_total"] or 1
        gen_total = r["gen_total"] or 1

        pro_dict = dict(r["pro_top"])
        gen_dict = dict(r["gen_top"])
        all_effects = set(pro_dict) | set(gen_dict)

        for eff in sorted(all_effects):
            pro_pct = pro_dict.get(eff, 0) / pro_total
            gen_pct = gen_dict.get(eff, 0) / gen_total
            delta   = pro_pct - gen_pct
            if abs(delta) < 0.05:
                continue
            direction = f"+{delta*100:.0f}pp" if delta > 0 else f"{delta*100:.0f}pp"
            print(f"  {sec:<18} {cat:<18} {eff:<22} {direction:>10}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compare a generated .xsq against a professional .xsq."
    )
    parser.add_argument("pro",       metavar="PRO.xsq",
                        help="Path to the professionally-made sequence")
    parser.add_argument("generated", metavar="GEN.xsq",
                        help="Path to the AI-generated sequence")
    parser.add_argument("--layout",  metavar="PATH", default=_LAYOUT_DEFAULT,
                        help="Path to xlights_rgbeffects.xml")
    parser.add_argument("--top",     metavar="N", type=int, default=5,
                        help="Top-N effects to show per bucket (default: 5)")
    parser.add_argument("--suggest", action="store_true",
                        help="Print suggested weight adjustments for choreography_probs.json")
    parser.add_argument("--probs",   metavar="PATH",
                        default=os.path.join(os.path.dirname(__file__), "choreography_probs.json"),
                        help="Path to choreography_probs.json (used with --suggest)")
    args = parser.parse_args()

    for p in (args.pro, args.generated):
        if not os.path.isfile(p):
            parser.error(f"File not found: {p}")

    print(f"Loading model categories from {args.layout} ...")
    model_categories = load_model_categories(args.layout)

    print(f"Scanning {os.path.basename(args.pro)} ...")
    pro_data = scan_xsq(args.pro, model_categories)

    print(f"Scanning {os.path.basename(args.generated)} ...")
    gen_data = scan_xsq(args.generated, model_categories)

    records = compare(pro_data, gen_data, top_n=args.top)
    print_report(args.pro, args.generated, records, pro_data, gen_data, top_n=args.top)

    if args.suggest:
        suggest_weights(records, args.probs)


if __name__ == "__main__":
    main()
