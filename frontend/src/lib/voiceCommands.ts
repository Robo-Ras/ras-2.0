// Comandos de voz do painel (reconhecimento nativo do Chrome). Mesmo dicionário e mesma lógica do José
// (voz/comandos.py): as palavras e variações ficam em comandos_voz.json, na raiz do projeto.
// Formato de uso: "José, <comando>"; "pare"/"para" também valem sozinhos.
import dictionary from '../../../comandos_voz.json';

export type VoiceCommandId =
  | 'frente' | 'tras' | 'direita' | 'esquerda' | 'gira' | 'parar'
  | 'meia_volta' | 'volta_completa' | 'me_segue' | 'lado_direito' | 'lado_esquerdo'
  | 'autonomo' | 'manual';

export interface VoiceCommandEvent {
  command: string;
  text: string;
  source: 'jose' | 'browser' | string;
  status: 'ok' | 'no_robot' | 'not_implemented' | 'duplicate' | 'unknown' | string;
}

// Rótulos dos comandos do dicionário vêm do JSON; os outros ids ainda aparecem se o backend os mandar
const EXTRA_LABELS: Record<string, string> = {
  meia_volta: 'Dê Meia Volta',
  volta_completa: 'Dê Volta Completa',
  me_segue: 'Me Segue',
  lado_direito: 'Fica do Meu Lado Direito',
  lado_esquerdo: 'Fica do Meu Lado Esquerdo',
  autonomo: 'Modo Autônomo',
  manual: 'Modo Manual',
};

export const voiceCommandLabel = (command: string): string => {
  const entry = (dictionary.comandos as Record<string, { rotulo: string }>)[command]
    ?? (dictionary.pedidos as Record<string, { rotulo: string }>)[command];
  return entry?.rotulo ?? EXTRA_LABELS[command] ?? command;
};

// ---- Interpretação (espelho de voz/comandos.py) ----

export interface Heard {
  called: boolean; // chamou o José na frase
  command: string | null; // id do comando ("frente", "parar") ou do pedido ("conversa")
  type: 'comando' | 'pedido' | null; // "pedido" é do próprio José (o painel não atende)
  withoutCall: boolean; // tinha palavra de comando, mas faltou o "José"
}

const MAX_AFTER_JOSE = 5; // quantas palavras depois do "José" ainda contam
const FUZZY_CUT = 0.8; // semelhança mínima para aceitar uma variação não listada (palavras com 5+ letras)
const FUZZY_CUT_JOSE = 0.75; // "jome", "jone", "joze"
const MIN_FUZZY_LETTERS = 5;

export const normalize = (text: string): string =>
  text
    .toLowerCase()
    .replace('[unk]', ' unk ')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9 ]+/g, ' ');

const tokens = (text: string): string[] => normalize(text).split(/\s+/).filter(Boolean);

// Semelhança de duas palavras: mesma medida do difflib.SequenceMatcher.ratio() do Python
// (maior trecho em comum, repetido dos dois lados), para o Chrome e o José decidirem igual.
const matchingChars = (a: string, b: string): number => {
  if (!a.length || !b.length) return 0;
  let best = 0;
  let ai = 0;
  let bi = 0;
  for (let i = 0; i < a.length; i++) {
    for (let j = 0; j < b.length; j++) {
      let k = 0;
      while (i + k < a.length && j + k < b.length && a[i + k] === b[j + k]) k++;
      if (k > best) {
        best = k;
        ai = i;
        bi = j;
      }
    }
  }
  if (!best) return 0;
  return best + matchingChars(a.slice(0, ai), b.slice(0, bi)) + matchingChars(a.slice(ai + best), b.slice(bi + best));
};
const ratio = (a: string, b: string): number => (a.length + b.length ? (2 * matchingChars(a, b)) / (a.length + b.length) : 1);

const callWords = new Set(dictionary.chamar.map(normalize));
const ignored = new Set(dictionary.ignorar.map(normalize));
const ambiguous = new Set(dictionary.comandos.parar._ambiguas.map(normalize));
const words = new Map<string, ['comando' | 'pedido', string]>();
for (const [kind, group] of [['comando', dictionary.comandos], ['pedido', dictionary.pedidos]] as const) {
  for (const [id, item] of Object.entries(group as Record<string, { palavras: string[] }>)) {
    for (const word of item.palavras) words.set(normalize(word), [kind, id]);
  }
}
const fuzzyKeys = [...words.keys()].filter((w) => w.length >= MIN_FUZZY_LETTERS);

const lookup = (token: string): ['comando' | 'pedido', string] | null => {
  if (ignored.has(token) || callWords.has(token)) return null;
  const exact = words.get(token);
  if (exact || token.length < MIN_FUZZY_LETTERS) return exact ?? null;
  let best: string | null = null;
  let bestScore = 0;
  for (const key of fuzzyKeys) {
    const score = ratio(token, key);
    // empate: vale a palavra "maior" (como o difflib.get_close_matches)
    if (score >= FUZZY_CUT && (score > bestScore || (score === bestScore && best !== null && key > best))) {
      best = key;
      bestScore = score;
    }
  }
  return best ? words.get(best) ?? null : null;
};

const isCall = (token: string): boolean =>
  callWords.has(token) || (token.length >= 4 && ratio(token, 'jose') >= FUZZY_CUT_JOSE);

const firstCommand = (list: string[]): ['comando' | 'pedido', string] | null => {
  const found = list.map((word) => ({ word, hit: lookup(word) })).filter((x) => x.hit);
  for (let n = 0; n < found.length; n++) {
    const [, id] = found[n].hit!;
    const restHasCommand = found.slice(n + 1).some((x) => x.hit![1] !== 'parar');
    if (id === 'parar' && ambiguous.has(found[n].word) && restHasCommand) continue; // "vai para frente"
    return found[n].hit!;
  }
  return null;
};

/** O que a frase pede. `called`: o José já foi chamado antes (a palavra de comando já basta). */
export const interpretVoice = (text: string, called = false): Heard => {
  const list = tokens(text);
  for (let i = 0; i < list.length; i++) {
    if (isCall(list[i])) {
      const hit = firstCommand(list.slice(i + 1, i + 1 + MAX_AFTER_JOSE));
      return { called: true, command: hit?.[1] ?? null, type: hit?.[0] ?? null, withoutCall: false };
    }
  }
  if (called) {
    const hit = firstCommand(list);
    return { called: false, command: hit?.[1] ?? null, type: hit?.[0] ?? null, withoutCall: false };
  }
  // Sem "José": só um "pare"/"para" dito sozinho (o "para" de frases comuns não pode parar o robô)
  if (list.length === 1) {
    const only = lookup(list[0]);
    if (only && only[0] === 'comando' && only[1] === 'parar') {
      return { called: false, command: 'parar', type: 'comando', withoutCall: false };
    }
  }
  return { called: false, command: null, type: null, withoutCall: list.some((w) => lookup(w)) };
};

export const exampleCases = dictionary.exemplos as [string, string | null][];
