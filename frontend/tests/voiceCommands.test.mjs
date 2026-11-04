// Confere que o Chrome (src/lib/voiceCommands.ts) entende o dicionário igual ao José (voz/comandos.py).
// Uso: node tests/voiceCommands.test.mjs <arquivo .mjs gerado pelo esbuild>
import { pathToFileURL } from 'node:url';

const mod = await import(pathToFileURL(process.argv[2]).href);
const { interpretVoice, exampleCases, voiceCommandLabel } = mod;
let failures = 0;
const check = (label, got, expected) => {
  const ok = JSON.stringify(got) === JSON.stringify(expected);
  if (!ok) {
    failures++;
    console.log(`ERRO ${label}: veio ${JSON.stringify(got)}, esperado ${JSON.stringify(expected)}`);
  }
};

// os mesmos exemplos do dicionário que o Python confere
for (const [text, expected] of exampleCases) check(text, interpretVoice(text).command, expected);

// regras (espelho de voz/tests/test_escuta.py)
check('andar exige José', interpretVoice('frente').command, null);
check('sem José avisa', interpretVoice('frente').withoutCall, true);
check('chamado: a palavra basta', interpretVoice('esquerda', true).command, 'esquerda');
check('pare sozinho', interpretVoice('pare').command, 'parar');
check('para sozinho', interpretVoice('para').command, 'parar');
for (const talk of ['eu vou para casa', 'vamos para a sala', 'pare de falar comigo'])
  check(talk, interpretVoice(talk).command, null);
check('para frente não é parar', interpretVoice('José vai para frente').command, 'frente');
check('primeira palavra vale', interpretVoice('José esquerda depois frente').command, 'esquerda');
for (const [text, id] of [['José frenti', 'frente'], ['jone direita', 'direita'], ['José atras', 'tras'], ['José recua', 'tras'], ['José rodar', 'gira'], ['josé dirá', 'gira']])
  check(text, interpretVoice(text).command, id);
check('pedido do José', [interpretVoice('José, conversa').command, interpretVoice('José, conversa').type], ['conversa', 'pedido']);
check('rótulo', voiceCommandLabel('frente'), 'Vai pra Frente');

if (failures) {
  console.log(`${failures} falha(s)`);
  process.exit(1);
}
console.log(`ok: ${exampleCases.length} exemplos do dicionário + regras`);
