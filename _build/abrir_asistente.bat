@echo off
title Asistente de Agostino Propiedades
cd /d "%~dp0.."
echo Iniciando el asistente... (para cerrarlo, cerra esta ventana o presiona Ctrl+C)
echo.
python _build\asistente.py
echo.
echo El asistente se cerro. Si fue por un error, esta arriba. Presiona una tecla para salir.
pause >nul
