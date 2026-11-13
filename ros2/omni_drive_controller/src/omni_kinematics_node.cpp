// /cmd_vel (Twist) -> /wheel_pwm (WheelPwm)
//
// - Cinemática inversa da base omni de 3 rodas (ver omni_kinematics.hpp)
// - Satura preservando a direção: se uma roda passaria do limite, todas são escaladas juntas
// - Rampa de aceleração opcional (evita derrapar / "freio ABS" do ras-2.0)
// - Watchdog: sem cmd_vel por cmd_vel_timeout segundos -> alvo zero
// - Publica /applied_cmd_vel: a velocidade que de fato foi mandada aos motores (depois de
//   saturação, rampa e watchdog). É isso que alimenta a odometria simulada (loopback).

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <memory>
#include <vector>

#include "geometry_msgs/msg/twist.hpp"
#include "omni_drive_controller/omni_kinematics.hpp"
#include "omni_drive_controller_msgs/msg/wheel_pwm.hpp"
#include "rclcpp/rclcpp.hpp"

namespace omni_drive_controller
{

class OmniKinematicsNode : public rclcpp::Node
{
public:
  OmniKinematicsNode()
  : Node("omni_kinematics")
  {
    const auto angles = declare_parameter<std::vector<double>>(
      "wheel_angles_deg", {120.0, 0.0, 240.0});
    const auto signs = declare_parameter<std::vector<double>>(
      "wheel_signs", {-1.0, -1.0, -1.0});
    const double robot_radius = declare_parameter<double>("robot_radius", 0.20);
    max_wheel_speed_ = declare_parameter<double>("max_wheel_speed", 0.50);
    deadband_pwm_ = declare_parameter<int>("deadband_pwm", 0);
    max_pwm_ = declare_parameter<int>("max_pwm", 255);
    max_wheel_accel_ = declare_parameter<double>("max_wheel_accel", 1.0);
    cmd_vel_timeout_ = declare_parameter<double>("cmd_vel_timeout", 0.5);
    const double rate = declare_parameter<double>("control_rate", 20.0);

    if (angles.size() != 3 || signs.size() != 3) {
      throw std::invalid_argument("wheel_angles_deg e wheel_signs precisam ter 3 valores");
    }
    if (max_wheel_speed_ <= 0.0 || rate <= 0.0) {
      throw std::invalid_argument("max_wheel_speed e control_rate precisam ser > 0");
    }
    deadband_pwm_ = std::clamp(deadband_pwm_, 0, 254);
    max_pwm_ = std::clamp(max_pwm_, deadband_pwm_ + 1, 255);

    kin_ = std::make_unique<OmniKinematics>(
      std::array<double, 3>{angles[0], angles[1], angles[2]},
      std::array<double, 3>{signs[0], signs[1], signs[2]},
      robot_radius);

    // Maior velocidade de roda permitida pelo max_pwm (inverso de wheel_speed_to_pwm)
    wheel_speed_limit_ = max_wheel_speed_ *
      static_cast<double>(max_pwm_ - deadband_pwm_) / (255.0 - deadband_pwm_);

    pwm_pub_ = create_publisher<omni_drive_controller_msgs::msg::WheelPwm>("wheel_pwm", 10);
    applied_pub_ = create_publisher<geometry_msgs::msg::Twist>("applied_cmd_vel", 10);
    cmd_sub_ = create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel", 10,
      [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
        target_ = {msg->linear.x, msg->linear.y, msg->angular.z};
        last_cmd_time_ = now();
        have_cmd_ = true;
      });

    dt_ = 1.0 / rate;
    timer_ = create_wall_timer(
      std::chrono::duration<double>(dt_), [this]() {update();});

    const BodyTwist max_fwd = kin_->forward(scaled(kin_->inverse({1.0, 0.0, 0.0})));
    const BodyTwist max_rot = kin_->forward(scaled(kin_->inverse({0.0, 0.0, 1.0})));
    RCLCPP_INFO(
      get_logger(),
      "omni_kinematics pronto: vel. máx. ~%.2f m/s para frente, ~%.2f rad/s girando "
      "(max_wheel_speed=%.2f, deadband=%d, max_pwm=%d)",
      max_fwd.vx, max_rot.omega, max_wheel_speed_, deadband_pwm_, max_pwm_);
  }

private:
  // Escala o vetor de rodas para nenhuma passar do limite (mantém a direção do movimento)
  WheelSpeeds scaled(WheelSpeeds w) const
  {
    double peak = 0.0;
    for (double v : w) {peak = std::max(peak, std::abs(v));}
    if (peak > wheel_speed_limit_) {
      const double k = wheel_speed_limit_ / peak;
      for (double & v : w) {v *= k;}
    }
    return w;
  }

  void update()
  {
    BodyTwist target = target_;
    if (!have_cmd_ || (now() - last_cmd_time_).seconds() > cmd_vel_timeout_) {
      if (have_cmd_ && !timed_out_) {
        RCLCPP_WARN(get_logger(), "sem cmd_vel há %.2f s: parando motores", cmd_vel_timeout_);
      }
      timed_out_ = have_cmd_;
      target = {};
    } else {
      timed_out_ = false;
    }

    const WheelSpeeds desired = scaled(kin_->inverse(target));

    // Rampa: limita a variação do vetor inteiro (sem distorcer a direção)
    if (max_wheel_accel_ > 0.0) {
      const double max_step = max_wheel_accel_ * dt_;
      double peak = 0.0;
      for (std::size_t i = 0; i < 3; ++i) {
        peak = std::max(peak, std::abs(desired[i] - current_[i]));
      }
      const double k = peak > max_step ? max_step / peak : 1.0;
      for (std::size_t i = 0; i < 3; ++i) {
        current_[i] += (desired[i] - current_[i]) * k;
      }
    } else {
      current_ = desired;
    }

    omni_drive_controller_msgs::msg::WheelPwm pwm;
    pwm.wheel_1 = static_cast<int16_t>(wheel_speed_to_pwm(current_[0], max_wheel_speed_, deadband_pwm_));
    pwm.wheel_2 = static_cast<int16_t>(wheel_speed_to_pwm(current_[1], max_wheel_speed_, deadband_pwm_));
    pwm.wheel_3 = static_cast<int16_t>(wheel_speed_to_pwm(current_[2], max_wheel_speed_, deadband_pwm_));
    pwm_pub_->publish(pwm);

    const BodyTwist applied = kin_->forward(current_);
    geometry_msgs::msg::Twist out;
    out.linear.x = applied.vx;
    out.linear.y = applied.vy;
    out.angular.z = applied.omega;
    applied_pub_->publish(out);
  }

  std::unique_ptr<OmniKinematics> kin_;
  double max_wheel_speed_{};
  double wheel_speed_limit_{};
  int deadband_pwm_{};
  int max_pwm_{};
  double max_wheel_accel_{};
  double cmd_vel_timeout_{};
  double dt_{};

  BodyTwist target_{};
  WheelSpeeds current_{};
  rclcpp::Time last_cmd_time_{0, 0, RCL_ROS_TIME};
  bool have_cmd_{false};
  bool timed_out_{false};

  rclcpp::Publisher<omni_drive_controller_msgs::msg::WheelPwm>::SharedPtr pwm_pub_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr applied_pub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace omni_drive_controller

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<omni_drive_controller::OmniKinematicsNode>());
  rclcpp::shutdown();
  return 0;
}
