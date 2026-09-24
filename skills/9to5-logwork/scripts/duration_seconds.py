#!/usr/bin/env python3
"""Normalize worklog duration (8, 1.5h, 1h30m, 90m) to integral seconds."""
import argparse
from decimal import Decimal
import re


def duration_seconds(value: str) -> int:
    text = value.strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        text += "h"
    match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?\s*(?:(\d+(?:\.\d+)?)m)?", text)
    if not match or not any(match.groups()):
        raise ValueError("use hours or minutes, e.g. 8, 1.5h, 1h30m, 90m")
    hours, minutes = (Decimal(part or "0") for part in match.groups())
    seconds = hours * 3600 + minutes * 60
    if seconds <= 0 or seconds != seconds.to_integral_value():
        raise ValueError("duration must be positive and resolve to whole seconds")
    return int(seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration")
    args = parser.parse_args()
    try:
        print(duration_seconds(args.duration))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
