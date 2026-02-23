#!/usr/bin/env python3
"""
Robust multi-format PDF -> CSV parser for swimming meet results.

Implements:
- Format detection for known families.
- Family-specific parsing adapters.
- Strict validation gates to block malformed/missing data.
- Backup refresh + atomic write workflow.
- Candidate CSV + JSON report on failure.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from pypdf import PdfReader

FIELDS = [
    "Meet_Name",
    "Meet_Date",
    "Name",
    "Age",
    "Rank",
    "Time",
    "Team",
    "Notes",
    "Event_Type",
]

STATUS_VALUES = {"DQ", "DNF", "DNS", "NS", "DW", "SCR", "DSQ"}
RELAY_MARKER_ARTIFACT_RE = re.compile(r"(?:\b[1-4]\)|\d[1-4]\))")


@dataclass
class ParseContext:
    meet_name: str = ""
    meet_date: str = ""
    event_headers: list[str] = field(default_factory=list)
    event_has_rows: list[bool] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    family: str = ""

    def open_event(self, event_name: str) -> None:
        self.event_headers.append(event_name)
        self.event_has_rows.append(False)

    def mark_event_has_row(self) -> None:
        if self.event_has_rows:
            self.event_has_rows[-1] = True


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    stats: dict[str, int | str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Robust swimming PDF parser")
    parser.add_argument("--pdf-path", required=True, help="Input PDF path")
    parser.add_argument("--active-csv-path", required=True, help="Target active CSV path")
    parser.add_argument("--backup-csv-path", required=True, help="Backup CSV path")
    parser.add_argument(
        "--mode", default="strict", choices=["strict", "lenient"], help="Validation mode"
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Optional output JSON report path",
    )
    parser.add_argument(
        "--candidate-path",
        default=None,
        help="Optional candidate CSV path for failed parses",
    )
    return parser.parse_args()


def convert_name(name_str: str) -> str:
    s = (name_str or "").strip()
    if "," in s:
        last, first = s.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return s


def format_rank(place_str: str) -> str:
    if not place_str or not place_str.isdigit():
        return place_str
    num = int(place_str)
    if num == 1:
        return "1st"
    if num == 2:
        return "2nd"
    if num == 3:
        return "3rd"
    return f"{num}th"


def infer_event_age_bounds(event_name: str) -> tuple[int, int] | None:
    s = event_name
    m = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})", s)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        if low <= high:
            return low, high
    m = re.search(r"(\d{1,2})\s*&\s*Under", s)
    if m:
        high = int(m.group(1))
        return 0, high
    m = re.search(r"(\d{1,2})\s*&\s*Over", s)
    if m:
        low = int(m.group(1))
        return low, 99
    m = re.search(r"(\d{1,2})\s*Year Olds", s)
    if m:
        age = int(m.group(1))
        return age, age
    return None


def split_age_place_token(token: str, event_name: str) -> tuple[str, str]:
    token = token.replace("*", "")
    if token.endswith("---"):
        return token[:-3], "---"

    bounds = infer_event_age_bounds(event_name)
    candidates: list[tuple[str, str]] = []
    for split_idx in range(1, len(token)):
        age_s = token[:split_idx]
        place_s = token[split_idx:]
        if not age_s.isdigit() or not place_s.isdigit():
            continue
        age_i = int(age_s)
        place_i = int(place_s)
        if age_i < 5 or age_i > 25:
            continue
        if place_i < 1:
            continue
        candidates.append((age_s, place_s))

    if not candidates:
        return token[:1], token[1:]

    if bounds:
        low, high = bounds
        bounded = [(a, p) for a, p in candidates if low <= int(a) <= high]
        if bounded:
            candidates = bounded

    # Prefer the longest valid age prefix (e.g., 10 over 1 in token 1010).
    candidates.sort(key=lambda ap: len(ap[0]), reverse=True)
    return candidates[0]


def detect_family_with_diagnostics(lines: list[str]) -> tuple[str, dict[str, int | str]]:
    count_hash_headers = 0
    count_event_headers = 0
    count_event_number_headers = 0
    count_age_name = 0
    count_teamname_headers = 0
    count_age_name_seed_headers = 0
    count_age_name_finals_headers = 0
    count_team_relay_finals_headers = 0
    count_individual_meet_results = 0
    count_besmartt_event_titles = 0
    count_besmartt_age_headers = 0
    for line in lines:
        s = line.strip()
        s_norm = re.sub(r"\s+", " ", s)
        if re.match(r"^#\d+\s+", s):
            count_hash_headers += 1
        if re.match(r"^Event\s+\d+\s+", s):
            count_event_headers += 1
        if re.match(r"^Event\s*#\s*\d+\s+", s):
            count_event_number_headers += 1
        if "Age Name" in s or "AgeName" in s:
            count_age_name += 1
        if "Age   TeamName Finals Time" in s or "RelayTeam Finals Time" in s:
            count_teamname_headers += 1
        if (
            "AgeName Team Finals TimeSeed Time" in s
            or "AgeName Team Finals TimeSeed Time Points" in s
        ):
            count_age_name_seed_headers += 1
        if re.match(r"^AgeName Team Finals Time(?:\s+)?$", s):
            count_age_name_finals_headers += 1
        if re.match(r"^Team Relay Finals Time(?:\s+)?$", s):
            count_team_relay_finals_headers += 1
        if "Individual  Meet  Results" in s:
            count_individual_meet_results += 1
        if re.match(r"^(Girls|Boys|Women|Men)\s+.+\s+Yard\s+.+$", s_norm):
            count_besmartt_event_titles += 1
        if "AgeName Team Finals" in s_norm and "Seed Time" in s_norm:
            count_besmartt_age_headers += 1

    diagnostics: dict[str, int | str] = {
        "count_hash_headers": count_hash_headers,
        "count_event_headers": count_event_headers,
        "count_event_number_headers": count_event_number_headers,
        "count_age_name": count_age_name,
        "count_teamname_headers": count_teamname_headers,
        "count_age_name_seed_headers": count_age_name_seed_headers,
        "count_age_name_finals_headers": count_age_name_finals_headers,
        "count_team_relay_finals_headers": count_team_relay_finals_headers,
        "count_individual_meet_results": count_individual_meet_results,
        "count_besmartt_event_titles": count_besmartt_event_titles,
        "count_besmartt_age_headers": count_besmartt_age_headers,
        "d1_probe_count": 0,
        "d2_probe_count": 0,
        "c1_probe_count": 0,
        "c2_probe_count": 0,
    }

    if count_hash_headers > 0:
        return "A", diagnostics
    if count_event_number_headers > 0 and count_individual_meet_results > 0:
        return "F", diagnostics
    if (
        count_event_headers == 0
        and count_besmartt_event_titles >= 8
        and count_besmartt_age_headers >= 8
    ):
        return "G", diagnostics

    # D1/D2 both use the seed-time header. Split by data-line row-shape probes.
    if count_event_headers > 0 and count_age_name_seed_headers > 0:
        d1_probe_pattern = re.compile(
            r"^.+?\s+\d{1,2}.+?\s+(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+(?:NT|\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})\s*(?:\*?\d+|---)$"
        )
        d2_probe_pattern = re.compile(
            r"^.+?\s+\d{1,2}(?:\*?\d+|---)\s+.+?\s+(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)(?:\s+\d+:\d{2}\.\d{2})?\s+(?:NT|\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})$"
        )

        d1_count = 0
        d2_count = 0
        for line in lines:
            s = line.strip()
            if (
                not s
                or s.startswith("Event ")
                or s.startswith("(Event ")
                or s.startswith("AgeName Team Finals TimeSeed Time")
                or s.startswith("Results")
                or "HY-TEK" in s
                or "HY - TEK" in s
            ):
                continue
            if d1_probe_pattern.match(s):
                d1_count += 1
            elif d2_probe_pattern.match(s):
                d2_count += 1

        diagnostics["d1_probe_count"] = d1_count
        diagnostics["d2_probe_count"] = d2_count

        if d1_count > d2_count:
            return "D1", diagnostics
        if d2_count > d1_count:
            return "D2", diagnostics
        diagnostics["reason"] = "ambiguous_d_subtype_detection"
        return "unsupported", diagnostics

    if count_event_headers > 0 and (
        count_age_name_finals_headers > 0 or count_team_relay_finals_headers > 0
    ):
        return "E", diagnostics
    if count_event_headers > 0 and count_teamname_headers > 0:
        c1_probe_pattern = re.compile(
            r"^[A-Z]{2,}[\-A-Z\s]+?\s+\d{1,2}(?:\*?\d+|---)\s+(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ).+$"
        )
        c2_probe_pattern = re.compile(
            r"^\S+\s+\d{1,2}.+?(?:\*?\d+|---)\s+(?:[xX]?(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ))(?:\s+\S+){0,2}$"
        )
        c1_count = 0
        c2_count = 0
        for line in lines:
            s = line.strip()
            if (
                not s
                or s.startswith("Event ")
                or s.startswith("(Event ")
                or s.startswith("Age   TeamName Finals Time")
                or s.startswith("RelayTeam Finals Time")
                or s.startswith("Results")
                or "HY-TEK" in s
                or "HY - TEK" in s
                or s.startswith("Combined Team Scores")
                or "Through Event" in s
                or s.startswith("Licensed To:")
                or re.match(r"^[1-4]\)\s+", s)
            ):
                continue
            if c1_probe_pattern.match(s):
                c1_count += 1
            elif c2_probe_pattern.match(s):
                c2_count += 1

        diagnostics["c1_probe_count"] = c1_count
        diagnostics["c2_probe_count"] = c2_count

        if c2_count > c1_count:
            return "C2", diagnostics
        return "C1", diagnostics
    if count_event_headers > 0:
        return "B", diagnostics
    if count_age_name > 0 and count_hash_headers > 0:
        return "A", diagnostics
    return "unsupported", diagnostics


def normalize_relay_swimmer_line_family_b(line: str) -> str:
    fixed = re.sub(r"(\d)([1-4]\))", r"\1 \2", line)
    fixed = re.sub(r"(?<!\s)([1-4]\))", r" \1", fixed)
    fixed = re.sub(r"\s+", " ", fixed).strip()
    return fixed


def normalize_relay_swimmer_line_family_a(line: str) -> str:
    # Fix merged age->next-name boundaries, e.g. "7LaVecchia, Jake" / "10Acosta, Luciana".
    fixed = re.sub(r"(\d)([A-Za-z][A-Za-z'\-\. ]*,)", r"\1 \2", line)
    fixed = re.sub(r"\s+", " ", fixed).strip()
    return fixed


def extract_text_lines(pdf_path: Path) -> list[str]:
    reader = PdfReader(pdf_path)
    lines: list[str] = []
    for page in reader.pages:
        lines.extend((page.extract_text() or "").splitlines())
    return lines


def parse_meet_line(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if "HY-TEK" in s or "HY - TEK" in s:
        return None
    m = re.match(r"^(.*?)\s+-\s+(\d{1,2}/\d{1,2}/\d{4})$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.*?)\s+-\s+(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


def parse_team_manager_meet_line(line: str) -> tuple[str, str] | None:
    s = line.strip()
    m = re.match(
        r"^(.*?)\s+(\d{1,2}-[A-Za-z]{3}-\d{2})\s+\[Ageup:\s*\d{1,2}/\d{1,2}/\d{4}\]\s+Yards$", s
    )
    if not m:
        return None
    meet_name = re.sub(r"\s+", " ", m.group(1)).strip()
    raw_date = m.group(2)
    try:
        meet_date = datetime.strptime(raw_date, "%d-%b-%y").strftime("%-m/%-d/%Y")
    except ValueError:
        return None
    return meet_name, meet_date


def parse_besmartt_meet_line(line: str) -> tuple[str, str] | None:
    s = re.sub(r"\s+", " ", line.strip())
    m = re.match(r"^(.*?)\s*-\s*(\d{1,2}-\d{1,2}-\d{4})\s+to\s+(\d{1,2}-\d{1,2}-\d{4})$", s)
    if not m:
        return None
    meet_name = m.group(1).strip()
    raw_date = m.group(2).strip()
    try:
        meet_date = datetime.strptime(raw_date, "%m-%d-%Y").strftime("%-m/%-d/%Y")
    except ValueError:
        return None
    return meet_name, meet_date


def parse_family_a(lines: list[str]) -> ParseContext:
    ctx = ParseContext(family="A")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    relay_team_pattern = re.compile(
        r"^([A-E])([A-Z]{2,}[\-A-Z\s]+?)(\d+|---)\s+(?:x|X)?([\d:\.]+[\$\*]?|DQ|DNF|DNS|NS|DW|SCR|DSQ)(?:\s+([\d:\.]+[\$\*]?|DQ|DNF|DNS|NS|DW|SCR|DSQ))?$"
    )
    relay_swimmer_pattern = re.compile(r"([^,]+,\s*.+?)\s+(\d+)(?=\s+[^,]+,\s|$)")
    individual_pattern = re.compile(
        r"^([A-Z]{2,}[\-A-Z\s]+?)\s+(\d{1,2})([A-Za-z][\w\s,'\-\.]+?)(\d+|---)\s+(?:x|X)?([\d:\.]+[\$\*]?|DQ|DNF|DNS|NS|DW|SCR|DSQ)(?:\s+([\d:\.]+[\$\*]?|DQ|DNF|DNS|NS|DW|SCR|DSQ))?$"
    )

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        header_match = re.match(r"^#\d+\s+(.*)$", line)
        if header_match:
            flush_pending_relay()
            current_event = header_match.group(1).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "Age Name" in line
            or "Team Finals Time" in line
            or "Team Relay Finals Time" in line
            or line.startswith("Results")
            or line.startswith("SpookSprint:")
            or "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
            or re.match(r"^\(#\d+", line)
            or re.match(r"^\d+\.\s", line)
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_match = relay_team_pattern.match(line)
            if relay_match:
                flush_pending_relay()
                letter, base_team, place, status_or_time, maybe_time = relay_match.groups()
                base_team = base_team.strip()
                status_or_time = status_or_time.rstrip("$*")
                final_time = maybe_time.rstrip("$*") if maybe_time else status_or_time

                rank = ""
                notes = ""
                if status_or_time in STATUS_VALUES:
                    rank = status_or_time
                    final_time = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if (
                            next_line
                            and not next_line.startswith("#")
                            and not relay_team_pattern.match(next_line)
                            and any(
                                key in next_line
                                for key in (
                                    "Infraction",
                                    "Did not",
                                    "kick",
                                    "False start",
                                    "Alternating",
                                    "Stroke",
                                )
                            )
                        ):
                            notes = next_line
                elif place == "---":
                    rank = "X"
                    notes = "Exhibition swim"
                else:
                    rank = format_rank(place)

                pending_relay = {
                    "team_name": f"{base_team} {letter}",
                    "team": base_team,
                    "rank": rank,
                    "time": final_time,
                    "event_type": current_event,
                    "notes": notes,
                }
                relay_swimmers = []
                i += 1
                continue

            if pending_relay and "," in line:
                swimmers_on_line: list[str] = []
                normalized_line = normalize_relay_swimmer_line_family_a(line)
                for m in relay_swimmer_pattern.finditer(normalized_line):
                    swimmers_on_line.append(f"{convert_name(m.group(1))} {m.group(2)}")
                if swimmers_on_line:
                    relay_swimmers.extend(swimmers_on_line)
                i += 1
                continue

            i += 1
            continue

        individual_match = individual_pattern.match(line)
        if individual_match:
            team, age, name_part, place, status_or_time, maybe_time = individual_match.groups()
            status_or_time = status_or_time.rstrip("$*")
            final_time = maybe_time.rstrip("$*") if maybe_time else status_or_time

            rank = ""
            notes = ""
            if status_or_time in STATUS_VALUES:
                rank = status_or_time
                final_time = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith("#")
                        and not re.match(r"^[A-Z]{2,}[\-A-Z\s]+?\s+\d{1,2}", next_line)
                        and any(
                            key in next_line
                            for key in (
                                "Infraction",
                                "Did not",
                                "kick",
                                "False start",
                                "Alternating",
                                "Stroke",
                            )
                        )
                    ):
                        notes = next_line
            elif place == "---":
                rank = "X"
                notes = "Exhibition swim"
            else:
                rank = format_rank(place)

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": convert_name(name_part),
                    "Age": age.strip(),
                    "Rank": rank,
                    "Time": final_time,
                    "Team": team.strip(),
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()

        i += 1

    flush_pending_relay()
    return ctx


def parse_family_b(lines: list[str]) -> ParseContext:
    ctx = ParseContext(family="B")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    relay_result_pattern = re.compile(
        r"^([A-E])(\d+|---)\s+(.+?)\s+(\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)$"
    )
    relay_swimmer_pattern = re.compile(r"([1-4])\)\s*(.+?)\s+(\d+)(?=\s+[1-4]\)|$)")
    individual_pattern = re.compile(
        r"^(?P<team>.+?)\s+(?P<token>\d(?:\d+|---))\s+(?P<name>.+?)\s+(?P<time>\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)$"
    )

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        event_match = re.match(r"^Event\s+\d+\s+(.*)$", line)
        if event_match:
            flush_pending_relay()
            current_event = event_match.group(1).strip()
            current_event = re.sub(r"AgeName\s+Team\s+Finals\s+Time\s*$", "", current_event).strip()
            current_event = re.sub(r"Team\s+Relay\s+Finals\s+Time\s*$", "", current_event).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or re.match(r"^\d{1,2}:\d{2}\.\d{2}\d{1,2}:\d{2}(?:\.\d{2})?$", line)
            or re.match(r"^(DQ|DNF|DNS|NS|DW|SCR|DSQ)\d", line)
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_match = relay_result_pattern.match(line)
            if relay_match:
                flush_pending_relay()
                letter, place, team, status_or_time = relay_match.groups()
                team = team.strip()
                rank = ""
                notes = ""
                final_time = status_or_time
                if status_or_time in STATUS_VALUES:
                    rank = status_or_time
                    final_time = ""
                elif place == "---":
                    rank = "X"
                    notes = "Exhibition swim"
                else:
                    rank = format_rank(place)

                pending_relay = {
                    "team_name": f"{team} {letter}",
                    "team": team,
                    "rank": rank,
                    "time": final_time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                i += 1
                continue

            if pending_relay and re.search(r"[1-4]\)", line):
                fixed_line = normalize_relay_swimmer_line_family_b(line)
                swimmers_found: list[tuple[int, str]] = []
                for sm in relay_swimmer_pattern.finditer(fixed_line):
                    idx = int(sm.group(1))
                    swimmers_found.append((idx, f"{convert_name(sm.group(2))} {sm.group(3)}"))
                if swimmers_found:
                    swimmers_found.sort(key=lambda pair: pair[0])
                    relay_swimmers.extend([name for _, name in swimmers_found])
                i += 1
                continue

            i += 1
            continue

        individual_match = individual_pattern.match(line)
        if individual_match:
            team = individual_match.group("team").strip()
            token = individual_match.group("token").strip()
            name = convert_name(individual_match.group("name"))
            time_or_status = individual_match.group("time").strip()

            age = token[0]
            place = "---" if token.endswith("---") else token[1:]
            rank = ""
            notes = ""
            final_time = time_or_status

            if time_or_status in STATUS_VALUES:
                rank = time_or_status
                final_time = ""
            elif place == "---":
                rank = "X"
                notes = "Exhibition swim"
            else:
                rank = format_rank(place)

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": name,
                    "Age": age,
                    "Rank": rank,
                    "Time": final_time,
                    "Team": team,
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()

        i += 1

    flush_pending_relay()
    return ctx


def parse_family_c1(lines: list[str]) -> ParseContext:
    """
    Family C1 format (e.g., 2024 HCY Autumn Challenge):
    - Event headers: "Event n  ..."
    - Individual rows: "TEAM 121 13:06.89Lastname, First"
    - Relay rows: "A1 2:08.88TEAM" / "B*14 3:02.84TEAM" / "A--- DQTEAM"
    """
    ctx = ParseContext(family="C1")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    relay_result_pattern = re.compile(
        r"^([A-E])(\*?)(\d+|---)\s+(\d+:\d{2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)([A-Z]{2,}[\-A-Z\s]+)$"
    )
    relay_swimmer_pattern = re.compile(r"([1-4])\)\s*(.+?)\s+(\d+)(?=\s+[1-4]\)|$)")
    individual_pattern = re.compile(
        r"^(?P<team>[A-Z]{2,}[\-A-Z\s]+?)\s+(?P<token>\d{1,2}(?:\*?\d+|---))\s+(?P<result>\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)(?P<name>.+)$"
    )

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        event_match = re.match(r"^Event\s+\d+\s+(.*)$", line)
        if event_match:
            flush_pending_relay()
            current_event = event_match.group(1).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or line.startswith("Age   TeamName Finals Time")
            or line.startswith("RelayTeam Finals Time")
            or line.startswith("(Event ")
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
            or re.match(r"^\d+\.\s", line)
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_match = relay_result_pattern.match(line)
            if relay_match:
                flush_pending_relay()
                letter, star, place, result, team = relay_match.groups()
                team = team.strip()
                rank = ""
                notes = ""
                final_time = result

                if result in STATUS_VALUES:
                    rank = result
                    final_time = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if (
                            next_line
                            and not next_line.startswith("1)")
                            and not next_line.startswith("2)")
                        ):
                            if any(
                                key in next_line
                                for key in (
                                    "Infraction",
                                    "Did not",
                                    "kick",
                                    "False start",
                                    "Alternating",
                                    "Stroke",
                                    "Early",
                                )
                            ):
                                notes = next_line
                elif star == "*" or place == "---":
                    rank = "X"
                    notes = "Exhibition swim"
                else:
                    rank = format_rank(place)

                pending_relay = {
                    "team_name": f"{team} {letter}",
                    "team": team,
                    "rank": rank,
                    "time": final_time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                i += 1
                continue

            if pending_relay and ("1)" in line or "2)" in line or "3)" in line or "4)" in line):
                normalized_line = normalize_relay_swimmer_line_family_b(line)
                swimmers_found: list[tuple[int, str]] = []
                for sm in relay_swimmer_pattern.finditer(normalized_line):
                    idx = int(sm.group(1))
                    swimmers_found.append((idx, f"{convert_name(sm.group(2))} {sm.group(3)}"))
                if swimmers_found:
                    swimmers_found.sort(key=lambda pair: pair[0])
                    relay_swimmers.extend([name for _, name in swimmers_found])
                i += 1
                continue

            i += 1
            continue

        individual_match = individual_pattern.match(line)
        if individual_match:
            team = individual_match.group("team").strip()
            token = individual_match.group("token").strip()
            result = individual_match.group("result").strip()
            name = convert_name(individual_match.group("name"))

            age, place = split_age_place_token(token, current_event)
            rank = ""
            notes = ""
            final_time = result

            if result in STATUS_VALUES:
                rank = result
                final_time = ""
            elif place == "---":
                rank = "X"
                notes = "Exhibition swim"
            else:
                rank = format_rank(place)

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": name.strip(),
                    "Age": age,
                    "Rank": rank,
                    "Time": final_time,
                    "Team": team,
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()
        i += 1

    flush_pending_relay()
    return ctx


def parse_family_c2(lines: list[str]) -> ParseContext:
    """
    Family C2 format (e.g., EB vs Cranford dual-meet style):
    - Event headers: "Event n  ..."
    - Individual rows:
      "EBSP 10Cui, Paige1 1:23.23   6"
      "EBSP 10Agustin, Cole--- X1:34.33"
      "EBSP 10Buster, Priya--- XDQ DQ"
    - Relay rows:
      "AEBSP1 1:54.10   4"
      "BEBSP--- X2:09.84"
      "BEBSP--- DQ 2:17.00  2"
    """
    ctx = ParseContext(family="C2")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    individual_pattern = re.compile(
        r"^(?P<team>\S+)\s+(?P<age>\d{1,2})(?P<name>.+?)(?P<place>\*?\d+|---)\s+(?P<rest>.+)$"
    )
    relay_result_pattern = re.compile(
        r"^(?P<letter>[A-E])(?P<team>\S+?)(?P<place>\*?\d+|---)\s+(?P<rest>.+)$"
    )
    relay_swimmer_pattern = re.compile(r"([1-4])\)\s*(.+?)\s+(\d+)(?=\s+[1-4]\)|$)")

    def parse_result_tokens(rest: str) -> tuple[str, str, str]:
        parts = rest.split()
        if not parts:
            return "", "", ""
        first = parts[0]
        second = parts[1] if len(parts) > 1 else ""
        exhibition = first.startswith(("X", "x"))
        core_first = first[1:] if exhibition else first

        status = ""
        final_time = ""
        notes = ""

        if core_first in STATUS_VALUES:
            status = core_first
        elif re.match(r"^\d+:\d{2}\.\d{2}$|^\d{1,2}\.\d{2}$", core_first):
            final_time = core_first

        if not status and second in STATUS_VALUES:
            status = second
            final_time = ""

        if exhibition:
            notes = "Exhibition swim"

        return status, final_time, notes

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        event_match = re.match(r"^Event\s+\d+\s+(.*)$", line)
        if event_match:
            flush_pending_relay()
            current_event = event_match.group(1).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or line.startswith("Age   TeamName Finals Time")
            or line.startswith("RelayTeam Finals Time")
            or line.startswith("(Event ")
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
            or line.startswith("Licensed To:")
            or re.match(r"^\d+\.\s", line)
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_match = relay_result_pattern.match(line)
            if relay_match:
                flush_pending_relay()
                letter = relay_match.group("letter")
                team = relay_match.group("team").strip()
                place = relay_match.group("place").strip()
                rest = relay_match.group("rest").strip()
                status, final_time, notes = parse_result_tokens(rest)

                if status:
                    rank = status
                    final_time = ""
                elif place == "---":
                    rank = "X"
                else:
                    rank = format_rank(place.lstrip("*"))

                pending_relay = {
                    "team_name": f"{team} {letter}",
                    "team": team,
                    "rank": rank,
                    "time": final_time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                i += 1
                continue

            if pending_relay and re.search(r"[1-4]\)", line):
                fixed_line = normalize_relay_swimmer_line_family_b(line)
                swimmers_found: list[tuple[int, str]] = []
                for sm in relay_swimmer_pattern.finditer(fixed_line):
                    idx = int(sm.group(1))
                    swimmers_found.append((idx, f"{convert_name(sm.group(2))} {sm.group(3)}"))
                if swimmers_found:
                    swimmers_found.sort(key=lambda pair: pair[0])
                    relay_swimmers.extend([name for _, name in swimmers_found])
                i += 1
                continue

            i += 1
            continue

        individual_match = individual_pattern.match(line)
        if individual_match:
            team = individual_match.group("team").strip()
            age = individual_match.group("age").strip()
            name = convert_name(individual_match.group("name").strip())
            place = individual_match.group("place").strip()
            rest = individual_match.group("rest").strip()
            status, final_time, notes = parse_result_tokens(rest)

            if status:
                rank = status
                final_time = ""
            elif place == "---":
                rank = "X"
            else:
                rank = format_rank(place.lstrip("*"))

            if rank in STATUS_VALUES and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (
                    next_line
                    and not next_line.startswith("Event ")
                    and not next_line.startswith("(Event ")
                    and not individual_pattern.match(next_line)
                    and any(
                        key in next_line
                        for key in (
                            "Infraction",
                            "Did not",
                            "kick",
                            "False start",
                            "Alternating",
                            "Stroke",
                            "Standing",
                            "One hand",
                            "Shoulders",
                        )
                    )
                ):
                    notes = f"{notes} | {next_line}".strip(" |") if notes else next_line

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": name,
                    "Age": age,
                    "Rank": rank,
                    "Time": final_time,
                    "Team": team,
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()
        i += 1

    flush_pending_relay()
    return ctx


def parse_family_d1(lines: list[str]) -> ParseContext:
    """
    Family D1 format (e.g., 2024 Holiday Mini Meet, GSCY 8 & Under Championships):
    - Event headers: "Event n  ..."
    - Individual rows with seed-time/points tails:
      TEAM 10Last, First 1:23.93  1:27.941
      TEAM  9Last, First DQ  NT---
    - Relay rows:
      ALakeland Hills YMCA-NJ 1:28.28  1:28.931
      ASummit Area YMCA-NJ DQ 1:32.15  1:28.20---
    """
    ctx = ParseContext(family="D1")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    # Parse from right to avoid greedy name/team ambiguity.
    seed_with_optional_points = r"(?:\d+)?(?:NT|\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})"
    medal_token = r"(?:GOLD|SILV|BRON)"
    tail_pattern = re.compile(
        rf"^(?P<prefix>.+?)\s+(?P<result>\d+:\d{{2}}\.\d{{2}}|\d{{1,2}}\.\d{{2}}|DQ|DNF|DNS|NS|DW|SCR|DSQ)(?:\s+{medal_token})?\s+(?P<seed>{seed_with_optional_points})\s*(?P<place>\*?\d+|---)$"
    )
    prefix_pattern = re.compile(r"^(?P<team>.+?)\s+(?P<age>\d{1,2})(?P<name>.+)$")
    relay_normal_pattern = re.compile(
        rf"^([A-E])(.+?)\s+(\d+:\d{{2}}\.\d{{2}}|\d{{1,2}}\.\d{{2}})\s+({seed_with_optional_points})(\*?\d+|---)$"
    )
    relay_status_with_time_pattern = re.compile(
        rf"^([A-E])(.+?)\s+(DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+(\d+:\d{{2}}\.\d{{2}}|\d{{1,2}}\.\d{{2}})\s+({seed_with_optional_points})(\*?\d+|---)$"
    )
    relay_status_no_time_pattern = re.compile(
        rf"^([A-E])(.+?)\s+(DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+({seed_with_optional_points})(\*?\d+|---)$"
    )
    relay_swimmer_pattern = re.compile(r"([1-4])\)\s*(.+?)\s+(\d+)(?=\s+[1-4]\)|$)")

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Some D1 exports glue medal tags to finals time (e.g. "1:22.01GOLD").
        line = re.sub(r"(\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})(GOLD|SILV|BRON)\b", r"\1 \2", line)
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        event_match = re.match(r"^Event\s+\d+\s+(.*)$", line)
        if event_match:
            flush_pending_relay()
            current_event = event_match.group(1).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or line.startswith("AgeName Team Finals TimeSeed Time")
            or line.startswith("Team Relay Finals TimeSeed Time")
            or line.startswith("(Event ")
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
            or re.match(r"^\d+\.\s", line)
            or re.match(r"^(?:DQ|DNF|DNS|NS|DW|SCR|DSQ|\d{1,2}:\d{2}\.\d{2})\s*\(", line)
            or re.match(r"^\d{1,2}:\d{2}\.\d{2}\s+\(", line)
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_parsed = False

            m = relay_status_with_time_pattern.match(line)
            if m:
                flush_pending_relay()
                letter, team, status, _status_time, _seed, place = m.groups()
                rank = status
                notes = ""
                time = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and any(
                        key in next_line
                        for key in (
                            "Infraction",
                            "Did not",
                            "kick",
                            "False start",
                            "Alternating",
                            "Stroke",
                            "Early",
                        )
                    ):
                        notes = next_line
                if place == "---" and status not in STATUS_VALUES:
                    rank = "X"
                    notes = "Exhibition swim"
                pending_relay = {
                    "team_name": f"{team.strip()} {letter}",
                    "team": team.strip(),
                    "rank": rank,
                    "time": time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                relay_parsed = True

            if not relay_parsed:
                m = relay_status_no_time_pattern.match(line)
                if m:
                    flush_pending_relay()
                    letter, team, status, _seed, place = m.groups()
                    rank = status
                    notes = ""
                    time = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and any(
                            key in next_line
                            for key in (
                                "Infraction",
                                "Did not",
                                "kick",
                                "False start",
                                "Alternating",
                                "Stroke",
                                "Early",
                            )
                        ):
                            notes = next_line
                    if place == "---" and status not in STATUS_VALUES:
                        rank = "X"
                        notes = "Exhibition swim"
                    pending_relay = {
                        "team_name": f"{team.strip()} {letter}",
                        "team": team.strip(),
                        "rank": rank,
                        "time": time,
                        "notes": notes,
                        "event_type": current_event,
                    }
                    relay_swimmers = []
                    relay_parsed = True

            if not relay_parsed:
                m = relay_normal_pattern.match(line)
                if m:
                    flush_pending_relay()
                    letter, team, final_time, _seed, place = m.groups()
                    rank = "X" if place == "---" else format_rank(place.lstrip("*"))
                    notes = "Exhibition swim" if place == "---" else ""
                    pending_relay = {
                        "team_name": f"{team.strip()} {letter}",
                        "team": team.strip(),
                        "rank": rank,
                        "time": final_time,
                        "notes": notes,
                        "event_type": current_event,
                    }
                    relay_swimmers = []
                    relay_parsed = True

            if relay_parsed:
                i += 1
                continue

            if pending_relay and re.search(r"[1-4]\)", line):
                fixed_line = normalize_relay_swimmer_line_family_b(line)
                swimmers_found: list[tuple[int, str]] = []
                for sm in relay_swimmer_pattern.finditer(fixed_line):
                    idx = int(sm.group(1))
                    swimmers_found.append((idx, f"{convert_name(sm.group(2))} {sm.group(3)}"))
                if swimmers_found:
                    swimmers_found.sort(key=lambda pair: pair[0])
                    relay_swimmers.extend([name for _, name in swimmers_found])
                i += 1
                continue

            i += 1
            continue

        tail = tail_pattern.match(line)
        if not tail:
            i += 1
            continue

        prefix = tail.group("prefix").strip()
        result = tail.group("result").strip()
        place = tail.group("place").strip()

        prefix_match = prefix_pattern.match(prefix)
        if not prefix_match:
            i += 1
            continue

        team = prefix_match.group("team").strip()
        age = prefix_match.group("age").strip()
        name = convert_name(prefix_match.group("name"))

        rank = ""
        notes = ""
        final_time = result

        if result in STATUS_VALUES:
            rank = result
            final_time = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (
                    next_line
                    and not next_line.startswith("Event ")
                    and not next_line.startswith("(Event ")
                    and not tail_pattern.match(next_line)
                    and any(
                        key in next_line
                        for key in (
                            "Infraction",
                            "Did not",
                            "kick",
                            "False start",
                            "Alternating",
                            "Stroke",
                            "Standing",
                            "One hand",
                            "Shoulders",
                        )
                    )
                ):
                    notes = next_line
        elif place == "---":
            rank = "X"
            notes = "Exhibition swim"
        else:
            rank = format_rank(place.lstrip("*"))

        ctx.rows.append(
            {
                "Meet_Name": ctx.meet_name,
                "Meet_Date": ctx.meet_date,
                "Name": name.strip(),
                "Age": age,
                "Rank": rank,
                "Time": final_time,
                "Team": team,
                "Notes": notes,
                "Event_Type": current_event,
            }
        )
        ctx.mark_event_has_row()
        i += 1

    flush_pending_relay()
    return ctx


def parse_family_d2(lines: list[str]) -> ParseContext:
    """
    Family D2 format (e.g., 2025 HCY Stingray Splash):
    - Event headers: "Event n ..."
    - Individual rows:
      TEAM 101 Abd, Leah 2:40.81  2:40.05
      TEAM 10--- Zaninovic, Ian DQ 3:17.62  3:20.55
    - Relay rows:
      A1 Team Name 1:23.17  1:19.57
      B3 Team Name x1:43.84  1:34.83
      A--- Team Name DQ 2:23.33  2:22.36
    """
    ctx = ParseContext(family="D2")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    individual_pattern = re.compile(
        r"^(?P<team>.+?)\s+(?P<token>\d{1,2}(?:\*?\d+|---))\s+(?P<name>.+?)\s+(?P<result>[xX]?(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ))(?:\s+(?P<status_time>\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}))?\s+(?P<seed>NT|\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})$"
    )
    relay_result_pattern = re.compile(
        r"^(?P<letter>[A-E])(?P<place>\*?\d+|---)\s+(?P<team>.+?)\s+(?P<result>[xX]?(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ))(?:\s+(?P<status_time>\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}))?\s+(?P<seed>NT|\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})$"
    )
    relay_swimmer_pattern = re.compile(r"([1-4])\)\s*(.+?)\s+(\d+)(?=\s+[1-4]\)|$)")

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        event_match = re.match(r"^Event\s+\d+\s+(.*)$", line)
        if event_match:
            flush_pending_relay()
            current_event = event_match.group(1).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or line.startswith("AgeName Team Finals TimeSeed Time")
            or line.startswith("(Event ")
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
            or re.match(r"^\d+\.\s", line)
            # split/lap lines
            or re.match(r"^(?:DQ|DNF|DNS|NS|DW|SCR|DSQ|\d{1,2}:\d{2}\.\d{2})\s*\(", line)
            or re.match(r"^\d{1,2}:\d{2}\.\d{2}\s+\(", line)
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_match = relay_result_pattern.match(line)
            if relay_match:
                flush_pending_relay()
                letter = relay_match.group("letter")
                place = relay_match.group("place").strip()
                team = relay_match.group("team").strip()
                result_raw = relay_match.group("result").strip()
                exhibition = result_raw.startswith(("x", "X"))
                result = result_raw[1:] if exhibition else result_raw

                rank = ""
                notes = ""
                final_time = result

                if result in STATUS_VALUES:
                    rank = result
                    final_time = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if (
                            next_line
                            and not next_line.startswith("Event ")
                            and not next_line.startswith("(Event ")
                            and not relay_result_pattern.match(next_line)
                            and any(
                                key in next_line
                                for key in (
                                    "Infraction",
                                    "Did not",
                                    "kick",
                                    "False start",
                                    "Alternating",
                                    "Stroke",
                                    "Standing",
                                    "One hand",
                                    "Shoulders",
                                    "Early",
                                )
                            )
                        ):
                            notes = next_line
                elif exhibition or place == "---":
                    rank = "X"
                    notes = "Exhibition swim"
                else:
                    rank = format_rank(place.lstrip("*"))

                if exhibition and notes:
                    notes = f"Exhibition swim | {notes}"
                elif exhibition:
                    notes = "Exhibition swim"

                pending_relay = {
                    "team_name": f"{team} {letter}",
                    "team": team,
                    "rank": rank,
                    "time": final_time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                i += 1
                continue

            if pending_relay and re.search(r"[1-4]\)", line):
                fixed_line = normalize_relay_swimmer_line_family_b(line)
                swimmers_found: list[tuple[int, str]] = []
                for sm in relay_swimmer_pattern.finditer(fixed_line):
                    idx = int(sm.group(1))
                    swimmers_found.append((idx, f"{convert_name(sm.group(2))} {sm.group(3)}"))
                if swimmers_found:
                    swimmers_found.sort(key=lambda pair: pair[0])
                    relay_swimmers.extend([name for _, name in swimmers_found])
                i += 1
                continue

            i += 1
            continue

        m = individual_pattern.match(line)
        if not m:
            i += 1
            continue

        team = m.group("team").strip()
        token = m.group("token").strip()
        name = convert_name(m.group("name"))
        result_raw = m.group("result").strip()
        exhibition = result_raw.startswith(("x", "X"))
        result = result_raw[1:] if exhibition else result_raw

        age, place = split_age_place_token(token, current_event)
        rank = ""
        notes = ""
        final_time = result

        if result in STATUS_VALUES:
            rank = result
            final_time = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (
                    next_line
                    and not next_line.startswith("Event ")
                    and not next_line.startswith("(Event ")
                    and not individual_pattern.match(next_line)
                    and any(
                        key in next_line
                        for key in (
                            "Infraction",
                            "Did not",
                            "kick",
                            "False start",
                            "Alternating",
                            "Stroke",
                            "Standing",
                            "One hand",
                            "Shoulders",
                        )
                    )
                ):
                    notes = next_line
        elif exhibition or place == "---":
            rank = "X"
            notes = "Exhibition swim"
        else:
            rank = format_rank(place.lstrip("*"))

        ctx.rows.append(
            {
                "Meet_Name": ctx.meet_name,
                "Meet_Date": ctx.meet_date,
                "Name": name.strip(),
                "Age": age,
                "Rank": rank,
                "Time": final_time,
                "Team": team,
                "Notes": notes,
                "Event_Type": current_event,
            }
        )
        ctx.mark_event_has_row()
        i += 1

    flush_pending_relay()
    return ctx


def parse_family_e(lines: list[str]) -> ParseContext:
    """
    Family E format (e.g., NJRC TYR New Years Splash):
    - Event headers: "Event n ..."
    - Relay rows:
      "BNew Jersey Race Club-NJ 2:27.97  1"
      "BLakeland Hills YMCA-NJ DQ  ---"
    - Individual rows:
      "New Jersey Race Club-NJ 10Jones, Kaya A 1:14.87  3"
      "Lakeland Hills YMCA-NJ 10Bennington, Adelyn M DQ  ---"
    """
    ctx = ParseContext(family="E")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    relay_result_pattern = re.compile(
        r"^([A-E])(.+?)\s+(\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+(\*?\d+|---)$"
    )
    relay_swimmer_pattern = re.compile(r"([1-4])\)\s*(.+?)\s+(\d+)(?=\s+[1-4]\)|$)")
    individual_pattern = re.compile(
        r"^(?P<team>.+?)\s+(?P<age>\d{1,2})(?P<name>.+?)\s+(?P<result>\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+(?P<place>\*?\d+|---)$"
    )

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        event_match = re.match(r"^Event\s+\d+\s+(.*)$", line)
        if event_match:
            flush_pending_relay()
            current_event = event_match.group(1).strip()
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or line.startswith("AgeName Team Finals Time")
            or "Team Relay Finals Time" in line
            or line.startswith("(Event ")
            or line.startswith("Combined Team Scores")
            or "Through Event" in line
            or re.match(r"^\d+\.\s", line)
            # split/lap lines like "1:11.98 (37.74)34.24" or "DQ (...)".
            or re.match(r"^(?:DQ|DNF|DNS|NS|DW|SCR|DSQ|\d{1,2}:\d{2}\.\d{2})\s*\(", line)
            or re.match(r"^\d{1,2}:\d{2}\.\d{2}\s+\(", line)
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        if is_relay_event:
            relay_match = relay_result_pattern.match(line)
            if relay_match:
                flush_pending_relay()
                letter, team, result, place = relay_match.groups()
                team = team.strip()
                rank = ""
                notes = ""
                final_time = result

                if result in STATUS_VALUES:
                    rank = result
                    final_time = ""
                elif place == "---":
                    rank = "X"
                    notes = "Exhibition swim"
                else:
                    rank = format_rank(place.lstrip("*"))

                pending_relay = {
                    "team_name": f"{team} {letter}",
                    "team": team,
                    "rank": rank,
                    "time": final_time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                i += 1
                continue

            if pending_relay and re.search(r"[1-4]\)", line):
                fixed_line = normalize_relay_swimmer_line_family_b(line)
                swimmers_found: list[tuple[int, str]] = []
                for sm in relay_swimmer_pattern.finditer(fixed_line):
                    idx = int(sm.group(1))
                    swimmers_found.append((idx, f"{convert_name(sm.group(2))} {sm.group(3)}"))
                if swimmers_found:
                    swimmers_found.sort(key=lambda pair: pair[0])
                    relay_swimmers.extend([name for _, name in swimmers_found])
                i += 1
                continue

            i += 1
            continue

        individual_match = individual_pattern.match(line)
        if individual_match:
            team = individual_match.group("team").strip()
            age = individual_match.group("age").strip()
            name = convert_name(individual_match.group("name"))
            result = individual_match.group("result").strip()
            place = individual_match.group("place").strip()

            rank = ""
            notes = ""
            final_time = result

            if result in STATUS_VALUES:
                rank = result
                final_time = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith("Event ")
                        and not next_line.startswith("(Event ")
                        and not individual_pattern.match(next_line)
                        and any(
                            key in next_line
                            for key in (
                                "Infraction",
                                "Did not",
                                "kick",
                                "False start",
                                "Alternating",
                                "Stroke",
                                "Standing",
                                "One hand",
                                "Shoulders",
                            )
                        )
                    ):
                        notes = next_line
            elif place == "---":
                rank = "X"
                notes = "Exhibition swim"
            else:
                rank = format_rank(place.lstrip("*"))

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": name.strip(),
                    "Age": age,
                    "Rank": rank,
                    "Time": final_time,
                    "Team": team,
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()
        i += 1

    flush_pending_relay()
    return ctx


def parse_family_f(lines: list[str]) -> ParseContext:
    """
    Family F format (e.g., Team Manager "Individual Meet Results"):
    - Event headers: "Event #  1   Female 100 IM 10 & Under"
    - Meet line: "EB @ Somerset Hills  21-Jun-25 [Ageup: 6/30/2025] Yards"
    - Individual rows:
      "6 -4.211101:21.39Y F Paige Cui"
      "--- ---      ---13NS F Nathan Pathak"
      "--- ---      ---7    44.57YDQ F Isla Mather"
    """
    ctx = ParseContext(family="F")
    current_event = ""
    current_team = ""

    event_pattern = re.compile(r"^Event\s*#\s*\d+\s+(.*)$")
    team_pattern = re.compile(r"^(.*?)\s+\[([A-Za-z0-9\-]+)\]$")
    result_time_pattern = re.compile(
        r"^(?P<points>\d+|---)\s+(?P<improv>-?\d+\.\d+|---)\s*(?P<place>\d+|---)(?P<age>\d{1,2})\s*(?P<time>\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})Y(?P<status>DQ)?\s+F\s+(?P<name>.+)$"
    )
    result_status_pattern = re.compile(
        r"^(?P<points>\d+|---)\s+(?P<improv>-?\d+\.\d+|---)\s*(?P<place>\d+|---)(?P<age>\d{1,2})\s*(?P<status>DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+F\s+(?P<name>.+)$"
    )
    status_note_pattern = re.compile(r"^\d+[A-Z]\s+.+$")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not ctx.meet_name:
            parsed = parse_meet_line(line) or parse_team_manager_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                i += 1
                continue

        team_match = team_pattern.match(line)
        if team_match:
            current_team = team_match.group(1).strip()
            i += 1
            continue

        event_match = event_pattern.match(line)
        if event_match:
            current_event = re.sub(r"\s+", " ", event_match.group(1)).strip()
            ctx.open_event(current_event)
            i += 1
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Licensed To:")
            or line.startswith("Individual  Meet  Results")
            or line.startswith("Location:")
            or line.startswith("Time PointsPlaceF/P/S Name Age Improv")
        ):
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        m = result_time_pattern.match(line)
        if m:
            place = m.group("place").strip()
            age = m.group("age").strip()
            status = (m.group("status") or "").strip()
            raw_time = m.group("time").strip()
            name = convert_name(m.group("name").strip())

            rank = ""
            notes = ""
            time = raw_time

            if status in STATUS_VALUES:
                rank = status
                time = ""
            elif place != "---":
                rank = format_rank(place)

            if rank in STATUS_VALUES and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if status_note_pattern.match(next_line):
                    notes = next_line

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": name,
                    "Age": age,
                    "Rank": rank,
                    "Time": time,
                    "Team": current_team,
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()
            i += 1
            continue

        m = result_status_pattern.match(line)
        if m:
            place = m.group("place").strip()
            age = m.group("age").strip()
            status = m.group("status").strip()
            name = convert_name(m.group("name").strip())

            rank = status if status in STATUS_VALUES else ""
            notes = ""
            if rank in STATUS_VALUES and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if status_note_pattern.match(next_line):
                    notes = next_line
            elif place != "---":
                rank = format_rank(place)

            ctx.rows.append(
                {
                    "Meet_Name": ctx.meet_name,
                    "Meet_Date": ctx.meet_date,
                    "Name": name,
                    "Age": age,
                    "Rank": rank,
                    "Time": "",
                    "Team": current_team,
                    "Notes": notes,
                    "Event_Type": current_event,
                }
            )
            ctx.mark_event_has_row()
            i += 1
            continue

        i += 1

    return ctx


def parse_family_g(lines: list[str]) -> ParseContext:
    """
    Family G format (e.g., Be Smartt Snowflake):
    - Event headers are plain titles (no "Event n"), e.g.:
      "Girls 10 & Under 50 Yard Freestyle"
    - Individual rows:
      "TEAM 10Last, First 33.04 SIL V  32.831"
      "TEAM  8Name NS  49.87---"
    - Relay rows:
      "ARaritan Valley YMCA Riptide 2:01.06  2:04.511"
      "BBergen Barracudas Swim Tea SCR  2:14.57---"
    """
    ctx = ParseContext(family="G")
    current_event = ""
    is_relay_event = False
    pending_relay: dict[str, str] | None = None
    relay_swimmers: list[str] = []

    event_title_pattern = re.compile(r"^(Girls|Boys|Women|Men)\s+.+\s+Yard\s+.+$")
    individual_left_pattern = re.compile(
        r"^(?P<team>.+?)\s+(?P<age>\d{1,2})(?P<name>.+?)\s+"
        r"(?P<result>[xX]?(?:\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2}|DQ|DNF|DNS|NS|DW|SCR|DSQ))"
        r"(?:\s+(?P<extra>.+))?$"
    )
    relay_left_pattern = re.compile(
        r"^(?P<letter>[A-E])(?P<team>.+?)\s+(?P<result>\S+)(?:\s+(?P<extra>.+))?$"
    )

    def normalize_line(s: str) -> str:
        x = re.sub(r"\s+", " ", s.strip())
        x = re.sub(r"([1-4])\s+\)", r"\1)", x)
        x = re.sub(r"(?<!\s)([1-4]\))", r" \1", x)
        x = re.sub(r"([A-Za-z])S CR\b", r"\1 SCR", x)
        x = re.sub(r"([A-Za-z])N S\b", r"\1 NS", x)
        x = re.sub(r"(\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})(GOLD|SILV|BRON)\b", r"\1 \2", x)
        return x

    def extract_swimmers(line: str) -> list[str]:
        fixed = normalize_line(line)
        marker_iter = list(re.finditer(r"([1-4])\)\s*", fixed))
        if not marker_iter:
            return []
        swimmers: list[tuple[int, str]] = []
        for idx, m in enumerate(marker_iter):
            start = m.end()
            end = marker_iter[idx + 1].start() if idx + 1 < len(marker_iter) else len(fixed)
            payload = fixed[start:end].strip()
            if not payload:
                continue
            age = ""
            am = re.search(r"\s+(\d+)\s*$", payload)
            if am:
                age = am.group(1)
                payload = payload[: am.start()].strip()
            name = convert_name(payload)
            swimmer = f"{name} {age}".strip()
            swimmers.append((int(m.group(1)), swimmer))
        swimmers.sort(key=lambda pair: pair[0])
        return [name for _, name in swimmers]

    def split_seed_place(token: str) -> tuple[str, str] | None:
        t = token.strip()
        if not t:
            return None
        if t.endswith("---"):
            return t[:-3].strip(), "---"
        for n in (3, 2, 1):
            if len(t) <= n:
                continue
            seed = t[:-n]
            place = t[-n:]
            if not place.isdigit():
                continue
            if re.match(r"^(NT|\d+:\d{2}\.\d{2}|\d{1,2}\.\d{2})$", seed):
                return seed, place
        return None

    def parse_result_token(token: str) -> tuple[str, str, str]:
        raw = token.strip()
        exhibition = raw.startswith(("x", "X"))
        core = raw[1:] if exhibition else raw
        if core in STATUS_VALUES:
            return core, "", "Exhibition swim" if exhibition else ""
        if re.match(r"^\d+:\d{2}\.\d{2}$|^\d{1,2}\.\d{2}$", core):
            return "", core, "Exhibition swim" if exhibition else ""
        return "", "", "Exhibition swim" if exhibition else ""

    def flush_pending_relay() -> None:
        nonlocal pending_relay, relay_swimmers
        if not pending_relay:
            return
        notes = pending_relay.get("notes", "")
        if relay_swimmers:
            swimmer_names = " | ".join(relay_swimmers)
            notes = f"Swimmers: {swimmer_names}" + (f" | {notes}" if notes else "")
        row = {
            "Meet_Name": ctx.meet_name,
            "Meet_Date": ctx.meet_date,
            "Name": pending_relay["team_name"],
            "Age": "",
            "Rank": pending_relay["rank"],
            "Time": pending_relay["time"],
            "Team": pending_relay["team"],
            "Notes": notes,
            "Event_Type": pending_relay["event_type"],
        }
        ctx.rows.append(row)
        ctx.mark_event_has_row()
        pending_relay = None
        relay_swimmers = []

    for raw_line in lines:
        line = normalize_line(raw_line)
        if not line:
            continue

        if not ctx.meet_name:
            parsed = parse_besmartt_meet_line(line)
            if parsed:
                ctx.meet_name, ctx.meet_date = parsed
                continue

        if line.startswith("(") and line.endswith(")"):
            inner = line[1:-1].strip()
            if event_title_pattern.match(inner):
                # Continuation page header for current event.
                continue

        if event_title_pattern.match(line):
            flush_pending_relay()
            current_event = line
            is_relay_event = "Relay" in current_event
            ctx.open_event(current_event)
            continue

        if (
            "HY-TEK" in line
            or "HY - TEK" in line
            or line.startswith("Results")
            or line.startswith("AgeName Team Finals")
            or line.startswith("Team Rela")
            or line.startswith("www.besmarttinc.com")
            or line.startswith("Follow Be Smartt")
            or line.startswith("Be Smartt Inc.")
            or line.startswith("Combined Team Scores")
            or line.startswith("10&U ")
            or line.startswith("11-12 ")
            or line.startswith("13-14 ")
            or line.startswith("15-19 ")
            or re.match(r"^\d+:\d{2}\.\d{2}\s*\(", line)
            or re.match(r"^(?:DQ|DNF|DNS|NS|DW|SCR|DSQ)\s+\d+:\d{2}\.\d{2}\s*\(", line)
        ):
            continue

        if not current_event:
            continue

        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            if pending_relay and re.search(r"[1-4]\)", line):
                swimmers_found = extract_swimmers(line)
                if swimmers_found:
                    relay_swimmers.extend(swimmers_found)
            continue

        left, seed_place_token = parts
        split = split_seed_place(seed_place_token)
        if not split:
            if pending_relay and re.search(r"[1-4]\)", line):
                swimmers_found = extract_swimmers(line)
                if swimmers_found:
                    relay_swimmers.extend(swimmers_found)
            continue
        _seed, place = split

        if is_relay_event:
            relay_match = relay_left_pattern.match(left)
            if relay_match:
                flush_pending_relay()
                letter = relay_match.group("letter")
                team = relay_match.group("team").strip()
                result_token = relay_match.group("result").strip()
                extra = (relay_match.group("extra") or "").strip()

                status, final_time, notes = parse_result_token(result_token)
                if status:
                    rank = status
                    final_time = ""
                elif place == "---":
                    rank = "X"
                    notes = notes or "Exhibition swim"
                else:
                    rank = format_rank(place.lstrip("*"))

                if extra:
                    if any(
                        k in extra
                        for k in ("Early", "Infraction", "Stroke", "False", "kick", "Did not")
                    ):
                        notes = f"{notes} | {extra}".strip(" |") if notes else extra

                pending_relay = {
                    "team_name": f"{team} {letter}",
                    "team": team,
                    "rank": rank,
                    "time": final_time,
                    "notes": notes,
                    "event_type": current_event,
                }
                relay_swimmers = []
                continue

            if pending_relay and re.search(r"[1-4]\)", line):
                swimmers_found = extract_swimmers(line)
                if swimmers_found:
                    relay_swimmers.extend(swimmers_found)
            continue

        m = individual_left_pattern.match(left)
        if not m:
            continue
        team = m.group("team").strip()
        age = m.group("age").strip()
        name = convert_name(m.group("name").strip())
        result_token = m.group("result").strip()
        extra = (m.group("extra") or "").strip()

        status, final_time, notes = parse_result_token(result_token)
        if status:
            rank = status
            final_time = ""
        elif place == "---":
            rank = "X"
            notes = notes or "Exhibition swim"
        else:
            rank = format_rank(place.lstrip("*"))

        if extra and any(
            k in extra for k in ("Early", "Infraction", "Stroke", "False", "kick", "Did not")
        ):
            notes = f"{notes} | {extra}".strip(" |") if notes else extra

        ctx.rows.append(
            {
                "Meet_Name": ctx.meet_name,
                "Meet_Date": ctx.meet_date,
                "Name": name,
                "Age": age,
                "Rank": rank,
                "Time": final_time,
                "Team": team,
                "Notes": notes,
                "Event_Type": current_event,
            }
        )
        ctx.mark_event_has_row()

    flush_pending_relay()
    return ctx


def dedup_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    unique_rows: list[dict[str, str]] = []
    for row in rows:
        key = (
            row["Meet_Name"],
            row["Meet_Date"],
            row["Name"],
            row["Age"],
            row["Rank"],
            row["Time"],
            row["Event_Type"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def count_swimmers_in_notes(notes: str) -> int:
    if not notes.startswith("Swimmers: "):
        return 0
    payload = notes[len("Swimmers: ") :]
    if not payload:
        return 0
    chunks = [chunk.strip() for chunk in payload.split(" | ") if chunk.strip()]
    return sum(1 for chunk in chunks if re.match(r".+\s\d+$", chunk))


def validate(ctx: ParseContext, mode: str = "strict") -> ValidationResult:
    rows = dedup_rows(ctx.rows)
    ctx.rows = rows

    errors = list(ctx.errors)
    warnings = list(ctx.warnings)

    if not ctx.meet_name or not ctx.meet_date:
        errors.append("Structural gate failed: meet name/date not found")
    if not ctx.event_headers:
        errors.append("Structural gate failed: no event headers detected")
    if not rows:
        errors.append("Structural gate failed: no parsed rows")

    detected_events = len(ctx.event_headers)
    events_with_rows = sum(1 for has_rows in ctx.event_has_rows if has_rows)
    if detected_events != events_with_rows:
        errors.append(
            f"Event reconciliation failed: detected={detected_events}, with_rows={events_with_rows}"
        )

    for idx, has_rows in enumerate(ctx.event_has_rows):
        if not has_rows:
            errors.append(
                "Event reconciliation failed: "
                f"no rows for event #{idx + 1}: {ctx.event_headers[idx]}"
            )

    required_fields = ("Meet_Name", "Meet_Date", "Name", "Team", "Event_Type")
    for row_idx, row in enumerate(rows, start=1):
        for field_name in required_fields:
            if not (row.get(field_name) or "").strip():
                errors.append(
                    f"Content sanity failed: empty required field {field_name} at row {row_idx}"
                )
        if "Relay" not in row["Event_Type"] and not row["Age"].strip():
            errors.append(f"Content sanity failed: missing age for individual row {row_idx}")

    relay_rows = [row for row in rows if "Relay" in row["Event_Type"]]
    for _row_idx, row in enumerate(relay_rows, start=1):
        notes = row.get("Notes", "")
        if RELAY_MARKER_ARTIFACT_RE.search(notes):
            errors.append(
                "Relay integrity failed: marker artifact in relay notes for "
                f"{row['Event_Type']} / {row['Name']}"
            )

        if row.get("Rank") not in STATUS_VALUES:
            if not notes.startswith("Swimmers: "):
                msg = (
                    f"Relay integrity failed: missing swimmers list for non-status relay row "
                    f"{row['Event_Type']} / {row['Name']}"
                )
                if mode == "lenient":
                    warnings.append(msg.replace("failed", "warning"))
                else:
                    errors.append(msg)
            else:
                swimmers_count = count_swimmers_in_notes(notes)
                if row.get("Rank") == "X" and swimmers_count != 4:
                    warnings.append(
                        "Relay warning: exhibition row has "
                        f"{swimmers_count} swimmers for "
                        f"{row['Event_Type']} / {row['Name']}"
                    )
                elif mode == "strict" and swimmers_count != 4:
                    errors.append(
                        "Relay integrity failed: expected 4 swimmers, "
                        f"got {swimmers_count} for "
                        f"{row['Event_Type']} / {row['Name']}"
                    )
                elif swimmers_count != 4:
                    warnings.append(
                        "Relay warning: expected 4 swimmers, "
                        f"got {swimmers_count} for "
                        f"{row['Event_Type']} / {row['Name']}"
                    )

    stats = {
        "family": ctx.family,
        "meet_name": ctx.meet_name,
        "meet_date": ctx.meet_date,
        "rows_parsed": len(rows),
        "event_headers_detected": detected_events,
        "events_with_rows": events_with_rows,
        "relay_rows": len(relay_rows),
    }
    return ValidationResult(ok=not errors, errors=errors, warnings=warnings, stats=stats)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [{key: row.get(key, "") for key in FIELDS} for row in reader]


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def atomic_write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", newline="", encoding="utf-8", dir=path.parent, delete=False
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def choose_report_path(user_path: str | None, active_csv: Path, pdf_path: Path) -> Path:
    if user_path:
        return Path(user_path)
    return active_csv.parent / f"{pdf_path.stem}_parse_report.json"


def choose_candidate_path(user_path: str | None, active_csv: Path, pdf_path: Path) -> Path:
    if user_path:
        return Path(user_path)
    return active_csv.parent / f"{pdf_path.stem}_candidate.csv"


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf_path)
    active_csv_path = Path(args.active_csv_path)
    backup_csv_path = Path(args.backup_csv_path)
    report_path = choose_report_path(args.report_path, active_csv_path, pdf_path)
    candidate_path = choose_candidate_path(args.candidate_path, active_csv_path, pdf_path)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    backup_csv_path.parent.mkdir(parents=True, exist_ok=True)
    active_csv_path.parent.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        report = {
            "status": "failed",
            "reason": "pdf_not_found",
            "pdf_path": str(pdf_path),
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"ERROR: PDF not found: {pdf_path}")
        print(f"Report written: {report_path}")
        return 1

    # Refresh backup snapshot before parse attempt.
    if active_csv_path.exists():
        shutil.copy2(active_csv_path, backup_csv_path)
    else:
        write_csv_rows(backup_csv_path, [])

    try:
        lines = extract_text_lines(pdf_path)
    except Exception as exc:
        report = {
            "status": "failed",
            "reason": "pdf_read_error",
            "pdf_path": str(pdf_path),
            "error": str(exc),
            "active_csv_path": str(active_csv_path),
            "backup_csv_path": str(backup_csv_path),
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_csv_rows(candidate_path, [])
        print(f"ERROR: Could not read PDF: {pdf_path}")
        print(f"Report written: {report_path}")
        return 1

    family, family_diagnostics = detect_family_with_diagnostics(lines)

    if family == "A":
        ctx = parse_family_a(lines)
    elif family == "B":
        ctx = parse_family_b(lines)
    elif family == "C1":
        ctx = parse_family_c1(lines)
    elif family == "C2":
        ctx = parse_family_c2(lines)
    elif family == "D1":
        ctx = parse_family_d1(lines)
    elif family == "D2":
        ctx = parse_family_d2(lines)
    elif family == "E":
        ctx = parse_family_e(lines)
    elif family == "F":
        ctx = parse_family_f(lines)
    elif family == "G":
        ctx = parse_family_g(lines)
    else:
        ctx = ParseContext(family="unsupported")
        ctx.errors.append("unsupported_format")

    validation = validate(ctx, mode=args.mode)

    candidate_rows = dedup_rows(ctx.rows)
    write_csv_rows(candidate_path, candidate_rows)

    existing_rows = read_csv_rows(active_csv_path)
    before_total_rows = len(existing_rows)
    before_meet_rows = (
        len([r for r in existing_rows if r.get("Meet_Name") == ctx.meet_name])
        if ctx.meet_name
        else 0
    )

    if validation.ok:
        base_rows = [r for r in existing_rows if r.get("Meet_Name") != ctx.meet_name]
        updated_rows = base_rows + candidate_rows
        atomic_write_csv(active_csv_path, updated_rows)
        status = "passed"
        after_total_rows = len(updated_rows)
        after_meet_rows = len(candidate_rows)
    else:
        status = "failed"
        after_total_rows = before_total_rows
        after_meet_rows = before_meet_rows

    report = {
        "status": status,
        "mode": args.mode,
        "pdf_path": str(pdf_path),
        "active_csv_path": str(active_csv_path),
        "backup_csv_path": str(backup_csv_path),
        "candidate_csv_path": str(candidate_path),
        "family_detected": family,
        "family_diagnostics": family_diagnostics,
        "validation": asdict(validation),
        "counts": {
            "before_total_rows": before_total_rows,
            "before_meet_rows": before_meet_rows,
            "candidate_meet_rows": len(candidate_rows),
            "after_total_rows": after_total_rows,
            "after_meet_rows": after_meet_rows,
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Family detected: {family}")
    print(f"Meet: {ctx.meet_name} ({ctx.meet_date})")
    print(f"Candidate rows: {len(candidate_rows)}")
    print(f"Validation status: {status}")
    print(f"Report: {report_path}")
    print(f"Candidate CSV: {candidate_path}")
    if status == "failed":
        for err in validation.errors[:10]:
            print(f"ERROR: {err}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
