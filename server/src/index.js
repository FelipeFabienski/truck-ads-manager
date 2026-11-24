import { createApp } from './app.js';
import { config } from './config.js';

const app = createApp();
app.listen(config.port, () => {
  console.log(`🚀 Facilitador de Anúncios — API em http://localhost:${config.port}`);
  console.log(`   Ambiente: ${config.env} · Textos dos anúncios: escritos pelo usuário · Emails: ${config.smtp.host ? 'SMTP' : 'modo dev (outbox local)'}`);
});
