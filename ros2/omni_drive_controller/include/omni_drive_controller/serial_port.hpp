// Porta serial POSIX mínima (termios), sem dependências externas.
#pragma once

#include <string>

namespace omni_drive_controller
{

class SerialPort
{
public:
  SerialPort() = default;
  ~SerialPort();
  SerialPort(const SerialPort &) = delete;
  SerialPort & operator=(const SerialPort &) = delete;

  // Abre em modo raw 8N1, não bloqueante. Lança std::runtime_error em caso de falha.
  void open(const std::string & device, int baud_rate);
  void close();
  bool is_open() const {return fd_ >= 0;}

  // Escreve tudo (espera o buffer do kernel se precisar). Lança em caso de erro.
  void write_all(const std::string & data);
  // Espera os bytes saírem fisicamente pela porta
  void drain();
  // Lê o que estiver disponível (não bloqueia). Lança se a porta sumiu.
  std::string read_available();

private:
  int fd_{-1};
};

}  // namespace omni_drive_controller
