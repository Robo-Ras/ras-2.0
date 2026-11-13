cmake_minimum_required(VERSION 3.8)
project(omni_drive_controller)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(omni_drive_controller_msgs REQUIRED)

include_directories(include)

add_library(omni_serial src/serial_port.cpp)

add_executable(omni_kinematics_node src/omni_kinematics_node.cpp)
ament_target_dependencies(omni_kinematics_node rclcpp geometry_msgs omni_drive_controller_msgs)

add_executable(arduino_bridge_node src/arduino_bridge_node.cpp)
target_link_libraries(arduino_bridge_node omni_serial)
ament_target_dependencies(arduino_bridge_node rclcpp std_msgs omni_drive_controller_msgs)

install(TARGETS omni_kinematics_node arduino_bridge_node
  DESTINATION lib/${PROJECT_NAME})
install(PROGRAMS scripts/fake_arduino.py
  DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_omni_kinematics test/test_omni_kinematics.cpp)
endif()

ament_package()
