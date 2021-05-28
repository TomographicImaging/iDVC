set -ex
mkdir -p $SRC_DIR
cp -rv $RECIPE_DIR/../src $SRC_DIR
cp -rv $RECIPE_DIR/../test $SRC_DIR/test
cp -rv $RECIPE_DIR/../setup.py $SRC_DIR/setup.py
cd ${SRC_DIR}

${PYTHON} setup.py install
