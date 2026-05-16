"""apply_suggestions.py

Compare a generated .xsq against a professional .xsq and blend the observed
distribution differences into choreography_probs.json, moving the generator
toward the pro distribution incrementally.

Usage:
    python apply_suggestions.py <pro.xsq> <generated.xsq> [options]

Options:
    --layout PATH         xlights_rgbeffects.xml (default: training data folder 1)
    --probs  PATH         choreography_probs.json to patch (default: ./choreography_probs.json)
    --learning-rate N     Blend rate toward pro distribution, 0–1 (default: 0.4)
    --min-effects N       Minimum pro effect count in a bucket to apply adjustments (default: 8)
    --dry-run             Print adjustments without writing the file

Learning formula (per effect per bucket):
    new_weight = old_weight + lr * (pro_pct - old_weight)
    → 0.4 lr moves 40% of the way toward pro in one pass
    → Capped at [0.005, 1.0] before renormalization
"""

import argparse
import json
import os
from collections import Counter, defaultdict

from compare_sequences import scan_xsq
from scan_sequences import load_model_categories

_LAYOUT_DEFAULT = os.path.join(
    os.path.dirname(__file__), "training data", "folder 1", "xlights_rgbeffects.xml"
)
_PROBS_DEFAULT = os.path.join(os.path.dirname(__file__), "choreography_probs.json")

_SKIP_CATS = {"skip", "unknown", "group", "everything_group", "generic_group"}


def _normalize_section(label: str) -> str:
    l = label.lower().strip()
    if any(w in l for w in ("chorus", "drop", "hook", "refrain")):
        return "chorus"
    if "verse" in l:
        return "verse"
    if "intro" in l or "opening" in l:
        return "intro"
    if any(w in l for w in ("outro", "ending", "coda", "fade")):
        return "outro"
    if "bridge" in l or "interlude" in l:
        return "bridge"
    if "pre" in l:
        return "pre_chorus"
    return "global"


def _aggregate_by_norm_section(raw_buckets: dict) -> dict:
    """
    Collapse raw (section_label, category) buckets into (norm_section, category) Counters.
    """
    out: dict = defaultdict(Counter)
    for (sec_label, cat), ctr in raw_buckets.items():
        norm = _normalize_section(sec_label)
        out[(norm, cat)].update(ctr)
    return dict(out)


