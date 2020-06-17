import sys
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QThreadPool, QRegExp, QSize, Qt, QSettings, QByteArray
from PyQt5.QtWidgets import QMainWindow, QAction, QDockWidget, QFrame, QVBoxLayout, QFileDialog, QStyle, QMessageBox, QApplication, QWidget, QDialog, QDoubleSpinBox
from PyQt5.QtWidgets import QLineEdit, QSpinBox, QLabel, QComboBox, QProgressBar, QStatusBar,  QPushButton, QFormLayout, QGroupBox, QCheckBox, QTabWidget, qApp
from PyQt5.QtWidgets import QProgressDialog, QDialogButtonBox
from PyQt5.QtGui import QRegExpValidator, QKeySequence, QCloseEvent
import os
import time
import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from functools import partial
from datetime import datetime

from os import listdir
from os.path import isfile, join
from os import path

import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor #
from ccpi.viewer.QCILRenderWindowInteractor import QCILRenderWindowInteractor #
from ccpi.viewer import viewer2D, viewer3D # 
from ccpi.viewer.QCILViewerWidget import QCILViewerWidget #

from ccpi.viewer.utils import Converter
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XZ
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_YZ 
from ccpi.viewer.utils import cilRegularPointCloudToPolyData

from ccpi.viewer.CILViewer2D import CILInteractorStyle as CILInteractorStyle2D
from ccpi.viewer.CILViewer import CILInteractorStyle as CILInteractorStyle3D

from ccpi.viewer.utils import cilNumpyMETAImageWriter

import locale

from ccpi.viewer.QtThreading import Worker, WorkerSignals, ErrorObserver #

from natsort import natsorted
import imghdr

from vtk.util import numpy_support

from vtk.numpy_interface import dataset_adapter as dsa
from vtk.numpy_interface import algorithms as algs

from vtk.util.vtkAlgorithm import VTKPythonAlgorithmBase

import ccpi.viewer.viewerLinker as vlink

working_directory = os.getcwd()
os.chdir(working_directory) 

from ccpi.viewer.utils import cilMaskPolyData, cilClipPolyDataBetweenPlanes

import tempfile
import json
import shutil
import zipfile
import zlib

import csv
from functools import reduce

import subprocess

import copy

from distutils.dir_util import copy_tree

#from ccpi.dvc.apps import image_data
from image_data import ImageDataCreator

class cilNumpyPointCloudToPolyData(VTKPythonAlgorithmBase): #This class is copied from dvc_configurator.py
    '''vtkAlgorithm to read a point cloud from a NumPy array
    '''
    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self, nInputPorts=0, nOutputPorts=1)
        self.__Points = vtk.vtkPoints()
        self.__Vertices = vtk.vtkCellArray()
        self.__Data = None


    def GetPoints(self):
        '''Returns the Points'''
        return self.__Points
    def SetData(self, value):
        '''Sets the points from a numpy array or list'''
        if not isinstance (value, np.ndarray) :
            raise ValueError('Data must be a numpy array. Got', value)

        if not np.array_equal(value,self.__Data):
            self.__Data = value
            self.Modified()

    def GetData(self):
        return self.__Data


    def GetNumberOfPoints(self):
        '''returns the number of points in the point cloud'''
        return self.__Points.GetNumberOfPoints()


    def FillInputPortInformation(self, port, info):
        # if port == 0:
        #    info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        return 1

    def FillOutputPortInformation(self, port, info):
        info.Set(vtk.vtkDataObject.DATA_TYPE_NAME(), "vtkPolyData")
        return 1

    def RequestData(self, request, inInfo, outInfo):

        # print ("Request Data")
        # image_data = vtk.vtkDataSet.GetData(inInfo[0])
        pointPolyData = vtk.vtkPolyData.GetData(outInfo)
        vtkPointCloud = self.__Points
        for point in self.GetData():
            # point = id, x, y, z
            vtkPointCloud.InsertNextPoint( point[1] , point[2] , point[3])

        self.FillCells()

        pointPolyData.SetPoints(self.__Points)
        pointPolyData.SetVerts(self.__Vertices)
        return 1


    def FillCells(self):
        '''Fills the Vertices'''
        vertices = self.__Vertices
        number_of_cells = vertices.GetNumberOfCells()
        for i in range(self.GetNumberOfPoints()):
            if i >= number_of_cells:
                vertices.InsertNextCell(1)
                vertices.InsertCellPoint(i)


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        
        self.threadpool = QThreadPool()

        self.temp_folder = None

        self.CreateWorkingTempFolder()
        self.CreateSessionSelector("new window")
        
        self.setWindowTitle("DVC Interface")
        
        self.InitialiseSessionVars()

        self.setDockNestingEnabled(True)
        self.CreateDockWindows()


        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")

        #Settings QAction
        settings_action = QAction("Settings", self)
        #save_action.setShortcut(QKeySequence.Save)
        settings_action.triggered.connect(self.OpenSettings)
        self.file_menu.addAction(settings_action)

        #Save QAction
        save_action = QAction("Save", self)
        save_action.triggered.connect(partial(self.CreateSaveWindow,"Cancel"))
        self.file_menu.addAction(save_action)

        #New QAction
        new_action = QAction("New Session", self)
        new_action.triggered.connect(self.NewSession)
        self.file_menu.addAction(new_action)

        #Load QAction
        load_action = QAction("Load Session", self)
        #load_action.setShortcut(QKeySequence.Open)
        load_action.triggered.connect(lambda: self.CreateSessionSelector("current window"))
        self.file_menu.addAction(load_action)

        #Export Session
        export_action = QAction("Export Session", self)
        export_action.triggered.connect(self.export_session)
        self.file_menu.addAction(export_action)

        # Exit QAction
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage("Ready")
             
        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)
        self.setGeometry(geometry.width(), geometry.height(),1200, 600)

        self.e = ErrorObserver()

        #Load Settings:
        self.settings = QSettings("CCPi", "DVC Interface")
        if self.settings.value("copy_files"):
            self.copy_files = True
        else:
            self.copy_files = False


#Setting up the session:
    def CreateWorkingTempFolder(self):
        directories = [x for x in next(os.walk(working_directory))[1]]

        temp_folder = None

        for directory in directories:
            if 'temp' in directory:
                temp_folder = directory
        
        if(not temp_folder):
            temp_folder = os.mkdir("temp")

        self.temp_folder = temp_folder
        tempfile.tempdir = tempfile.mkdtemp(dir = self.temp_folder)

        os.mkdir(os.path.join(tempfile.tempdir, "Masks")) # Creates folder in tempdir to save mask files in
        os.mkdir(os.path.join(tempfile.tempdir, "Results"))

    def OpenSettings(self):
        self.settings_window = CreateSettingsWindow(self)
        self.settings_window.show()

    def InitialiseSessionVars(self):
        self.config={}
        self.image=[[],[]]
        self.dvc_input_image = [[],[]]
        self.roi = None
        self.run_folder = [None]
        self.results_folder = [None]
        #self.loaded_session = False
        self.pointCloudCreated = False
        self.pointCloudLoaded = False
        self.orientation = 2 #z orientation is default
        self.mask_reader = None
        self.current_slice = None
        self.mask_details = {}
        self.pointCloud_details = {}
        self.image_copied = [False,False]
        self.runs_completed = 0
        self.run_config_file = None
        self.mask_load = False
        self.raw_import_dialog = None
        self.reg_load = False
          
    def UpdateClippingPlanes(self, interactor, event):
        try:
            normal = [0, 0, 0]
            origin = [0, 0, 0]
            norm = 1
            v = self.vis_widget_2D.frame.viewer
            bpcpoints = self.bpcpoints
            bpcvolume = self.bpcvolume
            orientation = v.GetSliceOrientation()
            if orientation == SLICE_ORIENTATION_XY:
                norm = 1
            elif orientation == SLICE_ORIENTATION_XZ:
                norm = 1
            elif orientation == SLICE_ORIENTATION_YZ:
                norm = 1

            if event == "MouseWheelForwardEvent":
                # this is pretty absurd but it seems the
                # plane cuts too much in Forward...
                # Made new adjustments for each direction
                if orientation == SLICE_ORIENTATION_XY: #z
                    beta = 2
                elif orientation == SLICE_ORIENTATION_XZ: #y
                    beta = 1
                elif orientation == SLICE_ORIENTATION_YZ: #x
                    beta = 1

            if event == "MouseWheelBackwardEvent":
                # since modifying the camera direction in CILViewer2D,
                # and to enable viewing in the y direction, had to update
                # beta for MouseWheelBackward as well.
                if orientation == SLICE_ORIENTATION_XY: #z
                    beta = 0
                elif orientation == SLICE_ORIENTATION_XZ: #y
                    beta = -1
                elif orientation == SLICE_ORIENTATION_YZ: #x
                    beta = -1

            spac = v.img3D.GetSpacing()
            #print("spacing")
            #print(spac)
            orig = v.img3D.GetOrigin()
            slice_thickness = spac[orientation]

            normal[orientation] = norm
            origin [orientation] = (v.style.GetActiveSlice() + beta ) * slice_thickness - orig[orientation]

            bpcpoints.SetPlaneOriginAbove(origin)
            bpcpoints.SetPlaneNormalAbove(normal)

            bpcvolume.SetPlaneOriginAbove(origin)
            bpcvolume.SetPlaneNormalAbove(normal)

            # update the  plane below
            #beta += 1
            slice_below = v.style.GetActiveSlice() -1 + beta
            if slice_below < 0:
                slice_below = 0

            origin_below = [i for i in origin]
            origin_below[orientation] = ( slice_below ) * slice_thickness - orig[orientation]

            bpcpoints.SetPlaneOriginBelow(origin_below)
            bpcpoints.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))
            bpcvolume.SetPlaneOriginBelow(origin_below)
            bpcvolume.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))

            bpcpoints.Update()
            bpcvolume.Update()
            #self.vis_widget_2D.frame.viewer.sliceActor.GetProperty().SetOpacity(0.99)
            #self.vis_widget_2D.frame.viewer.sliceActor2.GetProperty().SetOpacity(0.99) #actor with mask
            #self.vis_widget_2D.frame.viewer.sliceActor.GetProperty().SetOpacity(0.1)
            # print (">>>>>>>>>>>>>>>>>>>>>")
        except AttributeError as ae:
            print (ae)
            print ("Probably Point Cloud not yet created")

#Loading the DockWidgets:
    def CreateDockWindows(self):

        
        
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas,QTabWidget.North)

        #Create widgets to view images in 2D and 3D and link them:
        self.vis_widget_2D = VisualisationWidget(self, viewer=viewer2D, interactorStyle=vlink.Linked2DInteractorStyle)#interactorStyle= CILInteractorStyle2D) #previously unliked for testing
        self.vis_widget_3D = VisualisationWidget(self, viewer=viewer3D, interactorStyle=vlink.Linked3DInteractorStyle) #interactorStyle= CILInteractorStyle3D)#previously unlinked for testing

        self.CreateHelpPanel()

        self.CreateSelectImagePanel()
        self.CreateRegistrationPanel()
        self.CreateMaskPanel()
        self.CreatePointCloudPanel()
        self.CreateRunDVCPanel()
        self.CreateViewDVCResultsPanel()

        
        
        #self.CreateGenerateGraphsPanel()
        
        #Tabifies dockwidgets in LeftDockWidgetArea:
        prev = None
        first_dock = None
        docks = []
        for current_dock in self.findChildren(QDockWidget):
            if self.dockWidgetArea(current_dock) == QtCore.Qt.LeftDockWidgetArea:
                if prev:
                    self.tabifyDockWidget(prev,current_dock)                    
                else:
                    first_dock = current_dock
                prev= current_dock
                docks.append(current_dock)
                
        first_dock.raise_() # makes first panel the one that is open by default.

        

        self.VisualisationWindow = VisualisationWindow(self)

        self.setCentralWidget(self.VisualisationWindow)

        dock4 = QDockWidget("2D View",self.VisualisationWindow)
        dock4.setObjectName("2DImageView")
        dock4.setWidget(self.vis_widget_2D)
        self.viewer2D_dock = dock4

        dock5 = QDockWidget("3D View",self.VisualisationWindow)
        dock5.setObjectName("3DImageView")
        dock5.setWidget(self.vis_widget_3D)
        dock5.setAllowedAreas(Qt.RightDockWidgetArea)
        self.viewer3D_dock = dock5


        self.VisualisationWindow.addDockWidget(QtCore.Qt.TopDockWidgetArea,dock4)
        self.VisualisationWindow.addDockWidget(QtCore.Qt.BottomDockWidgetArea,dock5)

    def CreateHelpPanel(self):
        self.help_panel = generateUIDockParameters(self, "Help")
        dockWidget = self.help_panel[0]
        dockWidget.setObjectName("HelpPanel")
        groupBox = self.help_panel[5]
        formLayout = self.help_panel[6]
        self.help_dock = dockWidget

        self.help_text = ["'raw' and 'npy' formats are recommended.\n You can view the shortcuts for the viewer by clicking on the 2D image and then pressing the 'h' key."]

        self.help_text.append("Click 'Select point 0' to select a point and region for registering the image.\n It is recommended to select 'Register on Selection' \
and select a size smaller than 1000.\n Once you are satisfied with the registration, make sure the point 0 you have selected is the point you want the DVC to start from.")
        
        self.help_text.append("Enable trace mode by clicking on the 2D viewer, then pressing 't'. Then you may draw a region freehand.")

        self.help_text.append("If you load a pointcloud from a file, you must still specify the pointcloud radius on this panel, \
which will later be doubled to get the pointcloud size and then input to the DVC code.")

        self.help_text.append("Once the code is run it is recommended that you save or export your session, to back up your results. You can access these options under 'File'.")

        self.help_text.append("Vectors can be displayed in 2D or 3D on the 2D viewer. It is not advised to load vectors for more than 1000 points as this may cause the viewer to crash.")

        self.help_label = QLabel(groupBox)
        self.help_label.setWordWrap(True)
        self.help_label.setText(self.help_text[0])
        formLayout.setWidget(1, QFormLayout.SpanningRole, self.help_label)

        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea,dockWidget)


    def displayHelp(self, open, panel_no = None):
        if open:
            self.help_label.setText(self.help_text[panel_no])
        




#Select Image Panel:
    def CreateSelectImagePanel(self):
        self.select_image_panel = generateUIDockParameters(self, "1 - Select Image")
        dockWidget = self.select_image_panel[0]
        dockWidget.setObjectName("SelectImagePanel")
        groupBox = self.select_image_panel[5]
        groupBox.setTitle('Image Selection')
        formLayout = self.select_image_panel[6]
        self.select_image_dock = dockWidget

        dockWidget.visibilityChanged.connect(partial(self.displayHelp,panel_no = 0))

        

        #Create the widgets:

        widgetno = 1

        si_widgets = {}

        si_widgets['ref_vol_label'] = QLabel(groupBox)
        si_widgets['ref_vol_label'].setText("Reference Volume:")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, si_widgets['ref_vol_label'])

        si_widgets['ref_file_label'] = QLabel(groupBox)
        si_widgets['ref_file_label'].setText("")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, si_widgets['ref_file_label'])
        widgetno += 1

        si_widgets['ref_browse'] = QPushButton(groupBox)
        si_widgets['ref_browse'].setText("Browse..")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, si_widgets['ref_browse'])
        widgetno += 1

        separators = []
        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1

        si_widgets['cor_vol_label'] = QLabel(groupBox)
        si_widgets['cor_vol_label'].setText("Correlate Volume:")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, si_widgets['cor_vol_label'])

        si_widgets['cor_file_label'] = QLabel(groupBox)
        si_widgets['cor_file_label'].setText("")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, si_widgets['cor_file_label'])
        widgetno += 1

        si_widgets['cor_browse'] = QPushButton(groupBox)
        si_widgets['cor_browse'].setText("Browse..")
        si_widgets['cor_browse'].setEnabled(False)
        
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, si_widgets['cor_browse'])
        widgetno += 1

        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1

        # si_widgets['roi_label'] = QLabel(groupBox)
        # si_widgets['roi_label'].setText("ROI:")
        # formLayout.setWidget(widgetno, QFormLayout.LabelRole, si_widgets['roi_label'])

        # si_widgets['roi_file_label'] = QLabel(groupBox)
        # si_widgets['roi_file_label'].setText("")
        # formLayout.setWidget(widgetno, QFormLayout.FieldRole, si_widgets['roi_file_label'])
        # widgetno += 1

        si_widgets['view_button'] = QPushButton(groupBox)
        si_widgets['view_button'].setText("View Image")
        si_widgets['view_button'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, si_widgets['view_button'])
        widgetno += 1

        #button functions:
        si_widgets['ref_browse'].clicked.connect(lambda: self.SelectImage(si_widgets['ref_file_label'],0,si_widgets['cor_browse']))
        si_widgets['cor_browse'].clicked.connect(lambda: self.SelectImage(si_widgets['cor_file_label'],1,si_widgets['view_button']))
        #si_widgets['roi_browse'].clicked.connect(lambda: self.select_pointcloud(si_widgets['roi_file_label']))
        si_widgets['view_button'].clicked.connect(self.view_and_load_images)

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,dockWidget)

        self.si_widgets = si_widgets
    
    def view_and_load_images(self):
        self.view_image()
        #self.load_corr_image()
        self.resetRegistration()
        #del self.vis_widget_reg.frame.viewer

    def SelectImage(self, label, image_var, next_button): 
        #print("In select image")
        dialogue = QFileDialog()
        files = dialogue.getOpenFileNames(self,"Load Images")[0]

        if len(files) > 0:
            if self.copy_files:
                self.image_copied[image_var] = True
                count = 0
                self.create_progress_window("Copying", "Copying files", 100, None)
                self.progress_window.setValue(1)
                file_num = 0
                for f in files:
                    file_name = f.split("/")[-1]
                    file_ext = f.split(".")[-1]
                    if file_ext == "mhd":
                        new_file_dest = os.path.join(tempfile.tempdir, file_name[:-3] + "mha")
                    else:
                        new_file_dest = os.path.join(tempfile.tempdir, file_name)
                    
                    copy_worker = Worker(self.copy_file, f, new_file_dest)
                    self.threadpool.start(copy_worker)
                    files[file_num] = new_file_dest
                    file_num+=1
                    count+=1
                    if len(files) == 1:
                        self.show_copy_progress(f, new_file_dest, 1, file_ext, len(files))
                    else:
                        self.progress_window.setValue(count/len(files)*100)
            else:
                self.image_copied[image_var] = False

            if len(files) == 1: #@todo
                if(self.image[image_var]):
                    #print("Right here")
                    #print(self.vis_widget_2D.image_file)
                    self.image[image_var]= files
                    #print(self.vis_widget_2D.image_file)
                else:
                    #print(self.vis_widget_2D.image_file)
                    self.image[image_var].append(files[0])
                    #print(self.vis_widget_2D.image_file)
                label.setText(files[0].split("\\")[-1])
                
            else:
                # Make sure that the files are sorted 0 - end
                filenames = natsorted(files)
                # Basic test for tiff images
                for f in filenames:
                    ftype = imghdr.what(f)
                    if ftype != 'tiff':
                        # A non-TIFF file has been loaded, present error message and exit method
                        self.e(
                            '', '', 'When reading multiple files, all files must TIFF formatted.')
                        error_title = "READ ERROR"
                        error_text = "Error reading file: ({filename})".format(filename=f)
                        self.displayFileErrorDialog(message=error_text, title=error_title)
                        #self.CreateSessionSelector()
                        #return #prevents dialog showing for every single file by exiting the for loop
                if(self.image[image_var]):
                    self.image[image_var] = filenames
                else:
                    self.image[image_var]=filenames
                label.setText(self.image[image_var][0].split("/")[-1] + " + " + str(len(files)) + " more files.")
            
            next_button.setEnabled(True)
            #print(self.vis_widget_2D.image_file)

    def copy_file(self, start_location, end_location, progress_callback):
        file_extension = start_location.split(".")[-1]
        #CHECK LOCATION FOR THIS CODE
        if file_extension == 'mhd':
            reader = vtk.vtkMetaImageReader()
            reader.SetFileName(start_location)
            reader.Update()
            writer = vtk.vtkMetaImageWriter()
            tmpdir = tempfile.gettempdir()
            writer.SetFileName(end_location)
            writer.SetInputData(reader.GetOutput())
            writer.Write()
            #print("wrote")
        else:
            shutil.copyfile(start_location, end_location)

    def show_copy_progress(self, _file, new_file_dest,ratio, file_type, num_files):

        while not os.path.exists(new_file_dest):
            time.sleep(0.001)

        if(file_type != "mhd"):
            while os.path.getsize(_file) != os.path.getsize(new_file_dest):
                self.progress_window.setValue(int((float(os.path.getsize(new_file_dest))/float(os.path.getsize(_file)*ratio))*100))
                time.sleep(0.1)
                
        self.progress_window.setValue(100)


    def displayFileErrorDialog(self, message, title):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setDetailedText(self.e.ErrorMessage())
        msg.exec_()

    def view_image(self):
            self.ref_image_data = vtk.vtkImageData()
            self.ref_image_data3D = vtk.vtkImageData()
            self.image_info = dict()
            ImageDataCreator.createImageData(self, self.image[0], [self.ref_image_data, self.ref_image_data3D], self.image_info, True, partial(self.save_image_info, "ref"))
    
    def load_corr_image(self):
        self.corr_image_data = vtk.vtkImageData()
        ImageDataCreator.createImageData(self, self.image[1], [self.corr_image_data], self.image_info, True, partial(self.save_image_info, "cor"))

    def save_image_info(self, image_type):
        if 'numpy_file' in self.image_info:
            image_file = [self.image_info['numpy_file']]
            if 'vol_bit_depth' in self.image_info:
                self.vol_bit_depth = self.image_info['vol_bit_depth']
            
            # if not 'temp' in image_file:
            #     image_file = image_file[len(working_directory):]
            
            if image_type == "ref":
                self.dvc_input_image[0] = image_file
            else:
                self.dvc_input_image[1] = image_file
        else:
            self.dvc_input_image = self.image
        
        if image_type == "ref":
            self.visualise()
        # else:
        #     print("The image files:", self.image)
        #     print("DVC input:", self.dvc_input_image)

    def visualise(self):
        if self.ref_image_data is None:
            #self.progress_window.setValue(100)
            self.warningDialog('Unable to load image.','Error', 'Image is in incorrect format to perform run of DVC. Please load a different image.')
            return

        time.sleep(0.1)

        self.create_progress_window("Loading", "Loading Image")
        self.progress_window.setValue(10)

        #print("2D")
        self.vis_widget_2D.setImageData(self.ref_image_data) 
        self.vis_widget_2D.displayImageData()
        #print("3D")
        print(50)
        self.progress_window.setValue(50)
        self.vis_widget_3D.setImageData(self.ref_image_data3D)
        self.vis_widget_3D.displayImageData()

        self.progress_window.setValue(80)

        self.link2D3D = vlink.ViewerLinker(self.vis_widget_2D.frame.viewer,
                                           self.vis_widget_3D.frame.viewer)
        self.link2D3D.setLinkPan(False)
        self.link2D3D.setLinkZoom(False)
        self.link2D3D.setLinkWindowLevel(True)
        self.link2D3D.setLinkSlice(True)
        self.link2D3D.enable()

        self.vis_widget_2D.frame.viewer.style.AddObserver("MouseWheelForwardEvent",
                                                self.UpdateClippingPlanes, 1.9)
        self.vis_widget_2D.frame.viewer.style.AddObserver("MouseWheelBackwardEvent",
                                                self.UpdateClippingPlanes, 1.9)

        self.progress_window.setValue(100)
        
        time.sleep(0.1)
        self.load_corr_image()

        if(self.mask_load):
            self.MaskWorker("load session")

        if hasattr(self, 'no_mask_pc_load'):        
            if(self.no_mask_pc_load):
                self.PointCloudWorker("load pointcloud file")
                self.pointCloudLoaded = True
                self.no_mask_pc_load = False

        if(self.reg_load):
            #Image Reg:
            
                self.displayViewer(registration_open = True)
                #first we need to set the z slice -> go to slice self.config['point0'][2]
                self.createPoint0(self.config['point0'])
                rp = self.registration_parameters
                rp['translate_X_entry'].setText(str(self.config['reg_translation'][0]*-1))
                rp['translate_Y_entry'].setText(str(self.config['reg_translation'][1]*-1))
                rp['translate_Z_entry'].setText(str(self.config['reg_translation'][2]*-1))
                self.translate = vtk.vtkImageTranslateExtent()
                self.translate.SetTranslation(self.config['reg_translation'])
                self.registration_parameters['register_on_selection_check'].setChecked(self.config['reg_sel'] )
                self.registration_parameters['register_on_selection_check'].setEnabled(True )
                self.registration_parameters['registration_box_size_entry'].setValue(self.config['reg_sel_size'])
                self.registration_parameters['registration_box_size_entry'].setEnabled(True)
                self.displayRegistrationSelection()
                self.displayViewer(registration_open = False)
                self.reg_load = False

        #TODO: Need to be able to load pointcloud w/o loading mask

    def create_progress_window(self, title, text, max = 100, cancel = None):
        self.progress_window = QProgressDialog(text, "Cancel", 0,max, self, QtCore.Qt.Window) 
        self.progress_window.setWindowTitle(title)
        
        self.progress_window.setWindowModality(QtCore.Qt.ApplicationModal) #This means the other windows can't be used while this is open
        self.progress_window.setMinimumDuration(0.01)
        self.progress_window.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        self.progress_window.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)
        if cancel is None:
            self.progress_window.setCancelButton(None)
        else:
            self.progress_window.canceled.connect(cancel)


    def setup2DPointCloudPipeline(self):
        bpcpoints = cilClipPolyDataBetweenPlanes()
        # save reference
        
        #polydata_masker = self.polydata_masker
        bpcpoints.SetInputConnection(self.polydata_masker.GetOutputPort()) 
        #bpcpoints.SetInputData(self.polydata_masker.GetOutputDataObject(0))
        bpcpoints.SetPlaneOriginAbove((0,0,3))
        bpcpoints.SetPlaneOriginBelow((0,0,1))
        bpcpoints.SetPlaneNormalAbove((0,0,1))
        bpcpoints.SetPlaneNormalBelow((0,0,-1))
        bpcpoints.Update()
        self.bpcpoints = bpcpoints

        mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.pointmapper = mapper

        #print(type(self.polydata_masker.GetOutputPort()))

        #maybe need:
        #mapper.SetInputConnection(self.polydata_masker.GetOutputPort()) #nothing
        #mapper.SetInputData(self.bpcpoints.GetOutputDataObject(0)) #does nothing
        
       # mapper.SetInputData(self.polydata_masker.GetOutputDataObject(0))


        mapper.SetInputConnection(bpcpoints.GetOutputPort()) #does nothing

        #print(type(bpcpoints.GetOutputPort()))

        # create an actor for the points as point
        actor = vtk.vtkLODActor()
        # save reference
        self.pointactor = actor
        actor.SetMapper(mapper)
        actor.GetProperty().SetPointSize(3)
        actor.GetProperty().SetColor(0., 1., 1.)
        actor.VisibilityOn()
        actor.AddObserver("ModifiedEvent", lambda: print ("point actor modified"))

        # create a mapper/actor for the point cloud with a CubeSource and with vtkGlyph3D
        # which copies oriented and scaled glyph geometry to every input point

        subv_glyph = vtk.vtkGlyph3D()
        #subv_glyph = vtk.vtkGlyph2D()

        # save reference
        self.cubesphere = subv_glyph
        subv_glyph.SetScaleFactor(1.)
        
        v = self.vis_widget_2D.frame.viewer
        spacing = v.img3D.GetSpacing()
        #print(spacing)
        #spacing = [1.0,1.0,1.0]


        # pointCloud = self.pointCloud
        radius = self.pointCloud_radius

        #radius=1

        # # Spheres may be a bit complex to visualise if the spacing of the image is not homogeneous
        sphere_source = vtk.vtkSphereSource()
        # # save reference
        self.sphere_source = sphere_source
        sphere_source.SetRadius(self.pointCloud_radius * v.img3D.GetSpacing()[0])
        sphere_source.SetThetaResolution(12)
        sphere_source.SetPhiResolution(12)

        # # Cube source
        polygon = False
        
        if polygon:
            cube_source = vtk.vtkRegularPolygonSource()
            cube_source.SetNumberOfSides(4)
            cube_source.GeneratePolygonOn()
        #cube_source = vtk.vtk
        # # save reference

        else:
            cube_source = vtk.vtkCubeSource()
            cube_source.SetXLength(v.img3D.GetSpacing()[0]*self.pointCloud_radius)
            cube_source.SetYLength(v.img3D.GetSpacing()[1]*self.pointCloud_radius)
            cube_source.SetZLength(v.img3D.GetSpacing()[2]*self.pointCloud_radius)
            self.cube_source = cube_source
            rotate= self.pointCloud_rotation
            print("Rotate", self.pointCloud_rotation)
            transform = vtk.vtkTransform()
            # save reference
            self.transform = transform
            # rotate around the center of the image data
            transform.RotateX(self.pointCloud_rotation[0])
            transform.RotateY(self.pointCloud_rotation[1])
            transform.RotateZ(self.pointCloud_rotation[2])
            t_filter = vtk.vtkTransformPolyDataFilter()
            t_filter.SetTransform(self.transform)
            t_filter.SetInputConnection(self.cube_source.GetOutputPort())
            self.cube_transform_filter = t_filter


        #cube_source.SetRadius(spacing[0])
        
        self.cube_source = cube_source
        # # clip between planes
        bpcvolume = cilClipPolyDataBetweenPlanes()
        # # save reference
        self.bpcvolume = bpcvolume
        bpcvolume.SetInputConnection(subv_glyph.GetOutputPort())
        bpcvolume.SetPlaneOriginAbove((0,0,3))
        bpcvolume.SetPlaneOriginBelow((0,0,1))
        bpcvolume.SetPlaneNormalAbove((0,0,1))
        bpcvolume.SetPlaneNormalBelow((0,0,-1))

        #bpcvolume.Update()


        # # mapper for the glyphs
        sphere_mapper = vtk.vtkPolyDataMapper()
        # # save reference
        self.cubesphere_mapper = sphere_mapper
        # # sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )
        sphere_mapper.SetInputConnection( bpcvolume.GetOutputPort() )
        

        subv_glyph.SetInputConnection( self.polydata_masker.GetOutputPort() )


        if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
            print("CUBE")
            self.glyph_source = t_filter #self.cube_source
        else:
            print("SPHERE")
            self.glyph_source = self.sphere_source
        
        subv_glyph.SetSourceConnection( self.glyph_source.GetOutputPort() )
        
        # # subv_glyph.SetSourceConnection( sphere_source.GetOutputPort() )
        # # subv_glyph.SetSourceConnection( cube_source.GetOutputPort() )

        subv_glyph.SetVectorModeToUseNormal()

        # # actor for the glyphs
        sphere_actor = vtk.vtkActor()
        # # save reference
        self.cubesphere_actor = sphere_actor
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1, 0, 0)
        #sphere_actor.GetProperty().SetColor(1, .2, .2)
        sphere_actor.GetProperty().SetOpacity(0.5)
        #sphere_actor.GetProperty().SetRepresentationToWireframe()
        sphere_actor.GetProperty().SetLineWidth(2.0)
        sphere_actor.GetProperty().SetEdgeVisibility(True)
        sphere_actor.GetProperty().SetEdgeColor(1, .2, .2)
        # sphere_actor.SetOrigin(self.cube_source.GetCenter())
        # sphere_actor.RotateZ(rotate[2])

        #self.vtkWidget needs to become self.parent.vis_widget_.frame

        #actor = 'PointCloud' in self.vis_widget_2D.frame.viewer.actors
        #actor = 'PointCloud' in self.vis_widget_2D.frame.viewer.actors
        self.vis_widget_2D.frame.viewer.AddActor(actor, 'PointCloud')
        self.vis_widget_2D.frame.viewer.AddActor(sphere_actor, 'PointCloudFrame')
        
        if not hasattr(self, 'actors2D'):
            self.actors_2D = {}
        
        self.actors_2D['pointcloud'] = actor
        self.actors_2D ['pointcloud_frame'] = sphere_actor

    def setup3DPointCloudPipeline(self):
        #polydata_masker = self.polydata_masker

        mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.pointmapper = mapper
        # mapper.SetInputConnection(bpc.GetOutputPort())
        mapper.SetInputConnection(self.polydata_masker.GetOutputPort())
        # mapper.SetInputConnection(pointCloud.GetOutputPort())
        #mapper.SetInputData(self.polydata_masker.GetOutputDataObject(0))
        

        # create an actor for the points as point
        actor = vtk.vtkLODActor()
        # save reference
        self.pointactor = actor
        actor.SetMapper(mapper)
        actor.GetProperty().SetPointSize(3)
        actor.GetProperty().SetColor(1, .2, .2)
        actor.VisibilityOn()


        # create a mapper/actor for the point cloud with a CubeSource and with vtkGlyph3D
        # which copies oriented and scaled glyph geometry to every input point

        # get reference
        subv_glyph = self.cubesphere

        # # Spheres may be a bit complex to visualise if the spacing of the image is not homogeneous
        # # get reference
        sphere_source = self.sphere_source

        # # get reference
        cube_source = self.cube_source

        # # mapper for the glyphs
        sphere_mapper = vtk.vtkPolyDataMapper()
        # # save reference
        self.cubesphere_mapper3D = sphere_mapper
        sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )

        subv_glyph.SetInputConnection( self.polydata_masker.GetOutputPort() )
        if self.pointCloud_shape == 'cube':
            subv_glyph.SetSourceConnection( cube_source.GetOutputPort() )
        else:
            print("SPHERE")
            subv_glyph.SetSourceConnection( sphere_source.GetOutputPort() )
        subv_glyph.Modified()

        # # actor for the glyphs
        sphere_actor = vtk.vtkActor()
        # # save reference
        self.cubesphere_actor3D = sphere_actor
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1, 0, 0)
        sphere_actor.GetProperty().SetOpacity(0.5)
        #sphere_actor.GetProperty().SetRepresentationToWireframe() #wireframe
        # sphere_actor.GetProperty().SetLineWidth(2.0)
        # sphere_actor.GetProperty().SetEdgeVisibility(True)
        # sphere_actor.GetProperty().SetEdgeColor(0,0,0)


        self.vis_widget_3D.frame.viewer.getRenderer().AddActor(actor)
        self.vis_widget_3D.frame.viewer.getRenderer().AddActor(sphere_actor)

        if not hasattr(self, 'actors3D'):
            self.actors_3D = {}
        
        self.actors_3D['pointcloud'] = actor
        self.actors_3D ['pointcloud_frame'] = sphere_actor

