import { Button } from "@/components/ui/button";
import { OctagonX } from "lucide-react";

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

type Tone = "ok" | "warn" | "off" | "info";

const TONE: Record<Tone, string> = {
  ok: "bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400/70",
  warn: "bg-amber-400",
  off: "bg-slate-500",
  info: "bg-sky-400 shadow-[0_0_8px] shadow-sky-400/70",
};

const Pill = ({ label, detail, tone }: { label: string; detail: string; tone: Tone }) => (
  <div className="flex min-w-0 items-center gap-2 rounded-md border border-border bg-muted/60 px-2.5 py-1.5">
    <span className={`h-2 w-2 shrink-0 rounded-full ${TONE[tone]}`} />
    <div className="min-w-0 leading-tight">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="truncate text-xs font-medium">{detail}</div>
    </div>
  </div>
);

interface StatusBarProps {
  isConnected: boolean;
  isArduinoConnected: boolean;
  arduinoPort: string | null;
  sensors?: SensorsStatus;
  autonomousMode: boolean;
  robotMoving: boolean;
  onEmergencyStop: () => void;
}

const sensorDetail = (info?: SensorInfo, fallback = "Desconectado") => {
  if (!info?.online) return fallback;
  return info.kind === "sim" ? `${info.name ?? "OK"} (sim)` : info.name ?? "OK";
};

export const StatusBar = ({
  isConnected,
  isArduinoConnected,
  arduinoPort,
  sensors,
  autonomousMode,
  robotMoving,
  onEmergencyStop,
}: StatusBarProps) => {
  const sensor = (info?: SensorInfo): Tone => (!isConnected ? "off" : info?.online ? "ok" : "warn");

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3">
        <div className="mr-2">
          <div className="text-lg font-bold tracking-tight">RAS 2.0</div>
          <div className="text-[11px] text-muted-foreground">Robô Autônomo de Serviços</div>
        </div>

        <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-3 2xl:grid-cols-6">
          <Pill label="Servidor" tone={isConnected ? "ok" : "off"} detail={isConnected ? "Conectado" : "Desconectado"} />
          <Pill
            label="Arduino"
            tone={!isConnected ? "off" : isArduinoConnected ? "ok" : "warn"}
            detail={isArduinoConnected ? (arduinoPort === "SIM" ? "SIM (simulado)" : arduinoPort ?? "Conectado") : "Desconectado"}
          />
          <Pill label="LiDAR 2D" tone={sensor(sensors?.lidar)} detail={sensorDetail(sensors?.lidar, "Aguardando")} />
          <Pill label="Câmera" tone={sensor(sensors?.camera)} detail={sensorDetail(sensors?.camera)} />
          <Pill label="L515" tone={sensors?.l515?.online ? "ok" : "off"} detail={sensors?.l515?.online ? "Online" : "Não usada"} />
          <Pill
            label="Modo"
            tone={autonomousMode ? "info" : robotMoving ? "ok" : "off"}
            detail={`${autonomousMode ? "Autônomo" : "Manual"} · ${robotMoving ? "andando" : "parado"}`}
          />
        </div>

        <Button
          variant="destructive"
          size="lg"
          onClick={onEmergencyStop}
          disabled={!isConnected}
          className="gap-2 font-bold tracking-wide"
          title="Para todos os motores e desliga o modo autônomo"
        >
          <OctagonX className="h-5 w-5" />
          PARAR
        </Button>
      </div>
    </header>
  );
};
