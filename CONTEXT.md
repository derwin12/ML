# Session Context — 2026-05-14

## Current Task
Section labeling pipeline is complete. training_data.json rebuilt with 90.8% section coverage (up from 0%). Ready to generate a test sequence and review quality.

## Key Decisions
- `detect_structure_audio()` uses chroma+MFCC+pychorus for boundary detection and chorus labeling
- `scan_sequences.py` now has `--folder` arg; "Scan Labeled Sequences" PyCharm config points at LabeledShowFolder
- Workflow order: add_timing_tracks → Scan Labeled Sequences → analyze_choreography → generate + review
- Always use "Scan Labeled Sequences" config (not default) to preserve section labels

## What Was Completed This Session
- [x] Audio-based structure detection (replaced LLM) with pychorus chorus labeling
- [x] add_timing_tracks.py web UI card + PyCharm configs
- [x] scan_sequences.py --folder arg + Scan Labeled/Original PyCharm configs
- [x] 90.8% section coverage in training_data.json (was 0%)
- [x] choreography_probs.json rebuilt on labeled data

## Next Steps
1. Generate a test sequence and review it in xLights — does chorus feel more intense than verse?
2. Build quality rating workflow (rate sequences 1–5, feed back into training weights)
3. Use co-occurrence data to coordinate effects across prop categories
