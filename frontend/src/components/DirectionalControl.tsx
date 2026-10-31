import { useEffect, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { driveVector } from '@/lib/drive';
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Square, RotateCw, RotateCcw } from 'lucide-react';

interface DirectionalControlProps {
  onSendCommand: (m1: number, m2: number, m3: number) => void;
}

const DirectionalControl = ({ onSendCommand }: DirectionalControlProps) => {
  const [speed, setSpeed] = useState(60);
  const [activeDirection, setActiveDirection] = useState<string | null>(null);

  const moveForward = useCallback(() => {
    // Frente: M1=+speed, M2=0, M3=-speed (invertido após teste no robô real)
    console.log(`🎯 moveForward chamado com speed=${speed}, enviando: M1=${speed}, M2=0, M3=${-speed}`);
    onSendCommand(...driveVector('forward', speed));
    setActiveDirection('forward');
  }, [speed, onSendCommand]);
  
  const moveBackward = useCallback(() => {
    // Trás: M1=-speed, M2=0, M3=+speed (invertido após teste no robô real)
    console.log(`🎯 moveBackward chamado com speed=${speed}, enviando: M1=${-speed}, M2=0, M3=${speed}`);
    onSendCommand(...driveVector('backward', speed));
    setActiveDirection('backward');
  }, [speed, onSendCommand]);
  
  const moveRight = useCallback(() => {
    // Direita: M1=0, M2=+speed, M3=-speed
    console.log(`🎯 moveRight chamado com speed=${speed}, enviando: M1=0, M2=${speed}, M3=${-speed}`);
    onSendCommand(...driveVector('right', speed));
    setActiveDirection('right');
  }, [speed, onSendCommand]);
  
  const moveLeft = useCallback(() => {
    // Esquerda: M1=0, M2=-speed, M3=+speed
    console.log(`🎯 moveLeft chamado com speed=${speed}, enviando: M1=0, M2=${-speed}, M3=${speed}`);
    onSendCommand(...driveVector('left', speed));
    setActiveDirection('left');
  }, [speed, onSendCommand]);
  
  const stop = useCallback(() => {
    console.log(`🎯 stop chamado`);
    onSendCommand(0, 0, 0);
    setActiveDirection(null);
  }, [onSendCommand]);

  const rotateClockwise = useCallback(() => {
    // Rotação horária: M1=+speed, M2=+speed, M3=+speed (60% da velocidade)
    const rotateSpeed = Math.round(speed * 0.6);
    console.log(`🎯 rotateClockwise chamado com speed=${speed}, enviando: M1=${rotateSpeed}, M2=${rotateSpeed}, M3=${rotateSpeed}`);
    onSendCommand(...driveVector('clockwise', speed));
    setActiveDirection('clockwise');
  }, [speed, onSendCommand]);

  const rotateCounterClockwise = useCallback(() => {
    // Rotação anti-horária: M1=-speed, M2=-speed, M3=-speed (60% da velocidade)
    const rotateSpeed = Math.round(speed * 0.6);
    console.log(`🎯 rotateCounterClockwise chamado com speed=${speed}, enviando: M1=${-rotateSpeed}, M2=${-rotateSpeed}, M3=${-rotateSpeed}`);
    onSendCommand(...driveVector('counterclockwise', speed));
    setActiveDirection('counterclockwise');
  }, [speed, onSendCommand]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Não dirige o robô enquanto alguém digita num campo (ex.: velocidade)
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
      switch (event.key.toLowerCase()) {
        case 'w':
        case 'arrowup':
          moveForward();
          break;
        case 's':
        case 'arrowdown':
          moveBackward();
          break;
        case 'd':
        case 'arrowright':
          moveRight();
          break;
        case 'a':
        case 'arrowleft':
          moveLeft();
          break;
        case 'q':
          rotateCounterClockwise();
          break;
        case 'e':
          rotateClockwise();
          break;
        case ' ':
          stop();
          event.preventDefault();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [moveForward, moveBackward, moveRight, moveLeft, stop, rotateClockwise, rotateCounterClockwise]);

  const padButton = (dir: string, onClick: () => void, icon: React.ReactNode, label: string) => (
    <Button
      onClick={onClick}
      variant={activeDirection === dir ? 'default' : 'secondary'}
      className="h-14 w-full p-0"
      aria-label={label}
      title={label}
    >
      {icon}
    </Button>
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2 max-w-[240px] mx-auto">
        {padButton('counterclockwise', rotateCounterClockwise, <RotateCcw size={20} />, 'Girar anti-horário (Q)')}
        {padButton('forward', moveForward, <ArrowUp size={24} />, 'Frente (W)')}
        {padButton('clockwise', rotateClockwise, <RotateCw size={20} />, 'Girar horário (E)')}
        {padButton('left', moveLeft, <ArrowLeft size={24} />, 'Esquerda (A)')}
        <Button onClick={stop} variant="destructive" className="h-14 w-full p-0" aria-label="Parar (espaço)" title="Parar (espaço)">
          <Square size={22} />
        </Button>
        {padButton('right', moveRight, <ArrowRight size={24} />, 'Direita (D)')}
        <div />
        {padButton('backward', moveBackward, <ArrowDown size={24} />, 'Trás (S)')}
        <div />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Velocidade</span>
          <Input
            type="number"
            value={speed}
            onChange={(e) => setSpeed(Math.max(0, Math.min(255, Number(e.target.value))))}
            min={0}
            max={255}
            className="h-8 w-20 text-right tabular"
          />
        </div>
        <Slider value={[speed]} onValueChange={(value) => setSpeed(value[0])} min={0} max={255} step={1} />
      </div>

      <p className="text-xs text-muted-foreground text-center">
        Teclado: <kbd className="rounded bg-muted px-1">W A S D</kbd> ou setas · <kbd className="rounded bg-muted px-1">Q</kbd>/<kbd className="rounded bg-muted px-1">E</kbd> giram · <kbd className="rounded bg-muted px-1">espaço</kbd> para
      </p>

      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer select-none">Valores enviados aos motores</summary>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono tabular">
          <span>Frente</span><span>{speed}, 0, {-speed}</span>
          <span>Trás</span><span>{-speed}, 0, {speed}</span>
          <span>Direita</span><span>0, {speed}, {-speed}</span>
          <span>Esquerda</span><span>0, {-speed}, {speed}</span>
          <span>Horário</span><span>{Math.round(speed * 0.6)} × 3</span>
          <span>Anti-horário</span><span>{-Math.round(speed * 0.6)} × 3</span>
        </div>
      </details>
    </div>
  );
};

export default DirectionalControl;