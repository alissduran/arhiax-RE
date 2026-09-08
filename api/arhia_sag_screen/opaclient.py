"""Puente Python -> OPA (eval): consulta los bundes de dominio SAG como motor normativo.

Este módulo permite que el pipeline único de cumplimiento consuma las decisiones
Rego (los bundes B20..B30) en lugar de re-implementarlas. Si OPA no está disponible
o la evaluación falla, devuelve None para que el orquestador caiga a la regla Python
equivalente (paridad de comportamiento), de modo que el sistema siga siendo
determinista y los tests corran en cualquier máquina.
"""
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Optional

# Ubicaciones candidatas del binario de OPA. Primera que exista gana.
_CANDIDATOS = [
    r"C:\Users\Inicio\AppData\Local\opa\opa.exe",  # Windows (esta estación)
    "/usr/local/bin/opa",
    "/usr/bin/opa",
    "opa",
]


def encontrar_opa(opa_bin: Optional[str] = None) -> Optional[str]:
    """Devuelve la ruta al binario de OPA, o None si no se encuentra."""
    if opa_bin:
        return opa_bin if os.path.exists(opa_bin) else None
    env = os.environ.get("ARHIA_OPA_BIN")
    if env and os.path.exists(env):
        return env
    candidato = shutil.which("opa") if shutil.which else None
    if candidato:
        return candidato
    for c in _CANDIDATOS:
        try:
            if os.path.exists(c):
                return c
        except OSError:
            continue
    return None


def _write_temp(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _extract(doc: dict) -> Optional[Any]:
    """Extrae el value de `result[0].expressions[0].value` del doc de OPA."""
    try:
        return doc["result"][0]["expressions"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return None


def evaluar(query: str, data_dir: str, input_dict: dict,
            opa_bin: Optional[str] = None, timeout: int = 30) -> Optional[Any]:
    """Evalúa `query` contra el `data_dir` con `input_dict`.

    Devuelve el valor (bool/dict/...) o None si OPA falta o falla. Nunca lanza.
    `query` es un path de regla, p. ej. `data.arhia.sag.detection.evidence`.
    """
    opa = encontrar_opa(opa_bin)
    if not opa:
        return None
    try:
        payload = json.dumps(input_dict, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    inp = _write_temp(payload)
    try:
        res = subprocess.run(
            [opa, "eval", "--data", data_dir, "--input", inp, "--format", "json", query],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        )
        if res.returncode != 0:
            return None
        return _extract(json.loads(res.stdout))
    except Exception:
        return None
    finally:
        try:
            os.unlink(inp)
        except OSError:
            pass
