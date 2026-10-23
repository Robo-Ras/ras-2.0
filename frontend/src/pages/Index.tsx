import { useState, useEffect, useRef } from "react";
import DirectionalControl from "@/components/DirectionalControl";
import MotorSpeedControl from "@/components/MotorSpeedControl";
import VoiceControl from "@/components/VoiceControl";
import { SensorVisualization } from "@/components/SensorVisualization";
import { MultiCameraView } from "@/components/MultiCameraView";
import { CameraStatus, type SensorsStatus } from "@/components/CameraStatus";
import { Lidar2DView, type LidarScan } from "@/components/Lidar2DView";
import { AutonomousControl } from "@/components/AutonomousControl";
import { SerialConnectionControl } from "@/components/SerialConnectionControl";
import { ArduinoTroubleshooting } from "@/components/ArduinoTroubleshooting";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { getWsUrl } from "@/lib/ws";
import type { VoiceCommandEvent, VoiceCommandId } from "@/lib/voiceCommands";

const Index = () => {
  const [lastCommand, setLastCommand] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isArduinoConnected, setIsArduinoConnected] = useState(false);
  const [arduinoPort, setArduinoPort] = useState<string | null>(null);
  const [autonomousMode, setAutonomousMode] = useState(false);
  const [autonomousSpeed, setAutonomousSpeed] = useState(100);
  const [cameraImage, setCameraImage] = useState<string>();
  const [l515Image, setL515Image] = useState<string>();
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
          // Imagens: câmera principal (C270) e L515 opcional
          setCameraImage(data.camera_image);
          setL515Image(data.l515_image);
          setSensorsStatus(data.sensors_status);
          setLidarScan(data.lidar_scan);

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
        console.error('❌ ERRO WebSocket:', error);
        console.error('Certifique-se que robot_autonomous_control.py está rodando!');
        console.error('Execute: python robot_autonomous_control.py');
        toast({
          title: "Erro de Conexão",
          description: "Servidor Python não está rodando. Execute: python robot_autonomous_control.py",
          variant: "destructive",
        });
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
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-4xl font-bold">Tri-Bot Pilot</h1>
      </div>
      <p className="text-center text-muted-foreground mb-8">
        Sistema de Controle Remoto com Navegação Autônoma
      </p>
      
      {/* Connection Status */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* WebSocket Status */}
        <div className={`p-4 rounded-lg border-2 ${isConnected ? 'bg-green-500/10 border-green-500' : 'bg-destructive/10 border-destructive'}`}>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-destructive'}`} />
            <span className="font-semibold">Servidor Python</span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {isConnected ? 'Conectado (WebSocket)' : 'Desconectado - Execute ./start.sh'}
          </p>
        </div>

        {/* Arduino Status */}
        <div className={`p-4 rounded-lg border-2 ${isArduinoConnected ? 'bg-green-500/10 border-green-500' : 'bg-muted/50 border-border'}`}>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isArduinoConnected ? 'bg-green-500 animate-pulse' : 'bg-muted-foreground'}`} />
            <span className="font-semibold">Arduino</span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {isArduinoConnected ? `Conectado${arduinoPort ? ` em ${arduinoPort}` : ''}${arduinoPort === 'SIM' ? ' (simulado)' : ''}` : 'Aguardando conexão'}
          </p>
        </div>
      </div>

      {/* Arduino Connection */}
      <div className="mb-6 space-y-4">
        <SerialConnectionControl
          wsRef={wsRef}
          isArduinoConnected={isArduinoConnected}
          availablePorts={availablePorts}
          connectedPort={arduinoPort}
          onConnectionChange={setIsArduinoConnected}
        />
        
        {!isArduinoConnected && <ArduinoTroubleshooting />}
      </div>
      
      {lastCommand && (
        <div className="text-center mb-6 p-4 bg-secondary rounded-lg">
          <p className="text-sm text-muted-foreground">Último comando enviado:</p>
          <p className="font-mono font-semibold">{lastCommand}</p>
        </div>
      )}

      {/* Autonomous Control */}
      <div className="mb-6">
        <AutonomousControl
          isConnected={isConnected}
          autonomousMode={autonomousMode}
          onToggleAutonomous={handleToggleAutonomous}
          onEmergencyStop={handleEmergencyStop}
          autonomousSpeed={autonomousSpeed}
          onSpeedChange={handleAutonomousSpeedChange}
          navigationStatus={navigationStatus}
          heightObstacles={heightObstacles}
        />
      </div>

      {/* Voice Control */}
      <div className="mb-6">
        <VoiceControl
          onVoiceCommand={handleVoiceCommand}
          lastVoiceEvent={lastVoiceEvent}
          isConnected={isConnected}
        />
      </div>

      {/* Camera D435 + Multi-Camera View */}
      <div className="mb-6 space-y-6">
        {/* Status das Câmeras */}
        <CameraStatus
          sensors={sensorsStatus}
          yoloEnabled={yoloEnabled}
          trackingMode={trackingMode}
        />

        {/* Visualização com Múltiplas Câmeras */}
        <MultiCameraView
          lidarImage={l515Image}
          d435Image={cameraImage}
          cameraLabel={sensorsStatus?.camera?.kind === 'sim' ? 'Câmera simulada' : 'Câmera C270'}
          trackedObjects={trackedObjects}
          trackingMode={trackingMode}
          yoloEnabled={yoloEnabled}
          onToggleYolo={handleToggleYolo}
        />

        {/* LiDAR 2D */}
        <Lidar2DView
          scan={lidarScan}
          groundObstacles={groundObstacles}
          sensorName={sensorsStatus?.lidar?.name ? `LiDAR 2D · ${sensorsStatus.lidar.name}` : 'LiDAR 2D'}
          online={sensorsStatus?.lidar?.online}
        />

        {/* Visualização de Sensores (versão simplificada) */}
        <SensorVisualization
          cameraImage={cameraImage}
          groundObstacles={groundObstacles}
          heightObstacles={heightObstacles}
          trackedObjects={trackedObjects}
        />
      </div>

      <Tabs defaultValue="directional" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="directional">Controle Direcional</TabsTrigger>
          <TabsTrigger value="motor">Controle por Motor</TabsTrigger>
        </TabsList>
        
        <TabsContent value="directional">
          <DirectionalControl onSendCommand={handleSendCommand} />
        </TabsContent>
        
        <TabsContent value="motor">
          <MotorSpeedControl onSendCommand={handleSendCommand} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Index;
