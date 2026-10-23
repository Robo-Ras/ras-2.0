import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface MultiCameraViewProps {
  lidarImage?: string;
  d435Image?: string;
  trackedObjects?: any[];
  trackingMode?: string;
  yoloEnabled?: boolean;
  onToggleYolo?: (enabled: boolean) => void;
  cameraLabel?: string;
}

export const MultiCameraView = ({ 
  lidarImage, 
  d435Image, 
  trackedObjects = [],
  trackingMode = "basic",
  yoloEnabled = false,
  onToggleYolo,
  cameraLabel = "Câmera C270",
}: MultiCameraViewProps) => {
  return (
    <div className="space-y-4">
      {/* Controle do YOLO */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Sistema de Tracking</CardTitle>
            <div className="flex items-center gap-2">
              <Label htmlFor="yolo-toggle">YOLO Tracking</Label>
              <Switch 
                id="yolo-toggle"
                checked={yoloEnabled}
                onCheckedChange={onToggleYolo}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Badge variant={trackingMode === "yolo" ? "default" : "secondary"}>
              {trackingMode === "yolo" ? "YOLO Ativo" : 
               trackingMode === "basic" ? "Tracking Básico" : "Erro"}
            </Badge>
            <span className="text-sm text-muted-foreground">
              Objetos rastreados: {trackedObjects.length}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Grid de Câmeras */}
      <div className={`grid grid-cols-1 gap-4 ${lidarImage ? "lg:grid-cols-2" : ""}`}>
        {/* RealSense L515 (opcional, só aparece se estiver conectada) */}
        {lidarImage && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-lg">
              <span>RealSense L515</span>
              <Badge variant={lidarImage ? "default" : "secondary"}>
                {lidarImage ? "ONLINE" : "OFFLINE"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {lidarImage ? (
              <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
                <img
                  src={`data:image/jpeg;base64,${lidarImage}`}
                  alt="LiDAR L515 Feed"
                  className="w-full h-full object-contain"
                />
              </div>
            ) : (
              <div className="w-full aspect-video bg-muted rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">Aguardando dados do L515...</p>
              </div>
            )}
          </CardContent>
        </Card>
        )}

        {/* Câmera principal (C270) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-lg">
              <span>{cameraLabel}</span>
              <Badge variant={d435Image ? "default" : "secondary"}>
                {d435Image ? "ONLINE" : "OFFLINE"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {d435Image ? (
              <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
                <img
                  src={`data:image/jpeg;base64,${d435Image}`}
                  alt="Camera Feed"
                  className="w-full h-full object-contain"
                />
              </div>
            ) : (
              <div className="w-full aspect-video bg-muted rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">Aguardando imagem da câmera...</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lista de Objetos Rastreados */}
      {trackedObjects.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Objetos Detectados</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {trackedObjects.map((obj, index) => (
                <div
                  key={obj.id || index}
                  className="flex items-center justify-between p-2 bg-muted rounded-lg text-sm"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">#{obj.id}</Badge>
                    {obj.class_name && (
                      <span className="font-medium">{obj.class_name}</span>
                    )}
                    {obj.camera && (
                      <Badge variant="secondary" className="text-xs">
                        {obj.camera}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {obj.depth > 0 && (
                      <span>Dist: {obj.depth.toFixed(2)}m</span>
                    )}
                    {obj.confidence > 0 && (
                      <span>Conf: {(obj.confidence * 100).toFixed(0)}%</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
