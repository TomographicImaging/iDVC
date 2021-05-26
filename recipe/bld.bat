

mkdir "%SRC_DIR%"
ROBOCOPY /E "%RECIPE_DIR%\..\src\ccpi" "%SRC_DIR%\ccpi"
copy "%RECIPE_DIR%\..\setup.py" "%SRC_DIR%\setup.py"
cd %SRC_DIR%

%PYTHON% setup.py install
if errorlevel 1 exit 1