def apply_adjustments(
    probs: dict,
    pro_buckets: dict,
    gen_buckets: dict,
    learning_rate: float,
    min_effects: int,
    verbose: bool = True,
) -> tuple[dict, int]:
    """
    Blend choreography_probs.json toward the pro distribution.
    Returns (updated_probs, num_buckets_changed).
    """
    all_keys = set(pro_buckets) | set(gen_buckets)
    num_changed = 0

    for (norm_sec, cat) in sorted(all_keys):
        if cat in _SKIP_CATS:
            continue
        if cat not in probs:
            continue

        pro_ctr = pro_buckets.get((norm_sec, cat), Counter())
        gen_ctr = gen_buckets.get((norm_sec, cat), Counter())

        pro_total = sum(pro_ctr.values())
        gen_total = sum(gen_ctr.values())

        if pro_total < min_effects:
            continue  # too little pro data to trust

        all_effects = set(pro_ctr) | set(gen_ctr)
        pro_total_f = float(pro_total) or 1.0
        gen_total_f = float(gen_total) or 1.0

        l1 = sum(
            abs(pro_ctr.get(e, 0) / pro_total_f - gen_ctr.get(e, 0) / gen_total_f)
            for e in all_effects
        ) / 2
        if l1 < 0.10:
            continue  # distributions already close

        # Find or create section bucket in probs
        cat_data = probs[cat]
        if norm_sec in cat_data:
            bucket = cat_data[norm_sec]
        elif norm_sec == "global" and "global" in cat_data:
            bucket = cat_data["global"]
        elif "global" in cat_data:
            # Adjust global when we don't have a section-specific bucket yet
            bucket = cat_data["global"]
        else:
            continue

        current = dict(bucket.get("probs", {}))
        if not current:
            continue

        pro_dist = {e: pro_ctr[e] / pro_total_f for e in pro_ctr}
        gen_dist = {e: gen_ctr[e] / gen_total_f for e in gen_ctr}

        adjusted = dict(current)
        changed = False

        # Move weights toward pro
        for eff, pro_p in pro_dist.items():
            cur_p = adjusted.get(eff, 0.0)
            new_p = cur_p + learning_rate * (pro_p - cur_p)
            new_p = max(0.005, min(new_p, 1.0))
            if round(new_p, 4) != round(cur_p, 4):
                adjusted[eff] = new_p
                changed = True

        # Pull down over-generated effects that pro doesn't use
        for eff in list(adjusted):
            if eff in pro_dist:
                continue
            gen_p = gen_dist.get(eff, 0.0)
            if gen_p > 0.10:
                cur_p = adjusted[eff]
                new_p = cur_p * (1.0 - learning_rate * 0.5)
                new_p = max(0.005, new_p)
                if round(new_p, 4) != round(cur_p, 4):
                    adjusted[eff] = new_p
                    changed = True

        if changed:
            total = sum(adjusted.values())
            bucket["probs"] = {k: round(v / total, 4) for k, v in sorted(adjusted.items(), key=lambda x: -x[1])}
            num_changed += 1
            if verbose:
                top_pro = sorted(pro_dist.items(), key=lambda x: -x[1])[:3]
                top_pro_str = "  ".join(f"{e}={p:.0%}" for e, p in top_pro)
                print(f"  [{norm_sec}] {cat:<16} L1={l1:.2f}  pro: {top_pro_str}")

    return probs, num_changed


def main():
    parser = argparse.ArgumentParser(
        description="Blend compare-output differences into choreography_probs.json"
    )
    parser.add_argument("pro",       metavar="PRO.xsq")
    parser.add_argument("generated", metavar="GEN.xsq")
    parser.add_argument("--layout",  default=_LAYOUT_DEFAULT)
    parser.add_argument("--probs",   default=_PROBS_DEFAULT)
    parser.add_argument("--learning-rate", dest="lr", type=float, default=0.4,
                        metavar="N")
    parser.add_argument("--min-effects",   dest="min_eff", type=int, default=8,
                        metavar="N")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for p in (args.pro, args.generated):
        if not os.path.isfile(p):
            parser.error(f"File not found: {p}")
    if not os.path.isfile(args.probs):
        parser.error(f"choreography_probs.json not found: {args.probs}")

    print(f"Loading model categories from {os.path.basename(args.layout)} ...")
    model_categories = load_model_categories(args.layout)

    print(f"Scanning {os.path.basename(args.pro)} ...")
    pro_data = scan_xsq(args.pro, model_categories)

    print(f"Scanning {os.path.basename(args.generated)} ...")
    gen_data = scan_xsq(args.generated, model_categories)

    pro_buckets = _aggregate_by_norm_section(pro_data["buckets"])
    gen_buckets = _aggregate_by_norm_section(gen_data["buckets"])

    print(f"\nLoading {os.path.basename(args.probs)} ...")
    with open(args.probs, encoding="utf-8") as f:
        probs = json.load(f)

    print(f"\nApplying adjustments (lr={args.lr}, min_effects={args.min_eff}):")
    probs, num_changed = apply_adjustments(
        probs, pro_buckets, gen_buckets, args.lr, args.min_eff
    )

    print(f"\n{num_changed} buckets adjusted.")

    if args.dry_run:
        print("[dry-run] Not writing changes.")
        return

    backup = args.probs + ".bak"
    with open(args.probs, encoding="utf-8") as f:
        original = f.read()
    with open(backup, "w", encoding="utf-8") as f:
        f.write(original)
    print(f"Backup: {backup}")

    with open(args.probs, "w", encoding="utf-8") as f:
        json.dump(probs, f, indent=2)
    print(f"Saved:  {args.probs}")


if __name__ == "__main__":
    main()
