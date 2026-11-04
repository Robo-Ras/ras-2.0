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

  // Tudo em vmin (a menor dimensão da tela): a carinha cresce até ocupar a tela, em pé ou deitada,
  // e nunca passa da altura (antes tinha tamanho fixo e cortava em telas baixas)
  return (
    <div className="flex h-[100dvh] w-screen flex-col items-center justify-center gap-[4vmin] overflow-hidden bg-black">
      <div
        className={`${config.bgColor} flex items-center justify-center rounded-full shadow-2xl transition-colors duration-500`}
        style={{ width: '68vmin', height: '68vmin' }}
      >
        <StatusIcon className={config.iconColor} style={{ width: '56vmin', height: '56vmin' }} strokeWidth={1.4} />
      </div>
      <h1 className="font-bold tracking-wider text-white" style={{ fontSize: '11vmin', lineHeight: 1 }}>
        {config.text}
      </h1>
    </div>
  );
};

export default TabletStatus;
