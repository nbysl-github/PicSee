@echo off
python -u PicSee.py > crash_log.txt 2>&1
echo Program exited. Log saved to crash_log.txt.
type crash_log.txt
pause