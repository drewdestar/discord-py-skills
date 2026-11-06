@echo off
REM newr launcher for Windows.
REM Put this file next to the `newr` script (same folder) and run it as:
REM   newr.bat search
REM   newr.bat install all
REM Requires Python 3.10+ on PATH (python.org or Microsoft Store).
REM UNVERIFIED on a real Windows machine: this file was written and
REM reviewed on Linux, where no Windows host exists to run it. If it
REM fails, run the same command directly: py -3 newr <command>.
setlocal
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0newr" %*
) else (
  python "%~dp0newr" %*
)
