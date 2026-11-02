"""Comandos de administración - Operativa.ia

Uso:
    python -m app.cli create-admin --username USUARIO
    python -m app.cli reset-password --username USUARIO

La contraseña siempre se pide por consola: nunca como argumento, para que no quede en el historial.
"""

import argparse
import getpass
import re
import sqlite3
import sys

from app.services import auth


def _ask_password() -> str:
    password = getpass.getpass("Contraseña: ")
    if password != getpass.getpass("Repite la contraseña: "):
        raise ValueError("Las contraseñas no coinciden.")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-admin", "reset-password"])
    parser.add_argument("--username", required=True)
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", args.username):
        print("Usuario inválido: usa de 3 a 64 letras, números, _ . o -", file=sys.stderr)
        return 2

    try:
        password = _ask_password()
        if args.command == "create-admin":
            auth.create_admin(args.username, password)
        elif not auth.reset_password(args.username, password):
            print("No existe ese usuario.", file=sys.stderr)
            return 1
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    except sqlite3.IntegrityError:
        print("Ese usuario ya existe.", file=sys.stderr)
        return 1

    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
