"""Bus bunching: planned headway vs actual arrival gaps."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

@dataclass
class GapEvent:
    stop_name: str
    earlier_trip: str
    later_trip: str
    gap_min: float
    planned_headway_min: float
    status: str
    suggestion: str

def classify_gap(gap_min: float, planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> tuple[str, str]:
    if gap_min < bunch_threshold:
        return ("bunching", f"间隔 {gap_min:.1f} 分钟低于串车阈值 {bunch_threshold}，建议后车缓行或抽稀。")
    if gap_min > large_threshold:
        return ("large_gap", f"间隔 {gap_min:.1f} 分钟超过大间隔阈值 {large_threshold}，建议前车减速或加发。")
    return ("normal", f"间隔接近计划 {planned_headway_min:.1f} 分钟，保持即可。")

def apply_holds(arrivals: list[dict], holds: dict[tuple[str, str], float]) -> list[dict]:
    """返回应用扣车后的到站记录副本:扣车分钟右移,原始记录不被修改。

    仅当 (trip_no, stop_name) 有 >0 的扣车登记时才移动;未登记或 0 分与底座一致,
    不产生任何偏移。报告间隔、轴上点位、建议间隔必须共用这一套「扣完后的生效钟点」,
    不允许各自另算。
    """
    out: list[dict] = []
    for a in arrivals:
        item = {**a}
        minutes = float(holds.get((a["trip_no"], a["stop_name"])) or 0.0)
        if minutes > 0:
            item["actual_arrive"] = a["actual_arrive"] + timedelta(minutes=minutes)
        out.append(item)
    return out

def detect_bunching(arrivals: list[dict], planned_headway_min: float, bunch_threshold: float, large_threshold: float) -> list[GapEvent]:
    by_stop: dict[str, list[dict]] = {}
    for a in arrivals:
        by_stop.setdefault(a["stop_name"], []).append(a)
    events: list[GapEvent] = []
    for stop, items in by_stop.items():
        items = sorted(items, key=lambda x: x["actual_arrive"])
        for i in range(1, len(items)):
            prev, cur = items[i - 1], items[i]
            gap_min = (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0
            status, suggestion = classify_gap(gap_min, planned_headway_min, bunch_threshold, large_threshold)
            events.append(GapEvent(stop, prev["trip_no"], cur["trip_no"], round(gap_min, 2), planned_headway_min, status, suggestion))
    return events

def events_to_dicts(events: list[GapEvent]) -> list[dict]:
    return [asdict(e) for e in events]

# topic helpers for report assembly

def raw_gap_minutes(prev: dict, cur: dict) -> float:
    return (cur["actual_arrive"] - prev["actual_arrive"]).total_seconds() / 60.0

def hold_display_minutes(holds: dict, trip_no: str, stop_name: str) -> float:
    return float(holds.get((trip_no, stop_name)) or 0.0)

