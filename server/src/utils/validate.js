export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function isEmail(v) {
  return typeof v === 'string' && EMAIL_RE.test(v.trim());
}

export function str(v, max = 255) {
  if (v === undefined || v === null) return '';
  return String(v).trim().slice(0, max);
}

export function num(v, { min = 0, max = Number.MAX_SAFE_INTEGER } = {}) {
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  return Math.min(Math.max(n, min), max);
}

/** Valida o payload completo de campanha; devolve lista de erros por campo. */
export function validateCampaignPayload(data) {
  const errors = {};
  if (!data.product_name) errors.product_name = 'Informe o nome/modelo do produto.';
  if (!data.seller_name) errors.seller_name = 'Informe o nome do vendedor.';
  if (!data.whatsapp) errors.whatsapp = 'Informe o número do WhatsApp.';
  else if (!/^\+?[\d\s()-]{10,20}$/.test(data.whatsapp)) errors.whatsapp = 'Número de WhatsApp inválido.';
  if (data.daily_budget === undefined || data.daily_budget === null || data.daily_budget === '') errors.daily_budget = 'Informe o orçamento diário.';
  else if (Number(data.daily_budget) < 5) errors.daily_budget = 'O orçamento diário mínimo é R$ 5,00.';
  if (!data.duration_days) errors.duration_days = 'Informe a duração da campanha.';
  else if (Number(data.duration_days) < 1 || Number(data.duration_days) > 90) errors.duration_days = 'A duração deve ser de 1 a 90 dias.';
  if (!data.age_min) errors.age_min = 'Informe a idade mínima.';
  if (!data.age_max) errors.age_max = 'Informe a idade máxima.';
  if (Number(data.age_min) < 13 || Number(data.age_min) > 65) errors.age_min = 'Idade mínima deve ser entre 13 e 65.';
  if (Number(data.age_max) < 13 || Number(data.age_max) > 65) errors.age_max = 'Idade máxima deve ser entre 13 e 65.';
  if (Number(data.age_min) > Number(data.age_max)) errors.age_min = 'Idade mínima não pode ser maior que a máxima.';
  if (!['all', 'male', 'female'].includes(data.gender)) errors.gender = 'Gênero inválido.';
  if (!Array.isArray(data.interests)) errors.interests = 'Interesses devem ser uma lista.';
  if (Array.isArray(data.interests) && data.interests.length > 10) errors.interests = 'Máximo de 10 interesses.';
  return errors;
}

/** Valida o texto do anúncio escrito pelo usuário (título + corpo). */
export function validateAdCopy(title, adText) {
  const errors = {};
  const t = (title || '').trim();
  const a = (adText || '').trim();
  if (t.length < 3) errors.title = 'Escreva um título para o anúncio (mínimo 3 caracteres).';
  if (t.length > 90) errors.title = 'O título pode ter no máximo 90 caracteres.';
  if (a.length < 10) errors.ad_text = 'Escreva o texto do anúncio (mínimo 10 caracteres).';
  if (a.length > 900) errors.ad_text = 'O texto pode ter no máximo 900 caracteres.';
  return errors;
}