#Registration Panel:
    def CreateRegistrationPanel(self):
        '''Create the Registration Dockable Widget'''

        #self.treeWidgetInitialElements = []
        #self.treeWidgetUpdateElements = []

        self.registration_panel = generateUIDockParameters(self, '2 - Manual Registration')
        dockWidget = self.registration_panel[0]
        groupBox = self.registration_panel[5]
        groupBox.setTitle('Registration Parameters')
        formLayout = self.registration_panel[6]

        # Create validation rule for text entry
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        rp = {}

        dockWidget.visibilityChanged.connect(self.displayViewer)
        
        # Button select point0
        rp['select_point_zero'] = QPushButton(groupBox)
        rp['select_point_zero'].setText("Select Point 0")
        rp['select_point_zero'].setEnabled(True)
        rp['select_point_zero'].setCheckable(True)
        rp['select_point_zero'].setChecked(False)
        rp['select_point_zero'].clicked.connect( lambda: self.selectPointZero() )
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['select_point_zero'])
        widgetno += 1
        # Point0 Location
        rp['point_zero_label'] = QLabel(groupBox)
        rp['point_zero_label'].setText("Point Zero Location")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['point_zero_label'])
        rp['point_zero_entry']= QLineEdit(groupBox)
        rp['point_zero_entry'].setEnabled(False)
        rp['point_zero_entry'].setText("")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['point_zero_entry'])
        widgetno += 1
        # Put the viewer at the slice where point 0 is
        # Button select point0
        rp['goto_point_zero'] = QPushButton(groupBox)
        rp['goto_point_zero'].setText("Center on Point 0")
        rp['goto_point_zero'].setEnabled(True)
        rp['goto_point_zero'].setCheckable(False)
        rp['goto_point_zero'].setChecked(False)
        rp['goto_point_zero'].clicked.connect( lambda: self.centerOnPointZero() )
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['goto_point_zero'])
        widgetno += 1
        
        separators = []
        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1
        # Add should extend checkbox
        rp['register_on_selection_check'] = QCheckBox(groupBox)
        rp['register_on_selection_check'].setText("Register on Selection")
        rp['register_on_selection_check'].setEnabled(False)
        rp['register_on_selection_check'].setChecked(False)
        rp['register_on_selection_check'].stateChanged.connect( self.displayRegistrationSelection )

        formLayout.setWidget(widgetno,QFormLayout.FieldRole, rp['register_on_selection_check'])
        widgetno += 1
        # Registration Box
        rp['registration_box_size_label'] = QLabel(groupBox)
        rp['registration_box_size_label'].setText("Registration Box Size")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['registration_box_size_label'])
        # rp['registration_box_size_entry']= QLineEdit(groupBox)
        # rp['registration_box_size_entry'].setValidator(validatorint)
        # rp['registration_box_size_entry'].setText("10")
        # rp['registration_box_size_entry'].setEnabled(False)
        # rp['registration_box_size_entry'].returnPressed.connect(self.displayRegistrationSelection)
        rp['registration_box_size_entry'] = QSpinBox(groupBox)
        rp['registration_box_size_entry'].setSingleStep(1)
        rp['registration_box_size_entry'].setValue(10)
        rp['registration_box_size_entry'].setMaximum(2000)
        rp['registration_box_size_entry'].setEnabled(False)
        rp['registration_box_size_entry'].valueChanged.connect(self.displayRegistrationSelection)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['registration_box_size_entry'])
        widgetno += 1


        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1
        # Translate X field
        rp['translate_X_label'] = QLabel(groupBox)
        rp['translate_X_label'].setText("Translate X")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['translate_X_label'])
        rp['translate_X_entry']= QLineEdit(groupBox)
        rp['translate_X_entry'].setValidator(validatorint)
        rp['translate_X_entry'].setText("0")
        rp['translate_X_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['translate_X_entry'])
        widgetno += 1
        # Translate Y field
        rp['translate_Y_label'] = QLabel(groupBox)
        rp['translate_Y_label'].setText("Translate Y")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['translate_Y_label'])
        rp['translate_Y_entry']= QLineEdit(groupBox)
        rp['translate_Y_entry'].setValidator(validatorint)
        rp['translate_Y_entry'].setText("0")
        rp['translate_Y_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['translate_Y_entry'])
        widgetno += 1
        # Translate Z field
        rp['translate_Z_label'] = QLabel(groupBox)
        rp['translate_Z_label'].setText("Translate Z")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['translate_Z_label'])
        rp['translate_Z_entry']= QLineEdit(groupBox)
        rp['translate_Z_entry'].setValidator(validatorint)
        rp['translate_Z_entry'].setText("0")
        rp['translate_Z_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['translate_Z_entry'])
        widgetno += 1

        # Add submit button
        rp['start_registration_button'] = QPushButton(groupBox)
        rp['start_registration_button'].setText("Start Registration")
        rp['start_registration_button'].setCheckable(True)
        rp['start_registration_button'].setEnabled(True)
        rp['start_registration_button'].clicked.connect(self.manualRegistration)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['start_registration_button'])
        widgetno += 1

        # rp['start_registration_button'].stateChanged.connect(lambda: rp['start_registration_button'].setText("Stop Registration") \
        #                                          if rp['start_registration_button'].isChecked() \
        #                                          else rp['start_registration_button'].setText("Start Registration"))


        # Add elements to layout
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)
        # save to instance
        self.registration_parameters = rp

    def displayViewer(self,registration_open):
        if hasattr(self, 'ref_image_data') and hasattr(self, 'corr_image_data'):
            #check for image data else do nothing
            if registration_open:
                self.help_label.setText(self.help_text[1])
                if not hasattr(self, 'vis_widget_reg'):
                    self.vis_widget_reg = VisualisationWidget(self, viewer2D)
                    dock_reg = QDockWidget("Image Registration",self.VisualisationWindow)
                    dock_reg.setObjectName("2DRegView")
                    dock_reg.setWidget(self.vis_widget_reg)
                    self.VisualisationWindow.addDockWidget(Qt.TopDockWidgetArea,dock_reg)
                    ref_image_copy = vtk.vtkImageData()
                    ref_image_copy.DeepCopy(self.ref_image_data)
                    self.vis_widget_reg.setImageData(ref_image_copy)
                    self.vis_widget_reg.displayImageData()
                    #self.tabifyDockWidget(self.viewer2D_dock,dock_reg) #breaks
                    self.viewer2D_dock.setVisible(False)
                    self.dock_reg = dock_reg
                    windowHeight = self.size().height()

                else:
                    self.dock_reg.setVisible(True)
                    self.viewer2D_dock.setVisible(False)

            else:
                if (hasattr(self, 'dock_reg')):
                    self.dock_reg.setVisible(False)
                    self.viewer2D_dock.setVisible(True)


    def manualRegistration(self):
        if hasattr(self, 'vis_widget_reg'):
            rp = self.registration_parameters
            v = self.vis_widget_reg.frame.viewer
            if rp['start_registration_button'].isChecked():
                print ("Start Registration Checked")
                rp['register_on_selection_check'].setEnabled(True)
                rp['start_registration_button'].setText("Stop Registration")

                # setup the appropriate stuff to run the registration
                print("translate")
                if not hasattr(self, 'translate'):
                    translate = vtk.vtkImageTranslateExtent()
                    translate.SetTranslation(0,0,0)
                    self.translate = translate
                elif self.translate is None:
                    translate = vtk.vtkImageTranslateExtent()
                    translate.SetTranslation(0,0,0)
                    self.translate = translate

                self.reg_worker = Worker(self.registerImages)
                self.reg_worker.signals.finished.connect(self.reg_viewer_update) 
                self.create_progress_window("Loading", "Registering Image")
                self.reg_worker.signals.progress.connect(self.progress)
                self.progress_window.setValue(5)
                self.threadpool.start(self.reg_worker)  
            
            else:
                print ("Start Registration Unchecked")
                rp['start_registration_button'].setText("Start Registration")
                # hide registration box
                #if hasattr(self, 'registration_box'):
                    #self.registration_box['actor'].VisibilityOff()
                #v.setInput3DData(self.reader.GetOutput())
                v.setInput3DData(self.ref_image_data) #may need to make copy
                v.style.UpdatePipeline()


    def resetRegistration(self):
        if hasattr(self, 'vis_widget_reg'):
            self.displayViewer(False)

            del self.vis_widget_reg
            self.translate = None

            rp = self.registration_parameters
            rp['select_point_zero'].setChecked(False)
            rp['translate_X_entry'].setText("0")
            rp['translate_Y_entry'].setText("0")
            rp['translate_Z_entry'].setText("0")
            rp['goto_point_zero'].setCheckable(False)
            rp['goto_point_zero'].setChecked(False)
            rp['point_zero_entry'].setText("")

            if hasattr(self, 'point0_loc'):
                del self.point0_loc
        if hasattr(self, 'vis_widget_reg'):
            print("Still exists")



    def registerImages(self, progress_callback = None):
        progress_callback.emit(10)
        rp = self.registration_parameters
        v = self.vis_widget_reg.frame.viewer
        if rp['register_on_selection_check'].isChecked():
                print ("Extracting selection")
                # get the selected ROI
                voi = vtk.vtkExtractVOI()
                ref_copy = self.ref_image_data #vtk.vtkImageData()
                #ref_copy.DeepCopy(self.ref_image_data)
                print ("image 1", self.ref_image_data.GetDimensions())
                voi.SetInputData(ref_copy) #ref image data
                # box around the point0
                p0 = eval(rp['point_zero_entry'].text())
                bbox = rp['registration_box_size_entry'].value()
                extent = [ p0[0] - bbox//2, p0[0] + bbox//2, 
                           p0[1] - bbox//2, p0[1] + bbox//2, 
                           p0[2] - bbox//2, p0[2] + bbox//2]

                extent = [ el if el > 0 else 0 for i,el in enumerate(extent) ]
                # spacing = self.reader.GetOutput().GetSpacing()
                # extent[0] /= spacing[0]
                # extent[1] /= spacing[0]
                # extent[2] /= spacing[1]
                # extent[3] /= spacing[1]
                # extent[4] /= spacing[2]
                # extent[5] /= spacing[2]
                print ("Current roi", extent)
                
                voi.SetVOI(*extent)
                voi.Update()
                print ("Done")

                # copy the data to be registered if selection 
                data1 = vtk.vtkImageData()
                data1.DeepCopy(voi.GetOutput())
                progress_callback.emit(15)

                # voi_2 = vtk.vtkExtractVOI()
                # voi_2.SetVOI(*extent)
                
                print ("Reading image 2")
                print ("image 2", self.corr_image_data.GetDimensions())
                corr_copy = self.corr_image_data #vtk.vtkImageData()
                #corr_copy.DeepCopy(self.corr_image_data)
                progress_callback.emit(20)
                
                # copy the data to be registered if selection 
                #voi.SetInputConnection(self.correlate_reader.GetOutputPort())
                voi.SetInputData(corr_copy)
                
                print ("Extracting selection")
                voi.Update()
                progress_callback.emit(30)
                data2 = vtk.vtkImageData()
                data2.DeepCopy(voi.GetOutput())
                progress_callback.emit(35)

                #self.translate.SetInputData(data2)
                self.translate.SetInputData(data2)
                progress_callback.emit(40)
            
                print ("clearing memory")
                del voi
                #del voi_2
                # fname = self.correlate_reader.GetFileName() #filename of corr image
                # print ("filename", fname, type(self.correlate_reader))
                # cr = type(self.correlate_reader)()
                # cr.SetFileName(fname)
                # self.correlate_reader = cr
                print ("clearing memory done")

        else:
                
                print ("Registration on whole image")
                #data1 = vtk.vtkImageData()
                #data1.DeepCopy(self.ref_image_data)
                data1 = self.ref_image_data
                #data2 = vtk.vtkImageData()
                #data2.DeepCopy(self.corr_image_data)
                data2 = self.corr_image_data
                #self.translate.SetInputData(data2)
                self.translate.SetInputData(data2)
                print ("clearing memory")
                # fname = self.correlate_reader.GetFileName()
                # print ("filename", fname, type(self.correlate_reader))
                # cr = type(self.correlate_reader)()
                # cr.SetFileName(fname)
                # self.correlate_reader = cr
                print ("clearing memory done")

                #data2 = self.correlate_reader.GetOutput()
                #translate.SetInputConnection(self.correlate_reader.GetOutputPort())
                print ("Reading image 2")

        print ("Done")

        
        #voi = reader
        self.translate.Update()
        progress_callback.emit(45)

        v.style.AddObserver('KeyPressEvent', self.OnKeyPressEventForRegistration, 0.5)

        # print ("out of the reader", reader.GetOutput())

        cast1 = vtk.vtkImageCast()
        cast2 = vtk.vtkImageCast()
        cast1.SetInputData(data1)
        cast1.SetOutputScalarTypeToFloat()
        cast2.SetInputConnection(self.translate.GetOutputPort())
        cast2.SetOutputScalarTypeToFloat()
        progress_callback.emit(50)
        
        subtract = vtk.vtkImageMathematics()
        subtract.SetOperationToSubtract()
        subtract.SetInputConnection(1,cast1.GetOutputPort())
        subtract.SetInputConnection(0,cast2.GetOutputPort())
        progress_callback.emit(70)
        
        subtract.Update()
        progress_callback.emit(80)
        
        print ("subtract type", subtract.GetOutput().GetScalarTypeAsString(), subtract.GetOutput().GetDimensions())
        
        stats = vtk.vtkImageHistogramStatistics()
        stats.SetInputConnection(subtract.GetOutputPort())
        stats.Update()
        progress_callback.emit(90)
        print ("stats ", stats.GetMinimum(), stats.GetMaximum(), stats.GetMean(), stats.GetMedian())
        self.subtract = subtract
        self.cast = [cast1, cast2]
        progress_callback.emit(95)

    def reg_viewer_update(self, type = None):
        print("Reg viewer update")
        # update the current translation on the interface:
        rp = self.registration_parameters
        rp['translate_X_entry'].setText(str(self.translate.GetTranslation()[0]*-1))
        rp['translate_Y_entry'].setText(str(self.translate.GetTranslation()[1]*-1))
        rp['translate_Z_entry'].setText(str(self.translate.GetTranslation()[2]*-1))

        #update the viewer:
        v = self.vis_widget_reg.frame.viewer
        v.setInputData(self.subtract.GetOutput())
        # trigger visualisation by programmatically click 'z'
        # interactor = v.getInteractor()
        # interactor.SetKeyCode("z")
        # v.style.OnKeyPress(interactor, 'KeyPressEvent')
        v.style.UpdatePipeline()
        #v.startRenderLoop()

        if not rp['register_on_selection_check'].isChecked():
            rp['registration_box_size_entry'].setValue(rp['registration_box_size_entry'].maximum())

        if (self.progress_window.isVisible()):
            self.progress_window.setValue(100)
            self.progress_window.close()

    def OnKeyPressEventForRegistration(self, interactor, event):
        key_code = interactor.GetKeyCode()
        print('OnKeyPressEventForRegistration', key_code) #,event)
        rp = self.registration_parameters
        if key_code in ['j','n','b','m'] and \
            rp['start_registration_button'].isChecked():
            self.translate_worker = Worker(self.translate_image_reg, key_code, event)
            self.translate_worker.signals.finished.connect(self.reg_viewer_update)

            # produces windows which don't close if buttons pressed in quick succession
            # if rp['registration_box_size_entry'].value() >1000:
            #     self.create_progress_window("Loading", "Translating Image")
            #     self.translate_worker.signals.progress.connect(self.progress)
            #self.progress_window.setValue(10)
            
            self.threadpool.start(self.translate_worker)  
        
    def translate_image_reg(self,key_code, event, progress_callback):
        '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''
        progress_callback.emit(10)
        rp = self.registration_parameters
        v = self.vis_widget_reg.frame.viewer
        trans = list(self.translate.GetTranslation())
        print("Previous translation: ", trans)
        orientation = v.style.GetSliceOrientation()
        ij = [0,1]
        if orientation == SLICE_ORIENTATION_XY:
            ij = [0,1]
        elif orientation == SLICE_ORIENTATION_XZ:
            ij = [0,2]
        elif orientation == SLICE_ORIENTATION_YZ:
            ij = [1,2]
        if key_code == "j":
            if trans[ij[1]] < int(rp['registration_box_size_entry'].value()):
                trans[ij[1]] += 1
        elif key_code == "n":
            if trans[ij[1]] > int(rp['registration_box_size_entry'].value())*-1:
                trans[ij[1]] -= 1
        elif key_code == "b":
            if trans[ij[0]] > int(rp['registration_box_size_entry'].value())*-1:
                trans[ij[0]] -= 1
        elif key_code == "m":
            if trans[ij[0]] < int(rp['registration_box_size_entry'].value()):
                trans[ij[0]] += 1
        self.translate.SetTranslation(*trans)
        self.translate.Update()
        self.subtract.Update()
        print ("Translation", trans)
        
        # v.setInputData(subtract.GetOutput())
        # print ("OnKeyPressEventForRegistration", v.img3D.GetDimensions(), subtract.GetOutput().GetDimensions())
        # v.style.UpdatePipeline()
        # trigger visualisation by programmatically click 'z'
        # interactor = v.getInteractor()
        # interactor.SetKeyCode("z")
        # v.style.OnKeyPress(interactor, 'KeyPressEvent')
            

    def selectPointZero(self):
        if hasattr(self, 'ref_image_data') and hasattr(self, 'corr_image_data'):
                       
            rp = self.registration_parameters
            v = self.vis_widget_reg.frame.viewer
            rp['register_on_selection_check'].setEnabled(True)
            if rp['select_point_zero'].isChecked():
                v.style.AddObserver('LeftButtonPressEvent', self.OnLeftButtonPressEventForPointZero, 0.5)
                # should find a way to not show this again
                self.warningDialog(
                    window_title='Select Point 0',
                    message='Select point 0 by SHIFT-Left Click on the Image'
                )
                rp['select_point_zero'].setText('Selecting point 0')
            else:
                rp['select_point_zero'].setText('Select Point 0')
        
        else:
            self.warningDialog("Load an image on the viewer first.", "Error")
        
    def OnLeftButtonPressEventForPointZero(self, interactor, event):
            print('OnLeftButtonPressEventForPointZero', event)
            v = self.vis_widget_reg.frame.viewer
            shift = interactor.GetShiftKey()          
            rp = self.registration_parameters
            
            if shift and rp['select_point_zero'].isChecked():
                print ("Shift pressed", shift)
                position = interactor.GetEventPosition()
                #vox = v.style.display2world(position)
                p0l = v.style.display2imageCoordinate(position)[:-1]               
                self.createPoint0(p0l)

    def createPoint0(self, p0l):
        v = self.vis_widget_reg.frame.viewer
        spacing = v.img3D.GetSpacing()
        origin = v.img3D.GetOrigin()
        p0 = [ el * spacing[i] + origin[i] for i,el in enumerate(p0l) ]
        point0actor = 'Point0' in v.actors
        rp = self.registration_parameters
        vox = p0
        print ("vox ", vox, 'p0', p0)
        bbox = rp['registration_box_size_entry'].value()
        extent = [ p0[0] - int( bbox * spacing[0] / 2 ), p0[0] + int( bbox * spacing[0] / 2 ), 
                p0[1] - int( bbox * spacing[1] / 2 ), p0[1] + int( bbox * spacing[1] / 2 ), 
                p0[2] - int( bbox * spacing[2] / 2 ), p0[2] + int( bbox * spacing[2] / 2 )]
        if not point0actor:
            #point0 = vtk.vtkSphereSource()
            # calculate radius 
            #point0.SetRadius(3)
            #point0.SetCenter(*vox)
            #point0.Update()
            point0 = vtk.vtkCursor3D()
            point0.SetModelBounds(-10 + vox[0], 10 + vox[0], -10 + vox[1], 10 + vox[1], -10 + vox[2], 10 + vox[2])
            point0.SetFocalPoint(*vox)
            point0.AllOff()
            point0.AxesOn()
            point0.OutlineOn()
            #point0.TranslationModeOn()
            point0.Update()
            point0Mapper = vtk.vtkPolyDataMapper()
            point0Mapper.SetInputConnection(point0.GetOutputPort())
            point0Actor = vtk.vtkLODActor()
            point0Actor.SetMapper(point0Mapper)
            point0Actor.GetProperty().SetColor(1.,0.,0.)
            point0Actor.GetProperty().SetLineWidth(2.0)
            v.AddActor(point0Actor, 'Point0')
            self.vis_widget_3D.frame.viewer.getRenderer().AddActor(point0Actor)
            self.vis_widget_2D.frame.viewer.AddActor(point0Actor)
            self.point0 = [ point0 , point0Mapper, point0Actor ] 
        else:
            self.point0[0].SetFocalPoint(*vox)
            self.point0[0].SetModelBounds(-10 + vox[0], 10 + vox[0], -10 + vox[1], 10 + vox[1], -10 + vox[2], 10 + vox[2])
            self.point0[0].Update()
        rp = self.registration_parameters
        rp['point_zero_entry'].setText(str(p0l))
        self.point0_loc = p0
        print("Finished")

    def centerOnPointZero(self):
        '''Centers the viewing slice where Point 0 is'''
        if hasattr(self, 'vis_widget_reg'):
            rp = self.registration_parameters
            v = self.vis_widget_reg.frame.viewer
            #v3 = 
            point0 = rp['point_zero_entry'].text()
            #point0 = tuple(map(int, point0.split(', '))) 
            if point0 !="": 
                point0= eval(point0)
            if isinstance (point0, tuple) or isinstance(point0, list):
                print("Tuple")
                orientation = v.style.GetSliceOrientation()
                gotoslice = point0[orientation]
                v.style.SetActiveSlice( gotoslice )
                v.style.UpdatePipeline(True)
                self.displayRegistrationSelection()
            else:
                self.warningDialog("Choose a Point 0 first.", "Error")


    def displayRegistrationSelection(self):
        if hasattr(self, 'vis_widget_reg'):
            print ("displayRegistrationSelection")
            rp = self.registration_parameters
            rp['registration_box_size_entry'].setEnabled( rp['register_on_selection_check'].isChecked() )
            v = self.vis_widget_reg.frame.viewer
            rbdisplay = 'RegistrationBox' in v.actors
            if rp['register_on_selection_check'].isChecked():
                spacing = v.img3D.GetSpacing()
                origin = v.img3D.GetOrigin()
                p0 = [ el * spacing[i] + origin[i] for i,el in enumerate(eval(rp['point_zero_entry'].text())) ]
                bbox = rp['registration_box_size_entry'].value()
                extent = [ p0[0] - int( bbox * spacing[0] / 2 ), p0[0] + int( bbox * spacing[0] / 2 ), 
                        p0[1] - int( bbox * spacing[1] / 2 ), p0[1] + int( bbox * spacing[1] / 2 ), 
                        p0[2] - int( bbox * spacing[2] / 2 ), p0[2] + int( bbox * spacing[2] / 2 )]
                print ("registration_box_extent", extent)
                if not rbdisplay:
                    point0 = vtk.vtkCursor3D()
                    point0.SetModelBounds(*extent)
                    point0.SetFocalPoint(*p0)
                    point0.AllOff()
                    point0.OutlineOn()
                    #point0.TranslationModeOn()
                    point0.Update()
                    point0Mapper = vtk.vtkPolyDataMapper()
                    point0Mapper.SetInputConnection(point0.GetOutputPort())
                    point0Actor = vtk.vtkLODActor()
                    point0Actor.SetMapper(point0Mapper)
                    point0Actor.GetProperty().SetColor(0.,.5,.5)
                    point0Actor.GetProperty().SetLineWidth(2.0)
                    v.AddActor(point0Actor, 'RegistrationBox')
                    self.vis_widget_3D.frame.viewer.getRenderer().AddActor(point0Actor)
                    self.vis_widget_2D.frame.viewer.AddActor(point0Actor)
                    self.registration_box = {'source': point0 , 'mapper': point0Mapper, 
                                            'actor': point0Actor }
                    v.style.UpdatePipeline()
                else:
                    self.registration_box['actor'].VisibilityOn()
                    bb = self.registration_box['source']
                    bb.SetModelBounds(*extent)
                    bb.SetFocalPoint(*p0)
                    v.style.UpdatePipeline()
            else:
                if rbdisplay:
                    # hide actor
                    self.registration_box['actor'].VisibilityOff()
                    v.style.UpdatePipeline()


#Mask Panel:
    def CreateMaskPanel(self):
            self.mask_panel = generateUIDockParameters(self,'3 - Mask')
            dockWidget = self.mask_panel[0]
            dockWidget.setObjectName("CreateMaskPanel")
            groupBox = self.mask_panel[5]
            groupBox.setTitle('Mask Parameters')
            formLayout = self.mask_panel[6]

            # Create validation rule for text entry
            validator = QtGui.QDoubleValidator()
            validator.setDecimals(2)
            validatorint = QtGui.QIntValidator()

            #Need to move this to when loading session bc here the sesh hasn't been loaded.

            #So create empty dropdwon in this section

            dockWidget.visibilityChanged.connect(partial(self.displayHelp, panel_no = 2))

            mp_widgets = {}
            self.mask_parameters = mp_widgets

            widgetno = 1

            mp_widgets['masksList'] = QComboBox(groupBox)
            mp_widgets['masksList'].setEnabled(False)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['masksList'])
            widgetno += 1

            mp_widgets['loadButton'] = QPushButton(groupBox)
            mp_widgets['loadButton'].setText("Load Saved Mask")
            mp_widgets['loadButton'].clicked.connect(lambda: self.MaskWorker("load mask"))
            mp_widgets['loadButton'].setEnabled(False)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['loadButton'])
            widgetno += 1

            mp_widgets['mask_browse'] = QPushButton(groupBox)
            mp_widgets['mask_browse'].setText("Load Mask from File")
            mp_widgets['mask_browse'].clicked.connect(self.select_mask)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['mask_browse'])
            widgetno += 1

            mp_widgets['mask_extend_above_label'] = QLabel(groupBox)
            mp_widgets['mask_extend_above_label'].setText("Extend Above ")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, mp_widgets['mask_extend_above_label'])
            mp_widgets['mask_extend_above_entry'] = QSpinBox(groupBox)
            mp_widgets['mask_extend_above_entry'].setSingleStep(1)
            mp_widgets['mask_extend_above_entry'].setValue(10)
            mp_widgets['mask_extend_above_entry'].setEnabled(True)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['mask_extend_above_entry'])
            widgetno += 1

            mp_widgets['mask_extend_below_label'] = QLabel(groupBox)
            mp_widgets['mask_extend_below_label'].setText("Extend Below ")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, mp_widgets['mask_extend_below_label'])
            mp_widgets['mask_extend_below_entry'] = QSpinBox(groupBox)
            mp_widgets['mask_extend_below_entry'].setSingleStep(1)
            mp_widgets['mask_extend_below_entry'].setValue(10)
            mp_widgets['mask_extend_below_entry'].setEnabled(True)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['mask_extend_below_entry'])
            widgetno += 1

            # Add should extend checkbox
            mp_widgets['extendMaskCheck'] = QCheckBox(groupBox)
            mp_widgets['extendMaskCheck'].setText("Extend mask")
            #mp_widgets['extendMaskCheck'].setEnabled(False)

            formLayout.setWidget(widgetno,QFormLayout.FieldRole, mp_widgets['extendMaskCheck'])
            widgetno += 1

            # Add submit button
            mp_widgets['submitButton'] = QPushButton(groupBox)
            mp_widgets['submitButton'].setText("Create Mask")
            mp_widgets['submitButton'].clicked.connect(lambda: self.MaskWorker("extend"))
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['submitButton'])
            widgetno += 1

            mp_widgets['saveButton'] = QPushButton(groupBox)
            mp_widgets['saveButton'].setText("Save Mask")
            mp_widgets['saveButton'].clicked.connect(lambda: self.ShowSaveMaskWindow(save_only = True))
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['saveButton'])
            widgetno += 1

            mp_widgets['clear_button'] = QPushButton(groupBox)
            mp_widgets['clear_button'].setText("Clear Mask")
            mp_widgets['clear_button'].clicked.connect(self.clearMask)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['clear_button'])
            widgetno += 1

            mp_widgets['extendMaskCheck'].stateChanged.connect(lambda: mp_widgets['submitButton'].setText("Extend Mask") \
                                                     if mp_widgets['extendMaskCheck'].isChecked() \
                                                     else mp_widgets['submitButton'].setText("Create Mask"))


            # Add elements to layout
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)

    def MaskWorker(self, type):
        v = self.vis_widget_2D.frame.viewer
        if not v.img3D:
                self.warningDialog(window_title="Error", 
                               message="Load an image on the viewer first" )
                return

        if type == "extend":
            if v.image2 and self.mask_parameters['submitButton'].text() != "Extend Mask" and self.mask_reader:
                self.ShowSaveMaskWindow(save_only = False)
                return
                #while hasattr(self, "SaveWindow"):
                    #print("waiting")
                    #time.sleep(0.5)
            else:
                self.mask_worker = Worker(self.extendMask)
                self.mask_worker.signals.finished.connect(self.DisplayMask)
        elif type == "load mask":
            self.mask_worker = Worker(self.loadMask, load_session = False)
            self.mask_worker.signals.finished.connect(self.DisplayMask)
        elif type == "load session":
            self.mask_worker = Worker(self.loadMask, load_session = True)
            self.mask_worker.signals.finished.connect(lambda:self.DisplayMask(type = "load session"))
            
        self.create_progress_window("Loading", "Loading Mask")
        self.mask_worker.signals.progress.connect(self.progress)
       
        self.progress_window.setValue(10)
        self.threadpool.start(self.mask_worker)  

    def ShowSaveMaskWindow(self, save_only):
        if not self.mask_reader:
                self.warningDialog(window_title="Error", 
                               message="Create or load a mask on the viewer first." )
                return
        self.SaveWindow = CreateSaveObjectWindow(self, "mask", save_only)
        self.SaveWindow.show()

    def extendMask(self, progress_callback=None):
            #if we have loaded the mask from a file then atm we cannot extend it bc we don't have stencil so need to set stencil somewhere?
            #we can easily get the image data v.image2 but would need a stencil?

            print("Extend mask")

            v = self.vis_widget_2D.frame.viewer

            poly = vtk.vtkPolyData()
            v.imageTracer.GetPath(poly) 
            #print(v.imageTracer.GetPath(poly))
            pathpoints = poly.GetPoints()
            #print(pathpoints)
            # for i in range(poly.GetPoints().GetNumberOfPoints()):
            #    print (poly.GetPoints().GetPoint(i))
            lasso = vtk.vtkLassoStencilSource()
            self.lasso = lasso

            image_data = self.vis_widget_2D.image_data

            lasso.SetShapeToPolygon()
            # pass the slice at which the lasso has to process
            sliceno = v.style.GetActiveSlice()
            lasso.SetSlicePoints(sliceno , pathpoints)
            orientation = v.GetSliceOrientation()
            lasso.SetSliceOrientation(orientation)
            lasso.SetInformationInput(image_data)

            #print([orientation,sliceno])

            self.mask_details['current'] = [orientation, sliceno]

            #print(self.mask_details)

            #Appropriate modification to Point Cloud Panel
            self.updatePointCloudPanel()
            
            # create a blank image
            dims = image_data.GetDimensions()
            print("Dims:" + str(dims))


            print(image_data.GetSpacing())
            

            progress_callback.emit(40)


            mask0 = Converter.numpy2vtkImage(np.zeros((dims[0],dims[1],dims[2]),order='F', 
                                                dtype=np.uint8),origin = image_data.GetOrigin(), spacing = image_data.GetSpacing())

            mask1 = Converter.numpy2vtkImage(np.ones((dims[0],dims[1],dims[2]),order='F', dtype=np.uint8),
                                                origin = image_data.GetOrigin(), spacing = image_data.GetSpacing())

            print("Mask spacing:", mask0.GetSpacing())


            # Create a Mask from the lasso.
            stencil = vtk.vtkImageStencil()
            self.mask_reader = stencil
            stencil.SetInputData(mask1)
            stencil.SetBackgroundInputData(mask0)

            stencil.SetStencilConnection(lasso.GetOutputPort())
            stencil.Update()
            dims = stencil.GetOutput().GetDimensions()

            progress_callback.emit(80)

            #print("Stencil dims: " + str(dims))

            down = self.mask_parameters['mask_extend_below_entry'].value()
            up = self.mask_parameters['mask_extend_above_entry'].value()

            # do not extend outside the image
            zmin = sliceno -down if sliceno-down>=0 else 0
            zmax = sliceno + up if sliceno+up < dims[orientation] else dims[orientation]

            #vtkutils.copyslices(stencil.GetOutput(), sliceno , zmin, zmax, orientation, None)
            stencil_output = self.copySlices(stencil.GetOutput(), sliceno , zmin, zmax, orientation, None)

            progress_callback.emit(85)

            # save the mask to a file in temp folder
            writer = vtk.vtkMetaImageWriter()
            tmpdir = tempfile.gettempdir()
            writer.SetFileName(os.path.join(tmpdir, "Masks/latest_selection.mha"))
            self.mask_file = "Masks/latest_selection.mha"

            progress_callback.emit(90)

            # if extend mask -> load temp saved mask
            if self.mask_parameters['extendMaskCheck'].isChecked():
                self.setStatusTip('Extending mask')
                if os.path.exists(os.path.join(tmpdir, "Masks/latest_selection.mha")):
                    print  ("extending mask ", os.path.join(tmpdir, "Masks/latest_selection.mha"))
                    reader = vtk.vtkMetaImageReader()
                    reader.SetFileName(os.path.join(tmpdir, "Masks/latest_selection.mha"))
                    reader.Update()

                    math = vtk.vtkImageMathematics()
                    math.SetOperationToAdd()
                    #math.SetInput1Data(stencil.GetOutput())
                    math.SetInput1Data(stencil_output)
                    math.SetInput2Data(reader.GetOutput())
                    math.Update()

                    threshold = vtk.vtkImageThreshold()
                    threshold.ThresholdBetween(1, 255)
                    threshold.ReplaceInOn()
                    threshold.SetInValue(1)
                    threshold.SetInputConnection(math.GetOutputPort())
                    threshold.Update()

                    writer.SetInputData(threshold.GetOutput())
                    self.mask_data = threshold.GetOutput()
                else:
                    print  ("extending mask failed ", tmpdir)
            else:
                #writer.SetInputData(stencil.GetOutput())
                writer.SetInputData(stencil_output)
                #self.mask_data = stencil.GetOutput()
                self.mask_data = stencil_output

            writer.Write() # writes to file.
            self.mask_parameters['extendMaskCheck'].setEnabled(True)
            self.setStatusTip('Done')

            progress_callback.emit(100)

    def copySlices(self, indata, fromslice, min, max, orientation, progress_callback):

        dims = indata.GetDimensions() #dimensions in fortran order

        i_range = range(min, max)

        indata_np = Converter.vtk2numpy(indata)

        #print("The new shape: ", np.shape(indata_np))

        for i in i_range: #note x and z are swapped due to vtkdata being F order and numpy being C order
            if orientation == 0:
                    #indata_np[i,:,:] = indata_np[fromslice,:,:]
                    indata_np[:,:,i] = indata_np[:,:,fromslice]
            elif orientation == 1:
                    indata_np[:,i,:] = indata_np[:,fromslice,:]
            elif orientation == 2:
                    #indata_np[:,:,i] = indata_np[:,:,fromslice]
                    indata_np[i,:,:] = indata_np[fromslice,:,:]

        return (indata)

    def loadMask(self, load_session, progress_callback = None): #loading mask from a file
        print("Load mask")
        time.sleep(0.1) #required so that progress window displays
        progress_callback.emit(30)
        #Appropriate modification to Point Cloud Panel
        self.updatePointCloudPanel()
        
        v =  self.vis_widget_2D.frame.viewer
        if not isinstance(v.img3D, vtk.vtkImageData):
            return 
            
        #print("loadMask")

        self.mask_reader = vtk.vtkMetaImageReader()
        self.mask_reader.AddObserver("ErrorEvent", self.e)
        tmpdir = tempfile.gettempdir()
        if (load_session):
            self.mask_reader.SetFileName(os.path.join(tmpdir, "Masks/latest_selection.mha"))
            progress_callback.emit(40)
        else:
            filename = self.mask_parameters["masksList"].currentText()
            self.mask_reader.SetFileName(os.path.join(tmpdir, "Masks/" + filename))
            #print("MASK DETAILS")
            #print(self.mask_details)
            if filename in self.mask_details:
                orientation = self.mask_details[filename][0]
                if orientation == SLICE_ORIENTATION_XY:
                        axis = 'z'
                elif orientation == SLICE_ORIENTATION_XZ:
                        axis = 'y'
                elif orientation == SLICE_ORIENTATION_YZ:
                        axis = 'x'
                self.axis = axis

                self.sliceno = self.mask_details[filename][1]
            progress_callback.emit(60)
            
        self.mask_reader.Update()
        #progress_callback.emit(50)

        writer = vtk.vtkMetaImageWriter()
       
        writer.SetFileName(os.path.join(tmpdir, "Masks/latest_selection.mha"))
        writer.SetInputConnection(self.mask_reader.GetOutputPort())
        progress_callback.emit(80)
        writer.Write()
        self.mask_file = "Masks/latest_selection.mha"
        
        
        dims = v.img3D.GetDimensions()
        print("Image dims:" + str(v.img3D.GetDimensions()))
        print("Mask dims:" + str(self.mask_reader.GetOutput().GetDimensions()))
        if not dims == self.mask_reader.GetOutput().GetDimensions():
            print("Not compatible")
            return 

        #v.setInputData2(self.mask_reader.GetOutput())
        self.mask_data = self.mask_reader.GetOutput()

    def select_mask(self): 
        dialogue = QFileDialog()
        mask = dialogue.getOpenFileName(self,"Select a mask")[0]
        if mask:
            if ".mha" in mask:
                filename = mask.split("/")[-1]
                shutil.copyfile(mask, os.path.join(tempfile.tempdir, "Masks/" + filename))
                self.mask_parameters["masksList"].addItem(filename)
                self.mask_parameters["masksList"].setCurrentText(filename)
                self.clearMask()
                self.MaskWorker("load mask")
            else:
                self.warningDialog("Please select a .mha file", "Error")


    def clearMask(self):
        self.vis_widget_2D.frame.viewer.setInputData2(vtk.vtkImageData()) #deletes mask
        self.mask_reader = None

        #how to clear the tracer? ...
        #self.vis_widget_2D.frame.viewer.imageTracer =  vtk.vtkImageTracerWidget() #this line causes problems
        #self.mask_reader = vtk.vtkImageStencil() #this is the stencil - does nothing
        #self.mask_reader.Update()
        #self.lasso = vtk.vtkLassoStencilSource()
        #self.vis_widget_2D.frame.viewer.imageTracer = vtk.vtkImageTracerWidget() #cause problems - as removes functionality
        #self.vis_widget_2D.frame.viewer.imageTracer.Modified()

    def DisplayMask(self, type = None):
        v = self.vis_widget_2D.frame.viewer
        if (hasattr(self,'mask_data')):
            v.setInputData2(self.mask_data)
        else:
            if v.img3D:
                self.warningDialog( 
                        window_title="Error", 
                        message="Mask and Dataset are not compatible",
                        detailed_text='Dataset dimensions {}\nMask dimensions {}'\
                            .format(str(v.img3D.GetDimensions()),
                                    self.mask_reader.GetOutput().GetDimensions()
                                    ))

            else:    
                self.warningDialog(window_title="Error", 
                                message="Load a dataset on the viewer first" )               
            
                
        self.progress_window.setValue(90)

        if (hasattr(self, 'axis')):
            if self.axis != None:
                v.setSliceOrientation(self.axis)
                v.displaySlice(self.sliceno)
                self.axis = None
                self.sliceno = None
        self.progress_window.setValue(100)

        if(type == "load session"):
            if(self.roi):
                print("ROI true")
                print(self.roi)
                self.PointCloudWorker("load pointcloud file")
                self.pointCloudLoaded = True
        

