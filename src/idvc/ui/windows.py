import os
import ccpi.viewer.viewerLinker as vlink
import vtk
from ccpi.viewer import viewer2D, viewer3D
from ccpi.viewer.CILViewer2D import (SLICE_ORIENTATION_XY,
                                     SLICE_ORIENTATION_XZ,
                                     SLICE_ORIENTATION_YZ)
from ccpi.viewer.QCILViewerWidget import QCILViewerWidget
from ccpi.viewer.utils import *
from ccpi.viewer.utils.error_handling import ErrorObserver
from PySide2 import QtCore, QtGui, QtWidgets

from idvc.ui.graphs_widgets import *
import logging 
import pandas as pd
from idvc.utils.manipulate_result_files import createResultsDataFrame, addMeanAndStdToResultDataFrame


class VisualisationWindow(QtWidgets.QMainWindow):
    '''creates a window which will contain the VisualisationWidgets
    '''
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setMinimumSize(200,200)

    def createPopupMenu(self):
        '''returns an empty menu for the main window to use as a popup menu.
        
        https://doc.qt.io/qt-6/qmainwindow.html#createPopupMenu
        '''
        return QtWidgets.QMenu(self)
    

class VisualisationWidget(QtWidgets.QMainWindow):
    '''creates a window with a QCILViewerWidget as the central widget
    '''
    def __init__(self, parent, viewer=viewer2D, interactorStyle=vlink.Linked2DInteractorStyle, enableSliderWidget=True):
        super().__init__()
        self.parent = parent

        self.e = ErrorObserver()
        self.viewer = viewer
        self.interactorStyle = interactorStyle
        self.enableSliderWidget = enableSliderWidget
        self.createEmptyFrame()
        self.threadpool = QThreadPool()
        self._consume_CharEvent = ['s', 'w']
        

    def getViewer(self):
        return self.frame.viewer

    def getInteractor(self):
        return self.getViewer().getInteractor()

    def getInteractorStyle(self):
        return self.getViewer().style

    def getViewerType(self):
        return self.viewer
     
    def createEmptyFrame(self):
        self.frame = QCILViewerWidget(self.parent, self.viewer, shape=(600,600), interactorStyle=self.interactorStyle, 
                                      enableSliderWidget=self.enableSliderWidget)
        self.setCentralWidget(self.frame)
        self.image_file = [""]
        
       
    def displayImageData(self):
        self.createEmptyFrame()
        if self.viewer == viewer3D:
            #set volume mapper according to user settings:
            if self.parent.settings.value("volume_mapper") == "cpu":
                self.frame.viewer.volume_mapper = vtk.vtkFixedPointVolumeRayCastMapper()
                self.frame.viewer.volume.SetMapper(self.frame.viewer.volume_mapper)
        elif self.viewer == viewer2D:
            self.frame.viewer.style.htext = """
            Mouse Interactions:
                - Slice: Mouse Scroll
                - Quick Slice: Shift + Mouse Scroll
                - Zoom: Shift + Right Mouse + Move Up/Down
                - Pan: Ctrl + Right Mouse + Move
                - Adjust Window: Alt+ Right Mouse + Move Up/Down
                - Adjust Level: Alt + Right Mouse + Move Left/Right

            Keyboard Interactions:
                h: This help
                x: YZ Plane
                y: XZ Plane
                z: XY Plane
                a: Whole image Auto Window/Level
                w: Region around cursor Auto Window/Level
                l: Line Profile at cursor
                s: Save Current Image
                i: Toggle interpolation of slice
                """
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

        # consume 's' and 'w' events
        # https://github.com/vais-ral/CILViewer/issues/332#issuecomment-1888940327
        self.getInteractor().AddObserver('CharEvent', self.consumeCharEvent, 10.)

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

    def consumeCharEvent(self, interactor, event):
        '''Changes the event in self._consume_CharEvent to "" so that the event is not processed by the viewer.
        
        This prevents the viewer from changing the rendered scene to surface or wireframe mode when the user presses 's' or 'w' respectively.
        '''
        if interactor.GetKeyCode() in self._consume_CharEvent:
            logging.info("Consuming event: " + interactor.GetKeyCode())
            interactor.SetKeyCode("")


