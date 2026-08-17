Read new.json and rubric.md in the current directory.
Score each posting 0–10 against rubric.md following the two-stage procedure
(disqualifier gate, then axis scoring). Add display_score, weighted_score,
disqualified, disqualifier_reason, confidence, axes, and why_relevant to each
posting. Preserve all original fields from new.json unchanged.
Write the complete scored array to scored.json in the same directory.
Do not edit rubric.md. Do not browse the web.
If any posting is unclear, score conservatively and set confidence="low".
