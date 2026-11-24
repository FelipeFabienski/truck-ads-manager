import express from 'express';
import cookieParser from 'cookie-parser';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { config } from './config.js';
import { requireAuth } from './middlewares/auth.js';
import { rateLimit } from './middlewares/rateLimit.js';
import authRoutes from './routes/auth.js';
import profileRoutes from './routes/profile.js';
import credentialRoutes from './routes/credentials.js';
import campaignRoutes from './routes/campaignsThin.js';
import metricsRoutes from './routes/metrics.js';
import planRoutes from './routes/plans.js';
import adminRoutes from './routes/admin.js';
import devRoutes from './routes/dev.js';

export function createApp() {
  const app = express();
  app.set('trust proxy', 1);
  app.disable('x-powered-by');

  app.use(express.json({ limit: '2mb' }));
  app.use(cookieParser());

  // Proteções adicionais nos cookies/sessões via cabeçalhos de segurança
  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    next();
  });

  // Rate limit global: X requisições por minuto por IP
  app.use('/api', rateLimit('global', config.rateLimit.globalMax));

  // Fotos e avatares enviados pelos usuários
  fs.mkdirSync(config.uploadDir, { recursive: true });
  app.use('/uploads', express.static(config.uploadDir, { fallthrough: true, maxAge: '7d' }));

  app.get('/api/health', (req, res) => res.json({ ok: true, devEmailMode: config.isDev }));

  app.use('/api/auth', authRoutes);
  app.use('/api/profile', profileRoutes);
  app.use('/api/credentials', credentialRoutes);
  app.use('/api/campaigns', campaignRoutes);
  app.use('/api/metrics', metricsRoutes);
  app.use('/api/plans', planRoutes);
  app.use('/api/admin', adminRoutes);
  app.use('/api/dev', requireAuth, devRoutes);

  app.use('/api', (req, res) => res.status(404).json({ error: 'Rota não encontrada.' }));

  // Frontend React em produção: serve web/dist com fallback SPA (serviço único no Railway).
  // Ativa apenas quando o build existe — em dev o Vite continua servindo o frontend.
  const webDist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../web/dist');
  const spaIndex = path.join(webDist, 'index.html');
  if (fs.existsSync(spaIndex)) {
    app.use(express.static(webDist, { maxAge: '1d', index: false }));
    app.use((req, res, next) => {
      if (req.method !== 'GET' || req.path.startsWith('/api') || req.path.startsWith('/uploads')) return next();
      try {
        res.type('html').send(fs.readFileSync(spaIndex));
      } catch (err) {
        console.error('Falha ao servir SPA:', err.message);
        res.status(500).send('Falha ao carregar a interface.');
      }
    });
  }

  // Tratamento central de erros (JSON de erro amigável)
  app.use((err, req, res, next) => {
    if (err?.type === 'entity.parse.failed') {
      return res.status(400).json({ error: 'Corpo da requisição inválido (JSON malformado).' });
    }
    if (err?.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({ error: 'Arquivo muito grande (máximo 10MB).' });
    }
    if (err?.code === 'LIMIT_UNEXPECTED_FILE') {
      return res.status(400).json({ error: `Campo de arquivo inesperado: ${err.field}. Use "photos" para fotos e "avatar" para foto de perfil.` });
    }
    if (err?.code === 'EBADCSRFTOKEN' || err?.code === 'ETIMEDOUT') {
      return res.status(400).json({ error: 'Requisição inválida.' });
    }
    console.error('Erro não tratado:', err);
    res.status(500).json({ error: 'Erro interno do servidor.' });
  });

  return app;
}
