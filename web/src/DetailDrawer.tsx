import { useState } from "react";
import { patchApp } from "./api";
import { Sparkline } from "./Sparkline";
import type { Activity, Service } from "./types";

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="field">
      <div className="field-label">{label}</div>
      <div className="field-value">{value}</div>
    </div>
  );
}

export function DetailDrawer({
  service,
  activity,
  onClose,
  onSaved,
}: {
  service: Service;
  activity?: Activity;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(service.app.name);
  const [description, setDescription] = useState(service.app.description || "");
  const [saving, setSaving] = useState(false);

  const dirty =
    name !== service.app.name ||
    description !== (service.app.description || "");

  async function save() {
    setSaving(true);
    try {
      await patchApp(service.fingerprint, { name, description });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer">
        <button className="drawer-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h2>{service.app.name}</h2>
        <div className="drawer-port">:{service.port}</div>

        <div className="field">
          <div className="field-label">
            Activity — connections (last {activity?.samples.length ?? 0} samples
            @ 3s)
          </div>
          <div className="activity-panel">
            <Sparkline
              samples={activity?.samples ?? []}
              width={460}
              height={64}
            />
            <div className="activity-stats">
              <span>
                <b>{activity?.current ?? 0}</b> now
              </span>
              <span>
                <b>{activity?.peak ?? 0}</b> peak
              </span>
            </div>
          </div>
        </div>

        <Field
          label="Bind"
          value={`${service.address}:${service.port}`}
        />
        <Field label="User" value={service.user} />
        <Field label="Process" value={`${service.process_name} (pid ${service.pid})`} />
        <Field label="Working directory" value={service.cwd} />
        <Field label="Executable" value={service.exe} />
        <Field
          label="Command line"
          value={service.cmdline.length ? service.cmdline.join(" ") : null}
        />
        {service.app.description && (
          <Field label="Description" value={service.app.description} />
        )}

        <div className="field">
          <div className="field-label">Evidence ({service.app.kind}, conf {service.app.confidence.toFixed(2)})</div>
          <ul className="evidence-list">
            {service.app.evidence.map((e, i) => (
              <li key={i}>
                <b>{e.source}</b>
                {e.detail}
              </li>
            ))}
          </ul>
        </div>

        <div className="edit-form">
          <div className="field-label">Rename / annotate</div>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Display name"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
          />
          <button onClick={save} disabled={!dirty || saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </>
  );
}
