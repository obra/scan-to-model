"""Verify explicitly selected artifact paths against recorded bytes and SHA-256."""

import hashlib
import json
from pathlib import Path
import re

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(root, value):
    path = Path(value)
    return path if path.is_absolute() else root / path


def verify(bindings_path, root):
    """Return a JSON-serializable verification report for an explicit binding list."""
    bindings_path = Path(bindings_path)
    root = Path(root)
    document = json.loads(bindings_path.read_text(encoding="utf-8"))
    bindings = document.get("bindings") if isinstance(document, dict) else document
    if not isinstance(bindings, list):
        raise ValueError("bindings must be a JSON list or an object with a bindings list")
    report = {"valid": True, "root": str(root), "bindings": str(bindings_path), "verified": [], "mismatches": []}
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str) or not binding["path"]:
            report["valid"] = False
            report["mismatches"].append({"index": index, "reason": "invalid_binding"})
            continue
        expected = binding.get("sha256")
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            report["valid"] = False
            report["mismatches"].append({"index": index, "path": binding["path"], "reason": "invalid_sha256"})
            continue
        path = _path(root, binding["path"])
        if not path.is_file():
            report["valid"] = False
            report["mismatches"].append({"index": index, "path": binding["path"], "resolved_path": str(path), "reason": "missing"})
            continue
        actual_bytes = path.stat().st_size
        actual_sha256 = _digest(path)
        mismatch = None
        if actual_sha256.lower() != expected.lower():
            mismatch = {"index": index, "path": binding["path"], "resolved_path": str(path), "reason": "sha256_mismatch", "expected_sha256": expected, "actual_sha256": actual_sha256}
        elif "bytes" in binding and (not isinstance(binding["bytes"], int) or isinstance(binding["bytes"], bool) or binding["bytes"] < 0 or actual_bytes != binding["bytes"]):
            mismatch = {"index": index, "path": binding["path"], "resolved_path": str(path), "reason": "bytes_mismatch", "expected_bytes": binding.get("bytes"), "actual_bytes": actual_bytes}
        if mismatch:
            report["valid"] = False
            report["mismatches"].append(mismatch)
        else:
            report["verified"].append({"path": binding["path"], "resolved_path": str(path), "sha256": actual_sha256, "bytes": actual_bytes})
    return report