# Point Cloud Panel:

    def CreatePointCloudPanel(self):
        self.treeWidgetInitialElements = []
        self.treeWidgetUpdateElements = []


        self.pointCloudDockWidget = QDockWidget(self)
        self.pointCloudDockWidget.setWindowTitle('4 - Point Cloud')
        self.pointCloudDockWidgetContents = QWidget()

        self.pointCloudDockWidget.visibilityChanged.connect(partial(self.displayHelp, panel_no = 3))


        # Add vertical layout to dock contents
        self.graphDockVL = QVBoxLayout(self.pointCloudDockWidgetContents)
        self.graphDockVL.setContentsMargins(0, 0, 0, 0)

        # Create widget for dock contents
        self.dockWidget = QWidget(self.pointCloudDockWidgetContents)

        # Add vertical layout to dock widget
        self.graphWidgetVL = QVBoxLayout(self.dockWidget)
        self.graphWidgetVL.setContentsMargins(0, 0, 0, 0)

        # Add group box
        self.graphParamsGroupBox = QGroupBox(self.dockWidget)
        self.graphParamsGroupBox.setTitle("Point Cloud Parameters")

        # Add form layout to group box
        self.graphWidgetFL = QFormLayout(self.graphParamsGroupBox)

        # Create validation rule for text entry
        validator = QtGui.QDoubleValidator()
        validator.setDecimals(2)
        validatorint = QtGui.QIntValidator()

        dockWidget = self.pointCloudDockWidget
        #dockWidget.visibilityChanged.connect(lambda: self.showRangesConfigurator.setEnabled(True)) #SHOULD BE IN


        widgetno = 1

        pc = {}
        self.pointcloud_parameters = pc

        

        # Add ISO Value field
        self.isoValueLabel = QLabel(self.graphParamsGroupBox)
        self.isoValueLabel.setText("Subvolume radius")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.isoValueLabel)
        self.isoValueEntry= QLineEdit(self.graphParamsGroupBox)
        self.isoValueEntry.setValidator(validatorint)
        self.isoValueEntry.setText('80')
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.isoValueEntry)
        self.treeWidgetUpdateElements.append(self.isoValueEntry)
        self.treeWidgetUpdateElements.append(self.isoValueLabel)
        widgetno += 1
        pc['pointcloud_radius_entry'] = self.isoValueEntry

        # Add collapse priority field
        self.subvolumeShapeLabel = QLabel(self.graphParamsGroupBox)
        self.subvolumeShapeLabel.setText("Subvolume shape")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.subvolumeShapeLabel)
        self.subvolumeShapeValue = QComboBox(self.graphParamsGroupBox)
        self.subvolumeShapeValue.addItem("Cube")
        self.subvolumeShapeValue.addItem("Sphere")
        # self.subvolumeShapeValue.addItem("Box")
        # self.subvolumeShapeValue.addItem("Circle")
        self.subvolumeShapeValue.setCurrentIndex(0)

        self.treeWidgetUpdateElements.append(self.subvolumeShapeValue)
        self.treeWidgetUpdateElements.append(self.subvolumeShapeLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.subvolumeShapeValue)
        widgetno += 1
        pc['pointcloud_volume_shape_entry'] = self.subvolumeShapeValue
    #        # Add local/global checkbox
    #        self.isGlobalCheck = QCheckBox(self.graphParamsGroupBox)
    #        self.isGlobalCheck.setText("Global Iso")
    #        self.isGlobalCheck.setChecked(True)
    #        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.isGlobalCheck)
    #        self.treeWidgetUpdateElements.append(self.isGlobalCheck)
    #        widgetno += 1

        # Add horizonal seperator
        self.seperator = QFrame(self.graphParamsGroupBox)
        self.seperator.setFrameShape(QFrame.HLine)
        self.seperator.setFrameShadow(QFrame.Raised)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.SpanningRole, self.seperator)
        widgetno += 1
    #        # Add colour surfaces checkbox
    #        self.surfaceColourCheck = QCheckBox(self.graphParamsGroupBox)
    #        self.surfaceColourCheck.setText("Colour Surfaces")
    #        self.graphWidgetFL.setWidget(widgetno,QFormLayout.FieldRole, self.surfaceColourCheck)
    #        self.treeWidgetUpdateElements.append(self.surfaceColourCheck)
    #        widgetno += 1

        # Add collapse priority field
        self.dimensionalityLabel = QLabel(self.graphParamsGroupBox)
        self.dimensionalityLabel.setText("Dimensionality")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.dimensionalityLabel)
        self.dimensionalityValue = QComboBox(self.graphParamsGroupBox)
        self.dimensionalityValue.addItems(["3D","2D"])
        self.dimensionalityValue.setCurrentIndex(1)
        # self.dimensionalityValue.currentIndexChanged.connect(lambda: \
        #             self.overlapZValueEntry.setEnabled(True) \
        #             if self.dimensionalityValue.currentIndex() == 0 else \
        #                 self.overlapZValueEntry.setEnabled(False))
        self.dimensionalityValue.currentIndexChanged.connect(self.updatePointCloudPanel)
        self.treeWidgetUpdateElements.append(self.dimensionalityValue)
        self.treeWidgetUpdateElements.append(self.dimensionalityValue)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.dimensionalityValue)
        widgetno += 1
        pc['pointcloud_dimensionality_entry'] = self.dimensionalityValue

        v = self.vis_widget_2D.frame.viewer
        orientation = v.GetSliceOrientation()

        # Add Log Tree field
        # Add Overlap X
        self.overlapXLabel = QLabel(self.graphParamsGroupBox)
        self.overlapXLabel.setText("Overlap X")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapXLabel)
        self.overlapXValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapXValueEntry.setValue(0.20)
        self.overlapXValueEntry.setMaximum(0.99)
        self.overlapXValueEntry.setMinimum(0.00)
        self.overlapXValueEntry.setSingleStep(0.01)
        if orientation == 0:
            self.overlapXValueEntry.setEnabled(False)
        self.treeWidgetUpdateElements.append(self.overlapXValueEntry)
        self.treeWidgetUpdateElements.append(self.overlapXLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.overlapXValueEntry)
        widgetno += 1
        pc['pointcloud_overlap_x_entry'] = self.overlapXValueEntry
        # Add Overlap Y
        self.overlapYLabel = QLabel(self.graphParamsGroupBox)
        self.overlapYLabel.setText("Overlap Y")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapYLabel)
        self.overlapYValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapYValueEntry.setValue(0.20)
        self.overlapYValueEntry.setMaximum(0.99)
        self.overlapYValueEntry.setMinimum(0.00)
        self.overlapYValueEntry.setSingleStep(0.01)
        if orientation == 1:
            self.overlapYValueEntry.setEnabled(False)
        self.treeWidgetUpdateElements.append(self.overlapYValueEntry)
        self.treeWidgetUpdateElements.append(self.overlapYLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.overlapYValueEntry)
        widgetno += 1
        pc['pointcloud_overlap_y_entry'] = self.overlapYValueEntry
        # Add Overlap Z
        self.overlapZLabel = QLabel(self.graphParamsGroupBox)
        self.overlapZLabel.setText("Overlap Z")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapZLabel)
        self.overlapZValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapZValueEntry.setValue(0.20)
        self.overlapZValueEntry.setMaximum(0.99)
        self.overlapZValueEntry.setMinimum(0.00)
        self.overlapZValueEntry.setSingleStep(0.01)
        if orientation == 2:
            self.overlapZValueEntry.setEnabled(False)
        self.treeWidgetUpdateElements.append(self.overlapZValueEntry)
        self.treeWidgetUpdateElements.append(self.overlapZLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.overlapZValueEntry)
        widgetno += 1
        pc['pointcloud_overlap_z_entry'] = self.overlapZValueEntry

        # Add Rotation X
        self.rotateXLabel = QLabel(self.graphParamsGroupBox)
        self.rotateXLabel.setText("Rotation angle X")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.rotateXLabel)
        self.rotateXValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateXValueEntry.setValidator(validator)
        self.rotateXValueEntry.setText("0.00")
        self.treeWidgetUpdateElements.append(self.rotateXValueEntry)
        self.treeWidgetUpdateElements.append(self.rotateXLabel)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.rotateXValueEntry)
        widgetno += 1
        pc['pointcloud_rotation_x_entry'] = self.rotateXValueEntry

        # Add Overlap Y
        self.rotateYLabel = QLabel(self.graphParamsGroupBox)
        self.rotateYLabel.setText("Rotation angle Y")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.rotateYLabel)
        self.rotateYValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateYValueEntry.setValidator(validator)
        self.rotateYValueEntry.setText("0.00")
        self.treeWidgetUpdateElements.append(self.rotateYValueEntry)
        self.treeWidgetUpdateElements.append(self.rotateYLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.rotateYValueEntry)
        widgetno += 1
        pc['pointcloud_rotation_y_entry'] = self.rotateYValueEntry

        # Add Overlap Z
        self.rotateZLabel = QLabel(self.graphParamsGroupBox)
        self.rotateZLabel.setText("Rotation angle Z")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.rotateZLabel)
        self.rotateZValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateZValueEntry.setValidator(validator)
        self.rotateZValueEntry.setText("0.00")
        self.treeWidgetUpdateElements.append(self.rotateZValueEntry)
        self.treeWidgetUpdateElements.append(self.rotateZLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.rotateZValueEntry)
        widgetno += 1
        pc['pointcloud_rotation_z_entry'] = self.rotateZValueEntry


        # Add should extend checkbox
        self.erodeCheck = QCheckBox(self.graphParamsGroupBox)
        self.erodeCheck.setText("Erode mask")
        self.erodeCheck.setEnabled(True)
        self.erodeCheck.setChecked(False)
        self.erodeCheck.stateChanged.connect(lambda: 
            self.warningDialog('Erosion of mask may take long time!', 
                                window_title='WARNING', 
                                detailed_text='You may better leave this unchecked while experimenting with the point clouds' ) \
                                if self.erodeCheck.isChecked() else (lambda: True) )

        self.graphWidgetFL.setWidget(widgetno,QFormLayout.FieldRole, self.erodeCheck)
        widgetno += 1
        pc['pointcloud_erode_entry'] = self.erodeCheck

        
        # Add submit button
        self.graphParamsSubmitButton = QPushButton(self.graphParamsGroupBox)
        self.graphParamsSubmitButton.setText("Generate Point Cloud")
        self.graphParamsSubmitButton.clicked.connect(lambda: self.createSavePointCloudWindow(save_only=False))
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.graphParamsSubmitButton)
        self.treeWidgetUpdateElements.append(self.graphParamsSubmitButton)
        widgetno += 1
        # Add elements to layout
        self.graphWidgetVL.addWidget(self.graphParamsGroupBox)
        self.graphDockVL.addWidget(self.dockWidget)
        self.pointCloudDockWidget.setWidget(self.pointCloudDockWidgetContents)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.pointCloudDockWidget)
        widgetno += 1

        # Set update elements to disabled when first opening the window
        #if self.segmentor.dimensions is None:
        #    for element in self.treeWidgetUpdateElements:
        #        element.setEnabled(False)

        #self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.pcDock)

        # self.pointCloudDockWidget.show()

        pc['pointcloudList'] = QComboBox(self.graphParamsGroupBox)
        pc['pointcloudList'].setEnabled(False)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['pointcloudList'])
        widgetno += 1

        pc['loadButton'] = QPushButton(self.graphParamsGroupBox)
        pc['loadButton'].setText("Load Saved Point Cloud")
        pc['loadButton'].clicked.connect(lambda: self.PointCloudWorker("load selection"))
        pc['loadButton'].setEnabled(False)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['loadButton'])
        widgetno += 1

        pc['roi_browse'] = QPushButton(self.graphParamsGroupBox)
        pc['roi_browse'].setText("Load Pointcloud from File")
        pc['roi_browse'].clicked.connect(self.select_pointcloud)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['roi_browse'])
        widgetno += 1

        pc['clear_button'] = QPushButton(self.graphParamsGroupBox)
        pc['clear_button'].setText("Clear Point Cloud")
        pc['clear_button'].clicked.connect(self.clearPointCloud)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['clear_button'])
        widgetno += 1

        pc['subvolumes_check'] = QCheckBox(self.graphParamsGroupBox)
        pc['subvolumes_check'].setText("Display Subvolume Regions")
        pc['subvolumes_check'].setChecked(True)
        pc['subvolumes_check'].stateChanged.connect( self.showSubvolumeRegions )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['subvolumes_check'])

    def updatePointCloudPanel(self):
        #updates which settings can be changed when orientation/dimensions of image changed
        orientation = self.vis_widget_2D.frame.viewer.GetSliceOrientation()
        dimensionality = self.dimensionalityValue.currentText()

        self.overlapXValueEntry.setEnabled(True)
        self.overlapYValueEntry.setEnabled(True)
        self.overlapZValueEntry.setEnabled(True)

        if dimensionality == "2D":
            if orientation == SLICE_ORIENTATION_XY:
                self.overlapZValueEntry.setEnabled(False)
            elif orientation == SLICE_ORIENTATION_XZ:
                self.overlapYValueEntry.setEnabled(False)
            elif orientation == SLICE_ORIENTATION_YZ:
                self.overlapXValueEntry.setEnabled(False)

    def select_pointcloud(self): #, label):
        dialogue = QFileDialog()
        self.roi = dialogue.getOpenFileName(self,"Select a roi")[0]
        print(self.roi)
        if self.roi:
            if ".roi" in self.roi:
                self.PointCloudWorker("load pointcloud file")
            else:
                self.warningDialog("Please select a .roi file", "Error")
            #array = folder[0].split("/")
            #self.roi = array[-1]
            #label.setText(self.roi)
        if self.copy_files:
            filename = self.roi.split("/")[-1]
            shutil.copyfile(self.roi, os.path.join(tempfile.tempdir, filename))
            self.pointcloud_parameters['pointcloudList'].addItem(filename)
            self.pointcloud_parameters['pointcloudList'].setCurrentText(filename)


    def PointCloudWorker(self, type, filename = None, disp_file = None, vector_dim = None):
        if type == "create":
            if not self.pointCloudCreated:
                self.clearPointCloud()
            self.pointcloud_worker = Worker(self.createPointCloud, filename = "latest_pointcloud.roi")
            self.pointcloud_worker.signals.finished.connect(self.DisplayPointCloud)
        elif type == "load selection":
            self.clearPointCloud()
            self.pointcloud_worker = Worker(self.loadPointCloud, os.path.join(tempfile.tempdir, self.pointcloud_parameters['pointcloudList'].currentText()))
            self.pointcloud_worker.signals.finished.connect(self.DisplayLoadedPointCloud)
        elif type == "load pointcloud file":
            self.clearPointCloud()
            self.pointcloud_worker = Worker(self.loadPointCloud, self.roi)
            self.pointcloud_worker.signals.finished.connect(self.DisplayLoadedPointCloud)
        elif type == "create without loading":
            if not self.pointCloudCreated:
                self.clearPointCloud()
            self.pointcloud_worker = Worker(self.createPointCloud, filename = filename)
            self.pointcloud_worker.signals.finished.connect(self.progress_complete)
        elif type == "load vectors":
            self.clearPointCloud()
            self.pointcloud_worker = Worker(self.loadPointCloud, filename)
            self.pointcloud_worker.signals.finished.connect(lambda: self.displayVectors(disp_file, vector_dim))
            
        self.create_progress_window("Loading", "Loading Pointcloud")
        self.pointcloud_worker.signals.progress.connect(self.progress)
        self.progress_window.setValue(10)
        self.threadpool.start(self.pointcloud_worker)  

    def displayVectors(self,disp_file, vector_dim):
        self.DisplayLoadedPointCloud()
        self.createVectors(disp_file, vector_dim)
        self.createVectors3D(disp_file)

    def progress_complete(self):
        print("FINISHED")
        self.progress_window.setValue(100)

    def createSavePointCloudWindow(self, save_only):
        print("Create save pointcloud window -----------------------------------------------------------------------------------")
        if not self.mask_reader:
                self.warningDialog(window_title="Error", 
                               message="Load a mask on the viewer first" )
                return
        elif not hasattr(self, 'point0_loc'):
            self.warningDialog(window_title="Error", 
                               message="Select a point 0 in image registration first." )
            return

        else:
            if(self.pointCloudCreated or self.pointCloudLoaded): 
                print("pointcloud created")
                self.SavePointCloudWindow = CreateSaveObjectWindow(self, "pointcloud", save_only)
                self.SavePointCloudWindow.show()
            else:
                self.PointCloudWorker("create")

    def createPointCloud(self, filename = "latest_pointcloud.roi", progress_callback=None, radius = None):
            ## Create the PointCloud
            print("Create point cloud")
            #print(filename)
            # Mask is read from temp file
            tmpdir = tempfile.gettempdir() 
            reader = vtk.vtkMetaImageReader()
            reader.AddObserver("ErrorEvent", self.e)
            reader.SetFileName(os.path.join(tmpdir,"Masks\\latest_selection.mha"))
            reader.Update()
            origin = reader.GetOutput().GetOrigin()
            spacing = reader.GetOutput().GetSpacing()
            dimensions = reader.GetOutput().GetDimensions()

            print("read mask")
            
            
            if not self.pointCloudCreated:
                print("Not created")
                #self.clearPointCloud() #removes existing pointcloud from viewer if one has been loaded from a file - TODO make sure this is done outside thread, cant do in thread
                pointCloud = cilRegularPointCloudToPolyData()
                # save reference
                self.pointCloud = pointCloud
                print("Not created")
            else:
                print("created")
                pointCloud = self.pointCloud
                print("created")

            #print(type(pointCloud))
            

            v = self.vis_widget_2D.frame.viewer
            orientation = v.GetSliceOrientation()
            pointCloud.SetOrientation(orientation)
                        
            shapes = [cilRegularPointCloudToPolyData.CUBE, cilRegularPointCloudToPolyData.SPHERE]  

            dimensionality = [3,2]
            
            pointCloud.SetMode(shapes[self.subvolumeShapeValue.currentIndex()])
            pointCloud.SetDimensionality(
                    dimensionality[self.dimensionalityValue.currentIndex()]
                    )

            self.pointCloud_shape =  shapes[self.subvolumeShapeValue.currentIndex()]
            print(self.pointCloud_shape)
            
            #slice is read from the viewer
            pointCloud.SetSlice(v.GetActiveSlice())

            print(v.GetActiveSlice())
            
            pointCloud.SetInputConnection(0, reader.GetOutputPort())

            print("Overlap: ", [self.overlapXValueEntry.text(), self.overlapYValueEntry.text(), self.overlapZValueEntry.text()])

            if radius is None:
                radius = int(self.isoValueEntry.text())

            if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
                radius = radius * 2 #in cube case, radius is side length 
                pointCloud.SetOverlap(0,float(self.overlapXValueEntry.text()))
                pointCloud.SetOverlap(1,float(self.overlapYValueEntry.text()))
                pointCloud.SetOverlap(2,float(self.overlapZValueEntry.text()))
                
            else:
                pointCloud.SetOverlap(0,float(self.overlapXValueEntry.text()))
                pointCloud.SetOverlap(1,float(self.overlapYValueEntry.text()))
                pointCloud.SetOverlap(2,float(self.overlapZValueEntry.text()))


            print("Radius: ", radius)
            pointCloud.SetSubVolumeRadiusInVoxel(radius)
            pointCloud.Update()
            self.pointCloud_radius = radius
            self.pointCloud_overlap = [float(self.overlapXValueEntry.text()), float(self.overlapYValueEntry.text()), float(self.overlapZValueEntry.text())]
            
            print ("pointCloud number of points", pointCloud.GetNumberOfPoints())

            if pointCloud.GetNumberOfPoints() == 0: 
                return         

            # Erode the transformed mask of SubVolumeRadius because we don't want to have subvolumes 
            # outside the mask
            if not self.pointCloudCreated:
                erode = vtk.vtkImageDilateErode3D()
                erode.SetErodeValue(1)
                erode.SetDilateValue(0) 
                # save reference
                self.erode = erode
                self.erode_pars = {'selection_mtime':os.path.getmtime(
                        os.path.join(tmpdir, "Masks\\latest_selection.mha"))}
                
            else:
                erode = self.erode

            
            print("Orientation: " + str(orientation))

            if orientation == SLICE_ORIENTATION_XY:
                ks = [pointCloud.GetSubVolumeRadiusInVoxel(), pointCloud.GetSubVolumeRadiusInVoxel(), 1]
                if pointCloud.GetDimensionality() == 3:
                    ks[2]= pointCloud.GetSubVolumeRadiusInVoxel()
            elif orientation == SLICE_ORIENTATION_XZ:
                ks = [pointCloud.GetSubVolumeRadiusInVoxel(), 1, pointCloud.GetSubVolumeRadiusInVoxel()]
                if pointCloud.GetDimensionality() == 3:
                    ks[1]= pointCloud.GetSubVolumeRadiusInVoxel()
            elif orientation == SLICE_ORIENTATION_YZ:
                ks = [1, pointCloud.GetSubVolumeRadiusInVoxel(), pointCloud.GetSubVolumeRadiusInVoxel()]
                if pointCloud.GetDimensionality() == 3:
                    ks[0]= pointCloud.GetSubVolumeRadiusInVoxel()

            # if shape is box or square to be sure that the subvolume is within
            # the mask we need to take the half of the diagonal rather than the
            # half of the size
            if self.pointCloud_shape == 'cube':
                ks = [round(1.41 * l) for l in ks]
            
            
            # the mask erosion takes a looong time. Try not do it all the 
            # time if neither mask nor other values have changed
            if not self.pointCloudCreated:
                self.erode_pars['ks'] =  ks[:]        
                run_erode = True
                #run_erode = False
            else:
                run_erode = False
                # test if mask is different from last one by checking the modification
                # time
                mtime = os.path.getmtime(os.path.join(tmpdir, "Masks\\latest_selection.mha"))
                if mtime != self.erode_pars['selection_mtime']:
                    print("mask has changed")
                    run_erode = True
                if ks != self.erode_pars['ks']:
                    run_erode = True
                    print("radius has changed")
                    self.erode_pars['ks'] = ks[:]
                
            print ("Erode checked" ,self.erodeCheck.isChecked())
            if run_erode and self.erodeCheck.isChecked():
                erode.SetInputConnection(0,reader.GetOutputPort())
                erode.SetKernelSize(ks[0],ks[1],ks[2])
                erode.Update()
            
            
            # Mask the point cloud with the eroded mask
            if not self.pointCloudCreated:
                polydata_masker = cilMaskPolyData()
                # save reference
                self.polydata_masker = polydata_masker
            else:
                polydata_masker = self.polydata_masker
            polydata_masker.SetMaskValue(1)
            if self.erodeCheck.isChecked():
                polydata_masker.SetInputConnection(1, erode.GetOutputPort())
            else:
                polydata_masker.SetInputConnection(1, reader.GetOutputPort())
            
            ## Create a Transform to modify the PointCloud
            # Translation and Rotation
            #rotate = (0.,0.,25.)
            rotate = [
                    float(self.rotateXValueEntry.text()),
                    float(self.rotateYValueEntry.text()),
                    float(self.rotateZValueEntry.text())
            ]
            self.pointCloud_rotation = rotate
    #        if not self.pointCloudCreated:
    #            transform = vtk.vtkTransform()
    #            # save reference
    #            self.transform = transform
    #        else:
    #            transform = self.transform
            transform = vtk.vtkTransform()
            # save reference
            self.transform = transform
            # rotate around the center of the image data

            if orientation == SLICE_ORIENTATION_XY:
                transform.Translate(dimensions[0]/2*spacing[0], dimensions[1]/2*spacing[1],0)
            elif orientation == SLICE_ORIENTATION_XZ:
                transform.Translate(dimensions[0]/2*spacing[0], 0,dimensions[2]/2*spacing[2])
            elif orientation == SLICE_ORIENTATION_YZ:
                transform.Translate(0, dimensions[1]/2*spacing[1],dimensions[2]/2*spacing[2])
            #WAS:
            #transform.Translate(dimensions[0]/2*spacing[0], dimensions[1]/2*spacing[1],0)
            # rotation angles
            transform.RotateX(rotate[0])
            transform.RotateY(rotate[1])
            transform.RotateZ(rotate[2])

            #WAS:
            #transform.Translate(-dimensions[0]/2*spacing[0], -dimensions[1]/2*spacing[1],0)
            if orientation == SLICE_ORIENTATION_XY:
                transform.Translate(-dimensions[0]/2*spacing[0], -dimensions[1]/2*spacing[1],0)
            elif orientation == SLICE_ORIENTATION_XZ:
                transform.Translate(-dimensions[0]/2*spacing[0], 0,-dimensions[2]/2*spacing[2])
            elif orientation == SLICE_ORIENTATION_YZ:
                transform.Translate(0, -dimensions[1]/2*spacing[1],-dimensions[2]/2*spacing[2])

            #Translate pointcloud so that point 0 is in the cloud
            if hasattr(self, 'point0'):
                pointCloud_points = []
                pointCloud_distances = []
                print("Point 0: ", self.point0_loc)
                for i in range (0, pointCloud.GetNumberOfPoints()):
                    current_point = pointCloud.GetPoints().GetPoint(i)
                    pointCloud_points.append(current_point)
                    pointCloud_distances.append((self.point0_loc[0]-current_point[0])**2+(self.point0_loc[1]-current_point[1])**2+(self.point0_loc[2]-current_point[2])**2)

                lowest_distance_index = pointCloud_distances.index(min(pointCloud_distances))

                print("The point closest to point 0 is:", pointCloud_points[lowest_distance_index])

                pointCloud_Translation = (self.point0_loc[0]-pointCloud_points[lowest_distance_index][0],self.point0_loc[1]-pointCloud_points[lowest_distance_index][1],self.point0_loc[2]-pointCloud_points[lowest_distance_index][2])

                print("Translation from it is:", pointCloud_Translation)

                #transform = vtk.vtkTransform()
                transform.Translate(pointCloud_Translation)

                # t_filter = vtk.vtkTransformFilter()
                # # save reference
                # t_filter.SetTransform(transform)
                # t_filter.SetInputConnection(pointCloud.GetOutputPort())


            
            if self.pointCloudCreated:
                t_filter = self.t_filter
            else:
                # Actual Transformation is done here
                t_filter = vtk.vtkTransformFilter()
                # save reference
                self.t_filter = t_filter
            t_filter.SetTransform(transform)
            t_filter.SetInputConnection(pointCloud.GetOutputPort())
            
            polydata_masker.SetInputConnection(0, t_filter.GetOutputPort())
            # polydata_masker.Modified()
            
            polydata_masker.Update()
            # print ("polydata_masker type", type(polydata_masker.GetOutputDataObject(0)))

            

            print("Updated polydata_masker")
            
            self.reader = reader
            self.pointcloud = pointCloud

    # self.polydata_masker.Modified()
    #            self.cubesphere_actor3D.VisibilityOff()
    #            self.pointactor.VisibilityOff()
    #            self.cubesphere_actor.VisibilityOff()
    #        print ("should be already changed")
    #            self.cubesphere_actor3D.VisibilityOn()
    #            self.pointactor.VisibilityOn()
    #            self.cubesphere_actor.VisibilityOn()

            #pointcloud= self.pointCloud.GetOutputDataObject(0) #this saved the whole array of points not cut to the mask shape
            pointcloud = self.polydata_masker.GetOutputDataObject(0)
            #array = np.zeros((pointcloud.GetNumberOfPoints(), 4))
            array = []
            count = 2
            for i in range(pointcloud.GetNumberOfPoints()):
                pp = pointcloud.GetPoint(i)
                distance = pp[0]-self.point0_loc[0] + pp[1]-self.point0_loc[1] + pp[2]-self.point0_loc[2]
                if distance == 0:
                    print(pp)
                    print("Add to front of list")
                    array.insert(0,(1,*pp))
                else:
                    array.append((count, *pp))
                    count += 1

            print(array[0])
            np.savetxt(tempfile.tempdir + "/" + filename, array, '%d\t%.3f\t%.3f\t%.3f', delimiter=';')
            self.roi = os.path.join(tempfile.tempdir, filename)
            print(self.roi)
            print("finished making the cloud")

            # for i in range (0, pointcloud.GetNumberOfPoints()):
            #     current_point = pointcloud.GetPoint(i)
            #     pointCloud_points.append(current_point)
            #     pointCloud_distances.append((self.point0_loc[0]-current_point[0])**2+(self.point0_loc[1]-current_point[1])**2+(self.point0_loc[2]-current_point[2])**2)

            # print("Point 0: ", self.point0_loc)

            # lowest_distance_index = pointCloud_distances.index(min(pointCloud_distances))

            # print("The point closest to point 0 is:", pointCloud_points[lowest_distance_index])
            

    def loadPointCloud(self, pointcloud_file, progress_callback):
        time.sleep(0.1) #required so that progress window displays
        progress_callback.emit(20)
        #self.clearPointCloud() #need to clear current pointcloud before we load next one TODO: move outside thread
        progress_callback.emit(30)
        self.roi = pointcloud_file
        #print(self.roi)
        points = np.loadtxt(self.roi)
        progress_callback.emit(50)
        self.polydata_masker = cilNumpyPointCloudToPolyData()
        self.polydata_masker.SetData(points)
        self.polydata_masker.Update()
        progress_callback.emit(80)

        print(pointcloud_file)
        pointcloud_file = pointcloud_file.split("\\")[-1]
        print(self.pointCloud_details)
        print(pointcloud_file)

        if pointcloud_file in self.pointCloud_details:
            self.pointCloud_radius = self.pointCloud_details[pointcloud_file][0]
            self.pointCloud_overlap = self.pointCloud_details[pointcloud_file][1]
            self.pointCloud_rotation = self.pointCloud_details[pointcloud_file][2]
            self.pointCloud_shape = self.pointCloud_details[pointcloud_file][3]
            print("Set properties")
        else:
            self.pointCloud_radius = 0
            self.pointCloud_overlap = [0.00,0.00,0.00]
            self.pointCloud_rotation = [0.00,0.00,0.00]
            self.pointCloud_shape = cilRegularPointCloudToPolyData.CUBE
            print("No details found")

        #SET UP APPROPRIATE VALUES OF SPINBOXES ON INTERFACE:
        # self.overlapXValueEntry.setValue(float(self.pointCloud_overlap[0]))
        # self.overlapYValueEntry.setValue(float(self.pointCloud_overlap[1]))
        # self.overlapZValueEntry.setValue(float(self.pointCloud_overlap[2]))
        # print("Set xyz")
        # print(self.pointCloud_radius)
        # print(str(self.pointCloud_radius))
        # self.isoValueEntry.setText(str(self.pointCloud_radius))
        # print(str("{:.2f}".format(self.pointCloud_rotation[0])))
        # self.rotateXValueEntry.setText(str("{:.2f}".format(self.pointCloud_rotation[0])))
        # self.rotateYValueEntry.setText(str("{:.2f}".format(self.pointCloud_rotation[1])))
        # self.rotateZValueEntry.setText(str("{:.2f}".format(self.pointCloud_rotation[2])))
        # print("Set the values")

    def DisplayLoadedPointCloud(self):
        self.setup2DPointCloudPipeline()
        self.setup3DPointCloudPipeline()
        print(self.loading_session)
        self.progress_window.setValue(100)
        if not self.loading_session:
            self.warningDialog(window_title="Success", message="Point cloud loaded.")
        self.loading_session = False 
        self.pointCloudLoaded = True
        self.pointCloud_details["latest_pointcloud.roi"] = [self.pointCloud_radius, self.pointCloud_overlap, self.pointCloud_rotation, self.pointCloud_shape]
        
        
    def DisplayPointCloud(self):
        if self.pointCloud.GetNumberOfPoints() == 0:
            self.progress_window.setValue(100) 
            self.warningDialog(window_title="Error", 
                    message="Failed to create point cloud.",
                    detailed_text='A pointcloud could not be created because there were no points in the selected region. \
                    Try modifying the subvolume radius before creating a new pointcloud.' )
            self.pointCloudCreated = False
            self.pointCloudLoaded = False
            return
        print("display pointcloud")
        
        v = self.vis_widget_2D.frame.viewer
        if not self.pointCloudCreated:
                # visualise polydata
                self.setup2DPointCloudPipeline()
                v.setInputData2(self.reader.GetOutput())
                self.setup3DPointCloudPipeline()
                self.pointCloudCreated = True
                self.pointCloudLoaded = True

        else:
            spacing = v.img3D.GetSpacing()
            radius = self.pointCloud_radius
            rotate = self.pointCloud_rotation
            print("Spacing ",spacing)
            print("Radius ",radius)
            print("Rotation", rotate)

            if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
            #cube
                #self.glyph_source = self.cube_source
                self.cube_source.SetXLength(spacing[0]*radius)
                self.cube_source.SetYLength(spacing[1]*radius)
                self.cube_source.SetZLength(spacing[2]*radius)
                self.cube_source.Update()
                self.transform.RotateX(rotate[0])
                self.transform.RotateY(rotate[1])
                self.transform.RotateZ(rotate[2])  
                self.cube_transform_filter.Update()
                self.cubesphere.SetSourceConnection(self.cube_transform_filter.GetOutputPort())
            else:
                #self.glyph_source = self.sphere_source
                self.sphere_source.SetRadius(radius * spacing[0]) # ??? should this change with orientation?
                self.cubesphere.SetSourceConnection(self.sphere_source.GetOutputPort())
            
            self.cubesphere.Update()
        

        #Update window so pointcloud is instantly visible without user having to interact with viewer first
        self.vis_widget_2D.frame.viewer.GetRenderWindow().Render()
        self.vis_widget_3D.frame.viewer.getRenderWindow().Render()

        print(self.pointCloudCreated)

        self.progress_window.setValue(100)

        self.warningDialog(window_title="Success", message="Point cloud created." )
        self.pointCloud_details["latest_pointcloud.roi"] = [self.pointCloud_radius, self.pointCloud_overlap, self.pointCloud_rotation, self.pointCloud_shape]

    def clearPointCloud(self):
        if hasattr(self, 'actors_2D'):
            if 'pointcloud' in self.actors_2D:
                self.actors_2D ['pointcloud_frame'].VisibilityOff()
                self.actors_2D['pointcloud'].VisibilityOff()

                if 'pactor' in self.actors_2D:
                    self.actors_2D ['pactor'].VisibilityOff()
                    self.actors_2D['arrow_actor'].VisibilityOff()


        if hasattr(self, 'actors_3D'):
            if 'pointcloud' in self.actors_3D:
                self.actors_3D ['pointcloud_frame'].VisibilityOff()
                self.actors_3D['pointcloud'].VisibilityOff()

        self.pointCloudLoaded = False
        self.pointCloudCreated = False
        

        v2D = self.vis_widget_2D.frame.viewer
        v3D = self.vis_widget_3D.frame.viewer

        v2D.GetRenderWindow().Render()
        v3D.getRenderWindow().Render()

        print("Cleared pc")

        # ren2D = self.vis_widget_2D.frame.viewer.getRenderer()
        # ren3D = self.vis_widget_3D.frame.viewer.getRenderer()

        # present_actors = ren2D.GetActors()
        # present_actors.InitTraversal()
        # #self.log("Currently present actors {}".format(present_actors))
        # #print(present_actors.GetNumberOfItems())
        # for i in range(present_actors.GetNumberOfItems()):
        #      nextActor = present_actors.GetNextActor()
        #      #print(nextActor)
        #      #print(type(nextActor))
        #      #ren2D.RemoveActor(nextActor)
       
  
        # v2D.GetRenderWindow().Render()

        # present_actors = ren3D.GetActors()
        # present_actors.InitTraversal()
        # #self.log("Currently present actors {}".format(present_actors))
        # print(present_actors.GetNumberOfItems())
        # for i in range(present_actors.GetNumberOfItems()):
        #      nextActor = present_actors.GetNextActor()
        #      print(type(nextActor))
        #      #ren3D.RemoveActor(nextActor)

        # 
        # #print("Rendered")

    def showSubvolumeRegions(self, show):
        if hasattr(self, 'actors_2D'):
            if 'pointcloud' in self.actors_2D:
                if show:
                    self.actors_2D ['pointcloud_frame'].VisibilityOn()
                else:
                    self.actors_2D ['pointcloud_frame'].VisibilityOff()

        if hasattr(self, 'actors_3D'):
            if 'pointcloud' in self.actors_3D:
                if show:
                    self.actors_3D ['pointcloud_frame'].VisibilityOn()
                else:
                    self.actors_3D ['pointcloud_frame'].VisibilityOff()

        self.vis_widget_2D.frame.viewer.ren.Render()
   

        
    def loadPointCloudFromCSV(self,filename, delimiter=','):
        print ("loadPointCloudFromCSV")
        pointcloud = []
        with open(filename, 'r') as csvfile:
            read = csv.reader(csvfile, delimiter=delimiter)
            for row in read:
                #read in only numerical values
                #print (row)
                try:
                    row = list(map(lambda x: float(x),row))
                #print ("reduce " , reduce( lambda x,y: isinstance(x,Number) and \
                #          isinstance(y,Number) , row))
                #if reduce( lambda x,y: isinstance(x,Number) and \
                #          isinstance(y,Number) , row):
                    pointcloud.append(row)
                except ValueError as ve:
                    print ('Value Error' , ve)
        return pointcloud

    def createVectors(self, filename, dimensions = 2):
        displ = np.asarray(
        self.loadPointCloudFromCSV(filename,'\t')[:]
        )

        #displ[10][6] = 20.
        #displ[10][7] = 0.
        #displ[10][8] = 0.
        #displ[11][6] = 0.
        #displ[11][7] = 20.
        #displ[11][8] = 0.
        #displ[12][6] = 0.
        #displ[12][7] = 0.
        #displ[12][8] = 20.

        #dist = (displ.T[6]**2 + displ.T[7]**2 + displ.T[8]**2)
        #m = dist.min()
        #M = dist.max()
        #%%

        grid = vtk.vtkUnstructuredGrid()
        vertices = vtk.vtkCellArray()
        arrow = vtk.vtkDoubleArray()
        arrow.SetNumberOfComponents(3)
        acolor = vtk.vtkDoubleArray()

        pc = vtk.vtkPoints()
        for count in range(len(displ)):
            p = pc.InsertNextPoint(displ[count][1],
                                displ[count][2], 
                                displ[count][3]) #xyz coords
            vertices.InsertNextCell(1) # Create cells by specifying a count of total points to be inserted
            vertices.InsertCellPoint(p)
            #arrow.InsertNextTuple3(displ[count][6],displ[count][7],displ[count][8])

            orientation = self.vis_widget_2D.frame.viewer.GetSliceOrientation()

            #print("Sum of square of points:")
            #print(displ[count][6:9])

            if dimensions ==2:
                if orientation == SLICE_ORIENTATION_XY:
                    arrow.InsertNextTuple3(displ[count][6],displ[count][7],0) #u and v are set for x and y
                    new_points = displ[count][6:8]

                elif orientation == SLICE_ORIENTATION_XZ:
                    arrow.InsertNextTuple3(displ[count][6],0,displ[count][8]) #u and v are set for x and y
                    new_points = [displ[count][6], displ[count][8]]

                elif orientation == SLICE_ORIENTATION_YZ:
                    arrow.InsertNextTuple3(0,displ[count][7],displ[count][8]) #u and v are set for x and y
                    new_points = [displ[count][7], displ[count][8]]
                
                #print(reduce(lambda x,y: x + y**2, (*new_points,0), 0))
                acolor.InsertNextValue(reduce(lambda x,y: x + y**2, (*new_points,0), 0)) #inserts u^2 + v^2 + w^2

            else:
                arrow.InsertNextTuple3(displ[count][6],displ[count][7],displ[count][8]) #u and v are set for x and y
                new_points = displ[count][6:9]
                #print(displ[count][6]**2+displ[count][7]**2+displ[count][8]**2)
                acolor.InsertNextValue(displ[count][6]**2+displ[count][7]**2+displ[count][8]**2) #inserts u^2 + v^2
            
        lut = vtk.vtkLookupTable()
        print ("lut table range" , acolor.GetRange())
        lut.SetTableRange(acolor.GetRange())
        lut.SetNumberOfTableValues( 256 )
        lut.SetHueRange( 240/360., 0. )
        #lut.SetSaturationRange( 1, 1 )
        lut.Build()

        pointPolyData = vtk.vtkPolyData()
        #2. Add the points to a vtkPolyData.
        pointPolyData.SetPoints( pc ) 
        pointPolyData.SetVerts( vertices ) 
        pointPolyData.GetPointData().SetVectors(arrow) #(u,v,w) vector in 2D
        pointPolyData.GetPointData().SetScalars(acolor) 

        # arrow
        arrow_glyph = vtk.vtkGlyph3D()
        #arrow_glyph.SetScaleModeToDataScalingOff()
        arrow_glyph.SetScaleModeToScaleByVector()
        #arrow_glyph.SetColorModeToColorByVector()
        arrow_source = vtk.vtkArrowSource()
        arrow_source.SetTipRadius(0.2)
        arrow_source.SetShaftRadius(0.075)
        arrow_mapper = vtk.vtkPolyDataMapper()
        arrow_mapper.SetInputConnection(arrow_glyph.GetOutputPort())
        arrow_mapper.SetScalarModeToUsePointFieldData()
        arrow_mapper.SelectColorArray(0)
        arrow_mapper.SetScalarRange(acolor.GetRange())
        arrow_mapper.SetLookupTable(lut)

        arrow_glyph.SetInputData(pointPolyData)
        arrow_glyph.SetSourceConnection(arrow_source.GetOutputPort())
        #arrow_glyph.SetScaleFactor(5)
        arrow_glyph.SetScaleModeToScaleByVector()
        arrow_glyph.SetVectorModeToUseVector()
        arrow_glyph.ScalingOn()
        arrow_glyph.OrientOn()

        # Usual actor
        arrow_actor = vtk.vtkActor()
        arrow_actor.SetMapper(arrow_mapper)
        #arrow_actor.GetProperty().SetColor(0, 1, 1)

        # vtk user guide p.95
        conesource = vtk.vtkConeSource()
        conesource.SetResolution(6)
        transform = vtk.vtkTransform()
        transform.Translate(0.5,0.,0.)
        transformF = vtk.vtkTransformPolyDataFilter()
        transformF.SetInputConnection(conesource.GetOutputPort())
        transformF.SetTransform(transform)

        cones = vtk.vtkGlyph3D()
        cones.SetInputData(pointPolyData)
        cones.SetSourceConnection(transformF.GetOutputPort())

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(cones.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        #actor.GetProperty().SetPointSize(3)
        actor.GetProperty().SetColor(0,1,1)

        pmapper = vtk.vtkPolyDataMapper()
        pmapper.SetInputData(pointPolyData)

        pactor = vtk.vtkActor()
        pactor.SetMapper(pmapper)
        pactor.GetProperty().SetPointSize(3)
        pactor.GetProperty().SetColor(1,0,1)

        #v = CILViewer()
        v = self.vis_widget_2D.frame.viewer
        v.ren.AddActor(pactor)
        #v.ren.AddActor(actor)
        v.ren.AddActor(arrow_actor)
        self.actors_2D ['pactor'] = pactor
        self.actors_2D['arrow_actor'] = arrow_actor


        ## add volume
        # if True:
        #     runconfig = json.load(open("dvc_kalpani.json", "r"))
        #     dataset = numpy.load(os.path.abspath(runconfig['correlate_filename']))
        #     conv = Converter.numpy2vtkImporter(numpy.transpose(dataset, [0,1,2]))
        #     conv.Update()
        #     v.setInput3DData(conv.GetOutput())
        #     v.style.SetActiveSlice(255)
        #     v.style.UpdatePipeline()
            
        v.startRenderLoop()

    def createVectors3D(self, filename):
        displ = np.asarray(
        self.loadPointCloudFromCSV(filename,'\t')[:]
        )

        #displ[10][6] = 20.
        #displ[10][7] = 0.
        #displ[10][8] = 0.
        #displ[11][6] = 0.
        #displ[11][7] = 20.
        #displ[11][8] = 0.
        #displ[12][6] = 0.
        #displ[12][7] = 0.
        #displ[12][8] = 20.

        #dist = (displ.T[6]**2 + displ.T[7]**2 + displ.T[8]**2)
        #m = dist.min()
        #M = dist.max()
        #%%

        grid = vtk.vtkUnstructuredGrid()
        vertices = vtk.vtkCellArray()
        arrow = vtk.vtkDoubleArray()
        arrow.SetNumberOfComponents(3)
        acolor = vtk.vtkDoubleArray()

        pc = vtk.vtkPoints()
        for count in range(len(displ)):
            p = pc.InsertNextPoint(displ[count][1],
                                displ[count][2], 
                                displ[count][3]) #xyz coords
            vertices.InsertNextCell(1) # Create cells by specifying a count of total points to be inserted
            vertices.InsertCellPoint(p)
            #arrow.InsertNextTuple3(displ[count][6],displ[count][7],displ[count][8])

        arrow.InsertNextTuple3(displ[count][6],displ[count][7],displ[count][8]) #u and v are set for x and y
        new_points = displ[count][6:9]
        #print(displ[count][6]**2+displ[count][7]**2+displ[count][8]**2)
        acolor.InsertNextValue(displ[count][6]**2+displ[count][7]**2+displ[count][8]**2) #inserts u^2 + v^2
            
        lut = vtk.vtkLookupTable()
        print ("lut table range" , acolor.GetRange())
        lut.SetTableRange(acolor.GetRange())
        lut.SetNumberOfTableValues( 256 )
        lut.SetHueRange( 240/360., 0. )
        #lut.SetSaturationRange( 1, 1 )
        lut.Build()

        pointPolyData = vtk.vtkPolyData()
        #2. Add the points to a vtkPolyData.
        pointPolyData.SetPoints( pc ) 
        pointPolyData.SetVerts( vertices ) 
        pointPolyData.GetPointData().SetVectors(arrow) #(u,v,w) vector in 2D
        pointPolyData.GetPointData().SetScalars(acolor) 

        # arrow
        arrow_glyph = vtk.vtkGlyph3D()
        #arrow_glyph.SetScaleModeToDataScalingOff()
        arrow_glyph.SetScaleModeToScaleByVector()
        #arrow_glyph.SetColorModeToColorByVector()
        arrow_source = vtk.vtkArrowSource()
        arrow_source.SetTipRadius(0.2)
        arrow_source.SetShaftRadius(0.075)
        arrow_mapper = vtk.vtkPolyDataMapper()
        arrow_mapper.SetInputConnection(arrow_glyph.GetOutputPort())
        arrow_mapper.SetScalarModeToUsePointFieldData()
        arrow_mapper.SelectColorArray(0)
        arrow_mapper.SetScalarRange(acolor.GetRange())
        arrow_mapper.SetLookupTable(lut)

        arrow_glyph.SetInputData(pointPolyData)
        arrow_glyph.SetSourceConnection(arrow_source.GetOutputPort())
        #arrow_glyph.SetScaleFactor(5)
        arrow_glyph.SetScaleModeToScaleByVector()
        arrow_glyph.SetVectorModeToUseVector()
        arrow_glyph.ScalingOn()
        arrow_glyph.OrientOn()

        # Usual actor
        arrow_actor = vtk.vtkActor()
        arrow_actor.SetMapper(arrow_mapper)
        #arrow_actor.GetProperty().SetColor(0, 1, 1)

        # vtk user guide p.95
        conesource = vtk.vtkConeSource()
        conesource.SetResolution(6)
        transform = vtk.vtkTransform()
        transform.Translate(0.5,0.,0.)
        transformF = vtk.vtkTransformPolyDataFilter()
        transformF.SetInputConnection(conesource.GetOutputPort())
        transformF.SetTransform(transform)

        cones = vtk.vtkGlyph3D()
        cones.SetInputData(pointPolyData)
        cones.SetSourceConnection(transformF.GetOutputPort())

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(cones.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        #actor.GetProperty().SetPointSize(3)
        actor.GetProperty().SetColor(0,1,1)

        pmapper = vtk.vtkPolyDataMapper()
        pmapper.SetInputData(pointPolyData)

        pactor = vtk.vtkActor()
        pactor.SetMapper(pmapper)
        pactor.GetProperty().SetPointSize(3)
        pactor.GetProperty().SetColor(1,0,1)

        #v = CILViewer()
        v = self.vis_widget_3D.frame.viewer
        v.ren.AddActor(pactor)
        #v.ren.AddActor(actor)
        v.ren.AddActor(arrow_actor)


        ## add volume
        # if True:
        #     runconfig = json.load(open("dvc_kalpani.json", "r"))
        #     dataset = numpy.load(os.path.abspath(runconfig['correlate_filename']))
        #     conv = Converter.numpy2vtkImporter(numpy.transpose(dataset, [0,1,2]))
        #     conv.Update()
        #     v.setInput3DData(conv.GetOutput())
        #     v.style.SetActiveSlice(255)
        #     v.style.UpdatePipeline()
            
        v.startRenderLoop()


#Run DVC  Panel:
    def CreateRunDVCPanel(self):
            self.run_dvc_panel = generateUIDockParameters(self, "5 - Run DVC")
            dockWidget = self.run_dvc_panel[0]
            dockWidget.setObjectName("RunDVCPanel")
            internalWidgetVerticalLayout = self.run_dvc_panel[4]
            groupBox = self.run_dvc_panel[5]
            groupBox.setTitle('Run Parameters')
            formLayout = self.run_dvc_panel[6]

            dockWidget.visibilityChanged.connect(partial(self.displayHelp, panel_no = 4))

            #Create the widgets:
            widgetno = 1

            rdvc_widgets = {}

            # rdvc_widgets['dir_label'] = QLabel(groupBox)
            # rdvc_widgets['dir_label'].setText("Select a directory to save the run:")
            # formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['dir_label'])

            # rdvc_widgets['dir_name_label'] = QLabel(groupBox)
            # rdvc_widgets['dir_name_label'].setText("")
            # formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['dir_name_label'])
            # widgetno += 1

            # rdvc_widgets['dir_browse'] = QPushButton(groupBox)
            # rdvc_widgets['dir_browse'].setText("Browse..")
            # formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['dir_browse'])
            # widgetno += 1

            rdvc_widgets['name_label'] = QLabel(groupBox)
            rdvc_widgets['name_label'].setText("Set a name for the run:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['name_label'])

            rdvc_widgets['name_entry'] = QLineEdit(self)
            rx = QRegExp("[A-Za-z0-9]+")
            validator = QRegExpValidator(rx, rdvc_widgets['name_entry']) #need to check this
            rdvc_widgets['name_entry'].setValidator(validator)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['name_entry'])
            widgetno += 1

            separators = []
            separators.append(QFrame(groupBox))
            separators[-1].setFrameShape(QFrame.HLine)
            separators[-1].setFrameShadow(QFrame.Raised)
            formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
            widgetno += 1  

            rdvc_widgets['run_points_label'] = QLabel(groupBox)
            rdvc_widgets['run_points_label'].setText("Points in Run:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_points_label'])

            rdvc_widgets['run_points_spinbox'] = QSpinBox(groupBox)
            rdvc_widgets['run_points_spinbox'].setMinimum(1)
            rdvc_widgets['run_points_spinbox'].setMaximum(10000)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_points_spinbox'])
            widgetno += 1         

            rdvc_widgets['run_max_displacement_label'] = QLabel(groupBox)
            rdvc_widgets['run_max_displacement_label'].setText("Maximum Displacement (voxels)")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_max_displacement_label'])
            rdvc_widgets['run_max_displacement_entry'] = QSpinBox(groupBox)
            rdvc_widgets['run_max_displacement_entry'].setValue(10)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_max_displacement_entry'])
            widgetno += 1

            rdvc_widgets['run_ndof_label'] = QLabel(groupBox)
            rdvc_widgets['run_ndof_label'].setText("Number of Degrees of Freedom")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_ndof_label'])
            rdvc_widgets['run_ndof_entry'] = QComboBox(groupBox)
            rdvc_widgets['run_ndof_entry'].addItem('3')
            rdvc_widgets['run_ndof_entry'].addItem('6')
            rdvc_widgets['run_ndof_entry'].addItem('12')
            rdvc_widgets['run_ndof_entry'].setCurrentIndex(1)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_ndof_entry'])
            widgetno += 1

            rdvc_widgets['run_objf_label'] = QLabel(groupBox)
            rdvc_widgets['run_objf_label'].setText("Objective Function")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_objf_label'])
            rdvc_widgets['run_objf_entry'] = QComboBox(groupBox)
            rdvc_widgets['run_objf_entry'].addItem('sad')
            rdvc_widgets['run_objf_entry'].addItem('ssd')
            rdvc_widgets['run_objf_entry'].addItem('zssd')
            rdvc_widgets['run_objf_entry'].addItem('nssd')
            rdvc_widgets['run_objf_entry'].addItem('znssd')
            rdvc_widgets['run_objf_entry'].setCurrentIndex(4)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_objf_entry'])
            widgetno += 1

            rdvc_widgets['run_iterp_type_label'] = QLabel(groupBox)
            rdvc_widgets['run_iterp_type_label'].setText("Interpolation type")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_iterp_type_label'])
            rdvc_widgets['run_iterp_type_entry'] = QComboBox(groupBox)
            rdvc_widgets['run_iterp_type_entry'].addItem('Nearest')
            rdvc_widgets['run_iterp_type_entry'].addItem('Trilinear')
            rdvc_widgets['run_iterp_type_entry'].addItem('Tricubic')
            rdvc_widgets['run_iterp_type_entry'].setCurrentIndex(2)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_iterp_type_entry'])
            widgetno += 1

            # Add horizonal seperator
            separators.append(QFrame(groupBox))
            separators[-1].setFrameShape(QFrame.HLine)
            separators[-1].setFrameShadow(QFrame.Raised)
            formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
            widgetno += 1 

            rdvc_widgets['run_type_label'] = QLabel(groupBox)
            rdvc_widgets['run_type_label'].setText("Run type:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_type_label'])
            rdvc_widgets['run_type_entry'] = QComboBox(groupBox)
            rdvc_widgets['run_type_entry'].addItems(['Single', 'Bulk'])
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_type_entry'])
            widgetno += 1


            singleRun_groupBox = QGroupBox("Single Run Parameters")
            singleRun_groupBox.setMinimumSize(QSize(0,0))
            self.singleRun_groupBox = singleRun_groupBox
            singleRun_groupBoxFormLayout = QFormLayout(singleRun_groupBox)
            internalWidgetVerticalLayout.addWidget(singleRun_groupBox)

            widgetno = 0

            rdvc_widgets['subvol_points_label'] = QLabel(singleRun_groupBox)
            rdvc_widgets['subvol_points_label'].setText("Points in Subvolume:")
            singleRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['subvol_points_label'])
        
            rdvc_widgets['subvol_points_spinbox'] = QSpinBox(singleRun_groupBox)
            rdvc_widgets['subvol_points_spinbox'].setMinimum(1)
            rdvc_widgets['subvol_points_spinbox'].setMaximum(20000)
            singleRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['subvol_points_spinbox'])
            widgetno += 1

            bulkRun_groupBox = QGroupBox("Bulk Run Parameters")
            self.bulkRun_groupBox = bulkRun_groupBox
            bulkRun_groupBoxFormLayout = QFormLayout(bulkRun_groupBox)
            internalWidgetVerticalLayout.addWidget(bulkRun_groupBox)
            bulkRun_groupBox.hide()

            validatorint = QtGui.QIntValidator()

            widgetno = 0

            rdvc_widgets['radius_range_min_label'] = QLabel(bulkRun_groupBox)
            rdvc_widgets['radius_range_min_label'].setText("Radius min ")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['radius_range_min_label'])
            rdvc_widgets['radius_range_min_value'] = QLineEdit(bulkRun_groupBox)
            rdvc_widgets['radius_range_min_value'].setValidator(validatorint)
            
            current_radius = self.isoValueEntry.text()
            
            rdvc_widgets['radius_range_min_value'].setText(current_radius)
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['radius_range_min_value'])
            #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
            #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
            widgetno += 1
            # radius range max
            rdvc_widgets['radius_range_max_label'] = QLabel(bulkRun_groupBox)
            rdvc_widgets['radius_range_max_label'].setText("Radius max ")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['radius_range_max_label'])
            rdvc_widgets['radius_range_max_value'] = QLineEdit(bulkRun_groupBox)
            rdvc_widgets['radius_range_max_value'].setValidator(validatorint)
            rdvc_widgets['radius_range_max_value'].setText("100")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['radius_range_max_value'])
            #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
            #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
            widgetno += 1
            # radius range step
            rdvc_widgets['radius_range_step_label'] = QLabel(bulkRun_groupBox)
            rdvc_widgets['radius_range_step_label'].setText("Radius step ")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['radius_range_step_label'])
            rdvc_widgets['radius_range_step_value'] = QLineEdit(bulkRun_groupBox)
            rdvc_widgets['radius_range_step_value'].setValidator(validatorint)
            rdvc_widgets['radius_range_step_value'].setText("0")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['radius_range_step_value'])
            #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
            #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
            widgetno += 1
            
            separators = [QFrame(groupBox)]
            separators[-1].setFrameShape(QFrame.HLine)
            separators[-1].setFrameShadow(QFrame.Raised)
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
            widgetno += 1
            
            # NUMBER OF POINTS IN SUBVOLUME min
            rdvc_widgets['points_in_subvol_range_min_label'] = QLabel(bulkRun_groupBox)
            rdvc_widgets['points_in_subvol_range_min_label'].setText("number of points in subvolume min ")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['points_in_subvol_range_min_label'])
            rdvc_widgets['points_in_subvol_range_min_value'] = QLineEdit(bulkRun_groupBox)
            rdvc_widgets['points_in_subvol_range_min_value'].setValidator(validatorint)
            rdvc_widgets['points_in_subvol_range_min_value'].setText("10")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['points_in_subvol_range_min_value'])
            #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
            #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
            widgetno += 1
            # overlap range max
            rdvc_widgets['points_in_subvol_range_max_label'] = QLabel(bulkRun_groupBox)
            rdvc_widgets['points_in_subvol_range_max_label'].setText("number of points in subvolume max ")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['points_in_subvol_range_max_label'])
            rdvc_widgets['points_in_subvol_range_max_value'] = QLineEdit(bulkRun_groupBox)
            rdvc_widgets['points_in_subvol_range_max_value'].setValidator(validatorint)
            rdvc_widgets['points_in_subvol_range_max_value'].setText("100")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['points_in_subvol_range_max_value'])
            #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
            #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
            widgetno += 1
            # overlap range step
            rdvc_widgets['points_in_subvol_range_step_label'] = QLabel(bulkRun_groupBox)
            rdvc_widgets['points_in_subvol_range_step_label'].setText("number of points in subvolume step ")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['points_in_subvol_range_step_label'])
            rdvc_widgets['points_in_subvol_range_step_value'] = QLineEdit(bulkRun_groupBox)
            rdvc_widgets['points_in_subvol_range_step_value'].setValidator(validatorint)
            rdvc_widgets['points_in_subvol_range_step_value'].setText("0")
            bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['points_in_subvol_range_step_value'])
            #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
            #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
            widgetno += 1

            button_groupBox = QGroupBox()
            self.button_groupBox = button_groupBox
            button_groupBoxFormLayout = QFormLayout(button_groupBox)
            internalWidgetVerticalLayout.addWidget(button_groupBox)

            rdvc_widgets['run_button'] = QPushButton(button_groupBox)
            rdvc_widgets['run_button'].setText("Run DVC")
            #rdvc_widgets['run_button'].setEnabled(False)
            button_groupBoxFormLayout.setWidget(widgetno, QFormLayout.SpanningRole, rdvc_widgets['run_button'])
            widgetno += 1

            # rdvc_widgets['run_config'] = QPushButton(button_groupBox)
            # rdvc_widgets['run_config'].setText("Generate Run Config")
            # #rdvc_widgets['run_config'].setEnabled(False)
            # button_groupBoxFormLayout.setWidget(widgetno, QFormLayout.SpanningRole, rdvc_widgets['run_config'])
            # widgetno += 1

            #Add button functionality:
            #rdvc_widgets['dir_browse'].clicked.connect(lambda: self.select_directory(rdvc_widgets['dir_name_label'], [rdvc_widgets['run_button'], rdvc_widgets['run_config']], self.run_folder, "Select a directory to save the run", "run"))
            #rdvc_widgets['roi_browse'].clicked.connect(lambda: self.select_roi(rdvc_widgets['roi_name_label'], rdvc_widgets['run_button']))
            rdvc_widgets['run_type_entry'].currentIndexChanged.connect(self.show_run_groupbox)
            rdvc_widgets['run_button'].clicked.connect(self.create_config_worker)

            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)

            self.rdvc_widgets = rdvc_widgets

    def show_run_groupbox(self):
        if self.rdvc_widgets['run_type_entry'].currentIndex() == 0:
            self.bulkRun_groupBox.hide()
            self.singleRun_groupBox.show()
        else:
            self.singleRun_groupBox.hide()
            self.bulkRun_groupBox.show()

    def select_directory(self, label, next_buttons, folder, title, type):
        dialogue = QFileDialog()
        selection = dialogue.getExistingDirectory(self,title)
        folder = []
        folder.append(selection)
        label.setText(folder[0][len(working_directory):])
        if folder[0]:
            for button in next_buttons:
                button.setEnabled(True)
            if(type == "run"):
                self.run_folder = [folder[0][len(working_directory):]]
            elif(type == "results"):
                self.results_folder = folder
        #print(self.run_folder)
        #print(self.results_folder)

    def select_roi(self, label, next_button):
        dialogue = QFileDialog()
        f = dialogue.getOpenFileName(self,"Select a roi")
        array = f[0].split("/")
        self.roi = array[-1]
        label.setText(self.roi)
        if self.roi:
            next_button.setEnabled(True)

    def create_config_worker(self):
        if hasattr(self, 'translate'):
            if self.translate is None:
                self.warningDialog("Complete image registration first.", "Error")
                return
        if not hasattr(self, 'translate'):
            self.warningDialog("Complete image registration first.", "Error")
            return

        if self.singleRun_groupBox.isVisible():
            if not self.roi:
                self.warningDialog(window_title="Error", 
                               message="Create or load a pointcloud on the viewer first." )
                return
        else:
            if not self.mask_reader:
                self.warningDialog(window_title="Error", 
                               message="Load a mask on the viewer first" )
                progress_callback.emit(100)
                return
        
        folder_name = "_" + self.rdvc_widgets['name_entry'].text()

        results_folder = os.path.join(tempfile.tempdir, "Results")

        new_folder = os.path.join(results_folder, folder_name)

        if os.path.exists(new_folder):
            self.warningDialog(window_title="Error", 
                                message="This directory already exists. Please choose a different name." )
            return

        self.config_worker = Worker(self.create_run_config)
        self.create_progress_window("Loading", "Generating Run Config")
        self.config_worker.signals.progress.connect(self.progress)
        self.config_worker.signals.finished.connect(self.run_external_code)
        self.threadpool.start(self.config_worker)  
        self.progress_window.setValue(10)
        

    def create_run_config(self, progress_callback = None):
        folder_name = "_" + self.rdvc_widgets['name_entry'].text()

        results_folder = os.path.join(tempfile.tempdir, "Results")
        os.mkdir(os.path.join(results_folder, folder_name))

        if self.singleRun_groupBox.isVisible():
            setting = "single"
        else:
            setting = "bulk"

        #Prepare the config files.
        self.points = self.rdvc_widgets['run_points_spinbox'].value()

        if setting == "single":
            self.subvolume_points = [self.rdvc_widgets['subvol_points_spinbox'].value()]
            self.radii = [self.pointcloud_parameters['pointcloud_radius_entry'].text()]
            self.roi_files = [self.roi]
            pointcloud_new_file = results_folder + "/" + folder_name +  "/_" + str(self.pointcloud_parameters['pointcloud_radius_entry'].text() + ".roi")
            shutil.copyfile(self.roi, pointcloud_new_file)
            
        else:
            xmin = int(self.rdvc_widgets['points_in_subvol_range_min_value'].text())
            xmax = int(self.rdvc_widgets['points_in_subvol_range_max_value'].text())
            xstep = int(self.rdvc_widgets['points_in_subvol_range_step_value'].text())

            if xstep != 0:
                if xmax > xmin:
                    N = (xmax-xmin)//xstep + 1
                    self.subvolume_points = [xmin + i * xstep for i in range(N)]
                else:
                    self.warningDialog("Points in subvolume. Min ({}) value higher than Max ({})".format(
                            xmin, xmax) , window_title="Value Error")
                    return
            else:
                self.subvolume_points = [xmin]

            xmin = int(self.rdvc_widgets['radius_range_min_value'].text())
            xmax = int(self.rdvc_widgets['radius_range_max_value'].text())
            xstep = int(self.rdvc_widgets['radius_range_step_value'].text())
            if xstep != 0:
                if xmax > xmin:
                    N = (xmax-xmin)//xstep + 1
                    self.radii = [xmin + i * xstep for i in range(N)]
                else:
                    self.warningDialog("Radius. Min ({}) value higher than Max ({})".format(
                            xmin, xmax), window_title="Value Error", 
                        )
                    return
            else:
                self.radii = [xmin]

            self.roi_files = []
            #print(self.radii)
            radius_count = 0
            for radius in self.radii:
                #print(radius)
                radius_count+=1
                filename = "Results/" + folder_name + "/_" + str(radius) + ".roi"
                #print(filename)
                self.createPointCloud(filename, radius)
                self.roi_files.append(os.path.join(tempfile.tempdir, filename))
                #print("completed radius")
                progress_callback.emit(radius_count/len(self.radii)*90)
            #print("finished making pointclouds")

            print(self.roi_files)

        print("DVC in: ", self.dvc_input_image)
            
        
        if(self.image_copied[0]):
            self.reference_file = self.dvc_input_image[0][0]
        else:
            self.reference_file = self.dvc_input_image[0][0][len(working_directory) + 1:]

        if(self.image_copied[1]):
            self.correlate_file = self.dvc_input_image[1][0]
        else:
            self.correlate_file = self.dvc_input_image[1][0][len(working_directory) + 1:]

        run_config = {}
        run_config['points'] = self.points
        run_config['subvolume_points'] = self.subvolume_points
        run_config['cloud_radii'] = self.radii
        run_config['reference_file'] = self.reference_file
        run_config['correlate_file'] = self.correlate_file
        run_config['roi_files']= self.roi_files
        run_config['vol_bit_depth'] = 8
        run_config['vol_hdr_lngth'] = 96
        run_config['dims']=[self.vis_widget_2D.image_data.GetDimensions()[0],self.vis_widget_2D.image_data.GetDimensions()[1],self.vis_widget_2D.image_data.GetDimensions()[2]] #image dimensions

        run_config['subvol_geom'] = self.pointcloud_parameters['pointcloud_volume_shape_entry'].currentText().lower()
        run_config['subvol_npts'] = self.subvolume_points

        run_config['disp_max'] = self.rdvc_widgets['run_max_displacement_entry'].value(), #38 for test image
        run_config['dof'] = self.rdvc_widgets['run_ndof_entry'].currentText()
        run_config['obj'] = self.rdvc_widgets['run_objf_entry'].currentText()
        run_config['interp_type'] = self.rdvc_widgets['run_iterp_type_entry'].currentText().lower()

        if (hasattr(self, 'translate')):
            run_config['rigid_trans'] = str(self.translate.GetTranslation()[0]*-1) + " " + str(self.translate.GetTranslation()[1]*-1) + " " + str(self.translate.GetTranslation()[2]*-1)
        else:
            run_config['rigid_trans']= "0.0 0.0 0.0"


        self.run_folder = os.path.join(results_folder, folder_name)
        run_config['run_folder']= self.run_folder

        suffix_text = "run_config"

        self.run_config_file = os.path.join(tempfile.tempdir, "Results/" +folder_name + "/_" + suffix_text + ".json")

        with open(self.run_config_file, "w+") as tmp:
            json.dump(run_config, tmp)
            print("Saving")

        progress_callback.emit(100)
        

    def run_external_code(self):
        #print("About to run dvc")

        self.create_progress_window("Running", "Running DVC code", 100, self.cancel_run)
        self.progress_window.setValue(1)

        self.process = QtCore.QProcess(self)
        self.process.setWorkingDirectory(working_directory)
        #self.process.setStandardOutputFile("QProcess_Output.txt") #use in testing to get errors from QProcess
        self.process.setStandardErrorFile("QProcess_Error.txt") #use in testing to get errors from QProcess
        self.process.readyRead.connect(lambda: self.update_progress(exe = True))
        self.process.finished.connect(self.finished_run)

        #python_file = os.path.abspath("dvc_runner.exe")
        python_file = os.path.abspath("dvc_runner.py")
        #self.process.start(python_file, [self.run_config_file])

        pythonCommand = "python " + "dvc_runner.py" + " " + self.run_config_file

        #print (pythonCommand)

        self.process.start(pythonCommand)

        self.cancelled = False



    def update_progress(self, exe = None):
        if exe:
            line_b = self.process.readLine()
            line = str(line_b,"utf-8")
            #print(line)
            if len(line) > 4:
                num = float(line[:3]) #weird delay means isn't correct
                if num > self.progress_window.value() and self.progress_window.value()<99:
                    self.progress_window.setValue(num)
        else:
            if (self.progress_window.value()<1):
                self.progress_window.setValue(1)

            self.progress_window.setValue(self.progress_window.value()+1)


    def finished_run(self):
        #print("Completed all runs")
        if not self.cancelled:
            #print("cancelled false")
            self.result_widgets['run_entry'].addItem(self.rdvc_widgets['name_entry'].text())
            self.progress_window.setValue(100)
            self.progress_window.close()
            self.status.showMessage("Ready")
            self.alert = QMessageBox(QMessageBox.NoIcon,"Success","The DVC code ran successfully.", QMessageBox.Ok) 
            self.alert.show()
        if self.cancelled:
            #print("cancelled true")
            self.progress_window.setValue(100)
        #self.createVectors(filename, dimensions=3)

    def cancel_run(self):
         print(self.progress_window.value())
         self.status.showMessage("Run cancelled")
         self.process.kill()
         self.alert = QMessageBox(QMessageBox.NoIcon,"Cancelled","The run was cancelled.", QMessageBox.Ok)  
         self.alert.show()
         self.cancelled = True

