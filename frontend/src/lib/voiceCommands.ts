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

export const identifyVoiceCommand = (text: string): VoiceCommandId | null => {
  const t = normalize(text);
  // "para" só vale no fim da frase ("Para!"), para não disparar com "vai para a frente"
  if (/\b(parar|pare|stop)\b|\bpara\b\s*(?:[.!?,]|$)/.test(t)) return 'parar';
  const dir = t.match(/(?:vai|anda|va) (?:pra|para) a? ?(frente|tras|direita|esquerda)/);
  if (dir) return dir[1] as VoiceCommandId;
  if (/\bme segue\b/.test(t)) return 'me_segue';
  if (/meia volta/.test(t)) return 'meia_volta';
  if (/volta completa/.test(t)) return 'volta_completa';
  const side = t.match(/fica do meu lado (direito|esquerdo)/);
  if (side) return `lado_${side[1]}` as VoiceCommandId;
  if (/\bautonomo\b/.test(t)) return 'autonomo';
  if (/\bmanual\b/.test(t)) return 'manual';
  return null;
};
