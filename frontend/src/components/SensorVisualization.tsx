import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle } from "lucide-react";

interface ObstacleData {
  type?: string;
  left: boolean;
  center: boolean;
  right: boolean;
  distances: {
    left: number;
    center: number;
    right: number;
  };
}

interface TrackedObject {
  id: number;
  bbox: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  centroid: {
    x: number;
    y: number;
  };
  area: number;
  depth?: number;
}

interface SensorVisualizationProps {
  cameraImage?: string;
  groundObstacles?: ObstacleData;
  heightObstacles?: ObstacleData;
  trackedObjects?: TrackedObject[];
}

export const SensorVisualization = ({ cameraImage, groundObstacles, heightObstacles, trackedObjects }: SensorVisualizationProps) => {
  const renderObstacleSector = (sector: 'left' | 'center' | 'right', obstacles: ObstacleData | undefined) => {
    const sectorName = sector === 'left' ? 'Esquerda' : sector === 'center' ? 'Centro' : 'Direita';
    const hasObstacle = obstacles?.[sector];
    const distance = obstacles?.distances[sector];

    return (
      <div className={`p-3 rounded-lg border-2 transition-colors ${
        hasObstacle 
          ? 'border-destructive bg-destructive/10' 
          : 'border-border bg-secondary'
      }`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium">{sectorName}</span>
          {hasObstacle ? (
            <AlertCircle className="w-4 h-4 text-destructive" />
          ) : (
            <CheckCircle className="w-4 h-4 text-primary" />
          )}
        </div>
        <div className="text-lg font-bold">
          {distance?.toFixed(2) ?? '--'}m
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Camera Feed with Object Tracking */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold">📹 Câmera C270 (Frontal)</h3>
          {trackedObjects && trackedObjects.length > 0 && (
            <Badge variant="default">{trackedObjects.length} objeto(s)</Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground mb-3">Tracking de objetos em tempo real</p>
        <div className="aspect-video bg-secondary rounded-lg overflow-hidden relative">
          {cameraImage ? (
            <>
              <img 
                src={`data:image/jpeg;base64,${cameraImage}`} 
                alt="Camera feed"
                className="w-full h-full object-cover"
              />
              {/* Overlay com objetos rastreados */}
              <svg 
                className="absolute inset-0 w-full h-full pointer-events-none"
                viewBox="0 0 640 480"
                preserveAspectRatio="none"
              >
                {trackedObjects?.map((obj) => {
                  // Validação defensiva dos dados do objeto
                  if (!obj || !obj.bbox || !obj.centroid) return null;
                  
                  const bboxX = obj.bbox.x || 0;
                  const bboxY = obj.bbox.y || 0;
                  const bboxW = obj.bbox.w || 0;
                  const bboxH = obj.bbox.h || 0;
                  const centroidX = obj.centroid.x || 0;
                  const centroidY = obj.centroid.y || 0;
                  
                  return (
                    <g key={obj.id}>
                      {/* Bounding box */}
                      <rect
                        x={bboxX}
                        y={bboxY}
                        width={bboxW}
                        height={bboxH}
                        fill="none"
                        stroke="hsl(var(--primary))"
                        strokeWidth="2"
                        className="animate-pulse"
                      />
                      {/* Label */}
                      <rect
                        x={bboxX}
                        y={bboxY - 24}
                        width={obj.depth ? 110 : 70}
                        height="20"
                        fill="hsl(var(--primary))"
                        opacity="0.9"
                      />
                      <text
                        x={bboxX + 5}
                        y={bboxY - 10}
                        fill="hsl(var(--primary-foreground))"
                        fontSize="12"
                        fontWeight="bold"
                      >
                        ID:{obj.id} {obj.depth && `${obj.depth.toFixed(2)}m`}
                      </text>
                      {/* Centroide */}
                      <circle
                        cx={centroidX}
                        cy={centroidY}
                        r="3"
                        fill="hsl(var(--accent))"
                      />
                    </g>
                  );
                })}
              </svg>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Aguardando dados da câmera...
            </div>
          )}
        </div>
      </Card>

      {/* Ground Obstacles - LiDAR */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-2">🎯 LiDAR 2D</h3>
        <p className="text-xs text-muted-foreground mb-3">Obstáculos à frente (setores de 40°)</p>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            {renderObstacleSector('left', groundObstacles)}
            {renderObstacleSector('center', groundObstacles)}
            {renderObstacleSector('right', groundObstacles)}
          </div>
          {groundObstacles && (
            <div className="text-center">
              <Badge variant={groundObstacles.left || groundObstacles.center || groundObstacles.right ? "destructive" : "default"}>
                {groundObstacles.left || groundObstacles.center || groundObstacles.right 
                  ? '⚠️ Obstáculos no Chão' 
                  : '✓ Chão Livre'}
              </Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Height Obstacles - Camera */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-2">📏 Detecção de Altura</h3>
        <p className="text-xs text-muted-foreground mb-3">Câmera (YOLO) ou L515</p>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            {renderObstacleSector('left', heightObstacles)}
            {renderObstacleSector('center', heightObstacles)}
            {renderObstacleSector('right', heightObstacles)}
          </div>
          {heightObstacles && (
            <div className="text-center">
              <Badge variant={heightObstacles.left || heightObstacles.center || heightObstacles.right ? "destructive" : "default"}>
                {heightObstacles.left || heightObstacles.center || heightObstacles.right 
                  ? '⚠️ Objetos Altos' 
                  : '✓ Altura Livre'}
              </Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <CheckCircle className="w-3 h-3 text-primary" />
          <span className="text-muted-foreground">Livre</span>
        </div>
        <div className="flex items-center gap-1">
          <AlertCircle className="w-3 h-3 text-destructive" />
          <span className="text-muted-foreground">Obstáculo</span>
        </div>
      </div>
    </div>
  );
};
