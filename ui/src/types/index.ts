export type RoutePath = 'dashboard' | 'accounts' | 'sandbox' | 'sentinel' | 'docs';

export interface Account {
  email: string;
  is_active: boolean;
  tier?: string;
  models_count?: number;
  added_at?: string;
  last_used?: string;
  quota_summary?: QuotaItem[];
}

export interface QuotaItem {
  family: string;
  label: string;
  percentage: number;
  remaining_fraction?: number;
  reset_time: string;
}

export interface ModelCapabilities {
  thinking: boolean;
  thinking_budget?: number;
  thinking_level?: string;
  streaming: boolean;
  tools: boolean;
  multimodal: boolean;
  supports_images: boolean;
  supports_video: boolean;
  modalities: string[];
  context_window: number;
  max_output_tokens: number;
  temperature_range?: [number, number];
  top_p_range?: [number, number];
}

export interface ModelInfo {
  id: string;
  name: string;
  object?: string;
  created?: number;
  owned_by: string;
  provider?: string;
  upstream_provider?: string;
  root?: string;
  parent?: string | null;
  permission?: unknown[];
  supports_thinking?: boolean;
  thinking_budget?: number;
  thinking_level?: string;
  thinking_desc?: string;
  supports_streaming?: boolean;
  supports_tools?: boolean;
  multimodal?: boolean;
  supports_images?: boolean;
  supports_video?: boolean;
  modalities?: string[];
  context_window?: number;
  max_output_tokens?: number;
  recommended?: boolean;
  capabilities?: ModelCapabilities;
}

export interface TelemetryMetrics {
  throughput_tokens_per_sec: number;
  tokens_today: {
    total: number;
    prompt: number;
    completion: number;
    reasoning: number;
  };
  latency_ms: {
    ttft_avg: number;
    status: 'optimal' | 'warning' | 'high';
  };
  cumulative: {
    requests: number;
    tokens: number;
  };
  active_subscribers: number;
}

export interface TokenVolumePoint {
  timestamp: string;
  timeLabel: string;
  prompt: number;
  completion: number;
  reasoning: number;
  total: number;
}

export interface DbSentinelStatus {
  status: 'healthy' | 'degraded' | 'corrupted';
  db_path: string;
  crc32_valid: boolean;
  wal_mode: boolean;
  audit_interval_sec: number;
  last_audit_timestamp: string;
  page_count: number;
  page_size: number;
  journal_mode: string;
  integrity_check: string;
}

export interface AuditLogEvent {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  source: string;
  message: string;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_seconds: number;
  version: string;
  engine: string;
  active_account: string | null;
  accounts_count: number;
  models_health: Record<string, {
    status: 'operational' | 'degraded' | 'rate_limited';
    quota_percentage: number;
    provider: string;
  }>;
  recent_logs: Array<{
    timestamp: string;
    level: string;
    source: string;
    message: string;
  }>;
}

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

export interface ModalConfig {
  isOpen: boolean;
  title: string;
  description?: string;
  content?: React.ReactNode;
  confirmText?: string;
  confirmVariant?: 'primary' | 'danger' | 'warning';
  cancelText?: string;
  onConfirm?: () => Promise<void> | void;
  onCancel?: () => void;
}
