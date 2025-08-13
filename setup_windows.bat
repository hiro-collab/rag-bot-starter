\
    @echo off
    REM Create venv and install requirements (Windows)
    py -3 -m venv .venv
    call .\.venv\Scripts\activate.bat
    python -m pip install -U pip
    pip install -r requirements.txt
    echo Copied .env.example -> .env (edit it!)
    copy .env.example .env
