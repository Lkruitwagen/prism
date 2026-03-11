import type { Inference, PeriodPoint } from "./types";

export function periodToTime(period: number): string {
  const minutes = (period - 1) * 30;
  const h = Math.floor(minutes / 60)
    .toString()
    .padStart(2, "0");
  const m = (minutes % 60).toString().padStart(2, "0");
  return `${h}:${m}`;
}

export function offsetDate(dateStr: string, days: number): string {
  const d = new Date(dateStr + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function buildChartData(
  inference: Inference,
  bmUnits: string[],
): PeriodPoint[] {
  const points: PeriodPoint[] = [];

  // Collect plant generation entries that belong to this group.
  // "matched" entries have bm_units[]; "unmatched" entries have a single bm_unit_id.
  const bmUnitSet = new Set(bmUnits);
  const uniquePlants = new Set(
    inference.plant_generation.filter((pg) => {
      if (pg.source === "matched") {
        return pg.bm_units.some((bu) => bmUnitSet.has(bu));
      } else {
        return bmUnitSet.has(pg.bm_unit_id);
      }
    }),
  );

  for (let p = 1; p <= 48; p++) {
    const pStr = String(p);

    // Sum actual B1610 for all BM units in group
    let actual = 0;
    for (const bu of bmUnits) {
      actual += inference.bm_unit_quantities[bu]?.[pStr] ?? 0;
    }

    // Sum estimated generation across unique matched plants
    let estimated = 0;
    for (const plant of uniquePlants) {
      estimated += plant.generation[pStr] ?? 0;
    }

    points.push({
      period: p,
      time: periodToTime(p),
      actual: Math.round(actual * 10) / 10,
      estimated: Math.round(estimated * 10) / 10,
      residual: Math.round((actual - estimated) * 10) / 10,
    });
  }

  return points;
}
