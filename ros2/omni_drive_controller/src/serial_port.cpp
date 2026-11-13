#include "omni_drive_controller/serial_port.hpp"

#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <stdexcept>

namespace omni_drive_controller
{

namespace
{
speed_t to_speed(int baud)
{
  switch (baud) {
    case 9600: return B9600;
    case 19200: return B19200;
    case 38400: return B38400;
    case 57600: return B57600;
    case 115200: return B115200;
    case 230400: return B230400;
    default: throw std::runtime_error("baud rate não suportado: " + std::to_string(baud));
  }
}

std::string errno_str() {return std::strerror(errno);}
}  // namespace

SerialPort::~SerialPort() {close();}

void SerialPort::open(const std::string & device, int baud_rate)
{
  close();
  const speed_t speed = to_speed(baud_rate);
  fd_ = ::open(device.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd_ < 0) {
    throw std::runtime_error("não abriu " + device + ": " + errno_str());
  }

  termios tty{};
  if (tcgetattr(fd_, &tty) != 0) {
    const std::string err = errno_str();
    close();
    throw std::runtime_error("tcgetattr: " + err);
  }
  cfmakeraw(&tty);
  cfsetispeed(&tty, speed);
  cfsetospeed(&tty, speed);
  tty.c_cflag |= (CLOCAL | CREAD);
  tty.c_cflag &= ~(CSTOPB | CRTSCTS | PARENB);
  tty.c_cflag &= ~CSIZE;
  tty.c_cflag |= CS8;
  tty.c_cc[VMIN] = 0;
  tty.c_cc[VTIME] = 0;
  if (tcsetattr(fd_, TCSANOW, &tty) != 0) {
    const std::string err = errno_str();
    close();
    throw std::runtime_error("tcsetattr: " + err);
  }
  tcflush(fd_, TCIOFLUSH);
}

void SerialPort::close()
{
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
}

void SerialPort::write_all(const std::string & data)
{
  if (fd_ < 0) {
    throw std::runtime_error("porta fechada");
  }
  std::size_t sent = 0;
  while (sent < data.size()) {
    const ssize_t n = ::write(fd_, data.data() + sent, data.size() - sent);
    if (n > 0) {
      sent += static_cast<std::size_t>(n);
    } else if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) {
      pollfd p{fd_, POLLOUT, 0};
      if (::poll(&p, 1, 200) <= 0 || (p.revents & (POLLERR | POLLHUP | POLLNVAL))) {
        throw std::runtime_error("timeout/erro escrevendo na serial");
      }
    } else {
      throw std::runtime_error("write: " + errno_str());
    }
  }
}

void SerialPort::drain()
{
  if (fd_ >= 0) {
    tcdrain(fd_);
  }
}

std::string SerialPort::read_available()
{
  if (fd_ < 0) {
    throw std::runtime_error("porta fechada");
  }
  std::string out;
  char buf[256];
  while (true) {
    const ssize_t n = ::read(fd_, buf, sizeof(buf));
    if (n > 0) {
      out.append(buf, static_cast<std::size_t>(n));
      continue;
    }
    if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) {
      break;
    }
    if (n == 0) {
      // Em tty não bloqueante, 0 com POLLHUP significa que o dispositivo sumiu (cabo puxado)
      pollfd p{fd_, POLLIN, 0};
      if (::poll(&p, 1, 0) > 0 && (p.revents & (POLLHUP | POLLERR | POLLNVAL))) {
        throw std::runtime_error("dispositivo desconectado");
      }
      break;
    }
    throw std::runtime_error("read: " + errno_str());
  }
  return out;
}

}  // namespace omni_drive_controller
