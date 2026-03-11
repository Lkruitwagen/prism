import { useState } from "react";
import { DetailPanel } from "./components/DetailPanel";
import { MapPanel } from "./components/MapPanel";
import { useGroups, useInference, usePlants } from "./hooks/useData";
import "./styles.css";

const DEFAULT_DATE = "2026-03-01";
const ALL_TECHS = new Set([
  "Solar",
  "Wind",
  "Bioenergy",
  "Nuclear",
  "Hydro",
  "Pumped Hydro",
  "Fossil Fuel",
  "OCGT",
]);

export default function App() {
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [activeDate, setActiveDate] = useState(DEFAULT_DATE);
  const [techFilter, setTechFilter] = useState<Set<string>>(ALL_TECHS);

  const { plants } = usePlants();
  const { groups } = useGroups();
  const {
    inference,
    loading: inferenceLoading,
    error: inferenceError,
  } = useInference(activeDate);

  return (
    <div className="layout">
      <MapPanel
        plants={plants}
        selectedGroup={selectedGroup}
        techFilter={techFilter}
        onTechFilterChange={setTechFilter}
        onSelectGroup={setSelectedGroup}
      />
      <DetailPanel
        groups={groups}
        plants={plants}
        inference={inference}
        inferenceLoading={inferenceLoading}
        inferenceError={inferenceError}
        activeDate={activeDate}
        onDateChange={setActiveDate}
        selectedGroup={selectedGroup}
        onSelectGroup={setSelectedGroup}
      />
    </div>
  );
}
