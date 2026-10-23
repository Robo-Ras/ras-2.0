import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Bot } from "lucide-react";

interface AutonomousControlProps {
  isConnected: boolean;
  autonomousMode: boolean;
  onToggleAutonomous: (enabled: boolean) => void;
  autonomousSpeed: number;
  onSpeedChange: (speed: number) => void;
  navigationStatus?: {
    active: boolean;
    direction?: string;
    speed?: number;
    reason?: string;
  };
}

const DIRECTION_LABEL: Record<string, string> = {
  forward: "Avançando",
  backward: "Recuando",
  left: "Indo à esquerda",
  right: "Indo à direita",
  stop: "Parado",
  rotate_left: "Girando à esquerda",
  rotate_right: "Girando à direita",
};

export const AutonomousControl = ({
  isConnected,
  autonomousMode,
  onToggleAutonomous,
  autonomousSpeed,
  onSpeedChange,
  navigationStatus,
}: AutonomousControlProps) => {
  const active = autonomousMode && navigationStatus?.active;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Bot className="h-5 w-5 text-primary" />
            Modo autônomo
          </CardTitle>
          <Switch
            id="autonomous-mode"
            checked={autonomousMode}
            onCheckedChange={onToggleAutonomous}
            disabled={!isConnected}
            aria-label="Modo autônomo"
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          className={`rounded-md border px-3 py-2.5 text-sm ${
            autonomousMode ? "border-sky-500/40 bg-sky-500/10" : "border-border bg-muted/40"
          }`}
        >
          {autonomousMode ? (
            <div className="flex items-center justify-between gap-2">
              <span>Desviando de obstáculos com LiDAR e câmera</span>
              <Badge variant="outline" className="shrink-0">
                {active && navigationStatus?.direction ? DIRECTION_LABEL[navigationStatus.direction] ?? navigationStatus.direction : "Iniciando"}
              </Badge>
            </div>
          ) : (
            <span className="text-muted-foreground">Desligado: o robô só anda pelos controles manuais e pela voz.</span>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <Label>Velocidade</Label>
            <span className="tabular font-medium">{autonomousSpeed}</span>
          </div>
          <Slider
            value={[autonomousSpeed]}
            onValueChange={(value) => onSpeedChange(value[0])}
            min={50}
            max={200}
            step={10}
            disabled={!isConnected}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Lento</span>
            <span>Rápido</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
