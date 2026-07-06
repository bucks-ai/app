import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InMemoryRateLimiter, limit, tooManyRequests } from "@/lib/rate-limit";

describe("InMemoryRateLimiter", () => {
  let limiter: InMemoryRateLimiter;

  beforeEach(() => {
    limiter = new InMemoryRateLimiter();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("allows requests up to the limit", async () => {
    const opts = { limit: 3, windowMs: 1000 };

    const first = await limiter.limit("a", opts);
    const second = await limiter.limit("a", opts);
    const third = await limiter.limit("a", opts);

    expect(first).toEqual({ allowed: true, remaining: 2 });
    expect(second).toEqual({ allowed: true, remaining: 1 });
    expect(third).toEqual({ allowed: true, remaining: 0 });
  });

  it("rejects requests once the limit is exceeded", async () => {
    const opts = { limit: 2, windowMs: 1000 };

    await limiter.limit("a", opts);
    await limiter.limit("a", opts);
    const blocked = await limiter.limit("a", opts);

    expect(blocked).toEqual({ allowed: false, remaining: 0 });
  });

  it("keeps rejecting while the same window is still active", async () => {
    const opts = { limit: 1, windowMs: 1000 };

    await limiter.limit("a", opts);
    vi.advanceTimersByTime(500);
    const stillBlocked = await limiter.limit("a", opts);

    expect(stillBlocked).toEqual({ allowed: false, remaining: 0 });
  });

  it("allows requests again once the window has fully elapsed", async () => {
    const opts = { limit: 1, windowMs: 1000 };

    await limiter.limit("a", opts);
    vi.advanceTimersByTime(1001);
    const afterWindow = await limiter.limit("a", opts);

    expect(afterWindow).toEqual({ allowed: true, remaining: 0 });
  });

  it("slides the window instead of resetting it all at once", async () => {
    const opts = { limit: 2, windowMs: 1000 };

    await limiter.limit("a", opts); // t=0
    vi.advanceTimersByTime(600);
    await limiter.limit("a", opts); // t=600, both still in window

    vi.advanceTimersByTime(500); // t=1100: first hit (t=0) has expired
    const result = await limiter.limit("a", opts);
    expect(result).toEqual({ allowed: true, remaining: 0 });

    const blocked = await limiter.limit("a", opts);
    expect(blocked).toEqual({ allowed: false, remaining: 0 });
  });

  it("tracks separate keys independently", async () => {
    const opts = { limit: 1, windowMs: 1000 };

    const a = await limiter.limit("a", opts);
    const b = await limiter.limit("b", opts);

    expect(a).toEqual({ allowed: true, remaining: 0 });
    expect(b).toEqual({ allowed: true, remaining: 0 });
  });

  it("clear() resets all recorded hits", async () => {
    const opts = { limit: 1, windowMs: 1000 };

    await limiter.limit("a", opts);
    limiter.clear();
    const result = await limiter.limit("a", opts);

    expect(result).toEqual({ allowed: true, remaining: 0 });
  });
});

describe("limit() (in-memory fallback, no Upstash env vars set)", () => {
  it("returns allowed/remaining and enforces the limit across calls", async () => {
    const key = `test-limit-${crypto.randomUUID()}`;
    const opts = { limit: 2, windowMs: 1000 };

    const first = await limit(key, opts);
    const second = await limit(key, opts);
    const third = await limit(key, opts);

    expect(first.allowed).toBe(true);
    expect(second.allowed).toBe(true);
    expect(third).toEqual({ allowed: false, remaining: 0 });
  });
});

describe("tooManyRequests", () => {
  it("returns a 429 envelope with the rate_limited code", async () => {
    const response = tooManyRequests();
    expect(response.status).toBe(429);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Too many requests. Please try again later.",
      code: "rate_limited",
    });
  });

  it("allows a custom message", async () => {
    const response = tooManyRequests("Slow down.");
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "Slow down.",
      code: "rate_limited",
    });
  });
});
