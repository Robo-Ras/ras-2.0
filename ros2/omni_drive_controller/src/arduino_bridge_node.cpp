// /wheel_pwm (WheelPwm) -> serial "m1,m2,m3\n" para o arduino_robot_control.ino
//
// Cuidados com o sketch atual:
// - Abrir a serial reseta o Arduino (DTR): espera "Sistema iniciado" ou arduino_reset_delay.
// - O Arduino responde cada comando com ~50 bytes a 9600 baud (~50 ms de TX). Mandar mais
//   rápido que ~10 Hz trava o loop dele nos Serial.print. Por isso só reenvia quando o valor
//   muda (limitado a max_send_rate) ou a cada keepalive_period.
// - O sketch NÃO tem watchdog: se o ROS morrer, o motor continua no último valor. Este nó
//   manda 0,0,0 ao perder /wheel_pwm (input_timeout) e ao fechar.
// - Se o cabo cair, tenta reconectar a cada reconnect_period.

#include <algorithm>
#include <array>
#include <chrono>
#include <memory>
#include <sstream>
#include <string>

#include "omni_drive_controller/serial_port.hpp"
#include "omni_drive_controller_msgs/msg/wheel_pwm.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/bool.hpp"

namespace omni_drive_controller
{

using Pwm3 = std::array<int, 3>;

class ArduinoBridgeNode : public rclcpp::Node
{
public:
  ArduinoBridgeNode()
  : Node("arduino_bridge")
  {
    port_ = declare_parameter<std::string>("port", "/dev/ttyACM0");
    baud_ = declare_parameter<int>("baud_rate", 9600);
    reset_delay_ = declare_parameter<double>("arduino_reset_delay", 2.0);
    const double max_rate = declare_parameter<double>("max_send_rate", 10.0);
    keepalive_ = declare_parameter<double>("keepalive_period", 0.5);
    input_timeout_ = declare_parameter<double>("input_timeout", 0.5);
    reconnect_period_ = declare_parameter<double>("reconnect_period", 2.0);
    log_replies_ = declare_parameter<bool>("log_arduino_replies", false);

    connected_pub_ = create_publisher<std_msgs::msg::Bool>(
      "arduino/connected", rclcpp::QoS(1).transient_local());
    sub_ = create_subscription<omni_drive_controller_msgs::msg::WheelPwm>(
      "wheel_pwm", 10,
      [this](omni_drive_controller_msgs::msg::WheelPwm::ConstSharedPtr msg) {
        target_ = {msg->wheel_1, msg->wheel_2, msg->wheel_3};
        last_input_ = steady_now();
        have_input_ = true;
      });

    timer_ = create_wall_timer(
      std::chrono::duration<double>(1.0 / std::max(1.0, max_rate)), [this]() {tick();});
    publish_connected(false);
    try_connect();
  }

  ~ArduinoBridgeNode() override
  {
    // Garante motores parados ao encerrar (Ctrl+C)
    if (serial_.is_open()) {
      try {
        serial_.write_all("0,0,0\n");
        serial_.drain();
      } catch (...) {
      }
    }
  }

private:
  static double steady_now()
  {
    return std::chrono::duration<double>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
  }

  void publish_connected(bool c)
  {
    std_msgs::msg::Bool m;
    m.data = c;
    connected_pub_->publish(m);
  }

  void try_connect()
  {
    last_connect_attempt_ = steady_now();
    try {
      serial_.open(port_, baud_);
    } catch (const std::exception & e) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 10000, "Arduino indisponível (%s). Tentando de novo a cada %.0f s",
        e.what(), reconnect_period_);
      return;
    }
    opened_at_ = steady_now();
    ready_ = false;
    rx_buffer_.clear();
    last_sent_ = {9999, 9999, 9999};  // força o primeiro envio
    RCLCPP_INFO(get_logger(), "Serial %s aberta a %d baud, aguardando o Arduino iniciar...",
      port_.c_str(), baud_);
  }

  void lost_connection(const std::string & why)
  {
    RCLCPP_ERROR(get_logger(), "Conexão com o Arduino perdida: %s", why.c_str());
    serial_.close();
    ready_ = false;
    publish_connected(false);
  }

  void read_replies()
  {
    rx_buffer_ += serial_.read_available();
    std::size_t nl;
    while ((nl = rx_buffer_.find('\n')) != std::string::npos) {
      std::string line = rx_buffer_.substr(0, nl);
      rx_buffer_.erase(0, nl + 1);
      while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) {line.pop_back();}
      if (line.empty()) {continue;}
      if (line.find("Sistema iniciado") != std::string::npos && !ready_) {
        set_ready("Arduino respondeu: " + line);
      } else if (log_replies_) {
        RCLCPP_INFO(get_logger(), "Arduino: %s", line.c_str());
      } else {
        RCLCPP_DEBUG(get_logger(), "Arduino: %s", line.c_str());
      }
    }
    if (rx_buffer_.size() > 1024) {rx_buffer_.clear();}  // lixo sem '\n'
  }

  void set_ready(const std::string & why)
  {
    ready_ = true;
    publish_connected(true);
    RCLCPP_INFO(get_logger(), "Arduino pronto (%s)", why.c_str());
  }

  void tick()
  {
    const double now = steady_now();
    if (!serial_.is_open()) {
      if (now - last_connect_attempt_ >= reconnect_period_) {try_connect();}
      return;
    }

    try {
      read_replies();
      if (!ready_) {
        if (now - opened_at_ < reset_delay_) {return;}
        set_ready("timeout de reset");
      }

      Pwm3 cmd{0, 0, 0};
      const bool fresh = have_input_ && (now - last_input_) <= input_timeout_;
      if (fresh) {
        cmd = target_;
        input_lost_logged_ = false;
      } else if (have_input_ && !input_lost_logged_) {
        RCLCPP_WARN(get_logger(), "sem /wheel_pwm há %.2f s: mandando 0,0,0", input_timeout_);
        input_lost_logged_ = true;
      }
      for (int & v : cmd) {v = std::clamp(v, -255, 255);}

      if (cmd != last_sent_ || now - last_send_time_ >= keepalive_) {
        std::ostringstream ss;
        ss << cmd[0] << ',' << cmd[1] << ',' << cmd[2] << '\n';
        serial_.write_all(ss.str());
        if (cmd != last_sent_) {
          RCLCPP_DEBUG(get_logger(), "-> %d,%d,%d", cmd[0], cmd[1], cmd[2]);
        }
        last_sent_ = cmd;
        last_send_time_ = now;
      }
    } catch (const std::exception & e) {
      lost_connection(e.what());
    }
  }

  std::string port_;
  int baud_{};
  double reset_delay_{};
  double keepalive_{};
  double input_timeout_{};
  double reconnect_period_{};
  bool log_replies_{};

  SerialPort serial_;
  bool ready_{false};
  double opened_at_{0.0};
  double last_connect_attempt_{0.0};
  std::string rx_buffer_;

  Pwm3 target_{0, 0, 0};
  Pwm3 last_sent_{9999, 9999, 9999};
  double last_send_time_{0.0};
  double last_input_{0.0};
  bool have_input_{false};
  bool input_lost_logged_{false};

  rclcpp::Subscription<omni_drive_controller_msgs::msg::WheelPwm>::SharedPtr sub_;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr connected_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace omni_drive_controller

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<omni_drive_controller::ArduinoBridgeNode>();
  rclcpp::spin(node);
  node.reset();  // destrutor manda 0,0,0 antes do shutdown
  rclcpp::shutdown();
  return 0;
}
