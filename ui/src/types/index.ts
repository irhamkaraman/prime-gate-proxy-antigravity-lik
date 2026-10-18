export type RoutePath = 'dashboard' | 'benchmarks' | 'caching' | 'accounts' | 'sandbox' | 'sentinel' | 'docs';

export type TimeRange = '1m' | '1h' | '1d' | '1month';

export interface ModelBenchmark {
  model: string;
  requests_count: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  cache_hits?: number;
  tokens_saved?: number;
  usd_value_saved?: number;
  idr_value_saved?: number;
  avg_latency_ms: number;
  min_latency_ms: number;
  max_latency_ms: number;
  tokens_per_second: number;
  token_share_pct: number;
  quota_impact_score: number;
  last_seen_ts: number | null;
  last_seen_formatted: string;
}

export interface ModelBenchmarksResponse {
  total_models_tracked: number;
  total_requests: number;
  total_tokens: number;
  total_cache_hits?: number;
  total_tokens_saved?: number;
  total_usd_delivered?: number;
  total_idr_delivered?: number;
  top_spender_model: string | null;
  models: ModelBenchmark[];
}

export interface RequestLogEntry {
  id: number;
  request_id: string;
  timestamp: number;
  time_formatted: string;
  account_email: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status_code: number;
  stream: boolean;
  cache_hit?: boolean;
  tokens_saved?: number;
  cache_hit_type?: number;
  similarity_score?: number;
  quota_snapshot?: Array<{
    family: string;
    label: string;
    percentage: number;
    reset_time: string;
  }> | null;
}

export interface RequestLogsResponse {
  total: number;
  limit: number;
  offset: number;
  logs: RequestLogEntry[];
}

export interface CacheConfig {
  enabled: boolean;
  bypass_tools: boolean;
  min_prompt_length: number;
  ttl_seconds: number;
  semantic_enabled?: boolean;
  semantic_threshold?: number;
  cache_mode?: 'exact' | 'semantic' | 'hybrid' | string;
  turn_based_keying?: boolean;
  compactor_enabled?: boolean;
  compactor_window?: number;
  compactor_max_tool_lines?: number;
  loop_guard_enabled?: boolean;
  loop_guard_max_repeat?: number;
}

export interface CacheStats {
  total_entries: number;
  total_hits: number;
  exact_hits?: number;
  semantic_hits?: number;
  upstream_hits?: number;
  total_tokens_saved: number;
  hit_ratio_pct: number;
  estimated_seconds_saved: number;
  usd_value_saved?: number;
  idr_value_saved?: number;
  config: CacheConfig;
}


export interface CacheEntry {
  id: number;
  cache_key: string;
  prompt_hash: string;
  prompt_preview: string;
  response_preview?: string;
  response_text: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  hit_count: number;
  tokens_saved_total: number;
  created_at: number;
  created_at_formatted?: string;
  last_hit_at: number | null;
  last_hit_formatted?: string;
}

export interface CacheEntriesResponse {
  total: number;
  limit: number;
  offset: number;
  entries: CacheEntry[];
}

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
