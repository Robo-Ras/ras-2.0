// Cinemática de uma base omnidirecional de 3 rodas.
//
// Convenção (REP-103): x para frente, y para a esquerda, omega positivo = anti-horário.
// Cada roda i fica num ângulo alpha_i (graus, medido a partir de +x, anti-horário) a uma
// distância R do centro. O sentido "positivo" de uma roda é o tangente anti-horário, então
//
//     v_i = sign_i * ( -sin(alpha_i) * vx + cos(alpha_i) * vy + R * omega )
//
// sign_i (+1/-1) corrige a polaridade de cada motor (fiação/montagem).
//
// Os valores padrão (alpha = {120, 0, 240}, sign = {-1, -1, -1}) reproduzem os vetores
// testados no robô real em ras-2.0/backend/robot_autonomous_control.py:
//     frente        -> ( +,  0,  - )
//     giro horário  -> ( +,  +,  + )
// ou seja: M2 na frente, M1 atrás à esquerda, M3 atrás à direita.

#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

namespace omni_drive_controller
{

struct BodyTwist
{
  double vx{0.0};     // m/s, para frente
  double vy{0.0};     // m/s, para a esquerda
  double omega{0.0};  // rad/s, anti-horário
};

using WheelSpeeds = std::array<double, 3>;  // m/s na superfície da roda, já com sign_i

class OmniKinematics
{
public:
  OmniKinematics(
    const std::array<double, 3> & wheel_angles_deg,
    const std::array<double, 3> & wheel_signs,
    double robot_radius)
  {
    if (robot_radius <= 0.0) {
      throw std::invalid_argument("robot_radius precisa ser > 0");
    }
    for (std::size_t i = 0; i < 3; ++i) {
      if (wheel_signs[i] != 1.0 && wheel_signs[i] != -1.0) {
        throw std::invalid_argument("wheel_signs só aceita +1 ou -1");
      }
      const double a = wheel_angles_deg[i] * M_PI / 180.0;
      j_[i] = {
        wheel_signs[i] * -std::sin(a),
        wheel_signs[i] * std::cos(a),
        wheel_signs[i] * robot_radius};
    }
    invert();
  }

  // Inversa: velocidade do corpo -> velocidade de cada roda
  WheelSpeeds inverse(const BodyTwist & t) const
  {
    WheelSpeeds w{};
    for (std::size_t i = 0; i < 3; ++i) {
      w[i] = j_[i][0] * t.vx + j_[i][1] * t.vy + j_[i][2] * t.omega;
    }
    return w;
  }

  // Direta: velocidade de cada roda -> velocidade do corpo
  BodyTwist forward(const WheelSpeeds & w) const
  {
    BodyTwist t;
    t.vx = inv_[0][0] * w[0] + inv_[0][1] * w[1] + inv_[0][2] * w[2];
    t.vy = inv_[1][0] * w[0] + inv_[1][1] * w[1] + inv_[1][2] * w[2];
    t.omega = inv_[2][0] * w[0] + inv_[2][1] * w[1] + inv_[2][2] * w[2];
    return t;
  }

private:
  void invert()
  {
    const auto & m = j_;
    const double det =
      m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
      m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
      m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
    if (std::abs(det) < 1e-9) {
      throw std::invalid_argument("geometria das rodas não é omnidirecional (matriz singular)");
    }
    const double d = 1.0 / det;
    inv_[0][0] = (m[1][1] * m[2][2] - m[1][2] * m[2][1]) * d;
    inv_[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * d;
    inv_[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * d;
    inv_[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * d;
    inv_[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * d;
    inv_[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * d;
    inv_[2][0] = (m[1][0] * m[2][1] - m[1][1] * m[2][0]) * d;
    inv_[2][1] = (m[0][1] * m[2][0] - m[0][0] * m[2][1]) * d;
    inv_[2][2] = (m[0][0] * m[1][1] - m[0][1] * m[1][0]) * d;
  }

  std::array<std::array<double, 3>, 3> j_{};
  std::array<std::array<double, 3>, 3> inv_{};
};

// Converte velocidade de roda (m/s) em PWM do Arduino (-255..255).
//   max_wheel_speed: velocidade da roda com PWM 255 (calibrar no robô)
//   deadband: menor PWM que de fato faz o motor girar (abaixo disso ele só zune)
inline int wheel_speed_to_pwm(double v, double max_wheel_speed, int deadband)
{
  constexpr double kEps = 1e-4;
  if (std::abs(v) < kEps || max_wheel_speed <= 0.0) {
    return 0;
  }
  const double frac = std::min(std::abs(v) / max_wheel_speed, 1.0);
  const double pwm = deadband + frac * (255.0 - deadband);
  const int out = static_cast<int>(std::lround(pwm));
  return v > 0 ? std::min(out, 255) : -std::min(out, 255);
}

}  // namespace omni_drive_controller
