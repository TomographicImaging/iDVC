
mkdir "$SRC_DIR/ccpi"
cp -rv "$RECIPE_DIR/.." "$SRC_DIR/ccpi"

cd $SRC_DIR/ccpi


#$PYTHON setup-regularisers.py build_ext
$PYTHON setup.py install



mkdir ${SRC_DIR}/ccpi
cp -r ${RECIPE_DIR}/../src ${SRC_DIR}/ccpi/src
ROBOCOPY /E ${RECIPE_DIR}/../ccpi ${SRC_DIR}/ccpi/ccpi
copy ${RECIPE_DIR}/../setup.py ${SRC_DIR}/ccpi
cd ${SRC_DIR}/ccpi

#:: issue cmake to create setup.py
cmake -G "Unix Makefiles" ${RECIPE_DIR}/../../../ -DBUILD_PYTHON_WRAPPERS=OFF -DCONDA_BUILD=ON -DBUILD_CUDA=OFF -DCMAKE_BUILD_TYPE="Release" -DLIBRARY_LIB="${CONDA_PREFIX}/lib" -DLIBRARY_INC="${CONDA_PREFIX}" -DCMAKE_INSTALL_PREFIX="${PREFIX}/Library" 

cmake --build . --target install
${PYTHON} setup.py install