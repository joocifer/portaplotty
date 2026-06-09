import type { Service } from "./types";

export async function fetchServices(): Promise<Service[]> {
  const r = await fetch("/api/services");
  if (!r.ok) throw new Error(`/api/services: ${r.status}`);
  return r.json();
}

export async function patchApp(
  fingerprint: string,
  patch: { name?: string; description?: string },
): Promise<void> {
  const r = await fetch(`/api/apps/${fingerprint}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`PATCH /api/apps: ${r.status}`);
}
