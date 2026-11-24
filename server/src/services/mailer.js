import nodemailer from 'nodemailer';
import { db } from '../db.js';
import { config } from '../config.js';

let transporter = null;
if (config.smtp.host) {
  transporter = nodemailer.createTransport({
    host: config.smtp.host,
    port: config.smtp.port,
    secure: config.smtp.secure,
    auth: config.smtp.user ? { user: config.smtp.user, pass: config.smtp.pass } : undefined,
  });
}

export const mailer = {
  /** true quando SMTP não está configurado — emails ficam no outbox local (modo dev) */
  get isDevMode() {
    return !transporter;
  },

  /** Envia o email; em modo dev grava no outbox (visível via GET /api/dev/emails) e loga no console. */
  async send({ to, subject, html, text = '' }) {
    if (transporter) {
      await transporter.sendMail({ from: config.smtp.from, to, subject, html, text });
      return { delivered: true };
    }
    db.prepare(
      'INSERT INTO email_outbox (to_email, subject, html, text, created_at) VALUES (?, ?, ?, ?, ?)'
    ).run(to, subject, html, text, new Date().toISOString());
    console.log(`\n📧 [modo dev] Email para ${to} — "${subject}"\n${text}\n`);
    return { delivered: false };
  },

  linkHtml(url, label) {
    return `<p style="font-size:16px;line-height:1.6">${label}</p>
      <p><a href="${url}" style="background:#2590eb;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">${url}</a></p>`;
  },
};
