"""Comandos de administración - Operativa.ia

Uso:
    python -m app.cli create-tenant --slug clinica-sol --name "Clínica Sol" [--timezone America/Toronto]
    python -m app.cli create-user --tenant clinica-sol --username ana --role owner
    python -m app.cli reset-password --username ana
    python -m app.cli set-active --tenant clinica-sol --active false
    python -m app.cli link-whatsapp --tenant clinica-sol --phone-number-id 123456789012345
    python -m app.cli purge

La contraseña siempre se pide por consola: nunca como argumento, para que no quede en el historial.
Crear negocios y owners solo es posible aquí, con acceso al servidor.
"""

import argparse
import getpass
import re
import sqlite3
import sys

from pydantic import ValidationError

from app.core.config import get_settings
from app.services import auth, channels, conversations, tenants

USERNAME = re.compile(r"[A-Za-z0-9_.-]{3,64}")


def _ask_password() -> str:
    password = getpass.getpass("Contraseña: ")
    if password != getpass.getpass("Repite la contraseña: "):
        raise ValueError("Las contraseñas no coinciden.")
    return password


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-tenant")
    p.add_argument("--slug", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--business-type", default="")
    p.add_argument("--timezone", default="America/Toronto")

    p = sub.add_parser("create-user")
    p.add_argument("--tenant", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--role", choices=auth.ROLES, required=True)

    p = sub.add_parser("reset-password")
    p.add_argument("--username", required=True)

    p = sub.add_parser("set-active")
    p.add_argument("--tenant", required=True)
    p.add_argument("--active", choices=["true", "false"], required=True)

    p = sub.add_parser("link-whatsapp", help="Asocia el phone_number_id de WhatsApp Business a un negocio.")
    p.add_argument("--tenant", required=True)
    p.add_argument("--phone-number-id", required=True)

    sub.add_parser("purge", help="Borra sesiones vencidas, intentos de login viejos y conversaciones fuera de retención.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if getattr(args, "username", None) is not None and not USERNAME.fullmatch(args.username):
        print("Usuario inválido: usa de 3 a 64 letras, números, _ . o -", file=sys.stderr)
        return 2

    try:
        if args.command == "create-tenant":
            profile = tenants.TenantProfile(name=args.name, business_type=args.business_type, timezone=args.timezone)
            tenants.create_tenant(args.slug, profile)
        elif args.command == "create-user":
            tenant = tenants.get_by_slug(args.tenant)
            if tenant is None:
                print("No existe ese negocio.", file=sys.stderr)
                return 1
            auth.create_user(tenant["id"], args.username, _ask_password(), args.role)
        elif args.command == "reset-password":
            if not auth.reset_password(args.username, _ask_password()):
                print("No existe ese usuario.", file=sys.stderr)
                return 1
        elif args.command == "set-active":
            if not tenants.set_active(args.tenant, args.active == "true"):
                print("No existe ese negocio.", file=sys.stderr)
                return 1
        elif args.command == "link-whatsapp":
            tenant = tenants.get_by_slug(args.tenant)
            if tenant is None:
                print("No existe ese negocio.", file=sys.stderr)
                return 1
            channels.link_whatsapp(tenant["id"], args.phone_number_id)
        elif args.command == "purge":
            removed = (
                auth.purge_expired_sessions(),
                auth.purge_login_attempts(),
                conversations.purge_older_than(get_settings().conversation_retention_days),
                channels.purge_events(),
            )
            print("Sesiones: {}, intentos de login: {}, conversaciones: {}, eventos de webhook: {}".format(*removed))
    except ValidationError as exc:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        print(f"Datos inválidos: {fields}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    except sqlite3.IntegrityError:
        print("Ya existe.", file=sys.stderr)
        return 1

    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
