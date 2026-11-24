"""Trava de rede dos testes: importar este módulo faz qualquer tentativa de falar com um endereço de FORA da própria máquina falhar na hora.

Os testes de tests/ são locais (bancos e APIs de mentira, sem segredo e sem rede: docs/testes.md). Sem esta trava, um teste que volte a chamar o banco ou um
serviço de verdade passaria calado (no CI a chamada sairia mesmo, com chave falsa). Uso: `import sem_rede  # noqa: F401`, antes de importar o que mais for.
Não é um teste: o CI só roda tests/test_*.py.
"""
import ipaddress
import socket

_conectar_original = socket.socket.connect
_resolver_original = socket.getaddrinfo
_LOCAL = {"", "localhost", "ip6-localhost"}


class SemRede(OSError):
    pass


def _endereco_local(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host in _LOCAL:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _conectar(self, endereco):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _endereco_local(endereco[0]):
        raise SemRede(f"os testes não falam com a rede: tentou conectar em {endereco[0]}")
    return _conectar_original(self, endereco)


def _resolver(host, *args, **kwargs):
    if not _endereco_local(host):
        raise SemRede(f"os testes não falam com a rede: tentou resolver {host}")
    return _resolver_original(host, *args, **kwargs)


socket.socket.connect = _conectar
socket.getaddrinfo = _resolver
