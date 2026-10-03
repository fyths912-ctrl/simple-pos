#!/bin/sh
# Azure App Service (Linux / Python) のスタートアップコマンド用
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:${PORT:-8000} --timeout 60
