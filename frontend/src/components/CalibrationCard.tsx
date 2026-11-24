import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChevronDown, ChevronUp, RotateCcw, SlidersHorizontal } from "lucide-react";

export interface Calibration {
  ganhos: number[]; // força de M1 (trás-esquerda), M2 (frente), M3 (trás-direita)
  correcao_lateral: number; // fração da velocidade; + empurra para a direita
  correcao_giro: number; // fração da velocidade; + gira no sentido horário
  teclas?: Record<string, number[]>; // teclas com PWM ajustado à mão (nível 60)
  tabela?: Record<string, number[]>; // o que cada tecla envia agora (nível 60)
  limites?: {
    pwm_min_base: number; pwm_max_base: number; nivel_base: number; nivel_min: number; nivel_max: number;
    razao_max_ganhos: number; pwm_teto: number;
  };
}

interface CalibrationCardProps {
  calibration?: Calibration;
  onChange: (change: Partial<Pick<Calibration, "ganhos" | "correcao_lateral" | "correcao_giro">>) => void;
  onKeyPwm: (key: string, pwm: number[] | null) => void; // null: volta à conta da cinemática
  onReset: () => void;
  disabled: boolean;
}

const MOTORS = ["M1 · trás-esquerda", "M2 · frente", "M3 · trás-direita"];

// Ordem do teclado numérico, com o giro no fim
const KEY_ROWS: { key: string; label: string }[] = [
  { key: "7", label: "7 ↖" }, { key: "8", label: "8 ↑" }, { key: "9", label: "9 ↗" },
  { key: "4", label: "4 ←" }, { key: "6", label: "6 →" },
  { key: "1", label: "1 ↙" }, { key: "2", label: "2 ↓" }, { key: "3", label: "3 ↘" },
  { key: "ccw", label: "Q ↺" }, { key: "cw", label: "E ↻" },
];

