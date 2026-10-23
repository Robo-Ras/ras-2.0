import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { RefreshCw, Plug } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface SerialConnectionControlProps {
  wsRef: React.RefObject<WebSocket | null>;
  isArduinoConnected: boolean;
  availablePorts: string[];
  connectedPort?: string | null;
  onConnectionChange: (connected: boolean) => void;
}

const FALLBACK_PORTS = ["ttyUSB0", "ttyUSB1", "ttyACM0", "ttyACM1"];

// "ttyUSB0" vira "/dev/ttyUSB0"; caminhos completos e "SIM" (simulador) ficam iguais
const toFullPort = (port: string) => (port.startsWith("tty") ? `/dev/${port}` : port);

export const SerialConnectionControl = ({
  wsRef,
  isArduinoConnected,
  availablePorts,
  connectedPort,
  onConnectionChange,
}: SerialConnectionControlProps) => {
  const [selectedPort, setSelectedPort] = useState<string>("ttyUSB0");
  const [isConnecting, setIsConnecting] = useState(false);
  const { toast } = useToast();

  const ports = availablePorts.length > 0 ? availablePorts : FALLBACK_PORTS;

  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'discover_ports' }));
    }
  }, [wsRef]);

  // Quando o backend manda a lista de portas, seleciona a primeira se a atual não existir
  useEffect(() => {
    if (availablePorts.length > 0 && !availablePorts.includes(selectedPort)) {
      setSelectedPort(availablePorts[0]);
    }
  }, [availablePorts, selectedPort]);

  const handleRefreshPorts = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'discover_ports' }));
      toast({
        title: "Atualizando portas",
        description: "Buscando portas disponíveis...",
      });
    }
  };

  const handleConnect = () => {
    if (!selectedPort) {
      toast({
        title: "Selecione uma porta",
        variant: "destructive",
      });
      return;
    }

    setIsConnecting(true);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const fullPort = toFullPort(selectedPort);

      console.log(`🔌 Tentando conectar ao Arduino na porta: ${fullPort}`);
      
      wsRef.current.send(JSON.stringify({
        type: 'connect_serial',
        port: fullPort
      }));
      
      setTimeout(() => setIsConnecting(false), 3000);
    } else {
      setIsConnecting(false);
      toast({
        title: "Erro",
        description: "WebSocket não conectado. Execute robot_autonomous_control.py",
        variant: "destructive",
      });
    }
  };

  const handleDisconnect = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'disconnect_serial' }));
      onConnectionChange(false);
    }
  };

  if (isArduinoConnected) {
    const displayPort = connectedPort || toFullPort(selectedPort);

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 p-3 rounded-lg bg-primary/10">
          <Plug className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">Conectado: {displayPort}</span>
        </div>
        <Button onClick={handleDisconnect} variant="outline" className="w-full">
          Desconectar
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="port-select">Porta Serial</Label>
        <div className="flex gap-2">
          <Select value={selectedPort} onValueChange={setSelectedPort}>
            <SelectTrigger id="port-select" className="flex-1">
              <SelectValue placeholder="Selecione a porta" />
            </SelectTrigger>
            <SelectContent>
              {ports.map((port) => (
                <SelectItem key={port} value={port}>
                  {port === "SIM" ? "SIM (Arduino simulado)" : toFullPort(port)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Button
            variant="outline"
            size="icon"
            onClick={handleRefreshPorts}
            title="Atualizar portas"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Button
        onClick={handleConnect}
        disabled={isConnecting}
        className="w-full"
      >
        {isConnecting ? "Conectando..." : "Conectar Arduino"}
      </Button>
    </div>
  );
};
