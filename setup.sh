#!/bin/bash
# ============================================
# InmoBot - Script de Setup Rápido
# ============================================
# Ejecutá este script para configurar el proyecto
# en tu máquina local o servidor.
#
# Uso: bash setup.sh
# ============================================

set -e

echo "============================================"
echo "  INMOBOT - Setup Rápido"
echo "============================================"
echo ""

# Verificar dependencias
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "ERROR: $1 no está instalado."
        echo "Instalalo antes de continuar."
        exit 1
    fi
}

echo "Verificando dependencias..."
check_command python3
check_command node
check_command npm
echo "OK: Python3, Node.js y npm instalados."
echo ""

# Crear archivos .env si no existen
if [ ! -f backend/.env ]; then
    echo "Creando backend/.env desde .env.example..."
    cp backend/.env.example backend/.env
    echo "IMPORTANTE: Editá backend/.env con tus credenciales"
else
    echo "backend/.env ya existe, saltando..."
fi

if [ ! -f frontend/.env ]; then
    echo "Creando frontend/.env desde .env.example..."
    cp frontend/.env.example frontend/.env
    echo "IMPORTANTE: Editá frontend/.env con la URL de tu backend"
else
    echo "frontend/.env ya existe, saltando..."
fi

echo ""

# Instalar dependencias del backend
echo "Instalando dependencias del backend..."
cd backend
python3 -m venv venv 2>/dev/null || python3 -m venv venv
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null
pip install -r requirements.txt
cd ..
echo "OK: Backend listo."
echo ""

# Instalar dependencias del frontend
echo "Instalando dependencias del frontend..."
cd frontend
npm install
cd ..
echo "OK: Frontend listo."
echo ""

echo "============================================"
echo "  SETUP COMPLETO"
echo "============================================"
echo ""
echo "Próximos pasos:"
echo ""
echo "  1. Editá backend/.env con tus credenciales"
echo "     (MONGO_URL, OPENAI_API_KEY, etc.)"
echo ""
echo "  2. Editá frontend/.env con la URL de tu backend"
echo "     y el nombre de tu inmobiliaria"
echo ""
echo "  3. Creá el usuario admin:"
echo "     cd backend && python init_admin.py"
echo ""
echo "  4. Iniciá el backend:"
echo "     cd backend && source venv/bin/activate"
echo "     uvicorn server:app --host 0.0.0.0 --port 8001"
echo ""
echo "  5. En otra terminal, iniciá el frontend:"
echo "     cd frontend && npm start"
echo ""
echo "  6. Abrí http://localhost:3000 en tu navegador"
echo ""
echo "============================================"
echo "  Manual completo: docs/MANUAL_COMPRADOR.md"
echo "============================================"
