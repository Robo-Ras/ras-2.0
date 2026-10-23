import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Camera, Radar, Video, VideoOff } from "lucide-react";

export interface SensorInfo {
  online: boolean;
  name?: string;
  kind?: string; // usb | realsense | ld06 | rplidar | sim
  port?: string | null;
}

export interface SensorsStatus {
  camera?: SensorInfo;
  l515?: SensorInfo;
  lidar?: SensorInfo;
}

interface CameraStatusProps {
  sensors?: SensorsStatus;
  yoloEnabled?: boolean;
  trackingMode?: string;
}

const SensorRow = ({ label, info, lidar }: { label: string; info?: SensorInfo; lidar?: boolean }) => {
  const online = !!info?.online;
  const Icon = lidar ? Radar : online ? Video : VideoOff;
  const detail = [info?.name && info.name !== label ? info.name : null, info?.port && info.port !== "SIM" ? info.port : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
      <div className="flex items-center gap-2 min-w-0">
        <Icon className={`h-4 w-4 shrink-0 ${online ? "text-green-500" : "text-gray-400"}`} />
        <span className="font-medium">{label}</span>
        {detail && <span className="text-xs text-muted-foreground truncate">{detail}</span>}
        {info?.kind === "sim" && <Badge variant="outline" className="text-xs">simulado</Badge>}
      </div>
      <Badge variant={online ? "default" : "secondary"}>{online ? "ONLINE" : "OFFLINE"}</Badge>
    </div>
  );
};

export const CameraStatus = ({ sensors, yoloEnabled = false, trackingMode = "basic" }: CameraStatusProps) => {
  const anyCamera = sensors?.camera?.online || sensors?.l515?.online;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Camera className="h-5 w-5" />
          Status dos Sensores
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <SensorRow label="Câmera C270" info={sensors?.camera} />
          <SensorRow label="LiDAR 2D" info={sensors?.lidar} lidar />
          <SensorRow label="RealSense L515" info={sensors?.l515} />

          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <span className="font-medium text-sm">Modo de Tracking</span>
            <Badge variant={yoloEnabled ? "default" : "outline"}>
              {trackingMode === "yolo" ? "YOLO" :
               trackingMode === "basic" ? "Básico" :
               trackingMode === "error" ? "Erro" : "Aguardando"}
            </Badge>
          </div>

          {!sensors && (
            <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm">
              <p className="text-blue-600 dark:text-blue-400">
                💡 Aguardando o backend. Rode ./start.sh (ou ./start.sh --sim sem o robô)
              </p>
            </div>
          )}

          {sensors && !anyCamera && !sensors.lidar?.online && (
            <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-sm">
              <p className="text-yellow-600 dark:text-yellow-400">
                ⚠️ Nenhum sensor detectado. Verifique as conexões USB.
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
