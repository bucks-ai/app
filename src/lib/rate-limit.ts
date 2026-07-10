// Rate limiting helper for API routes.
//
// Uses Upstash Redis (@upstash/ratelimit + @upstash/redis) when
// UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are set, so limits are
// shared across serverless instances in production. Falls back to an
// in-memory sliding-window limiter otherwise, so the app works locally and in
// tests with no external account.

import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { apiError } from "@/lib/api-error";

export interface RateLimitOptions {
  /** Maximum number of requests allowed within the window. */
  limit: number;
  /** Window size in milliseconds. */
  windowMs: number;
}

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
}

interface RateLimiterBackend {
  limit(key: string, opts: RateLimitOptions): Promise<RateLimitResult>;
}

/** Sliding-window limiter backed by an in-process Map. Not shared across instances. */
export class InMemoryRateLimiter implements RateLimiterBackend {
  private hits = new Map<string, number[]>();

  async limit(key: string, { limit, windowMs }: RateLimitOptions): Promise<RateLimitResult> {
    const now = Date.now();
    const windowStart = now - windowMs;
    const recent = (this.hits.get(key) ?? []).filter((timestamp) => timestamp > windowStart);

    if (recent.length >= limit) {
      this.hits.set(key, recent);
      return { allowed: false, remaining: 0 };
    }

    recent.push(now);
    this.hits.set(key, recent);
    return { allowed: true, remaining: limit - recent.length };
  }

  /** Test-only: clears all recorded hits so cases don't leak state across each other. */
  clear() {
    this.hits.clear();
  }
}

class UpstashRateLimiter implements RateLimiterBackend {
  private limiters = new Map<string, Ratelimit>();

  constructor(private readonly redis: Redis) {}

  private getLimiter(opts: RateLimitOptions): Ratelimit {
    const cacheKey = `${opts.limit}:${opts.windowMs}`;
    let limiter = this.limiters.get(cacheKey);
    if (!limiter) {
      limiter = new Ratelimit({
        redis: this.redis,
        limiter: Ratelimit.slidingWindow(opts.limit, `${opts.windowMs} ms`),
        analytics: false,
      });
      this.limiters.set(cacheKey, limiter);
    }
    return limiter;
  }

  async limit(key: string, opts: RateLimitOptions): Promise<RateLimitResult> {
    const { success, remaining } = await this.getLimiter(opts).limit(key);
    return { allowed: success, remaining: Math.max(0, remaining) };
  }
}

function createBackend(): RateLimiterBackend {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (url && token) {
    return new UpstashRateLimiter(new Redis({ url, token }));
  }
  return new InMemoryRateLimiter();
}

let backend: RateLimiterBackend | undefined;

/** Lazily creates the backend so env vars can be read at call time, not import time. */
function getBackend(): RateLimiterBackend {
  if (!backend) backend = createBackend();
  return backend;
}

/**
 * Checks and records a request against a sliding-window limit for `key`.
 * `key` should identify the caller, e.g. `${userId}:${route}` or an IP.
 */
export async function limit(key: string, opts: RateLimitOptions): Promise<RateLimitResult> {
  return getBackend().limit(key, opts);
}

/** 429 envelope for routes that reject a request because a rate limit was hit. */
export function tooManyRequests(message = "Too many requests. Please try again later.") {
  return apiError(message, "rate_limited", 429);
}

/**
 * Named per-route rate-limit presets, kept in one place so every route's
 * limit can be audited and tuned together instead of being scattered as
 * ad-hoc constants across route files.
 */
export const RATE_LIMITS = {
  /** Expensive OpenAI blueprint generation call. */
  blueprintGenerate: { limit: 5, windowMs: 60_000 },
  /** AI-adjacent agent-run inference. */
  agentRunsInfer: { limit: 5, windowMs: 60_000 },
  /** AI-driven research workspace generation. */
  researchGenerate: { limit: 5, windowMs: 60_000 },
  /** Moderate default for mutating routes without a bespoke limit. */
  mutationDefault: { limit: 30, windowMs: 60_000 },
  /** Compiles a blueprint into a mission — cheap, but not something to spam. */
  executeBusiness: { limit: 5, windowMs: 60_000 },
  /** Public, unauthenticated signup endpoint — limited by IP, not user id. */
  authSignup: { limit: 10, windowMs: 60_000 },
} as const satisfies Record<string, RateLimitOptions>;
