"""Lectura de credenciales desde el entorno, compartida por los canales de envío."""

from __future__ import annotations

import os


class ConfigFaltante(RuntimeError):
    pass


class ErrorDeEnvio(RuntimeError):
    pass


def cfg(clave: str, obligatorio: bool = True) -> str:
    v = os.environ.get(clave, "").strip()
    if obligatorio and not v:
        raise ConfigFaltante(f"Falta la variable de entorno {clave}")
    return v
