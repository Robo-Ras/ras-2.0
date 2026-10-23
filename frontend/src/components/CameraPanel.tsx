import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Video, VideoOff } from "lucide-react";
import type { SensorInfo } from "@/components/StatusBar";

export interface TrackedObject {
  id: number;
  bbox: { x: number; y: number; w: number; h: number };
  centroid?: { x: number; y: number };
  depth?: number;
  class_name?: string;
  confidence?: number;
  camera?: string; // "camera" (C270) ou "realsense" (D435)
}

interface CameraPanelProps {
  cameraImage?: string;
  realsenseImage?: string;
  camera?: SensorInfo;
  realsense?: SensorInfo;
  backendConnected: boolean;
  trackedObjects?: TrackedObject[];
  trackingMode?: string;
  yoloEnabled: boolean;
  onToggleYolo: (enabled: boolean) => void;
}

const CameraView = ({
  title,
  subtitle,
  image,
  info,
  objects,
  waitingHint,
}: {
  title: string;
  subtitle: string;
  image?: string;
  info?: SensorInfo;
  objects: TrackedObject[];
  waitingHint: string;
}) => (
  <div className="space-y-1.5">
    <div className="flex items-baseline justify-between gap-2">
      <div className="text-sm font-medium">
        {title} <span className="font-normal text-muted-foreground">· {subtitle}</span>
      </div>
      <Badge variant={image ? "default" : "outline"} className="text-[10px]">
        {image ? (info?.kind === "sim" ? "SIMULADA" : "AO VIVO") : "AGUARDANDO"}
      </Badge>
    </div>
    <div className="relative aspect-[4/3] w-full overflow-hidden rounded-lg border border-border bg-black">
      {image ? (
        <>
          <img src={`data:image/jpeg;base64,${image}`} alt={`Imagem da ${title}`} className="h-full w-full object-contain" />
          <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 640 480" preserveAspectRatio="xMidYMid meet">
            {objects.map((obj) => {
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
        </>
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-muted-foreground">
          <VideoOff className="h-7 w-7" />
          <p className="font-medium text-foreground">Aguardando {title}</p>
          <p className="text-sm">{waitingHint}</p>
        </div>
      )}
    </div>
  </div>
);

export const CameraPanel = ({
  cameraImage,
  realsenseImage,
  camera,
  realsense,
  backendConnected,
  trackedObjects = [],
  trackingMode = "basic",
  yoloEnabled,
  onToggleYolo,
}: CameraPanelProps) => {
  const offline = "O backend não está rodando.";
  // Sem a C270, o backend manda a imagem da RealSense também em camera_image: não mostra duas vezes
  const c270Image = camera?.online ? cameraImage : undefined;
  const isSim = camera?.kind === "sim";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Video className="h-5 w-5 text-primary" />
              Câmeras
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
      </CardHeader>

      <CardContent className="space-y-4">
        <CameraView
          title={isSim ? "Câmera simulada" : "C270"}
          subtitle="frontal, cor"
          image={c270Image}
          info={camera}
          objects={trackedObjects.filter((o) => (o.camera ?? "camera") === "camera")}
          waitingHint={backendConnected ? "Conecte a C270 na USB (ou use --camera-device /dev/videoN)." : offline}
        />
        <CameraView
          title={realsense?.name ?? "D435"}
          subtitle="RealSense, cor + profundidade"
          image={realsenseImage}
          info={realsense}
          objects={trackedObjects.filter((o) => o.camera === "realsense")}
          waitingHint={
            !backendConnected ? offline : isSim ? "A D435 não é simulada no --sim." : "Conecte a D435 numa porta USB 3 (azul)."
          }
        />

        {trackedObjects.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {trackedObjects.slice(0, 8).map((obj) => (
              <Badge key={`${obj.camera}-${obj.id}`} variant="secondary" className="gap-1 font-normal">
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
