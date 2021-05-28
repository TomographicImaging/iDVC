
mkdir "%SRC_DIR%"
ROBOCOPY /E "%RECIPE_DIR%\..\src" "%SRC_DIR%"
ROBOCOPY /E "%RECIPE_DIR%\..\test" "%SRC_DIR%\test"
copy "%RECIPE_DIR%\..\setup.py" "%SRC_DIR%\setup.py"
cd %SRC_DIR%

%PYTHON% setup.py install
if errorlevel 1 exit 1