# DVC Results Panel:
    def CreateViewDVCResultsPanel(self):
            self.dvc_results_panel = generateUIDockParameters(self, "6 - DVC Results")
            dockWidget = self.dvc_results_panel[0]
            dockWidget.setObjectName("DVCResultsPanel")
            internalWidgetVerticalLayout = self.dvc_results_panel[4]
            groupBox = self.dvc_results_panel[5]
            groupBox.setTitle('View Results')
            formLayout = self.dvc_results_panel[6]

            dockWidget.visibilityChanged.connect(partial(self.displayHelp, panel_no = 5))

            #Create the widgets:
            widgetno = 1

            result_widgets = {}

            result_widgets['run_label'] = QLabel(groupBox)
            result_widgets['run_label'].setText("Select a run:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['run_label'])
            result_widgets['run_entry'] = QComboBox(groupBox)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['run_entry'])
            widgetno += 1

            separators = []
            separators.append(QFrame(groupBox))
            separators[-1].setFrameShape(QFrame.HLine)
            separators[-1].setFrameShadow(QFrame.Raised)
            formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
            widgetno += 1  

            result_widgets['graphs_button'] = QPushButton("Display Graphs")
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['graphs_button'])
            widgetno += 1

            separators.append(QFrame(groupBox))
            separators[-1].setFrameShape(QFrame.HLine)
            separators[-1].setFrameShadow(QFrame.Raised)
            formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
            widgetno += 1  

            result_widgets['pc_label'] = QLabel(groupBox)
            result_widgets['pc_label'].setText("Pointcloud Radius:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['pc_label'])
            result_widgets['pc_entry'] = QComboBox(groupBox)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['pc_entry'])
            widgetno += 1

            result_widgets['subvol_label'] = QLabel(groupBox)
            result_widgets['subvol_label'].setText("Points in Subvolume:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['subvol_label'])
            result_widgets['subvol_entry'] = QComboBox(groupBox)
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['subvol_entry'])
            widgetno += 1

            result_widgets['vec_label'] = QLabel(groupBox)
            result_widgets['vec_label'].setText("View vectors:")
            formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['vec_label'])

            result_widgets['vec_entry'] = QComboBox(groupBox)
            result_widgets['vec_entry'].addItems(['None', '2D', '3D'])
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['vec_entry'])
            widgetno += 1

            result_widgets['load_button'] = QPushButton("View Pointcloud/Vectors")
            formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['load_button'])
            widgetno += 1

            result_widgets['run_entry'].currentIndexChanged.connect(self.show_run_pcs)
            
            result_widgets['load_button'].clicked.connect(self.load_results)

            result_widgets['graphs_button'].clicked.connect(self.create_graphs_window)

            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)
            self.result_widgets = result_widgets

    def show_run_pcs(self):
        #show pointcloud files in list
        self.result_widgets['pc_entry'].clear()
        self.result_widgets['subvol_entry'].clear()

        directory = os.path.join(tempfile.tempdir, "Results/_" + self.result_widgets['run_entry'].currentText())
        self.results_folder = directory

        file_list=[]
        self.result_list=[]
        points_list=[]

        for r, d, f in os.walk(directory):
            for _file in f:
                if '.roi' in _file:
                    self.result_widgets['pc_entry'].addItem((_file.split('_')[-1]).split('.')[0])

                if _file.endswith(".disp"):
                    file_name= _file[:-5]
                    file_path = directory + "/" + file_name
                    result = run_outcome(file_path)
                    self.result_list.append(result)
                    #print(result.subvol_points)
                    if str(result.subvol_points) not in points_list:
                        points_list.append(str(result.subvol_points))
                        #self.result_widgets['pc_entry'].addItem(str(result.subvol_radius))

        
        self.result_widgets['subvol_entry'].addItems(points_list)
                


    def load_results(self):

        print("LOAD RESULTS")
        print("Number of results:")
        if hasattr(self, 'result_list'):
            print(len(self.result_list))
            radius = int(self.result_widgets['pc_entry'].currentText())
            subvol_points = int(self.result_widgets['subvol_entry'].currentText())

            if(subvol_points == ""):
                self.warningDialog("An error occurred with this run so the results could not be displayed.", "Error")

            else:

                results_folder = os.path.join(tempfile.tempdir, "Results/_" + self.result_widgets['run_entry'].currentText())
                self.roi = results_folder + "\\_" + str(radius) + ".roi"
                print("New roi is", self.roi)
                self.results_folder = results_folder

                if (self.result_widgets['vec_entry'].currentText() == "None"):
                    self.PointCloudWorker("load pointcloud file")

                else: 

                    for result in self.result_list:
                        #print(radius)
                        #print(result.subvol_radius)
                        if result.subvol_radius == radius:
                            print("Radius match")
                            print(result.subvol_points)
                            print(subvol_points)
                            if result.subvol_points == subvol_points:
                                print("SUB MATCH")
                                run_file = result.disp_file_name
                                run_file = results_folder + "\\" + run_file.split('/')[-1]

                    if(self.result_widgets['vec_entry'].currentText() == "2D"):
                        self.PointCloudWorker("load vectors", filename = self.roi, disp_file = run_file, vector_dim = 2)
                    elif(self.result_widgets['vec_entry'].currentText() == "3D"):
                        self.PointCloudWorker("load vectors", filename = None, disp_file = run_file, vector_dim = 3)


    def create_graphs_window(self, results_folder=None):
        print("Create graphs")
        self.results_folder = os.path.join(tempfile.tempdir, "Results/_" + self.result_widgets['run_entry'].currentText())
        print(self.results_folder)
        print(type(self.results_folder))
        # if results_folder == None:
        #     results_folder = self.results_folder
        if hasattr(self, 'results_folder'):
            if self.results_folder is not None:
                self.graph_window = GraphsWindow(self)
                self.graph_window.show()

                file_list=[]
                result_list=[]
                plot_titles = ["Objective Minimum", "Displacement in x", "Displacement in y", "Displacement in z", "Change in phi", "Change in theta", "Change in psi"]
                #print(results_folder[0])
                for f in listdir(self.results_folder):
                    if f.endswith(".disp"):
                        file_name= f[:-5]
                        file_path = self.results_folder + "/" + file_name
                        result = run_outcome(file_path)
                        result_list.append(result)
                
                        GraphWidget = ResultsWidget(self.graph_window, result, plot_titles)
                        dock1 = QDockWidget(result.title,self)
                        dock1.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
                        dock1.setWidget(GraphWidget)
                        self.graph_window.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock1)
            
                prev = None

                for current_dock in self.graph_window.findChildren(QDockWidget):
                    if self.graph_window.dockWidgetArea(current_dock) == QtCore.Qt.RightDockWidgetArea:
                        existing_widget = current_dock

                        if prev:
                            self.graph_window.tabifyDockWidget(prev,current_dock)
                        prev= current_dock
                
                SummaryTab = SummaryWidget(self.graph_window, result_list)#, summary_plot_titles)
                dock = QDockWidget("Summary",self)
                dock.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)
                dock.setWidget(SummaryTab)
                self.graph_window.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock)
                self.graph_window.tabifyDockWidget(prev,dock)

                dock.raise_() # makes summary panel the one that is open by default.

