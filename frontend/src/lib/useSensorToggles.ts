import { useCallback, useState } from "react";

// Quais sensores aparecem na interface. Só esconde da tela: o backend continua lendo todos.
// Fica salvo no navegador, então recarregar a página não traz de volta o que foi desligado.
export type SensorKey = "lidar" | "c270" | "d435";

const STORAGE_KEY = "ras-sensores-visiveis";
const ALL_ON: Record<SensorKey, boolean> = { lidar: true, c270: true, d435: true };

const load = (): Record<SensorKey, boolean> => {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    return { ...ALL_ON, ...saved };
  } catch {
    return ALL_ON; // sem localStorage ou JSON ruim: tudo ligado
  }
};

export const useSensorToggles = () => {
  const [enabled, setEnabled] = useState(load);

  const setSensor = useCallback((key: SensorKey, value: boolean) => {
    setEnabled((prev) => {
      const next = { ...prev, [key]: value };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignora
      }
      return next;
    });
  }, []);

  return { enabled, setSensor };
};
