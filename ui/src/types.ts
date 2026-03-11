export interface Plant {
  idx: number;
  site_name: string;
  company: string;
  technology: string;
  capacity_mw: number;
  lat: number;
  lon: number;
  gsp_group: string | null;
  group_id: string | null;
}

export interface Groups {
  groups_to_bmunit: Record<string, string[]>;
  groups_to_dukes_idx: Record<string, number[]>;
  dukes_idx_to_group: Record<string, string>;
  bm_unit_to_group: Record<string, string>;
}

export interface PlantGenerationMatched {
  bm_units: string[];
  lat: number;
  lon: number;
  plant_type: string;
  source: "matched";
  generation: Record<string, number>;
}

export interface PlantGenerationUnmatched {
  bm_unit_id: string;
  dukes_index: string;
  site_name: string;
  lat: number;
  lon: number;
  plant_type: string;
  capacity_mw: number;
  source: "unmatched";
  generation: Record<string, number>;
}

export type PlantGeneration = PlantGenerationMatched | PlantGenerationUnmatched;

export interface Inference {
  date: string;
  bm_unit_quantities: Record<string, Record<string, number>>;
  plant_generation: PlantGeneration[];
}

export interface PeriodPoint {
  period: number;
  time: string;
  actual: number;
  estimated: number;
  residual: number;
}
