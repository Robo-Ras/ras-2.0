import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Mic, MicOff } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { identifyVoiceCommand, voiceCommandLabel, type VoiceCommandEvent, type VoiceCommandId } from '@/lib/voiceCommands';

interface VoiceControlProps {
  onVoiceCommand: (command: VoiceCommandId, text: string) => void;
  lastVoiceEvent?: VoiceCommandEvent | null;
  isConnected: boolean;
}

const STATUS_TEXT: Record<string, string> = {
  ok: 'executado',
  no_robot: 'Arduino desconectado',
  not_implemented: 'ainda não implementado no robô',
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
  const { toast } = useToast();

  useEffect(() => {
    console.log('🎙️ Inicializando Web Speech API...');
    
    // Verificar se o navegador suporta Web Speech API
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.error('❌ Navegador não suporta Web Speech API');
      toast({
        title: "Navegador não suportado",
        description: "Seu navegador não suporta reconhecimento de voz. Use Chrome ou Edge.",
        variant: "destructive",
      });
      return;
    }

    // @ts-ignore
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'pt-BR';
    recognition.maxAlternatives = 1;

    console.log('✅ Web Speech API configurada:', {
      continuous: recognition.continuous,
      interimResults: recognition.interimResults,
      lang: recognition.lang
    });

    recognition.onstart = () => {
      console.log('🎤 Reconhecimento de voz INICIADO');
    };

    recognition.onresult = (event: any) => {
      const current = event.resultIndex;
      const transcript = event.results[current][0].transcript.toLowerCase().trim();
      const confidence = event.results[current][0].confidence;
      
      console.log('📝 Transcrição:', transcript, '| Confiança:', confidence);
      setTranscript(transcript);

      // Só processar comandos quando for resultado final
      if (event.results[current].isFinal) {
        console.log('✅ Resultado final:', transcript);
        processCommand(transcript);
      }
    };

    recognition.onerror = (event: any) => {
      console.error('❌ Erro no reconhecimento de voz:', event.error);
      if (event.error === 'no-speech') {
        console.log('ℹ️ Nenhuma fala detectada (normal)');
        return;
      }
      if (event.error === 'not-allowed') {
        toast({
          title: "Permissão Negada",
          description: "Permita o acesso ao microfone nas configurações do navegador",
          variant: "destructive",
        });
        setIsListening(false);
        return;
      }
      toast({
        title: "Erro no reconhecimento",
        description: `Erro: ${event.error}`,
        variant: "destructive",
      });
    };

    recognition.onend = () => {
      console.log('⏹️ Reconhecimento de voz FINALIZADO');
      // Reiniciar automaticamente se ainda estiver no modo listening
      if (isListening) {
        console.log('🔄 Reiniciando reconhecimento...');
        try {
          recognition.start();
        } catch (error) {
          console.error('❌ Erro ao reiniciar:', error);
          setIsListening(false);
        }
      }
    };

    recognitionRef.current = recognition;

    return () => {
      console.log('🧹 Limpando reconhecimento de voz');
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, [isListening]);

  const processCommand = (text: string) => {
    console.log('🔍 Processando comando:', text);
    const command = identifyVoiceCommand(text);
    if (!command) {
      console.log('❌ Comando não reconhecido:', text);
      toast({
        title: "❌ Comando não reconhecido",
        description: `Você disse: "${text}"`,
        variant: "destructive"
      });
      return;
    }
    console.log('✅ Comando reconhecido:', command);
    // O backend executa e devolve {type: 'voice_command'}, que aparece em lastVoiceEvent
    onVoiceCommand(command, text);
    setLastCommand(`${voiceCommandLabel(command)} (reconhecido: "${text}")`);
  };

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
        recognitionRef.current?.start();
        setIsListening(true);
        toast({
          title: "Reconhecimento Ativado",
          description: "🎤 Ex.: vai pra frente, meia volta, para, modo autônomo",
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
          <p className="text-xs text-red-400">Microfone bloqueado: libere nas configurações do navegador.</p>
        )}

        <p className="text-xs text-muted-foreground">
          "vai pra frente", "meia volta", "volta completa", <span className="font-semibold">"para"</span>, "modo autônomo"
        </p>
      </CardContent>
    </Card>
  );
};

export default VoiceControl;
