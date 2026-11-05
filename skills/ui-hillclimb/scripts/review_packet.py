#!/usr/bin/env python3
"""Prepare anonymous per-reviewer image copies and restore canonical result labels."""

import argparse
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import sys

from scorecard import artifact, digest, load, nonempty, require, verify_packet


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(packet_path, output_path, mapping_path, reviewer, workspace):
    packet = load(packet_path)
    verify_packet(packet)
    nonempty(reviewer, "reviewer")
    output = Path(output_path).resolve()
    private = Path(mapping_path).resolve()
    require(not output.is_relative_to(Path(workspace).resolve()), "reviewer copies must be outside the project workspace")
    require(not private.is_relative_to(output), "private mapping must be outside the reviewer directory")
    require(not private.is_relative_to(Path(workspace).resolve()), "private mapping must be outside the project workspace")
    require(not private.exists(), "private mapping already exists")
    variants = list(packet["images"])
    random.SystemRandom().shuffle(variants)
    labels = {f"sample-{i + 1:02}": variant for i, variant in enumerate(variants)}
    binding = {"packet_id": packet["packet_id"], "reviewer_id": reviewer,
               "labels": labels, "nonce": secrets.token_hex(32)}
    public = {"packet_id": packet["packet_id"], "reviewer_id": reviewer,
              "mapping_id": digest(binding), "images": {}}
    files = []
    output.mkdir(parents=True, exist_ok=False)
    try:
        for label, variant in labels.items():
            public["images"][label] = {}
            for index, (scenario, entry) in enumerate(sorted(packet["images"][variant].items())):
                suffix = Path(entry["path"]).suffix.lower()
                require(suffix in (".png", ".jpg", ".jpeg", ".webp", ".avif"), "unsupported image extension")
                destination = output / f"{label}-view-{index + 1:02}{suffix}"
                shutil.copyfile(entry["path"], destination)
                require(artifact(str(destination), output)["sha256"] == entry["sha256"], "image changed during copy")
                public["images"][label][scenario] = str(destination)
                files.append(artifact(str(destination), output))
        public_path = output / "packet.json"
        write_new(public_path, public)
        files.append(artifact(str(public_path), output))
        for entry in files:
            os.utime(entry["path"], (946684800, 946684800))
        write_new(private, {**binding, "files": files, "public_packet": str(public_path)})
    except Exception:
        shutil.rmtree(output)
        raise
    return {"reviewer_packet": str(public_path), "private_mapping": str(private)}


def unblind(result_path, mapping_path, output_path):
    result, mapping = load(result_path), load(mapping_path)
    require(result["packet_id"] == mapping["packet_id"], "review refers to another packet")
    require(result["reviewer_id"] == mapping["reviewer_id"], "reviewer mismatch")
    for entry in mapping["files"]:
        require(artifact(entry["path"], Path("/"))["sha256"] == entry["sha256"], "reviewer packet changed")
    labels = mapping["labels"]
    public = load(mapping["public_packet"])
    require(set(labels) == set(public["images"]) and len(set(labels.values())) == len(labels),
            "label mapping must be a bijection over the reviewer variants")
    binding = {key: mapping[key] for key in ("packet_id", "reviewer_id", "labels", "nonce")}
    require(public["mapping_id"] == digest(binding), "private label mapping changed")
    require(set(result["scores"]) <= set(labels), "unknown score variant")
    result["scores"] = {labels[label]: value for label, value in result["scores"].items()}
    for field in ("blockers", "findings"):
        for item in result.get(field, []):
            item["variant"] = labels[item["variant"]]
    for comparison in result.get("comparisons", []):
        for field in ("left", "right"):
            comparison[field] = labels[comparison[field]]
        if comparison["preferred"] not in ("tie", None):
            comparison["preferred"] = labels[comparison["preferred"]]
    write_new(output_path, result)
    return {"reviewer_id": result["reviewer_id"], "output": str(Path(output_path).resolve())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("packet")
    prepare_command.add_argument("output")
    prepare_command.add_argument("--map", required=True, dest="mapping")
    prepare_command.add_argument("--reviewer", required=True)
    prepare_command.add_argument("--workspace", required=True)
    restore_command = commands.add_parser("unblind")
    restore_command.add_argument("result")
    restore_command.add_argument("mapping")
    restore_command.add_argument("output")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.packet, args.output, args.mapping, args.reviewer, args.workspace)
        else:
            result = unblind(args.result, args.mapping, args.output)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"decision": "invalid", "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
