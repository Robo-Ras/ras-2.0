// Mesmo vocabulário do assistente José (voz/jose.py): o backend recebe só o id do comando
// em {type: 'voice_command'} e decide o movimento.

export type VoiceCommandId =
  | 'frente' | 'tras' | 'direita' | 'esquerda'
  | 'meia_volta' | 'volta_completa'
  | 'me_segue' | 'lado_direito' | 'lado_esquerdo'
  | 'parar' | 'autonomo' | 'manual';

export interface VoiceCommandEvent {
  command: string;
  text: string;
  source: 'jose' | 'browser' | string;
  status: 'ok' | 'no_robot' | 'not_implemented' | 'unknown' | string;
}

export const VOICE_COMMAND_LABELS: Record<VoiceCommandId, string> = {
  frente: 'Vai pra Frente',
  tras: 'Vai pra Trás',
  direita: 'Vai pra Direita',
  esquerda: 'Vai pra Esquerda',
  meia_volta: 'Dê Meia Volta',
  volta_completa: 'Dê Volta Completa',
  me_segue: 'Me Segue',
  lado_direito: 'Fica do Meu Lado Direito',
  lado_esquerdo: 'Fica do Meu Lado Esquerdo',
  parar: 'Parar',
  autonomo: 'Modo Autônomo',
  manual: 'Modo Manual',
};

export const voiceCommandLabel = (command: string) =>
  VOICE_COMMAND_LABELS[command as VoiceCommandId] ?? command;

const normalize = (text: string) =>
  text.toLowerCase().trim().normalize('NFKD').replace(/[̀-ͯ]/g, '');

// Palavra-chave de cada direção: vale a palavra ("frente"), não a frase ("vai pra frente").
// Se tiver mais de uma na frase, vale a primeira que aparecer. Mesmo vocabulário do voz/jose.py.
const DIRECTION_KEYWORDS: [RegExp, VoiceCommandId][] = [
  [/\b(frente|avanc\w*)\b/, 'frente'],
  [/\b(a?tras|re|recu\w*)\b/, 'tras'],
  [/\bdireita\b/, 'direita'],
  [/\besquerda\b/, 'esquerda'],
];

export const identifyVoiceCommand = (text: string): VoiceCommandId | null => {
  const t = normalize(text);
  // "para" só vale no fim da frase ("Para!"), para não disparar com "vai para a frente"
  if (/\b(parar|pare|stop)\b|\bpara\b\s*(?:[.!?,]|$)/.test(t)) return 'parar';
  if (/\bmeia volta\b/.test(t)) return 'meia_volta';
  if (/\bvolta completa\b/.test(t)) return 'volta_completa';
  if (/\bsegue\b/.test(t)) return 'me_segue';
  const side = t.match(/\blado\b.*\b(direit[oa]|esquerd[oa])\b/);
  if (side) return side[1].startsWith('direit') ? 'lado_direito' : 'lado_esquerdo';
  const found = DIRECTION_KEYWORDS.map(([re, id]) => ({ id, at: t.search(re) })).filter((k) => k.at >= 0);
  if (found.length) return found.reduce((a, b) => (b.at < a.at ? b : a)).id;
  if (/\bautonomo\b/.test(t)) return 'autonomo';
  if (/\bmanual\b/.test(t)) return 'manual';
  return null;
};
