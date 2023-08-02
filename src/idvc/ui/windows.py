import PySide2
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import os
import vtk
from ccpi.viewer import viewer2D, viewer3D
from ccpi.viewer.QCILViewerWidget import QCILViewerWidget
from ccpi.viewer.CILViewer2D import (SLICE_ORIENTATION_XY,
                                     SLICE_ORIENTATION_XZ,
                                     SLICE_ORIENTATION_YZ)
import ccpi.viewer.viewerLinker as vlink
from ccpi.viewer.utils.error_handling import ErrorObserver
from ccpi.viewer.utils import *

from idvc.ui.widgets import *


class VisualisationWindow(QtWidgets.QMainWindow):
    '''creates a window which will contain the VisualisationWidgets
    '''
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setMinimumSize(200,200)

class VisualisationWidget(QtWidgets.QMainWindow):
    '''creates a window with a QCILViewerWidget as the central widget
    '''
    def __init__(self, parent, viewer=viewer2D, interactorStyle=vlink.Linked2DInteractorStyle):
        super().__init__()
        self.parent = parent

        self.e = ErrorObserver()
        self.viewer = viewer
        self.interactorStyle = interactorStyle
        self.createEmptyFrame()
        self.threadpool = QThreadPool()

    def getViewer(self):
        return self.frame.viewer

    def getInteractor(self):
        return self.getViewer().getInteractor()

    def getInteractorStyle(self):
        return self.getViewer().style

    def getViewerType(self):
        return self.viewer

        
    def createEmptyFrame(self):
        #print("empty")
        self.frame = QCILViewerWidget(viewer=self.viewer, shape=(600,600), interactorStyle=self.interactorStyle)
        self.setCentralWidget(self.frame)
        self.image_file = [""]
       
    def displayImageData(self):
        self.createEmptyFrame()
        if self.viewer == viewer3D:
            #set volume mapper according to user settings:
            if self.parent.settings.value("volume_mapper") == "cpu":
                self.frame.viewer.volume_mapper = vtk.vtkFixedPointVolumeRayCastMapper()
                self.frame.viewer.volume.SetMapper(self.frame.viewer.volume_mapper)
        else:
            self.frame.viewer.setVisualisationDownsampling(self.parent.resample_rate)
            self.frame.viewer.setDisplayUnsampledCoordinates(True)

            vs_widgets = self.parent.visualisation_setting_widgets

            vs_widgets['loaded_image_dims_value'].setVisible(True)
            vs_widgets['loaded_image_dims_value'].setText(str(self.parent.unsampled_image_dimensions))

            #print("resample rate: ", self.parent.resample_rate)

            if self.parent.resample_rate != [1,1,1]:
                vs_widgets['displayed_image_dims_value'].setVisible(True)
                vs_widgets['displayed_image_dims_label'].setVisible(True)
                #print("Disp image size ", [self.parent.ref_image_data.GetDimensions()[i] for i in range(3)])
                vs_widgets['displayed_image_dims_value'].setText(str([round(self.parent.ref_image_data.GetDimensions()[i]) for i in range(3)]))
                vs_widgets['coords_combobox'].setEnabled(True)
                vs_widgets['coords_combobox'].setCurrentIndex(0)
                vs_widgets['coords_warning_label'].setVisible(True)
                vs_widgets['coords_info_label'].setVisible(True)

            
            else:
                vs_widgets['displayed_image_dims_value'].setVisible(False)
                vs_widgets['displayed_image_dims_label'].setVisible(False)
                vs_widgets['coords_warning_label'].setVisible(False)
                vs_widgets['coords_info_label'].setVisible(False)

                vs_widgets['coords_combobox'].setEnabled(False)
                vs_widgets['coords_combobox'].setCurrentIndex(0)

        self.frame.viewer.setInput3DData(self.image_data)  
        interactor = self.frame.viewer.getInteractor()


        if hasattr(self.parent, 'orientation'):
                orientation = self.parent.orientation
        else:
            orientation = self.frame.viewer.getSliceOrientation()
        
        if orientation == SLICE_ORIENTATION_XZ:
            axis = 'y'
        elif orientation == SLICE_ORIENTATION_YZ:
            axis = 'x'
        else:
            axis = 'z'
        interactor.SetKeyCode(axis)

        if self.viewer == viewer2D:
            self.frame.viewer.style.OnKeyPress(interactor, 'KeyPressEvent')
            if self.parent.current_slice:
                if self.parent.current_slice <= self.frame.viewer.img3D.GetExtent()[self.frame.viewer.getSliceOrientation()*2+1]:
                    self.frame.viewer.displaySlice(self.parent.current_slice)


        if self.viewer == viewer3D:
            self.frame.viewer.style.OnKeyPress(interactor, 'KeyPressEvent')
            # Depth peeling for volumes doesn't work as we would like when we have the vtk.vtkFixedPointVolumeRayCastMapper() instead of the vtk.vtkSmartVolumeMapper()
            # self.frame.viewer.sliceActor.GetProperty().SetOpacity(0.99)
            # self.frame.viewer.ren.SetUseDepthPeeling(True)
            # self.frame.viewer.renWin.SetAlphaBitPlanes(True)
            # self.frame.viewer.renWin.SetMultiSamples(False)
            # self.frame.viewer.ren.UseDepthPeelingForVolumesOn()
    
            if self.parent.current_slice:
                if self.parent.current_slice <= self.frame.viewer.img3D.GetExtent()[self.frame.viewer.getSliceOrientation()*2+1]:
                    self.frame.viewer.style.SetActiveSlice(self.parent.current_slice)
                    self.frame.viewer.style.UpdatePipeline()

        # print("set input data for" + str(self.viewer))

        if self.viewer == viewer2D:
            self.PlaneClipper = cilPlaneClipper()
            self.PlaneClipper.SetInteractorStyle(self.frame.viewer.style)


    def setImageData(self, image_data):
        self.image_data = image_data

    def getImageData(self):
        return self.image_data

