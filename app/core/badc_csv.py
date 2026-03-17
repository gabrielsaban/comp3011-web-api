from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path


def file_looks_like_html(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            head = "\n".join(handle.readline() for _ in range(12)).lower()
    except OSError:
        return False
    return "<!doctype html>" in head or "<html" in head or "/account/signin" in head


def is_badc_csv(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                candidate = line.strip()
                if not candidate:
                    continue
                return candidate == "Conventions,G,BADC-CSV,1"
    except OSError:
        return False
    return False


def parse_badc_metadata(path: Path) -> dict[str, list[str]]:
    metadata: dict[str, list[str]] = defaultdict(list)
    with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            key = row[0].strip()
            if key == "data":
                break
            if len(row) >= 3:
                metadata[key].append(row[2].strip())
    return dict(metadata)


def iter_badc_data_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        header: list[str] | None = None
        in_data_block = False

        for row in reader:
            if not row:
                continue

            token = row[0].strip()
            if token == "data":
                header = [column.strip() for column in next(reader)]
                in_data_block = True
                continue

            if token == "end data":
                break

            if in_data_block and header is not None:
                values = row[: len(header)]
                if len(values) < len(header):
                    values = values + [""] * (len(header) - len(values))
                yield {header[idx]: values[idx].strip() for idx in range(len(header))}
