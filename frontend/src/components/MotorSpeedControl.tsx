import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';

interface MotorSpeedControlProps {
  onSendCommand: (m1: number, m2: number, m3: number) => void;
}

const MotorSpeedControl = ({ onSendCommand }: MotorSpeedControlProps) => {
  const [motor1, setMotor1] = useState<number>(0);
  const [motor2, setMotor2] = useState<number>(0);
  const [motor3, setMotor3] = useState<number>(0);

  const goCommand = () => {
    onSendCommand(motor1, motor2, motor3);
  };

  const stopCommand = () => {
    onSendCommand(0, 0, 0);
  };

  return (
    <div className="space-y-6">
      <div className="space-y-6">
        <div className="space-y-3">
          <Label>Motor 1</Label>
          <div className="space-y-2">
            <div className="flex items-center space-x-4">
              <Slider
                value={[motor1]}
                onValueChange={(value) => setMotor1(value[0])}
                min={-167}
                max={167}
                step={1}
                className="flex-1"
              />
              <div className="w-12 text-center text-sm font-mono">
                {motor1}
              </div>
            </div>
            <Input
              type="number"
              min="-167"
              max="167"
              value={motor1}
              onChange={(e) => setMotor1(Number(e.target.value))}
              placeholder="0"
              className="text-center"
            />
          </div>
        </div>
        
        <div className="space-y-3">
          <Label>Motor 2</Label>
          <div className="space-y-2">
            <div className="flex items-center space-x-4">
              <Slider
                value={[motor2]}
                onValueChange={(value) => setMotor2(value[0])}
                min={-167}
                max={167}
                step={1}
                className="flex-1"
              />
              <div className="w-12 text-center text-sm font-mono">
                {motor2}
              </div>
            </div>
            <Input
              type="number"
              min="-167"
              max="167"
              value={motor2}
              onChange={(e) => setMotor2(Number(e.target.value))}
              placeholder="0"
              className="text-center"
            />
          </div>
        </div>
        
        <div className="space-y-3">
          <Label>Motor 3</Label>
          <div className="space-y-2">
            <div className="flex items-center space-x-4">
              <Slider
                value={[motor3]}
                onValueChange={(value) => setMotor3(value[0])}
                min={-167}
                max={167}
                step={1}
                className="flex-1"
              />
              <div className="w-12 text-center text-sm font-mono">
                {motor3}
              </div>
            </div>
            <Input
              type="number"
              min="-167"
              max="167"
              value={motor3}
              onChange={(e) => setMotor3(Number(e.target.value))}
              placeholder="0"
              className="text-center"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Button onClick={goCommand} size="lg" className="w-full">
          GO
        </Button>
        <Button onClick={stopCommand} size="lg" variant="destructive" className="w-full">
          STOP
        </Button>
      </div>

      <div className="text-sm text-muted-foreground text-center">
        <p>Controle direto dos motores</p>
        <p>Valores de -167 a 167 (o sistema limita em 167; acima de 100 só em velocidade alta). Abaixo de 50 o motor não gira</p>
      </div>
    </div>
  );
};

export default MotorSpeedControl;
