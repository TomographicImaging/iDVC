set -ex
mkdir -p $SRC_DIR/ccpi
cp -rv $RECIPE_DIR/.. $SRC_DIR/ccpi

cp -r ${RECIPE_DIR}/../ccpi ${SRC_DIR}/ccpi/ccpi
cp ${RECIPE_DIR}/../setup.py ${SRC_DIR}/ccpi
cd ${SRC_DIR}/ccpi

#:: issue cmake to create setup.py
if [ `python -c "from __future__ import print_function; import platform; print (platform.system())"`  == "Darwin" ] ;
then 
  echo "Darwin"; 
  
  #cmake ${RECIPE_DIR}/../../../ -DBUILD_PYTHON_WRAPPERS=OFF -DCONDA_BUILD=ON -DBUILD_CUDA=OFF -DCMAKE_BUILD_TYPE="Release" -DLIBRARY_LIB=${CONDA_PREFIX}/lib -DLIBRARY_INC=${CONDA_PREFIX} -DCMAKE_INSTALL_PREFIX=${PREFIX}/Library -DOPENMP_INCLUDES=${CONDA_PREFIX}/include -DOPENMP_LIBRARIES=${CONDA_PREFIX}/lib
  cmake ${RECIPE_DIR}/../../../  \
                        -DBUILD_PYTHON_WRAPPER=OFF\
                        -DCMAKE_BUILD_TYPE="Release"\
                        -DCMAKE_INSTALL_PREFIX=$PREFIX
#                        -DLIBRARY_LIB=$CONDA_PREFIX/lib \
#                        -DLIBRARY_INC=$CONDA_PREFIX \
#                        -DOPENMP_CXX_INCLUDE_DIR=${CONDA_PREFIX}/include \
#                        -DOPENMP_LIBRARIES=${CONDA_PREFIX}/lib
#-DOpenMP_C_FLAGS="-Xpreprocessor -fopenmp -I${CONDA_PREFIX}/include" \
#-DOpenMP_C_LIB_NAMES="omp" \
#-DOpenMP_CXX_FLAGS="-Xpreprocessor -fopenmp -I${CONDA_PREFIX}/include" \
 #               -DOpenMP_CXX_LIB_NAMES="omp" \
 #               -DOpenMP_omp_LIBRARY=${CONDA_PREFIX}/lib/libomp.dylib

else 
  echo "something else"; 
  #cmake ${RECIPE_DIR}/../../../ -DBUILD_PYTHON_WRAPPERS=OFF -DCONDA_BUILD=ON -DBUILD_CUDA=OFF -DCMAKE_BUILD_TYPE="Release" -DLIBRARY_LIB="${CONDA_PREFIX}/lib" -DLIBRARY_INC="${CONDA_PREFIX}" -DCMAKE_INSTALL_PREFIX="${PREFIX}/Library" 
  cmake ${RECIPE_DIR}../../../  \
                        -DBUILD_PYTHON_WRAPPER=OFF\
                        -DCMAKE_BUILD_TYPE="Release"\
                        -DCMAKE_INSTALL_PREFIX=$PREFIX
#                        -DLIBRARY_LIB=$CONDA_PREFIX/lib \
#                        -DLIBRARY_INC=$CONDA_PREFIX \
fi
cmake --build . --target install
${PYTHON} setup.py install
