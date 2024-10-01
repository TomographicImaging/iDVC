import PySide2
from PySide2 import QtWidgets, QtGui, QtCore
import os, sys
import logging
import argparse


def main():

    parser = argparse.ArgumentParser(description='iDVC - Digital Volume Correlation Software')

    parser.add_argument('--debug', type=str)
    args = parser.parse_args()

    if args.debug in ['debug', 'info', 'warning', 'error', 'critical']:
        level = eval(f'logging.{args.debug.upper()}')
        logging.basicConfig(level=level)
        logging.info(f"iDVC: Setting debugging level to {args.debug.upper()}")
    app = QtWidgets.QApplication([])
    # Set a global font for the application
    font = QtGui.QFont("Arial", 12)  # Replace with your preferred font and size
    QtWidgets.QApplication.setFont(font)

    
    file_dir = os.path.dirname(__file__)
    owl_file = os.path.join(file_dir, "DVCIconSquare.png")
    owl = QtGui.QPixmap(owl_file)
    splash = QtWidgets.QSplashScreen(owl)
    splash.show()
    

    import vtk
    err = vtk.vtkFileOutputWindow()
    err.SetFileName("../viewer.log")
    vtk.vtkOutputWindow.SetInstance(err)

    from idvc.dvc_interface import MainWindow
    window = MainWindow()
    
    window.show()
    splash.finish(window)

    

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
