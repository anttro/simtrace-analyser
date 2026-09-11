@echo off
setlocal enabledelayedexpansion

:: simtrace2-pysniff startup script for Windows
::
:: Usage: sniff-start.bat [--format FORMAT] [--gsmtap HOST[:PORT]] [--pcap FILE] [--output FILE] [--inactivity-timeout SECONDS]
::
:: Options set via environment variables act as defaults; CLI flags override them.

set "GSMTAP=%GSMTAP%"
set "PCAP=%PCAP%"
set "OUTPUT=%OUTPUT%"
set "FORMAT=%FORMAT%"
set "INACTIVITY_TIMEOUT=%INACTIVITY_TIMEOUT%"
if "%INACTIVITY_TIMEOUT%"=="" set "INACTIVITY_TIMEOUT=0"
set "EXTRA_ARGS="

:parse_args
if "%~1"=="" goto :run
if "%~1"=="--gsmtap" (
    set "GSMTAP=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--pcap" (
    set "PCAP=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--output" (
    set "OUTPUT=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="-o" (
    set "OUTPUT=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--format" (
    set "FORMAT=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="-f" (
    set "FORMAT=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--inactivity-timeout" (
    set "INACTIVITY_TIMEOUT=%~2"
    shift
    shift
    goto :parse_args
)
set "EXTRA_ARGS=!EXTRA_ARGS! %~1"
shift
goto :parse_args

:run
echo Starting simtrace2-pysniff...

set "ARGS="
if not "%GSMTAP%"=="" set "ARGS=!ARGS! --gsmtap %GSMTAP%"
if not "%PCAP%"=="" set "ARGS=!ARGS! --pcap %PCAP%"
if not "%OUTPUT%"=="" set "ARGS=!ARGS! --output %OUTPUT%"
if not "%FORMAT%"=="" set "ARGS=!ARGS! --format %FORMAT%"
if not "%INACTIVITY_TIMEOUT%"=="0" set "ARGS=!ARGS! --inactivity-timeout %INACTIVITY_TIMEOUT%"

set "PYTHONPATH=%~dp0"
python -m simtrace2_pysniff %ARGS% %EXTRA_ARGS%
