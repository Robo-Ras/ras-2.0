# omni_drive_controller

Base omni de 3 rodas do RAS no ROS 2 Humble: `/cmd_vel` → PWM das rodas → Arduino
(`ras-2.0/arduino/arduino_robot_control.ino`, sem mudar o sketch), mais odometria simulada
com o `nav2_loopback_sim` portado para o Humble no fork do Nav2
(`ros2_ws/src/navigation2`, branch `humble-ras-ports`).

```
/cmd_vel ──► omni_kinematics ──/wheel_pwm──► arduino_bridge ──serial "m1,m2,m3\n"──► Arduino
                   │
                   └──/applied_cmd_vel──► loopback_simulator ──► /odom, TF map→odom→base_link
```

| Nó | Faz |
|----|-----|
| `omni_kinematics` | cinemática inversa, saturação que preserva a direção, rampa de aceleração, para os motores se `/cmd_vel` sumir por 0,5 s |
| `arduino_bridge` | serial 9600, espera o reset do Arduino, reenvia só quando muda (máx. 10 Hz) e a cada 0,5 s como keepalive, manda `0,0,0` se `/wheel_pwm` sumir e ao fechar, reconecta se o cabo cair. Publica `/arduino/connected` |
| `loopback_simulator` | integra a velocidade **aplicada** (já depois de saturação, rampa e watchdog) e publica `/odom` e o TF. Começa já localizado em `initial_pose` |

## Rodar

```bash
cd ~/ros2_ws
# --packages-up-to compila só o omni e o que ele usa (inclui o nav2_loopback_sim do fork).
# NÃO rode um `colcon build` puro: ele tentaria compilar o Nav2 inteiro do fork.
colcon build --packages-up-to omni_drive_controller
source install/setup.bash

ros2 launch omni_drive_controller omni_drive.launch.py                    # Arduino em /dev/ttyACM0
ros2 launch omni_drive_controller omni_drive.launch.py port:=/dev/ttyUSB0
```

Para dirigir no teclado (segure **Shift** para andar de lado, o modo holonômico):

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

> O `ras-2.0` (`start.sh`) e o ROS **não podem usar a porta do Arduino ao mesmo tempo**. Feche um antes de abrir o outro.

### Sem o robô (Arduino falso)

```bash
ros2 run omni_drive_controller fake_arduino.py          # cria /tmp/ttyFakeArduino e mostra os comandos
ros2 launch omni_drive_controller omni_drive.launch.py port:=/tmp/ttyFakeArduino
```

### Conferir

```bash
ros2 topic echo /wheel_pwm
ros2 topic echo /odom --field pose.pose
ros2 run tf2_ros tf2_echo map base_link
```

## Primeiro teste no robô (rodas fora do chão)

Em `config/omni_drive.yaml`, comece com `max_pwm: 150`. Depois:

```bash
# frente: M1 positivo, M2 parado, M3 negativo (o mesmo do botão "frente" do ras-2.0)
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.15}}"
# giro horário: todas positivas (igual ao "rotate_right" do ras-2.0)
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{angular: {z: -0.8}}"
# esquerda
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {y: 0.15}}"
```

- **Andou para trás em vez de frente**: troque os três `wheel_signs`.
- **Uma roda só está ao contrário**: troque só o sinal dela em `wheel_signs`.
- **Frente certa mas lateral errada**: a geometria está espelhada ou girada. Ajuste `wheel_angles_deg`
  (o padrão `[120, 0, 240]` põe M2 na frente, M1 atrás à esquerda e M3 atrás à direita).

**Diferença em relação ao ras-2.0:** lá, "direita" é `(0, +s, -s)`, um vetor empírico que, pela
cinemática, anda na diagonal (de lado e um pouco para frente). Aqui a lateral é a pura:
esquerda a 0,2 m/s = `(+51, -102, +51)`. Se o robô andar reto de lado, a geometria está certa.

## Calibração (sem encoder, então é na trena)

1. **`deadband_pwm`**: aumente o PWM de uma roda até ela começar a girar no chão. Esse é o valor (algo como 30 a 60).
2. **`max_wheel_speed`**: mande frente com PWM 255 por um tempo `t` (`max_pwm: 255`, `/cmd_vel` alto),
   meça a distância `d` e use `max_wheel_speed = 0.866 · d / t`.
3. **`robot_radius`**: distância do centro do robô até o contato da roda. Confira girando no
   lugar com `angular.z = 1.0` por 6,28 s: deve dar uma volta. Se der menos, aumente o valor.

A odometria é só a integração do comando, sem nenhuma medida: escorregão, rampa e bateria
fraca viram erro que vai se acumulando. Serve para testar a navegação, não para medir a posição de verdade.

## Nav2

- `/cmd_vel` do Nav2 Humble é `Twist`, que é o que o nó espera.
- Use os limites de velocidade do Nav2 **menores** que os que o launch mostra no início
  ("vel. máx. ~X m/s"), senão a saturação corta o movimento e o caminho planejado não é seguido.
- Para omni: controlador `DWB` ou `MPPI` com `motion_model: "Omni"`, e `vy` liberado.
- O loopback publica `map→odom` (faz o papel do AMCL). Não rode AMCL junto. Se usar SLAM ou AMCL
  depois, ponha `publish_map_odom_tf: false`.
- O scan falso do loopback vai para `/loopback/scan` para não brigar com o LiDAR real em `/scan`.
