@echo off
chcp 65001 > nul
title Chuyên Viên Ảo - Zalo Bot
echo [INFO] Đang khởi động Chuyên Viên Ảo (Zalo Bot)...
cd /d "%~dp0"
python -u main.py
echo.
echo [WARNING] Bot đã dừng hoạt động. Nhấn phím bất kỳ để thoát.
pause
