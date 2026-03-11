import { useEffect, useState } from "react";
import { dataUrl } from "../config";
import type { Groups, Inference, Plant } from "../types";

export function usePlants(): { plants: Plant[]; loading: boolean } {
  const [plants, setPlants] = useState<Plant[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(dataUrl("data/plants.json"))
      .then((r) => r.json())
      .then((d) => setPlants(d))
      .finally(() => setLoading(false));
  }, []);
  return { plants, loading };
}

export function useGroups(): { groups: Groups | null; loading: boolean } {
  const [groups, setGroups] = useState<Groups | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(dataUrl("data/groups.json"))
      .then((r) => r.json())
      .then((d) => setGroups(d))
      .finally(() => setLoading(false));
  }, []);
  return { groups, loading };
}

export function useInference(
  date: string,
): { inference: Inference | null; loading: boolean; error: boolean } {
  const [inference, setInference] = useState<Inference | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    setLoading(true);
    setError(false);
    setInference(null);
    fetch(dataUrl(`data/inference_${date}.json`))
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((d) => setInference(d))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [date]);
  return { inference, loading, error };
}