// Ajusta como o sistema calcula o PWM de cada motor (backend/kinematics.py). Vale na hora e fica gravado em
// backend/calibracao_robo.json.
export const CalibrationCard = ({ calibration, onChange, onKeyPwm, onReset, disabled }: CalibrationCardProps) => {
  const [open, setOpen] = useState(false);
  const [gains, setGains] = useState<number[]>(calibration?.ganhos ?? [1.1, 2, 1]);
  const [lateral, setLateral] = useState(calibration?.correcao_lateral ?? 0);
  const [spin, setSpin] = useState(calibration?.correcao_giro ?? 0);
  const [table, setTable] = useState<Record<string, string[]>>({});

  // O backend é quem manda o valor válido (também depois de um valor recusado)
  useEffect(() => {
    if (!calibration) return;
    setGains(calibration.ganhos);
    setLateral(calibration.correcao_lateral);
    setSpin(calibration.correcao_giro);
    setTable(Object.fromEntries(Object.entries(calibration.tabela ?? {}).map(([k, v]) => [k, v.map(String)])));
  }, [calibration]);

  const setCell = (key: string, i: number, value: string) =>
    setTable((t) => ({ ...t, [key]: (t[key] ?? ["0", "0", "0"]).map((x, k) => (k === i ? value : x)) }));

  // Ao sair do campo (ou Enter): se o valor mudou, grava o ajuste desta tecla
  const commitRow = (key: string) => {
    const now = (table[key] ?? []).map((v) => Number(v));
    const cur = calibration?.tabela?.[key];
    if (now.length === 3 && now.every((v) => Number.isFinite(v)) && cur && now.some((v, i) => v !== cur[i])) {
      onKeyPwm(key, now);
    }
  };

  const lim = calibration?.limites;
  const set = (i: number, v: number) => setGains((g) => g.map((x, k) => (k === i ? v : x)));

  return (
    <Card>
      <CardHeader className="pb-3">
        <button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen(!open)}>
          <CardTitle className="flex items-center gap-2 text-base">
            <SlidersHorizontal className="h-5 w-5 text-primary" />
            Calibração dos motores
          </CardTitle>
          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </CardHeader>
      {open && (
        <CardContent className="space-y-5 text-sm">
          {lim && (
            <p className="text-xs text-muted-foreground">
              Na velocidade {lim.nivel_base} os motores trabalham entre {lim.pwm_min_base} (o mais forte) e {lim.pwm_max_base} (o
              mais fraco); a diferença máxima entre motores é {lim.razao_max_ganhos}:1. Em velocidade {lim.nivel_max} esses
              limites sobem para {Math.round((lim.pwm_min_base * lim.nivel_max) / lim.nivel_base)} e{" "}
              {Math.round((lim.pwm_max_base * lim.nivel_max) / lim.nivel_base)}.
            </p>
          )}

          <div className="space-y-3">
            <div className="font-medium">Força de cada motor</div>
            {MOTORS.map((name, i) => (
              <div key={name} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span>{name}</span>
                  <span className="tabular font-semibold">{gains[i]?.toFixed(2)}</span>
                </div>
                <Slider
                  value={[gains[i] ?? 1]}
                  min={1}
                  max={2}
                  step={0.05}
                  disabled={disabled}
                  onValueChange={(v) => set(i, v[0])}
                  onValueCommit={(v) => onChange({ ganhos: gains.map((x, k) => (k === i ? v[0] : x)) })}
                />
              </div>
            ))}
            <p className="text-[11px] text-muted-foreground">
              Só a proporção importa: motor mais forte recebe menos PWM. Se ao ir para frente ele puxa para a esquerda, a
              esquerda está rendendo mais que o valor aqui: suba M1.
            </p>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium">Correção lateral (frente/trás)</span>
              <span className="tabular font-semibold">{lateral > 0 ? "→ " : lateral < 0 ? "← " : ""}{Math.abs(lateral * 100).toFixed(0)}%</span>
            </div>
            <Slider value={[lateral]} min={-0.5} max={0.5} step={0.01} disabled={disabled}
              onValueChange={(v) => setLateral(v[0])} onValueCommit={(v) => onChange({ correcao_lateral: v[0] })} />
            <p className="text-[11px] text-muted-foreground">Positivo empurra para a direita (use se ainda puxa para a esquerda). Atua só pelas rodas de trás.</p>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium">Correção de giro</span>
              <span className="tabular font-semibold">{(spin * 100).toFixed(0)}%</span>
            </div>
            <Slider value={[spin]} min={-0.5} max={0.5} step={0.01} disabled={disabled}
              onValueChange={(v) => setSpin(v[0])} onValueCommit={(v) => onChange({ correcao_giro: v[0] })} />
            <p className="text-[11px] text-muted-foreground">Positivo gira no sentido horário enquanto anda (use se ele curva para a esquerda em vez de ir reto).</p>
          </div>

          <div className="space-y-2">
            <div className="font-medium">Valores por tecla (velocidade {lim?.nivel_base ?? 60})</div>
            <p className="text-[11px] text-muted-foreground">
              O que cada tecla envia aos motores. Edite um valor para acertar aquela tecla na prática: vale na hora, escala
              com a velocidade e fica gravado. Cada motor: 0 ou de {lim?.pwm_min_base ?? 50} a {lim?.pwm_max_base ?? 100}.
              Ao mexer, a linha vira <span className="font-semibold">manual</span>; <RotateCcw className="inline h-3 w-3" /> volta à conta.
            </p>
            <div className="grid grid-cols-[3.5rem_repeat(3,minmax(0,1fr))_1.75rem] items-center gap-1.5 text-[11px] text-muted-foreground">
              <span />
              <span className="text-center">M1</span>
              <span className="text-center">M2</span>
              <span className="text-center">M3</span>
              <span />
            </div>
            {KEY_ROWS.map(({ key, label }) => {
              const manual = !!calibration?.teclas?.[key];
              return (
                <div key={key} className="grid grid-cols-[3.5rem_repeat(3,minmax(0,1fr))_1.75rem] items-center gap-1.5">
                  <span className="text-xs font-medium">
                    {label}
                    {manual && <span className="ml-1 rounded bg-primary/15 px-1 text-[9px] text-primary">manual</span>}
                  </span>
                  {[0, 1, 2].map((i) => (
                    <Input
                      key={i}
                      type="number"
                      inputMode="numeric"
                      value={table[key]?.[i] ?? ""}
                      disabled={disabled}
                      onChange={(e) => setCell(key, i, e.target.value)}
                      onBlur={() => commitRow(key)}
                      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                      className="h-8 px-1.5 text-center text-xs tabular"
                    />
                  ))}
                  <button
                    className="flex h-8 w-7 items-center justify-center rounded text-muted-foreground hover:text-foreground disabled:opacity-30"
                    disabled={disabled || !manual}
                    title="Voltar ao valor da conta"
                    onClick={() => onKeyPwm(key, null)}
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })}
            <p className="text-[11px] text-muted-foreground">
              Se ao andar de lado (4/6) ele <span className="font-medium">gira no sentido horário</span> enquanto anda: reduza M1 e M3
              (ou suba M2); se gira anti-horário, o contrário. A soma de M1+M2+M3 perto de zero (em sentidos opostos) evita girar.
            </p>
          </div>

          <Button variant="outline" size="sm" onClick={onReset} disabled={disabled}>
            Voltar aos valores iniciais
          </Button>
        </CardContent>
      )}
    </Card>
  );
};