class GraphsWindow(QMainWindow):
    '''creates a new window with graphs from results saved in the selected run folder.
    '''
    def __init__(self, parent=None):
        super(GraphsWindow, self).__init__(parent)
        self.setWindowTitle("Digital Volume Correlation Results")
        DVCIcon = QtGui.QIcon()
        DVCIcon.addFile("DVCIconSquare.png")

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.settings_menu = self.menu.addMenu("Settings")

        displacement_setting_action = QAction("Show Displacement Relative to Reference Point 0", self)
        displacement_setting_action.setCheckable(True)
        displacement_setting_action.setChecked(False)
        self.displacement_setting_action = displacement_setting_action

        displacement_setting_action.triggered.connect(self.ReloadGraphs)
        self.settings_menu.addAction(displacement_setting_action)


        # Exit QAction
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)

        #Tab positions:
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas,QTabWidget.North)
        self.setDockOptions(QMainWindow.ForceTabbedDocks)
             
        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)

        self.setGeometry(50,50, geometry.width()-100, geometry.height()-100)
        #self.setFixedSize(geometry.width() * 0.6, geometry.height() * 0.8)

    def SetResultsFolder(self, folder):
        self.results_folder = folder
        self.setWindowTitle("Digital Volume Correlation Results - {foldername}".format(foldername=os.path.basename(self.results_folder)))
    
    def ReloadGraphs(self):
        self.DeleteAllWidgets()
        self.CreateDockWidgets(displ_wrt_point0 = self.displacement_setting_action.isChecked())

    def DeleteAllWidgets(self):
         for current_dock in self.findChildren(QDockWidget):
            current_dock.close()
            del current_dock

    def CreateDockWidgets(self, displ_wrt_point0 = False):
        result_list=[]
        #print(results_folder[0])
        for folder in glob.glob(os.path.join(self.results_folder, "dvc_result_*")):
            file_path = os.path.join(folder, os.path.basename(folder))
            result = RunResults(file_path)
            result_list.append(result)
    
            GraphWidget = SingleRunResultsWidget(self, result, displ_wrt_point0)
            dock1 = QDockWidget(result.title,self)
            dock1.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
            dock1.setWidget(GraphWidget)
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock1)
    
        prev = None

        for current_dock in self.findChildren(QDockWidget):
            if self.dockWidgetArea(current_dock) == QtCore.Qt.RightDockWidgetArea:
                existing_widget = current_dock

                if prev:
                    self.tabifyDockWidget(prev,current_dock)
                prev= current_dock
        
        SummaryTab = SummaryGraphsWidget(self, result_list)
        dock = QDockWidget("Summary",self)
        dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
        dock.setWidget(SummaryTab)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock)
        self.tabifyDockWidget(prev,dock)

        dock.raise_() # makes summary panel the one that is open by default.

