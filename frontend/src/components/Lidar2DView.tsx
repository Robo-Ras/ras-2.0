import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Radar } from "lucide-react";

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
  sensorName?: string;
  online?: boolean;
}

// Mesmos setores do backend (ObstacleDetector.SCAN_SECTORS)
const SECTORS: Record<"left" | "center" | "right", [number, number]> = {
  left: [20, 70],
  center: [-20, 20],
  right: [-70, -20],
};
const RANGES = [2, 4, 8];

export const Lidar2DView = ({ scan, groundObstacles, sensorName = "LiDAR 2D", online }: Lidar2DViewProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [maxRange, setMaxRange] = useState(4);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const size = canvas.width;
    const c = size / 2;
    const scale = (size / 2 - 10) / maxRange;
    // ângulo do robô -> tela (frente para cima, esquerda para a esquerda)
    const toXY = (deg: number, r: number) => {
      const a = (deg * Math.PI) / 180;
      return [c - r * Math.sin(a) * scale, c - r * Math.cos(a) * scale];
    };

    ctx.fillStyle = "#0b1220";
    ctx.fillRect(0, 0, size, size);

    // setores frontais (vermelho = bloqueado)
    (Object.keys(SECTORS) as (keyof typeof SECTORS)[]).forEach((sector) => {
      const [lo, hi] = SECTORS[sector];
      const blocked = groundObstacles?.[sector];
      const dist = Math.min(groundObstacles?.distances[sector] ?? maxRange, maxRange);
      ctx.beginPath();
      ctx.moveTo(c, c);
      ctx.arc(c, c, dist * scale, -Math.PI / 2 - (hi * Math.PI) / 180, -Math.PI / 2 - (lo * Math.PI) / 180);
      ctx.closePath();
      ctx.fillStyle = blocked ? "rgba(239,68,68,0.28)" : "rgba(34,197,94,0.14)";
      ctx.fill();
    });

    // anéis de distância
    ctx.strokeStyle = "rgba(148,163,184,0.35)";
    ctx.fillStyle = "rgba(148,163,184,0.8)";
    ctx.font = "11px sans-serif";
    const ringStep = maxRange <= 2 ? 0.5 : 1;
    for (let r = ringStep; r <= maxRange; r += ringStep) {
      ctx.beginPath();
      ctx.arc(c, c, r * scale, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillText(`${r}m`, c + 3, c - r * scale + 12);
    }
    ctx.beginPath();
    ctx.moveTo(c, 0);
    ctx.lineTo(c, size);
    ctx.moveTo(0, c);
    ctx.lineTo(size, c);
    ctx.stroke();

    // pontos
    if (scan) {
      ctx.fillStyle = "#facc15";
      scan.angles.forEach((deg, i) => {
        const r = scan.ranges[i];
        if (!r || r > maxRange) return;
        const [x, y] = toXY(deg, r);
        ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
      });
    }

    // robô (raio ~0.2 m) e seta da frente
    ctx.fillStyle = "#3b82f6";
    ctx.beginPath();
    ctx.arc(c, c, Math.max(4, 0.2 * scale), 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(c, c);
    ctx.lineTo(c, c - Math.max(10, 0.35 * scale));
    ctx.stroke();
    ctx.lineWidth = 1;
  }, [scan, groundObstacles, maxRange]);

  const isOnline = online ?? !!scan;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Radar className="h-5 w-5" />
              {sensorName}
            </CardTitle>
            <CardDescription>Vista de cima, frente do robô para cima</CardDescription>
          </div>
          <Badge variant={isOnline ? "default" : "secondary"}>{isOnline ? "ONLINE" : "OFFLINE"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="mx-auto w-full max-w-md">
          <canvas ref={canvasRef} width={480} height={480} className="w-full h-auto rounded-lg" />
        </div>
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="text-muted-foreground">
            {groundObstacles?.path_distance !== undefined
              ? `Caminho livre à frente: ${groundObstacles.path_distance.toFixed(2)} m`
              : isOnline
                ? "Sem dados de obstáculos"
                : "Aguardando dados do LiDAR..."}
          </span>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <Button key={r} size="sm" variant={r === maxRange ? "default" : "outline"} onClick={() => setMaxRange(r)}>
                {r}m
              </Button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