#Dealing with saving and loading sessions:

    def closeEvent(self, event):
        self.CreateSaveWindow("Quit without Saving", event) 
        
    def CreateSaveWindow(self, cancel_text, event):
        self.SaveWindow = CreateSaveSessionWindow(self, event)
        self.SaveWindow.show()

    def SaveSession(self, text_value, compress, event):
        #Save window geometry and state of dockwindows
        g = self.saveGeometry()
        self.config['geometry'] =  bytes(g.toHex()).decode('ascii') # can't save qbyte array to json so have to convert it
        #w = self.saveState()
        #self.config['window_state'] = bytes(w.toHex()).decode('ascii')
        
        #save values for select image panel:
        if len(self.image[0]) > 0: 
            if(self.copy_files):
                self.config['copy_files'] = self.copy_files

            #we need to change location of image to being the name of the image w/o directories
            image = [[],[]]
            for i in self.image[0]:
                if self.image_copied[0]:
                    array = i.split("\\")
                    image[0].append(array[-1])
                else:
                    image[0].append(i)
            for j in self.image[1]:
                if self.image_copied[1]:
                    array=j.split("\\")
                    image[1].append(array[-1])
                else:
                   image[1].append(j)

            self.config['image']=image
            self.config['image_copied']=self.image_copied
            self.config['image_orientation']=self.vis_widget_2D.frame.viewer.GetSliceOrientation()
            self.config['current_slice']=self.vis_widget_2D.frame.viewer.GetActiveSlice()

            #we need to do the same for the dvc input image:
            dvc_input_image = [[],[]]
            for i in self.dvc_input_image[0]:
                if self.image_copied[0]:
                    array = i.split("\\")
                    dvc_input_image[0].append(array[-1])
                else:
                    dvc_input_image[0].append(i)
            for j in self.dvc_input_image[1]:
                if self.image_copied[1]:
                    array=j.split("\\")
                    dvc_input_image[1].append(array[-1])
                else:
                   dvc_input_image[1].append(j)
            self.config['dvc_input_image']=dvc_input_image

            if (self.roi):
                if self.roi.startswith("temp\\"):
                    if "Results/_" in self.roi:
                        self.roi = self.roi[self.roi.find("Results/"):]
                    
                    else:
                        print(self.roi)
                        print("starts with temp")
                        array = self.roi.split("\\")
                        self.roi  = array[-1]

            print("Resulting roi", self.roi)

            self.config['roi_file'] = self.roi 

        if hasattr(self, 'mask_file'):
            self.config['mask_file']=self.mask_file
            self.config['mask_details']=self.mask_details
        
        self.config['pointCloud_details']=self.pointCloud_details

        #save values for Run DVC panel
        if hasattr(self,'subvolume_points'): #check if this test correct
            if self.subvolume_points is not None:
                self.config['subvol_points'] = self.subvolume_points
                self.config['points'] = self.points
                self.config['roi_file'] = self.roi
                self.config['run_button_enabled'] = True
                self.config['run_folder'] = self.run_folder

        #print(len(self.results_folder))
        # if self.gg_widgets['gen_button'].isEnabled():
        #     self.config['results_folder'] = self.results_folder
        #     if(hasattr(self, 'graph_window') and self.graph_window.isVisible()):
        #         self.config['results_open'] = True
        #     else:
        #         self.config['results_open'] = False

        self.config['pointcloud_loaded'] = self.pointCloudLoaded

        #Image Registration:
        
        if hasattr(self, 'translate'):
            if self.translate is not None:
                self.config['reg_translation'] = (self.translate.GetTranslation()[0],self.translate.GetTranslation()[1],self.translate.GetTranslation()[2])
            else:
                self.config['reg_translation'] = None

        else:
            self.config['reg_translation'] = None
        if hasattr(self, 'point0_loc'):
            self.config['point0'] = eval(self.registration_parameters['point_zero_entry'].text())
        else:
            self.config['point0'] = None

        self.config['reg_sel'] = self.registration_parameters['register_on_selection_check'].isChecked()
        self.config['reg_sel_size'] = self.registration_parameters['registration_box_size_entry'].value()
        # size of reg box
        # if tickbox checked

        pc = self.pointcloud_parameters

        #Pointcloud panel:
        self.config['pc_subvol_rad'] = pc['pointcloud_radius_entry'].text()
        self.config['pc_subvol_shape'] = pc['pointcloud_volume_shape_entry'].currentIndex()
        self.config['pc_dim'] = pc['pointcloud_dimensionality_entry'].currentIndex()
        self.config['pc_overlapx'] = pc['pointcloud_overlap_x_entry'].value()
        self.config['pc_overlapy'] = pc['pointcloud_overlap_y_entry'].value()
        self.config['pc_overlapz'] = pc['pointcloud_overlap_z_entry'].value()
        self.config['pc_rotx'] = pc['pointcloud_rotation_x_entry'].text()
        self.config['pc_roty'] = pc['pointcloud_rotation_y_entry'].text()
        self.config['pc_rotz'] = pc['pointcloud_rotation_z_entry'].text()
  
        now = datetime.now()
        now_string = now.strftime("%d-%m-%Y-%H-%M")
        self.config['datetime'] = now_string
        #save time to temp file

        user_string = text_value
        
        suffix_text = "_" + user_string + "_" + now_string 

        tempdir = shutil.move(tempfile.tempdir, 'temp/'+suffix_text)
        tempfile.tempdir = tempdir

        fd, f = tempfile.mkstemp(suffix=suffix_text + ".json", dir = tempfile.tempdir) #could not delete this using rmtree?

        with open(f, "w+") as tmp:
            json.dump(self.config, tmp)
            print("Saving")

        os.close(fd)

        self.create_progress_window("Saving","Saving")
  
        zip_worker = Worker(self.ZipDirectory, tempfile.tempdir, compress)
        if type(event) == QCloseEvent:
            zip_worker.signals.finished.connect(lambda: self.RemoveTemp(event))
        else:
            zip_worker.signals.finished.connect(self.CloseSaveWindow)
        zip_worker.signals.progress.connect(self.progress)
        self.threadpool.start(zip_worker)
        
        if compress:
            self.show_zip_progress(tempfile.tempdir, tempfile.tempdir +'.zip', 0.7)
        else:
            self.show_zip_progress(tempfile.tempdir, tempfile.tempdir +'.zip', 1)

    
    def CloseSaveWindow(self):
        if hasattr(self, 'progress_window'):
            self.progress_window.setValue(100)
    
        self.SaveWindow.close()
       
    def ZipDirectory(self, directory, compress, progress_callback):
        zip = zipfile.ZipFile(directory + '.zip', 'a')#, compression = zipfile.ZIP_STORED) #compression=zipfile.ZIP_DEFLATED)

        for r, d, f in os.walk(directory):
            #for folder in d:
                #zip.write(os.path.join(directory, folder),folder, compress_type=zipfile.ZIP_DEFLATED)
            for _file in f:
                if compress:
                    compress_type = zipfile.ZIP_DEFLATED
                else:
                    compress_type = zipfile.ZIP_STORED

                zip.write(os.path.join(r, _file),os.path.join(r, _file)[len(directory)+1:],compress_type=compress_type)#zipfile.ZIP_DEFLATED)
        zip.close()

        print("Finished zip")
        
    def progress(self, value):
        #print("progress emitted")
        if int(value) > self.progress_window.value():
            self.progress_window.setValue(value)

    def RemoveTemp(self, event):
        if hasattr(self, 'progress_window'):
            self.progress_window.setLabelText("Closing")
            self.progress_window.setMaximum(100)
            self.progress_window.setValue(98)
        print("removed temp")
        shutil.rmtree(tempfile.tempdir)
        
        
        if hasattr(self, 'progress_window'):
            self.progress_window.setValue(100)
        
        self.SaveWindow.close()
        QMainWindow.closeEvent(self, event)
        
    def show_zip_progress(self, folder, new_file_dest,ratio):
        print("in show zip progress")
        
        self.progress_window.setValue(10)

        temp_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    #print(fp)
                    temp_size += os.path.getsize(fp)

        while not os.path.exists(new_file_dest):
                time.sleep(0.01)

        zip_size = os.path.getsize(new_file_dest)

        while temp_size*ratio != zip_size and self.progress_window.value() < 98 and self.progress_window.value() !=-1:
                    #print((float(zip_size)/float(temp_size)*ratio)*100)
                    zip_size = os.path.getsize(new_file_dest)
                    #if self.progress_window.value() < 95:
                    #print((float(zip_size)/(float(temp_size)*ratio))*100)
                        
                    self.progress_window.setValue((float(zip_size)/(float(temp_size)*ratio))*100)
                    #else:
                    #    time.sleep(0.01)
                    time.sleep(0.1)
                    #zip_size = 0
        #print("Finished showing zip progress")
    
    def show_export_progress(self, folder, new_file_dest):
        
        self.progress_window.setValue(10)

        temp_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    #print(fp)
                    temp_size += os.path.getsize(fp)

        while not os.path.exists(new_file_dest):
                time.sleep(0.01)

        exp_size = 0
        for dirpath, dirnames, filenames in os.walk(new_file_dest):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    #print(fp)
                    exp_size += os.path.getsize(fp) 

        print(temp_size) 


        while temp_size != exp_size and self.progress_window.value() < 98 and self.progress_window.value() !=-1:
                print((float(exp_size)/(float(temp_size)))*100)
                self.progress_window.setValue((float(exp_size)/(float(temp_size)))*100)
                time.sleep(0.01)

                exp_size = 0
                for dirpath, dirnames, filenames in os.walk(folder):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        #print(fp)
                        exp_size += os.path.getsize(fp)
                print(exp_size)
                print(self.progress_window.value())  

    def export_session(self):
        #print("In select image")
        dialogue = QFileDialog()
        folder= dialogue.getExistingDirectory(self, "Select a Folder")
        now = datetime.now()
        now_string = now.strftime("%d-%m-%Y-%H-%M")
        export_location = folder + "\_" + now_string
        if folder:
            self.create_progress_window("Exporting","Exporting Files",max=100)
            self.progress_window.setValue(5)
            export_worker = Worker(self.exporter, export_location)
            export_worker.signals.finished.connect(self.progress_complete)
            self.threadpool.start(export_worker)
            self.show_export_progress(tempfile.tempdir, export_location)

    def exporter(self, export_location, progress_callback):
        shutil.copytree(tempfile.tempdir, export_location)

                
    def CreateSessionSelector(self, stage): 
        temp_folders = []
        print ("TEMP FOLDER IS ", self.temp_folder)
        if self.temp_folder is not None:
            for r, d, f in os.walk(self.temp_folder):
                for _file in f:
                    if '.zip' in _file:
                        array = _file.split("_")
                        if(len(array)>1):
                            name = array[-2] + " " + array[-1]
                            name = name[:-4]
                            temp_folders.append(name)

        if len(temp_folders) ==0 and stage =="new window":
            return
        elif len(temp_folders) == 0:
            self.e('', '', '')
            error_title = "LOAD ERROR"
            error_text = "There are no previously saved sessions to load."
            self.displayFileErrorDialog(message=error_text, title=error_title)
            return #Exits the LoadSession function

        else:     
            self.SessionSelectionWindow = CreateSessionSelectionWindow(self, temp_folders)
            self.SessionSelectionWindow.show()

    def NewSession(self):
        self.InitialiseSessionVars()
        self.LoadSession() #Loads blank session
        self.resetRegistration()

        #other possibility for loading new session is closing and opening window:
        # self.close()
        # subprocess.Popen(['python', 'dvc_interface.py'], shell = True) 

    def load_config_worker(self, selected_text, progress_callback = None): 
        date_and_time = selected_text.split(' ')[-1]
        #print(date_and_time)
        selected_folder = ""

        for r, d, f in os.walk(self.temp_folder):
            for _file in f:
                if date_and_time + '.zip' in _file:
                    
                    selected_folder_name = _file
                    #print(selected_folder_name)
                    selected_folder =  os.path.join(self.temp_folder, _file)
                    break

        progress_callback.emit(50)
        
        shutil.unpack_archive(selected_folder, selected_folder[:-4])
        loaded_tempdir = selected_folder[:-4]

        progress_callback.emit(70)

        #Create folder to store masks if one doesn't exist
        mask_folder_exists = False
        results_folder_exists = False
        for r, d, f in os.walk(loaded_tempdir):
            for directory in d:
                if 'Masks' in directory:
                    mask_folder_exists = True
                if 'Results' in directory:
                    results_folder_exists = True

        if not mask_folder_exists:
            os.mkdir(os.path.join(loaded_tempdir, "Masks"))
        if not results_folder_exists:
            os.mkdir(os.path.join(loaded_tempdir, "Results"))
        
            

        #print(tempfile.tempdir)

        if tempfile.tempdir != loaded_tempdir: # if we are not loading the same session that we already had open
            shutil.rmtree(tempfile.tempdir) 

        progress_callback.emit(90)

        tempfile.tempdir = loaded_tempdir
        #print("working tempdir")
        #print(tempfile.tempdir)
        #selected_file = ""
 
        json_filename = date_and_time + ".json"
        for r, d, f in os.walk(loaded_tempdir):
            for _file in f:
                if json_filename in _file:
                    #print(file)
                    selected_file = os.path.join(loaded_tempdir, _file)

        with open(selected_file) as tmp:
            self.config = json.load(tmp)
        
        os.remove(selected_file)
        progress_callback.emit(100)
       
    def LoadSession(self):
        
        self.loading_session = True

        self.mask_parameters['masksList'].clear()
        self.pointcloud_parameters['pointcloudList'].clear()
        
        
        #use info to update the window:
        if 'geometry' in self.config:
            g = QByteArray.fromHex(bytes(self.config['geometry'], 'ascii'))
            #w = QByteArray.fromHex(bytes(self.config['window_state'], 'ascii'))
            self.restoreGeometry(g)
            #self.restoreState(w)

        if 'pointcloud_loaded' in self.config: #whether a pointcloud was displayed when session saved
            self.pointCloudLoaded = self.config['pointcloud_loaded']
            if self.pointCloudLoaded:
                self.roi = self.config['roi_file']
                if  "Results/_" in self.roi or not "/" in self.roi:
                    self.roi = os.path.join(tempfile.tempdir, self.roi)

        #pointcloud files could still exist even if there wasn't a pointcloud displayed when the session was saved.
        pointcloud_files = []
        #get list of pointcloud files:
        for r, d, f in os.walk(tempfile.tempdir):
            for _file in f:
                if '.roi' in _file:
                    pointcloud_files.append(_file)
        if len(pointcloud_files) >0:
            self.pointcloud_parameters['pointcloudList'].addItems(pointcloud_files)
            self.pointcloud_parameters['pointcloudList'].setEnabled(True)
            self.pointcloud_parameters['pointcloudList'].setCurrentText("latest_selection.mha")
            self.pointcloud_parameters['loadButton'].setEnabled(True)  
        else:
            self.pointcloud_parameters['pointcloudList'].setEnabled(False)
            self.mask_parameters['loadButton'].setEnabled(False)

        if 'image' in self.config:
            #print("Image in config")
            self.image_copied = self.config['image_copied']
            
            for j in range(2):
                
                for i in self.config['image'][j]:

                    #save paths to images to variable
                    if self.config['image_copied'][j]:
                        path = os.path.join(tempfile.tempdir, i)
                        print("The path is")
                        print(path)
                        self.image[j].append(path)
                    else:
                        path = i
                        self.image[j].append(i)
                    if not os.path.exists(path):
                            self.e(
                            '', '', 'This file has been deleted or moved to another location. Therefore this session cannot be loaded. \
Please move the file back to this location and reload the session, select a different session to load or start a new session')
                            error_title = "READ ERROR"
                            error_text = "Error reading file: ({filename})".format(filename=i)
                            self.displayFileErrorDialog(message=error_text, title=error_title)
                            return #Exits the LoadSession function

                
                for i in self.config['dvc_input_image'][j]:

                    #save paths to images to variable
                    if self.config['image_copied'][j]:
                        path = os.path.join(tempfile.tempdir, i)
                        print("The DVC input path is")
                        print(path)
                        self.dvc_input_image[j].append(path)
                    else:
                        path = i
                        self.dvc_input_image[j].append(i)
                    if not os.path.exists(path):
                            self.e(
                            '', '', 'This file has been deleted or moved to another location. Therefore this session cannot be loaded. \
Please move the file back to this location and reload the session, select a different session to load or start a new session')
                            error_title = "READ ERROR"
                            error_text = "Error reading file: ({filename})".format(filename=i)
                            self.displayFileErrorDialog(message=error_text, title=error_title)
                            return #Exits the LoadSession function
            
             # Set labels to display file names:
            if len(self.config['image'][0])>1:
                self.si_widgets['ref_file_label'].setText(self.config['image'][0][0].split("/")[-1] + " + " + str(len(self.config['image'][0])-1) + " more files.")
            else:
                self.si_widgets['ref_file_label'].setText(self.config['image'][0][0].split("/")[-1])
            
            if len(self.config['image'][1])>1:
                self.si_widgets['cor_file_label'].setText(self.config['image'][1][0].split("/")[-1] + " + " + str(len(self.config['image'][1])-1) + " more files.")
            elif self.config['image'][1]:
                self.si_widgets['cor_file_label'].setText(self.config['image'][1][0].split("/")[-1])                      

            #self.roi = self.config['roi_file']
        
            #if(self.roi):
                #self.si_widgets['roi_file_label'].setText(self.roi[0])
            
            self.si_widgets['cor_browse'].setEnabled(True)
            self.si_widgets['view_button'].setEnabled(True)

            if 'current_slice' in self.config:
                self.current_slice = self.config['current_slice']

            if 'image_orientation' in self.config:
                self.orientation = self.config['image_orientation']

            if 'mask_file' in self.config:
                self.mask_details=self.config['mask_details']
                self.mask_load = True
            else:
                self.mask_load = False

            if self.roi and not self.mask_load:
                self.no_mask_pc_load = True
                

            self.pointCloud_details = self.config['pointCloud_details']

            self.view_image()
            
                
        else:
            self.vis_widget_2D.createEmptyFrame()
            self.vis_widget_3D.createEmptyFrame()
            self.si_widgets['ref_file_label'].setText("")
            self.si_widgets['cor_file_label'].setText("")
            self.si_widgets['view_button'].setEnabled(False)
            self.si_widgets['cor_browse'].setEnabled(False)


        #Load state of Run DVC dockwidget
        if 'points' in self.config:

            self.subvolume_points = self.config['subvol_points'] 
            #self.rdvc_widgets['subvol_points_spinbox'].setValue(self.subvolume_points)

            self.points = self.config['points']
            self.rdvc_widgets['run_points_spinbox'].setValue(self.points)

            #self.roi = self.config['roi_file'] 


            #self.rdvc_widgets['run_button'].setEnabled(self.config['run_button_enabled'])
            #self.rdvc_widgets['run_config'].setEnabled(self.config['run_button_enabled'])

            self.run_folder = self.config['run_folder']
            #self.rdvc_widgets['dir_name_label'].setText(self.run_folder[0])
        
        else:
            self.subvolume_points = None 
            self.rdvc_widgets['subvol_points_spinbox'].setValue(self.rdvc_widgets['subvol_points_spinbox'].minimum())

            self.points = None
            self.rdvc_widgets['run_points_spinbox'].setValue(self.rdvc_widgets['run_points_spinbox'].minimum())

            #self.roi = None

            #self.rdvc_widgets['run_button'].setEnabled(False)
            #self.rdvc_widgets['run_config'].setEnabled(False)

            self.run_folder = [None]
            #self.rdvc_widgets['dir_name_label'].setText("")

        if 'results_folder' in self.config:
            self.results_folder = self.config['results_folder']
            #self.gg_widgets['dir_name_label'].setText(self.results_folder[0])
            #self.gg_widgets['gen_button'].setEnabled(True)
            if(self.config['results_open']):
                print("results open")
                if (hasattr(self, 'graph_window')):
                    plt.close('all') #closes all open figures
                    self.graph_window.close()
                self.create_graphs_window()
        else:
            self.results_folder = None
            #self.gg_widgets['dir_name_label'].setText("")
            #self.gg_widgets['gen_button'].setEnabled(False)
            if (hasattr(self, 'graph_window')):
                    plt.close('all') #closes all open figures
                    self.graph_window.close()

        if 'mask_file' in self.config:
            self.mask_parameters['loadButton'].setEnabled(True)
            mask_folder = os.path.join(tempfile.tempdir, "Masks")
            mask_files = []
            #get list of mask files:
            #print(mask_folder)
            for r, d, f in os.walk(mask_folder):
                for _file in f:
                    if '.mha' in _file:
                        #array = file.split("_")
                        #if(len(array)>1):
                            #name = array[-2] + " " + array[-1]
                            #name= array[-1]
                            #name = name[:-4]
                        mask_files.append(_file)
            self.mask_parameters['masksList'].addItems(mask_files)
            self.mask_parameters['masksList'].setEnabled(True)
            self.mask_parameters['masksList'].setCurrentText("latest_selection.mha")
            
        else:
            self.mask_parameters['masksList'].setEnabled(False)
            self.mask_parameters['loadButton'].setEnabled(False)   


        results_directory = os.path.join(tempfile.tempdir, "Results")

        for r, d, f in os.walk(results_directory):
            for directory in d:
                self.result_widgets['run_entry'].addItem(directory.split('_')[-1])

        self.reg_load = False
        if 'point0' in self.config:
            if self.config['point0']:
                self.reg_load = True

        #PC panel:

        pc = self.pointcloud_parameters

        if 'pc_subvol_rad' in  self.config:

            pc['pointcloud_radius_entry'].setText(self.config['pc_subvol_rad'])
            pc['pointcloud_volume_shape_entry'].setCurrentIndex(self.config['pc_subvol_shape'])
            pc['pointcloud_dimensionality_entry'].setCurrentIndex(self.config['pc_dim'])
            pc['pointcloud_overlap_x_entry'].setValue(self.config['pc_overlapx'])
            pc['pointcloud_overlap_y_entry'].setValue(self.config['pc_overlapy'])
            pc['pointcloud_overlap_z_entry'].setValue(self.config['pc_overlapz'])
            pc['pointcloud_rotation_x_entry'].setText(self.config['pc_rotx'])
            pc['pointcloud_rotation_y_entry'].setText(self.config['pc_roty'])
            pc['pointcloud_rotation_z_entry'].setText(self.config['pc_rotz'])


            #if hasattr(self, 'translate'):
                #self.config['reg_translation'] = (self.translate.GetTranslation()[0],self.translate.GetTranslation()[1],self.translate.GetTranslation()[2])
            #else:
                #self.config['reg_translation'] = None

            # if hasattr(self, 'point0_loc'):
            #     self.config['point0'] = self.point0_loc
            # else:
            #     self.config['point0'] = None



    def warningDialog(self, message='', window_title='', detailed_text=''):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Information)
        dialog.setText(message)
        dialog.setWindowTitle(window_title)
        dialog.setDetailedText(detailed_text)
        dialog.setStandardButtons(QMessageBox.Ok)
        retval = dialog.exec_()
        return retval

