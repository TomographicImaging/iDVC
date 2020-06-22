::IF NOT DEFINED CIL_VERSION (
::ECHO CIL_VERSION Not Defined.
::exit 1
::)

mkdir "%SRC_DIR%\ccpi"
ROBOCOPY /E "%RECIPE_DIR%\..\src" "%SRC_DIR%\ccpi\src"
ROBOCOPY /E "%RECIPE_DIR%\..\ccpi" "%SRC_DIR%\ccpi\ccpi"
copy "%RECIPE_DIR%\..\setup.py" "%SRC_DIR%\ccpi"
::ROBOCOPY /E "%RECIPE_DIR%\..\..\..\Core" "%SRC_DIR%\Core"
::cd %SRC_DIR%\ccpi\Python
cd %SRC_DIR%\ccpi

:: issue cmake to create setup.py
cmake -G "NMake Makefiles" %RECIPE_DIR%\..\..\..\ -DBUILD_PYTHON_WRAPPERS=OFF -DCONDA_BUILD=ON -DBUILD_CUDA=OFF -DCMAKE_BUILD_TYPE="Release" -DLIBRARY_LIB="%CONDA_PREFIX%\lib" -DLIBRARY_INC="%CONDA_PREFIX%" -DCMAKE_INSTALL_PREFIX="%PREFIX%\Library" 

nmake install
if errorlevel 1 exit 1

%PYTHON% setup.py install
if errorlevel 1 exit 1

::nmake install
::if errorlevel 1 exit 1