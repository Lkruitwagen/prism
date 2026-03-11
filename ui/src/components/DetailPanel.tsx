import { useMemo, useRef, useState } from "react";
import { TECH_COLORS } from "../colors";
import type { Groups, Inference, Plant } from "../types";
import { buildChartData, offsetDate } from "../utils";
import { GenerationChart } from "./GenerationChart";

interface Props {
  groups: Groups | null;
  plants: Plant[];
  inference: Inference | null;
  inferenceLoading: boolean;
  inferenceError: boolean;
  activeDate: string;
  onDateChange: (d: string) => void;
  selectedGroup: string | null;
  onSelectGroup: (g: string | null) => void;
}

export function DetailPanel({
  groups,
  plants,
  inference,
  inferenceLoading,
  inferenceError,
  activeDate,
  onDateChange,
  selectedGroup,
  onSelectGroup,
}: Props) {
  const [bmQuery, setBmQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Build sorted list of all BM units
  const allBmUnits = useMemo(() => {
    if (!groups) return [];
    return Object.keys(groups.bm_unit_to_group).sort();
  }, [groups]);

  const filteredBmUnits = useMemo(() => {
    if (!bmQuery.trim()) return allBmUnits.slice(0, 50);
    const q = bmQuery.toLowerCase();
    return allBmUnits.filter((u) => u.toLowerCase().includes(q)).slice(0, 50);
  }, [allBmUnits, bmQuery]);

  // Group info
  const groupBmUnits = useMemo(() => {
    if (!selectedGroup || !groups) return [];
    return groups.groups_to_bmunit[selectedGroup] ?? [];
  }, [selectedGroup, groups]);

  const groupDukesIdx = useMemo(() => {
    if (!selectedGroup || !groups) return [];
    return groups.groups_to_dukes_idx[selectedGroup] ?? [];
  }, [selectedGroup, groups]);

  const groupPlants = useMemo(() => {
    const idxSet = new Set(groupDukesIdx);
    return plants.filter((p) => idxSet.has(p.idx));
  }, [groupDukesIdx, plants]);

  // Chart data
  const chartData = useMemo(() => {
    if (!inference || !selectedGroup || groupBmUnits.length === 0) return null;
    return buildChartData(inference, groupBmUnits);
  }, [inference, selectedGroup, groupBmUnits]);

  function handleBmSelect(unit: string) {
    if (!groups) return;
    const gid = groups.bm_unit_to_group[unit];
    if (gid) onSelectGroup(gid);
    setBmQuery(unit);
    setDropdownOpen(false);
  }

  return (
    <div className="detail-panel">
      <div className="logo-bar">
        <img src="/im.png" alt="PRISM" className="logo" />
      </div>

      <div className="date-nav">
        <button
          className="arrow-btn"
          onClick={() => onDateChange(offsetDate(activeDate, -1))}
          aria-label="Previous day"
        >
          ‹
        </button>
        <span className="active-date">{activeDate}</span>
        <button
          className="arrow-btn"
          onClick={() => onDateChange(offsetDate(activeDate, 1))}
          aria-label="Next day"
        >
          ›
        </button>
        {inferenceLoading && <span className="status-dot loading" title="Loading…" />}
        {inferenceError && (
          <span className="no-data">no data</span>
        )}
      </div>

      <div className="bm-select-wrap">
        <div className="bm-select-field">
          <input
            ref={inputRef}
            className="bm-input"
            placeholder="Search BM unit…"
            value={bmQuery}
            onChange={(e) => {
              setBmQuery(e.target.value);
              setDropdownOpen(true);
            }}
            onFocus={() => setDropdownOpen(true)}
            onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
          />
          {dropdownOpen && filteredBmUnits.length > 0 && (
            <ul className="bm-dropdown">
              {filteredBmUnits.map((u) => (
                <li
                  key={u}
                  className={`bm-option${
                    groups?.bm_unit_to_group[u] === selectedGroup
                      ? " selected"
                      : ""
                  }`}
                  onMouseDown={() => handleBmSelect(u)}
                >
                  {u}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {selectedGroup && (
        <div className="group-info">
          <div className="group-section">
            <div className="section-label">BM UNITS</div>
            <div className="tags">
              {groupBmUnits.map((u) => (
                <span key={u} className="tag tag-bm">
                  {u}
                </span>
              ))}
            </div>
          </div>
          <div className="group-section">
            <div className="section-label">DUKES PLANTS</div>
            <div className="tags">
              {groupPlants.map((p) => (
                <span
                  key={p.idx}
                  className="tag tag-plant"
                  style={{
                    borderColor: TECH_COLORS[p.technology] ?? "#555",
                  }}
                >
                  {p.site_name}
                  <span className="tag-sub">{p.technology}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {chartData ? (
        <div className="chart-wrap">
          <GenerationChart data={chartData} />
        </div>
      ) : selectedGroup && !inference ? (
        <div className="chart-placeholder">
          {inferenceLoading ? "Loading inference data…" : "No inference data for this date."}
        </div>
      ) : !selectedGroup ? (
        <div className="chart-placeholder">
          Select a plant on the map or search for a BM unit to view generation.
        </div>
      ) : null}
    </div>
  );
}
