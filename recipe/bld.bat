::IF NOT DEFINED CIL_VERSION (
::ECHO CIL_VERSION Not Defined.
::exit 1
::)

mkdir "%SRC_DIR%"
copy "%RECIPE_DIR%\.." "%SRC_DIR%"
cd %SRC_DIR%

%PYTHON% setup.py install
if errorlevel 1 exit 1
