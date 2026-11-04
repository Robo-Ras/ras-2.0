import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Mic, MicOff } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { interpretVoice, voiceCommandLabel, type VoiceCommandEvent, type VoiceCommandId } from '@/lib/voiceCommands';

interface VoiceControlProps {
  onVoiceCommand: (command: VoiceCommandId, text: string) => void;
  lastVoiceEvent?: VoiceCommandEvent | null;
  isConnected: boolean;
}

const STATUS_TEXT: Record<string, string> = {
  ok: 'executado',
  no_robot: 'Arduino desconectado',
  not_implemented: 'ainda não implementado no robô',
  duplicate: 'o outro reconhecedor (José) chegou primeiro',
  unknown: 'desconhecido pelo backend',
};

const VoiceControl = ({ onVoiceCommand, lastVoiceEvent, isConnected }: VoiceControlProps) => {
  const [isListening, setIsListening] = useState(false);
  const [lastCommand, setLastCommand] = useState<string>('');
  const [transcript, setTranscript] = useState<string>('');
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [micPermission, setMicPermission] = useState<'granted' | 'denied' | 'prompt'>('prompt');
  const recognitionRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number>(0);
  const listeningRef = useRef(false); // o reconhecimento reinicia sozinho enquanto estiver ligado
  const onCommandRef = useRef(onVoiceCommand); // sempre a versão mais nova da função, sem recriar o reconhecimento
  const firedRef = useRef<Set<number>>(new Set()); // resultados desta sessão que já viraram comando
  const calledUntilRef = useRef(0); // depois de dizer só "José", por alguns segundos a palavra do comando basta
  const { toast } = useToast();
  onCommandRef.current = onVoiceCommand;

  // Reconhecimento nativo do Chrome, criado uma vez só. Fala o comando como "José, frente".
  // O José (Vosk) ouve a mesma frase ao mesmo tempo: o backend executa o primeiro que chegar.
  useEffect(() => {
    // @ts-ignore
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      toast({
        title: "Navegador não suportado",
        description: "Seu navegador não suporta reconhecimento de voz. Use Chrome ou Edge.",
        variant: "destructive",
      });
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true; // age já no resultado parcial, sem esperar a frase terminar
    recognition.lang = 'pt-BR';
    recognition.maxAlternatives = 1;

    recognition.onstart = () => firedRef.current.clear();

    recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = String(result[0].transcript).trim();
        setTranscript(text);
        if (firedRef.current.has(i)) continue;

        const heard = interpretVoice(text, Date.now() < calledUntilRef.current);
        if (heard.command && heard.type === 'comando') {
          // "para" só vale quando a frase termina: "para frente" começa igual a "para"
          if (heard.command === 'parar' && !result.isFinal) continue;
          firedRef.current.add(i);
          calledUntilRef.current = 0;
          const command = heard.command as VoiceCommandId;
          onCommandRef.current(command, text);
          setLastCommand(`${voiceCommandLabel(command)} (ouvido: "${text}")`);
        } else if (heard.called && !heard.command && result.isFinal) {
          calledUntilRef.current = Date.now() + 6000; // só "José": o próximo comando não precisa dele
        }
      }
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return; // normal
      if (event.error === 'not-allowed') {
        toast({
          title: "Permissão Negada",
          description: "Permita o acesso ao microfone nas configurações do navegador",
          variant: "destructive",
        });
        listeningRef.current = false;
        setIsListening(false);
        return;
      }
      toast({ title: "Erro no reconhecimento", description: `Erro: ${event.error}`, variant: "destructive" });
    };

    recognition.onend = () => {
      // O Chrome encerra a sessão de tempos em tempos: reinicia enquanto o botão estiver ligado
      if (!listeningRef.current) return;
      setTimeout(() => {
        try {
          if (listeningRef.current) recognition.start();
        } catch {
          // já iniciado
        }
      }, 250);
    };

    recognitionRef.current = recognition;
    return () => {
      listeningRef.current = false;
      recognition.onend = null;
      recognition.stop();
    };
  }, []);

  const startAudioMonitoring = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);
      
      analyserRef.current.fftSize = 256;
      const bufferLength = analyserRef.current.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      const updateAudioLevel = () => {
        if (!analyserRef.current) return;
        
        analyserRef.current.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / bufferLength;
        setAudioLevel(Math.min(100, (average / 255) * 200));
        
        animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
      };
      
      updateAudioLevel();
      console.log('✅ Monitoramento de áudio iniciado');
    } catch (error) {
      console.error('❌ Erro ao monitorar áudio:', error);
    }
  };

  const stopAudioMonitoring = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setAudioLevel(0);
    console.log('⏹️ Monitoramento de áudio parado');
  };

  const checkMicPermission = async () => {
    try {
      const result = await navigator.permissions.query({ name: 'microphone' as PermissionName });
      setMicPermission(result.state as 'granted' | 'denied' | 'prompt');
      console.log('🎤 Permissão do microfone:', result.state);
    } catch (error) {
      console.log('ℹ️ Não foi possível verificar permissão automaticamente');
    }
  };

  const toggleListening = async () => {
    console.log('🎤 Toggle listening. Estado atual:', isListening, '| Conectado:', isConnected);
    
    if (!isConnected) {
      toast({
        title: "Robô Desconectado",
        description: "Conecte-se ao robô antes de usar comandos de voz",
        variant: "destructive",
      });
      return;
    }

    if (isListening) {
      console.log('🛑 Desativando reconhecimento...');
      listeningRef.current = false;
      recognitionRef.current?.stop();
      setIsListening(false);
      setTranscript('');
      stopAudioMonitoring();
      toast({
        title: "Reconhecimento Desativado",
        description: "Comandos de voz desativados",
      });
    } else {
      try {
        console.log('▶️ Solicitando permissão do microfone...');
        
        await startAudioMonitoring();
        setMicPermission('granted');
        console.log('✅ Permissão concedida');
        
        console.log('▶️ Iniciando reconhecimento...');
        listeningRef.current = true;
        recognitionRef.current?.start();
        setIsListening(true);
        toast({
          title: "Reconhecimento Ativado",
          description: "🎤 Diga: José frente · José trás · José direita · José esquerda · José gira · pare",
        });
      } catch (error) {
        console.error('❌ Erro ao acessar microfone:', error);
        setMicPermission('denied');
        toast({
          title: "Erro de Permissão",
          description: "Permita o acesso ao microfone nas configurações do navegador",
          variant: "destructive",
        });
      }
    }
  };

  useEffect(() => {
    checkMicPermission();
    return () => {
      stopAudioMonitoring();
    };
  }, []);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Mic className="h-5 w-5 text-primary" />
            Voz
          </CardTitle>
          <Button
            onClick={toggleListening}
            size="sm"
            variant={isListening ? 'default' : 'outline'}
            className="gap-1.5"
            disabled={!isConnected}
          >
            {isListening ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
            {isListening ? 'Ouvindo' : 'Microfone do navegador'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {lastVoiceEvent ? (
          <div className="rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">{voiceCommandLabel(lastVoiceEvent.command)}</span>
              <span className="text-xs text-muted-foreground">
                {lastVoiceEvent.source === 'jose' ? 'José' : 'navegador'} · {STATUS_TEXT[lastVoiceEvent.status] ?? lastVoiceEvent.status}
              </span>
            </div>
            {lastVoiceEvent.text && <p className="mt-0.5 text-xs text-muted-foreground">"{lastVoiceEvent.text}"</p>}
          </div>
        ) : (
          <p className="text-muted-foreground">
            Nenhum comando ainda. Fale com o José (rosto em <span className="font-mono">:8090</span>) ou use o microfone do navegador.
          </p>
        )}

        {isListening && (
          <div className="space-y-2 rounded-md border border-border bg-muted/40 px-3 py-2">
            <div className="h-1.5 overflow-hidden rounded-full bg-background">
              <div className="h-full bg-emerald-400 transition-all duration-100" style={{ width: `${audioLevel}%` }} />
            </div>
            <p className="font-mono text-xs">{transcript || 'Aguardando fala...'}</p>
            {lastCommand && <p className="text-xs text-muted-foreground">Último: {lastCommand}</p>}
          </div>
        )}

        {micPermission === 'denied' && (
          <p className="text-xs text-red-600 dark:text-red-400">Microfone bloqueado: libere nas configurações do navegador.</p>
        )}

        <p className="text-xs text-muted-foreground">
          "José, frente" · "José, trás" · "José, direita" · "José, esquerda" · "José, gira" · <span className="font-semibold">"pare"</span>
        </p>
      </CardContent>
    </Card>
  );
};

export default VoiceControl;
