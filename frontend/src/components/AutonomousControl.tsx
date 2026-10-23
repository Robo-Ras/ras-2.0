import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Bot, Hand, Wifi, WifiOff, Gauge } from "lucide-react";

interface AutonomousControlProps {
  isConnected: boolean;
  autonomousMode: boolean;
  onToggleAutonomous: (enabled: boolean) => void;
  onEmergencyStop: () => void;
  autonomousSpeed: number;
  onSpeedChange: (speed: number) => void;
  navigationStatus?: {
    active: boolean;
    direction?: string;
    speed?: number;
    detection?: {
      mode?: string;
      obstacles?: {
        left: boolean;
        center: boolean;
        right: boolean;
      };
      distances?: {
        left: number;
        center: number;
        right: number;
      };
    };
    reason?: string;
  };
  heightObstacles?: {
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

export const AutonomousControl = ({
  isConnected,
  autonomousMode,
  onToggleAutonomous,
  onEmergencyStop,
  autonomousSpeed,
  onSpeedChange,
  navigationStatus,
  heightObstacles,
}: AutonomousControlProps) => {
  return (
    <Card className="p-6">
      <div className="space-y-6">
        {/* Connection Status */}
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <>
                <Wifi className="w-5 h-5 text-primary" />
                <span className="font-medium">Conectado ao Notebook</span>
              </>
            ) : (
              <>
                <WifiOff className="w-5 h-5 text-muted-foreground" />
                <span className="font-medium text-muted-foreground">Desconectado</span>
              </>
            )}
          </div>
          <Badge variant={isConnected ? "default" : "secondary"}>
            {isConnected ? "Online" : "Offline"}
          </Badge>
        </div>

        {/* Autonomous Mode Toggle */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label htmlFor="autonomous-mode" className="text-base font-semibold">
                Modo Autônomo
              </Label>
              <p className="text-sm text-muted-foreground">
                O robô desviará automaticamente dos obstáculos detectados pelos sensores
              </p>
            </div>
            <Switch
              id="autonomous-mode"
              checked={autonomousMode}
              onCheckedChange={onToggleAutonomous}
              disabled={!isConnected}
            />
          </div>

          {/* Mode Indicator */}
          <div className={`p-4 rounded-lg border-2 transition-colors ${
            autonomousMode 
              ? 'border-primary bg-primary/10' 
              : 'border-border bg-secondary'
          }`}>
            <div className="flex items-center gap-3">
              {autonomousMode ? (
                <>
                  <Bot className="w-6 h-6 text-primary" />
                  <div className="flex-1">
                    <div className="font-semibold">Navegação Autônoma Ativa</div>
                    <div className="text-sm text-muted-foreground">
                      Desviando de obstáculos com LiDAR 2D e câmera
                    </div>
                    
                    {/* Navigation Status */}
                    {navigationStatus?.active && navigationStatus.detection && (
                      <div className="mt-3 p-3 rounded bg-background/50 border border-border">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold uppercase tracking-wide">
                            🎥 Detecção Ativa
                          </span>
                          <Badge variant="outline" className="text-xs">
                            {navigationStatus.direction === 'forward' && '➡️ Avançando'}
                            {navigationStatus.direction === 'backward' && '⬅ Recuando'}
                            {navigationStatus.direction === 'left' && '↩ Esquerda'}
                            {navigationStatus.direction === 'right' && '↪ Direita'}
                            {navigationStatus.direction === 'stop' && '⏸ Parado'}
                            {navigationStatus.direction === 'rotate_left' && '↺ Girando à esquerda'}
                            {navigationStatus.direction === 'rotate_right' && '↻ Girando à direita'}
                          </Badge>
                        </div>
                        
                        {/* Obstacle Status */}
                        {navigationStatus.detection.obstacles && (
                          <div className="grid grid-cols-3 gap-2 mt-2">
                            <div className={`p-2 rounded text-center text-xs ${
                              navigationStatus.detection.obstacles.left 
                                ? 'bg-destructive/20 text-destructive' 
                                : 'bg-green-500/20 text-green-600'
                            }`}>
                              <div className="font-bold">Esquerda</div>
                              <div className="text-xs opacity-70">
                                {navigationStatus.detection.distances?.left.toFixed(1)}m
                              </div>
                            </div>
                            <div className={`p-2 rounded text-center text-xs ${
                              navigationStatus.detection.obstacles.center 
                                ? 'bg-destructive/20 text-destructive' 
                                : 'bg-green-500/20 text-green-600'
                            }`}>
                              <div className="font-bold">Centro</div>
                              <div className="text-xs opacity-70">
                                {navigationStatus.detection.distances?.center.toFixed(1)}m
                              </div>
                            </div>
                            <div className={`p-2 rounded text-center text-xs ${
                              navigationStatus.detection.obstacles.right 
                                ? 'bg-destructive/20 text-destructive' 
                                : 'bg-green-500/20 text-green-600'
                            }`}>
                              <div className="font-bold">Direita</div>
                              <div className="text-xs opacity-70">
                                {navigationStatus.detection.distances?.right.toFixed(1)}m
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <Hand className="w-6 h-6 text-muted-foreground" />
                  <div>
                    <div className="font-semibold">Controle Manual</div>
                    <div className="text-sm text-muted-foreground">
                      Use os controles direcionais para mover o robô
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Speed Control */}
        <div className="space-y-3 p-4 rounded-lg bg-muted/50 border border-border">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-primary" />
            <Label className="font-semibold">Velocidade Autônoma</Label>
            <Badge variant="outline" className="ml-auto">
              {autonomousSpeed}
            </Badge>
          </div>
          <Slider
            value={[autonomousSpeed]}
            onValueChange={(value) => onSpeedChange(value[0])}
            min={50}
            max={200}
            step={10}
            disabled={!isConnected}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Lento (50)</span>
            <span>Rápido (200)</span>
          </div>
        </div>

        {/* Emergency Stop */}
        <div className="pt-4 border-t border-border">
          <Button
            onClick={onEmergencyStop}
            variant="destructive"
            size="lg"
            className="w-full"
            disabled={!isConnected}
          >
            PARADA DE EMERGÊNCIA
          </Button>
          <p className="text-xs text-muted-foreground text-center mt-2">
            Pressione para interromper todos os movimentos imediatamente
          </p>
        </div>

        {/* Instructions */}
        {!isConnected && (
          <div className="p-4 rounded-lg bg-muted">
            <p className="text-sm text-muted-foreground">
              Execute o script <code className="px-1 py-0.5 rounded bg-background">robot_autonomous_control.py</code> no notebook para iniciar o sistema.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
};
