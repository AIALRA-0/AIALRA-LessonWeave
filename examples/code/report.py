import csv
import math


def readings(path):
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"station", "value", "unit"}.issubset(reader.fieldnames or []):
            raise ValueError("missing headers")
        for row in reader:
            station = row["station"].strip()
            unit = row["unit"].strip().upper()
            value = float(row["value"])
            if not station or not math.isfinite(value) or unit not in {"C", "F"}:
                raise ValueError("invalid reading")
            yield station, value if unit == "C" else (value - 32) * 5 / 9


def means(rows):
    groups = {}
    for station, value in rows:
        groups.setdefault(station, []).append(value)
    return [(station, sum(values) / len(values)) for station, values in sorted(groups.items())]
