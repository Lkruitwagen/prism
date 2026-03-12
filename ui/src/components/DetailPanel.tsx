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
        <img src="/im-inv.png" alt="PRISM" className="logo" />
        <a
          href="https://github.com/Lkruitwagen/prism"
          target="_blank"
          rel="noopener noreferrer"
          className="github-link"
          aria-label="GitHub repository"
        >
          <svg height="20" width="20" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
              0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
              -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87
              2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95
              0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12
              0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04
              2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15
              0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48
              0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8
              c0-4.42-3.58-8-8-8z" />
          </svg>
          <span>Lkruitwagen/prism</span>
        </a>
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
