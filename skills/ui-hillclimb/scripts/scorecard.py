#!/usr/bin/env python3
"""Seal visual evidence and assess a complete UI review pass. Standard library only."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, name, low=0, high=float("inf")):
    require(type(value) in (int, float) and math.isfinite(value)
            and low <= value <= high, f"{name}: expected finite number in [{low}, {high}]")
    return value


def nonempty(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name}: expected nonempty string")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def fixed_images(contract, packet):
    candidate = contract["candidate"]
    fixed = contract.get("fixed_variants", [v for v in contract["variants"] if v != candidate])
    require(bool(fixed) and len(set(fixed)) == len(fixed), "at least one fixed comparison variant is required")
    require(candidate not in fixed, "candidate cannot be a fixed comparison")
    require(set(fixed) <= set(contract["variants"]), "unknown fixed comparison variant")
    return {variant: {scenario: packet["images"][variant][scenario]["sha256"]
                      for scenario in contract["variants"][variant]} for variant in fixed}


def start(contract_path, state_path, packet_path):
    contract, packet = load(contract_path), load(packet_path)
    verify_packet(packet)
    state = {"contract_id": digest(contract), "started_at": time.time(), "history": [],
             "fixed_images": fixed_images(contract, packet)}
    with Path(state_path).open("x") as stream:
        json.dump(state, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return {"state": str(Path(state_path).resolve()), "contract_id": state["contract_id"]}


def artifact(path, base):
    resolved = (base / path).resolve()
    require(resolved.is_file(), f"missing artifact: {resolved}")
    return {"path": str(resolved), "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()}


def seal(spec_path, output):
    spec = load(spec_path)
    base = Path(spec_path).resolve().parent
    nonempty(spec["revision"], "revision")
    require(bool(spec["images"]), "images must not be empty")
    images = {}
    for variant, scenarios in spec["images"].items():
        nonempty(variant, "variant")
        require(bool(scenarios), f"{variant}: empty scenarios")
        images[variant] = {scenario: artifact(path, base) for scenario, path in scenarios.items()}
    checks = {}
    for name, check in spec["checks"].items():
        require(type(check["passed"]) is bool, f"{name}: passed must be boolean")
        checks[name] = {"passed": check["passed"], **artifact(check["path"], base)}
    packet = {"revision": spec["revision"], "images": images, "checks": checks}
    packet["packet_id"] = digest(packet)
    with Path(output).open("x") as stream:
        json.dump(packet, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return {"packet_id": packet["packet_id"], "output": str(Path(output).resolve())}


def verify_packet(packet):
    unsigned = {k: v for k, v in packet.items() if k != "packet_id"}
    require(digest(unsigned) == packet["packet_id"], "packet content changed after sealing")
    for collection in [*packet["images"].values(), packet["checks"]]:
        for entry in collection.values():
            current = artifact(entry["path"], Path("/"))
            require(current["sha256"] == entry["sha256"], f"artifact changed: {entry['path']}")


def assess(contract, packet, review_pass):
    verify_packet(packet)
    target = number(contract["target_score"], "target_score", 0, 10)
    max_rounds = number(contract["max_rounds"], "max_rounds", 1)
    max_minutes = number(contract["max_minutes"], "max_minutes", 0.001)
    round_number = number(review_pass["round"], "round", 1)
    require(int(round_number) == round_number and int(max_rounds) == max_rounds,
            "round and max_rounds must be integers")
    elapsed = number(review_pass["elapsed_minutes"], "elapsed_minutes")
    require(review_pass["stage"] in ("pilot", "full", "confirmation"), "unknown review stage")
    require(review_pass["revision"] == packet["revision"], "review pass refers to another revision")
    require(review_pass["packet_id"] == packet["packet_id"], "review pass refers to another packet")
    candidate = contract["candidate"]
    variants = contract["variants"]
    require(candidate in variants, "candidate missing from variants")
    categories = contract["categories"]
    require(bool(categories) and len(set(categories)) == len(categories), "invalid categories")
    require(bool(contract["checks"]), "at least one workflow/check is required")
    reviewers = contract["reviewers"]
    require(bool(reviewers), "reviewers must not be empty")
    ids = [nonempty(r["id"], "reviewer id") for r in reviewers]
    require(len(set(ids)) == len(ids), "duplicate reviewer IDs")
    identities = [(nonempty(r["provider"], "provider"), nonempty(r["model"], "model")) for r in reviewers]
    require(len(set(identities)) == len(identities), "duplicate provider/model identities")
    for variant, scenarios in variants.items():
        require(bool(scenarios) and len(set(scenarios)) == len(scenarios), f"invalid scenarios: {variant}")
        for scenario in scenarios:
            require(scenario in packet["images"].get(variant, {}), f"missing image: {variant}/{scenario}")
    reasons = []
    for check in contract["checks"]:
        if packet["checks"].get(check, {}).get("passed") is not True:
            reasons.append(f"required check not passed: {check}")
    submitted = review_pass["reviews"]
    require(len({r["reviewer_id"] for r in submitted}) == len(submitted), "duplicate submitted reviewer")
    require({r["reviewer_id"] for r in submitted} <= set(ids), "unexpected reviewer")
    by_id = {r["reviewer_id"]: r for r in submitted}
    minimums = {}
    preference_counts = {reference: 0 for reference in contract.get("prefer_over", [])}
    for reference in preference_counts:
        require(reference in variants and reference != candidate, "invalid prefer_over variant")
    for expected in reviewers:
        reviewer_id = expected["id"]
        if reviewer_id not in by_id:
            reasons.append(f"missing reviewer: {reviewer_id}")
            continue
        result = by_id[reviewer_id]
        require(result["provider"] == expected["provider"] and result["model"] == expected["model"],
                f"model identity mismatch: {reviewer_id}")
        require(result["packet_id"] == packet["packet_id"], f"stale review: {reviewer_id}")
        require(isinstance(result["blockers"], list), f"{reviewer_id}/blockers: expected list")
        for blocker in result["blockers"]:
            require(blocker["variant"] in variants, "blocker refers to unknown variant")
            require(blocker["scenario"] in variants[blocker["variant"]], "blocker refers to unknown scenario")
            nonempty(blocker["evidence"], "blocker evidence")
            if blocker["variant"] == candidate:
                reasons.append(f"{reviewer_id}/blocker: {blocker['scenario']}: {blocker['evidence']}")
        require(isinstance(result["unverified"], list), f"{reviewer_id}/unverified: expected list")
        reasons.extend(f"{reviewer_id}/unverified: {nonempty(item, 'unverified')}"
                       for item in result["unverified"])
        candidate_scores = []
        for variant, scenarios in variants.items():
            for scenario in scenarios:
                cells = result["scores"].get(variant, {}).get(scenario, {})
                for category in categories:
                    label = f"{reviewer_id}/{variant}/{scenario}/{category}"
                    cell = cells.get(category, {})
                    score = cell.get("score")
                    evidence = cell.get("evidence")
                    if score is None or not isinstance(evidence, str) or not evidence.strip():
                        reasons.append(f"missing score/evidence: {label}")
                        continue
                    number(score, label, 0, 10)
                    if variant == candidate:
                        candidate_scores.append(score)
                        if score < target:
                            reasons.append(f"below target: {label}={score}")
        minimums[reviewer_id] = min(candidate_scores) if candidate_scores else None
        for reference in preference_counts:
            comparisons = [entry for entry in result.get("comparisons", [])
                           if {entry["left"], entry["right"]} == {candidate, reference}]
            require(len(comparisons) <= 1, f"duplicate pairwise preference: {reviewer_id}/{reference}")
            if not comparisons or not comparisons[0].get("evidence", "").strip():
                reasons.append(f"missing pairwise preference: {reviewer_id}/{reference}")
                continue
            preference = comparisons[0]["preferred"]
            require(preference in (candidate, reference, "tie", None), "invalid preferred variant")
            preference_counts[reference] += preference == candidate
            if preference is None:
                reasons.append(f"unverified pairwise preference: {reviewer_id}/{reference}")
        for reference in contract.get("must_beat", []):
            require(reference in variants and reference != candidate, "invalid must_beat variant")
            for scenario in variants[reference]:
                require(scenario in variants[candidate], "must_beat needs matching candidate scenario")
                for category in categories:
                    left = result["scores"].get(candidate, {}).get(scenario, {}).get(category, {}).get("score")
                    right = result["scores"].get(reference, {}).get(scenario, {}).get(category, {}).get("score")
                    if left is None or right is None or left <= right:
                        reasons.append(f"comparison not won: {reviewer_id}/{reference}/{scenario}/{category}")
    for reference, count in preference_counts.items():
        if count <= len(reviewers) // 2:
            reasons.append(f"no strict-majority preference over {reference}")
    if review_pass["stage"] == "pilot" or len(reviewers) < 2:
        reasons.append("pilot pass cannot establish panel agreement")
    money_cap = contract.get("max_spend_usd")
    cost_stop = False
    if money_cap is not None:
        number(money_cap, "max_spend_usd")
        spend = review_pass.get("spend_usd")
        if spend is None:
            reasons.append("spend unknown under explicit money cap")
            cost_stop = True
        else:
            cost_stop = number(spend, "spend_usd") >= money_cap
    exceeded = round_number > max_rounds or elapsed > max_minutes or cost_stop
    exhausted = round_number >= max_rounds or elapsed >= max_minutes or cost_stop
    if exceeded:
        reasons.append("run exceeded a limit or cannot continue within the money cap")
    if not reasons:
        decision = "panel_met"
    elif exhausted:
        decision = "budget_stop"
    else:
        decision = "needs_work"
    return {"decision": decision, "stage": review_pass["stage"], "packet_id": packet["packet_id"],
            "candidate_minimums": minimums, "preference_votes": preference_counts, "reasons": reasons,
            "note": "Checks declarations, coverage and artifact integrity; does not prove taste, execution or independence."}


def record_pass(contract_path, packet_path, pass_path, state_path):
    contract, packet, review_pass = load(contract_path), load(packet_path), load(pass_path)
    state = load(state_path)
    require(state["contract_id"] == digest(contract), "contract changed; resume with the original contract")
    verify_packet(packet)
    require(state["fixed_images"] == fixed_images(contract, packet), "fixed comparison images changed during this run")
    history = state["history"]
    declared_elapsed = number(review_pass["elapsed_minutes"], "elapsed_minutes")
    declared_spend = review_pass.get("spend_usd")
    if declared_spend is not None:
        number(declared_spend, "spend_usd")
    last = history[-1] if history else None
    round_number = review_pass["round"]
    evidence_id = digest({"revision": packet["revision"],
                          "candidate_images": {scenario: packet["images"][contract["candidate"]][scenario]["sha256"]
                                               for scenario in contract["variants"][contract["candidate"]]}})
    previous_round = last["round"] if last else 0
    require(previous_round <= round_number <= previous_round + 1 and round_number >= 1,
            "round reset or skipped round in persisted history")
    if last:
        require(last["decision"] not in ("budget_stop", "target_met"), "run already stopped; preserve its final result")
        require(declared_elapsed >= last["declared_elapsed_minutes"], "elapsed time reset")
        if last["spend_usd"] is not None:
            require(declared_spend is not None and declared_spend >= last["spend_usd"], "spend reset")
        if round_number == previous_round:
            require(packet["packet_id"] == last["packet_id"], "changed capture requires a new round")
        else:
            require(packet["packet_id"] != last["packet_id"], "a new round requires new capture evidence")
    if review_pass["stage"] == "full":
        require(not any(event["stage"] == "full" and event["evidence_id"] == evidence_id for event in history),
                "full review already recorded for this source and candidate images; change the candidate before another full panel")
    tasks = review_pass["delegate_tasks"]
    submitted_ids = {r["reviewer_id"] for r in review_pass["reviews"]}
    require(isinstance(tasks, dict) and set(tasks) == submitted_ids, "delegate_tasks must map every submitted reviewer")
    task_ids = [nonempty(value, "delegate task ID") for value in tasks.values()]
    require(len(set(task_ids)) == len(task_ids), "duplicate delegate task IDs")
    used_tasks = {task for event in history for task in event["delegate_tasks"].values()}
    require(not (set(task_ids) & used_tasks), "review delegate reused; start fresh review tasks")
    confirmation = review_pass["stage"] == "confirmation"
    if confirmation:
        require(last is not None and last["stage"] == "full" and last["decision"] == "panel_met"
                and last["packet_id"] == packet["packet_id"],
                "confirmation needs the immediately preceding passing full panel on this capture")
    effective_pass = dict(review_pass)
    actual_elapsed = max(0, (time.time() - number(state["started_at"], "started_at")) / 60)
    effective_pass["elapsed_minutes"] = max(declared_elapsed, actual_elapsed)
    result = assess(contract, packet, effective_pass)
    if confirmation and result["decision"] == "panel_met":
        result["decision"] = "target_met"
    event = {"round": round_number, "stage": review_pass["stage"], "packet_id": packet["packet_id"],
             "evidence_id": evidence_id,
             "declared_elapsed_minutes": declared_elapsed, "elapsed_minutes": effective_pass["elapsed_minutes"],
             "spend_usd": declared_spend, "delegate_tasks": tasks, "decision": result["decision"]}
    state["history"].append(event)
    destination = Path(state_path)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, allow_nan=False) + "\n")
    temporary.replace(destination)
    result["elapsed_minutes"] = effective_pass["elapsed_minutes"]
    result["recorded_passes"] = len(state["history"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start_command = commands.add_parser("start", help="Freeze the contract and start a persisted run clock")
    start_command.add_argument("contract")
    start_command.add_argument("state")
    start_command.add_argument("--packet", required=True, help="Initial sealed evidence that freezes comparison image bytes")
    seal_command = commands.add_parser("seal", help="Hash capture artifacts into a new immutable packet file")
    seal_command.add_argument("spec")
    seal_command.add_argument("output")
    gate = commands.add_parser("gate", help="Assess one review pass; outputs JSON, never edits the app")
    gate.add_argument("contract")
    gate.add_argument("packet")
    gate.add_argument("review_pass")
    gate.add_argument("--state", required=True, help="State file created by start; keep it when resuming")
    args = parser.parse_args()
    try:
        if args.command == "start":
            result = start(args.contract, args.state, args.packet)
        elif args.command == "seal":
            result = seal(args.spec, args.output)
        else:
            result = record_pass(args.contract, args.packet, args.review_pass, args.state)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result.get("decision", "panel_met") in ("panel_met", "target_met") else 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"decision": "invalid", "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
