import { useState, useEffect, useRef } from "react";
import DirectionalControl from "@/components/DirectionalControl";
import MotorSpeedControl from "@/components/MotorSpeedControl";
import VoiceControl from "@/components/VoiceControl";
import { StatusBar, type SensorsStatus } from "@/components/StatusBar";
import { CameraPanel } from "@/components/CameraPanel";
import { ObstaclePanel } from "@/components/ObstaclePanel";
import { Lidar2DView, type LidarScan } from "@/components/Lidar2DView";
import { AutonomousControl } from "@/components/AutonomousControl";
import { SerialConnectionControl } from "@/components/SerialConnectionControl";
import { ArduinoTroubleshooting } from "@/components/ArduinoTroubleshooting";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Gamepad2, Plug } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { getWsUrl } from "@/lib/ws";
import type { VoiceCommandEvent, VoiceCommandId } from "@/lib/voiceCommands";

const Index = () => {
  const [lastCommand, setLastCommand] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isArduinoConnected, setIsArduinoConnected] = useState(false);
  const [arduinoPort, setArduinoPort] = useState<string | null>(null);
  const [autonomousMode, setAutonomousMode] = useState(false);
  const [robotMoving, setRobotMoving] = useState(false);
  const [autonomousSpeed, setAutonomousSpeed] = useState(100);
  const [cameraImage, setCameraImage] = useState<string>();
  const [realsenseImage, setRealsenseImage] = useState<string>();
  const [sensorsStatus, setSensorsStatus] = useState<SensorsStatus>();
  const [lidarScan, setLidarScan] = useState<LidarScan>();
  const [groundObstacles, setGroundObstacles] = useState<any>();
  const [heightObstacles, setHeightObstacles] = useState<any>();
  const [trackedObjects, setTrackedObjects] = useState<any>();
  const [trackingMode, setTrackingMode] = useState<string>("basic");
  const [yoloEnabled, setYoloEnabled] = useState(false);
  const [navigationStatus, setNavigationStatus] = useState<any>();
  const [availablePorts, setAvailablePorts] = useState<string[]>([]);
  const [lastVoiceEvent, setLastVoiceEvent] = useState<VoiceCommandEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const { toast } = useToast();

  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      const wsUrl = getWsUrl();
      console.log(`🌐 Tentando conectar ao servidor Python em ${wsUrl}`);
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('✓✓✓ CONECTADO ao servidor Python com sucesso!');
        setIsConnected(true);
        toast({
          title: "Conectado",
          description: "Conexão estabelecida com o sistema de sensores",
        });
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('📩 Mensagem recebida do servidor:', data.type);
        
        if (data.type === 'sensor_data') {
          // Imagens: C270 (frontal) e RealSense D435
          setCameraImage(data.camera_image);
          setRealsenseImage(data.realsense_image);
          setSensorsStatus(data.sensors_status);
          setLidarScan(data.lidar_scan);
          setRobotMoving(!!data.robot_moving);

          // Dados de obstáculos
          setGroundObstacles(data.ground_obstacles);
          setHeightObstacles(data.height_obstacles);

          // Tracking
          setTrackedObjects(data.tracked_objects || []);
          if (data.tracking_mode) {
            setTrackingMode(data.tracking_mode);
          }
          
          // Navegação
          if (data.navigation_status) {
            setNavigationStatus(data.navigation_status);
          }
        } else if (data.type === 'ports_list') {
          console.log('✅ Lista de portas recebida:', data.ports);
          setAvailablePorts(data.ports || []);
        } else if (data.type === 'serial_status') {
          console.log('✅ Status serial atualizado:', data.connected, data.port);
          setIsArduinoConnected(data.connected);
          setArduinoPort(data.port ?? null);
          if (data.connected && !data.initial) {
            toast({
              title: "Arduino Conectado",
              description: `Conectado na porta ${data.port}`,
            });
          }
        } else if (data.type === 'voice_command') {
          setLastVoiceEvent(data);
          if (data.source === 'jose') {
            toast({ title: "🎙️ José", description: `Comando de voz: ${data.text || data.command}` });
          }
        } else if (data.type === 'autonomous_status') {
          setAutonomousMode(data.enabled);
        } else if (data.type === 'yolo_status') {
          setYoloEnabled(data.enabled);
          if (data.initial) {
            // estado inicial enviado ao conectar, sem aviso
          } else if (data.error) {
            toast({
              title: "Erro YOLO",
              description: data.error,
              variant: "destructive",
            });
          } else if (data.enabled) {
            toast({
              title: "YOLO Ativado",
              description: "Detectando objetos com a câmera",
            });
          } else {
            toast({
              title: "YOLO Desativado",
              description: "Voltando ao tracking básico",
            });
          }
        }
      };
      
      ws.onerror = (error) => {
        // A faixa "Backend desconectado" já avisa; um toast aqui repetiria a cada tentativa de reconexão
        console.error('❌ ERRO WebSocket:', error);
      };
      
      ws.onclose = () => {
        console.log('✗ Desconectado do servidor Python');
        setIsConnected(false);
        if (closedByPage) return;
        // Tentar reconectar após 3 segundos
        console.log('⏳ Tentando reconectar em 3 segundos...');
        reconnectTimer = setTimeout(connectWebSocket, 3000);
      };
      
      wsRef.current = ws;
    };
    
    let closedByPage = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    connectWebSocket();
    
    return () => {
      closedByPage = true;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [toast]);

  const handleSendCommand = (m1: number, m2: number, m3: number) => {
    setLastCommand(`M1: ${m1}, M2: ${m2}, M3: ${m3}`);
    console.log("Sending command:", m1, m2, m3);
    
    // Envia comando via WebSocket se conectado
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'move',
        m1, m2, m3
      }));
    }
  };

  const handleVoiceCommand = (command: VoiceCommandId, text: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'voice_command', command, text, source: 'browser' }));
    }
  };

  const handleToggleAutonomous = (enabled: boolean) => {
    setAutonomousMode(enabled);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'set_autonomous',
        enabled,
        speed: autonomousSpeed
      }));
    }
    
    toast({
      title: enabled ? "Modo Autônomo Ativado" : "Modo Manual Ativado",
      description: enabled 
        ? "O robô agora desviará automaticamente de obstáculos" 
        : "Use os controles manuais para mover o robô",
    });
  };

  const handleAutonomousSpeedChange = (speed: number) => {
    setAutonomousSpeed(speed);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && autonomousMode) {
      wsRef.current.send(JSON.stringify({
        type: 'set_autonomous_speed',
        speed
      }));
    }
  };

  const handleToggleYolo = (enabled: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'toggle_yolo',
        enabled
      }));
    }
  };
  
  const handleEmergencyStop = () => {
    handleSendCommand(0, 0, 0);
    setAutonomousMode(false);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'set_autonomous',
        enabled: false
      }));
    }
    toast({
      title: "Parada de Emergência",
      description: "Todos os motores foram parados",
      variant: "destructive",
    });
  };

  return (
    <div className="min-h-screen">
      <StatusBar
        isConnected={isConnected}
        isArduinoConnected={isArduinoConnected}
        arduinoPort={arduinoPort}
        sensors={sensorsStatus}
        autonomousMode={autonomousMode}
        robotMoving={robotMoving}
        onEmergencyStop={handleEmergencyStop}
      />

      <main className="mx-auto max-w-[1600px] px-4 py-4">
        {!isConnected && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
            <span className="font-semibold text-amber-700 dark:text-amber-300">Backend desconectado.</span>{" "}
            <span className="text-muted-foreground">
              Rode <code className="rounded bg-muted px-1">./start.sh</code> (ou <code className="rounded bg-muted px-1">./start.sh --sim</code> sem o robô).
              Tentando reconectar a cada 3 s...
            </span>
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-12">
          {/* Sensores */}
          <section className="space-y-4 xl:col-span-8">
            <div className="grid items-start gap-4 lg:grid-cols-2">
              <Lidar2DView
                scan={lidarScan}
                groundObstacles={groundObstacles}
                sensor={sensorsStatus?.lidar}
                backendConnected={isConnected}
              />
              <CameraPanel
                cameraImage={cameraImage}
                realsenseImage={realsenseImage}
                camera={sensorsStatus?.camera}
                realsense={sensorsStatus?.realsense}
                backendConnected={isConnected}
                trackedObjects={trackedObjects}
                trackingMode={trackingMode}
                yoloEnabled={yoloEnabled}
                onToggleYolo={handleToggleYolo}
              />
            </div>
            <ObstaclePanel ground={groundObstacles} height={heightObstacles} />
          </section>

          {/* Controles */}
          <aside className="grid items-start gap-4 md:grid-cols-2 xl:col-span-4 xl:grid-cols-1">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Gamepad2 className="h-5 w-5 text-primary" />
                  Controle manual
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="directional">
                  <TabsList className="mb-4 grid w-full grid-cols-2">
                    <TabsTrigger value="directional">Direcional</TabsTrigger>
                    <TabsTrigger value="motor">Por motor</TabsTrigger>
                  </TabsList>
                  <TabsContent value="directional">
                    <DirectionalControl onSendCommand={handleSendCommand} />
                  </TabsContent>
                  <TabsContent value="motor">
                    <MotorSpeedControl onSendCommand={handleSendCommand} />
                  </TabsContent>
                </Tabs>
                {lastCommand && (
                  <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
                    Último comando: <span className="font-mono tabular text-foreground">{lastCommand}</span>
                  </p>
                )}
              </CardContent>
            </Card>

            <AutonomousControl
              isConnected={isConnected}
              autonomousMode={autonomousMode}
              onToggleAutonomous={handleToggleAutonomous}
              autonomousSpeed={autonomousSpeed}
              onSpeedChange={handleAutonomousSpeedChange}
              navigationStatus={navigationStatus}
            />

            <VoiceControl
              onVoiceCommand={handleVoiceCommand}
              lastVoiceEvent={lastVoiceEvent}
              isConnected={isConnected}
            />

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Plug className="h-5 w-5 text-primary" />
                  Arduino
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <SerialConnectionControl
                  wsRef={wsRef}
                  isArduinoConnected={isArduinoConnected}
                  availablePorts={availablePorts}
                  connectedPort={arduinoPort}
                  onConnectionChange={setIsArduinoConnected}
                />
                {!isArduinoConnected && <ArduinoTroubleshooting />}
              </CardContent>
            </Card>
          </aside>
        </div>
      </main>
    </div>
  );
};

export default Index;
