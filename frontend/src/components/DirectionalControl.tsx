import { useEffect, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Square, RotateCw, RotateCcw } from 'lucide-react';

interface DirectionalControlProps {
  onSendCommand: (m1: number, m2: number, m3: number) => void;
}

const DirectionalControl = ({ onSendCommand }: DirectionalControlProps) => {
  const [speed, setSpeed] = useState(60);
  const [activeDirection, setActiveDirection] = useState<string | null>(null);

  const moveForward = useCallback(() => {
    // Frente: M1=-speed, M2=0, M3=+speed
    console.log(`🎯 moveForward chamado com speed=${speed}, enviando: M1=${-speed}, M2=0, M3=${speed}`);
    onSendCommand(-speed, 0, speed);
    setActiveDirection('forward');
  }, [speed, onSendCommand]);
  
  const moveBackward = useCallback(() => {
    // Trás: M1=+speed, M2=0, M3=-speed
    console.log(`🎯 moveBackward chamado com speed=${speed}, enviando: M1=${speed}, M2=0, M3=${-speed}`);
    onSendCommand(speed, 0, -speed);
    setActiveDirection('backward');
  }, [speed, onSendCommand]);
  
  const moveRight = useCallback(() => {
    // Direita: M1=0, M2=+speed, M3=-speed
    console.log(`🎯 moveRight chamado com speed=${speed}, enviando: M1=0, M2=${speed}, M3=${-speed}`);
    onSendCommand(0, speed, -speed);
    setActiveDirection('right');
  }, [speed, onSendCommand]);
  
  const moveLeft = useCallback(() => {
    // Esquerda: M1=0, M2=-speed, M3=+speed
    console.log(`🎯 moveLeft chamado com speed=${speed}, enviando: M1=0, M2=${-speed}, M3=${speed}`);
    onSendCommand(0, -speed, speed);
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
    onSendCommand(rotateSpeed, rotateSpeed, rotateSpeed);
    setActiveDirection('clockwise');
  }, [speed, onSendCommand]);

  const rotateCounterClockwise = useCallback(() => {
    // Rotação anti-horária: M1=-speed, M2=-speed, M3=-speed (60% da velocidade)
    const rotateSpeed = Math.round(speed * 0.6);
    console.log(`🎯 rotateCounterClockwise chamado com speed=${speed}, enviando: M1=${-rotateSpeed}, M2=${-rotateSpeed}, M3=${-rotateSpeed}`);
    onSendCommand(-rotateSpeed, -rotateSpeed, -rotateSpeed);
    setActiveDirection('counterclockwise');
  }, [speed, onSendCommand]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
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

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h3 className="text-lg font-semibold">Controle Direcional</h3>
        <p className="text-sm text-muted-foreground">
          Use WASD, setas ou clique nos botões. Q/E para rotação. Espaço para parar.
        </p>
      </div>

      <div className="space-y-4 max-w-md mx-auto">
        <div className="space-y-2">
          <label className="text-sm font-medium">Velocidade: {speed}</label>
          <div className="flex gap-4 items-center">
            <Slider
              value={[speed]}
              onValueChange={(value) => setSpeed(value[0])}
              min={0}
              max={255}
              step={1}
              className="flex-1"
            />
            <Input
              type="number"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              min={0}
              max={255}
              className="w-20"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 max-w-xs mx-auto">
        <div></div>
        <Button
          onClick={moveForward}
          size="lg"
          variant={activeDirection === 'forward' ? 'default' : 'outline'}
          className="aspect-square p-0"
        >
          <ArrowUp size={24} />
        </Button>
        <div></div>

        <Button
           onClick={moveLeft}
           size="lg"
           variant={activeDirection === 'left' ? 'default' : 'outline'}
           className="aspect-square p-0"
         >
           <ArrowLeft size={24} />
         </Button>
         <Button
           onClick={stop}
           size="lg"
           variant="destructive"
           className="aspect-square p-0"
         >
           <Square size={24} />
         </Button>
         <Button
           onClick={moveRight}
           size="lg"
           variant={activeDirection === 'right' ? 'default' : 'outline'}
           className="aspect-square p-0"
         >
           <ArrowRight size={24} />
         </Button>

        <div></div>
        <Button
          onClick={moveBackward}
          size="lg"
          variant={activeDirection === 'backward' ? 'default' : 'outline'}
          className="aspect-square p-0"
        >
          <ArrowDown size={24} />
        </Button>
        <div></div>
      </div>

      <div className="flex gap-4 max-w-xs mx-auto mt-4">
        <Button
          onClick={rotateCounterClockwise}
          size="lg"
          variant={activeDirection === 'counterclockwise' ? 'default' : 'outline'}
          className="flex-1"
        >
          <RotateCcw size={20} className="mr-2" />
          Anti-horário (Q)
        </Button>
        <Button
          onClick={rotateClockwise}
          size="lg"
          variant={activeDirection === 'clockwise' ? 'default' : 'outline'}
          className="flex-1"
        >
          <RotateCw size={20} className="mr-2" />
          Horário (E)
        </Button>
      </div>

      <div className="text-xs text-muted-foreground text-center space-y-1">
         <p><strong>Comandos:</strong></p>
         <p>Frente: M1={-speed}, M2=0, M3={speed}</p>
         <p>Trás: M1={speed}, M2=0, M3={-speed}</p>
         <p>Direita: M1=0, M2={speed}, M3={-speed}</p>
         <p>Esquerda: M1=0, M2={-speed}, M3={speed}</p>
         <p>Horário: M1={speed}, M2={speed}, M3={speed}</p>
         <p>Anti-horário: M1={-speed}, M2={-speed}, M3={-speed}</p>
       </div>
    </div>
  );
};

export default DirectionalControl;