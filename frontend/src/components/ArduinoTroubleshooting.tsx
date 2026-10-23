import { AlertCircle, Terminal, CheckCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useState } from "react";

export const ArduinoTroubleshooting = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="w-full">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Problemas ao conectar?</AlertTitle>
          <AlertDescription>
            Clique aqui para ver o guia de diagnóstico
          </AlertDescription>
        </Alert>
      </CollapsibleTrigger>
      
      <CollapsibleContent className="mt-4 space-y-4">
        <div className="bg-muted/50 p-4 rounded-lg space-y-4">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <Terminal className="w-5 h-5" />
            Checklist de Conexão Arduino
          </h3>

          <div className="space-y-3 text-sm">
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 text-primary flex-shrink-0" />
              <div>
                <p className="font-medium">1. Servidor Python rodando?</p>
                <code className="block mt-1 bg-background p-2 rounded text-xs">
                  python robot_autonomous_control.py
                </code>
                <p className="text-muted-foreground mt-1">
                  Verifique se vê "✓ Servidor WebSocket rodando em ws://localhost:8765"
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 text-primary flex-shrink-0" />
              <div>
                <p className="font-medium">2. Arduino conectado via USB?</p>
                <code className="block mt-1 bg-background p-2 rounded text-xs">
                  ls -la /dev/ttyUSB* /dev/ttyACM*
                </code>
                <p className="text-muted-foreground mt-1">
                  Deve aparecer algo como: /dev/ttyUSB0 ou /dev/ttyACM0
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 text-primary flex-shrink-0" />
              <div>
                <p className="font-medium">3. Permissões configuradas?</p>
                <code className="block mt-1 bg-background p-2 rounded text-xs">
                  sudo usermod -a -G dialout $USER
                </code>
                <p className="text-muted-foreground mt-1">
                  ⚠️ Após executar, faça logout e login novamente
                </p>
                <p className="text-muted-foreground mt-1">
                  Verifique se está no grupo: <code>groups</code> (deve mostrar "dialout")
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 text-primary flex-shrink-0" />
              <div>
                <p className="font-medium">4. Porta correta selecionada?</p>
                <p className="text-muted-foreground mt-1">
                  Clique em "Atualizar portas" para buscar portas disponíveis
                </p>
                <p className="text-muted-foreground mt-1">
                  Geralmente é <strong>/dev/ttyUSB0</strong> ou <strong>/dev/ttyACM0</strong>
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 text-primary flex-shrink-0" />
              <div>
                <p className="font-medium">5. Testar conexão manualmente</p>
                <code className="block mt-1 bg-background p-2 rounded text-xs">
                  python -m serial.tools.miniterm /dev/ttyUSB0 9600
                </code>
                <p className="text-muted-foreground mt-1">
                  Use Ctrl+] para sair. Se não funcionar, o problema é na porta ou Arduino.
                </p>
              </div>
            </div>
          </div>

          <div className="border-t pt-4">
            <p className="text-xs text-muted-foreground">
              💡 <strong>Dica:</strong> Se nada funcionar, tente trocar o cabo USB ou a porta USB do notebook.
              Verifique também se o Arduino está com o sketch correto carregado.
            </p>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};
