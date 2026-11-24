/**
 * Status das integrações Meta (conforme especificação):
 * Pendente de validação · Conectado · Token expirado · Permissões insuficientes ·
 * Erro de conexão · Desativado.
 */
const LABELS = {
  pending: { label: 'Pendente de validação', cls: 'badge-paused' },
  connected: { label: 'Conectado', cls: 'badge-active' },
  token_expired: { label: 'Token expirado', cls: 'badge-error' },
  insufficient_permissions: { label: 'Permissões insuficientes', cls: 'badge-error' },
  connection_error: { label: 'Erro de conexão', cls: 'badge-error' },
};

export default function IntegrationStatusBadge({ status, isActive = true }) {
  if (!isActive) {
    return <span className="badge badge-draft">Desativado</span>;
  }
  const s = LABELS[status] || { label: status, cls: 'badge-draft' };
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}
