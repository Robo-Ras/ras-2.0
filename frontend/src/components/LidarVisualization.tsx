import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Radar } from "lucide-react";

interface LidarVisualizationProps {
  lidarImage?: string;
  groundObstacles?: {
    type: string;
    left: boolean;
    center: boolean;
    right: boolean;
    distances: {
      left: number;
      center: number;
      right: number;
    };
  };
}

export const LidarVisualization = ({ lidarImage, groundObstacles }: LidarVisualizationProps) => {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Radar className="h-5 w-5" />
              LiDAR L515 - Vista Inferior
            </CardTitle>
            <CardDescription>
              Sensor de profundidade posicionado na parte inferior do robô
            </CardDescription>
          </div>
          <Badge variant={lidarImage ? "default" : "secondary"}>
            {lidarImage ? "Ativo" : "Offline"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Imagem do LiDAR */}
        <div className="relative aspect-video bg-muted rounded-lg overflow-hidden">
          {lidarImage ? (
            <img
              src={`data:image/jpeg;base64,${lidarImage}`}
              alt="LiDAR Feed"
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground">Aguardando dados do LiDAR...</p>
            </div>
          )}
        </div>

        {/* Obstáculos detectados no chão */}
        {groundObstacles && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Obstáculos no Chão</h4>
            <div className="grid grid-cols-3 gap-2">
              {/* Esquerda */}
              <div className="flex flex-col items-center p-3 rounded-lg border bg-card">
                <span className="text-xs text-muted-foreground mb-1">Esquerda</span>
                <Badge
                  variant={groundObstacles.left ? "destructive" : "default"}
                  className="mb-1"
                >
                  {groundObstacles.left ? "BLOQUEADO" : "LIVRE"}
                </Badge>
                <span className="text-sm font-mono">
                  {groundObstacles.distances.left.toFixed(2)}m
                </span>
              </div>

              {/* Centro */}
              <div className="flex flex-col items-center p-3 rounded-lg border bg-card">
                <span className="text-xs text-muted-foreground mb-1">Centro</span>
                <Badge
                  variant={groundObstacles.center ? "destructive" : "default"}
                  className="mb-1"
                >
                  {groundObstacles.center ? "BLOQUEADO" : "LIVRE"}
                </Badge>
                <span className="text-sm font-mono">
                  {groundObstacles.distances.center.toFixed(2)}m
                </span>
              </div>

              {/* Direita */}
              <div className="flex flex-col items-center p-3 rounded-lg border bg-card">
                <span className="text-xs text-muted-foreground mb-1">Direita</span>
                <Badge
                  variant={groundObstacles.right ? "destructive" : "default"}
                  className="mb-1"
                >
                  {groundObstacles.right ? "BLOQUEADO" : "LIVRE"}
                </Badge>
                <span className="text-sm font-mono">
                  {groundObstacles.distances.right.toFixed(2)}m
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Legenda de cores */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-blue-500"></div>
            <span>Próximo (frio)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-red-500"></div>
            <span>Distante (quente)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
