/** Cliente da API: fetch com cookies, JSON e mensagens de erro amigáveis. */
async function request(path, { method = 'GET', body, formData, onProgress } = {}) {
  const opts = { method, credentials: 'same-origin', headers: {} };
  if (formData) {
    opts.body = formData;
    if (onProgress && typeof XMLHttpRequest !== 'undefined') {
      return xhrPromise(path, opts, onProgress);
    }
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new ApiError('Não foi possível conectar ao servidor. Verifique se a API está rodando.', 0, {});
  }
  return handleResponse(res);
}

function xhrPromise(path, opts, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(opts.method, path);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let data = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* resposta não-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(data.error || `Erro ${xhr.status}`, xhr.status, data));
    };
    xhr.onerror = () => reject(new ApiError('Falha de rede durante o envio.', 0, {}));
    xhr.send(opts.body);
  });
}

async function handleResponse(res) {
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* corpo vazio */
  }
  if (res.status >= 200 && res.status < 300) return data;
  throw new ApiError(data.error || `Erro ${res.status}`, res.status, data);
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data || {};
  }
  get fieldErrors() {
    return this.data?.errors || null;
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  postForm: (path, formData, onProgress) => request(path, { method: 'POST', formData, onProgress }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
};

export const AUTH_PATHS = {
  login: '/login',
  dashboard: '/app/dashboard',
};

export function formatBRL(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 2 });
}

export function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}
