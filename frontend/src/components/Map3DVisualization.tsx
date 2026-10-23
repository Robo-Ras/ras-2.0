import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useEffect, useRef } from "react";

interface Point3D {
  points: number[][];
  colors: number[][];
}

interface Map3DVisualizationProps {
  pointCloud?: Point3D;
}

const Map3DVisualization = ({ pointCloud }: Map3DVisualizationProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();
  const rotationRef = useRef({ x: 0, y: 0 });
  const pointCloudRef = useRef<Point3D | undefined>(pointCloud);

  // Atualiza referência quando pointCloud mudar
  useEffect(() => {
    pointCloudRef.current = pointCloud;
  }, [pointCloud]);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const scale = 100; // Escala de visualização

    const drawPointCloud = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = 'hsl(var(--background))';
      ctx.fillRect(0, 0, width, height);

      // Desenha grid
      ctx.strokeStyle = 'hsl(var(--border))';
      ctx.lineWidth = 1;
      for (let i = -5; i <= 5; i++) {
        const x = width / 2 + i * scale;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();

        const y = height / 2 + i * scale;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Desenha pontos 3D
      const currentCloud = pointCloudRef.current;
      if (currentCloud && currentCloud.points && currentCloud.points.length > 0) {
        const centerX = width / 2;
        const centerY = height / 2;

        // Ordena pontos por profundidade (z) para melhor visualização
        const sortedPoints = currentCloud.points.map((point, i) => ({
          point,
          color: currentCloud.colors[i],
          z: point[2]
        })).sort((a, b) => b.z - a.z);

        sortedPoints.forEach(({ point, color }) => {
          const [x, y, z] = point;

          // Rotação simples
          const cosX = Math.cos(rotationRef.current.x);
          const sinX = Math.sin(rotationRef.current.x);
          const cosY = Math.cos(rotationRef.current.y);
          const sinY = Math.sin(rotationRef.current.y);

          // Aplica rotação
          const y1 = y * cosX - z * sinX;
          const z1 = y * sinX + z * cosX;
          const x1 = x * cosY + z1 * sinY;
          const z2 = -x * sinY + z1 * cosY;

          // Projeção perspectiva
          const perspective = 400 / (400 + z2);
          const screenX = centerX + x1 * scale * perspective;
          const screenY = centerY - y1 * scale * perspective;

          // Desenha ponto
          const size = Math.max(1, 3 * perspective);
          ctx.fillStyle = `rgb(${color[0] * 255}, ${color[1] * 255}, ${color[2] * 255})`;
          ctx.beginPath();
          ctx.arc(screenX, screenY, size, 0, Math.PI * 2);
          ctx.fill();
        });
      }

      // Auto-rotação lenta
      rotationRef.current.y += 0.005;

      animationRef.current = requestAnimationFrame(drawPointCloud);
    };

    drawPointCloud();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []); // Só executa uma vez no mount

  // Controle de rotação com mouse
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let isDragging = false;
    let lastX = 0;
    let lastY = 0;

    const handleMouseDown = (e: MouseEvent) => {
      isDragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;

      const deltaX = e.clientX - lastX;
      const deltaY = e.clientY - lastY;

      rotationRef.current.y += deltaX * 0.01;
      rotationRef.current.x += deltaY * 0.01;

      lastX = e.clientX;
      lastY = e.clientY;
    };

    const handleMouseUp = () => {
      isDragging = false;
    };

    canvas.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      canvas.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reconstrução 3D do Ambiente</CardTitle>
        <CardDescription>
          Mapa 3D gerado em tempo real pelo LiDAR (arraste para rotacionar)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <canvas
          ref={canvasRef}
          width={600}
          height={400}
          className="w-full border border-border rounded-lg bg-background cursor-move"
        />
        {!pointCloud && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-muted-foreground">Aguardando dados de reconstrução 3D...</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default Map3DVisualization;
