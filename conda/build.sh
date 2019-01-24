
mkdir "$SRC_DIR/ccpi"
cp -rv "$RECIPE_DIR/.." "$SRC_DIR/ccpi"

cd $SRC_DIR/ccpi


#$PYTHON setup-regularisers.py build_ext
$PYTHON setup.py install


