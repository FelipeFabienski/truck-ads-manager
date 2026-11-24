const STATUS = {
  draft: { label: 'Rascunho', cls: 'badge-draft' },
  paused: { label: 'Pausado', cls: 'badge-paused' },
  active: { label: 'Ativo', cls: 'badge-active' },
};

export default function StatusBadge({ status }) {
  const s = STATUS[status] || { label: status, cls: '' };
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}
