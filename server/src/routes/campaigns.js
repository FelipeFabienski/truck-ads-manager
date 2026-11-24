import { Router } from 'express';
import multer from 'multer';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';
import { config } from '../config.js';
import { requireAuth } from '../middlewares/auth.js';
import { validateCampaignPayload, validateAdCopy, str } from '../utils/validate.js';
import { audit } from '../services/audit.js';

const router = Router();
router.use(requireAuth);

const photoStorage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = path.join(config.uploadDir, 'products');
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase() || '.jpg';
    cb(null, `${Date.now()}-${Math.random().toString(36).slice(2, 10)}${ext}`);
  },
});
const photoUpload = multer({
  storage: photoStorage,
  limits: { fileSize: 10 * 1024 * 1024, files: 6 },
  fileFilter: (req, file, cb) => cb(null, /^image\/(jpeg|png|webp)$/.test(file.mimetype)),
});

function extractCampaignFields(body) {
  let interests = [];
  try {
    const raw = body?.interests;
    interests = typeof raw === 'string' ? JSON.parse(raw || '[]') : Array.isArray(raw) ? raw : [];
    interests = interests.map((i) => String(i).trim()).filter(Boolean).slice(0, 10);
  } catch {
    interests = [];
  }
  const credentialId = Number.parseInt(String(body?.credential_id ?? ''), 10);
  return {
    product_name: str(body?.product_name, 120),
    color: str(body?.color, 60),
    year: str(body?.year, 10),
    price: str(body?.price, 20),
    km: str(body?.km, 20),
    city: str(body?.city, 80),
    state: str(body?.state, 2).toUpperCase(),
    seller_name: str(body?.seller_name, 80),
    whatsapp: str(body?.whatsapp, 30),
    daily_budget: body?.daily_budget,
    duration_days: body?.duration_days,
    age_min: body?.age_min,
    age_max: body?.age_max,
    gender: str(body?.gender, 10) || 'all',
    interests,
    credentialId: Number.isInteger(credentialId) && credentialId > 0 ? credentialId : null,
  };
}

function parseCampaign(row) {
  return {
    id: row.id,
    userId: row.user_id,
    productName: row.product_name,
    color: row.color,
    year: row.year,
    price: row.price,
    km: row.km,
    city: row.city,
    state: row.state,
    sellerName: row.seller_name,
    whatsapp: row.whatsapp,
    dailyBudget: row.daily_budget,
    durationDays: row.duration_days,
    ageMin: row.age_min,
    ageMax: row.age_max,
    gender: row.gender,
    interests: JSON.parse(row.interests || '[]'),
    photos: JSON.parse(row.photos || '[]'),
    title: row.title,
    adText: row.ad_text,
    status: row.status,
    credentialId: row.credential_id || null,
    metaCampaignId: row.meta_campaign_id,
    metaAdsetId: row.meta_adset_id,
    metaAdId: row.meta_ad_id,
    publishedAt: row.published_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

router.get('/health-local', (req, res) => {
  res.json({ ok: true, router: 'campaigns' });
});

export default router;
