import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { useToast } from '../components/Toast.jsx';

const STEPS = [
  { n: 1, title: 'Produto', desc: 'Dados do que você vai anunciar' },
  { n: 2, title: 'Vendedor', desc: 'Quem vai atender no WhatsApp' },
  { n: 3, title: 'Campanha', desc: 'Orçamento e duração' },
  { n: 4, title: 'Público', desc: 'Segmentação do anúncio' },
  { n: 5, title: 'Anúncio', desc: 'Escreva o texto e revise' },
];

const UFS = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'];

// mapeia erros do servidor para o passo correspondente
const ERROR_STEP = {
  product_name: 0, photos: 0, seller_name: 1, whatsapp: 1,
  daily_budget: 2, duration_days: 2, age_min: 3, age_max: 3, gender: 3, interests: 3,
};

export default function CampaignWizard() {
  const toast = useToast();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  const [form, setForm] = useState({
    product_name: '', color: '', year: '', price: '', km: '', city: '', state: 'SP',
    seller_name: '', whatsapp: '',
    daily_budget: '20', duration_days: '7',
    age_min: '18', age_max: '65', gender: 'all', interests: '',
    title: '', ad_text: '', credential_id: '',
  });
  const [photos, setPhotos] = useState([]);
  const [credentials, setCredentials] = useState([]);
  const photoUrls = useMemo(() => photos.map((p) => URL.createObjectURL(p)), [photos]);

  // Integrações Meta conectadas do usuário (seleção na criação do anúncio)
  useEffect(() => {
    api
      .get('/api/credentials')
      .then((data) => {
        setCredentials(data.credentials.filter((c) => c.validationStatus === 'connected' && c.isActive));
        const active = data.credentials.find((c) => c.isActive && c.validationStatus === 'connected');
        if (active) setForm((f) => ({ ...f, credential_id: String(active.id) }));
      })
      .catch(() => {});
  }, []);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function validateStep(i) {
    const e = {};
    if (i === 0) {
      if (!form.product_name.trim()) e.product_name = 'Informe o nome/modelo do produto.';
      if (photos.length === 0) e.photos = 'Adicione pelo menos uma foto do produto.';
    }
    if (i === 1) {
      if (!form.seller_name.trim()) e.seller_name = 'Informe o nome do vendedor.';
      if (!/^\+?[\d\s()-]{10,20}$/.test(form.whatsapp.trim())) e.whatsapp = 'Informe um número válido, ex: (11) 99999-9999.';
    }
    if (i === 2) {
      if (!form.daily_budget || Number(form.daily_budget) < 5) e.daily_budget = 'Orçamento diário mínimo de R$ 5,00.';
      if (!form.duration_days || Number(form.duration_days) < 1 || Number(form.duration_days) > 90) e.duration_days = 'Duração de 1 a 90 dias.';
    }
    if (i === 3) {
      const mn = Number(form.age_min), mx = Number(form.age_max);
      if (mn < 13 || mn > 65) e.age_min = 'Entre 13 e 65 anos.';
      if (mx < 13 || mx > 65) e.age_max = 'Entre 13 e 65 anos.';
      if (mn > mx) e.age_min = 'Mínima não pode ser maior que a máxima.';
    }
    if (i === 4) {
      if (form.title.trim().length < 3) e.title = 'Escreva um título para o anúncio (mínimo 3 caracteres).';
      if (form.title.trim().length > 90) e.title = 'O título pode ter no máximo 90 caracteres.';
      if (form.ad_text.trim().length < 10) e.ad_text = 'Escreva o texto do anúncio (mínimo 10 caracteres).';
      if (form.ad_text.trim().length > 900) e.ad_text = 'O texto pode ter no máximo 900 caracteres.';
    }
    return e;
  }

  function next() {
    const e = validateStep(step);
    setErrors(e);
    if (Object.keys(e).length) return;
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }

  function back() {
    setErrors({});
    setStep((s) => Math.max(s - 1, 0));
  }

  async function handleSubmit() {
    const allErrors = [0, 1, 2, 3, 4].map(validateStep).reduce((acc, e) => ({ ...acc, ...e }), {});
    setErrors(allErrors);
    if (Object.keys(allErrors).length) {
      toast.error('Há campos pendentes em passos anteriores.');
      return;
    }
    setLoading(true);
    setProgress(0);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      photos.forEach((p) => fd.append('photos', p));
      const data = await api.postForm('/api/campaigns', fd, setProgress);
      toast.success(data.message);
      navigate(`/app/campanhas/${data.campaign.id}`, { state: { justCreated: true } });
    } catch (err) {
      const fe = err.fieldErrors || {};
      setErrors(fe);
      const stepIdx = Object.keys(fe).map((k) => ERROR_STEP[k]).find((s) => s !== undefined);
      if (stepIdx !== undefined) setStep(stepIdx);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  function addPhotos(fileList) {
    const accepted = Array.from(fileList).filter((f) => /^image\/(jpeg|png|webp)$/.test(f.type));
    if (accepted.length === 0) {
      setErrors((e) => ({ ...e, photos: 'Envie imagens JPG, PNG ou WEBP.' }));
      return;
    }
    setPhotos((prev) => [...prev, ...accepted].slice(0, 6));
    setErrors((e) => ({ ...e, photos: undefined }));
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Nova campanha</h1>
          <p className="page-subtitle">Preencha os dados e escreva o texto do anúncio no último passo.</p>
        </div>
      </div>

      <div className="wizard-steps">
        {STEPS.map((s, i) => (
          <button key={s.n} className={`wizard-step ${i === step ? 'current' : ''} ${i < step ? 'done' : ''}`} onClick={() => i < step && setStep(i)} disabled={i > step}>
            <span className="wizard-step-num">{i < step ? '✓' : s.n}</span>
            <span><strong>{s.title}</strong><small>{s.desc}</small></span>
          </button>
        ))}
      </div>

      <div className="card wizard-card">
        {step === 0 && (
          <>
            <h2>1. Dados do produto</h2>
            <div className="form-grid">
              <div className="field span-2">
                <label>Nome / modelo do produto *</label>
                <input value={form.product_name} onChange={(e) => set('product_name', e.target.value)} placeholder="Ex: Toyota Corolla XEi 2.0" className={errors.product_name ? 'invalid' : ''} />
                {errors.product_name && <span className="field-error">{errors.product_name}</span>}
              </div>
              <div className="field"><label>Cor</label><input value={form.color} onChange={(e) => set('color', e.target.value)} placeholder="Ex: Prata" /></div>
              <div className="field"><label>Ano</label><input value={form.year} onChange={(e) => set('year', e.target.value)} placeholder="Ex: 2022" /></div>
              <div className="field"><label>Preço (R$)</label><input value={form.price} onChange={(e) => set('price', e.target.value)} placeholder="Ex: 125000" inputMode="decimal" /></div>
              <div className="field"><label>Quilometragem (veículos)</label><input value={form.km} onChange={(e) => set('km', e.target.value)} placeholder="Ex: 45000" inputMode="numeric" /></div>
              <div className="field"><label>Cidade</label><input value={form.city} onChange={(e) => set('city', e.target.value)} placeholder="Ex: São Paulo" /></div>
              <div className="field"><label>Estado (UF)</label><select value={form.state} onChange={(e) => set('state', e.target.value)}>{UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}</select></div>
              <div className="field span-2">
                <label>Fotos do produto * (até 6 — a primeira é a foto principal)</label>
                <label className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); addPhotos(e.dataTransfer.files); }}>
                  <input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={(e) => addPhotos(e.target.files)} />
                  <span className="dropzone-inner">📷 Arraste fotos aqui ou <strong>clique para selecionar</strong> (JPG, PNG, WEBP — 10MB cada)</span>
                </label>
                {errors.photos && <span className="field-error">{errors.photos}</span>}
                {photoUrls.length > 0 && (
                  <div className="photo-thumbs">
                    {photoUrls.map((url, i) => (
                      <div className="photo-thumb" key={url}>
                        <img src={url} alt={`Foto ${i + 1}`} />
                        <button type="button" className="photo-remove" onClick={() => { URL.revokeObjectURL(url); setPhotos((p) => p.filter((_, idx) => idx !== i)); }} aria-label="Remover foto">✕</button>
                        {i === 0 && <span className="photo-main-tag">Principal</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <h2>2. Dados do vendedor</h2>
            <div className="form-grid">
              <div className="field">
                <label>Nome do vendedor *</label>
                <input value={form.seller_name} onChange={(e) => set('seller_name', e.target.value)} placeholder="Ex: João Silva" className={errors.seller_name ? 'invalid' : ''} />
                {errors.seller_name && <span className="field-error">{errors.seller_name}</span>}
              </div>
              <div className="field">
                <label>WhatsApp de contato *</label>
                <input value={form.whatsapp} onChange={(e) => set('whatsapp', e.target.value)} placeholder="(11) 99999-9999" className={errors.whatsapp ? 'invalid' : ''} />
                <small className="field-hint">Os interessados no anúncio serão direcionados para este número.</small>
                {errors.whatsapp && <span className="field-error">{errors.whatsapp}</span>}
              </div>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h2>3. Configuração da campanha</h2>
            <div className="form-grid">
              {credentials.length > 0 && (
                <div className="field span-2">
                  <label>Integração Meta para publicação</label>
                  <select value={form.credential_id} onChange={(e) => set('credential_id', e.target.value)}>
                    {credentials.map((c) => (
                      <option key={c.id} value={String(c.id)}>{c.name} ({c.adAccountId || 'sem conta'})</option>
                    ))}
                  </select>
                  <small className="field-hint">Somente integrações validadas ("Conectadas") publicam. Configure em Integrações se precisar de outras.</small>
                </div>
              )}
              <div className="field">
                <label>Orçamento diário (R$) *</label>
                <input value={form.daily_budget} onChange={(e) => set('daily_budget', e.target.value)} inputMode="decimal" className={errors.daily_budget ? 'invalid' : ''} />
                <small className="field-hint">Quanto você quer gastar por dia (mínimo R$ 5,00).</small>
                {errors.daily_budget && <span className="field-error">{errors.daily_budget}</span>}
              </div>
              <div className="field">
                <label>Duração da campanha (dias) *</label>
                <input value={form.duration_days} onChange={(e) => set('duration_days', e.target.value)} inputMode="numeric" className={errors.duration_days ? 'invalid' : ''} />
                <small className="field-hint">Total previsto: R$ {(Number(form.daily_budget) * Number(form.duration_days || 0)).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</small>
                {errors.duration_days && <span className="field-error">{errors.duration_days}</span>}
              </div>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <h2>4. Segmentação de público</h2>
            <div className="form-grid">
              <div className="field">
                <label>Idade mínima *</label>
                <input value={form.age_min} onChange={(e) => set('age_min', e.target.value)} inputMode="numeric" className={errors.age_min ? 'invalid' : ''} />
                {errors.age_min && <span className="field-error">{errors.age_min}</span>}
              </div>
              <div className="field">
                <label>Idade máxima *</label>
                <input value={form.age_max} onChange={(e) => set('age_max', e.target.value)} inputMode="numeric" className={errors.age_max ? 'invalid' : ''} />
                {errors.age_max && <span className="field-error">{errors.age_max}</span>}
              </div>
              <div className="field span-2">
                <label>Gênero</label>
                <div className="radio-row">
                  {[['all', 'Todos'], ['male', 'Masculino'], ['female', 'Feminino']].map(([v, label]) => (
                    <label key={v} className={`radio-card ${form.gender === v ? 'selected' : ''}`}>
                      <input type="radio" name="gender" value={v} checked={form.gender === v} onChange={() => set('gender', v)} />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="field span-2">
                <label>Interesses do público (separados por vírgula)</label>
                <input value={form.interests} onChange={(e) => set('interests', e.target.value)} placeholder="Ex: carros, economia familiar, automóveis usados" />
                <small className="field-hint">Aparecerão para pessoas com esses interesses no Facebook/Instagram.</small>
              </div>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <h2>5. Texto do anúncio</h2>
            <p className="page-subtitle">Escreva o título e o texto que aparecerão no Facebook/Instagram. Dica: seja direto, destaque o que o produto tem de melhor e convide o leitor a chamar no WhatsApp.</p>
            <div className="form-grid">
              <div className="field span-2">
                <label>Título do anúncio * <span className="char-count">{form.title.length}/90</span></label>
                <input value={form.title} onChange={(e) => set('title', e.target.value)} maxLength={90} placeholder="Ex: Toyota Corolla XEi 2022 — Oportunidade Imperdível!" className={errors.title ? 'invalid' : ''} />
                {errors.title && <span className="field-error">{errors.title}</span>}
              </div>
              <div className="field span-2">
                <label>Texto do anúncio * <span className="char-count">{form.ad_text.length}/900</span></label>
                <textarea rows={8} value={form.ad_text} onChange={(e) => set('ad_text', e.target.value)} maxLength={900} placeholder={'Ex:\n🔥 Corolla XEi 2022 à pronta entrega em São Paulo!\n🚗 Prata, 45.000 km, único dono.\n💰 R$ 125.000 — aceito troca e financiamento.\n📲 Chame no WhatsApp e agende seu test drive!'} className={errors.ad_text ? 'invalid' : ''} />
                {errors.ad_text && <span className="field-error">{errors.ad_text}</span>}
              </div>
            </div>

            <h2>Revisão</h2>
            <div className="review-grid">
              <div className="review-section">
                <h3>Produto</h3>
                <ul>
                  <li><strong>Produto:</strong> {form.product_name}</li>
                  {form.color && <li><strong>Cor:</strong> {form.color}</li>}
                  {form.year && <li><strong>Ano:</strong> {form.year}</li>}
                  {form.price && <li><strong>Preço:</strong> R$ {form.price}</li>}
                  {form.km && <li><strong>KM:</strong> {form.km}</li>}
                  <li><strong>Local:</strong> {form.city}/{form.state}</li>
                  <li><strong>Fotos:</strong> {photos.length}</li>
                </ul>
                <h3>Vendedor</h3>
                <ul><li><strong>Nome:</strong> {form.seller_name}</li><li><strong>WhatsApp:</strong> {form.whatsapp}</li></ul>
              </div>
              <div className="review-section">
                <h3>Campanha</h3>
                <ul>
                  <li><strong>Orçamento:</strong> R$ {form.daily_budget}/dia × {form.duration_days} dias</li>
                  <li><strong>Investimento total:</strong> R$ {(Number(form.daily_budget) * Number(form.duration_days)).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</li>
                </ul>
                <h3>Público</h3>
                <ul>
                  <li><strong>Idade:</strong> {form.age_min} a {form.age_max} anos</li>
                  <li><strong>Gênero:</strong> {form.gender === 'all' ? 'Todos' : form.gender === 'male' ? 'Masculino' : 'Feminino'}</li>
                  {form.interests && <li><strong>Interesses:</strong> {form.interests}</li>}
                </ul>
              </div>
            </div>
            {loading && (
              <div className="progress-box">
                <div className="progress-label">{progress > 0 ? `Enviando fotos... ${progress}%` : 'Criando campanha...'}</div>
                <div className="progress-bar"><div style={{ width: `${progress || 15}%` }} /></div>
              </div>
            )}
          </>
        )}

        <div className="wizard-footer">
          <button className="btn btn-ghost" onClick={back} disabled={step === 0 || loading}>← Voltar</button>
          {step < 4 ? (
            <button className="btn btn-primary" onClick={next}>Continuar →</button>
          ) : (
            <button className="btn btn-primary btn-lg" onClick={handleSubmit} disabled={loading}>
              {loading ? '⏳ Salvando...' : '✅ Criar campanha'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