class CreateSettingsWindow(QDialog):
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent):
        super(CreateSettingsWindow, self).__init__(parent)

        self.parent = parent

        self.copy_files_checkbox = QCheckBox("Allow a copy of the image files to be stored. ")

        if hasattr(self.parent, 'copy_files'):
            self.copy_files_checkbox.setChecked(self.parent.copy_files)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.copy_files_checkbox)
        self.buttons = QDialogButtonBox(
           QDialogButtonBox.Save | QDialogButtonBox.Cancel,
           Qt.Horizontal, self)
        self.layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def accept(self):
        #self.parent.settings.setValue("settings_chosen", 1)
        if self.copy_files_checkbox.isChecked():
            self.parent.copy_files = 1 # save for this session
            self.parent.settings.setValue("copy_files", 1) #save for next time we open app
        else:
            self.parent.copy_files = 0
            self.parent.settings.setValue("copy_files", 0)
        self.close()
        #print(self.parent.settings.value("copy_files"))

class CreateSessionSelectionWindow(QtWidgets.QWidget):
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent, temp_folders):
        super().__init__()

        self.parent = parent

        self.setWindowTitle("Load a Session")
        self.label = QLabel("Select a session:")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        #self.setInputMode(QtWidgets.QInputDialog.TextInput)
        self.combo = QComboBox(self)
        self.combo.addItems(temp_folders)

        self.load_button = QPushButton("Load")
        self.new_button = QPushButton("New Session")
        self.load_button.clicked.connect(self.load)
        self.new_button.clicked.connect(self.new)
        
        #self.setWindowFlags(QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)
        #self.setCancelButtonText("New Session")
        #self.setAttribute(Qt.WA_DeleteOnClose)
        self.layout = QtWidgets.QFormLayout()
        self.layout.addRow(self.label)
        self.layout.addRow(self.combo)
        self.layout.addRow(self.load_button, self.new_button)
        self.setLayout(self.layout)

    def load(self):
        #Load Saved Session
        self.parent.InitialiseSessionVars()

        config_worker = Worker(self.parent.load_config_worker, self.combo.currentText())
        self.parent.create_progress_window("Loading", "Loading Session")
        config_worker.signals.progress.connect(self.parent.progress)
        config_worker.signals.finished.connect(self.parent.LoadSession)
        self.parent.threadpool.start(config_worker)
        self.parent.progress_window.setValue(10)
        #self.parent.loaded_session = True
        self.close()

    def new(self):
        #print("NEW SESH")
        self.parent.NewSession()

        self.close()

