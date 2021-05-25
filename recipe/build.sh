set -ex
mkdir -p $SRC_DIR
cp -rv $RECIPE_DIR/../../Apps/DVC_configurator/ccpi $SRC_DIR
cp -rv $RECIPE_DIR/../../Apps/DVC_configurator/setup.py $SRC_DIR/setup.py
cd ${SRC_DIR}

${PYTHON} setup.py install
