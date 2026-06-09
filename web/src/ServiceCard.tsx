import type { Service } from "./types";

const DEV_LOW = 3000;
const DEV_HIGH = 9000;

export function ServiceCard({
  service,
  onClick,
}: {
  service: Service;
  onClick: () => void;
}) {
  const isDev = service.port >= DEV_LOW && service.port <= DEV_HIGH;
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
    </div>
  );
}
