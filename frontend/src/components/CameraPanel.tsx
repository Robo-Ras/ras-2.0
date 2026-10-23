import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Video, VideoOff } from "lucide-react";

export interface TrackedObject {
  id: number;
  bbox: { x: number; y: number; w: number; h: number };
  centroid?: { x: number; y: number };
  depth?: number;
  class_name?: string;
  confidence?: number;
  camera?: string;
}

interface CameraPanelProps {
  cameraImage?: string;
  l515Image?: string;
  cameraLabel: string;
  backendConnected: boolean;
  trackedObjects?: TrackedObject[];
  trackingMode?: string;
  yoloEnabled: boolean;
  onToggleYolo: (enabled: boolean) => void;
}

export const CameraPanel = ({
  cameraImage,
  l515Image,
  cameraLabel,
  backendConnected,
  trackedObjects = [],
  trackingMode = "basic",
  yoloEnabled,
  onToggleYolo,
}: CameraPanelProps) => {
  const [source, setSource] = useState<"camera" | "l515">("camera");
  const showL515 = source === "l515" && !!l515Image;
  const image = showL515 ? l515Image : cameraImage;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Video className="h-5 w-5 text-primary" />
              {showL515 ? "RealSense L515" : cameraLabel}
            </CardTitle>
            <CardDescription>
              {trackingMode === "yolo" ? "YOLO detectando pessoas e objetos" : trackingMode === "error" ? "Erro no tracking" : "Tracking básico"}
              {" · "}
              {trackedObjects.length} objeto(s)
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="yolo-toggle" className="text-sm">YOLO</Label>
            <Switch id="yolo-toggle" checked={yoloEnabled} onCheckedChange={onToggleYolo} disabled={!backendConnected} />
          </div>
        </div>
        {l515Image && (
          <div className="flex gap-1 pt-1">
            <Button size="sm" variant={source === "camera" ? "default" : "outline"} onClick={() => setSource("camera")}>
              {cameraLabel}
            </Button>
            <Button size="sm" variant={source === "l515" ? "default" : "outline"} onClick={() => setSource("l515")}>
              L515
            </Button>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="relative aspect-[4/3] w-full overflow-hidden rounded-lg border border-border bg-black">
          {image ? (
            <>
              <img src={`data:image/jpeg;base64,${image}`} alt={showL515 ? "Imagem da L515" : "Imagem da câmera"} className="h-full w-full object-contain" />
              {!showL515 && (
                <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 640 480" preserveAspectRatio="xMidYMid meet">
                  {trackedObjects.map((obj) => {
                    if (!obj?.bbox) return null;
                    const { x = 0, y = 0, w = 0, h = 0 } = obj.bbox;
                    const label = [obj.class_name ?? `#${obj.id}`, obj.depth ? `${obj.depth.toFixed(2)} m` : null].filter(Boolean).join(" · ");
                    return (
                      <g key={obj.id}>
                        <rect x={x} y={y} width={w} height={h} fill="none" stroke="#38bdf8" strokeWidth="2.5" rx="3" />
                        <rect x={x} y={Math.max(0, y - 22)} width={label.length * 7.5 + 12} height="20" fill="#38bdf8" rx="3" />
                        <text x={x + 6} y={Math.max(0, y - 22) + 14} fill="#04121f" fontSize="13" fontWeight="bold">
                          {label}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-muted-foreground">
              <VideoOff className="h-8 w-8" />
              <p className="font-medium text-foreground">Aguardando imagem da câmera</p>
              <p className="text-sm">
                {backendConnected ? "Conecte a C270 na USB (ou use --camera-device /dev/videoN)." : "O backend não está rodando."}
              </p>
            </div>
          )}
        </div>

        {trackedObjects.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {trackedObjects.slice(0, 8).map((obj) => (
              <Badge key={obj.id} variant="secondary" className="gap-1 font-normal">
                <span className="font-semibold">{obj.class_name ?? `#${obj.id}`}</span>
                {obj.depth ? <span className="tabular">{obj.depth.toFixed(2)} m</span> : null}
                {obj.confidence ? <span className="text-muted-foreground">{Math.round(obj.confidence * 100)}%</span> : null}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