class CreateSaveSessionWindow(QtWidgets.QWidget):
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent, event):
        super().__init__()

        self.parent = parent
        self.event = event

        self.setWindowTitle("Save Session")
        self.label = QLabel("Save session as:")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        #self.setInputMode(QtWidgets.QInputDialog.TextInput)

        self.textbox = QLineEdit(self)
        rx = QRegExp("[A-Za-z0-9]+")
        validator = QRegExpValidator(rx, self.textbox) #need to check this
        self.textbox.setValidator(validator)

        self.checkbox = QCheckBox()
        self.checkbox.setText("Compress Files")
        self.checkbox.setEnabled(True)
        self.checkbox.setChecked(False)
        
        self.save_button = QPushButton("Save")
        if type(self.event) ==  QCloseEvent:
            self.quit_button = QPushButton("Quit without Saving")
        else:
            self.quit_button = QPushButton("Cancel")

        self.save_button.clicked.connect(partial(self.save, event))
        self.quit_button.clicked.connect(partial(self.quit, event))
        
        self.setWindowFlags(QtCore.Qt.WindowTitleHint )
        #self.setCancelButtonText("New Session")
        #self.setAttribute(Qt.WA_DeleteOnClose)
        self.layout = QtWidgets.QFormLayout()
        self.layout.addRow(self.label)
        self.layout.addRow(self.textbox)
        self.layout.addRow(self.checkbox)
        self.layout.addRow(self.save_button, self.quit_button)
        self.setLayout(self.layout)


    def save(self, event):
        #Load Saved Session
        if(self.checkbox.checkState()):
            compress = True
        else:
            compress=False
        print(compress)
        self.parent.SaveSession(self.textbox.text(), compress, event)
        

    def quit(self, event):
        if type(self.event) ==  QCloseEvent:
            self.parent.RemoveTemp(event) # remove tempdir for this session.
            self.close()
            QMainWindow.closeEvent(self.parent, event)
        else:
            self.close()


