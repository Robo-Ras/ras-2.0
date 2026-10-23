import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ShieldAlert } from "lucide-react";

export interface ObstacleData {
  left: boolean;
  center: boolean;
  right: boolean;
  distances: { left: number; center: number; right: number };
  path_distance?: number;
}

const SECTORS = [
  ["left", "Esquerda"],
  ["center", "Centro"],
  ["right", "Direita"],
] as const;

const Row = ({ title, source, data }: { title: string; source: string; data?: ObstacleData }) => (
  <div>
    <div className="mb-1.5 flex items-baseline justify-between">
      <span className="text-sm font-medium">{title}</span>
      <span className="text-xs text-muted-foreground">{source}</span>
    </div>
    <div className="grid grid-cols-3 gap-2">
      {SECTORS.map(([key, label]) => {
        const blocked = data?.[key];
        const dist = data?.distances[key];
        return (
          <div
            key={key}
            className={`rounded-md border px-2.5 py-2 transition-colors ${
              !data ? "border-border bg-muted/40" : blocked ? "border-red-500/60 bg-red-500/15" : "border-emerald-500/30 bg-emerald-500/10"
            }`}
          >
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className={`tabular text-base font-semibold ${blocked ? "text-red-400" : ""}`}>
              {dist !== undefined && dist < 9.9 ? `${dist.toFixed(2)} m` : data ? "livre" : "—"}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

export const ObstaclePanel = ({ ground, height }: { ground?: ObstacleData; height?: ObstacleData }) => (
  <Card>
    <CardHeader className="pb-3">
      <CardTitle className="flex items-center gap-2 text-base">
        <ShieldAlert className="h-5 w-5 text-primary" />
        Obstáculos à frente
      </CardTitle>
    </CardHeader>
    <CardContent className="grid gap-4 md:grid-cols-2">
      <Row title="Chão" source="LiDAR 2D" data={ground} />
      <Row title="Altura" source="D435 (profundidade) / YOLO" data={height} />
    </CardContent>
  </Card>
);
