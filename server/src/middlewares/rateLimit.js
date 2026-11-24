import { config } from '../config.js';

/**
 * Rate limit por IP com janela deslizante em memória.
 * Uso: rateLimit('auth', 20) — 20 requisições por minuto na rota.
 */
const buckets = new Map();

// Limpa entradas antigas periodicamente para não vazar memória
setInterval(() => {
  const cutoff = Date.now() - config.rateLimit.windowMs * 2;
  for (const [key, hits] of buckets) {
    const recent = hits.filter((t) => t > cutoff);
    if (recent.length === 0) buckets.delete(key);
    else buckets.set(key, recent);
  }
}, 120_000).unref();

export function rateLimit(bucket, max) {
  const limit = max ?? config.rateLimit.globalMax;
  return (req, res, next) => {
    const ip = req.ip || req.socket?.remoteAddress || 'unknown';
    const key = `${bucket}:${ip}`;
    const now = Date.now();
    const windowStart = now - config.rateLimit.windowMs;

    const hits = (buckets.get(key) || []).filter((t) => t > windowStart);
    if (hits.length >= limit) {
      const oldest = hits[0];
      const retryAfter = Math.ceil((oldest + config.rateLimit.windowMs - now) / 1000);
      res.set('Retry-After', String(retryAfter));
      return res.status(429).json({
        error: `Muitas requisições. Tente novamente em ${retryAfter} segundo(s).`,
      });
    }
    hits.push(now);
    buckets.set(key, hits);
    next();
  };
}
