import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Radar } from "lucide-react";
import type { SensorInfo } from "@/components/StatusBar";

export interface LidarScan {
  angles: number[]; // graus, 0 = frente, positivo = esquerda
  ranges: number[]; // metros, 0 = sem leitura
}

interface ObstacleData {
  left: boolean;
  center: boolean;
  right: boolean;
  distances: { left: number; center: number; right: number };
  path_distance?: number;
}

interface Lidar2DViewProps {
  scan?: LidarScan;
  groundObstacles?: ObstacleData;
  sensor?: SensorInfo;
  backendConnected: boolean;
}

// Mesmos setores do backend (ObstacleDetector.SCAN_SECTORS)
const SECTORS: Record<"left" | "center" | "right", [number, number]> = {
  left: [20, 70],
  center: [-20, 20],
  right: [-70, -20],
};
const RANGES = [2, 4, 8];
const TRAIL_SCANS = 12; // quantos scans antigos ficam no "rastro" (~1 s)
const CANVAS = 720;

// Cor do ponto pela distância: perto = vermelho, médio = âmbar, longe = ciano
const pointColor = (r: number) => (r < 0.5 ? "248,113,113" : r < 1.0 ? "251,191,36" : "45,212,191");

export const Lidar2DView = ({ scan, groundObstacles, sensor, backendConnected }: Lidar2DViewProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailRef = useRef<LidarScan[]>([]);
  const updatesRef = useRef<number[]>([]);
  const [maxRange, setMaxRange] = useState(4);
  const [trail, setTrail] = useState(false);
  const [rate, setRate] = useState(0);

  const live = backendConnected && !!scan && scan.angles.length > 0;

  // Guarda os últimos scans (rastro) e mede a taxa de atualização
  useEffect(() => {
    if (!scan) {
      trailRef.current = [];
      return;
    }
    trailRef.current = [scan, ...trailRef.current].slice(0, TRAIL_SCANS);
    const now = performance.now();
    updatesRef.current = [...updatesRef.current.filter((t) => now - t < 2000), now];
  }, [scan]);

  useEffect(() => {
    const id = setInterval(() => {
      const now = performance.now();
      setRate(updatesRef.current.filter((t) => now - t < 2000).length / 2);
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const stats = useMemo(() => {
    if (!scan) return null;
    let valid = 0;
    let nearest: { r: number; deg: number } | null = null;
    scan.ranges.forEach((r, i) => {
      if (!r) return;
      valid++;
      if (!nearest || r < nearest.r) nearest = { r, deg: scan.angles[i] };
    });
    return { valid, nearest: nearest as { r: number; deg: number } | null };
  }, [scan]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const size = CANVAS;
    const c = size / 2;
    const scale = (size / 2 - 16) / maxRange;
    // ângulo do robô -> tela (frente para cima, esquerda para a esquerda)
    const toXY = (deg: number, r: number) => {
      const a = (deg * Math.PI) / 180;
      return [c - r * Math.sin(a) * scale, c - r * Math.cos(a) * scale];
    };

    ctx.clearRect(0, 0, size, size);
    const bg = ctx.createRadialGradient(c, c, 0, c, c, c * 1.1);
    bg.addColorStop(0, "#0c1a2b");
    bg.addColorStop(1, "#050b14");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, size, size);

    // setores frontais usados pela navegação (vermelho = bloqueado)
    if (live) {
      (Object.keys(SECTORS) as (keyof typeof SECTORS)[]).forEach((sector) => {
        const [lo, hi] = SECTORS[sector];
        const blocked = groundObstacles?.[sector];
        const dist = Math.min(groundObstacles?.distances[sector] ?? maxRange, maxRange);
        ctx.beginPath();
        ctx.moveTo(c, c);
        ctx.arc(c, c, dist * scale, -Math.PI / 2 - (hi * Math.PI) / 180, -Math.PI / 2 - (lo * Math.PI) / 180);
        ctx.closePath();
        ctx.fillStyle = blocked ? "rgba(239,68,68,0.22)" : "rgba(34,197,94,0.10)";
        ctx.fill();
      });
    }

    // grade: anéis de distância e raios a cada 30°
    ctx.strokeStyle = "rgba(148,163,184,0.16)";
    ctx.lineWidth = 1;
    for (let deg = 0; deg < 360; deg += 30) {
      const [x, y] = toXY(deg, maxRange);
      ctx.beginPath();
      ctx.moveTo(c, c);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(148,163,184,0.75)";
    ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
    const ringStep = maxRange <= 2 ? 0.5 : 1;
    for (let r = ringStep; r <= maxRange + 1e-6; r += ringStep) {
      ctx.strokeStyle = Number.isInteger(r) ? "rgba(148,163,184,0.32)" : "rgba(148,163,184,0.16)";
      ctx.beginPath();
      ctx.arc(c, c, r * scale, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillText(`${r} m`, c + 4, c - r * scale + 14);
    }
    ctx.fillStyle = "rgba(148,163,184,0.9)";
    ctx.textAlign = "center";
    ctx.fillText("FRENTE", c, 13);
    ctx.textAlign = "start";

    // pontos (mais antigos primeiro, mais apagados)
    if (live) {
      const scans = trail ? [...trailRef.current].reverse() : trailRef.current.slice(0, 1);
      scans.forEach((s, idx) => {
        const age = scans.length - 1 - idx; // 0 = scan atual
        const alpha = age === 0 ? 1 : Math.max(0.08, 0.5 - age * 0.04);
        const dot = age === 0 ? 3.5 : 2.5;
        s.angles.forEach((deg, i) => {
          const r = s.ranges[i];
          if (!r || r > maxRange) return;
          const [x, y] = toXY(deg, r);
          ctx.fillStyle = `rgba(${pointColor(r)},${alpha})`;
          ctx.fillRect(x - dot / 2, y - dot / 2, dot, dot);
        });
      });
    }

    // robô (raio ~0.2 m) e seta da frente
    const robotR = Math.max(6, 0.2 * scale);
    ctx.fillStyle = live ? "#38bdf8" : "#475569";
    ctx.beginPath();
    ctx.arc(c, c, robotR, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(c, c);
    ctx.lineTo(c, c - robotR - 10);
    ctx.stroke();
    ctx.lineWidth = 1;
  }, [scan, groundObstacles, maxRange, trail, live]);

  const status = !backendConnected
    ? { badge: "SEM BACKEND", variant: "secondary" as const }
    : live
      ? { badge: sensor?.kind === "sim" ? "SIMULADO" : "AO VIVO", variant: "default" as const }
      : { badge: "AGUARDANDO", variant: "outline" as const };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Radar className="h-5 w-5 text-primary" />
              Mapa de pontos · LiDAR 2D
              {sensor?.name && <span className="text-sm font-normal text-muted-foreground">({sensor.name})</span>}
            </CardTitle>
            <CardDescription>Vista de cima, frente do robô para cima</CardDescription>
          </div>
          <Badge variant={status.variant}>{status.badge}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="relative mx-auto aspect-square w-full max-w-[560px] overflow-hidden rounded-lg border border-border">
          <canvas ref={canvasRef} width={CANVAS} height={CANVAS} className="h-full w-full" />

          {!live && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/55 p-6 backdrop-blur-[1px]">
              <div className="max-w-xs text-center">
                <div className="relative mx-auto mb-4 h-16 w-16">
                  <span className="absolute inset-0 animate-ping rounded-full bg-primary/25" />
                  <span className="relative flex h-16 w-16 items-center justify-center rounded-full border border-primary/40 bg-background/80">
                    <Radar className="h-7 w-7 text-primary" />
                  </span>
                </div>
                <p className="font-semibold">Aguardando o LiDAR 2D</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {!backendConnected
                    ? "O backend não está rodando. Inicie com ./start.sh (ou ./start.sh --sim)."
                    : "Conecte o LiDAR (LD06/LD19 ou RPLIDAR) na USB. Os pontos aparecem aqui assim que chegarem as leituras."}
                </p>
                {backendConnected && (
                  <div className="mt-3 text-xs text-muted-foreground">
                    Não detectou? Escolha o modelo e a porta:
                    <code className="mt-1 block whitespace-nowrap rounded bg-muted px-2 py-1 text-[11px]">
                      ./start.sh --lidar ld06 --lidar-port /dev/ttyUSB0
                    </code>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          <Stat label="Pontos" value={live && stats ? `${stats.valid}` : "—"} />
          <Stat label="Taxa" value={live ? `${rate.toFixed(0)} Hz` : "—"} />
          <Stat
            label="Mais perto"
            value={live && stats?.nearest ? `${stats.nearest.r.toFixed(2)} m` : "—"}
            hint={live && stats?.nearest ? `${Math.round(stats.nearest.deg)}°` : undefined}
          />
          <Stat
            label="Livre à frente"
            value={
              !live || groundObstacles?.path_distance === undefined
                ? "—"
                : groundObstacles.path_distance >= 9.9 // backend usa 10 m para "nada no caminho"
                  ? "livre"
                  : `${groundObstacles.path_distance.toFixed(2)} m`
            }
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Switch id="lidar-trail" checked={trail} onCheckedChange={setTrail} />
            <Label htmlFor="lidar-trail" className="text-sm">Rastro (~1 s)</Label>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 text-xs text-muted-foreground md:flex">
              <Legend color="bg-red-400" label="< 0,5 m" />
              <Legend color="bg-amber-400" label="< 1 m" />
              <Legend color="bg-teal-400" label="longe" />
            </div>
            <div className="flex gap-1">
              {RANGES.map((r) => (
                <Button key={r} size="sm" variant={r === maxRange ? "default" : "outline"} onClick={() => setMaxRange(r)}>
                  {r} m
                </Button>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const Stat = ({ label, value, hint }: { label: string; value: string; hint?: string }) => (
  <div className="rounded-md border border-border bg-muted/50 px-3 py-2">
    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="tabular font-semibold">
      {value}
      {hint && <span className="ml-1 text-xs font-normal text-muted-foreground">{hint}</span>}
    </div>
  </div>
);

const Legend = ({ color, label }: { color: string; label: string }) => (
  <span className="flex items-center gap-1">
    <span className={`h-2 w-2 rounded-sm ${color}`} />
    {label}
  </span>
);
