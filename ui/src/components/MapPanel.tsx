import "leaflet/dist/leaflet.css";
import { useMemo } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import { DEFAULT_TECH_COLOR, TECH_COLORS } from "../colors";
import type { Plant } from "../types";

const ALL_TECHS = [
  "Solar",
  "Wind",
  "Bioenergy",
  "Nuclear",
  "Hydro",
  "Pumped Hydro",
  "Fossil Fuel",
  "OCGT",
];

function capacityToRadius(mw: number): number {
  // sqrt scaling, clamped to [3, 20]
  return Math.max(3, Math.min(20, 3 + Math.sqrt(mw) * 0.6));
}

interface Props {
  plants: Plant[];
  selectedGroup: string | null;
  techFilter: Set<string>;
  onTechFilterChange: (t: Set<string>) => void;
  onSelectGroup: (g: string | null) => void;
}

export function MapPanel({
  plants,
  selectedGroup,
  techFilter,
  onTechFilterChange,
  onSelectGroup,
}: Props) {
  const visiblePlants = useMemo(
    () =>
      plants.filter((p) => {
        const techKey = ALL_TECHS.find(
          (t) => t.toLowerCase() === p.technology.toLowerCase(),
        );
        return techFilter.has(techKey ?? p.technology);
      }),
    [plants, techFilter],
  );

  function toggleTech(tech: string) {
    const next = new Set(techFilter);
    if (next.has(tech)) {
      if (next.size > 1) next.delete(tech);
    } else {
      next.add(tech);
    }
    onTechFilterChange(next);
  }

  function toggleAll() {
    if (techFilter.size === ALL_TECHS.length) {
      onTechFilterChange(new Set([ALL_TECHS[0]]));
    } else {
      onTechFilterChange(new Set(ALL_TECHS));
    }
  }

  return (
    <div className="map-panel">
      <div className="tech-filter">
        <button
          className={`tech-chip all-chip${
            techFilter.size === ALL_TECHS.length ? " active" : ""
          }`}
          onClick={toggleAll}
        >
          All
        </button>
        {ALL_TECHS.map((tech) => (
          <button
            key={tech}
            className={`tech-chip${techFilter.has(tech) ? " active" : ""}`}
            style={
              techFilter.has(tech)
                ? {
                    borderColor: TECH_COLORS[tech] ?? DEFAULT_TECH_COLOR,
                    color: TECH_COLORS[tech] ?? DEFAULT_TECH_COLOR,
                  }
                : {}
            }
            onClick={() => toggleTech(tech)}
          >
            {tech}
          </button>
        ))}
      </div>
      <div className="map-container">
        <MapContainer
          center={[54.5, -2.5]}
          zoom={6}
          style={{ height: "100%", width: "100%", background: "#0a0a0f" }}
          zoomControl={true}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />
          {visiblePlants.map((plant) => {
            const techKey =
              ALL_TECHS.find(
                (t) => t.toLowerCase() === plant.technology.toLowerCase(),
              ) ?? plant.technology;
            const color = TECH_COLORS[techKey] ?? DEFAULT_TECH_COLOR;
            const isSelected = plant.group_id === selectedGroup;
            const hasGroup = plant.group_id !== null;
            return (
              <CircleMarker
                key={plant.idx}
                center={[plant.lat, plant.lon]}
                radius={capacityToRadius(plant.capacity_mw)}
                pathOptions={{
                  color: isSelected ? "#fff" : color,
                  weight: isSelected ? 2 : 0.5,
                  fillColor: color,
                  fillOpacity: hasGroup ? 0.85 : 0.2,
                  opacity: 1,
                }}
                eventHandlers={{
                  click: () => {
                    if (plant.group_id) {
                      onSelectGroup(
                        plant.group_id === selectedGroup
                          ? null
                          : plant.group_id,
                      );
                    }
                  },
                }}
              >
                <Tooltip>
                  <div style={{ fontSize: 12 }}>
                    <strong>{plant.site_name}</strong>
                    <br />
                    {plant.technology} · {plant.capacity_mw} MW
                    <br />
                    {plant.company}
                    {plant.group_id && (
                      <>
                        <br />
                        Group {plant.group_id}
                      </>
                    )}
                  </div>
                </Tooltip>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}
