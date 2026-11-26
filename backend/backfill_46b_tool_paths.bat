@echo off
REM [46b] P2b existing tool_paths_json backfill wrapper - XiaoOu 2026-11-18
REM Usage: optionally set OMNI_DB_PATH=<absolute path to chat_history.db> before running.
REM        When unset, DB path is resolved via resolve_db_dir() (OMNI_DATA_DIR honored).
REM Config isolation: never write config/config.yaml; never hardcode a DB path in this file.
REM Before APPLY, back up chat_history.db manually. tool_paths only; ref_ledger is untouched.
cd /d "%~dp0"

echo [1/2] DRY RUN - statistics only, no DB writes
if defined OMNI_DB_PATH (
    python -m app.services.chat.backfill_tool_paths --db "%OMNI_DB_PATH%"
) else (
    python -m app.services.chat.backfill_tool_paths
)
if errorlevel 1 goto :failed

echo.
set /p CONFIRM="Apply backfill now? Type y to continue, any other key to exit: "
if /i not "%CONFIRM%"=="y" goto :cancelled

echo [2/2] APPLY - overwrite tool_paths_json (idempotent, safe to rerun)
if defined OMNI_DB_PATH (
    python -m app.services.chat.backfill_tool_paths --db "%OMNI_DB_PATH%" --apply
) else (
    python -m app.services.chat.backfill_tool_paths --apply
)
if errorlevel 1 goto :failed

echo.
echo Done. Spot-check tool_paths_json of large sessions and the cold-start recommend row.
goto :end

:failed
echo.
echo Backfill FAILED. See the error above; no partial data is committed on failure.
goto :end

:cancelled
echo.
echo Cancelled. Nothing was written.

:end
pause
