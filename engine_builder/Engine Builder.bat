@echo off
cd /d "%~dp0"
py engine_builder.py || python engine_builder.py || pause
