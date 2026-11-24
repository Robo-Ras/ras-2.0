import { useEffect, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ArrowUpLeft, ArrowUpRight, ArrowDownLeft, ArrowDownRight, Square, RotateCw, RotateCcw } from 'lucide-react';
import { NUMPAD_ROWS, DRIVE_KEY_LABELS, SPEED_DEFAULT, SPEED_MIN, SPEED_MAX, clampSpeed, keyToDrive, type DriveKey } from '@/lib/drive';

interface DirectionalControlProps {
  onDrive: (key: DriveKey, speed: number) => void;
  onStop: () => void;
}

const ICONS: Record<number, JSX.Element> = {
  7: <ArrowUpLeft size={26} />, 8: <ArrowUp size={26} />, 9: <ArrowUpRight size={26} />,
  4: <ArrowLeft size={26} />, 5: <Square size={22} />, 6: <ArrowRight size={26} />,
  1: <ArrowDownLeft size={26} />, 2: <ArrowDown size={26} />, 3: <ArrowDownRight size={26} />,
};

const DirectionalControl = ({ onDrive, onStop }: DirectionalControlProps) => {
  const [speed, setSpeed] = useState(SPEED_DEFAULT);
  const [active, setActive] = useState<DriveKey | null>(null);

  const press = useCallback((key: DriveKey) => {
    if (key === 5) {
      onStop(); // o 5 para o robô na hora
      setActive(null);
      return;
    }
    onDrive(key, speed); // só a tecla: o backend calcula os motores
    setActive(key);
  }, [speed, onDrive, onStop]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Não dirige o robô enquanto alguém digita num campo (ex.: velocidade)
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
      if (event.repeat) return; // segurar a tecla não reenvia
      const key = keyToDrive(event.key);
      if (key === null) return;
      if (event.key === ' ') event.preventDefault();
      press(key);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [press]);

  return (
    <div className="space-y-4">
      {/* Mesma disposição do teclado numérico: 7 8 9 / 4 5 6 / 1 2 3 */}
      <div className="grid grid-cols-3 gap-2 max-w-[240px] mx-auto">
        {NUMPAD_ROWS.flat().map((key) => (
          <Button
            key={String(key)}
            onClick={() => press(key)}
            variant={key === 5 ? 'destructive' : active === key ? 'default' : 'secondary'}
            className="h-14 w-full p-0 relative"
            aria-label={`${DRIVE_KEY_LABELS[key]} (tecla ${key})`}
            title={`${DRIVE_KEY_LABELS[key]} (tecla ${key})`}
          >
            {ICONS[key as number]}
            <span className="absolute bottom-0.5 right-1.5 text-[10px] opacity-60">{key}</span>
          </Button>
        ))}
      </div>

      <div className="flex gap-2 max-w-[240px] mx-auto">
        {(['ccw', 'cw'] as DriveKey[]).map((key) => (
          <Button
            key={String(key)}
            onClick={() => press(key)}
            variant={active === key ? 'default' : 'secondary'}
            className="flex-1 gap-1.5"
            title={DRIVE_KEY_LABELS[key]}
          >
            {key === 'ccw' ? <RotateCcw size={18} /> : <RotateCw size={18} />}
            {key === 'ccw' ? 'Q' : 'E'}
          </Button>
        ))}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Velocidade</span>
          <Input
            type="number"
            value={speed}
            onChange={(e) => setSpeed(clampSpeed(Number(e.target.value)))}
            min={SPEED_MIN}
            max={SPEED_MAX}
            className="h-8 w-20 text-right tabular"
          />
        </div>
        <Slider value={[speed]} onValueChange={(value) => setSpeed(value[0])} min={SPEED_MIN} max={SPEED_MAX} step={1} />
        <p className="text-[11px] text-muted-foreground">
          {SPEED_DEFAULT} é o padrão; o PWM dos motores sobe junto com a velocidade (limites da conta no cartão Calibração).
        </p>
      </div>

      <p className="text-xs text-muted-foreground text-center">
        Teclado numérico: <kbd className="rounded bg-muted px-1">7 8 9 / 4 5 6 / 1 2 3</kbd>, o{' '}
        <kbd className="rounded bg-muted px-1">5</kbd> para o robô · <kbd className="rounded bg-muted px-1">Q</kbd>/
        <kbd className="rounded bg-muted px-1">E</kbd> giram · W A S D e setas também valem
      </p>
    </div>
  );
};

export default DirectionalControl;
