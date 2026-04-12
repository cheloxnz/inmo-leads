#!/usr/bin/env python3
"""
InmoBot - Script de Distribución de Actualizaciones a Clientes
=============================================================

Este script pushea actualizaciones desde tu repo principal
a los repositorios privados de tus clientes con soporte activo.

Uso:
    python push_updates.py                  # Push a todos los clientes activos
    python push_updates.py --add            # Agregar nuevo cliente
    python push_updates.py --remove NOMBRE  # Desactivar un cliente
    python push_updates.py --list           # Ver lista de clientes
    python push_updates.py --dry-run        # Simular sin pushear

Requisitos:
    - Git instalado
    - Acceso SSH o HTTPS a los repos de los clientes
    - Estar parado en el directorio raíz del proyecto

Cómo funciona:
    1. Vos hacés cambios en tu repo principal (main)
    2. Ejecutás este script
    3. El script pushea los cambios a cada repo de cliente activo
    4. El cliente hace 'git pull' en su servidor (o Railway lo actualiza solo)
"""

import json
import subprocess
import sys
import os
from datetime import datetime

CLIENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clients.json')

def load_clients():
    if not os.path.exists(CLIENTS_FILE):
        return []
    with open(CLIENTS_FILE, 'r') as f:
        return json.load(f)

def save_clients(clients):
    with open(CLIENTS_FILE, 'w') as f:
        json.dump(clients, f, indent=2, ensure_ascii=False)

def run_cmd(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        return None, result.stderr
    return result.stdout.strip(), None

def add_client():
    print("\n=== Agregar Nuevo Cliente ===\n")
    name = input("Nombre del cliente (ej: inmobiliaria-lopez): ").strip()
    if not name:
        print("Error: El nombre es obligatorio")
        return

    repo_url = input("URL del repo del cliente (ej: git@github.com:tu-user/inmobot-lopez.git): ").strip()
    if not repo_url:
        print("Error: La URL del repo es obligatoria")
        return

    plan = input("Plan (codigo/instalacion): ").strip() or "instalacion"
    soporte = input("Tiene soporte activo? (s/n): ").strip().lower() == 's'
    soporte_hasta = ""
    if soporte:
        soporte_hasta = input("Soporte activo hasta (YYYY-MM-DD): ").strip()

    clients = load_clients()
    
    # Verificar que no exista
    if any(c['name'] == name for c in clients):
        print(f"Error: Ya existe un cliente con el nombre '{name}'")
        return

    client = {
        'name': name,
        'repo_url': repo_url,
        'plan': plan,
        'soporte_activo': soporte,
        'soporte_hasta': soporte_hasta,
        'remote_name': f"client-{name}",
        'created_at': datetime.now().isoformat(),
        'last_push': None
    }

    clients.append(client)
    save_clients(clients)

    # Agregar remote en git
    output, err = run_cmd(f'git remote add {client["remote_name"]} {repo_url}', check=False)
    if err and 'already exists' not in err:
        print(f"Advertencia: {err}")
    
    print(f"\nCliente '{name}' agregado exitosamente.")
    print(f"Remote git: {client['remote_name']}")
    if soporte:
        print(f"Soporte activo hasta: {soporte_hasta}")

def remove_client(name):
    clients = load_clients()
    client = next((c for c in clients if c['name'] == name), None)
    
    if not client:
        print(f"Error: No se encontró cliente '{name}'")
        return

    client['soporte_activo'] = False
    save_clients(clients)
    
    print(f"Cliente '{name}' marcado como inactivo.")
    print("El remote de git se mantiene por si se reactiva.")

def list_clients():
    clients = load_clients()
    
    if not clients:
        print("\nNo hay clientes registrados.")
        print("Usá: python push_updates.py --add")
        return

    print(f"\n{'='*70}")
    print(f"  CLIENTES REGISTRADOS ({len(clients)} total)")
    print(f"{'='*70}\n")

    active = [c for c in clients if c.get('soporte_activo')]
    inactive = [c for c in clients if not c.get('soporte_activo')]

    if active:
        print("  ACTIVOS (reciben actualizaciones):\n")
        for c in active:
            last = c.get('last_push', 'Nunca')
            hasta = c.get('soporte_hasta', 'Sin fecha')
            print(f"    {c['name']}")
            print(f"      Plan: {c['plan']} | Soporte hasta: {hasta}")
            print(f"      Repo: {c['repo_url']}")
            print(f"      Último push: {last}")
            print()

    if inactive:
        print("  INACTIVOS (no reciben actualizaciones):\n")
        for c in inactive:
            print(f"    {c['name']} ({c['plan']})")
        print()

def push_updates(dry_run=False):
    clients = load_clients()
    active = [c for c in clients if c.get('soporte_activo')]

    if not active:
        print("\nNo hay clientes con soporte activo.")
        return

    # Verificar si hay cambios pendientes de commit
    output, _ = run_cmd('git status --porcelain')
    if output:
        print("ADVERTENCIA: Hay cambios sin commitear.")
        resp = input("¿Querés continuar igual? (s/n): ").strip().lower()
        if resp != 's':
            print("Cancelado.")
            return

    # Obtener branch actual
    branch, _ = run_cmd('git branch --show-current')
    if not branch:
        branch = 'main'

    print(f"\n{'='*50}")
    print(f"  PUSH DE ACTUALIZACIONES")
    print(f"  Branch: {branch}")
    print(f"  Clientes activos: {len(active)}")
    if dry_run:
        print(f"  MODO: DRY RUN (simulación)")
    print(f"{'='*50}\n")

    success = 0
    failed = 0

    for client in active:
        name = client['name']
        remote = client['remote_name']
        
        # Verificar si el remote existe
        output, _ = run_cmd(f'git remote get-url {remote}', check=False)
        if not output:
            print(f"  Agregando remote para {name}...")
            run_cmd(f'git remote add {remote} {client["repo_url"]}', check=False)

        print(f"  Pusheando a {name}...", end=" ")
        
        if dry_run:
            print("OK (dry run)")
            success += 1
            continue

        _, err = run_cmd(f'git push {remote} {branch}:main --force')
        if err and 'error' in err.lower():
            print(f"ERROR: {err[:100]}")
            failed += 1
        else:
            print("OK")
            client['last_push'] = datetime.now().isoformat()
            success += 1

    if not dry_run:
        save_clients(clients)

    print(f"\n  Resultado: {success} exitosos, {failed} fallidos\n")

def main():
    args = sys.argv[1:]

    if '--add' in args:
        add_client()
    elif '--remove' in args:
        idx = args.index('--remove')
        if idx + 1 < len(args):
            remove_client(args[idx + 1])
        else:
            print("Error: Especificá el nombre del cliente")
            print("Uso: python push_updates.py --remove NOMBRE")
    elif '--list' in args:
        list_clients()
    elif '--dry-run' in args:
        push_updates(dry_run=True)
    elif '--help' in args or '-h' in args:
        print(__doc__)
    else:
        push_updates()

if __name__ == '__main__':
    main()
