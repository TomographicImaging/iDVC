import PySide2
from PySide2 import QtWidgets, QtGui
import os, sys

def main():
    app = QtWidgets.QApplication([])
    
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
