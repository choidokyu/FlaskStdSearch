@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: Excel 임시 파일 무시 규칙을 .gitignore에 추가 (중복 방지)
if not exist .gitignore (
    echo ~$* > .gitignore
) else (
    findstr /C:"~$*" .gitignore >nul 2>&1
    if errorlevel 1 (
        echo ~$*>> .gitignore
    )
)

:: 날짜 기반 자동 커밋 메시지 생성
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (
    set yyyy=%%a
    set mm=%%b
    set dd=%%c
)
for /f "tokens=1 delims=:" %%a in ("%time%") do (
    set hhmm=%%a
)
set commitMsg=Auto-commit %yyyy%-%mm%-%dd% %hhmm%

:: 변경된 파일을 스테이징
git add .

:: 커밋 및 푸시
call git commit -m "%commitMsg%"
git push origin main

echo [완료] %commitMsg% 으로 푸시되었습니다.
pause
