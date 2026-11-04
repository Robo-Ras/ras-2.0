import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, OctagonX, RotateCcw, RotateCw, VideoOff } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { driveVector, type Direction } from "@/lib/drive";
import { getWsUrl } from "@/lib/ws";

// Controle pelo celular: só os botões de movimento. Segure para andar, solte para parar.
// Enquanto o dedo está na tela o comando é repetido; o backend para o robô se ele deixar de chegar.
const REPEAT_MS = 150;
const SPEED_KEY = "ras-controle-speed";

const loadSpeed = () => {
  try {
    const saved = Number(localStorage.getItem(SPEED_KEY));
    if (saved >= 20 && saved <= 255) return saved;
  } catch {
    // sem localStorage (modo privado): usa o padrão
  }
  return 60;
};

type Link = "connecting" | "online" | "offline";

const Controle = () => {
  const [link, setLink] = useState<Link>("connecting");
  const [arduino, setArduino] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);
  const [speed, setSpeed] = useState(loadSpeed);
  const [active, setActive] = useState<Direction | null>(null);
  const [frame, setFrame] = useState<string | null>(null); // preview da câmera (JPEG em base64)

  const wsRef = useRef<WebSocket | null>(null);
  const speedRef = useRef(speed);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const holdingRef = useRef<Direction | null>(null);

  useEffect(() => {
    speedRef.current = speed;
    try {
      localStorage.setItem(SPEED_KEY, String(speed));
    } catch {
      // ignora
    }
  }, [speed]);

  const send = useCallback((message: object) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  // soft=true (soltou o botão): o robô freia em 1 s (cai à metade e para). Sem soft (PARAR, PARE, tela apagou):
  // corta na hora. Duas vezes: se um pacote se perder, o segundo ainda vale (e o backend também para sozinho)
  const stop = useCallback((soft = false) => {
    clearInterval(timerRef.current);
    timerRef.current = undefined;
    holdingRef.current = null;
    setActive(null);
    send({ type: "move", m1: 0, m2: 0, m3: 0, soft });
    send({ type: "move", m1: 0, m2: 0, m3: 0, soft });
  }, [send]);

  const start = useCallback(
    (direction: Direction) => {
      if (holdingRef.current === direction) return;
      clearInterval(timerRef.current);
      holdingRef.current = direction;
      setActive(direction);
      const tick = () => {
        const [m1, m2, m3] = driveVector(direction, speedRef.current);
        // sem conexão: não segura o botão "ativo" à toa
        if (!send({ type: "move", m1, m2, m3, hold: true })) stop();
      };
      tick();
      timerRef.current = setInterval(tick, REPEAT_MS);
      try {
        navigator.vibrate?.(15);
      } catch {
        // iOS não tem vibrate
      }
    },
    [send, stop],
  );

  const emergency = useCallback(() => {
    stop(false);
    send({ type: "set_autonomous", enabled: false });
    try {
      navigator.vibrate?.([60, 40, 60]);
    } catch {
      // ignora
    }
  }, [send, stop]);

  // Conexão com o backend (reconecta sozinha)
  useEffect(() => {
    let closed = false;
    let reconnect: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      setLink("connecting");
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;
      ws.onopen = () => {
        setLink("online");
        // modo leve: só o estado e a imagem da câmera principal (sem LiDAR nem a segunda câmera)
        ws.send(JSON.stringify({ type: "set_lite", enabled: true, camera: true }));
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "serial_status") setArduino(data.connected ? data.port ?? "ok" : null);
        else if (data.type === "sensor_data") {
          setMoving(!!data.robot_moving);
          if (data.camera_image) setFrame(data.camera_image);
        }
      };
      ws.onclose = () => {
        holdingRef.current = null;
        clearInterval(timerRef.current);
        setActive(null);
        setLink("offline");
        setMoving(false);
        setFrame(null);
        if (!closed) reconnect = setTimeout(connect, 2000);
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(reconnect);
      stop(false);
      wsRef.current?.close();
    };
  }, [stop]);

  // Saiu da aba, bloqueou a tela ou perdeu o foco: para
  useEffect(() => {
    const onHide = () => stop(false);
    const onVisibility = () => document.hidden && stop(false);
    window.addEventListener("blur", onHide);
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("blur", onHide);
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [stop]);

  const holdProps = (direction: Direction) => ({
    onPointerDown: (e: React.PointerEvent<HTMLButtonElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      start(direction);
    },
    onPointerUp: () => stop(true),
    onPointerCancel: () => stop(true),
    onLostPointerCapture: () => stop(true),
    onContextMenu: (e: React.SyntheticEvent) => e.preventDefault(),
  });

  const padClass = (direction: Direction) =>
    `flex aspect-square w-full select-none items-center justify-center rounded-xl border text-foreground transition-colors disabled:opacity-40 ${
      active === direction ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card active:bg-accent"
    }`;
  const disabled = link !== "online";

  const status =
    link === "online" ? (arduino ? `Arduino ${arduino}` : "Arduino desconectado") : link === "connecting" ? "Conectando..." : "Sem conexão";
  const statusTone = link === "online" && arduino ? "bg-emerald-400" : link === "online" ? "bg-amber-400" : "bg-red-500";

  return (
    <div
      className="mx-auto flex min-h-[100dvh] max-w-md flex-col select-none"
      style={{ touchAction: "none", WebkitUserSelect: "none", WebkitTouchCallout: "none" }}
    >
      <header className="flex items-center justify-between gap-3 px-3 py-2">
        <div className="min-w-0">
          <h1 className="text-base font-bold leading-tight">RAS 2.0</h1>
          <div className="flex items-center gap-1.5 truncate text-[11px] text-muted-foreground">
            <span className={`h-2 w-2 shrink-0 rounded-full ${statusTone}`} />
            {status}
            {link === "online" && <span>· {moving ? "andando" : "parado"}</span>}
          </div>
        </div>
        <button
          onClick={emergency}
          disabled={disabled}
          className="flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-destructive px-3.5 text-sm font-bold tracking-wide text-destructive-foreground active:opacity-80 disabled:opacity-40"
        >
          <OctagonX className="h-5 w-5" />
          PARAR
        </button>
      </header>

      {/* Preview da C270 na largura toda; a altura que sobra fica para os botões */}
      <div className="relative aspect-[4/3] w-full overflow-hidden bg-black">
        {frame ? (
          <img src={`data:image/jpeg;base64,${frame}`} alt="Câmera do robô" className="h-full w-full object-cover" draggable={false} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1.5 text-muted-foreground">
            <VideoOff className="h-7 w-7" />
            <span className="text-xs">{link === "online" ? "Sem imagem da câmera" : "Sem conexão"}</span>
          </div>
        )}
      </div>

      {link === "offline" && (
        <div className="mx-3 mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs">
          Sem conexão com o robô. Confira o Wi-Fi do notebook. Tentando de novo...
        </div>
      )}

      <main className="flex flex-1 flex-col justify-center gap-3 px-4 py-3">
        <div className="mx-auto grid w-full max-w-[236px] grid-cols-3 gap-2">
          <button disabled={disabled} className={padClass("counterclockwise")} aria-label="Girar anti-horário" {...holdProps("counterclockwise")}>
            <RotateCcw className="h-6 w-6" />
          </button>
          <button disabled={disabled} className={padClass("forward")} aria-label="Frente" {...holdProps("forward")}>
            <ArrowUp className="h-8 w-8" />
          </button>
          <button disabled={disabled} className={padClass("clockwise")} aria-label="Girar horário" {...holdProps("clockwise")}>
            <RotateCw className="h-6 w-6" />
          </button>

          <button disabled={disabled} className={padClass("left")} aria-label="Esquerda" {...holdProps("left")}>
            <ArrowLeft className="h-8 w-8" />
          </button>
          <button
            disabled={disabled}
            onPointerDown={() => stop(false)}
            className="flex aspect-square w-full items-center justify-center rounded-xl border border-destructive/50 bg-destructive/15 text-xs font-bold tracking-wide text-destructive active:bg-destructive/30 disabled:opacity-40"
          >
            PARE
          </button>
          <button disabled={disabled} className={padClass("right")} aria-label="Direita" {...holdProps("right")}>
            <ArrowRight className="h-8 w-8" />
          </button>

          <div />
          <button disabled={disabled} className={padClass("backward")} aria-label="Trás" {...holdProps("backward")}>
            <ArrowDown className="h-8 w-8" />
          </button>
          <div />
        </div>

        <div className="space-y-1.5 rounded-xl border border-border bg-card px-3 py-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium">Velocidade</span>
            <span className="tabular text-sm font-semibold">{speed}</span>
          </div>
          <Slider value={[speed]} onValueChange={(v) => setSpeed(v[0])} min={20} max={255} step={5} />
        </div>

        <p className="text-center text-[11px] text-muted-foreground">Segure para andar; ao soltar o robô freia e para.</p>
      </main>
    </div>
  );
};

export default Controle;