class GraphsWindow(QtWidgets.QMainWindow):
    """
    Creates a new window with graphs from results saved in the selected run folder.
    """
    def __init__(self, parent=None):
        """
        Initialises the class. Adds an icon to the window. 
        Adds a menu with the option to show displacement relative to point 0.
        Sets the position of the tabs in the window and the geometry of the window.
        """
        super(GraphsWindow, self).__init__(parent)
        DVCIcon = QtGui.QIcon()
        DVCIcon.addFile("DVCIconSquare.png")

        # Menu
        self.menu = self.menuBar()
        self.settings_menu = self.menu.addMenu("Custom options")

        displacement_setting_action = QAction("Show Displacement Relative to Reference Point 0", self)
        displacement_setting_action.setCheckable(True)
        displacement_setting_action.setChecked(False)
        self.displacement_setting_action = displacement_setting_action

        displacement_setting_action.triggered.connect(self.ReloadGraphs)
        self.settings_menu.addAction(displacement_setting_action)

        #Tab positions:
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas,QTabWidget.North)
        self.setDockOptions(QMainWindow.ForceTabbedDocks)
             
        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)

        self.setGeometry(50,50, geometry.width()-100, geometry.height()-100)
        #self.setFixedSize(geometry.width() * 0.6, geometry.height() * 0.8)

    def SetResultsFolder(self, folder):
        """Creates the attribute 'result_folder' and sets the graphs-window title."""
        self.results_folder = folder
        self.setWindowTitle("Run {foldername}".format(foldername=os.path.basename(self.results_folder)))
    
    def ReloadGraphs(self):
        """Deletes all widgets in the graphs window and creates new ones."""
        self.DeleteAllWidgets()
        self.CreateDockWidgets(displ_wrt_point0 = self.displacement_setting_action.isChecked())

    def DeleteAllWidgets(self):
         """Deletes all dock widgets in the graphs window."""
         for current_dock in self.findChildren(QDockWidget):
            current_dock.close()
            del current_dock

    def CreateDockWidgets(self, displ_wrt_point0 = False):  
        """
        Creates and configures dock widgets for displaying results.

        Initialises and adds dock widgets to the graphs window.
        It creates a single-run results widget and, if there are multiple results,
        a bulk-run results widget and a statistical-analysis widget. 
        The widgets are added to the right dock widget area and tabified.
        
        Parameters
        ----------
        displ_wrt_point0 : bool, optional
            A flag to indicate whether to display results with respect to point 0.
        """
        result_data_frame = createResultsDataFrame(self.results_folder, displ_wrt_point0)
        result_data_frame = addMeanAndStdToResultDataFrame(result_data_frame)
        single_run_results_widget = SingleRunResultsWidget(self, result_data_frame)
        dock1 = QDockWidget("Single", self)
        dock1.setFeatures(QDockWidget.NoDockWidgetFeatures) 
        dock1.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
        dock1.setWidget(single_run_results_widget)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock1)

        prev = None

        for current_dock in self.findChildren(QDockWidget):
            if self.dockWidgetArea(current_dock) == QtCore.Qt.RightDockWidgetArea:
                existing_widget = current_dock

                if prev:
                    self.tabifyDockWidget(prev,current_dock)
                prev= current_dock
        
        if len(result_data_frame) > 1:
            bulk_run_results_widget = BulkRunResultsWidget(self, result_data_frame)
            dock2 = QDockWidget("Bulk",self)
            dock2.setFeatures(QDockWidget.NoDockWidgetFeatures) 
            dock2.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
            dock2.setWidget(bulk_run_results_widget)
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock2)
            self.tabifyDockWidget(prev,dock2)

            dock2.raise_() # makes bulk panel the one that is open by default.
            
            # add statistial analysis tab
            statistical_analisis_widget = StatisticsResultsWidget(self, result_data_frame)
            dock3 = QDockWidget("Statistical analysis",self)
            dock3.setFeatures(QDockWidget.NoDockWidgetFeatures) 
            dock3.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
            dock3.setWidget(statistical_analisis_widget)
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock3)
            self.tabifyDockWidget(dock2,dock3)

        # Stop the widgets in the tab to be moved around
        for wdg in self.findChildren(QTabBar):
            wdg.setMovable(False)


