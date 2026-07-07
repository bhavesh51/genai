"""
Project 5 – Observability & Guardrails
Prometheus metrics definitions for LLM observability
"""
from prometheus_client import Counter, Histogram, Gauge, Info

# ─── Request metrics ─────────────────────────────────────────────────────────

REQUESTS_TOTAL = Counter(
    "genai_requests_total",
    "Total number of GenAI inference requests",
    ["service", "model", "tenant", "status"],
)

REQUEST_LATENCY = Histogram(
    "genai_request_latency_seconds",
    "End-to-end request latency in seconds",
    ["service", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

TIME_TO_FIRST_TOKEN = Histogram(
    "genai_time_to_first_token_seconds",
    "Time to first token for streaming responses",
    ["service", "model"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

TOKENS_PER_SECOND = Histogram(
    "genai_tokens_per_second",
    "Token generation throughput",
    ["service", "model"],
    buckets=[1, 5, 10, 20, 50, 100, 200],
)

# ─── Token metrics ────────────────────────────────────────────────────────────

TOKENS_INPUT = Counter(
    "genai_tokens_input_total",
    "Total input tokens processed",
    ["service", "model", "tenant"],
)

TOKENS_OUTPUT = Counter(
    "genai_tokens_output_total",
    "Total output tokens generated",
    ["service", "model", "tenant"],
)

# ─── Guardrails metrics ───────────────────────────────────────────────────────

GUARDRAIL_VIOLATIONS = Counter(
    "genai_guardrail_violations_total",
    "Total guardrail violations detected",
    ["violation_type", "service"],
)

GUARDRAIL_CHECK_DURATION = Histogram(
    "genai_guardrail_check_duration_seconds",
    "Time spent running guardrail checks",
    ["service"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.5],
)

# ─── GPU metrics ──────────────────────────────────────────────────────────────

GPU_MEMORY_USED_BYTES = Gauge(
    "genai_gpu_memory_used_bytes",
    "GPU memory currently used",
    ["node", "device"],
)

KV_CACHE_HIT_RATE = Gauge(
    "genai_kv_cache_hit_rate",
    "KV cache hit rate for vLLM",
    ["model"],
)

REQUEST_QUEUE_DEPTH = Gauge(
    "genai_request_queue_depth",
    "Number of requests in queue",
    ["service"],
)

# ─── Cost metrics ─────────────────────────────────────────────────────────────

ESTIMATED_COST_USD = Counter(
    "genai_estimated_cost_usd_total",
    "Estimated token cost in USD",
    ["service", "model", "tenant"],
)

GPU_HOURS = Counter(
    "genai_gpu_hours_total",
    "GPU hours consumed",
    ["service", "namespace"],
)