class CreateSaveObjectWindow(QtWidgets.QWidget):
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent, object, save_only):
        super().__init__()

        print(save_only)

        self.parent = parent
        self.object = object
        #self.object = object

        if self.object == "mask":
            self.setWindowTitle("Save Existing Mask")
            self.label = QLabel("Save mask as:")
        elif self.object == "pointcloud":
            self.setWindowTitle("Save Existing Point Cloud")
            self.label = QLabel("Save Point Cloud as:")


        self.setWindowModality(QtCore.Qt.ApplicationModal)
        #self.setInputMode(QtWidgets.QInputDialog.TextInput)

        self.textbox = QLineEdit(self)
        rx = QRegExp("[A-Za-z0-9]+")
        validator = QRegExpValidator(rx, self.textbox) #need to check this
        self.textbox.setValidator(validator)

        self.save_button = QPushButton("Save")
        self.quit_button = QPushButton("Discard")
        self.save_button.clicked.connect(lambda: self.save(save_only))
        self.quit_button.clicked.connect(self.quit)
        
        self.setWindowFlags(QtCore.Qt.WindowTitleHint )
        #self.setCancelButtonText("New Session")
        #self.setAttribute(Qt.WA_DeleteOnClose)
        self.layout = QtWidgets.QFormLayout()
        self.layout.addRow(self.label)
        self.layout.addRow(self.textbox)
        self.layout.addRow(self.save_button, self.quit_button)
        self.setLayout(self.layout)


    def save(self, save_only):
        if self.object == "mask":
            #Load Saved Session
            #print("Write mask to file, then carry on")
            filename = self.textbox.text() + ".mha"
            shutil.copyfile(os.path.join(tempfile.tempdir, self.parent.mask_file), os.path.join(tempfile.tempdir, "Masks/" + filename))
            self.parent.mask_parameters['masksList'].addItem(filename)
            self.parent.mask_details[filename] = self.parent.mask_details['current']
            print(self.parent.mask_details)

            self.parent.mask_parameters['loadButton'].setEnabled(True)
            self.parent.mask_parameters['masksList'].setEnabled(True)


            if not save_only:
                print("Not save only")
                #would be better to move this elsewhere
                self.parent.mask_worker = Worker(self.parent.extendMask)
                self.parent.create_progress_window("Loading", "Loading Mask")
                self.parent.mask_worker.signals.progress.connect(self.parent.progress)
                self.parent.mask_worker.signals.finished.connect(self.parent.DisplayMask)
                self.parent.threadpool.start(self.parent.mask_worker)
                self.parent.progress_window.setValue(10)
            
        if self.object == "pointcloud":
            filename = self.textbox.text() + ".roi"
            shutil.copyfile(os.path.join(tempfile.tempdir, "latest_pointcloud.roi"), os.path.join(tempfile.tempdir, filename))

            self.parent.pointcloud_parameters['loadButton'].setEnabled(True)
            self.parent.pointcloud_parameters['pointcloudList'].setEnabled(True)
            self.parent.pointcloud_parameters['pointcloudList'].addItem(filename)
            self.parent.pointCloud_details[filename] = self.parent.pointCloud_details['latest_pointcloud.roi']
            print(self.parent.pointCloud_details)
            #self.parent.createPointCloud()
            if not save_only:
                self.parent.PointCloudWorker("create")
            

        self.close()

    def quit(self):
        if self.object == "mask":
            #would be better to move this elsewhere
            self.parent.mask_worker = Worker(self.parent.extendMask)
            self.parent.create_progress_window("Loading", "Loading Mask")
            self.parent.mask_worker.signals.progress.connect(self.parent.progress)
            self.parent.mask_worker.signals.finished.connect(self.parent.DisplayMask)
            self.parent.threadpool.start(self.parent.mask_worker)
            self.parent.progress_window.setValue(10)

        if self.object == "pointcloud":
            self.parent.PointCloudWorker("create")
            #self.parent.createPointCloud()

        self.close()

class VisualisationWindow(QtWidgets.QMainWindow):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas,QTabWidget.North)


class VisualisationWidget(QtWidgets.QMainWindow):
    def __init__(self, parent, viewer=viewer2D, interactorStyle=vlink.Linked2DInteractorStyle):
        super().__init__()
        self.parent = parent

        self.e = ErrorObserver()
        self.viewer = viewer
        self.interactorStyle = interactorStyle
        self.createEmptyFrame()

        self.show()
        self.threadpool = QThreadPool()
        
    def createEmptyFrame(self):
        #print("empty")
        self.frame = QCILViewerWidget(viewer=self.viewer, shape=(600,600), interactorStyle=self.interactorStyle)
        self.setCentralWidget(self.frame)
        self.image_file = [""]

    def displayImageData(self):
            self.createEmptyFrame()
            start = time.time()
            #print(image_data)
            print("start of finish" + str(self.viewer))
            self.frame.viewer.setInput3DData(self.image_data)
            print("set input data for" + str(self.viewer))

            interactor = self.frame.viewer.getInteractor()

            if hasattr(self.parent, 'orientation'):
                    orientation = self.parent.orientation
                    if orientation == SLICE_ORIENTATION_XY:
                        axis = 'z'
                        interactor.SetKeyCode("z")
                        
                    elif orientation == SLICE_ORIENTATION_XZ:
                        axis = 'y'
                        interactor.SetKeyCode("y")
                    elif orientation == SLICE_ORIENTATION_YZ:
                        axis = 'x'
                        interactor.SetKeyCode("x")
            else:
                interactor.SetKeyCode("z")

            
            

            if self.viewer == viewer2D:
                #Loads appropriate orientation
                self.frame.viewer.setSliceOrientation(axis)
                self.parent.orientation = self.frame.viewer.GetSliceOrientation()
                if self.parent.current_slice:
                    self.frame.viewer.displaySlice(self.parent.current_slice)
                    self.parent.current_slice = None
                
                #self.frame.viewer.style.OnKeyPress(interactor, 'KeyPressEvent')
                
                #self.frame.viewer.sliceActor.GetProperty().SetOpacity(0.99)
                #self.frame.viewer.
                # self.frame.viewer.ren.SetUseDepthPeeling(True)
                # self.frame.viewer.renWin.SetAlphaBitPlanes(True)
                # self.frame.viewer.renWin.SetMultiSamples(False)
                # self.frame.viewer.ren.UseDepthPeelingForVolumesOn()
                # self.frame.viewer.ren.Render()
            if self.viewer == viewer3D:
                self.frame.viewer.sliceActor.GetProperty().SetOpacity(0.99)
                self.frame.viewer.ren.SetUseDepthPeeling(True)
                self.frame.viewer.renWin.SetAlphaBitPlanes(True)
                self.frame.viewer.renWin.SetMultiSamples(False)
                self.frame.viewer.ren.UseDepthPeelingForVolumesOn()

                #self.frame.viewer.style.keyPress(interactor, 'KeyPressEvent')

                if self.parent.current_slice:
                    self.frame.viewer.style.SetActiveSlice(self.parent.current_slice)
                    #self.frame.viewer.displaySlice(self.parent.current_slice)

                self.frame.viewer.ren.Render()


                #self.frame.viewer.sliceOrientation = orientation #no method to set this? didn't seem to do anything

            
            end = time.time() - start
            print("loaded image" + str(self.viewer) + "in " + str(end) + " seconds." )

    def setImageData(self, image_data):
        self.image_data = image_data

class GraphsWindow(QMainWindow):
    def __init__(self, parent=None):
        super(GraphsWindow, self).__init__(parent)
        #QMainWindow.__init__(self)
        self.setWindowTitle("DVC Graphs Window")

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")

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
        self.setGeometry(geometry.width() * 0.8, geometry.height() * 0.8, 1200, 600)
        #self.setFixedSize(geometry.width() * 0.6, geometry.height() * 0.8)
  
class ResultsWidget(QtWidgets.QWidget):
    def __init__(self, parent, plot_data, plot_titles):
        super().__init__()
        self.parent = parent

        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        #Layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

        self.create_histogram(plot_data, plot_titles)

    def create_histogram(self, result, plot_titles):
        numGraphs = len(plot_titles)
        if numGraphs <= 3:
            numRows = 1
        else:
            numRows = np.round(np.sqrt(numGraphs))
        numColumns = np.ceil(numGraphs/numRows)
        plot_data = [result.obj_mins, result.u_disp, result.v_disp, result.w_disp, result.phi_disp, result.theta_disp, result.psi_disp]
        plotNum = 0
        for array in plot_data:
            plotNum = plotNum + 1
            ax = self.figure.add_subplot(numRows, numColumns, plotNum)
            ax.set_ylabel("")
            #ax.set_xlabel(plot_titles[plotNum-1])
            ax.set_title(plot_titles[plotNum-1])
            ax.hist(array,20)

        plt.tight_layout() # Provides proper spacing between figures

        self.canvas.draw() 

class SummaryWidget(QtWidgets.QWidget):
    def __init__(self, parent, result_list):
        super().__init__()
        self.parent = parent

        self.label = QLabel(self)
        self.label.setText("Select which variable would like to compare: ")
        self.label1 = QLabel(self)
        self.label1.setText("Select which parameter you would like to compare: ")

        self.combo = QComboBox(self)
        self.var_list = ["Objective Minimum", "x displacement", "y displacement","z displacment", "phi", "theta", "psi"]
        self.combo.addItems(self.var_list)


        self.combo1 = QComboBox(self)
        self.param_list = ["All","Points in Subvolume", "Radius"]
        self.combo1.addItems(self.param_list)

        self.subvolPoints=[]
        self.radii=[]

        for result in result_list:
            if result.subvol_points not in self.subvolPoints:
                self.subvolPoints.append(result.subvol_points)
            if result.subvol_radius not in self.radii:
                self.radii.append(result.subvol_radius)
        self.subvolPoints.sort()
        self.radii.sort()

        self.secondParamLabel = QLabel(self)
        self.secondParamLabel.setText("Radius:")
        self.secondParamCombo = QComboBox(self)
        self.secondParamList = [str(i) for i in self.radii]
        self.secondParamCombo.addItems(self.secondParamList)
        self.combo1.currentIndexChanged.connect(self.showSecondParam)
        self.secondParamLabel.hide()
        self.secondParamCombo.hide()

        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.button = QtWidgets.QPushButton("Plot Histograms")
        self.button.clicked.connect(partial(self.create_histogram,result_list))

        #Layout
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.label,1,1)
        self.layout.addWidget(self.combo,1,2)
        self.layout.addWidget(self.label1,2,1)
        self.layout.addWidget(self.combo1,2,2)
        self.layout.addWidget(self.secondParamLabel,3,1)
        self.layout.addWidget(self.secondParamCombo,3,2)
        self.layout.addWidget(self.button,4,2)
        self.layout.addWidget(self.toolbar,5,1,1,2)
        self.layout.addWidget(self.canvas,6,1,1,2)
        self.setLayout(self.layout)

    def showSecondParam(self):
        index = self.combo1.currentIndex()
        if index ==0:
            self.secondParamLabel.hide()
            self.secondParamCombo.hide()

        elif index == 1:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Radius:")
            self.secondParamCombo.clear()
            self.secondParamCombo.addItems([str(i) for i in self.radii])

        elif index == 2:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Points in Subvolume:")
            self.secondParamCombo.clear()
            newList = []
            self.secondParamCombo.addItems([str(i) for i in self.subvolPoints])   
        
    
    def create_histogram(self, result_list):

        self.figure.clear()

        index = self.combo1.currentIndex()
        

        points = []

        resultsToPlot= []

        for result in result_list:
            if result.points not in points:
                points.append(result.points)

            if index == 0: #compare all
                resultsToPlot.append(result)
            
            if index == 1: # Points in subvolume is compared
                if result.subvol_radius == float(self.secondParamCombo.currentText()):
                    resultsToPlot.append(result)

            elif index ==2:
                if result.subvol_points == float(self.secondParamCombo.currentText()):
                    resultsToPlot.append(result)

        
        points.sort()

        if index ==0:
            numRows = len(self.subvolPoints)
            numColumns = len(self.radii)

        else:
            # if index ==1:
            #     numRows = len(self.subvolPoints)
            # elif index ==2:
            #     numRows = len(self.radii)
            # numColumns = len(points)
            if len(resultsToPlot) <= 3:
                numRows = 1
            else:
                numRows = np.round(np.sqrt(len(resultsToPlot)))
            numColumns = np.ceil(len(resultsToPlot)/numRows)

        plotNum = 0
        for result in resultsToPlot:

                if index ==0:
                    row = self.subvolPoints.index(result.subvol_points) + 1
                    column= self.radii.index(result.subvol_radius) + 1
                    plotNum = (row-1)*numColumns + column
                    ax = self.figure.add_subplot(numRows, numColumns, plotNum)
                    
                    if row ==1:
                        ax.set_title("Radius:" + str(result.subvol_radius) )
                    if column == 1:
                        text = str(result.subvol_points) 
                        ax.set_ylabel(text + " " + "Points in subvol")

                else:
                    # if index ==1:
                    #     row = self.subvolPoints.index(result.subvol_points) + 1
                    # if index ==2:
                    #     row= self.radii.index(result.subvol_radius) + 1


                    plotNum = plotNum + 1
                    ax = self.figure.add_subplot(numRows, numColumns, plotNum)
                    #ax.set_ylabel("")
                    #ax.set_xlabel(plot_titles[plotNum-1])
                    #ax.set_title(plot_titles[plotNum-1])
                    #ax.hist(array,20)
    
                    # column = points.index(result.points) + 1
                    # plotNum = (row-1)*numColumns + column
                    # ax = self.figure.add_subplot(numRows, numColumns, plotNum)
                    
                    #if row ==1:
                        #ax.set_title(str(result.points) + " Points")
                    #if column == 1:
                    if index ==1:
                        text = str(result.subvol_points) 
                    if index ==2:
                        text = str(result.subvol_radius) 
                    ax.set_ylabel(text + " " + self.combo1.currentText())

                #get variable to display graphs for:
                if self.combo.currentIndex()==0:
                    ax.hist(result.obj_mins,20)
                elif self.combo.currentIndex()==1:
                    ax.hist(result.u_disp,20)
                elif self.combo.currentIndex()==2:
                    ax.hist(result.v_disp,20)
                elif self.combo.currentIndex()==3:
                    ax.hist(result.w_disp,20)
                elif self.combo.currentIndex()==4:
                    ax.hist(result.phi_disp,20)
                elif self.combo.currentIndex()==5:
                    ax.hist(result.theta_disp,20)
                elif self.combo.currentIndex()==6:
                    ax.hist(result.psi_disp,20)

        self.figure.suptitle(self.combo.currentText(),size ="large")

        plt.tight_layout() # Provides proper spacing between figures
        plt.subplots_adjust(top=0.88) # Means heading doesn't overlap with subplot titles
        self.canvas.draw()
        
class run_outcome:
    def __init__(self,file_name):
        self.obj_mins=[]
        self.u_disp=[]
        self.v_disp=[]
        self.w_disp=[]
        self.phi_disp=[]
        self.theta_disp=[]
        self.psi_disp=[]       

        disp_file_name = file_name + ".disp"
        stat_file_name = file_name + ".stat"
        disp_file = open(disp_file_name,"r")
        self.disp_file_name = disp_file_name

        self.points = 0
        for line in disp_file:
            if self.points>0:
                line_array = line.split()
                self.obj_mins.append(float(line_array[5]))
                self.u_disp.append(float(line_array[6]))
                self.v_disp.append(float(line_array[7]))
                self.w_disp.append(float(line_array[8]))
                self.phi_disp.append(float(line_array[9]))
                self.theta_disp.append(float(line_array[10]))
                self.psi_disp.append(float(line_array[11]))
            self.points+=1

        self.points-=1

        stat_file = open(stat_file_name,"r")
        count = 0
        for line in stat_file:
            if count ==16:
                self.subvol_points = int(line.split('\t')[1])
            if count ==15:
                self.subvol_radius = round(int(line.split('\t')[1])/2)
            count+=1

        self.title =  str(self.subvol_points) + " Points in Subvolume," + " Radius: " + str(self.subvol_radius) # + str(self.points) + " Points, " +

def generateUIDockParameters(self, title): #copied from dvc_configurator.py
        '''creates a dockable widget with a form layout group to add things to

        basically you can add widget to the returned groupBoxFormLayout and paramsGroupBox
        The returned dockWidget must be added with
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
        '''
        dockWidget = QDockWidget(self)
        dockWidget.setWindowTitle(title)
        dockWidgetContents = QWidget()


        # Add vertical layout to dock contents
        dockContentsVerticalLayout = QVBoxLayout(dockWidgetContents)
        dockContentsVerticalLayout.setContentsMargins(0, 0, 0, 0)

        # Create widget for dock contents
        internalDockWidget = QWidget(dockWidgetContents)

        # Add vertical layout to dock widget
        internalWidgetVerticalLayout = QVBoxLayout(internalDockWidget)
        internalWidgetVerticalLayout.setContentsMargins(0, 0, 0, 0)

        # Add group box
        paramsGroupBox = QGroupBox(internalDockWidget)


        # Add form layout to group box
        groupBoxFormLayout = QFormLayout(paramsGroupBox)
        #groupBoxFormLayout.setFormAlignment(Qt.AlignCenter)

        # Add elements to layout
        internalWidgetVerticalLayout.addWidget(paramsGroupBox)
        dockContentsVerticalLayout.addWidget(internalDockWidget)
        dockWidget.setWidget(dockWidgetContents)

        #        self.graphWidgetVL.addWidget(self.graphParamsGroupBox)
        #        self.graphDockVL.addWidget(self.dockWidget)
        #        self.pointCloudDockWidget.setWidget(self.pointCloudDockWidgetContents)
        #
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.pointCloudDockWidget)
        return (dockWidget, dockWidgetContents,
                dockContentsVerticalLayout, internalDockWidget,
                internalWidgetVerticalLayout, paramsGroupBox,
                groupBoxFormLayout)


def main():
    err = vtk.vtkFileOutputWindow()
    err.SetFileName("viewer.log")
    vtk.vtkOutputWindow.SetInstance(err)

    # log = open("dvc_interface.log", "a")
    # sys.stdout = log

    app = QtWidgets.QApplication([])

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
