"""Validate and synchronize structured completion-plan next actions."""

import argparse
import json
from pathlib import Path
import re
import sys


HEADING_RE = re.compile(r"^## ([^:\r\n]+):")
ACTION_RE = re.compile(r"^(?P<prefix>\s*\*\*Next action:\*\*)(?P<text>.*)$")


def _normalise_action(text):
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _backlog_actions(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    packages = data.get("packages")
    if not isinstance(packages, list):
        raise ValueError("backlog packages must be a list")
    actions = {}
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError("backlog package must be an object")
        package_id = package.get("id")
        action = package.get("next_action")
        if not isinstance(package_id, str) or not package_id.strip():
            raise ValueError("backlog package id must be a nonempty string")
        package_id = package_id.strip()
        if package_id in actions:
            raise ValueError(f"duplicate backlog package id: {package_id}")
        if not isinstance(action, str) or not _normalise_action(action):
            raise ValueError(f"backlog next_action must be nonempty: {package_id}")
        actions[package_id] = _normalise_action(action)
    return actions


def _human_sections(document):
    lines = document.splitlines(keepends=True)
    headings = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line.rstrip("\r\n"))
        if match:
            package_id = match.group(1).strip()
            if not package_id:
                raise ValueError("package heading id must be nonempty")
            headings.append((package_id, index))
    sections = []
    seen = set()
    for heading_index, (package_id, start) in enumerate(headings):
        if package_id in seen:
            raise ValueError(f"duplicate package heading: {package_id}")
        seen.add(package_id)
        end = headings[heading_index + 1][1] if heading_index + 1 < len(headings) else len(lines)
        action_slots = []
        for index in range(start + 1, end):
            body = lines[index].rstrip("\r\n")
            if ACTION_RE.match(body):
                action_slots.append(index)
        if not action_slots:
            raise ValueError(f"missing Next action slot: {package_id}")
        if len(action_slots) > 1:
            raise ValueError(f"duplicate Next action slot: {package_id}")
        action_index = action_slots[0]
        action_end = action_index + 1
        action_lines = [lines[action_index].rstrip("\r\n")]
        while action_end < end:
            continuation = lines[action_end].rstrip("\r\n")
            if not continuation.strip() or continuation.lstrip().startswith("**"):
                break
            action_lines.append(continuation)
            action_end += 1
        match = ACTION_RE.match(action_lines[0])
        action_text = [match.group("text").lstrip(), *[line.strip() for line in action_lines[1:]]]
        action_text = _normalise_action("\n".join(action_text))
        if not action_text:
            raise ValueError(f"empty Next action slot: {package_id}")
        sections.append({"id": package_id, "action_index": action_index,
                         "action_end": action_end, "action_text": action_text,
                         "lines": lines})
    return sections


def _validated_sections(backlog, document):
    sections = _human_sections(document)
    section_ids = {section["id"] for section in sections}
    for package_id in backlog:
        if package_id not in section_ids:
            raise ValueError(f"missing package heading: {package_id}")
    for section in sections:
        if section["id"] not in backlog:
            raise ValueError(f"unknown package heading: {section['id']}")
    return sections


def _mismatches(backlog, sections):
    return [section["id"] for section in sections
            if section["action_text"] != backlog[section["id"]]]


def _render_action(section, action):
    lines = section["lines"]
    index = section["action_index"]
    original = lines[index]
    body = original.rstrip("\r\n")
    separator = original[len(body):]
    final_line = lines[section["action_end"] - 1]
    final_body = final_line.rstrip("\r\n")
    final_ending = final_line[len(final_body):]
    prefix = ACTION_RE.match(body).group("prefix")
    values = action.splitlines() or [""]
    continuation_ending = separator or ("\n" if len(values) > 1 else "")
    rendered = []
    for value_index, value in enumerate(values):
        content = prefix + (" " + value if value else "") if value_index == 0 else value
        if value_index < len(values) - 1:
            content += continuation_ending
        elif final_ending:
            content += final_ending
        rendered.append(content)
    return rendered


def sync_document(backlog, document, sections):
    lines = document.splitlines(keepends=True)
    for section in reversed(sections):
        replacement = _render_action(section, backlog[section["id"]])
        lines[section["action_index"]:section["action_end"]] = replacement
    return "".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backlog", type=Path, required=True)
    parser.add_argument("--work-packages", type=Path, required=True)
    parser.add_argument("--sync", action="store_true",
                        help="update only human Next action text from the backlog")
    args = parser.parse_args(argv)
    backlog = _backlog_actions(args.backlog)
    document_bytes = args.work_packages.read_bytes()
    document = document_bytes.decode("utf-8")
    sections = _validated_sections(backlog, document)
    mismatches = _mismatches(backlog, sections)
    if not args.sync:
        if mismatches:
            for package_id in mismatches:
                print(f"action mismatch for {package_id}", file=sys.stderr)
            return 1
        print(json.dumps({"status": "pass", "mode": "validate",
                          "packages": len(backlog), "mismatches": 0}))
        return 0
    updated = sync_document(backlog, document, sections)
    updated_bytes = updated.encode("utf-8")
    if updated_bytes != document_bytes:
        args.work_packages.write_bytes(updated_bytes)
    print(json.dumps({"status": "pass", "mode": "sync", "packages": len(backlog),
                      "updated": len(mismatches)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(f"plan actions refused: {error}", file=sys.stderr)
        raise SystemExit(2)
