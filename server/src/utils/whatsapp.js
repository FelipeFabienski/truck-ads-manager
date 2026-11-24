/**
 * Monta o link wa.me com mensagem pré-preenchida para o anúncio.
 * Construção estrita (anti-SSRF/injeção): apenas dígitos validados, protocolo
 * https e host wa.me em allowlist — o valor sai daqui já pronto para uso seguro.
 */
export function whatsappUrl(whatsapp, productName) {
  const digits = String(whatsapp || '').replace(/\D/g, '');
  if (digits.length < 10 || digits.length > 15) {
    throw new Error('Número de WhatsApp inválido para o link do anúncio.');
  }
  const url = new URL(`https://wa.me/${digits}`);
  url.searchParams.set('text', `Olá! Vi o anúncio do ${productName} no Facebook/Instagram e quero saber mais.`);
  // Verificação de allowlist antes de o valor fluir para qualquer requisição
  if (
    url.protocol !== 'https:' ||
    url.hostname !== 'wa.me' ||
    !/^\d{10,15}$/.test(url.pathname.slice(1))
  ) {
    throw new Error('Link de WhatsApp inválido.');
  }
  return url.toString();
}
