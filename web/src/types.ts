export interface Evidence {
  source: string;
  detail: string;
}

export interface AppInfo {
  name: string;
  kind: string;
  confidence: number;
  description: string | null;
  evidence: Evidence[];
  previously_seen: boolean;
}

export interface Service {
  pid: number;
  port: number;
  address: string;
  process_name: string;
  user: string;
  exe: string | null;
  cwd: string | null;
  cmdline: string[];
  fingerprint: string;
  app: AppInfo;
  limited_info: boolean;
}
