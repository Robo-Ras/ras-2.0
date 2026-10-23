import { useEffect, useRef, useState } from "react";
import { Frown, Meh, Smile } from "lucide-react";
import { getWsUrl } from "@/lib/ws";

const TabletStatus = () => {
  const [status, setStatus] = useState<'disconnected' | 'stopped' | 'moving'>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const connectWebSocket = () => {
      // Se acessar via 10.21.10.186:8080, conecta em ws://10.21.10.186:8765
      const wsUrl = getWsUrl();
      console.log('📱 Tablet: Conectando ao WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Tablet: WebSocket conectado');
        setStatus('stopped');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'autonomous_status') {
            console.log('📱 Tablet: autonomous_status recebido:', data.enabled);
            setStatus(data.enabled ? 'moving' : 'stopped');
          } else if (data.type === 'serial_status') {
            console.log('📱 Tablet: serial_status recebido:', data.connected);
            if (!data.connected) {
              setStatus('stopped');
            }
          } else if (data.type === 'sensor_data') {
            console.log('📱 Tablet: sensor_data - robot_moving:', data.robot_moving);
            // Atualiza status com base no movimento do robô (manual ou autônomo)
            if (data.robot_moving) {
              setStatus('moving');
            } else {
              setStatus('stopped');
            }
          }
        } catch (error) {
          console.error('Erro ao processar mensagem:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('Erro WebSocket:', error);
        setStatus('disconnected');
      };

      ws.onclose = () => {
        console.log('WebSocket desconectado, tentando reconectar...');
        setStatus('disconnected');
        setTimeout(connectWebSocket, 3000);
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const getStatusConfig = () => {
    switch (status) {
      case 'disconnected':
        return {
          icon: Frown,
          bgColor: 'bg-red-500',
          iconColor: 'text-white',
          text: 'Desconectado'
        };
      case 'stopped':
        return {
          icon: Meh,
          bgColor: 'bg-orange-500',
          iconColor: 'text-white',
          text: 'Parado'
        };
      case 'moving':
        return {
          icon: Smile,
          bgColor: 'bg-green-500',
          iconColor: 'text-white',
          text: 'Andando'
        };
    }
  };

  const config = getStatusConfig();
  const StatusIcon = config.icon;

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-8">
      <div className="flex flex-col items-center gap-12">
        <div className={`${config.bgColor} rounded-full p-16 shadow-2xl transition-all duration-500`}>
          <StatusIcon className={`${config.iconColor} w-48 h-48 md:w-64 md:h-64`} strokeWidth={1.5} />
        </div>
        <h1 className="text-white text-6xl md:text-8xl font-bold tracking-wider">
          {config.text}
        </h1>
      </div>
    </div>
  );
};

export default TabletStatus;
