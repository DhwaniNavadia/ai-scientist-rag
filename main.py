from pathlib import Path
import json


def load_json(path: str):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# --- Preference fix: decision-aware ranking ---
def decision_rank(decision: str) -> int:
    # Higher is better
    if decision == "KEEP":
        return 3
    if decision == "REVISE":
        return 2
    return 1  # REJECT

def pick_preferred(entry: dict) -> str:
    """
    Decide preferred agent output using:
    1) decision rank (KEEP > REVISE > REJECT)
    2) total score
    3) tie-break -> AgentA
    """
    outputs = entry.get("agent_outputs", [])
    if len(outputs) < 2:
        return entry.get("disagreement_summary", {}).get("preferred", "AgentA")

    a = outputs[0]["critic"]
    b = outputs[1]["critic"]

    ra = decision_rank(a.get("decision", "REJECT"))
    rb = decision_rank(b.get("decision", "REJECT"))

    if ra > rb:
        return "AgentA"
    if rb > ra:
        return "AgentB"

    ta = a.get("total", 0)
    tb = b.get("total", 0)

    if ta > tb:
        return "AgentA"
    if tb > ta:
        return "AgentB"

    return "AgentA"


def main():
    sections = load_json("outputs/sections.json")
    claims = load_json("outputs/claims.json")
    gaps_actionable = load_json("outputs/gaps_actionable.json")
    hypotheses_scored = load_json("outputs/hypotheses_scored.json")
    reflections = load_json("outputs/reflection_logs.json")
    disagreements = load_json("outputs/disagreement_log_all.json")

    missing = []
    if sections is None: missing.append("outputs/sections.json")
    if claims is None: missing.append("outputs/claims.json")
    if gaps_actionable is None: missing.append("outputs/gaps_actionable.json")
    if hypotheses_scored is None: missing.append("outputs/hypotheses_scored.json")
    if reflections is None: missing.append("outputs/reflection_logs.json")
    if disagreements is None: missing.append("outputs/disagreement_log_all.json")

    if missing:
        print("❌ Missing required files:")
        for m in missing:
            print(" -", m)
        return

    # --- Apply preference fix to all disagreement entries ---
    for entry in disagreements:
        new_pref = pick_preferred(entry)
        entry.setdefault("disagreement_summary", {})
        entry["disagreement_summary"]["preferred"] = new_pref
        entry["disagreement_summary"]["reason"] = "Decision-aware preference (KEEP > REVISE > REJECT), then total score."

    # Index reflections by hypothesis_id for easy join
    reflection_by_hid = {r["hypothesis_id"]: r for r in reflections}

    # Index gaps by gap_id
    gap_by_gid = {g["gap_id"]: g for g in gaps_actionable}

    # Build lineage items: each hypothesis becomes a lineage record
    lineage = []
    for h in hypotheses_scored:
        gid = h["gap_id"]
        gap = gap_by_gid.get(gid, {})

        lineage.append({
            "hypothesis_id": h["hypothesis_id"],
            "hypothesis_text": h["hypothesis_text"],
            "failure_mode": h["failure_mode"],
            "critic": h["critic"],
            "reflection": reflection_by_hid.get(h["hypothesis_id"], {}),
            "gap": {
                "gap_id": gid,
                "gap_type": h["gap_type"],
                "gap_statement": gap.get("gap_statement", ""),
                "evidence_text": h["evidence_text"],
                "section": gap.get("section", ""),
            },
        })

    report = {
        "project": {
            "name": "Autonomous AI Scientist (MVP)",
            "scope": "Single-paper pipeline + multi-agent hypothesis generation + critic + traceability",
        },
        "paper_context": {
            "available_sections": list(sections.keys()),
            "num_claims": len(claims),
            "num_gaps": len(gaps_actionable),
            "num_hypotheses": len(hypotheses_scored),
            "num_disagreement_entries": len(disagreements),
        },
        "claims": claims,
        "gaps_actionable": gaps_actionable,
        "hypothesis_lineage": lineage,
        "disagreement_log": disagreements,
    }

    out_path = Path("outputs/final_report.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("✅ Saved final report to outputs/final_report.json")
    print("Lineage items:", len(lineage))

    # Quick verification: show G31 preferred if exists
    g31 = next((d for d in disagreements if d.get("gap_id") == "G31"), None)
    if g31:
        print("✅ G31 preferred:", g31["disagreement_summary"].get("preferred"))


if __name__ == "__main__":
    main()
