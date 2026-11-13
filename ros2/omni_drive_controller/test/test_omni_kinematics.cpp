#include <gtest/gtest.h>

#include <cmath>

#include "omni_drive_controller/omni_kinematics.hpp"

using omni_drive_controller::BodyTwist;
using omni_drive_controller::OmniKinematics;
using omni_drive_controller::wheel_speed_to_pwm;

namespace
{
OmniKinematics default_kin()
{
  return OmniKinematics({120.0, 0.0, 240.0}, {-1.0, -1.0, -1.0}, 0.2);
}
int sgn(double v) {return (v > 1e-9) - (v < -1e-9);}
}  // namespace

// Os padrões precisam reproduzir os vetores testados no robô (ras-2.0 backend)
TEST(OmniKinematics, ForwardMatchesRealRobot)
{
  const auto w = default_kin().inverse({0.3, 0.0, 0.0});
  EXPECT_EQ(sgn(w[0]), 1);
  EXPECT_EQ(sgn(w[1]), 0);
  EXPECT_EQ(sgn(w[2]), -1);
  EXPECT_NEAR(w[0], -w[2], 1e-9);
}

TEST(OmniKinematics, ClockwiseRotationMatchesRealRobot)
{
  const auto w = default_kin().inverse({0.0, 0.0, -1.0});
  EXPECT_GT(w[0], 0.0);
  EXPECT_NEAR(w[0], w[1], 1e-9);
  EXPECT_NEAR(w[1], w[2], 1e-9);
}

TEST(OmniKinematics, LateralKeepsM2SignOfBackend)
{
  // backend: direita = (0, +s, -s); a cinemática pura dá M2 > 0 também
  const auto w = default_kin().inverse({0.0, -0.3, 0.0});
  EXPECT_GT(w[1], 0.0);
}

TEST(OmniKinematics, ForwardIsInverseOfInverse)
{
  const auto kin = default_kin();
  const BodyTwist in{0.21, -0.13, 0.7};
  const BodyTwist out = kin.forward(kin.inverse(in));
  EXPECT_NEAR(out.vx, in.vx, 1e-9);
  EXPECT_NEAR(out.vy, in.vy, 1e-9);
  EXPECT_NEAR(out.omega, in.omega, 1e-9);
}

TEST(OmniKinematics, RejectsSingularGeometry)
{
  EXPECT_THROW(OmniKinematics({0.0, 0.0, 0.0}, {1.0, 1.0, 1.0}, 0.2), std::invalid_argument);
}

TEST(WheelSpeedToPwm, DeadbandAndSaturation)
{
  EXPECT_EQ(wheel_speed_to_pwm(0.0, 0.5, 40), 0);
  EXPECT_EQ(wheel_speed_to_pwm(0.5, 0.5, 40), 255);
  EXPECT_EQ(wheel_speed_to_pwm(-1.0, 0.5, 40), -255);
  EXPECT_EQ(wheel_speed_to_pwm(0.001, 0.5, 40), 40);  // qualquer movimento já vence a zona morta
  EXPECT_EQ(wheel_speed_to_pwm(0.25, 0.5, 0), 128);
}
