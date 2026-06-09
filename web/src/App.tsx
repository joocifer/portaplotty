import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchServices } from "./api";
import { DetailDrawer } from "./DetailDrawer";
import { ServiceCard } from "./ServiceCard";
import type { Service } from "./types";

const POLL_MS = 3000;

export function App() {
  const [services, setServices] = useState<Service[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [selectedPid, setSelectedPid] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setServices(await fetchServices());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const filtered = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return services;
    return services.filter((s) => {
      const hay = `${s.port} ${s.app.name} ${s.process_name} ${s.app.kind}`.toLowerCase();
      return hay.includes(f);
    });
  }, [services, filter]);

  const selected = useMemo(
    () => services.find((s) => s.pid === selectedPid) || null,
    [services, selectedPid],
  );

  return (
    <div className="app">
      <header className="header">
        <div className="title">
          portaplotty<em>what's listening on your Mac</em>
        </div>
        <div className="controls">
          <span className="count">
            {filtered.length} / {services.length}
          </span>
          <input
            className="search"
            placeholder="Filter port, name, kind…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      </header>

      {error && (
        <div className="empty">Error: {error}</div>
      )}

      {!error && filtered.length === 0 && (
        <div className="empty">
          {services.length === 0 ? "No listeners found." : "No matches."}
        </div>
      )}

      <div className="grid">
        {filtered.map((s) => (
          <ServiceCard
            key={`${s.pid}-${s.port}-${s.address}`}
            service={s}
            onClick={() => setSelectedPid(s.pid)}
          />
        ))}
      </div>

      {selected && (
        <DetailDrawer
          service={selected}
          onClose={() => setSelectedPid(null)}
          onSaved={() => {
            refresh();
            setSelectedPid(null);
          }}
        />
      )}
    </div>
  );
}
