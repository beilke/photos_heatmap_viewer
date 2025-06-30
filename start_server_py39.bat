@echo off
taskkill /F /IM python.exe
call .venv-py39\Scripts\activate
python server.py
