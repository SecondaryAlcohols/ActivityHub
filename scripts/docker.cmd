@echo off
setlocal
set "WSL=C:\Program Files\WSL\wsl.exe"
"%WSL%" -d DockerAlpine -u root -- sh -c "/usr/local/bin/start-docker.sh" >nul 2>&1
"%WSL%" -d DockerAlpine -u root --cd "%~dp0" -- sh wait-for-docker.sh >nul 2>&1
"%WSL%" -d DockerAlpine --cd "%CD%" -- docker %*
