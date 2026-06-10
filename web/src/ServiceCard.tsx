import { Sparkline } from "./Sparkline";
import type { Activity, Service } from "./types";

const DEV_LOW = 3000;
const DEV_HIGH = 9000;

export function ServiceCard({
  service,
  activity,
  onClick,
}: {
  service: Service;
  activity?: Activity;
  onClick: () => void;
}) {
  const isDev = service.port >= DEV_LOW && service.port <= DEV_HIGH;
  const current = activity?.current ?? 0;
  return (
    <div
      className={`card ${service.limited_info ? "limited" : ""}`}
      onClick={onClick}
    >
      <div className={`card-port ${isDev ? "dev" : ""}`}>
        :{service.port}
        {service.app.previously_seen && (
          <span className="star" title="Previously seen">
            ★
          </span>
        )}
      </div>
      <div className="card-name">{service.app.name}</div>
      <div className="card-meta">
        <span className="kind-badge" data-kind={service.app.kind}>
          {service.app.kind}
        </span>
        <span>
          {service.process_name} · {service.pid}
        </span>
      </div>
      <div className="card-activity">
        <Sparkline samples={activity?.samples ?? []} />
        <span className={`conn-count ${current > 0 ? "active" : ""}`}>
          <span className="conn-dot" />
          {current} conn
        </span>
      </div>
    </div>
  );
}
