import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";

export interface Calibration {
  ganhos: number[]; // força de M1 (trás-esquerda), M2 (frente), M3 (trás-direita)
  correcao_lateral: number; // fração da velocidade; + empurra para a direita
  correcao_giro: number; // fração da velocidade; + gira no sentido horário
  limites?: {
    pwm_min_base: number; pwm_max_base: number; nivel_base: number; nivel_min: number; nivel_max: number;
    razao_max_ganhos: number; pwm_teto: number;
  };
}

interface CalibrationCardProps {
  calibration?: Calibration;
  onChange: (change: Partial<Pick<Calibration, "ganhos" | "correcao_lateral" | "correcao_giro">>) => void;
  onReset: () => void;
  disabled: boolean;
}

const MOTORS = ["M1 · trás-esquerda", "M2 · frente", "M3 · trás-direita"];

// Ajusta como o sistema calcula o PWM de cada motor (backend/kinematics.py). Vale na hora e fica gravado em
// backend/calibracao_robo.json.
export const CalibrationCard = ({ calibration, onChange, onReset, disabled }: CalibrationCardProps) => {
  const [open, setOpen] = useState(false);
  const [gains, setGains] = useState<number[]>(calibration?.ganhos ?? [1.1, 2, 1]);
  const [lateral, setLateral] = useState(calibration?.correcao_lateral ?? 0);
  const [spin, setSpin] = useState(calibration?.correcao_giro ?? 0);

  // O backend é quem manda o valor válido (também depois de um valor recusado)
  useEffect(() => {
    if (!calibration) return;
    setGains(calibration.ganhos);
    setLateral(calibration.correcao_lateral);
    setSpin(calibration.correcao_giro);
  }, [calibration]);

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

          <Button variant="outline" size="sm" onClick={onReset} disabled={disabled}>
            Voltar aos valores iniciais
          </Button>
        </CardContent>
      )}
    </Card>
  );
};
