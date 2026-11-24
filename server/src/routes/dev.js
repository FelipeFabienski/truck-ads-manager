import { Router } from 'express';
import { db } from '../db.js';
import { config } from '../config.js';
import { mailer } from '../services/mailer.js';

const router = Router();

/**
 * Rota exclusiva de desenvolvimento (sem SMTP): consulta os emails do outbox.
 * Desabilitada quando SMTP está configurado ou NODE_ENV=production.
 */
router.get('/emails', (req, res) => {
  if (!config.isDev || !mailer.isDevMode) {
    return res.status(404).json({ error: 'Disponível apenas em modo dev.' });
  }
  const rows = db.prepare('SELECT * FROM email_outbox ORDER BY created_at DESC LIMIT 30').all();
  res.json({
    emails: rows.map((r) => ({ id: r.id, to: r.to_email, subject: r.subject, text: r.text, html: r.html, createdAt: r.created_at })),
  });
});

export default router;
