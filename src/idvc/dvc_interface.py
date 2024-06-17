#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

#   Author: Laura Murgatroyd (UKRI-STFC)
#   Author: Edoardo Pasca (UKRI-STFC)

import os
from openpyxl import load_workbook
import sys
import PySide2
from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import (QByteArray, QRegExp, QSettings, QSize, Qt,
                            QThreadPool)
from PySide2.QtGui import QCloseEvent, QKeySequence, QRegExpValidator
from PySide2.QtWidgets import (QAction, QCheckBox, QComboBox,
                               QDockWidget,
                               QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGroupBox, QLabel, QLineEdit,
                               QMainWindow, QMessageBox,
                               QProgressDialog, QPushButton, QScrollArea, QSpinBox,
                               QTabWidget, QTabBar, QVBoxLayout,
                               QHBoxLayout, QSizePolicy,
                               QWidget) 
import time
import numpy as np
import math


import matplotlib.pyplot as plt

from functools import partial
from datetime import datetime


import vtk
from ccpi.viewer import viewer2D, viewer3D
from ccpi.viewer.QCILViewerWidget import QCILViewerWidget
from ccpi.viewer.CILViewer2D import (SLICE_ORIENTATION_XY,
                                     SLICE_ORIENTATION_XZ,
                                     SLICE_ORIENTATION_YZ)
import ccpi.viewer.viewerLinker as vlink

# from ccpi.viewer.QtThreading import Worker, WorkerSignals, ErrorObserver #
from eqt.threading import Worker
from ccpi.viewer.utils.error_handling import ErrorObserver
from ccpi.viewer.utils.colormaps import CILColorMaps

from natsort import natsorted
import imghdr
import glob

# from vtk.numpy_interface import algorithms as algs
# from vtk.numpy_interface import dataset_adapter as dsa
# from vtk.util import numpy_support

working_directory = os.getcwd()
os.chdir(working_directory) 

from ccpi.viewer.utils import (cilMaskPolyData, cilPlaneClipper, Converter)
import tempfile
import json
import shutil
import zipfile

from functools import reduce

import copy

from idvc.io import ImageDataCreator, getProgress, displayErrorDialogFromWorker, warningDialog

from idvc.pointcloud_conversion import cilRegularPointCloudToPolyData, cilNumpyPointCloudToPolyData, PointCloudConverter

from idvc.dvc_runner import DVC_runner

from eqt.ui import FormDialog

import qdarkstyle
from qdarkstyle.dark.palette import DarkPalette
from qdarkstyle.light.palette import LightPalette

from idvc import version as gui_version

from idvc.ui.widgets import *
from idvc.ui.dialogs import *
from idvc.ui.windows import *
from idvc.utilities import *

__version__ = gui_version.version

import logging

from idvc.utils.AutomaticRegistration import AutomaticRegistration
from idvc.utils.point_cloud_io import extract_point_cloud_from_inp_file

allowed_point_cloud_file_formats = ('.roi', '.txt', '.csv', '.xlsx', '.inp')

class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        
        self.threadpool = QThreadPool()

        self.temp_folder = None
        

        self.setWindowTitle("Digital Volume Correlation v{}".format(__version__))
        DVCIcon = QtGui.QIcon()
        file_dir = os.path.dirname(__file__)
        DVCIcon.addFile(os.path.join(file_dir, "DVCIconSquare.png"))

        self.setWindowIcon(DVCIcon)
        
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
        save_action.triggered.connect(partial(self.CreateSaveWindow,"Cancel", lambda x: print(type(x))))
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
        export_action.triggered.connect(self.ExportSession)
        self.file_menu.addAction(export_action)

        # Exit QAction
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
             
        # # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)

        border = 50
        self.setGeometry(border, border, geometry.width()-2*border, geometry.height()-2*border)

        self.e = ErrorObserver()

        self.CreateWorkingTempFolder()

        #Load Settings:
        self.settings = QSettings("CCPi", "DVC Interface v20.7.2")

        if self.settings.value("copy_files"):
            self.copy_files = True
        else:
            self.copy_files = False

        self.SetAppStyle()

        if self.settings.value("first_app_load") != "False":
            self.OpenSettings()
            # self.settings.setValue("first_app_load", False)

        else:
            self.CreateSessionSelector("new window")

    def createPopupMenu(self):
        '''return an empty menu for the main window to use as a popup menu.
        
        https://doc.qt.io/qt-6/qmainwindow.html#createPopupMenu
        '''
        return QtWidgets.QMenu(self) # Create a new menu
    
    def SetAppStyle(self):
        if self.settings.value("dark_mode") is None:
            self.settings.setValue("dark_mode", True)
        if self.settings.value("dark_mode") == "true":
            style = qdarkstyle.load_stylesheet(palette=DarkPalette)
        else:
            style = qdarkstyle.load_stylesheet(palette=LightPalette)
        self.setStyleSheet(style)

        
#Setting up the session:
    def CreateWorkingTempFolder(self):
        temp_folder = os.path.join(working_directory, 'DVC_Sessions')
        
        if not os.path.isdir(temp_folder):
            os.mkdir("DVC_Sessions")
            temp_folder = os.path.join(working_directory, "DVC_Sessions")

        self.temp_folder = os.path.abspath(temp_folder)
        tempfile.tempdir = tempfile.mkdtemp(dir = self.temp_folder)

        os.chdir(tempfile.tempdir)

        # Creates folder in tempdir to save mask files in
        os.mkdir("Masks")
        os.mkdir("Results")

    def OpenSettings(self):
        self.settings_window = SettingsWindow(self)
        self.settings_window.show()

    def InitialiseSessionVars(self):
        self.config={}
        self.image=[[],[]]
        self.dvc_input_image = [[],[]]
        self.roi = None
        self.run_folder = [None]
        self.results_folder = [None]
        self.pointCloudCreated = False
        self.eroded_mask = False
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
        self.loading_session = False
        self.dvc_input_image_in_session_folder = False    
        if hasattr(self, 'ref_image_data'):
            del self.ref_image_data


#Loading the DockWidgets:
    def CreateDockWindows(self):
        
        self.setTabPosition(QtCore.Qt.AllDockWidgetAreas, QTabWidget.North)

        #Create widgets to view images in 2D and 3D and link them:
        self.vis_widget_2D = VisualisationWidget(self, viewer=viewer2D, interactorStyle=vlink.Linked2DInteractorStyle)#interactorStyle= CILInteractorStyle2D) #previously unliked for testing
        self.vis_widget_3D = VisualisationWidget(self, viewer=viewer3D, interactorStyle=vlink.Linked3DInteractorStyle) #interactorStyle= CILInteractorStyle3D)#previously unlinked for testing

        self.CreateViewerSettingsPanel()
        self.CreateHelpPanel()


        self.CreateSelectImagePanel()
        self.CreateRegistrationPanel()
        self.CreateMaskPanel()
        self.CreatePointCloudPanel()
        self.CreateRunDVCPanel()
        self.CreateViewDVCResultsPanel()

        self.viewer2D_dock = self.vis_widget_2D

        self.viewer3D_dock = QDockWidget("3D View")
        self.viewer3D_dock.setObjectName("3DImageView")
        self.viewer3D_dock.setWidget(self.vis_widget_3D)
        self.viewer3D_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.viewer3D_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)   

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
        
        # makes first panel the one that is open by default.
        first_dock.raise_()

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.viewer3D_dock)
        
        # Make a window to house the right dockwidgets
        # This ensures the 2D viewer is large and allows us to position the help and settings below it

        self.RightDockWindow = VisualisationWindow(self)

        self.setCentralWidget(self.RightDockWindow)

        self.RightDockWindow.setCentralWidget(self.viewer2D_dock)

        self.RightDockWindow.addDockWidget(QtCore.Qt.BottomDockWidgetArea,self.help_dock)

        self.RightDockWindow.addDockWidget(QtCore.Qt.BottomDockWidgetArea,self.viewer_settings_dock)

        # Stop the widgets in the tab to be moved around
        for wdg in self.findChildren(QTabBar):
            wdg.setMovable(False)
        
    def CreateViewerSettingsPanel(self):
        self.viewer_settings_panel = generateUIDockParameters(self, "Viewer Settings")
        dockWidget = self.viewer_settings_panel[0]
        dockWidget.setObjectName("ViewerSettingsPanel")
        groupBox = self.viewer_settings_panel[5]
        formLayout = self.viewer_settings_panel[6]
        self.viewer_settings_dock = dockWidget

        vs_widgets = {}

        widgetno = 0

        vs_widgets['coords_info_label'] = QLabel(groupBox)
        vs_widgets['coords_info_label'].setText("The viewer displays a downsampled image for visualisation purposes: ")
        vs_widgets['coords_info_label'].setVisible(False)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, vs_widgets['coords_info_label'])

        widgetno+=1

        vs_widgets['loaded_image_dims_label'] = QLabel(groupBox)
        vs_widgets['loaded_image_dims_label'].setText("Loaded Image Size: ")
        vs_widgets['loaded_image_dims_label'].setVisible(True)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, vs_widgets['loaded_image_dims_label'])

        vs_widgets['loaded_image_dims_value'] = QLabel(groupBox)
        vs_widgets['loaded_image_dims_value'].setText("")
        vs_widgets['loaded_image_dims_value'].setVisible(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, vs_widgets['loaded_image_dims_value'])

        widgetno+=1

        vs_widgets['displayed_image_dims_label'] = QLabel(groupBox)
        vs_widgets['displayed_image_dims_label'].setText("Displayed Image Size: ")
        vs_widgets['displayed_image_dims_label'].setVisible(False)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, vs_widgets['displayed_image_dims_label'])

        vs_widgets['displayed_image_dims_value'] = QLabel(groupBox)
        vs_widgets['displayed_image_dims_value'].setText("")
        vs_widgets['displayed_image_dims_value'].setVisible(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, vs_widgets['displayed_image_dims_value'])

        widgetno+=1

        vs_widgets['coords_label'] = QLabel(groupBox)
        vs_widgets['coords_label'].setText("Display viewer coordinates in: ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, vs_widgets['coords_label'])

        vs_widgets['coords_combobox'] = QComboBox(groupBox)
        vs_widgets['coords_combobox'].addItems(["Loaded Image", "Downsampled Image"])
        vs_widgets['coords_combobox'].setEnabled(False)
        vs_widgets['coords_combobox'].currentIndexChanged.connect(self.updateCoordinates)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, vs_widgets['coords_combobox'])

        widgetno +=1

        vs_widgets['coords_warning_label'] = QLabel(groupBox)
        vs_widgets['coords_warning_label'].setText("Warning: These coordinates are approximate.")
        vs_widgets['coords_warning_label'].setVisible(False)

        formLayout.setWidget(widgetno, QFormLayout.FieldRole, vs_widgets['coords_warning_label'])

        self.visualisation_setting_widgets = vs_widgets
        
    def updateCoordinates(self):
        viewers_2D = [self.vis_widget_2D.frame.viewer]
        vs_widgets = self.visualisation_setting_widgets
        if hasattr(self, 'vis_widget_reg'):
            viewers_2D.append(self.vis_widget_reg.frame.viewer)

        for viewer in viewers_2D:
            if hasattr(viewer, 'img3D'):
                if viewer.img3D is not None:
                    viewer.setVisualisationDownsampling(self.resample_rate)
                    shown_resample_rate = self.resample_rate
                    vs_widgets['loaded_image_dims_label'].setVisible(True)
                    vs_widgets['loaded_image_dims_value'].setVisible(True)

                    if vs_widgets['coords_combobox'].currentIndex() == 0:
                        viewer.setDisplayUnsampledCoordinates(True)
                        if shown_resample_rate != [1,1,1]:
                            vs_widgets['coords_warning_label'].setVisible(True)
                        else:
                            vs_widgets['coords_warning_label'].setVisible(False)

                    else:
                        viewer.setDisplayUnsampledCoordinates(False)
                        vs_widgets['coords_warning_label'].setVisible(False)

                    if hasattr(self, 'point0_world_coords'):
                        self.SetPoint0Text()

                    viewer.updatePipeline()

    def CreateHelpPanel(self):
        """Creates the help-text dock widget.
        
        Saves the help text for all tabs.
        Adds a QLabel in the form of scrollable text."""
        help_panel = generateUIDockParameters(self, "Help")
        dockWidget = help_panel[0]
        dockWidget.setObjectName("HelpPanel")
        groupBox = help_panel[5]
        formLayout = help_panel[6]
        self.help_dock = dockWidget

        self.help_text = ["Please use 'raw' or 'npy' images.\n"
        "You can view the shortcuts for the viewer by clicking on the 2D image and then pressing the 'h' key."]

        self.help_text.append(
            "1. Click 'Select point 0' to choose a point and region for the registration.\n"
            "2. Adjust the registration box size. The box should enclose enough material-texture details but be kept relatively small compared to the size of the image. E.g., 1/10 of one image dimension.\n"
            "3. Click 'Start Registration' to begin the registration process.\n"
            "4. The suggested registration will be displayed, and the difference volume of the registered image will be shown in the viewer.\n"
            "5. Use the mouse wheel to navigate in the third direction, and the 'x', 'y', or 'z' keys to control the slicing orientation.\n"
            "6. To manually adjust the registration, click on the image and move the two images relative to each other using the 'j' (up), 'n' (down), 'b' (right), and 'm' (left) keys.\n"
            "7. You can 'Reset' the registration values or 'Set to Automatic Registration'.\n"
            "8. You can 'Confirm Registration' or 'Cancel'.\n"
            "9. Once satisfied with the registration, move to the next tab. Be aware that point 0 is the point from which DVC will start."
            )
        
        self.help_text.append(
            "The mask dictates where the point cloud lies.\n\n"
            "1. Click on 'Load Mask from File' to upload a mask file (format '.mha').\n"
            "2. To create a new mask click 'Start tracing'. This enables freehand tracing on the viewer. The mask design consists of either the tracing of a single curve or the insertion of multiple spline segments separated by point handles.\n\n"
            "- Draw a free hand line: left button click over the image, hold and drag.\n"
            "- Erase the line: left button click and release.\n"
            "- Start a snap drawn line: middle button click. Terminate the line by clicking the middle button while depressing the ctrl key.\n"
            "- Form a closed loop with the line: trace a continuous or snap drawn line and place the last cursor position close to the first handle.\n" 
            "- Point handle dragging: right button click and hold on any handle that is part of a snap drawn line. The path can be closed by overlappingg the first and last points.\n" 
            "- Erase any point handle: ctrl key + right button down on the handle.\n"
            "- Split a segment at the cursor position: shift key + right button down on any snap drawn line segment.\n\n"
            "3. If you are not happy with the tracing, click on 'Stop tracing'.\n"
            "4. The mask is used across multiple slices in 3D. The volume can be adjusted by editing the 'Slices Above' and 'Slices Below' values.\n"
            "5. Click on 'Create mask' when the tracing is finalised.\n"
            "6. Tick the 'Extend Mask' checkbox if the mask needs to cover more than one area, or the area of the mask needs to be enlarged. Then, draw another region and press the button 'Extend Mask'.\n"
            "7. The most recent mask will automatically be applied. If it is intended to draw more than one mask click on 'Save Mask' and name it in the pop-up dialog.\n"
            "8. To restart the mask creation, click on 'Clear mask'.\n"
            "9. Each mask can be selected and reloaded by clicking on 'Load Saved Mask'.")
        
        self.help_text.append("Dense point clouds that accurately reflect sample geometry and reflect measurement objectives yield the best results.\n"
            "The first point in the cloud is significant, as it is used as a global starting point and reference for the rigid translation between the two images.\n"
            "If the point 0 you selected in image registration falls inside the mask, then the pointcloud will be created with the first point at the location of point 0.\n"
            "If you load a pointcloud from a file, you must still specify the subvolume size on this panel, which will later be input to the DVC code.\n"
            "It will be the first point in the file that is used as the reference point.")

        self.help_text.append("Once the code is run it is recommended that you save or export your session, to back up your results."
            "You can access these options under 'File'.")

        self.help_text.append("Vectors can be displayed for the displacement of points either including or excluding the rigid body offset."
            "You may also scale the vectors to make them larger and easier to view.")

        self.help_label = QLabel(groupBox)
        scroll_area_widget = QScrollArea()
        
        self.help_label.setWordWrap(True)
        self.help_label.setText(self.help_text[0])

        scroll_area_widget.setWidget(self.help_label)
        scroll_area_widget.setFrameShape(QFrame.NoFrame)
        scroll_area_widget.setFrameShadow(QFrame.Plain)
        scroll_area_widget.setStyleSheet("border: 0px;")
        scroll_area_widget.setWidgetResizable(True)


        formLayout.setWidget(1, QFormLayout.SpanningRole, scroll_area_widget)

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

        si_widgets['view_button'] = QPushButton(groupBox)
        si_widgets['view_button'].setText("View Image")
        si_widgets['view_button'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, si_widgets['view_button'])
        widgetno += 1

        #button functions:
        si_widgets['ref_browse'].clicked.connect(lambda: self.SelectImage(0, self.image, label=si_widgets['ref_file_label'], next_button=si_widgets['cor_browse']))
        si_widgets['cor_browse'].clicked.connect(lambda: self.SelectImage(1, self.image, label=si_widgets['cor_file_label'], next_button=si_widgets['view_button']))
        si_widgets['view_button'].clicked.connect(self.view_and_load_images)

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,dockWidget)

        self.si_widgets = si_widgets
    
    def view_and_load_images(self):
        self.view_image()
        self.resetRegistration()

    def SelectImage(self, image_var, image, label=None, next_button=None): 
        #print("In select image")
        dialogue = QFileDialog()
        files = dialogue.getOpenFileNames(self,"Load Images")[0]

        if len(files) > 0:
            if self.copy_files:
                new_file_name = 'reference'
                if image_var == 1:
                    new_file_name = 'correlate'
                # first of all we need to remove the files that were copied in the previous run
                self.create_progress_window("Copying", "Copying files", 100, None)
                # self.progress_window.setValue(1)
                

                self.image_copied[image_var] = True
                new_file_dest = []
                for file_num, f in enumerate(files):
                    file_name = os.path.basename(f)
                    file_ext = file_name.split(".")[-1]
                    if len(files) == 1:
                        if file_ext == "mhd":
                            new_file_dest.append( os.path.join(new_file_name + "." + "mha") )
                        else:
                            new_file_dest.append( os.path.join(new_file_name + "." + file_ext) )
                    else:
                        new_file_dest.append( os.path.join(new_file_name + "_" + str(file_num) + "." + file_ext) )

                    # files[file_num] = new_file_dest[-1]
                copy_worker = Worker(self.copy_file, start_location=files, end_location=new_file_dest, image_var=image_var)
                copy_worker.signals.progress.connect(self.progress_window.setValue)
                copy_worker.signals.finished.connect(partial(self.update_interface_on_copy_complete, image, image_var, label, next_button))
                copy_worker.signals.error.connect(partial(self.worker_error, progress_dialog=self.progress_window))
                self.threadpool.start(copy_worker)
                    
            else:
                self.image_copied[image_var] = False
                self.update_interface_no_copy(files, image, image_var, label, next_button)
                
    def worker_error(self, error, **kwargs):
        if 'progress_dialog' in kwargs.keys():
            kwargs['progress_dialog'].close()
        dialog_retval = warningDialog(self, str(error[1]), "Error", str(error[2]))

    def update_interface_on_copy_complete(self, image, image_var, label, next_button):

        new_file_name = 'reference'
        if image_var == 1:
            new_file_name = 'correlate'
        files = glob.glob(new_file_name+"*")
        
        self.update_interface_no_copy(files, image, image_var, label, next_button)
    
    def update_interface_no_copy(self, files, image, image_var, label, next_button):
        
        if len(files) == 1: #@todo
            if(image[image_var]):
                image[image_var]= files
            else:
                image[image_var].append(files[0])
            if label is not None:
                label.setText(os.path.basename(files[0]))
            
        elif len(files) > 1:
            # Make sure that the files are sorted 0 - end
            filenames = natsorted(files)
            
            image[image_var] = filenames
            if label is not None:
                label.setText(
                    os.path.dirname(self.image[image_var][0]) + "\n" +\
                    os.path.basename(self.image[image_var][0]) + " + " + str(len(files)-1) + " more files.")
        else:
            raise ValueError('Something went wrong with the file copy')

        if next_button is not None:
            next_button.setEnabled(True)

    def copy_file(self, start_location, end_location, image_var, **kwargs):
        progress_callback = kwargs.get('progress_callback', PrintCallback())
        # message_callback = kwargs.get('message_callback', PrintCallback())

        # first of all we need to remove the files that were copied in the previous run
        new_file_name = 'reference'
        if image_var == 1:
            new_file_name = 'correlate'
        files_to_remove = glob.glob(new_file_name+"*")
        N = len(files_to_remove)
        for i,f in enumerate(files_to_remove):
            progress_callback.emit(i/N*100)
            os.remove(f)

        self.image_copied[image_var] = True
        
        file_extension = os.path.splitext(start_location[0])[1]

        # if the file is a mhd file we have a header and the data blob, i.e. 2 files
        if file_extension == '.mhd':
            progress_callback.emit(0)
            reader = vtk.vtkMetaImageReader()
            reader.SetFileName(start_location[0])
            reader.Update()
            progress_callback.emit(50)
            writer = vtk.vtkMetaImageWriter()
            # tmpdir = tempfile.gettempdir()
            writer.SetFileName(end_location[0])
            writer.SetCompression(False)
            writer.SetInputData(reader.GetOutput())
            writer.Write()
            progress_callback.emit(100)
        else:
            N = len(start_location)
            for i,fs in enumerate(zip(start_location, end_location)):
                if N > 1:
                    ftype = imghdr.what(fs[0])
                    if ftype != 'tiff':
                        raise ValueError('File type not supported: {}'.format(fs[0]))
                progress_callback.emit(i/N*100)
                shutil.copyfile(fs[0], fs[1])
            progress_callback.emit(100)

    def show_copy_progress(self, _file, new_file_dest,ratio, file_type, num_files):

        while not os.path.exists(new_file_dest):
            time.sleep(0.001)

        if(file_type != "mhd"):
            while os.path.getsize(_file) != os.path.getsize(new_file_dest):
                self.progress_window.setValue(int((float(os.path.getsize(new_file_dest))/float(os.path.getsize(_file)*ratio))*100))
                time.sleep(0.1)
                
        self.progress_window.setValue(100)

    def displayFileErrorDialog(self, message, title, action_button=None):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        try:
            msg.setDetailedText(self.e.ErrorMessage())
        except:
            pass
        if action_button is not None:
            msg.addButton(action_button, msg.ActionRole)
        msg.exec_()

    def view_image(self):
        self.ref_image_data = vtk.vtkImageData()
        self.image_info = dict()
        if self.settings.value("gpu_size") is not None and self.settings.value("volume_mapper") == "gpu":
            if self.settings.value("vis_size"):
                if float(self.settings.value("vis_size")) < float(self.settings.value("gpu_size")):
                    target_size = float(self.settings.value("vis_size"))
                else:
                    target_size = (float(self.settings.value("gpu_size")))
            else:
                target_size = (float(self.settings.value("gpu_size")))
        else:
            if self.settings.value("vis_size"):
                target_size = float(self.settings.value("vis_size"))
            else:
                target_size = 0.125
        self.target_image_size = target_size
        
        ImageDataCreator.createImageData(self, self.image[0], self.ref_image_data, info_var = self.image_info, convert_raw = True,  
        finish_fn = partial(self.save_image_info, "ref"), resample= True, target_size = target_size, output_dir='.')

    def save_image_info(self, image_type):
        """Sets the value of the registration box size to the 1/10 of the max dimension."""
        if 'vol_bit_depth' in self.image_info:
            self.vol_bit_depth = self.image_info['vol_bit_depth']

            maximum_value = round((self.target_image_size**(1/3))*1024/3*int(self.vol_bit_depth)/8)
            minimum_image_dimension = np.min(self.ref_image_data.GetDimensions())-1

            if maximum_value > minimum_image_dimension:
                maximum_value = minimum_image_dimension

            #Update registration box size according to target size and vol bit depth
            self.registration_parameters['registration_box_size_entry'].setMaximum(maximum_value)
            self.registration_parameters['registration_box_size_entry'].setValue(round(np.max(self.ref_image_data.GetDimensions())/10))
        
        
        #Update mask slices above/below to be max extent of downsampled image
        self.mask_parameters['mask_extend_above_entry'].setMaximum(np.max(self.ref_image_data.GetDimensions()))
        self.mask_parameters['mask_extend_below_entry'].setMaximum(np.max(self.ref_image_data.GetDimensions()))

        #Update max subvolume size to be min dimension of image
        #TODO: fix so that this works
        validatorint = QtGui.QIntValidator()
        validatorint.setTop(np.min(self.ref_image_data.GetDimensions()))
        self.rdvc_widgets['subvol_size_range_max_value'].setValidator(validatorint)
        self.rdvc_widgets['subvol_size_range_min_value'].setValidator(validatorint)
        self.isoValueEntry.setValidator(validatorint)

        if 'header_length' in self.image_info:
            self.vol_hdr_lngth = self.image_info['header_length']
        else:
            self.vol_hdr_lngth = 0

        self.resample_rate = [1,1,1]

        if 'shape' in self.image_info:
            self.unsampled_image_dimensions = self.image_info['shape'] 

            #print("Unsampled dims: ", self.unsampled_image_dimensions)
            #print("current dims: ", self.ref_image_data.GetDimensions())
            
            for i, value in enumerate(self.resample_rate):
                self.resample_rate[i] = self.unsampled_image_dimensions[i]/(self.ref_image_data.GetDimensions()[i])

            self.visualisation_setting_widgets['coords_warning_label'].setVisible(True)


        else:
            self.unsampled_image_dimensions = list(self.ref_image_data.GetDimensions())
            self.visualisation_setting_widgets['coords_warning_label'].setVisible(False)

        if 'raw_file' in self.image_info:
            image_file = [self.image_info['raw_file']]
            if image_type == "ref":
                self.dvc_input_image[0] = image_file
                if os.path.splitext(self.image[0][0])[1] in ['.mhd', '.mha']: #need to call create image data so we read header and save image to file w/o header
                    self.temp_image_data = vtk.vtkImageData()
                    ImageDataCreator.createImageData(self, self.image[1], self.temp_image_data, info_var=self.image_info, convert_raw=True,  finish_fn=partial(
                        self.save_image_info, "corr"), output_dir='.')
            elif image_type == "corr":
                self.dvc_input_image[1] = image_file
                if hasattr(self, 'temp_image_data'):
                    del self.temp_image_data
            self.dvc_input_image_in_session_folder = True
        else:
            self.dvc_input_image = self.image
            self.dvc_input_image_in_session_folder = False
        
        if image_type == "ref":
            self.visualise()

    def visualise(self):
        if self.ref_image_data is None:
            #self.progress_window.setValue(100)
            self.warningDialog('Unable to load image.','Error', 'Image is in incorrect format to perform run of DVC. Please load a different image.')
            return

        time.sleep(0.1)

        self.create_progress_window("Loading", "Loading Image")
        self.progress_window.setValue(10)

        self.vis_widget_2D.setImageData(self.ref_image_data)
         
        self.vis_widget_2D.displayImageData()

        self.progress_window.setValue(50)
        
        self.vis_widget_3D.setImageData(self.ref_image_data) #3D)
        self.vis_widget_3D.displayImageData()

        self.progress_window.setValue(80)

        # observe mouse events and keypress events and invoke the plane clipper
        self.vis_widget_2D.frame.viewer.style.AddObserver("MouseWheelForwardEvent",
                                                self.vis_widget_2D.PlaneClipper.UpdateClippingPlanes, 0.9)
        self.vis_widget_2D.frame.viewer.style.AddObserver("MouseWheelBackwardEvent",
                                                self.vis_widget_2D.PlaneClipper.UpdateClippingPlanes, 0.9)
        self.vis_widget_2D.frame.viewer.style.AddObserver("KeyPressEvent",
                                                self.vis_widget_2D.PlaneClipper.UpdateClippingPlanes, 0.9)
        # handles vectors updating when switching orientation)
        self.vis_widget_2D.frame.viewer.style.AddObserver("KeyPressEvent", self.OnKeyPressEventForVectors, 0.95) 



        #Link Viewers:
        self.link2D3D = vlink.ViewerLinker(self.vis_widget_2D.frame.viewer,
                                           self.vis_widget_3D.frame.viewer)
        self.link2D3D.setLinkPan(False)
        self.link2D3D.setLinkZoom(False)
        self.link2D3D.setLinkWindowLevel(True)
        self.link2D3D.setLinkSlice(True)
        self.link2D3D.setLinkOrientation(True)
        self.link2D3D.enable()

        #reset these so they aren't remembered for next image load
        self.current_slice = None
        self.orientation = None

        self.progress_window.setValue(100)
        
        time.sleep(0.1)
        #self.LoadCorrImageForReg()

        self.pointCloudCreated = False
        self.pointCloudLoaded = False
        self.eroded_mask = False

        if(self.mask_load):
            self.MaskWorker("load session")
            self.mask_load = False # so it does not reload next time

        if hasattr(self, 'no_mask_pc_load'):        
            if(self.no_mask_pc_load):
                self.PointCloudWorker("load pointcloud file")
                self.pointCloudLoaded = True
                self.no_mask_pc_load = False
                self.pointcloud_is = 'loaded'

        if(self.reg_load):
            self.displayRegistrationViewer(registration_open = True)
            #first we need to set the z slice -> go to slice self.config['point0'][2]
            v = self.vis_widget_2D.frame.viewer
            if v.img3D is not None:
                self.createPoint0(self.config['point0'])
                rp = self.registration_parameters
                if self.config['reg_translation'] is not None:
                    rp['translate_X_entry'].setText(str(self.config['reg_translation'][0]*-1))
                    rp['translate_Y_entry'].setText(str(self.config['reg_translation'][1]*-1))
                    rp['translate_Z_entry'].setText(str(self.config['reg_translation'][2]*-1))
                    self.translate = vtk.vtkImageTranslateExtent()
                    self.translate.SetTranslation(self.config['reg_translation'])
                    self.registration_parameters['registration_box_size_entry'].setValue(self.config['reg_sel_size'])
                    self.registration_parameters['registration_box_size_entry'].setEnabled(True)

            self.reg_viewer_dock.setVisible(False)
            self.viewer2D_dock.setVisible(True)
            self.viewer3D_dock.setVisible(True)
            self.reg_load = False

            #bring image loading panel to front if it isnt already:          
            self.select_image_dock.raise_() 

    def create_progress_window(self, title, text, max = 100, cancel = None):
        self.progress_window = QProgressDialog(text, "Cancel", 0,max, self, QtCore.Qt.Dialog) 
        self.progress_window.setWindowTitle(title)
        
        self.progress_window.setWindowModality(QtCore.Qt.ApplicationModal) #This means the other windows can't be used while this is open
        self.progress_window.setMinimumDuration(0.01)
        self.progress_window.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, True)
        self.progress_window.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)
        self.progress_window.setAutoClose(True)
        if cancel is None:
            self.progress_window.setCancelButton(None)
        else:
            self.progress_window.canceled.connect(cancel)

    def setup2DPointCloudPipeline(self):

        self.vis_widget_2D.PlaneClipper.AddDataToClip('pc_actor', self.polydata_masker.GetOutputPort())

        mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.pointmapper = mapper

        mapper.SetInputConnection(self.vis_widget_2D.PlaneClipper.GetClippedData('pc_actor').GetOutputPort())         

        # create an actor for the points as point
        actor = vtk.vtkLODActor()
        # save reference
        self.pointactor = actor
        actor.SetMapper(mapper)
        actor.GetProperty().SetPointSize(3)
        actor.GetProperty().SetColor(0., 1., 1.)
        actor.VisibilityOn()

        # create a mapper/actor for the point cloud with a CubeSource and with vtkGlyph3D
        # which copies oriented and scaled glyph geometry to every input point

        subv_glyph = vtk.vtkGlyph3D()
        subv_glyph.OrientOn()

        # save reference
        self.cubesphere = subv_glyph
        subv_glyph.SetScaleFactor(1.)
        
        v = self.vis_widget_2D.frame.viewer
        spacing = v.img3D.GetSpacing()


        # pointCloud = self.pointCloud
        subvol_size = self.pointCloud_subvol_size

        # # Spheres may be a bit complex to visualise if the spacing of the image is not homogeneous
        sphere_source = vtk.vtkSphereSource()
        # # save reference
        self.sphere_source = sphere_source
        sphere_source.SetRadius(self.pointCloud_subvol_size/2) # * v.img3D.GetSpacing()[0])
        sphere_source.SetThetaResolution(12)
        sphere_source.SetPhiResolution(12)

        # # Cube source
        cube_source = vtk.vtkCubeSource()
        # print("IMAGE SPACING", v.img3D.GetSpacing())
        cube_source.SetXLength(self.pointCloud_subvol_size)
        cube_source.SetYLength(self.pointCloud_subvol_size)
        cube_source.SetZLength(self.pointCloud_subvol_size)
        self.cube_source = cube_source
        rotate= self.pointCloud_rotation
        # print("Rotate", self.pointCloud_rotation)
        transform = vtk.vtkTransform()
        # save reference
        self.transform = transform
        # rotate around the center of the image data
        # print("ROTATE: ", self.pointCloud_rotation[2])
        self.transform.RotateX(self.pointCloud_rotation[0])
        self.transform.RotateY(self.pointCloud_rotation[1])
        self.transform.RotateZ(self.pointCloud_rotation[2])
        t_filter = vtk.vtkTransformPolyDataFilter()
        t_filter.SetInputConnection(self.cube_source.GetOutputPort())
        t_filter.SetTransform(self.transform)
        self.cube_transform_filter = t_filter
        self.cube_transform_filter.Update()
        self.cube_source.Update()
        #cube_source.SetRadius(spacing[0])

        # # mapper for the glyphs
        sphere_mapper = vtk.vtkPolyDataMapper()
        # # save reference
        self.cubesphere_mapper = sphere_mapper
        # # sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )

        subv_glyph.SetInputConnection( self.polydata_masker.GetOutputPort() )


        if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
            #print("CUBE")
            self.glyph_source = self.cube_transform_filter #self.cube_source
            self.cubesphere.SetSourceConnection(self.cube_transform_filter.GetOutputPort())
        else:
            #print("SPHERE")
            self.glyph_source = self.sphere_source
            self.cubesphere.SetSourceConnection(self.sphere_source.GetOutputPort())
        
        #self.cubesphere.SetSourceConnection( self.glyph_source.GetOutputPort() )
        self.cubesphere.Update()
        self.vis_widget_2D.PlaneClipper.AddDataToClip('subvol_actor', self.cubesphere.GetOutputPort())
        sphere_mapper.SetInputConnection( self.vis_widget_2D.PlaneClipper.GetClippedData('subvol_actor').GetOutputPort())
        self.cubesphere.Update()
        self.cubesphere.SetVectorModeToUseNormal()

        # # actor for the glyphs
        sphere_actor = vtk.vtkActor()
        # # save reference
        self.cubesphere_actor = sphere_actor
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1, 0, 0)
        #sphere_actor.GetProperty().SetColor(1, .2, .2)
        sphere_actor.GetProperty().SetOpacity(0.5)
        sphere_actor.GetProperty().SetLineWidth(2.0)
        sphere_actor.GetProperty().SetEdgeVisibility(True)
        sphere_actor.GetProperty().SetEdgeColor(1, .2, .2)
        sphere_actor.GetProperty().SetRenderLinesAsTubes(True)
        sphere_actor.GetProperty().SetRepresentationToWireframe()

        self.vis_widget_2D.frame.viewer.AddActor(actor, 'pc_actor')
        self.vis_widget_2D.frame.viewer.AddActor(sphere_actor, 'subvol_actor')
        self.cubesphere.Update()
        
    def setup3DPointCloudPipeline(self):
        #polydata_masker = self.polydata_masker

        mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.pointmapper = mapper
        mapper.SetInputConnection(self.polydata_masker.GetOutputPort())

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

        # # mapper for the glyphs
        sphere_mapper = vtk.vtkPolyDataMapper()
        # # save reference
        self.cubesphere_mapper3D = sphere_mapper
        sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )

        # # actor for the glyphs
        sphere_actor = vtk.vtkActor()
        # # save reference
        self.cubesphere_actor3D = sphere_actor
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1, 0, 0)
        sphere_actor.GetProperty().SetOpacity(1)
        sphere_actor.GetProperty().SetRepresentationToWireframe() #wireframe
        sphere_actor.GetProperty().SetLineWidth(3.0)

        self.vis_widget_3D.frame.viewer.getRenderer().AddActor(actor)
        self.vis_widget_3D.frame.viewer.getRenderer().AddActor(sphere_actor)

        if not hasattr(self, 'actors3D'):
            self.actors_3D = {}
        
        self.actors_3D['pc_actor'] = actor
        self.actors_3D ['subvol_actor'] = sphere_actor

# Registration Panel:
    def CreateRegistrationPanel(self):
        """Create the Registration Dockable Widget"""

        self.registration_panel = generateUIDockParameters(self, '2 - Initial Registration')
        dockWidget = self.registration_panel[0]
        dockWidget.setObjectName("RegistrationPanel")
        groupBox = self.registration_panel[5]
        groupBox.setTitle('Registration Parameters')
        formLayout = self.registration_panel[6]

        # Create validation rule for text entry
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        rp = {}

        dockWidget.visibilityChanged.connect(self.displayRegistrationViewer)

        point0_text = "The rigid body offset will be centered on this point.\n\
If it falls within your chosen mask, this will be the first point of the ROI cloud.\n\
It is used as a global starting point and a translation reference."
        
        # Button select point0
        rp['select_point_zero'] = QPushButton(groupBox)
        rp['select_point_zero'].setText("Select Point 0")
        rp['select_point_zero'].setEnabled(True)
        rp['select_point_zero'].setCheckable(True)
        rp['select_point_zero'].setChecked(False)
        rp['select_point_zero'].setToolTip(point0_text)
        rp['select_point_zero'].clicked.connect( lambda: self.selectPointZero() )
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['select_point_zero'])
        widgetno += 1
        # Point0 Location
        rp['point_zero_label'] = QLabel(groupBox)
        rp['point_zero_label'].setText("Point Zero Location")
        rp['point_zero_label'].setToolTip(point0_text)
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

        # Registration Box
        rp['registration_box_size_label'] = QLabel(groupBox)
        rp['registration_box_size_label'].setText("Registration Box Size")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['registration_box_size_label'])
        rp['registration_box_size_entry'] = QSpinBox(groupBox)
        rp['registration_box_size_entry'].setSingleStep(1)
        rp['registration_box_size_entry'].setValue(200)
        rp['registration_box_size_entry'].setMaximum(200)
        rp['registration_box_size_entry'].setEnabled(True)
        rp['registration_box_size_entry'].valueChanged.connect(self.displayRegistrationSelection)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['registration_box_size_entry'])
        widgetno += 1


        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1

        translation_tooltip_text = "These translations will be input to the DVC code as the rigid body offset."
        # Translate X field
        rp['translate_X_label'] = QLabel(groupBox)
        rp['translate_X_label'].setText("Translate X")
        rp['translate_X_label'].setToolTip(translation_tooltip_text)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['translate_X_label'])
        rp['translate_X_entry']= QLineEdit(groupBox)
        rp['translate_X_entry'].setValidator(validatorint)
        rp['translate_X_entry'].setText("0")
        rp['translate_X_entry'].setToolTip(translation_tooltip_text)
        #rp['translate_X_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['translate_X_entry'])
        widgetno += 1
        # Translate Y field
        rp['translate_Y_label'] = QLabel(groupBox)
        rp['translate_Y_label'].setText("Translate Y")
        rp['translate_Y_label'].setToolTip(translation_tooltip_text)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['translate_Y_label'])
        rp['translate_Y_entry']= QLineEdit(groupBox)
        rp['translate_Y_entry'].setValidator(validatorint)
        rp['translate_Y_entry'].setText("0")
        rp['translate_Y_entry'].setToolTip(translation_tooltip_text)
        #rp['translate_Y_entry'].setEnabled(False) 
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['translate_Y_entry'])
        widgetno += 1
        # Translate Z field
        rp['translate_Z_label'] = QLabel(groupBox)
        rp['translate_Z_label'].setText("Translate Z")
        rp['translate_Z_label'].setToolTip(translation_tooltip_text)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['translate_Z_label'])
        rp['translate_Z_entry']= QLineEdit(groupBox)
        rp['translate_Z_entry'].setValidator(validatorint)
        rp['translate_Z_entry'].setText("0")
        rp['translate_Z_entry'].setToolTip(translation_tooltip_text)
        #rp['translate_Z_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['translate_Z_entry'])
        widgetno += 1

        # Add submit button
        rp['start_registration_button'] = QPushButton(groupBox)
        rp['start_registration_button'].setText("Start Registration")
        rp['start_registration_button'].setCheckable(True)
        rp['start_registration_button'].setEnabled(True)
        rp['start_registration_button'].clicked.connect(self.OnStartStopRegistrationPushed)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['start_registration_button'])
        widgetno += 1

        # Add cancel automatic registration button
        rp['cancel_auto_reg_button'] = QPushButton(groupBox)
        rp['cancel_auto_reg_button'].setText("Reset")
        rp['cancel_auto_reg_button'].setEnabled(True)
        rp['cancel_auto_reg_button'].clicked.connect(self.cancelAutomaticRegistration)
        formLayout.insertRow(widgetno - 1, '', rp['cancel_auto_reg_button'])
        widgetno += 1
        rp['cancel_auto_reg_button'].setVisible(False)

        # Add set to automatic registration button
        rp['set_auto_reg_button'] = QPushButton(groupBox)
        rp['set_auto_reg_label'] = QLabel(groupBox)
        rp['set_auto_reg_button'].setText("Set to Automatic Registration")
        rp['set_auto_reg_label'].setText("Automatic registration [0, 0, 0]")
        rp['set_auto_reg_button'].setEnabled(True)
        rp['set_auto_reg_button'].clicked.connect(self.setToAutomaticRegistration)
        formLayout.insertRow(widgetno - 1, rp['set_auto_reg_label'] , rp['set_auto_reg_button'])
        widgetno += 1
        rp['set_auto_reg_button'].setVisible(False)
        rp['set_auto_reg_label'].setVisible(False)

        # Add cancel registration button
        rp['cancel_reg_button'] = QPushButton(groupBox)
        rp['cancel_reg_button'].setText("Cancel")
        rp['cancel_reg_button'].setEnabled(True)
        rp['cancel_reg_button'].clicked.connect(self.cancelRegistration)
        formLayout.insertRow(widgetno, '', rp['cancel_reg_button'])
        widgetno += 1
        rp['cancel_reg_button'].setVisible(False)

        # Add elements to layout
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)
        # save to instance
        self.registration_parameters = rp

    def createRegistrationViewer(self):
        # print("Create reg viewer")
        #Get current orientation and slice of 2D viewer, registration viewer will be set up to have these
        self.orientation = self.vis_widget_2D.frame.viewer.getSliceOrientation()
        self.current_slice = self.vis_widget_2D.frame.viewer.getActiveSlice()

        self.vis_widget_reg = VisualisationWidget(self, viewer2D)
        

        reg_viewer_dock = QDockWidget("Image Registration",self.RightDockWindow)
        reg_viewer_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        reg_viewer_dock.setObjectName("2DRegView")
        reg_viewer_dock.setWidget(self.vis_widget_reg)
        #reg_viewer_dock.setMinimumHeight(self.size().height()*0.9)


        self.reg_viewer_dock = reg_viewer_dock
        
        self.RightDockWindow.addDockWidget(Qt.TopDockWidgetArea,reg_viewer_dock)


        self.vis_widget_reg.setImageData(self.ref_image_data)
        self.vis_widget_reg.displayImageData()
        self.viewer2D_dock.setVisible(False)
        self.viewer3D_dock.setVisible(False)

        #Clear for next image visualisation:
        self.orientation = None
        self.current_slice = None

        self.vis_widget_reg.frame.viewer.style.AddObserver("MouseWheelForwardEvent",
                                    self.vis_widget_reg.PlaneClipper.UpdateClippingPlanes, 0.9)
        self.vis_widget_reg.frame.viewer.style.AddObserver("MouseWheelBackwardEvent",
                                    self.vis_widget_reg.PlaneClipper.UpdateClippingPlanes, 0.9)
        
        self.vis_widget_reg.frame.viewer.style.AddObserver("KeyPressEvent",
                                    self.vis_widget_reg.PlaneClipper.UpdateClippingPlanes, 0.9)
        self.vis_widget_reg.frame.viewer.style.AddObserver("KeyPressEvent",
                                    self.vis_widget_reg.PlaneClipper.UpdateClippingPlanes, 0.9)

        self.vis_widget_reg.frame.viewer.style.AddObserver('KeyPressEvent', self.OnKeyPressEventForRegistration, 1.5) #Happens before viewer KeyPressEvent (higher priority)
        self.vis_widget_reg.frame.viewer.style.AddObserver('KeyPressEvent', self.AfterKeyPressEventForRegistration, 0.5) #Happens after viewer KeyPressEvent (lower priority)

    def displayRegistrationViewer(self,registration_open):
        
        if hasattr(self, 'ref_image_data'):
            #check for image data else do nothing
            if registration_open:
                self.help_label.setText(self.help_text[1])
                if not hasattr(self, 'vis_widget_reg'):
                    # print("Creating reg viewer")
                    self.viewer2D_dock.setVisible(False)
                    self.viewer3D_dock.setVisible(False)
                    self.help_dock.setMaximumHeight(self.size().height()*0.2)
                    self.viewer_settings_dock.setMaximumHeight(self.size().height()*0.2)
                    self.createRegistrationViewer()
                else:
                    if self.vis_widget_reg.getImageData() != self.ref_image_data:
                        self.orientation = self.vis_widget_2D.frame.viewer.getSliceOrientation()
                        self.current_slice = self.vis_widget_2D.frame.viewer.getActiveSlice()
                        self.vis_widget_reg.setImageData(self.ref_image_data)
                        self.vis_widget_reg.displayImageData()

                    self.viewer2D_dock.setVisible(False)
                    self.viewer3D_dock.setVisible(False)
                    self.reg_viewer_dock.setVisible(True)
                    self.help_dock.setMaximumHeight(self.size().height()*0.2)
                    self.viewer_settings_dock.setMaximumHeight(self.size().height()*0.2)

            else:
                if (hasattr(self, 'reg_viewer_dock')):
                    if self.registration_parameters['start_registration_button'].isChecked():
                        self.registration_parameters['start_registration_button'].setChecked(False)
                        self.OnStartStopRegistrationPushed()
                    self.reg_viewer_dock.setVisible(False)
                    self.viewer2D_dock.setVisible(True)
                    self.viewer3D_dock.setVisible(True)

    def selectPointZero(self):
        if self.ref_image_data is not None:
                       
            rp = self.registration_parameters
            v = self.vis_widget_reg.frame.viewer
            
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
    
    def openFinishRegistrationDialog(self):       
        self.warningDialog(
            window_title='Registration Completed',
            message='Move to the next tab or restart the registration.'
            )

    def OnLeftButtonPressEventForPointZero(self, interactor, event):
        # print('OnLeftButtonPressEventForPointZero', event)
        v = self.vis_widget_reg.frame.viewer
        shift = interactor.GetShiftKey()          
        rp = self.registration_parameters
        
        if shift and rp['select_point_zero'].isChecked():
            position = interactor.GetEventPosition()
            p0l = v.style.image2world(v.style.display2imageCoordinate(position)[:-1])             
            self.createPoint0(p0l)

    def updatePoint0Display(self):
        """Updates the point 0 vtk.vtkCursor3D on the viewer to be centred
        on the current value of self.point0_world_coords (returned by getPoint0WorldCoords()).
        """
        #point0 , point0Mapper, point0Actor
        vox = self.getPoint0WorldCoords()
        for point0 in self.point0:
            point0[0].SetFocalPoint(*vox)
            point0[0].SetModelBounds(-10 + vox[0], 10 + vox[0], -10 + vox[1], 10 + vox[1], -10 + vox[2], 10 + vox[2])
            point0[0].Update()

        self.vis_widget_reg.PlaneClipper.UpdateClippingPlanes()

    def createPoint0(self, p0):
        v = self.vis_widget_reg.frame.viewer
        spacing = v.img3D.GetSpacing()
        origin = v.img3D.GetOrigin()
        #  print("Point0 WORLD: ", p0)
        self.point0_world_coords = copy.deepcopy(p0)
        self.point0_sampled_image_coords = copy.deepcopy(self.getPoint0ImageCoords())
        point0actor = 'Point0' in v.actors
        rp = self.registration_parameters
        vox = p0
        # print ("vox ", vox, 'p0', p0)

        rp = self.registration_parameters
        self.SetPoint0Text()


        if not point0actor:
            point0 = vtk.vtkCursor3D()
            point0.SetModelBounds(-10 + vox[0], 10 + vox[0], -10 + vox[1], 10 + vox[1], -10 + vox[2], 10 + vox[2])
            point0.SetFocalPoint(*vox)
            point0.AllOff()
            point0.AxesOn()
            point0.OutlineOn()
            point0.TranslationModeOn()
            point0.Update()

            self.point0 = []
            viewer_widgets = [self.vis_widget_2D, self.vis_widget_reg, self.vis_widget_3D]

            for viewer_widget in viewer_widgets:
                point0Mapper = vtk.vtkPolyDataMapper()
                if viewer_widget.viewer == viewer2D:
                    viewer_widget.PlaneClipper.AddDataToClip('Point0', point0.GetOutputPort())
                    point0Mapper.SetInputConnection(viewer_widget.PlaneClipper.GetClippedData('Point0').GetOutputPort())
                else:
                    point0Mapper.SetInputConnection(point0.GetOutputPort())

                point0Actor = vtk.vtkLODActor()
                point0Actor.SetMapper(point0Mapper)
                point0Actor.GetProperty().SetColor(1.,0.,0.)
                point0Actor.GetProperty().SetLineWidth(2.0)

                if viewer_widget.viewer == viewer2D:
                    viewer_widget.frame.viewer.AddActor(point0Actor, 'Point0')
                else:
                    viewer_widget.frame.viewer.getRenderer().AddActor(point0Actor)

                self.point0.append((point0 , point0Mapper, point0Actor)) 
        
        else:
            self.updatePoint0Display()

        
        self.centerOnPointZero()

    def SetPoint0Text(self):
        if hasattr(self, 'point0_world_coords'):
            if self.visualisation_setting_widgets['coords_combobox'].currentIndex() == 0:
                self.registration_parameters['point_zero_entry'].setText(str([round(self.point0_world_coords[i]) for i in range(3)]))
            else:
                self.registration_parameters['point_zero_entry'].setText(str([round(self.point0_sampled_image_coords[i]) for i in range(3)]))

    def centerOnPointZero(self):
        """Centers the viewing slice on the registration viewer where Point 0 is.
        This makes sure that the point 0 is visible on the viewer, in the slicing direction.
        E.g. if point0 is at (5,6,7) and we are slicing in the Z direction, the viewer will 
        display slice Z=7.
        Produces a warning dialog if point0 has not yet been selected.
        """
        if hasattr(self, 'vis_widget_reg'):
            v = self.vis_widget_reg.frame.viewer

            if hasattr(self, 'point0_world_coords'):
                point0 = self.getPoint0ImageCoords()

                if isinstance (point0, tuple) or isinstance(point0, list):
                    #print("Tuple")
                    orientation = v.style.GetSliceOrientation()
                    gotoslice = point0[orientation]
                    v.style.SetActiveSlice( round(gotoslice) )
                    v.style.UpdatePipeline(True)
                    self.displayRegistrationSelection()
                    self.vis_widget_reg.PlaneClipper.UpdateClippingPlanes()
                else:
                    self.warningDialog("Choose a Point 0 first.", "Error")
            else:
                self.warningDialog("Choose a Point 0 first.", "Error")

    def displayRegistrationSelection(self):
        if hasattr(self, 'vis_widget_reg'):
            #print ("displayRegistrationSelection")
            rp = self.registration_parameters
            v = self.vis_widget_reg.frame.viewer
            rbdisplay = 'registration_box_actor' in v.actors
        else:
            return

        if hasattr(self, 'point0_world_coords'):
            point0 = self.getPoint0WorldCoords()

            reg_box_size = self.getRegistrationBoxSizeInWorldCoords()

            if not rbdisplay:
                
                cube_source = vtk.vtkCubeSource()
                cube_source.SetXLength(reg_box_size)
                cube_source.SetYLength(reg_box_size)
                cube_source.SetZLength(reg_box_size)
                cube_source.SetCenter(point0)
                cube_source.Update()

                self.registration_box = []
                viewer_widgets = [self.vis_widget_2D, self.vis_widget_reg, self.vis_widget_3D]

                for viewer_widget in viewer_widgets:
                    RegistrationBoxMapper = vtk.vtkPolyDataMapper()
                    if viewer_widget.viewer == viewer2D:
                        viewer_widget.PlaneClipper.AddDataToClip('registration_box_actor', cube_source.GetOutputPort())
                        RegistrationBoxMapper.SetInputConnection(viewer_widget.PlaneClipper.GetClippedData('registration_box_actor').GetOutputPort())
                    else:
                        RegistrationBoxMapper.SetInputConnection(cube_source.GetOutputPort())
                
                    RegistrationBoxActor = vtk.vtkLODActor()
                    RegistrationBoxActor.SetMapper(RegistrationBoxMapper)
                    RegistrationBoxActor.GetProperty().SetColor(0.,.5,.5)
                    RegistrationBoxActor.GetProperty().SetLineWidth(2.0)
                    RegistrationBoxActor.GetProperty().SetEdgeColor(0.,.5,.5)
                    RegistrationBoxActor.GetProperty().SetRepresentationToWireframe()

                    if viewer_widget.viewer == viewer2D:
                        RegistrationBoxActor.GetProperty().SetOpacity(0.5)
                        RegistrationBoxActor.GetProperty().SetLineWidth(4.0)
                        RegistrationBoxActor.GetProperty().SetEdgeVisibility(True)
                        RegistrationBoxActor.GetProperty().SetRenderLinesAsTubes(True)
                        viewer_widget.frame.viewer.AddActor(RegistrationBoxActor, 'registration_box_actor')
                    else:
                        viewer_widget.frame.viewer.getRenderer().AddActor(RegistrationBoxActor)
                        if not hasattr(self, 'actors_3D'):
                            self.actors_3D = {}
                        self.actors_3D ['registration_box_actor'] = RegistrationBoxActor
                    
                    self.registration_box.append({'source': cube_source , 'mapper': RegistrationBoxMapper,
                                            'actor': RegistrationBoxActor , 'viewer': viewer_widget.frame.viewer})
                    v.style.UpdatePipeline()
            else:
                for i, viewer_box_info in enumerate(self.registration_box):
                    viewer_box_info['actor'].VisibilityOn()
                    cube_source = viewer_box_info['source']
                    cube_source.SetXLength(reg_box_size)
                    cube_source.SetYLength(reg_box_size)
                    cube_source.SetZLength(reg_box_size)
                    cube_source.SetCenter(point0)
                    viewer_box_info['viewer'].style.UpdatePipeline()
  
    def getRegistrationBoxSizeInWorldCoords(self):
        # The value the user sets is in the world coords.
        rp = self.registration_parameters
        reg_box_size = rp['registration_box_size_entry'].value()
        return reg_box_size

    def getRegistrationBoxSizeInImageCoords(self):
        v = self.vis_widget_2D.frame.viewer 
        reg_box_size = v.style.world2imageCoordinates((0,0,self.getRegistrationBoxSizeInWorldCoords()))[2]
        return reg_box_size

    def getRegistrationBoxExtentInWorldCoords(self):
        '''
        Sets self.registration_box_extent to the extent of the registration box in world coordinates.
        The extent is a list of 6 values: [xmin, xmax, ymin, ymax, zmin, zmax]
        Returns self.registration_box_extent
        '''
        p0 = self.getPoint0WorldCoords()
        reg_box_size = self.getRegistrationBoxSizeInWorldCoords()

        extent = [ p0[0] - reg_box_size//2, p0[0] + reg_box_size//2, 
                    p0[1] - reg_box_size//2, p0[1] + reg_box_size//2, 
                    p0[2] - reg_box_size//2, p0[2] + reg_box_size//2]
        extent = [round(el) if el > 0 else 0 for el in extent] #TODO: add correction for upper bound as well
        self.registration_box_extent = extent

        return extent

    def getPoint0WorldCoords(self):
        p0 = self.point0_world_coords
        return p0

    def getPoint0ImageCoords(self):
        # The 2D viewer has image coordinates of the sampled image
        # Its world coordinates are the world coordinates of the unsampled image.
        # Before registration, the coord system of the reg_viewer is identical to the 2D viewer.
        # During registration the reg_viewer has the coord system of the unsampled image. The image coords take into account any spacing
        # The world coordinates of the reg_viewer are the same before and during registration and are the same as the 2D viewer's

        rp = self.registration_parameters
        p0_world = self.getPoint0WorldCoords()
        p0 =  self.vis_widget_reg.frame.viewer.style.world2imageCoordinate(p0_world)       

        p0 = [round(i) for i in p0]

        #print("Point0 orig image coords", p0)

        return p0

    def OnStartStopRegistrationPushed(self):
        ''' This method is triggered by pressing the "Start Registration" button or the "Confirm Registration" button.
        When the button is pressed again after the first registration, the button text is "Restart registration".
        '''
        rp = self.registration_parameters
        if "Restart registration" in rp['start_registration_button'].text():
            self.translate = None
            rp['translate_X_entry'].setText("0")
            rp['translate_Y_entry'].setText("0")
            rp['translate_Z_entry'].setText("0")
       
        if hasattr(self, 'vis_widget_reg'):
            self.UpdateViewerSettingsPanelForRegistration()
            if rp['start_registration_button'].isChecked(): # "Start Registration" has been pressed
                self.startRegistration()            
            else: # "Confirm Registration" has been pressed
                self.confirmRegistration()     
                self.openFinishRegistrationDialog()        

    def startRegistration(self):
        """
        If "Start Registration" is pressed:
        - the text on the button is changed to "Confirm Registration"
        - the widgets for setting point0, the registration box size and the translation are disabled
        - the size of the registration box may be updated to make sure it does not exceed the image extent
        - sets up self.translate, which is a vtk.vtkImageTranslateExtent() object, with translation values linked to the values in the translation widgets
        - calls LoadImagesAndCompleteRegistration()
        """
        rp = self.registration_parameters
        # check if we can make registration box, by checking
        # if the size of registration box is smaller than the difference 
        # between the current slice and the extent on the current dimension:
        registration_box_size = rp['registration_box_size_entry'].value()
        current_orientation = self.vis_widget_reg.frame.viewer.style.GetSliceOrientation()
        current_slice = self.vis_widget_reg.frame.viewer.getActiveSlice()
        extent_on_axis = self.vis_widget_reg.frame.viewer.img3D.GetExtent()[2*current_orientation+1] -1

        max_size_of_box = np.min([current_slice-1, extent_on_axis-current_slice])*2

        # if we can't make the registration box with the set size, then update
        # the size to the largest size possible:
        if max_size_of_box < registration_box_size:
            rp['registration_box_size_entry'].setMaximum(max_size_of_box)
        self.registration_parameters['start_registration_button'].setText("Confirm Registration")
        rp['cancel_reg_button'].setVisible(True)
        rp['registration_box_size_entry'].setEnabled(False)
        rp['select_point_zero'].setChecked(False)
        rp['select_point_zero'].setCheckable(False)
        rp['translate_X_entry'].setEnabled(False)
        rp['translate_Y_entry'].setEnabled(False)
        rp['translate_Z_entry'].setEnabled(False)
        # setup the appropriate stuff to run the registration
        if not hasattr(self, 'translate'):
            self.translate = vtk.vtkImageTranslateExtent()
        elif self.translate is None:
            self.translate = vtk.vtkImageTranslateExtent()
        #self.translate.SetTranslation(-int(rp['translate_X_entry'].text()),-int(rp['translate_Y_entry'].text()),-int(rp['translate_Z_entry'].text()))
        self.LoadImagesAndCompleteRegistration()

    def confirmRegistration(self):
        """
        if "Confirm Registration" is pressed:
        - the text on the button is changed to "Start Registration"
        - the widgets for setting point0, the registration box size and the translation are enabled
        - the full dimension (possibly downsampled) reference image is displayed on the viewer.
        """
        rp = self.registration_parameters
        v = self.vis_widget_reg.frame.viewer
        self.registration_parameters['start_registration_button'].setText("Restart registration")
        rp['registration_box_size_entry'].setEnabled(True)
        rp['select_point_zero'].setCheckable(True)
        rp['select_point_zero'].setChecked(False)
        #rp['translate_X_entry'].setEnabled(True)
        #rp['translate_Y_entry'].setEnabled(True)
        #rp['translate_Z_entry'].setEnabled(True)
        rp['cancel_auto_reg_button'].setVisible(False)
        rp['set_auto_reg_button'].setVisible(False)
        rp['set_auto_reg_label'].setVisible(False)
        v.setInput3DData(self.ref_image_data)
        v.style.UpdatePipeline()
        if rp['point_zero_entry'].text() != "":
            self.createPoint0(self.getPoint0WorldCoords())

    def UpdateViewerSettingsPanelForRegistration(self):
        vs_widgets = self.visualisation_setting_widgets
        rp = self.registration_parameters
        if rp['start_registration_button'].isChecked():
            self.current_coord_choice = copy.deepcopy(vs_widgets['coords_combobox'].currentIndex())
            vs_widgets['coords_combobox'].setCurrentIndex(0)
            vs_widgets['coords_combobox'].setEnabled(False)
            vs_widgets['coords_warning_label'].setVisible(False)
            vs_widgets['displayed_image_dims_label'].setVisible(False)
            vs_widgets['displayed_image_dims_value'].setVisible(False)
            self.vis_widget_reg.frame.viewer.setDisplayUnsampledCoordinates(False)
            self.vis_widget_reg.frame.viewer.setVisualisationDownsampling([1,1,1])
            vs_widgets['coords_info_label'].setText("The viewer displays the original image:")
            #vs_widgets['loaded_image_dims_label'].setText("Image Size: ")
            
            self.SetPoint0Text()
        else:
            if hasattr(self, 'current_coord_choice'):
                vs_widgets['coords_combobox'].setCurrentIndex(self.current_coord_choice)
                
                self.vis_widget_reg.frame.viewer.setDisplayUnsampledCoordinates(True)
                self.vis_widget_reg.frame.viewer.setVisualisationDownsampling(self.resample_rate)
                vs_widgets['coords_info_label'].setText("The viewer displays a downsampled image for visualisation purposes:")
                if self.resample_rate != [1,1,1]:
                    vs_widgets['coords_combobox'].setEnabled(True)
                    #vs_widgets['sample_level_value'].setText(str([round(self.resample_rate[i], 2) for i in range(3)]))
                    vs_widgets['displayed_image_dims_label'].setVisible(True)
                    vs_widgets['displayed_image_dims_value'].setVisible(True)
                else:
                    #vs_widgets['sample_level_value'].setText("None")
                    vs_widgets['displayed_image_dims_label'].setVisible(False)
                    vs_widgets['displayed_image_dims_value'].setVisible(False)
                    vs_widgets['coords_info_label'].setVisible(False)
                    
                self.SetPoint0Text()
                self.updateCoordinates()
                
                vs_widgets['loaded_image_dims_label'].setText("Original Image Size: ")
    
    def LoadImagesAndCompleteRegistration(self):
        '''
        1. Update self.unsampled_ref_image_data and self.unsampled_corr_image_data to contain the full resolution (unsampled) reference and correlate images,
           cropped on the Z axis to the current registration box extent.
        2. Run self.completeRegistration()
        '''

        if hasattr(self, 'registration_box_extent'):
            previous_reg_box_extent = copy.deepcopy(self.registration_box_extent)
        else:
            previous_reg_box_extent = None

        reg_box_extent = self.getRegistrationBoxExtentInWorldCoords()
        target_z_extent = tuple(self.enlarge_extent(2))

        self.target_cropped_image_z_extent = target_z_extent

        origin = [0,0,0] #TODO: set appropriately based on input image

        self.target_cropped_image_origin = origin

        self.unsampled_image_info = copy.deepcopy(self.image_info)
       
        if self.image_info['sampled']:
            
            if not (hasattr(self, 'unsampled_ref_image_data') and hasattr(self, 'unsampled_corr_image_data')):
                #print("About to create image")
                self.unsampled_ref_image_data = vtk.vtkImageData()
                ImageDataCreator.createImageData(self, self.image[0], self.unsampled_ref_image_data, info_var=self.unsampled_image_info, crop_image=True, origin=origin,
                                                 target_z_extent=target_z_extent, output_dir=os.path.abspath(tempfile.tempdir), finish_fn=self.LoadCorrImageForReg, crop_corr_image=True)
                #TODO: move to doing both image data creators simultaneously - would this work?
                return

            if previous_reg_box_extent != reg_box_extent: # If registration box is changed need to update the cropped images.
                ImageDataCreator.createImageData(self, self.image[0], self.unsampled_ref_image_data, info_var=self.unsampled_image_info, crop_image=True, origin=origin,
                                                 target_z_extent=target_z_extent, output_dir=os.path.abspath(tempfile.tempdir), finish_fn=self.LoadCorrImageForReg, crop_corr_image=True)
            else:
                self.completeRegistration()
            

        else:
            if not (hasattr(self, 'unsampled_ref_image_data') and hasattr(self, 'unsampled_corr_image_data')):
                self.unsampled_ref_image_data = self.ref_image_data 
                self.LoadCorrImageForReg(crop_corr_image=True)
            else:
                if previous_reg_box_extent != reg_box_extent:
                    self.LoadCorrImageForReg(crop_corr_image=True)
                else:
                    self.completeRegistration()

    def enlarge_extent(self, dim):
        """
        Given the regitration box size inputted by the user and the coordinates of the point zero wrt the unsampled volumes, 
        it returns 2*the box size in the direction specified by `dim`.         
        If the registration box is not fully included in the volumetric data, it accounts of the borders in both the negative 
        and positive directions.
        
        Parameters:
        dim : int
            Dimension along which to calculate the extent.
        """
        point0 = self.getPoint0WorldCoords()
        reg_box_size = self.getRegistrationBoxSizeInWorldCoords()
        target_extent = [round(point0[dim] - reg_box_size), round(point0[dim] + reg_box_size)]
        if target_extent[0] < 0:
            target_extent[0] = 0 
        if target_extent[1] > self.unsampled_image_dimensions[dim]:
            target_extent[1] = self.unsampled_image_dimensions[dim] 
        return target_extent

    def LoadCorrImageForReg(self,resample_corr_image= False, crop_corr_image = False): 
        """
        Loads the full resolution correlate image, cropped on the Z axis to the current registration box extent.
        Saves the result in self.unsampled_corr_image_data.
        Then runs self.completeRegistration()
        """
        origin = self.target_cropped_image_origin 
        z_extent = self.target_cropped_image_z_extent

        self.unsampled_corr_image_data = vtk.vtkImageData()
        ImageDataCreator.createImageData(self, self.image[1], self.unsampled_corr_image_data, info_var=self.unsampled_image_info, resample=resample_corr_image,
                                         crop_image=crop_corr_image, origin=origin, target_z_extent=z_extent, finish_fn=self.completeRegistration, output_dir=os.path.abspath(tempfile.tempdir))

    def completeRegistration(self):
        """It shows the registration difference volume in the viewer and sets up the tab for the registration. 
        It runs the automatic registration and shows the results and the extra buttons."""
        self.manualRegistration()
        automatic_reg_worker = Worker(self.automatic_reg_run)
        automatic_reg_worker.signals.result.connect(self.setRegistrationWidgetsFromWorker)
        self.threadpool.start(automatic_reg_worker)

    def setRegistrationWidgetsFromWorker(self,result):
        """
        Flips the result from the automatic registration class as numpy and vtk have different conventions.
        Updates widgets and viewer by calling `setRegistrationWidgets`.
        Updates the buttons.
        """
        self.auto_reg_result = np.flip(result)
        self.setRegistrationWidgets(self.auto_reg_result)
        rp = self.registration_parameters
        rp['set_auto_reg_label'].setText(f'Automatic registration {[self.auto_reg_result[0],self.auto_reg_result[1],self.auto_reg_result[2]]}')
        rp['cancel_auto_reg_button'].setVisible(True)
        rp['set_auto_reg_label'].setVisible(True)
        rp['set_auto_reg_button'].setVisible(True)
        
    def setRegistrationWidgets(self, array):
        """
        Updates the widgets and translates the viewer with the values stored in `array`.
        """
        
        # update widgets
        rp = self.registration_parameters
        rp['translate_X_entry'].setText(str(array[0])) 
        rp['translate_Y_entry'].setText(str(array[1])) 
        rp['translate_Z_entry'].setText(str(array[2]))
        # update viewer
        self.translate.SetTranslation(-int(array[0]),-int(array[1]),-int(array[2]))
        self.translate.Update()
        self.subtract.Update()
        self.reg_viewer_update(type = 'after automatic registration')

    def setRegistrationWidgetsShift(self, shift):   
        """
        Gets the total translation from the widgets.
        Updates the widgets and translates the viewer with the extra `shift`.
        """
        total_translation = self.getRegistrationTranslation()
        rp = self.registration_parameters
        rp['translate_X_entry'].setText(str(total_translation[0] + shift[0])) 
        rp['translate_Y_entry'].setText(str(total_translation[1] + shift[1])) 
        rp['translate_Z_entry'].setText(str(total_translation[2] + shift[2]))
        self.translate.SetTranslation(-int(total_translation[0] + shift[0]),-int(total_translation[1] + shift[1]),-int(total_translation[2] + shift[2]))
        self.translate.Update()
        self.subtract.Update()
        self.reg_viewer_update(type = 'after automatic registration')

    def getRegistrationTranslation(self):
        """Reads the current translation in the widgets and returns it."""
        rp = self.registration_parameters
        current_translation = np.array([int(rp['translate_X_entry'].text()),int(rp['translate_Y_entry'].text()),int(rp['translate_Z_entry'].text())])
        return current_translation
        
    def cancelAutomaticRegistration(self):
        """Resets the widgets and the viewer to no translation."""
        rp = self.registration_parameters
        self.setRegistrationWidgets(np.array([0,0,0]))

    def cancelRegistration(self):
        """Resets the widgets and the wiever to no translation and confirms the registration. Updates the buttons."""
        self.cancelAutomaticRegistration()
        self.confirmRegistration()
        self.registration_parameters['cancel_reg_button'].setVisible(False)
        self.registration_parameters['start_registration_button'].setChecked(False)

    def setToAutomaticRegistration(self):
        """Sets the widgets and the viewer to the translation calculated with the automatic registration procedure."""
        rp = self.registration_parameters
        self.setRegistrationWidgets(self.auto_reg_result)

    def manualRegistration(self):
        """
        1. Updates the point0 widget on the viewer to be centred on the location selected by the user.
        2. Translates the correlate image by the translation values set in the translation widgets, and subtracts the reference image from the translated correlate image.
        3. Updates the viewer to display the result of the subtraction.
        4. Centres the viewer on the slice that contains point 0.
        """
        self.updatePoint0Display()
        self.translateImages()
        #reg viewer update makes the text 0
        self.reg_viewer_update(type = 'starting registration')
        self.centerOnPointZero() 

    def resetRegistration(self):
        if hasattr(self, 'vis_widget_reg'):
            #print("About to del image reg viewer")
            self.displayRegistrationViewer(False)
            self.vis_widget_reg.createEmptyFrame()
            if hasattr(self, 'unsampled_ref_image_data'):
                del self.unsampled_ref_image_data
                del self.unsampled_corr_image_data

            self.translate = None

            rp = self.registration_parameters
            rp['select_point_zero'].setChecked(False)
            rp['translate_X_entry'].setText("0")
            rp['translate_Y_entry'].setText("0")
            rp['translate_Z_entry'].setText("0")
            rp['goto_point_zero'].setCheckable(False)
            rp['goto_point_zero'].setChecked(False)
            rp['point_zero_entry'].setText("")

            if hasattr(self, 'point0_world_coords'):
                del self.point0_world_coords

    def translateImages(self, progress_callback = None):
        '''
        Subtracts the reference image from the translated correlate image. Result is saved in self.subtract
        To do this the images must be cast to float first, and self.cast contains a list of the vtkImageCast
        objects set up for the reference and correlate images. 
        '''
        #progress_callback.emit(10)
        data = self.getRegistrationVOIs()
        data1 = data[0]
        data2 = data[1]

        self.translate.SetInputData(data2)
        self.translate.Update()
        #progress_callback.emit(45)

        # print ("out of the reader", reader.GetOutput())

        cast1 = vtk.vtkImageCast()
        cast2 = vtk.vtkImageCast()
        cast1.SetInputData(data1)
        cast1.SetOutputScalarTypeToFloat()
        cast2.SetInputConnection(self.translate.GetOutputPort())
        cast2.SetOutputScalarTypeToFloat()
        #progress_callback.emit(50)
        subtract = vtk.vtkImageMathematics()
        subtract.SetOperationToSubtract()
        subtract.SetInputConnection(1,cast1.GetOutputPort())
        subtract.SetInputConnection(0,cast2.GetOutputPort())
        #progress_callback.emit(70)
        
        subtract.Update()
        #progress_callback.emit(80)
        
        # print ("subtract type", subtract.GetOutput().GetScalarTypeAsString(), subtract.GetOutput().GetDimensions())
        
        stats = vtk.vtkImageHistogramStatistics()
        stats.SetInputConnection(subtract.GetOutputPort())
        stats.Update()
        #progress_callback.emit(90)
        # print ("stats ", stats.GetMinimum(), stats.GetMaximum(), stats.GetMean(), stats.GetMedian())
        self.subtract = subtract
        self.cast = [cast1, cast2]
        #progress_callback.emit(95)

    def getRegistrationVOIs(self, extent = None):            
        if extent is None:
            extent = self.getRegistrationBoxExtentInWorldCoords()

        # get the selected ROI
        voi = vtk.vtkExtractVOI()
        
        voi.SetInputData(self.unsampled_ref_image_data) 

        voi.SetVOI(*extent)
        voi.Update()

        # copy the data to be registered if selection 
        data1 = vtk.vtkImageData()
        data1.DeepCopy(voi.GetOutput())
        
        voi.SetInputData(self.unsampled_corr_image_data)
        
        # print ("Extracting selection")
        voi.Update()
        #progress_callback.emit(30)
        data2 = vtk.vtkImageData()
        data2.DeepCopy(voi.GetOutput())
        #progress_callback.emit(35)

        
        #progress_callback.emit(40)
        # print ("clearing memory")
        del voi

        return [data1, data2]

    def reg_viewer_update(self, type = None):
        '''
        Updates the translation widgets with the current translation on each axis.
        Updates the registration viewer to display the result of the difference between
        the reference and translated correlate image.

        Parameters
        ----------
        type : str
            If 'starting registration' then the registration viewer is centred on the slice that contains point 0.
            This is the case if the "Start Registration" button is pressed. Otherwise, when type=None we are in the middle of 
            registration and the viewer is centred on the current slice
            If 'manual registration' then the translation widgets are updated with the current translation on each axis.
            If 'automatic registration' then the translation widgets are not updated.
        '''
        # update the current translation on the interface:
        rp = self.registration_parameters
        if type == 'after automatic registration':
            pass
        if type == 'manual registration':
            rp['translate_X_entry'].setText(str(self.translate.GetTranslation()[0]*-1))
            rp['translate_Y_entry'].setText(str(self.translate.GetTranslation()[1]*-1))
            rp['translate_Z_entry'].setText(str(self.translate.GetTranslation()[2]*-1))
        printme = str(self.registration_parameters['translate_X_entry'].text())
        #print("after reg"+printme)
        #update the viewer:
        v = self.vis_widget_reg.frame.viewer
        if hasattr(v, 'img3D'):
            current_slice = v.getActiveSlice()
        
        v.setInputData(self.subtract.GetOutput())
        # print("Set the input data")

        if type == 'starting registration':
            v.style.UpdatePipeline()
            # v.startRenderLoop()
            self.centerOnPointZero()
        else:
            v.style.SetActiveSlice(round(current_slice))
            v.style.UpdatePipeline()
            # v.startRenderLoop()
            v.style.Render()

        if (self.progress_window.isVisible()):
            self.progress_window.setValue(100)
            self.progress_window.close()
        
    def OnKeyPressEventForRegistration(self, interactor, event):
        key_code = interactor.GetKeyCode()

        rp = self.registration_parameters
        if key_code in ['j','n','b','m'] and \
            rp['start_registration_button'].isChecked():
            self.translate_image_reg(key_code, event)
            self.reg_viewer_update(type = 'manual registration')

    def AfterKeyPressEventForRegistration(self, interactor, event):
        #Have to re-adjust registration VOI after the orientation has been switched by the viewer.
        key_code = interactor.GetKeyCode()
        rp = self.registration_parameters

        if key_code in ['x','y','z'] and rp['start_registration_button'].isChecked():
            rp['start_registration_button'].setChecked(True) #restart registration on correct orientation
            self.manualRegistration()

    def translate_image_reg(self, *args, **kwargs):
        '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''
        key_code, event = args
        rp = self.registration_parameters
        v = self.vis_widget_reg.frame.viewer
        trans = list(self.translate.GetTranslation())
        orientation = v.style.GetSliceOrientation()
        ij = [0,1]
        if orientation == SLICE_ORIENTATION_XY:
            ij = [0,1]
        elif orientation == SLICE_ORIENTATION_XZ:
            ij = [0, 2]
        elif orientation == SLICE_ORIENTATION_YZ:
            ij = [2, 1]
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

    def automatic_reg_run(self, **kwargs):
        """Runs the automatic registration. 
        
        This method prepares the arguments for the class `AutomaticRegistration` class and performs the registration process. 
        It retrieves the images in full resolution and crops them with an extended box.
        It evaluates the size of the box and the point zero in the box coordinate system.
        Then, it runs the registration procedure and returns the calculated shift.
        The class also outputs a logging file in the session directory.

        Returns:
        ----------------------------------------------------------------
        DD3d_accumulate : np.ndarray [int, int, int]
            The calculated 3D shift to register the two volumes.
        """
        # get images
        target_x_extent = self.enlarge_extent(0)
        target_y_extent = self.enlarge_extent(1)
        target_z_extent = self.enlarge_extent(2)
        extent = target_x_extent + target_y_extent + target_z_extent
        data = self.getRegistrationVOIs(extent)
        [image0,image1]=[Converter.vtk2numpy(el) for el in data]

        # get point zero and size in the box coordinate system
        p3d_0, size = self.find_p0_and_size()
        # run automatic registration class
        automatic_registration_object = AutomaticRegistration(image0,image1, p3d_0, size, log_folder = os.path.join(working_directory, 'DVC_Sessions'))
        automatic_registration_object.run()
        DD3d_accumulate=automatic_registration_object.DD3d_accumulate 
        return DD3d_accumulate

    def find_p0_and_size(self):
        """Finds the point zero and size of the registration box in the coordinate system of the registration box 
        and with the xyz ordering convention of `self.unsampled_ref_image_data`.
        If the registration box is not fully included in the volumetric data, it accounts for the borders in both the negative 
        and positive directions.
        
        Returns:
        tuple: A tuple containing the point zero and size of the registration box.
            - p3d_0 (np.ndarray) : The point zero in the registration box coordinate system.
            - size (np.ndarray) : The size of the registration box in each dimension.
        """
        point0 = self.getPoint0WorldCoords()
        reg_box_size = self.getRegistrationBoxSizeInWorldCoords()
        p3d_0 = np.array([reg_box_size, reg_box_size, reg_box_size])
        size = np.array([[reg_box_size//2,3*reg_box_size//2],[reg_box_size//2,3*reg_box_size//2],[reg_box_size//2,3*reg_box_size//2]])
        for dim in range(0,3):
            extent = [round(point0[dim] - reg_box_size), round(point0[dim] + reg_box_size)]
            size_extent = [round(point0[dim] - reg_box_size//2), round(point0[dim] + reg_box_size//2)]
            if extent[0] < 0:
                p3d_0[dim] = round(point0[dim])
                size[dim][1] = size_extent[1]
                if size_extent[0] < 0:
                    size[dim][0] = 0
                elif size_extent[0] > 0:
                    size[dim][0] = size_extent[0]
            if size_extent[1] > self.unsampled_image_dimensions[dim]:
                size[dim][1] = size[dim][1] - size_extent[1] + self.unsampled_image_dimensions[dim]

        return np.flip(p3d_0), np.flip(size, axis=0)

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
        mp_widgets['mask_extend_above_label'].setText("Slices Above ")
        mp_widgets['mask_extend_above_label'].setToolTip("Slices above the current plane to extend the mask to.")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, mp_widgets['mask_extend_above_label'])
        mp_widgets['mask_extend_above_entry'] = QSpinBox(groupBox)
        mp_widgets['mask_extend_above_entry'].setSingleStep(1)
        mp_widgets['mask_extend_above_entry'].setValue(10)
        mp_widgets['mask_extend_above_entry'].setEnabled(True)
        mp_widgets['mask_extend_above_entry'].setToolTip("Slices above the current plane to extend the mask to.")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['mask_extend_above_entry'])
        widgetno += 1

        mp_widgets['mask_extend_below_label'] = QLabel(groupBox)
        mp_widgets['mask_extend_below_label'].setText("Slices Below ")
        mp_widgets['mask_extend_below_label'].setToolTip("Slices below the current plane to extend the mask to.")
        
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, mp_widgets['mask_extend_below_label'])
        mp_widgets['mask_extend_below_entry'] = QSpinBox(groupBox)
        mp_widgets['mask_extend_below_entry'].setSingleStep(1)
        mp_widgets['mask_extend_below_entry'].setValue(10)
        mp_widgets['mask_extend_below_entry'].setEnabled(True)
        mp_widgets['mask_extend_below_entry'].setToolTip("Slices below the current plane to extend the mask to.")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['mask_extend_below_entry'])
        widgetno += 1

        mp_widgets['mask_downsampled_coords_warning'] = QLabel(groupBox)
        mp_widgets['mask_downsampled_coords_warning'].setText("Note: if your image has been downsampled, the number of slices is in the coordinates of the downsampled image.")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['mask_downsampled_coords_warning'])
        widgetno += 1

        # Add should extend checkbox
        mp_widgets['extendMaskCheck'] = QCheckBox(groupBox)
        mp_widgets['extendMaskCheck'].setText("Extend mask")
        mp_widgets['extendMaskCheck'].setToolTip("You may draw a second trace. Select extend mask to extend the mask to this second traced region.")
        mp_widgets['extendMaskCheck'].setEnabled(False)
        mp_widgets['extendMaskCheck'].stateChanged.connect(self.warnIfUnchecking)

        formLayout.setWidget(widgetno,QFormLayout.FieldRole, mp_widgets['extendMaskCheck'])
        widgetno += 1

        # Add start tracing button
        mp_widgets['start_tracing'] = QPushButton(groupBox)
        mp_widgets['start_tracing'].setText("Start Tracing")
        mp_widgets['start_tracing'].clicked.connect(self.ToggleTracing)
        mp_widgets['start_tracing'].setCheckable(True)
        mp_widgets['start_tracing'].setChecked(False)
        mp_widgets['start_tracing'].setToolTip("Begin drawing a region on the viewer to create a mask.")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp_widgets['start_tracing'])
        widgetno += 1

        # Add submit button
        mp_widgets['submitButton'] = QPushButton(groupBox)
        mp_widgets['submitButton'].setText("Create Mask")
        mp_widgets['submitButton'].clicked.connect(lambda: self.MaskWorker("extend"))
        mp_widgets['submitButton'].setToolTip("Press 'Start Tracing' button and draw a region on the viewer to create a mask.")
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

    def warnIfUnchecking(self):
        if not self.mask_parameters['extendMaskCheck'].isChecked() and self.mask_parameters['extendMaskCheck'].isEnabled():
            self.warningDialog(window_title="Attention", 
                               message="If you do not clear the mask and draw again the app will be very sad!" )

    def ToggleTracing(self):
        '''Toggles the tracing widget for tracing the mask'''
        # notice that the viewer will capture the keypress event linked with activating the tracing
        viewer = self.vis_widget_2D.getViewer()
        mp_widgets = self.mask_parameters
        # we come here after the user has clicked on the button:
        # thins means that if the button is checked, it was not before,
        # So the user expects to start tracing
        if mp_widgets['start_tracing'].isChecked():
            # enable tracing
            mp_widgets['start_tracing'].setText("Stop Tracing")
            viewer.imageTracer.On()
        else:
            # disable tracing
            mp_widgets['start_tracing'].setText("Start Tracing")
            viewer.imageTracer.Off()

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

            else:
                self.mask_worker = Worker(self.extendMask)
                self.mask_worker.signals.finished.connect(self.DisplayMask)
        elif type == "load mask":
            self.mask_worker = Worker(self.loadMask, load_session=False)
            self.mask_worker.signals.finished.connect(self.DisplayMask)
        elif type == "load session":
            self.mask_worker = Worker(self.loadMask, load_session=True)
            self.mask_worker.signals.finished.connect(lambda:self.DisplayMask(type = "load session"))
            
        self.create_progress_window("Loading", "Loading Mask")
        self.mask_worker.signals.progress.connect(self.progress)

        # disable tracing on the viewer and
        # set the button to unchecked and text to start tracing
        self._disableTracingAndResetUI()

        self.progress_window.setValue(10)
        self.threadpool.start(self.mask_worker)  
        self.mask_worker.signals.error.connect(self.select_mask)

    def ShowSaveMaskWindow(self, save_only):
        if not self.mask_reader:
                self.warningDialog(window_title="Error", 
                               message="Create or load a mask on the viewer first." )
                return
        self.SaveWindow = SaveObjectWindow(self, "mask", save_only)
        self.SaveWindow.show()

    def extendMask(self, **kwargs):
        #if we have loaded the mask from a file then atm we cannot extend it bc we don't have stencil so need to set stencil somewhere?
        #we can easily get the image data v.image2 but would need a stencil?

        # print("Extend mask")
        progress_callback = kwargs.get('progress_callback', lambda x: logging.info("extendMask Progress: {}".format(x)))
        # setup the progress bar
        ui_update = partial(self.ui_progress_update, progress_callback)
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
        orientation = v.getSliceOrientation()
        lasso.SetSliceOrientation(orientation)
        lasso.SetInformationInput(image_data)

        self.mask_details['current'] = [orientation, sliceno]

        #Appropriate modification to Point Cloud Panel
        #self.updatePointCloudPanel()
        
        # create a blank image
        dims = image_data.GetDimensions()
        
        # progress_callback.emit(40)


        mask0 = Converter.numpy2vtkImage(np.zeros((dims[0],dims[1],dims[2]),order='F', 
                                            dtype=np.uint8),origin = image_data.GetOrigin(), spacing = image_data.GetSpacing())

        mask1 = Converter.numpy2vtkImage(np.ones((dims[0],dims[1],dims[2]),order='F', dtype=np.uint8),
                                            origin = image_data.GetOrigin(), spacing = image_data.GetSpacing())

        # print("Mask spacing:", mask0.GetSpacing())

        # Create a Mask from the lasso.
        stencil = vtk.vtkImageStencil()
        self.mask_reader = stencil
        stencil.SetInputData(mask1)
        stencil.SetBackgroundInputData(mask0)

        stencil.SetStencilConnection(lasso.GetOutputPort())

        stencil.AddObserver(vtk.vtkCommand.ProgressEvent, ui_update)
        stencil.Update()
        dims = stencil.GetOutput().GetDimensions()

        # progress_callback.emit(80)

        #print("Stencil dims: " + str(dims))

        down = self.mask_parameters['mask_extend_below_entry'].value()
        up = self.mask_parameters['mask_extend_above_entry'].value()

        # do not extend outside the image
        zmin = sliceno -down if sliceno-down>=0 else 0
        zmax = sliceno + up if sliceno+up < dims[orientation] else dims[orientation]

        #vtkutils.copyslices(stencil.GetOutput(), sliceno , zmin, zmax, orientation, None)
        stencil_output = self.copySlices(stencil.GetOutput(), sliceno , zmin, zmax, orientation, None)

        # progress_callback.emit(85)

        # save the mask to a file in temp folder
        writer = vtk.vtkMetaImageWriter()
        writer.SetCompression(True)
        tmpdir = tempfile.gettempdir()
        writer.SetFileName(os.path.join(tmpdir, "Masks", "latest_selection.mha"))
        self.mask_file = "Masks/latest_selection.mha"

        # progress_callback.emit(90)

        # if extend mask -> load temp saved mask
        if self.mask_parameters['extendMaskCheck'].isChecked():
            # self.setStatusTip('Extending mask')
            if os.path.exists(os.path.join(tmpdir, "Masks", "latest_selection.mha")):
                # print  ("extending mask ", os.path.join(tmpdir, "Masks/latest_selection.mha"))
                reader = vtk.vtkMetaImageReader()
                reader.SetFileName(os.path.join(tmpdir, "Masks", "latest_selection.mha"))
                reader.Update()

                math = vtk.vtkImageMathematics()
                math.SetOperationToAdd()
                #math.SetInput1Data(stencil.GetOutput())
                math.SetInput1Data(stencil_output)
                math.SetInput2Data(reader.GetOutput())
                math.Update()

                progress_callback.emit(1)
                threshold = vtk.vtkImageThreshold()
                threshold.ThresholdBetween(1, 255)
                threshold.ReplaceInOn()
                threshold.SetInValue(1)
                threshold.SetInputConnection(math.GetOutputPort())
                threshold.AddObserver(vtk.vtkCommand.ProgressEvent, ui_update)
                threshold.Update()

                writer.SetInputData(threshold.GetOutput())
                self.mask_data = threshold.GetOutput()
            # else:
            #     print  ("extending mask failed ", tmpdir)
        else:
            writer.SetInputData(stencil_output)
            self.mask_data = stencil_output

        # the writer only updates two values 0 and 1
        # also it blocks the interface (why???)
        # adding a pause allows the progress to update correctly
        writer.AddObserver(vtk.vtkCommand.ProgressEvent, ui_update)

        progress_callback.emit(99)
        import time
        time.sleep(1)
        writer.Write() # writes to file.
        self.mask_parameters['extendMaskCheck'].setEnabled(True)
        # self.setStatusTip('Done')

        # progress_callback.emit(100)
        self._disableTracingAndResetUI()

    def _disableTracingAndResetUI(self):
        # disable tracing on the viewer
        v = self.vis_widget_2D.frame.viewer
        v.imageTracer.Off()
        # set the button to unchecked and text to start tracing
        self.mask_parameters['start_tracing'].setChecked(False)
        self.mask_parameters['start_tracing'].setText("Start Tracing")

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

    def loadMask(self, **kwargs): #loading mask from a file
        #print("Load mask")
        load_session = kwargs.get('load_session', False)
        progress_callback = kwargs.get('progress_callback', None)
        time.sleep(0.1) #required so that progress window displays
        # progress_callback.emit(30)
        
        
        v =  self.vis_widget_2D.frame.viewer
        if not isinstance(v.img3D, vtk.vtkImageData):
            return 
            
        #print("loadMask")

        self.mask_reader = vtk.vtkMetaImageReader()
        self.mask_reader.AddObserver("ErrorEvent", self.e)
        tmpdir = tempfile.gettempdir()
        if (load_session):
            self.mask_reader.SetFileName(os.path.join(tmpdir, "Masks", "latest_selection.mha"))
            # progress_callback.emit(40)
        else:
            filename = self.mask_parameters["masksList"].currentText()
            self.mask_reader.SetFileName(os.path.join(tmpdir, "Masks", filename))
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
            # progress_callback.emit(60)
        
        ui_update = partial(self.ui_progress_update, progress_callback)
        self.mask_reader.AddObserver(vtk.vtkCommand.ProgressEvent, ui_update)
        
        self.mask_reader.Update()
        progress_callback.emit(50)

        writer = vtk.vtkMetaImageWriter()
       
        writer.SetFileName(os.path.join(tmpdir, "Masks", "latest_selection.mha"))
        writer.SetInputConnection(self.mask_reader.GetOutputPort())
        # progress_callback.emit(80)
        writer.AddObserver(vtk.vtkCommand.ProgressEvent, ui_update)
        writer.Write()
        self.mask_file = "Masks/latest_selection.mha"
        
        
        dims = v.img3D.GetDimensions()
        #print("Image dims:" + str(v.img3D.GetDimensions()))
        #print("Mask dims:" + str(self.mask_reader.GetOutput().GetDimensions()))
        if not dims == self.mask_reader.GetOutput().GetDimensions():
            #print("Not compatible")
            return 
        self.mask_data = self.mask_reader.GetOutput()
        progress_callback.emit(100)

    def ui_progress_update(self, callback, vtkcaller, event):
        '''connects the progress from a vtkAlgorithm to a Qt callback from eqt Worker'''
        # print ("{} progress {}".format(type(vtkcaller), vtkcaller.GetProgress()))
        progress = vtkcaller.GetProgress()*100-1
        if progress < 0:
            progress = 0
        callback.emit(progress)

    def select_mask(self): 
        dialogue = QFileDialog()
        mask = dialogue.getOpenFileName(self,"Select a mask")[0]
        if mask:
            if ".mha" in mask:
                filename = os.path.basename(mask)
                shutil.copyfile(mask, os.path.join(tempfile.tempdir, "Masks", filename))
                self.mask_parameters["masksList"].addItem(filename)
                self.mask_parameters["masksList"].setCurrentText(filename)
                self.clearMask()
                self.MaskWorker("load mask")
            else:
                self.warningDialog("Please select a .mha file", "Error")

    def clearMask(self):
        self.mask_parameters['extendMaskCheck'].setEnabled(False)
        self.mask_parameters['extendMaskCheck'].setChecked(False)
        self.mask_parameters['submitButton'].setText("Create Mask")
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
        #Appropriate modification to Point Cloud Panel
        self.updatePointCloudPanel()

        self.mask_parameters['extendMaskCheck'].setEnabled(True)
        v = self.vis_widget_2D.frame.viewer
        if (hasattr(self,'mask_data')):
            ui_update = partial(lambda dialog, vtkcaller, event: dialog.setValue(vtkcaller.GetProgress()*100), self.progress_window)
            v.imageSlice.AddObserver(vtk.vtkCommand.ProgressEvent, ui_update)
            v.setInputData2(self.mask_data)
            # we loaded the mask, the app crashes if someone clicks on create mask
            # without clearing the mask first unless extendMaskCheck is checked 
            # Forcibly check extend mask checkbox
            self.mask_parameters['extendMaskCheck'].setChecked(True)
        else:
            if v.img3D:
                self.warningDialog( 
                        window_title="Error", 
                        message="Mask and Dataset are not compatible",
                        detailed_text='Dataset dimensions {}\nMask dimensions {}'\
                            .format(str(v.img3D.GetDimensions()),
                                    self.mask_reader.GetOutput().GetDimensions()))

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
                #print("ROI: ", self.roi)
                self.PointCloudWorker("load pointcloud file")
                self.pointCloudLoaded = True
        

# Point Cloud Panel:

    def CreatePointCloudPanel(self):

        self.pointCloudDockWidget = QDockWidget(self)
        self.pointCloudDockWidget.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.pointCloudDockWidget.setWindowTitle('4 - Point Cloud')
        self.pointCloudDockWidget.setObjectName("PointCloudPanel")
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
        self.isoValueLabel.setText("Subvolume size")
        self.isoValueLabel.setToolTip("Defines the diameter or side length of the subvolumes created around each search point. This is in units of voxels on the original image.")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.isoValueLabel)
        self.isoValueEntry= QLineEdit(self.graphParamsGroupBox)
        self.isoValueEntry.setValidator(validatorint)
        self.isoValueEntry.setText('30')
        self.isoValueEntry.setToolTip("Defines the diameter or side length of the subvolumes created around each search point. This is in units of voxels on the original image.")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.isoValueEntry)
        self.isoValueEntry.textChanged.connect(self.displaySubvolumePreview)

        widgetno += 1
        pc['pointcloud_size_entry'] = self.isoValueEntry

        pc['subvolume_preview_check'] = QCheckBox(self.graphParamsGroupBox)
        pc['subvolume_preview_check'].setText("Display Subvolume Preview")
        pc['subvolume_preview_check'].setChecked(True)
        pc['subvolume_preview_check'].stateChanged.connect( partial(self.showHideActor,actor_name='subvol_preview_actor') )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['subvolume_preview_check'])
        widgetno += 1

        # Add collapse priority field
        self.subvolumeShapeLabel = QLabel(self.graphParamsGroupBox)
        self.subvolumeShapeLabel.setText("Subvolume shape")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.subvolumeShapeLabel)
        self.subvolumeShapeValue = QComboBox(self.graphParamsGroupBox)
        self.subvolumeShapeValue.addItem("Cube")
        self.subvolumeShapeValue.addItem("Sphere")
        self.subvolumeShapeValue.setCurrentIndex(0)
        self.subvolumeShapeValue.currentTextChanged.connect(self.displaySubvolumePreview)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.subvolumeShapeValue)
        widgetno += 1
        pc['pointcloud_volume_shape_entry'] = self.subvolumeShapeValue

        # Add horizonal seperator
        # Generate panel
        self.seperator = QFrame(self.graphParamsGroupBox)
        self.seperator.setFrameShape(QFrame.HLine)
        self.seperator.setFrameShadow(QFrame.Raised)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.SpanningRole, self.seperator)
        widgetno += 1
        # Load point cloud section 
        # add a separator and title
        generatePointCloudLabel = QLabel("Generate Pointcloud", self.graphParamsGroupBox)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, generatePointCloudLabel)
        widgetno += 1


        # Add collapse priority field
        self.dimensionalityLabel = QLabel(self.graphParamsGroupBox)
        self.dimensionalityLabel.setText("Dimensionality")
        self.dimensionalityLabel.setToolTip("A 2D pointcloud is created only on the currently viewed plane.\n\
A 3D pointcloud is created within the full extent of the mask.")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.dimensionalityLabel)
        self.dimensionalityValue = QComboBox(self.graphParamsGroupBox)
        self.dimensionalityValue.addItems(["3D","2D"])
        self.dimensionalityValue.setCurrentIndex(0)
        self.dimensionalityValue.currentIndexChanged.connect(self.updatePointCloudPanel)
        self.dimensionalityValue.setToolTip("A 2D pointcloud is created only on the currently viewed plane.\n\
A 3D pointcloud is created within the full extent of the mask.")

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.dimensionalityValue)
        widgetno += 1
        pc['pointcloud_dimensionality_entry'] = self.dimensionalityValue

        v = self.vis_widget_2D.frame.viewer
        orientation = v.getSliceOrientation()

        # Add Log Tree field
        overlap_tooltip_text = "Overlap as a fraction of the subvolume size."
        # Add Overlap X

        self.overlapLabel = QLabel("Overlap", self.graphParamsGroupBox)
        self.overlapLabel.setToolTip(overlap_tooltip_text)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapLabel)

        overlap_layout = QHBoxLayout()
        overlap_layout.setContentsMargins(0,0,0,0)

        self.overlapXLabel = QLabel(self.graphParamsGroupBox)
        self.overlapXLabel.setText("X: ")
        overlap_layout.addWidget(self.overlapXLabel)
        self.overlapXLabel.setToolTip(overlap_tooltip_text)
        self.overlapXValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapXLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.overlapXValueEntry.setValue(0.20)
        self.overlapXValueEntry.setMaximum(0.99)
        self.overlapXValueEntry.setMinimum(0.00)
        self.overlapXValueEntry.setSingleStep(0.01)
        self.overlapXValueEntry.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self.overlapXValueEntry.valueChanged.connect(self.displaySubvolumePreview)
        self.overlapXValueEntry.setToolTip(overlap_tooltip_text)
        if orientation == 0:
            self.overlapXValueEntry.setEnabled(False)

        overlap_layout.addWidget(self.overlapXValueEntry)
        pc['pointcloud_overlap_x_entry'] = self.overlapXValueEntry
        # Add Overlap Y
        self.overlapYLabel = QLabel(self.graphParamsGroupBox)
        self.overlapYLabel.setText("Y: ")
        self.overlapYLabel.setToolTip(overlap_tooltip_text)
        self.overlapYLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        overlap_layout.addWidget(self.overlapYLabel)
        self.overlapYValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapYValueEntry.setValue(0.20)
        self.overlapYValueEntry.setMaximum(0.99)
        self.overlapYValueEntry.setMinimum(0.00)
        self.overlapYValueEntry.setSingleStep(0.01)
        self.overlapYValueEntry.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self.overlapYValueEntry.valueChanged.connect(self.displaySubvolumePreview)
        self.overlapYValueEntry.setToolTip(overlap_tooltip_text)
        if orientation == 1:
            self.overlapYValueEntry.setEnabled(False)

        overlap_layout.addWidget(self.overlapYValueEntry)
        pc['pointcloud_overlap_y_entry'] = self.overlapYValueEntry
        # Add Overlap Z
        self.overlapZLabel = QLabel(self.graphParamsGroupBox)
        self.overlapZLabel.setText("Z: ")
        self.overlapZLabel.setToolTip(overlap_tooltip_text)
        self.overlapZLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        overlap_layout.addWidget(self.overlapZLabel)
        self.overlapZValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapZValueEntry.setValue(0.20)
        self.overlapZValueEntry.setMaximum(0.99)
        self.overlapZValueEntry.setMinimum(0.00)
        self.overlapZValueEntry.setSingleStep(0.01)
        self.overlapZValueEntry.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self.overlapZValueEntry.valueChanged.connect(self.displaySubvolumePreview)
        self.overlapZValueEntry.setToolTip(overlap_tooltip_text)
        if orientation == 2:
            self.overlapZValueEntry.setEnabled(False)

        overlap_layout.addWidget(self.overlapZValueEntry)
        overlap_layout.update()
        pc['pointcloud_overlap_z_entry'] = self.overlapZValueEntry

        overlap_widget = QWidget()
        overlap_widget.setLayout(overlap_layout)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, overlap_widget)
        widgetno+=1

        rotation_tooltip_text = "Rotation of the pointcloud in degrees."

        rotation_layout = QHBoxLayout()
        rotation_layout.setContentsMargins(0,0,0,0)

        self.rotationLabel = QLabel("Rotation Angle", self.graphParamsGroupBox)
        self.rotationLabel.setToolTip(rotation_tooltip_text)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.rotationLabel)

        # Add Rotation X
        self.rotateXLabel = QLabel(self.graphParamsGroupBox)
        self.rotateXLabel.setText("X: ")
        self.rotateXLabel.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateXLabel)
        self.rotateXValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateXValueEntry.setValidator(validator)
        self.rotateXValueEntry.setText("0.00")
        self.rotateXValueEntry.textChanged.connect(self.displaySubvolumePreview)
        self.rotateXValueEntry.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateXValueEntry)
        pc['pointcloud_rotation_x_entry'] = self.rotateXValueEntry

        # Add Overlap Y
        self.rotateYLabel = QLabel(self.graphParamsGroupBox)
        self.rotateYLabel.setText("Y: ")
        self.rotateYLabel.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateYLabel)
        self.rotateYValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateYValueEntry.setValidator(validator)
        self.rotateYValueEntry.setText("0.00")
        self.rotateYValueEntry.setToolTip(rotation_tooltip_text)
        self.rotateYValueEntry.textChanged.connect(self.displaySubvolumePreview)

        rotation_layout.addWidget(self.rotateYValueEntry)
        pc['pointcloud_rotation_y_entry'] = self.rotateYValueEntry

        # Add Overlap Z
        self.rotateZLabel = QLabel(self.graphParamsGroupBox)
        self.rotateZLabel.setText("Z: ")
        self.rotateZLabel.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateZLabel)
        self.rotateZValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateZValueEntry.setValidator(validator)
        self.rotateZValueEntry.setText("0.00")
        self.rotateZValueEntry.setToolTip(rotation_tooltip_text)
        self.rotateZValueEntry.textChanged.connect(self.displaySubvolumePreview)

        rotation_layout.addWidget(self.rotateZValueEntry)

        pc['pointcloud_rotation_z_entry'] = self.rotateZValueEntry

        rotation_widget = QWidget()
        rotation_widget.setLayout(rotation_layout)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, rotation_widget)
        widgetno+=1

        # Add should extend checkbox
        self.erodeCheck = QCheckBox(self.graphParamsGroupBox)
        self.erodeCheck.setText("Erode mask")
        self.erodeCheck.setToolTip("Mask erosion ensures the entirety of the subvolume regions are within the mask.")
        self.erodeCheck.setEnabled(True)
        self.erodeCheck.setChecked(False)
        
        self.erodeCheck.stateChanged.connect(lambda: 
            self.warningDialog('Erosion of mask may take long time!', 
                                window_title='WARNING', 
                                detailed_text='You may better leave this unchecked while experimenting with the point clouds' ) \
                                if self.erodeCheck.isChecked() else (lambda: True) )
        
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.erodeCheck)
        widgetno += 1
        pc['pointcloud_erode_entry'] = self.erodeCheck
        
        self.erodeRatioLabel =  QLabel(self.graphParamsGroupBox)
        self.erodeRatioLabel.setText("Erosion Multiplier")
        self.erodeRatioLabel.setToolTip("Adjust the level of mask erosion.")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.erodeRatioLabel)
        self.erodeRatioSpinBox = QDoubleSpinBox(self.graphParamsGroupBox)
        self.erodeRatioSpinBox.setEnabled(False)
        self.erodeRatioSpinBox.setSingleStep(0.1)
        self.erodeRatioSpinBox.setMaximum(1.50)
        self.erodeRatioSpinBox.setMinimum(0.1)
        self.erodeRatioSpinBox.setValue(1.00)
        self.erodeRatioSpinBox.setToolTip("Adjust the level of mask erosion.")
        self.erodeCheck.stateChanged.connect(lambda: self.erodeRatioSpinBox.setEnabled(True) if self.erodeCheck.isChecked() else  self.erodeRatioSpinBox.setEnabled(False))
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.erodeRatioSpinBox)
        widgetno += 1
        

        # Add submit button
        self.graphParamsSubmitButton = QPushButton(self.graphParamsGroupBox)
        self.graphParamsSubmitButton.setText("Generate Point Cloud")
        self.graphParamsSubmitButton.clicked.connect(self._generatePointCloudClicked)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.graphParamsSubmitButton)
        widgetno += 1
        # Add elements to layout
        self.graphWidgetVL.addWidget(self.graphParamsGroupBox)
        self.graphDockVL.addWidget(self.dockWidget)
        self.pointCloudDockWidget.setWidget(self.pointCloudDockWidgetContents)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.pointCloudDockWidget)
        widgetno += 1

        # Load point cloud section 
        # add a separator and title
        seperator = QFrame(self.graphParamsGroupBox)
        seperator.setFrameShape(QFrame.HLine)
        seperator.setFrameShadow(QFrame.Raised)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.SpanningRole, seperator)
        widgetno += 1
        generatePointCloudLabel = QLabel("Load Pointcloud", self.graphParamsGroupBox)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, generatePointCloudLabel)
        widgetno += 1

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
        pc['roi_browse'].setToolTip("Specify the file containing data for all measurement points in the Region of Interest (ROI).\n\
The ROI is defined as a cloud of points that fill a geometric region within the reference volume.\n\
Point cloud size, shape, and density are completely flexible, as long as all points fall within the image volumes.\n\
Dense point clouds that accurately reflect sample geometry and reflect measurement objectives yield the best results.\n\
Each line in the tab delimited file contains an integer point label followed by the x,y,z point location, e.g. \n\
1   300   750.2  208\n\
2   300   750.2  209\n\
etc.\n\
Non-integer voxel locations are admitted, with reference volume interpolation used as needed.\n\
The first point is significant, as it is used as a global starting point and reference for the rigid_trans variable.\n\
File format allowed: 'roi', 'txt', 'csv, 'xlxs', 'inp'.")
        
        pc['roi_browse'].clicked.connect(self.select_pointcloud)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['roi_browse'])
        widgetno += 1

        # Display point cloud section 
        # add a separator and title
        seperator = QFrame(self.graphParamsGroupBox)
        seperator.setFrameShape(QFrame.HLine)
        seperator.setFrameShadow(QFrame.Raised)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.SpanningRole, seperator)
        widgetno += 1
        generatePointCloudLabel = QLabel("Display Pointcloud", self.graphParamsGroupBox)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, generatePointCloudLabel)
        widgetno += 1

        pc['clear_button'] = QPushButton(self.graphParamsGroupBox)
        pc['clear_button'].setText("Clear Point Cloud")
        pc['clear_button'].clicked.connect(self.clearPointCloud)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['clear_button'])
        widgetno += 1

        pc['subvolumes_check'] = QCheckBox(self.graphParamsGroupBox)
        pc['subvolumes_check'].setText("Display Subvolume Regions")
        pc['subvolumes_check'].setChecked(False)
        pc['subvolumes_check'].stateChanged.connect( partial(self.showHideActor,actor_name='subvol_actor') )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['subvolumes_check'])
        widgetno += 1

        pc['reg_box_check'] = QCheckBox(self.graphParamsGroupBox)
        pc['reg_box_check'].setText("Display Registration Region")
        pc['reg_box_check'].setChecked(True)
        pc['reg_box_check'].stateChanged.connect( partial(self.showHideActor,actor_name='registration_box_actor') )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['reg_box_check'])
        widgetno += 1

        #Pointcloud points label
        pc['pc_points_label'] = QLabel("Points in current pointcloud:")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, pc['pc_points_label'])
        pc['pc_points_value'] = QLabel("0")

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['pc_points_value'])

    def _generatePointCloudClicked(self):
        self.pointcloud_is = 'generated'
        self.createSavePointCloudWindow(save_only=False)

    def displaySubvolumePreview(self):
        if self.pointcloud_parameters['subvolume_preview_check'].isChecked():
            #add actor to 2D viewer that previews size and shape of subvolume region
            if self.isoValueEntry.text() == '' or self.rotateXValueEntry.text() ==''\
                or self.rotateYValueEntry.text() =='' or self.rotateZValueEntry.text() =='':
                return
            subvol_size = int(self.isoValueEntry.text())
            shapes = [cilRegularPointCloudToPolyData.CUBE, cilRegularPointCloudToPolyData.SPHERE]  
            self.pointCloud_shape =shapes[self.subvolumeShapeValue.currentIndex()]
            rotate = [
                    float(self.rotateXValueEntry.text()),
                    float(self.rotateYValueEntry.text()),
                    float(self.rotateZValueEntry.text())
            ]

            if hasattr(self, 'point0_world_coords'):
                point0 = self.getPoint0WorldCoords()
            else:
                return

            if hasattr(self, 'ref_image_data'):
                if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
                    subvol_source = vtk.vtkCubeSource()
                    subvol_source.SetXLength(subvol_size)
                    subvol_source.SetYLength(subvol_size)
                    subvol_source.SetZLength(subvol_size)
                    subvol_source.SetCenter(point0)
                    subvol_source.Update()
                    transform = vtk.vtkTransform()

                    v = self.vis_widget_2D.frame.viewer
                    orientation = v.getSliceOrientation()
                    spacing = v.img3D.GetSpacing()
                    dimensions = v.img3D.GetDimensions()
                    origin = v.img3D.GetOrigin()

                    #translate to origin, rotate, then translate back

                    translation = [-origin[0]+point0[0],-origin[1]+point0[1], -origin[2]+point0[2]]
                    transform.Translate(translation[0], translation[1], translation[2])
 
                    # rotation angles
                    transform.RotateX(rotate[0])
                    transform.RotateY(rotate[1])
                    transform.RotateZ(rotate[2])

                    transform.Translate(-translation[0], -translation[1], -translation[2])

                    t_filter = vtk.vtkTransformPolyDataFilter()
                    t_filter.SetInputConnection(subvol_source.GetOutputPort())
                    t_filter.SetTransform(transform)
                    t_filter.Update()
                    data_to_clip = t_filter
                else:
                    subvol_source = vtk.vtkSphereSource()
                    subvol_source.SetRadius(subvol_size/2)
                    subvol_source.SetThetaResolution(12)
                    subvol_source.SetPhiResolution(12)
                    subvol_source.SetCenter(point0)
                    subvol_source.Update()
                    data_to_clip = subvol_source

                data_to_clip.Update()

                viewer_widgets = [self.vis_widget_2D, self.vis_widget_3D]

                for viewer_widget in viewer_widgets:
                    subvol_preview_mapper = vtk.vtkPolyDataMapper()
                    if viewer_widget.viewer == viewer2D:
                        viewer_widget.PlaneClipper.AddDataToClip('subvol_preview_actor', data_to_clip.GetOutputPort())
                        subvol_preview_mapper.SetInputConnection(viewer_widget.PlaneClipper.GetClippedData('subvol_preview_actor').GetOutputPort())
                        if not 'subvol_preview_actor' in viewer_widget.frame.viewer.actors:
                            subvol_actor = vtk.vtkLODActor()
                        else:
                            subvol_actor = self.vis_widget_2D.frame.viewer.actors['subvol_preview_actor']

                    else:
                        subvol_preview_mapper.SetInputConnection(data_to_clip.GetOutputPort())
                        if not hasattr(self, 'actors_3D'):
                            self.actors_3D = {}
                        if not 'subvol_preview_actor' in self.actors_3D:
                            subvol_actor = vtk.vtkLODActor()
                        else:
                            subvol_actor = self.actors_3D['subvol_preview_actor']

                    subvol_preview_mapper.Update()

                    subvol_actor.SetMapper(subvol_preview_mapper)   
                    subvol_actor.VisibilityOn()
                    subvol_actor.GetProperty().SetColor(0.,0,0)
                    subvol_actor.GetProperty().SetLineWidth(2.0)
                    subvol_actor.GetProperty().SetEdgeColor(0.,0,0)
                    subvol_actor.GetProperty().SetRepresentationToWireframe()

                    if viewer_widget.viewer == viewer2D:
                        subvol_actor.GetProperty().SetOpacity(0.5)
                        subvol_actor.GetProperty().SetLineWidth(4.0)
                        subvol_actor.GetProperty().SetEdgeVisibility(True)
                        subvol_actor.GetProperty().SetEdgeColor(0, 0, 0)
                        subvol_actor.GetProperty().SetRenderLinesAsTubes(True)
                        if not 'subvol_preview_actor' in viewer_widget.frame.viewer.actors:
                            viewer_widget.frame.viewer.AddActor(subvol_actor, 'subvol_preview_actor')
                    else:
                        subvol_actor.GetProperty().SetColor(0, 0, 0)
                        subvol_actor.GetProperty().SetOpacity(1)
                        subvol_actor.GetProperty().SetLineWidth(3.0)
                        if not 'subvol_preview_actor' in self.actors_3D:
                            viewer_widget.frame.viewer.getRenderer().AddActor(subvol_actor)
                        self.actors_3D ['subvol_preview_actor'] = subvol_actor
                    viewer_widget.frame.viewer.style.UpdatePipeline()
                # print("Added preview")  

    def updatePointCloudPanel(self):
        #updates which settings can be changed when orientation/dimensions of image changed
        orientation = self.vis_widget_2D.frame.viewer.getSliceOrientation()
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
        """Opens a dialog to select the pointcloud from a file. 
        Runs the creation or loading of the point cloud in a worker.
        Sets the attribut `self.pointcloud_is` to 'loaded'."""
        dialogue = QFileDialog()
        self.roi = None
        self.roi = dialogue.getOpenFileName(self,"Select a roi")[0]
        if self.roi:
            self.PointCloudWorker("load pointcloud file")

        if self.copy_files:
            filename = os.path.basename(self.roi)
            shutil.copyfile(self.roi, os.path.join(tempfile.tempdir, filename))
            self.roi = os.path.abspath(os.path.join(tempfile.tempdir, filename))
            self.pointcloud_parameters['pointcloudList'].addItem(filename)
            self.pointcloud_parameters['pointcloudList'].setCurrentText(filename)
        
        if self.roi is not None:
            self.pointcloud_is = 'loaded'

    def PointCloudWorker(self, type, filename = None, disp_file = None, vector_dim = None):
        """Runs the worker to create or load the point cloud.
        If the format of the point-cloud file is not in the allowed list it displays an error dialog."""
        if type == "create":
            #if not self.pointCloudCreated:
            self.clearPointCloud()
            self.pointcloud_worker = Worker(self.createPointCloud, filename = "latest_pointcloud.roi")
            self.pointcloud_worker.signals.result.connect(self.DisplayPointCloud)
        elif type == "load selection":
            self.clearPointCloud()
            self.pointcloud_worker = Worker(self.loadPointCloud, os.path.join(tempfile.tempdir, self.pointcloud_parameters['pointcloudList'].currentText()))
            self.pointcloud_worker.signals.result.connect(self.DisplayLoadedPointCloud)
        elif type == "load pointcloud file":
            self.clearPointCloud()
            if self.roi.endswith(allowed_point_cloud_file_formats):
                self.pointcloud_worker = Worker(self.loadPointCloud, self.roi)
                self.pointcloud_worker.signals.result.connect(self.DisplayLoadedPointCloud)
            else:
                error_title = "FILE FORMAT ERROR"
                error_text = f"Error reading the point-cloud file {self.roi}. Allowed formats are {allowed_point_cloud_file_formats}."
                self.displayFileErrorDialog(message=error_text, title=error_title)
                return
                
        elif type == "create without loading":
            #if not self.pointCloudCreated:
            self.clearPointCloud()
            self.pointcloud_worker = Worker(self.createPointCloud, filename=filename)
            self.pointcloud_worker.signals.finished.connect(self.progress_complete)
            
        ff = partial(displayErrorDialogFromWorker, self)
        self.pointcloud_worker.signals.error.connect(ff)
        self.pointcloud_worker.signals.message.connect(self.updateProgressDialogMessage)
        self.create_progress_window("Loading", "Loading Pointcloud")
        self.pointcloud_worker.signals.progress.connect(self.progress)
        self.progress_window.setValue(10)
        os.chdir(tempfile.tempdir)
        self.threadpool.start(self.pointcloud_worker)

        # Show error and allow re-selection of pointcloud if it can't be loaded:
        search_button = QPushButton('Select Pointcloud')
        search_button.clicked.connect(self.reselect_pointcloud)

    def reselect_pointcloud(self):
        self.progress_complete()
        self.select_pointcloud()
        self.threadpool.start(self.pointcloud_worker)

    def progress_complete(self):
        try:
            self.progress_window.setValue(100)
        except NameError as ne:
            self.warningDialog(window_title="Warning", message="Error updating progress window progress: {message}".format(message=ne))
    
    def updateProgressDialogMessage(self, message):
        try:
            self.progress_window.setLabelText(message)
        except NameError as ne:
            self.warningDialog(window_title="Warning", message="Error updating progress window message: {message}".format(message=ne))

    def createSavePointCloudWindow(self, save_only):
        #print("Create save pointcloud window -----------------------------------------------------------------------------------")
        if not self.mask_reader:
                self.warningDialog(window_title="Error", 
                               message="Load a mask on the viewer first" )
                return
        elif not hasattr(self, 'point0_world_coords'):
            self.warningDialog(window_title="Error", 
                               message="Select a point 0 in image registration first." )
            return

        else:
            if(self.pointCloudCreated or self.pointCloudLoaded): 
                # print("pointcloud created")
                self.SavePointCloudWindow = SaveObjectWindow(self, "pointcloud", save_only)
                self.SavePointCloudWindow.show()
            else:
                self.PointCloudWorker("create")

    def createPointCloud(self, **kwargs):
        ## Create the PointCloud
        #print("Create point cloud")
        filename = kwargs.get('filename', "latest_pointcloud.roi")
        progress_callback = kwargs.get('progress_callback', PrintCallback())
        message_callback = kwargs.get('message_callback', PrintCallback())

        subvol_size = kwargs.get('subvol_size',None)
        # Mask is read from temp file
        tmpdir = tempfile.gettempdir() 
        reader = vtk.vtkMetaImageReader()
        reader.AddObserver("ErrorEvent", self.e)
        reader.SetFileName(os.path.join(tmpdir,"Masks","latest_selection.mha"))
        reader.Update()

        origin = reader.GetOutput().GetOrigin()
        spacing = reader.GetOutput().GetSpacing()
        dimensions = reader.GetOutput().GetDimensions()  

        if not self.pointCloudCreated:
            #print("Not created")
            pointCloud = cilRegularPointCloudToPolyData()
            # attach the progress update callback
            pointCloud.AddObserver(vtk.vtkCommand.ProgressEvent, partial(getProgress, progress_callback=progress_callback))
            self.pointCloud = pointCloud
        else:
            pointCloud = self.pointCloud
        # instead of translating the point cloud so that point0 is in the point cloud
        # we add point0 to the point cloud.
        if hasattr(self, 'point0'):
            pointCloud.SetPoint0(self.point0_world_coords)
        v = self.vis_widget_2D.frame.viewer
        orientation = v.getSliceOrientation()
        pointCloud.SetOrientation(orientation)
                    
        shapes = [cilRegularPointCloudToPolyData.CUBE, cilRegularPointCloudToPolyData.SPHERE]  

        dimensionality = [3,2]
        
        pointCloud.SetMode(shapes[self.subvolumeShapeValue.currentIndex()])
        pointCloud.SetDimensionality(
                dimensionality[self.dimensionalityValue.currentIndex()]
                )

        self.pointCloud_shape =  shapes[self.subvolumeShapeValue.currentIndex()]
        
        #slice is read from the viewer
        pointCloud.SetSlice(v.getActiveSlice())
        
        pointCloud.SetInputConnection(0, reader.GetOutputPort())

        if subvol_size is None:
            subvol_size = int(self.isoValueEntry.text())

        if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
            pointCloud.SetSubVolumeRadiusInVoxel(subvol_size) #in cube case, radius is side length
        else:
            pointCloud.SetSubVolumeRadiusInVoxel(subvol_size/2)

        pointCloud.SetOverlap(0,float(self.overlapXValueEntry.text()))
        pointCloud.SetOverlap(1,float(self.overlapYValueEntry.text()))
        pointCloud.SetOverlap(2,float(self.overlapZValueEntry.text()))
        
        message_callback.emit('Creating point cloud')
        pointCloud.Update()
        self.pointCloud_subvol_size = subvol_size
        self.pointCloud_overlap = [float(self.overlapXValueEntry.text()), float(self.overlapYValueEntry.text()), float(self.overlapZValueEntry.text())]
        
        #print ("pointCloud number of points", pointCloud.GetNumberOfPoints())

        if pointCloud.GetNumberOfPoints() == 0:
            self.pointCloudCreated = False
            raise ValueError("No points in pointcloud. Please check your settings and try again.")

        # Erode the transformed mask because we don't want to have subvolumes outside the mask
        if not self.pointCloudCreated:
            erode = vtk.vtkImageDilateErode3D()
            erode.SetErodeValue(1)
            erode.SetDilateValue(0) 
            # save reference
            self.erode = erode
            self.erode_pars = {'selection_mtime':os.path.getmtime(
                    os.path.join(tmpdir, "Masks","latest_selection.mha"))}
        else:
            erode = self.erode

        #Set up erosion if user has selected it:

        if( self.erodeCheck.isChecked()):
            #print ("Erode checked" ,self.erodeCheck.isChecked())
            
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

            # kernel size defines size of the structuring element in the erosion.
            # This needs to be the size of the subvolume diameter but we must add on 0.5 to account for the furthest distance a point may be offset from the centre of a pixel.
            # have to round up to an integer otherwise some of subvolume may be outside of mask if we round down

            erosion_multiplier = self.erodeRatioSpinBox.value()
            if self.pointCloud_shape == 'cube':
                ks = [math.ceil(l*erosion_multiplier + 0.5 ) for l in ks] # "radius" is side length of cube
                
            else:
                ks = [math.ceil(2*l*erosion_multiplier+ 0.5) for l in ks] 

            #print("KS", ks)
            
            # the mask erosion takes a looong time. Try not do it all the 
            # time if neither mask nor other values have changed
            if not self.eroded_mask:
                self.erode_pars['ks'] =  ks[:]        
                run_erode = True
            else:
                run_erode = False
                # test if mask is different from last one by checking the modification
                # time
                mtime = os.path.getmtime(os.path.join(tmpdir, "Masks","latest_selection.mha"))
                if mtime != self.erode_pars['selection_mtime']:
                    #print("mask has changed")
                    run_erode = True
                if ks != self.erode_pars['ks']:
                    run_erode = True
                    #print("subvolume size has changed")
                    self.erode_pars['ks'] = ks[:]
                                
            if run_erode:
                erode.SetInputConnection(0,reader.GetOutputPort())
                erode.SetKernelSize(ks[0],ks[1],ks[2])
                erode.Update()

            self.eroded_mask = True
        else:
            self.eroded_mask = False
        
        
        # Mask the point cloud with the eroded mask
        if not self.pointCloudCreated:
            polydata_masker = cilMaskPolyData()
            polydata_masker.AddObserver(vtk.vtkCommand.ProgressEvent, partial(getProgress, progress_callback=progress_callback))
            # save reference
            self.polydata_masker = polydata_masker
        else:
            polydata_masker = self.polydata_masker
        polydata_masker.SetMaskValue(1)
        if self.erodeCheck.isChecked():
            polydata_masker.SetInputConnection(1, erode.GetOutputPort())
            mask_data = erode.GetOutput()
        else:
            polydata_masker.SetInputConnection(1, reader.GetOutputPort())
            mask_data = reader.GetOutput()
        
        ## Create a Transform to modify the PointCloud
        # Translation and Rotation
        rotate = [
                float(self.rotateXValueEntry.text()),
                float(self.rotateYValueEntry.text()),
                float(self.rotateZValueEntry.text())
        ]
        self.pointCloud_rotation = rotate

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

        # rotation angles
        transform.RotateX(rotate[0])
        transform.RotateY(rotate[1])
        transform.RotateZ(rotate[2])

        if orientation == SLICE_ORIENTATION_XY:
            transform.Translate(-dimensions[0]/2*spacing[0], -dimensions[1]/2*spacing[1],0)
        elif orientation == SLICE_ORIENTATION_XZ:
            transform.Translate(-dimensions[0]/2*spacing[0], 0,-dimensions[2]/2*spacing[2])
        elif orientation == SLICE_ORIENTATION_YZ:
            transform.Translate(0, -dimensions[1]/2*spacing[1],-dimensions[2]/2*spacing[2])

        mm = mask_data.GetScalarComponentAsDouble(int(self.point0_sampled_image_coords[0]),int(self.point0_sampled_image_coords[1]), int(self.point0_sampled_image_coords[2]), 0)

        if int(mm) == 1: 
            #if point0 is in the mask and it has been added as first point to the point cloud
            remove_point0 = False
        else:
            # should remove point0 from the mask
            remove_point0 = True

        if self.pointCloudCreated:
            t_filter = self.t_filter
        else:
            # Actual Transformation is done here
            t_filter = vtk.vtkTransformFilter()
            # save reference
            self.t_filter = t_filter
        
        t_filter.SetTransform(transform)
        t_filter.SetInputConnection(pointCloud.GetOutputPort())

        #print("Number of points after transform", t_filter.GetOutputPort().GetNumberOfPoints() )
        
        polydata_masker.SetInputConnection(0, t_filter.GetOutputPort())
        # polydata_masker.Modified()
        message_callback.emit('Applying mask to pointcloud')
        polydata_masker.Update()
        message_callback.emit('Applying mask to pointcloud. Done')
        #print("Points in mask now: ", polydata_masker)
        
        self.reader = reader
        
        pointcloud = self.polydata_masker.GetOutputDataObject(0)
        array = []
        self.pc_no_points = pointcloud.GetNumberOfPoints()
        if(pointcloud.GetNumberOfPoints() == 0):
            raise ValueError('No points in pointcloud')
            
        
        if int(mm) == 1: #if point0 is in the mask
            count = 2
        else:
            count = 1

        for i in range(pointcloud.GetNumberOfPoints()):
            pp = pointcloud.GetPoint(i)
            distance = (pp[0]-self.point0_world_coords[0])**2 + (pp[1]-self.point0_world_coords[1])**2 + (pp[2]-self.point0_world_coords[2])**2
            if distance < 0.001:
                #print("Distance is 0 for:", pp)
                #print("Add to front of list")
                array.insert(0,(1,*pp))
            else:
                array.append((count, *pp))
                count += 1

        message_callback.emit('Saving pointcloud')
        start = 0 if remove_point0 is False else 1
        np.savetxt(tempfile.tempdir + "/" + filename, array[start:], '%d\t%.3f\t%.3f\t%.3f', delimiter=';')
        self.roi = filename

        return True

    def loadPointCloud(self, *args, **kwargs):
        """Loads a pointcloud from file. 
        Handles BOM in csv file.
        File formats allowed are 'roi', 'txt', 'csv', 'xlxs' and 'inp'. 
        Stores the pointcloud in a temporary txt file, whose path is stored in 'self.roi'.
        """
        time.sleep(0.1) #required so that progress window displays
        pointcloud_file = os.path.abspath(args[0])
        progress_callback = kwargs.get('progress_callback', None)
        progress_callback.emit(20)
        #self.clearPointCloud() #need to clear current pointcloud before we load next one TODO: move outside thread
        progress_callback.emit(30)
        
        if pointcloud_file.endswith('.txt') or pointcloud_file.endswith('.roi'):
            points = np.loadtxt(pointcloud_file)
        elif pointcloud_file.endswith('.csv'):
            with tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix='.csv', newline='', encoding='utf-8') as temp_file:
                with open(pointcloud_file, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                temp_file.writelines(lines)
                temp_file_path = temp_file.name
            points = np.genfromtxt(temp_file_path, delimiter=',', dtype=float)
            os.remove(temp_file_path)
        elif pointcloud_file.endswith('.xlsx'):
            workbook = load_workbook(pointcloud_file, read_only=True)
            sheet = workbook.active
            points = np.array(list(sheet.values))
        elif pointcloud_file.endswith('.inp'):
            points =  extract_point_cloud_from_inp_file(args[0])
        filename = os.path.basename(pointcloud_file)
        path = os.path.abspath(os.path.join(tempfile.tempdir, filename))
        np.savetxt(path, points,fmt=('%d','%f','%f','%f'))
        self.roi = path

        # except ValueError as ve:
        #     print(ve)
        #     return

        self.pc_no_points = np.shape(points)[0]
        progress_callback.emit(50)
        self.polydata_masker = cilNumpyPointCloudToPolyData()
        self.polydata_masker.SetData(points)
        self.polydata_masker.Update()
        progress_callback.emit(80)

        pointcloud_file = os.path.basename(pointcloud_file)


        if pointcloud_file in self.pointCloud_details:
            self.pointCloud_subvol_size = self.pointCloud_details[pointcloud_file][0]
            self.pointCloud_overlap = self.pointCloud_details[pointcloud_file][1]
            self.pointCloud_rotation = self.pointCloud_details[pointcloud_file][2]
            self.pointCloud_shape = self.pointCloud_details[pointcloud_file][3]
            #print("Set properties")
        else:
            # should read the subvolume size and shape from the interface
            # the other info has no meaning.
            self.pointCloud_subvol_size = int(self.isoValueEntry.text())
            # print ("load pointcloud from external ", self.subvolumeShapeValue.currentIndex())
            if int(self.subvolumeShapeValue.currentIndex()) == 0:
                self.pointCloud_shape = cilRegularPointCloudToPolyData.CUBE
            elif int(self.subvolumeShapeValue.currentIndex()) == 1:
                self.pointCloud_shape = cilRegularPointCloudToPolyData.SPHERE

            self.pointCloud_overlap = [0.00,0.00,0.00]
            self.pointCloud_rotation = [0.00,0.00,0.00]
            
            #print("No details found")

        #SET UP APPROPRIATE VALUES OF SPINBOXES ON INTERFACE: #TODO
        # self.overlapXValueEntry.setValue(float(self.pointCloud_overlap[0]))
        # self.overlapYValueEntry.setValue(float(self.pointCloud_overlap[1]))
        # self.overlapZValueEntry.setValue(float(self.pointCloud_overlap[2]))
        # print("Set xyz")
        # print(self.pointCloud_subvol_size)
        # print(str(self.pointCloud_subvol_size))
        # self.isoValueEntry.setText(str(self.pointCloud_subvol_size))
        # print(str("{:.2f}".format(self.pointCloud_rotation[0])))
        # self.rotateXValueEntry.setText(str("{:.2f}".format(self.pointCloud_rotation[0])))
        # self.rotateYValueEntry.setText(str("{:.2f}".format(self.pointCloud_rotation[1])))
        # self.rotateZValueEntry.setText(str("{:.2f}".format(self.pointCloud_rotation[2])))
        # print("Set the values")


    

    def DisplayNumberOfPointcloudPoints(self):
        "Updates the number of points in the widgets."
        self.pointcloud_parameters['pc_points_value'].setText(str(self.pc_no_points))
        self.rdvc_widgets['run_points_spinbox'].setMaximum(int(self.pc_no_points))
        if hasattr(self, 'num_processed_points'):
            self.result_widgets['pc_points_value'].setText(str(self.num_processed_points))

    def DisplayLoadedPointCloud(self):
        self.setup2DPointCloudPipeline()
        self.setup3DPointCloudPipeline()
        # hide actor if user does not request to see it. Off by default
        self.showHideActor(self.pointcloud_parameters['subvolumes_check'].isChecked(), actor_name='subvol_actor')
        
        #Update window so pointcloud is instantly visible without user having to interact with viewer first
        self.vis_widget_2D.frame.viewer.getRenderWindow().Render()
        self.vis_widget_3D.frame.viewer.getRenderWindow().Render()
        #print(self.loading_session)
        self.progress_window.setValue(100)
        if not self.loading_session:
            self.warningDialog(window_title="Success", message="Point cloud loaded.")
        self.loading_session = False 
        self.pointCloudLoaded = True
        self.pointCloud_details["latest_pointcloud.roi"] = [self.pointCloud_subvol_size, self.pointCloud_overlap, self.pointCloud_rotation, self.pointCloud_shape]
        self.DisplayNumberOfPointcloudPoints()
        self.pointcloud_is = 'loaded'
        
    def DisplayPointCloud(self):
        self.pointcloud_parameters['subvolume_preview_check'].setChecked(False)
        if self.pointCloud.GetNumberOfPoints() == 0:
            self.progress_window.setValue(100) 
            self.warningDialog(window_title="Error", 
                    message="Failed to create point cloud.",
                    detailed_text='A pointcloud could not be created because there were no points in the selected region. \
Try modifying the subvolume size before creating a new pointcloud, and make sure it is smaller than the extent of the mask.' )
            self.pointCloudCreated = False
            self.eroded_mask = False
            self.pointCloudLoaded = False
            return
        #print("display pointcloud")
        
        v = self.vis_widget_2D.frame.viewer
        if not self.pointCloudCreated:
            # visualise polydata
            self.setup2DPointCloudPipeline()
            if not hasattr(self, 'reader'):
                #TODO: fix this line - we don't have a reader
                tmpdir = tempfile.gettempdir()
                reader = vtk.vtkMetaImageReader()
                reader.AddObserver("ErrorEvent", self.e)
                reader.SetFileName(os.path.join(tmpdir,"Masks","latest_selection.mha"))
                reader.Update()
            v.setInputData2(self.reader.GetOutput()) 
            self.setup3DPointCloudPipeline()
            self.pointCloudCreated = True
            self.pointCloudLoaded = True

        else:
            spacing = v.img3D.GetSpacing()
            subvol_size = self.pointCloud_subvol_size
            rotate = self.pointCloud_rotation

            if self.pointCloud_shape == cilRegularPointCloudToPolyData.CUBE:
            #cube
                #self.glyph_source = self.cube_source
                self.cube_source.SetXLength(subvol_size)
                self.cube_source.SetYLength(subvol_size)
                self.cube_source.SetZLength(subvol_size)
                self.cube_source.Update()
                self.transform.RotateX(rotate[0])
                self.transform.RotateY(rotate[1])
                self.transform.RotateZ(rotate[2])  
                self.cube_transform_filter.Update()
                self.cubesphere.SetSourceConnection(self.cube_transform_filter.GetOutputPort())
            else:
                #self.glyph_source = self.sphere_source
                self.sphere_source.SetRadius(subvol_size/2)
                self.cubesphere.SetSourceConnection(self.sphere_source.GetOutputPort())
            
            self.cubesphere.Update()
        

        #Update window so pointcloud is instantly visible without user having to interact with viewer first
        self.vis_widget_2D.frame.viewer.getRenderWindow().Render()
        self.vis_widget_3D.frame.viewer.getRenderWindow().Render()

        #print(self.pointCloudCreated)

        self.progress_window.setValue(100)

        # hide actor if user does not request to see it. Off by default
        self.showHideActor(self.pointcloud_parameters['subvolumes_check'].isChecked(), actor_name='subvol_actor')
        
        self.warningDialog(window_title="Success", message="Point cloud created." )
        self.pointCloud_details["latest_pointcloud.roi"] = [self.pointCloud_subvol_size, self.pointCloud_overlap, self.pointCloud_rotation, self.pointCloud_shape]
        self.DisplayNumberOfPointcloudPoints()

    def clearPointCloud(self):
        self.clearPointCloud2D()
        self.clearPointCloud3D()
        self.pointcloud_parameters['pc_points_value'].setText("0")

    def clearPointCloud2D(self):
        actor_names = ['pc_actor', 'subvol_actor', 'arrow_pc_actor', 'arrowhead_actor', 'arrow_shaft_actor']
        v2D = self.vis_widget_2D.frame.viewer

        for actor_name in actor_names:
            if v2D.GetActor(actor_name):
               v2D.GetActor(actor_name).VisibilityOff() 
        
            if hasattr(self.vis_widget_2D, 'PlaneClipper'):
                self.vis_widget_2D.PlaneClipper.RemoveDataToClip(actor_name)

            v2D.getRenderWindow().Render()

        self.pointCloudLoaded = False
        self.pointCloudCreated = False
        self.eroded_mask = False

    def clearPointCloud3D(self):
        if hasattr(self, 'actors_3D'):
            actor_names = ['pc_actor', 'subvol_actor', 'arrow_pc_actor', 'arrows_actor']
            for actor_name in actor_names:
                if actor_name in self.actors_3D:
                    self.actors_3D[actor_name].VisibilityOff()

        v3D = self.vis_widget_3D.frame.viewer

        v3D.getRenderWindow().Render()

    def showHideActor(self, show, actor_name):
        v2D = self.vis_widget_2D.frame.viewer
        if hasattr(v2D, 'img3D'):
            if v2D.GetActor(actor_name):
                if show:
                    v2D.GetActor(actor_name).VisibilityOn()
                else:
                    v2D.GetActor(actor_name).VisibilityOff()

            if hasattr(self, 'actors_3D'):
                if actor_name in self.actors_3D:
                    if show:
                        self.actors_3D [actor_name].VisibilityOn()
                    else:
                        self.actors_3D [actor_name].VisibilityOff()

            self.vis_widget_2D.frame.viewer.ren.Render()
            self.vis_widget_3D.frame.viewer.getRenderWindow().Render()
            if hasattr(self.vis_widget_2D, 'PlaneClipper'):
                self.vis_widget_2D.PlaneClipper.UpdateClippingPlanes()

    def displayVectors(self,disp_file):
        self.clearPointCloud()
        self.pointcloud_parameters['subvolume_preview_check'].setChecked(False)
        self.disp_file = disp_file
        
        displ = self.loadDisplacementFile(disp_file, disp_wrt_point0 = self.result_widgets['vec_entry'].currentIndex() == 2, \
                                                     multiplier = self.result_widgets['scale_vectors_entry'].value())

        self.num_processed_points = np.shape(displ)[0]
        self.DisplayNumberOfPointcloudPoints()

        logging.info('Adding vectors 2D')
        self.createVectors2D(displ, self.vis_widget_2D)
        logging.info('Adding vectors 3D')
        self.createVectors3D(displ, self.vis_widget_3D, self.actors_3D)

        # add color bar in 2D/3D viewer
        logging.info('Adding color bar 2D')
        self._addColorBar(self.vis_widget_2D)
        logging.info('Adding color bar 3D')
        self._addColorBar(self.vis_widget_3D)

        # trigger a drawing
        self.vis_widget_2D.frame.viewer.renWin.Render()
        self.vis_widget_3D.frame.viewer.renWin.Render()
        
    def _removeColormap(self):
        '''remove vectors and colormap'''
        if hasattr(self, 'scalar_bar_2D'):
            self.vis_widget_2D.frame.viewer.removeActor('scalar_bar')

        if hasattr(self, 'scalar_bar_3D'):
            self.vis_widget_3D.frame.viewer.getRenderer().RemoveActor(self.scalar_bar_3D)
    
    def _setUIWithDisplacementVectorFullRange(self):
    
        self.result_widgets['range_vectors_max_entry'].setEnabled(True)
        self.result_widgets['range_vectors_min_entry'].setEnabled(True)
        dmin = self.result_widgets['range_vectors_max_entry'].minimum()
        dmax = self.result_widgets['range_vectors_max_entry'].maximum()
        self.result_widgets['range_vectors_max_entry'].setValue(dmax)
        self.result_widgets['range_vectors_min_entry'].setValue(dmin)
    
    def _updateUIwithDisplacementVectorRange(self, dmin, dmax):
        single_step = 1e-6

        self.result_widgets['range_vectors_max_entry'].setSingleStep(single_step)
        self.result_widgets['range_vectors_max_entry'].setMaximum(dmax)
        self.result_widgets['range_vectors_max_entry'].setMinimum(dmin)
        self.result_widgets['range_vectors_max_entry'].setValue(dmax)
        self.result_widgets['range_vectors_max_entry'].setEnabled(True)

        self.result_widgets['range_vectors_min_entry'].setSingleStep(single_step)
        self.result_widgets['range_vectors_min_entry'].setMaximum(dmax)
        self.result_widgets['range_vectors_min_entry'].setMinimum(dmin)
        self.result_widgets['range_vectors_min_entry'].setValue(dmin)
        self.result_widgets['range_vectors_min_entry'].setEnabled(True)
        self.result_widgets['range_vectors_all_entry'].setEnabled(True)
        
    def loadDisplacementFile(self, displ_file, disp_wrt_point0 = False, multiplier = 1):
        """Loads the point cloud from file. If the min is enabled it resamples the vectors to the range selected by the user,
        else, it extracts the range of the vectors magnitude and updates the min and max widgets.
        If the multiplier is not 1 it rescales the vectors.
        The method is invoked when the widget 'View' is set to 'total displacement' or 'displacement with respect to point 0'"""
        
        raw_displ = np.asarray(
            PointCloudConverter.loadPointCloudFromCSV(displ_file,'\t')[:]
        )

        if self.result_widgets['range_vectors_min_entry'].isEnabled():
            min_size = self.result_widgets['range_vectors_min_entry'].value() 
            max_size = self.result_widgets['range_vectors_max_entry'].value()
            displ, dmin, dmax = reduce_displ(raw_displ, min_size, max_size, disp_wrt_point0)
        else:
            min_size = None
            max_size = None
            displ, dmin, dmax = reduce_displ(raw_displ, min_size, max_size, disp_wrt_point0)
            self._updateUIwithDisplacementVectorRange(dmin, dmax)
                
        displ = np.asarray(displ)

        if multiplier != 1:
            for count in range(len(displ)):
                for i in range(3):
                    displ[count][i+6] *= multiplier

        return displ

    def _addColorBar(self, viewer_widget):
        # get lookup table
        lut2D = self.vectors_lut2D
        lut3D = self.vectors_lut3D

        # create the scalar_bar
        scalar_bar = vtk.vtkScalarBarActor()
        # scalar_bar.SetOrientationToHorizontal()
        scalar_bar.SetOrientationToVertical()
        scalar_bar.SetTitle('Displacement (pixels)')
        
        viewer = viewer_widget.frame.viewer
        # print("CREATE VECTORS", viewer.GetSliceOrientation())
        if isinstance(viewer, viewer2D):
            scalar_bar.SetLookupTable(lut2D)
            if hasattr(self, 'scalar_bar_2D'):
                viewer.removeActor('scalar_bar')
            self.scalar_bar_2D = scalar_bar
            viewer.AddActor(scalar_bar, 'scalar_bar')
        elif isinstance(viewer, viewer3D):
            scalar_bar.SetLookupTable(lut3D)
            if hasattr(self, 'scalar_bar_3D'):
                viewer.getRenderer().RemoveActor(self.scalar_bar_3D)
            self.scalar_bar_3D = scalar_bar
            viewer.addActor(scalar_bar)
        else:
            logging.warning('Wrong viewer type {}'.format(type(viewer)))

    def createVectors2D(self, displ, viewer_widget):
        '''Creates displacement vectors in 2D
        
        Uses the "vector scaling" multiplier from the UI to scale the vectors whilst keeping the value range in the color bar fixed.
        '''
        viewer = viewer_widget.frame.viewer
        # print("CREATE VECTORS", viewer.GetSliceOrientation())
        if isinstance(viewer, viewer2D):
            grid = vtk.vtkUnstructuredGrid()

            arrow_start_vertices = vtk.vtkCellArray()    
            arrow_shaft_centres = vtk.vtkCellArray()
            arrowhead_centres = vtk.vtkCellArray()

            arrow_vectors = vtk.vtkDoubleArray()
            arrow_vectors.SetNumberOfComponents(3)
        
            arrow_shaft_vectors = vtk.vtkDoubleArray()
            arrow_shaft_vectors.SetNumberOfComponents(3)

            arrowhead_vectors = vtk.vtkDoubleArray()
            arrowhead_vectors.SetNumberOfComponents(3)

            pc = vtk.vtkPoints()
            arrow_shaft_centres_pc = vtk.vtkPoints()
            arrowhead_centres_pc = vtk.vtkPoints()
            
            acolor = vtk.vtkDoubleArray()

            orientation = viewer.getSliceOrientation()

            # the vectors are scaled with multiplier
            multiplier = float(self.result_widgets['scale_vectors_entry'].value())
            for count in range(len(displ)):
                p = pc.InsertNextPoint(displ[count][1],displ[count][2], displ[count][3]) #xyz coords of pc
                arrow_start_vertices.InsertNextCell(1) # Create cells by specifying a count of total points to be inserted
                arrow_start_vertices.InsertCellPoint(p)

                arrow_vector = [0,0,0]
                arrow_shaft_centre = [displ[count][1],displ[count][2], displ[count][3]]
                arrow_shaft_vector = [0,0,0]
                arrowhead_centre = [displ[count][1],displ[count][2], displ[count][3]]
                arrowhead_vector = [0,0,0]

                for i, value in enumerate(arrow_shaft_centre):
                    if i != orientation:
                        arrow_vector[i] = displ[count][i+6] 
                        # Vector for arrowhead - determines height of triangle that forms arrowhead
                        arrowhead_vector[i] = (displ[count][i+6] * 0.3)
                         # Vector for arrow shaft - determines length of arrow shaft
                        arrow_shaft_vector[i] = displ[count][i+6] * 0.8
                        arrow_shaft_centre[i] = arrow_shaft_centre[i] + (displ[count][i+6]) * 0.4
                        arrowhead_centre[i] = arrow_shaft_centre[i] + (displ[count][i+6])*0.3 + displ[count][i+6]*0.15

                p = arrow_shaft_centres_pc.InsertNextPoint(arrow_shaft_centre[0], arrow_shaft_centre[1], arrow_shaft_centre[2])
                arrow_shaft_centres.InsertNextCell(1) 
                arrow_shaft_centres.InsertCellPoint(p)

                arrow_vectors.InsertNextTuple3(arrow_vector[0], arrow_vector[1], arrow_vector[2]) 
                arrow_shaft_vectors.InsertNextTuple3(arrow_shaft_vector[0], arrow_shaft_vector[1], arrow_shaft_vector[2])
                arrowhead_vectors.InsertNextTuple3(arrowhead_vector[0], arrowhead_vector[1], arrowhead_vector[2])        

                p = arrowhead_centres_pc.InsertNextPoint(arrowhead_centre[0], arrowhead_centre[1], arrowhead_centre[2])
                arrowhead_centres.InsertNextCell(1)
                arrowhead_centres.InsertCellPoint(p)


                arrow_vector.pop(orientation)

                # print("Arrow start loc: ", [displ[count][1],displ[count][2],displ[count][3]])
                # print("Arrow end loc: ", [displ[count][1] + displ[count][6],displ[count][2]+ displ[count][7],displ[count][3]+ displ[count][8]])
                # print("Arrow shaft centre: ", [arrow_shaft_centre[0], arrow_shaft_centre[1], arrow_shaft_centre[2]])
                # print("Arrow head loc: ", [arrowhead_centre[0], arrowhead_centre[1], arrowhead_centre[2]])
                # print("Arrow head size: ", arrowhead_vector) 
                #print(count, reduce(lambda x,y: x + y**2, (*new_points,0), 0))
                
                
                acolor.InsertNextValue(np.sqrt(
                    reduce(lambda x,y: x + y**2, (*arrow_vector,0), 0) 
                    ) / multiplier
                )#inserts u^2 + v^2 + w^2
                
            lut = self._createLookupTable()

            pointPolyData = vtk.vtkPolyData()
            pointPolyData.SetPoints( pc ) # (x,y,z)
            pointPolyData.SetVerts( arrow_start_vertices ) # (x,y,z)
            pointPolyData.GetPointData().SetVectors(arrow_vectors) #(u,v,w) vector in 2D
            pointPolyData.GetPointData().SetScalars(acolor)

            viewer_widget.PlaneClipper.AddDataToClip('arrow_pc_actor', pointPolyData)

            pmapper = vtk.vtkPolyDataMapper()
            pmapper.SetInputData(pointPolyData)
            pmapper.SetInputConnection(viewer_widget.PlaneClipper.GetClippedData('arrow_pc_actor').GetOutputPort())
            pmapper.SetScalarRange(acolor.GetRange())
            pmapper.SetLookupTable(lut)

            point_actor = vtk.vtkActor()
            point_actor.SetMapper(pmapper)
            point_actor.GetProperty().SetPointSize(5)
            point_actor.GetProperty().SetColor(1,0,1)

            linesPolyData = vtk.vtkPolyData()
            linesPolyData.SetPoints( arrow_shaft_centres_pc ) 
            linesPolyData.SetVerts( arrow_shaft_centres ) 
            linesPolyData.GetPointData().SetVectors(arrow_shaft_vectors) 
            linesPolyData.GetPointData().SetScalars(acolor)

            line_source = vtk.vtkLineSource()

            line_glyph = vtk.vtkGlyph3D()
            line_glyph.SetInputData(linesPolyData)
            line_glyph.SetSourceConnection(line_source.GetOutputPort())
            line_glyph.SetScaleModeToScaleByVector()
            line_glyph.SetVectorModeToUseVector()
            line_glyph.ScalingOn()
            line_glyph.OrientOn()
            line_glyph.Update()

            viewer_widget.PlaneClipper.AddDataToClip('arrow_shaft_actor', line_glyph.GetOutputPort())

            line_mapper = vtk.vtkPolyDataMapper()
            line_mapper.SetInputConnection(viewer_widget.PlaneClipper.GetClippedData('arrow_shaft_actor').GetOutputPort())
            line_mapper.SetScalarModeToUsePointFieldData()
            line_mapper.SelectColorArray(0)
            line_mapper.SetScalarRange(acolor.GetRange())
            line_mapper.SetLookupTable(lut)

            line_actor = vtk.vtkActor()
            line_actor.SetMapper(line_mapper)
            line_actor.GetProperty().SetOpacity(0.5)
            line_actor.GetProperty().SetLineWidth(2)

            arrowheadsPolyData = vtk.vtkPolyData()
            arrowheadsPolyData.SetPoints( arrowhead_centres_pc ) 
            arrowheadsPolyData.SetVerts( arrowhead_centres ) # 0.8 * (u,v,w) vector in 2D
            arrowheadsPolyData.GetPointData().SetVectors(arrowhead_vectors) #(u,v,w) vector in 2D
            arrowheadsPolyData.GetPointData().SetScalars(acolor) 

            arrowhead_source = vtk.vtkRegularPolygonSource()
            arrowhead_source.SetNumberOfSides(3)

            transform = vtk.vtkTransform()
            transform.RotateZ(270)
            if orientation == 0:
                #transform.RotateX(90)
                transform.RotateY(90)
            if orientation == 1:
                transform.RotateY(90) 

            transformF = vtk.vtkTransformPolyDataFilter()
            transformF.SetInputConnection(arrowhead_source.GetOutputPort())
            transformF.SetTransform(transform) 

            arrowhead_glyph = vtk.vtkGlyph3D()
            arrowhead_glyph.SetInputData(arrowheadsPolyData)
            arrowhead_glyph.SetSourceConnection(transformF.GetOutputPort())
            arrowhead_glyph.SetScaleModeToScaleByVector()
            arrowhead_glyph.SetVectorModeToUseVector()
            arrowhead_glyph.ScalingOn()
            arrowhead_glyph.OrientOn()
            arrowhead_glyph.Update()

            viewer_widget.PlaneClipper.AddDataToClip('arrowhead_actor', arrowhead_glyph.GetOutputPort())

            arrowhead_mapper = vtk.vtkPolyDataMapper()
            arrowhead_mapper.SetInputConnection(viewer_widget.PlaneClipper.GetClippedData('arrowhead_actor').GetOutputPort())
            arrowhead_mapper.SetScalarModeToUsePointFieldData()
            arrowhead_mapper.SelectColorArray(0)
            arrowhead_mapper.SetScalarRange(acolor.GetRange())
            arrowhead_mapper.SetLookupTable(lut)

            arrowhead_actor = vtk.vtkActor()
            arrowhead_actor.SetMapper(arrowhead_mapper)
            arrowhead_actor.GetProperty().SetOpacity(0.5)
            arrowhead_actor.GetProperty().SetLineWidth(2.0)
            
            viewer.AddActor(point_actor, 'arrow_pc_actor')
            viewer.AddActor(line_actor, 'arrow_shaft_actor')
            viewer.AddActor(arrowhead_actor, 'arrowhead_actor')

            # For testing, show 2D arrows on 3D viewer too. Best to do this without clipping
            # v = self.vis_widget_3D.frame.viewer
            # v.ren.AddActor(point_actor)
            # v.ren.AddActor(line_actor)
            # v.ren.AddActor(arrowhead_actor)
            self.vectors_lut2D = lut

            viewer.updatePipeline()
            
    def _createLookupTable(self, cmap='magma'):
        lut = vtk.vtkLookupTable()
        
        cmap = CILColorMaps.get_color_map('magma')
        lut.SetNumberOfTableValues(len(cmap))
        for i,el in enumerate(cmap):
            lut.SetTableValue(i, *el, 1)

        lut.Build()
        
        return lut

    def OnKeyPressEventForVectors(self, interactor, event):
        #Vectors have to be recreated on the 2D viewer when switching orientation
        key_code = interactor.GetKeyCode()
        #print("OnKeyPressEventForVectors", key_code)
        if key_code in ['x','y','z'] and \
            interactor._viewer.GetActor('arrow_shaft_actor') and interactor._viewer.GetActor('arrowhead_actor'):
                if interactor._viewer.GetActor('arrow_shaft_actor').GetVisibility() and interactor._viewer.GetActor('arrowhead_actor').GetVisibility():
                    self.clearPointCloud2D()
                    #print("Cleared pc")
                    displ = self.loadDisplacementFile(self.disp_file, disp_wrt_point0 = self.result_widgets['vec_entry'].currentIndex() == 2)
                    self.createVectors2D(displ, self.vis_widget_2D)

    def createVectors3D(self, displ, viewer_widget, actor_list):
        '''Creates displacement vectors in 3D
        
        Uses the "vector scaling" multiplier from the UI to scale the vectors whilst keeping the value range in the color bar fixed.
        '''
        viewer = viewer_widget.frame.viewer
        if isinstance(viewer, viewer3D):
            v = viewer
            arrow = vtk.vtkDoubleArray()
            arrow.SetNumberOfComponents(3)
            acolor = vtk.vtkDoubleArray()
            pc = vtk.vtkPoints()
            vertices = vtk.vtkCellArray()

            for count in range(len(displ)):
                p = pc.InsertNextPoint(displ[count][1],
                                displ[count][2], 
                                displ[count][3]) #xyz coords
                vertices.InsertNextCell(1) # Create cells by specifying a count of total points to be inserted
                vertices.InsertCellPoint(p)
                # these are scaled with multiplier
                multiplier = float(self.result_widgets['scale_vectors_entry'].value())
                arrow.InsertNextTuple3(displ[count][6],displ[count][7],displ[count][8]) #u and v are set for x and y
                # the colors need to remain the quantitative ones, independent on the multiplier
                acolor.InsertNextValue(np.sqrt(displ[count][6]**2+displ[count][7]**2+displ[count][8]**2)/multiplier) #inserts u^2 + v^2
                
            lut = self._createLookupTable()
        
            #2. Add the points to a vtkPolyData.
            pointPolyData = vtk.vtkPolyData()
            pointPolyData.SetPoints( pc ) 
            pointPolyData.SetVerts( vertices ) 
            pointPolyData.GetPointData().SetVectors(arrow) #(u,v,w) vector in 2D
            pointPolyData.GetPointData().SetScalars(acolor) 

            arrow_source = vtk.vtkArrowSource()
            arrow_source.SetTipRadius(0.2)
            arrow_source.SetShaftRadius(0.05)

            # arrow
            arrow_glyph = vtk.vtkGlyph3D()
            arrow_glyph.SetInputData(pointPolyData)
            arrow_glyph.SetSourceConnection(arrow_source.GetOutputPort())
            arrow_glyph.SetScaleModeToScaleByVector()
            arrow_glyph.SetVectorModeToUseVector()
            arrow_glyph.ScalingOn()
            arrow_glyph.OrientOn()

            arrow_mapper = vtk.vtkPolyDataMapper()
            arrow_mapper.SetInputConnection(arrow_glyph.GetOutputPort())
            arrow_mapper.SetScalarModeToUsePointFieldData()
            arrow_mapper.SelectColorArray(0)
            arrow_mapper.SetScalarRange(acolor.GetRange())
            arrow_mapper.SetLookupTable(lut)

            # Usual actor
            arrow_actor = vtk.vtkActor()
            arrow_actor.SetMapper(arrow_mapper)
            arrow_actor.GetProperty().SetOpacity(1)

            pmapper = vtk.vtkPolyDataMapper()
            pmapper.SetInputData(pointPolyData)
            pmapper.SelectColorArray(0)
            pmapper.SetScalarRange(acolor.GetRange())
            pmapper.SetLookupTable(lut)

            pactor = vtk.vtkActor()
            pactor.SetMapper(pmapper)
            pactor.GetProperty().SetPointSize(3)
            
            v.ren.AddActor(pactor)
            v.ren.AddActor(arrow_actor)
            actor_list['arrow_pc_actor'] = pactor
            actor_list['arrows_actor'] = arrow_actor

            self.vectors_lut3D = lut
            
            v.updatePipeline()


#Run DVC  Panel:
    def CreateRunDVCPanel(self):
        """Creates the 'Run DVC' tab. Creates the widgets in it and connects them."""
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

        rdvc_widgets['run_all_points_label'] = QLabel(groupBox)
        rdvc_widgets['run_all_points_label'].setText("Run all Points in cloud:")
        rdvc_widgets['run_all_points_label'].setToolTip("Run all of the points in the pointcloud.")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_all_points_label'])

        rdvc_widgets['run_all_points_entry'] = QtWidgets.QPushButton(groupBox)
        rdvc_widgets['run_all_points_entry'].setText("Set all points")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_all_points_entry'])
        rdvc_widgets['run_all_points_entry'].clicked.connect(self._set_num_points_in_run_to_all)

        widgetno +=1

        rdvc_widgets['run_points_label'] = QLabel(groupBox)
        rdvc_widgets['run_points_label'].setText("Points in Run:")
        rdvc_widgets['run_points_label'].setToolTip("Run on a selection of the points in the pointcloud.")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_points_label'])

        rdvc_widgets['run_points_spinbox'] = QSpinBox(groupBox)
        rdvc_widgets['run_points_spinbox'].setMinimum(10)
        # max will be set to the number in the point cloud in DisplayNumberOfPointcloudPoints
        maxpoints = 10000
        rdvc_widgets['run_points_spinbox'].setMaximum(maxpoints)
        rdvc_widgets['run_points_spinbox'].setValue(100)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_points_spinbox'])
        widgetno += 1         

        rdvc_widgets['run_max_displacement_label'] = QLabel(groupBox)
        rdvc_widgets['run_max_displacement_label'].setText("Maximum Displacement (voxels)")
        
        displacement_text = "Defines the maximum displacement expected within the reference image volume.\n\
This is a very important paramater used for search process control and memory allocation.\n\
Set to a reasonable value just greater than the actual sample maximum displacement.\n\
Be cautious: large displacements make the search process slower and less reliable.\n\
It is best to reduce large rigid body displacements through image volume manipulation.\n\
Future code development will introduce methods for better management of large displacements."
        rdvc_widgets['run_max_displacement_label'].setToolTip(displacement_text)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_max_displacement_label'])
        rdvc_widgets['run_max_displacement_entry'] = QSpinBox(groupBox)
        rdvc_widgets['run_max_displacement_entry'].setValue(15)
        rdvc_widgets['run_max_displacement_entry'].setToolTip(displacement_text)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_max_displacement_entry'])
        widgetno += 1

        rdvc_widgets['run_ndof_label'] = QLabel(groupBox)
        rdvc_widgets['run_ndof_label'].setText("Number of Optimisation Parameters")
        
        dof_text = "Defines the optimisation parameters in the final stage of the search.\n\
Translation only suffices for a quick, preliminary investigation.\nAdding rotation will significantly improve displacement accuracy in most cases.\nUse strain degrees of freedom for cases when the highest precision is required.\n\
3 = translation only,\n\
6 = translation and rotation,\n\
12 = translation, rotation and strain."
        rdvc_widgets['run_ndof_label'].setToolTip(dof_text)

        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_ndof_label'])
        rdvc_widgets['run_ndof_entry'] = QComboBox(groupBox)
        rdvc_widgets['run_ndof_entry'].addItem('3')
        rdvc_widgets['run_ndof_entry'].addItem('6')
        rdvc_widgets['run_ndof_entry'].addItem('12')
        rdvc_widgets['run_ndof_entry'].setCurrentIndex(1)
        rdvc_widgets['run_ndof_entry'].setToolTip(dof_text)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_ndof_entry'])
        widgetno += 1

        rdvc_widgets['run_objf_label'] = QLabel(groupBox)
        rdvc_widgets['run_objf_label'].setText("Objective Function")
        
        objf_text = "Defines the objective function template matching form.\n\
See B. Pan, Equivalence of Digital Image Correlation Criteria for Pattern Matching, 2010\n\
Functions become increasingly expensive and more robust as you progress from sad to znssd.\n\
Minimizing squared-difference and maximizing cross-correlation are functionally equivalent.\n\
sad  = sum of absolute differences\n\
ssd  = sum of squared differences\n\
zssd  = intensity offset insensitive sum of squared differences (value not normalized)\n\
nssd  = intensity range insensitive sum of squared differences (0.0 = perfect match, 1.0 = max value)\n\
znssd  = intensity offset and range insensitive sum of squared differences (0.0 = perfect match, 1.0 = max value)\n\
Notes on objective function values:\n\
    1. The normalized quantities nssd and znssd are preferred, as quality of match can be assessed.\n\
    2. The natural range of nssd is [0.0 to 2.0], and of znssd is [0.0 to 4.0].\n\
    3. Both are scaled for output into the [0.0 to 1.0] range for ease of comparison."
        rdvc_widgets['run_objf_label'].setToolTip(objf_text)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_objf_label'])
        rdvc_widgets['run_objf_entry'] = QComboBox(groupBox)
        rdvc_widgets['run_objf_entry'].addItem('sad')
        rdvc_widgets['run_objf_entry'].addItem('ssd')
        rdvc_widgets['run_objf_entry'].addItem('zssd')
        rdvc_widgets['run_objf_entry'].addItem('nssd')
        rdvc_widgets['run_objf_entry'].addItem('znssd')
        rdvc_widgets['run_objf_entry'].setCurrentIndex(4)
        rdvc_widgets['run_objf_entry'].setToolTip(objf_text)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['run_objf_entry'])
        widgetno += 1

        rdvc_widgets['run_iterp_type_label'] = QLabel(groupBox)
        rdvc_widgets['run_iterp_type_label'].setText("Interpolation type")
        interp_text = "Defines the interpolation method used during template matching.\n\
Trilinear is significantly faster, but with known template matching artifacts.\n\
Trilinear is most useful for tuning other search parameters during preliminary runs.\n\
Tricubic is computationally expensive, but is the choice if strain is of interst."
        rdvc_widgets['run_iterp_type_label'].setToolTip(interp_text)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['run_iterp_type_label'])
        rdvc_widgets['run_iterp_type_entry'] = QComboBox(groupBox)
        rdvc_widgets['run_iterp_type_entry'].addItem('Nearest')
        rdvc_widgets['run_iterp_type_entry'].addItem('Trilinear')
        rdvc_widgets['run_iterp_type_entry'].addItem('Tricubic')
        rdvc_widgets['run_iterp_type_entry'].setCurrentIndex(2)
        rdvc_widgets['run_iterp_type_entry'].setToolTip(interp_text)
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
        rdvc_widgets['subvol_points_label'].setText("Sampling points in subvolume:")

        subvol_points_text = "Defines the number of points within each subvolume.\n\
In this code, subvolume point locations are NOT voxel-centered and the number is INDEPENDENT of subvolume size.\n\
Interpolation within the reference image volume is used to establish templates with arbitrary point locations.\n\
For cubes a uniform grid of approximately this number of points is generated.\n\
For spheres the sampling points are randomly distributed within the subvolume.\n\
This parameter has a strong effect on computation time, so be careful."

        rdvc_widgets['subvol_points_label'].setToolTip(subvol_points_text)
        singleRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['subvol_points_label'])
    
        rdvc_widgets['subvol_points_spinbox'] = QSpinBox(singleRun_groupBox)
        rdvc_widgets['subvol_points_spinbox'].setMinimum(100)
        rdvc_widgets['subvol_points_spinbox'].setMaximum(50000)
        rdvc_widgets['subvol_points_spinbox'].setValue(10000)
        rdvc_widgets['subvol_points_spinbox'].setToolTip(subvol_points_text)

        singleRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['subvol_points_spinbox'])
        widgetno += 1

        bulkRun_groupBox = QGroupBox("Bulk Run Parameters")
        self.bulkRun_groupBox = bulkRun_groupBox
        bulkRun_groupBoxFormLayout = QFormLayout(bulkRun_groupBox)
        internalWidgetVerticalLayout.addWidget(bulkRun_groupBox)
        bulkRun_groupBox.hide()

        validatorint = QtGui.QIntValidator()

        widgetno = 0

        rdvc_widgets['subvol_size_range_min_label'] = QLabel(bulkRun_groupBox)
        rdvc_widgets['subvol_size_range_min_label'].setText("Minimum Subvolume Size ")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['subvol_size_range_min_label'])
        rdvc_widgets['subvol_size_range_min_value'] = QLineEdit(bulkRun_groupBox)
        rdvc_widgets['subvol_size_range_min_value'].setValidator(validatorint)
        
        current_subv_size = self.isoValueEntry.text()
        
        rdvc_widgets['subvol_size_range_min_value'].setText(current_subv_size)
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['subvol_size_range_min_value'])
        widgetno += 1

        rdvc_widgets['subvol_size_range_max_label'] = QLabel(bulkRun_groupBox)
        rdvc_widgets['subvol_size_range_max_label'].setText("Maximum Subvolume Size ")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['subvol_size_range_max_label'])
        rdvc_widgets['subvol_size_range_max_value'] = QLineEdit(bulkRun_groupBox)
        rdvc_widgets['subvol_size_range_max_value'].setValidator(validatorint)
        rdvc_widgets['subvol_size_range_max_value'].setText("100")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['subvol_size_range_max_value'])
        widgetno += 1

        rdvc_widgets['subvol_size_range_step_label'] = QLabel(bulkRun_groupBox)
        rdvc_widgets['subvol_size_range_step_label'].setText("Step in Subvolume Size ")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['subvol_size_range_step_label'])
        rdvc_widgets['subvol_size_range_step_value'] = QLineEdit(bulkRun_groupBox)
        rdvc_widgets['subvol_size_range_step_value'].setValidator(validatorint)
        rdvc_widgets['subvol_size_range_step_value'].setText("0")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['subvol_size_range_step_value'])
        widgetno += 1
        
        separators = [QFrame(groupBox)]
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1
        
        # NUMBER OF POINTS IN SUBVOLUME min
        rdvc_widgets['points_in_subvol_range_min_label'] = QLabel(bulkRun_groupBox)
        rdvc_widgets['points_in_subvol_range_min_label'].setText("Sampling points in subvolume min ")
        subvol_range_text = "Defines the number of points within each subvolume.\n\
In this code, subvolume point locations are NOT voxel-centered and the number is INDEPENDENT of subvolume size.\n\
Interpolation within the reference image volume is used to establish templates with arbitrary point locations.\n\
For cubes a uniform grid of approximately subvol_npts is generated.\n\
For spheres subvol_npts are randomly distributed within the subvolume.\n\
This parameter has a strong effect on computation time, so be careful."
        rdvc_widgets['points_in_subvol_range_min_label'].setToolTip(subvol_range_text)
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['points_in_subvol_range_min_label'])
        rdvc_widgets['points_in_subvol_range_min_value'] = QLineEdit(bulkRun_groupBox)
        rdvc_widgets['points_in_subvol_range_min_value'].setValidator(validatorint)
        rdvc_widgets['points_in_subvol_range_min_value'].setText("1000")
        rdvc_widgets['points_in_subvol_range_min_value'].setToolTip(subvol_range_text)
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['points_in_subvol_range_min_value'])
        widgetno += 1
        # overlap range max
        rdvc_widgets['points_in_subvol_range_max_label'] = QLabel(bulkRun_groupBox)
        rdvc_widgets['points_in_subvol_range_max_label'].setText("Sampling points in subvolume max ")
        rdvc_widgets['points_in_subvol_range_max_label'].setToolTip(subvol_range_text)
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['points_in_subvol_range_max_label'])
        rdvc_widgets['points_in_subvol_range_max_value'] = QLineEdit(bulkRun_groupBox)
        rdvc_widgets['points_in_subvol_range_max_value'].setValidator(validatorint)
        rdvc_widgets['points_in_subvol_range_max_value'].setText("10000")
        rdvc_widgets['points_in_subvol_range_max_value'].setToolTip(subvol_range_text)
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['points_in_subvol_range_max_value'])
        widgetno += 1
        # overlap range step
        rdvc_widgets['points_in_subvol_range_step_label'] = QLabel(bulkRun_groupBox)
        rdvc_widgets['points_in_subvol_range_step_label'].setText("Sampling points in subvolume step ")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.LabelRole, rdvc_widgets['points_in_subvol_range_step_label'])
        rdvc_widgets['points_in_subvol_range_step_value'] = QLineEdit(bulkRun_groupBox)
        rdvc_widgets['points_in_subvol_range_step_value'].setValidator(validatorint)
        rdvc_widgets['points_in_subvol_range_step_value'].setText("0")
        bulkRun_groupBoxFormLayout.setWidget(widgetno, QFormLayout.FieldRole, rdvc_widgets['points_in_subvol_range_step_value'])
        widgetno += 1

        button_groupBox = QGroupBox()
        self.button_groupBox = button_groupBox
        button_groupBoxFormLayout = QFormLayout(button_groupBox)
        internalWidgetVerticalLayout.addWidget(button_groupBox)

        rdvc_widgets['run_button'] = QPushButton(button_groupBox)
        rdvc_widgets['run_button'].setText("Run DVC")
        button_groupBoxFormLayout.setWidget(widgetno, QFormLayout.SpanningRole, rdvc_widgets['run_button'])
        widgetno += 1

        # TODO: implement option to only generate config
        # rdvc_widgets['run_config'] = QPushButton(button_groupBox)
        # rdvc_widgets['run_config'].setText("Generate Run Config")
        # #rdvc_widgets['run_config'].setEnabled(False)
        # button_groupBoxFormLayout.setWidget(widgetno, QFormLayout.SpanningRole, rdvc_widgets['run_config'])
        # widgetno += 1

        #Add button functionality:
        rdvc_widgets['run_type_entry'].currentIndexChanged.connect(self.show_run_groupbox)
        rdvc_widgets['run_button'].clicked.connect(self.create_config_worker)

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)

        self.rdvc_widgets = rdvc_widgets

    def _set_num_points_in_run_to_all(self):
        if hasattr(self, 'pc_no_points'):
            maxpoints = int(self.pc_no_points)
        else:
            maxpoints = 10000
        self.rdvc_widgets['run_points_spinbox'].setValue(maxpoints)

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
        label.setText(os.path.basename(folder[0]))
        if folder[0]:
            for button in next_buttons:
                button.setEnabled(True)
            if(type == "run"):
                self.run_folder = [folder[0]]
            elif(type == "results"):
                self.results_folder = folder
        #print(self.run_folder)
        #print(self.results_folder)

    def select_roi(self, label, next_button):
        dialogue = QFileDialog()
        f = dialogue.getOpenFileName(self,"Select a roi")
        self.roi = f[0]
        label.setText(os.path.basename(self.roi))
        if self.roi:
            next_button.setEnabled(True)

    def create_config_worker(self):
        """Creates warning dialogs if information is missing to run DVC.
        Calls the worker."""
        if hasattr(self, 'translate'):
            if self.translate is None:
                self.warningDialog("Complete image registration first.", "Error")
                return
        if not hasattr(self, 'translate'):
            self.warningDialog("Complete image registration first.", "Error")
            return
        
        if self.pointcloud_is == 'loaded':
            if not self.roi:
                self.warningDialog(window_title="Error", 
                               message="Create or load a pointcloud on the viewer first." )
                return
        elif self.pointcloud_is == 'generated':
            if not self.mask_reader:
                self.warningDialog(window_title="Error", 
                               message="Load a mask on the viewer first" )
                return
        else:
            self.warningDialog(window_title="Error", 
                               message="Missing pointcloud_is parameter! Contact developers" )
            return
        
        run_name = str( self.rdvc_widgets['name_entry'].text() )
        saved_run_names = []
        
        for i in range(self.result_widgets['run_entry'].count()):
            saved_run_names.append( str(self.result_widgets['run_entry'].itemText(i)) )
        if run_name in ['']:
            self.warningDialog(window_title="Error",
                message="Please set a run name")
            return
        elif run_name in saved_run_names:
            self.warningDialog(window_title="Error",
                message="Please set a run name not in the following list: {}".format(saved_run_names))
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
        # if single or bulk use the line below, if remote develop new functionality
        self.config_worker.signals.result.connect(partial (self.run_external_code))
        self.config_worker.signals.message.connect(self.updateProgressDialogMessage)
        self.threadpool.start(self.config_worker)  
        self.progress_window.setValue(10)
        
    def create_run_config(self, **kwargs):
        os.chdir(tempfile.tempdir)
        progress_callback = kwargs.get('progress_callback', PrintCallback())
        message_callback = kwargs.get('message_callback', PrintCallback())
        try:
            folder_name = self.rdvc_widgets['name_entry'].text()

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
                self.subvol_sizes = [self.pointcloud_parameters['pointcloud_size_entry'].text()]
                self.roi_files = [self.roi]
                pointcloud_new_file = os.path.join(results_folder, folder_name, "_" + self.pointcloud_parameters['pointcloud_size_entry'].text() + ".roi")
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

                        return ("subvolume error")
                else:
                    self.subvolume_points = [xmin]

                xmin = int(self.rdvc_widgets['subvol_size_range_min_value'].text())
                xmax = int(self.rdvc_widgets['subvol_size_range_max_value'].text())
                xstep = int(self.rdvc_widgets['subvol_size_range_step_value'].text())
                if xstep != 0:
                    if xmax > xmin:
                        N = (xmax-xmin)//xstep + 1
                        self.subvol_sizes = [xmin + i * xstep for i in range(N)]
                    else:
                        #print("subvolume size error")
                        return ("subvolume size error")
                else:
                    self.subvol_sizes = [xmin]

                self.roi_files = []
                #print(self.subvol_sizes)
                subvol_size_count = 0
                run_folder = os.path.join("Results" , folder_name)
                for subvol_size in self.subvol_sizes:
                    #print(subvol_size)
                    subvol_size_count+=1
                    filename = os.path.join( run_folder , "_{}.roi".format(str(subvol_size)))
                    if self.pointcloud_is == 'generated':
                        # we will generate the same pointcloud for each subvolume size
                        pc_subvol_size = self.pointcloud_parameters['pointcloud_size_entry'].text()
                        if not self.createPointCloud(filename=filename, subvol_size=int(pc_subvol_size), 
                                                     progress_callback=progress_callback, message_callback=message_callback):
                            return ("pointcloud error")
                    elif self.pointcloud_is == 'loaded':
                        # we will use the file with the pointcloud for each subvol size
                        shutil.copyfile(self.roi, filename)
                    else:
                        raise ValueError("pointcloud_is must be either 'generated' or 'loaded'")

                    self.roi_files.append(filename)
                    progress_callback.emit(subvol_size_count/len(self.subvol_sizes)*90)
                #print("finished making pointclouds")

            #print(self.roi_files)

            #print("DVC in: ", self.dvc_input_image)
            
            self.reference_file = self.dvc_input_image[0][0]
            if len(self.dvc_input_image[0]) > 1:
                self.reference_file = self.dvc_input_image[0]
            self.correlate_file = self.dvc_input_image[1][0]
            if len(self.dvc_input_image[1]) > 1:
                self.correlate_file = self.dvc_input_image[1]

            #print("REF: ", self.reference_file)


            run_config = {}
            run_config['points'] = self.points
            run_config['subvolume_points'] = self.subvolume_points
            run_config['subvolume_sizes'] = self.subvol_sizes
            run_config['reference_file'] = self.reference_file
            run_config['correlate_file'] = self.correlate_file
            run_config['roi_files']= self.roi_files
            run_config['vol_bit_depth'] = self.vol_bit_depth #8
            run_config['vol_hdr_lngth'] = self.vol_hdr_lngth #96
            run_config['vol_endian'] = "big" if self.image_info['isBigEndian'] else "little"
            run_config['dims']= self.unsampled_image_dimensions
            #[self.vis_widget_2D.image_data.GetDimensions()[0],self.vis_widget_2D.image_data.GetDimensions()[1],self.vis_widget_2D.image_data.GetDimensions()[2]] #image dimensions

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

            self.run_folder = "Results/" + folder_name
            run_config['run_folder'] = self.run_folder

            #where is point0
            run_config['point0'] = self.getPoint0ImageCoords()
            # here we assume that the world coordinate are the same as the original
            # image coordinate because spacing is 1,1,1 and origin is 0,0,0 for the 
            # original input image
            run_config['point0_world_coordinate'] = self.point0_world_coords
            suffix_text = "run_config"

            self.run_config_file = os.path.join(tempfile.tempdir, "Results", folder_name, "_" + suffix_text + ".json")

            with open(self.run_config_file, "w+") as tmp:
                json.dump(run_config, tmp)
                #print("Saving")

            progress_callback.emit(100)

            return(None)
        except Exception as e:
            print(e)
            self.progress_window.close()
            #TODO: test this and see if we need to stop the worker, or if not returning anything is enough

    def run_external_code(self, error = None):
        if error == "subvolume error":
            self.progress_window.setValue(100)
            self.warningDialog("Minimum number of sampling points in subvolume value higher than maximum", window_title="Value Error")
            self.cancelled = True
            return
        elif error == "pointcloud error":
            self.progress_window.setValue(100) 
            self.warningDialog(window_title="Error", 
                    message="Failed to create a point cloud.",
                    detailed_text='A pointcloud could not be created because there were no points in the selected region. \
Try modifying the subvolume size before creating a new pointcloud, and make sure it is smaller than the extent of the mask.\
The dimensionality of the pointcloud can also be changed in the Point Cloud panel.' )
            self.cancelled = True
            return
        elif error == "subvolume size error":
            self.progress_window.setValue(100) 
            self.warningDialog("Minimum subvolume size value higher than maximum", window_title="Value Error")
            self.cancelled = True
            return
            

        
        self.run_succeeded = True
    
        # this command will call DVC_runner to create the directories
        self.dvc_runner = DVC_runner(self, os.path.abspath(self.run_config_file), 
                                     self.finished_run, self.run_succeeded, tempfile.tempdir)

        setup = Worker(self.dvc_runner.set_up)
        setup.signals.message.connect(self.updateProgressDialogMessage)
        setup.signals.progress.connect(self.progress)
        # should connect also the error message
        setup.signals.finished.connect(self.dvc_runner.run_dvc)
        self.threadpool.start(setup)
        # self.dvc_runner.run_dvc()

    def update_progress(self, exe = None):
        if exe:
            line_b = self.process.readLine()
            line = str(line_b,"utf-8")
            #print(line)
            if len(line) > 4:
                try:
                    num = float(line.split(' ')[0]) #weird delay means isn't correct
                except ValueError as ve:
                    print(ve, file=sys.stderr)
                    num = 0
                if num > self.progress_window.value() and self.progress_window.value()<99:
                    self.progress_window.setValue(num)
        else:
            if (self.progress_window.value()<1):
                self.progress_window.setValue(1)

            self.progress_window.setValue(self.progress_window.value()+1)

    def finished_run(self):
        if self.run_succeeded:
            self.result_widgets['run_entry'].addItem(self.rdvc_widgets['name_entry'].text())
            self.show_run_pcs()


# DVC Results Panel:
    def CreateViewDVCResultsPanel(self):
        "Creates the 'DVC Results' tab. Creates the widgets in it and connects them."
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

        result_widgets['pc_label'] = QLabel(groupBox)
        result_widgets['pc_label'].setText("Subvolume Size:")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['pc_label'])
        result_widgets['pc_entry'] = QComboBox(groupBox)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['pc_entry'])
        widgetno += 1

        result_widgets['subvol_label'] = QLabel(groupBox)
        result_widgets['subvol_label'].setText("Points in Subvolume:")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['subvol_label'])
        result_widgets['subvol_entry'] = QComboBox(groupBox)
        result_widgets['subvol_entry'].setCurrentText("1000")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['subvol_entry'])
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

        #Pointcloud points label
        result_widgets['pc_points_label'] = QLabel("Points in current pointcloud:")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['pc_points_label'])
        result_widgets['pc_points_value'] = QLabel("0")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['pc_points_value'])
        widgetno += 1

        result_widgets['vec_label'] = QLabel(groupBox)
        result_widgets['vec_label'].setText("View:")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['vec_label'])

        result_widgets['vec_entry'] = QComboBox(groupBox)
        result_widgets['vec_entry'].addItems(['Pointcloud', 'Total Displacement', 'Displacement with respect to Reference Point 0'])
        result_widgets['vec_entry'].currentIndexChanged.connect(self._DVCResultsDisableRanges)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['vec_entry'])
        widgetno += 1

        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1  

        result_widgets['scale_vectors_label'] =  QLabel(groupBox)
        result_widgets['scale_vectors_label'].setText("Vector Scaling:")
        result_widgets['scale_vectors_label'].setToolTip("Adjust the scaling of the vectors. 1 means true displacement.")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['scale_vectors_label'])

        result_widgets['scale_vectors_entry'] = QDoubleSpinBox(groupBox)
        result_widgets['scale_vectors_entry'].setSingleStep(0.1)
        result_widgets['scale_vectors_entry'].setMaximum(10000.)
        result_widgets['scale_vectors_entry'].setMinimum(0.1)
        result_widgets['scale_vectors_entry'].setValue(1.00)
        result_widgets['scale_vectors_entry'].setToolTip("Adjust the scaling of the vectors. 1 means true displacement.")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['scale_vectors_entry'])
        widgetno += 1

        result_widgets['range_vectors_all_label'] =  QLabel(groupBox)
        result_widgets['range_vectors_all_label'].setText("Display Vectors Full Range:")
        result_widgets['range_vectors_all_label'].setToolTip("Show all displacement vectors")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['range_vectors_all_label'])

        result_widgets['range_vectors_all_entry'] = QPushButton(groupBox)
        result_widgets['range_vectors_all_entry'].setText("Reset to full range")
        result_widgets['range_vectors_all_entry'].setEnabled(False)
        result_widgets['range_vectors_all_entry'].clicked.connect(self._setUIWithDisplacementVectorFullRange)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['range_vectors_all_entry'])
        widgetno += 1

        result_widgets['range_vectors_min_label'] =  QLabel(groupBox)
        result_widgets['range_vectors_min_label'].setText("Vector Range Min:")
        result_widgets['range_vectors_min_label'].setToolTip("Adjust the range of the vectors. The full range is between 0 and 1.")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['range_vectors_min_label'])

        single_step = 0.00001
        result_widgets['range_vectors_min_entry'] = QDoubleSpinBox(groupBox)
        result_widgets['range_vectors_min_entry'].setSingleStep(single_step)
        result_widgets['range_vectors_min_entry'].setMaximum(1.-single_step)
        result_widgets['range_vectors_min_entry'].setMinimum(0.0)
        result_widgets['range_vectors_min_entry'].setValue(0.00)
        result_widgets['range_vectors_min_entry'].setToolTip("Adjust the range of the vectors. The full range is between 0 and 1.")
        result_widgets['range_vectors_min_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['range_vectors_min_entry'])
        widgetno += 1

        result_widgets['range_vectors_max_label'] =  QLabel(groupBox)
        result_widgets['range_vectors_max_label'].setText("Vector Range Max:")
        result_widgets['range_vectors_max_label'].setToolTip("Adjust the range of the vectors. The full range is between 0 and 1.")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, result_widgets['range_vectors_max_label'])

        single_step = 0.00001
        result_widgets['range_vectors_max_entry'] = QDoubleSpinBox(groupBox)
        result_widgets['range_vectors_max_entry'].setSingleStep(single_step)
        result_widgets['range_vectors_max_entry'].setMinimum(single_step)
        result_widgets['range_vectors_max_entry'].setValue(1.00)
        result_widgets['range_vectors_max_entry'].setToolTip("Adjust the range of the vectors. The full range is between 0 and 1.")
        result_widgets['range_vectors_max_entry'].setEnabled(False)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['range_vectors_max_entry'])
        widgetno += 1

        result_widgets['load_button'] = QPushButton("View Pointcloud/Vectors")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, result_widgets['load_button'])
        widgetno += 1

        result_widgets['load_button'].clicked.connect(self.LoadResultsOnViewer)

        result_widgets['run_entry'].currentIndexChanged.connect(self.show_run_pcs)   
        result_widgets['graphs_button'].clicked.connect(self.CreateGraphsWindow)

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)
        self.result_widgets = result_widgets
     
    def show_run_pcs(self):
        #show pointcloud files in list
        self.result_widgets['pc_entry'].clear()
        self.result_widgets['subvol_entry'].clear()

        directory = os.path.join(tempfile.tempdir, "Results", self.result_widgets['run_entry'].currentText())
        self.results_folder = directory

        self.result_list=[]
        points_list = []
        subvol_list = []
        for folder in glob.glob(os.path.join(directory, "dvc_result_*")):
            file_path = os.path.join(folder, os.path.basename(folder))
            result = RunResults(file_path)
            self.result_list.append(result)
            el = str(result.subvol_points)
            if el not in points_list:
                points_list.append(el)
            el = str(result.subvol_size)
            if el not in subvol_list:
                subvol_list.append(el)
                            
        # update the interface
        self.result_widgets['pc_entry'].addItems(subvol_list)
        self.result_widgets['subvol_entry'].addItems(points_list)
               
    def LoadResultsOnViewer(self):
        """Opens a warning dialog if the entries on 'subvolume size' and 'points in subvolume' are not suitable.
        If the point cloud is selected in 'view' it loads the point cloud on the viewers, 
        else, it shows the vectors on the viewers."""
        if hasattr(self, 'result_list'):
            try:
                subvol_size = int(self.result_widgets['pc_entry'].currentText())
            except ValueError as ve:
                self.warningDialog("Invalid input at Subvolume Size", "Error")
                return
            try:
                subvol_points = int(self.result_widgets['subvol_entry'].currentText())
            except ValueError as ve:
                self.warningDialog("Invalid input at Subvolume Size", "Error")
                return

            if(subvol_points == ""):
                self.warningDialog("An error occurred with this run so the results could not be displayed.", "Error")
                return


            results_folder = os.path.join(tempfile.tempdir, "Results", self.result_widgets['run_entry'].currentText())
            self.roi = os.path.join(results_folder ,"_" + str(subvol_size) + ".roi")
            self.results_folder = results_folder

            if (self.result_widgets['vec_entry'].currentText() == "Pointcloud"):
                self.PointCloudWorker("load pointcloud file")
                self._removeColormap()
                # reset the interface
                self.result_widgets['range_vectors_max_entry'].setEnabled(False)
                self.result_widgets['range_vectors_min_entry'].setEnabled(False)
                # set the label of the number of points to the number of points in the pointcloud
                self.num_processed_points = int( self.pc_no_points )
                self.DisplayNumberOfPointcloudPoints()

            else: 
                for result in self.result_list:
                    if result.subvol_size == subvol_size:
                        if result.subvol_points == subvol_points:
                            run_file = result.disp_file
                            self.displayVectors(run_file)


    def _DVCResultsDisableRanges(self, index):
        """Disables the range-vectors widgets. 
        Note: The min is used as a checker in 'loadDisplacementFile', hence when editing this method make
        sure the points/vectors are visualised correctly in the viewer. """
        # reset the interface
        self.result_widgets['range_vectors_max_entry'].setEnabled(False)
        self.result_widgets['range_vectors_min_entry'].setEnabled(False)

    def CreateGraphsWindow(self):
        #print("Create graphs")
        if self.result_widgets['run_entry'].currentText() != "":
            self.results_folder = os.path.join(tempfile.tempdir, "Results", self.result_widgets['run_entry'].currentText())
        else:
            self.results_folder = None

        if self.results_folder is not None:
            self.graph_window = GraphsWindow(self)
            self.graph_window.SetResultsFolder(self.results_folder)
            self.graph_window.CreateDockWidgets()
            self.graph_window.show()
        

#Dealing with saving sessions:

    def closeEvent(self, event):
        self.CreateSaveWindow("Quit without Saving", event)
        self.threadpool.waitForDone()
        if not hasattr(self, 'should_really_close') or not self.should_really_close:
            event.ignore()
        else:
            event.accept()

    def CreateSaveWindow(self, cancel_text, event):

        dialog = FormDialog(parent=self, title='Save Session')
        self.SaveWindow = dialog
        
        self.SaveWindow.Ok.setText('Save')
        

        # add input 1 as QLineEdit
        qlabel = QtWidgets.QLabel(dialog.groupBox)
        qlabel.setText("Save session as:")
        qwidget = QtWidgets.QLineEdit(dialog.groupBox)
        qwidget.setClearButtonEnabled(True)
        rx = QRegExp("[A-Za-z0-9]+")
        validator = QRegExpValidator(rx, dialog) #need to check this
        qwidget.setValidator(validator)
        # finally add to the form widget
        dialog.addWidget(qwidget, qlabel, 'session_name')
        
        qwidget = QtWidgets.QCheckBox(dialog.groupBox)
        qwidget.setText("Compress Files")
        qwidget.setEnabled(True)
        qwidget.setChecked(False)
        dialog.addWidget(qwidget,'','compress')
        
        self.save_button = QPushButton("Save")
        # We have 2 instances of the window.
        if type(event) ==  QCloseEvent:
            # This is the case where we are quitting the app and the window asks if we
            # would like to save
            self.SaveWindow.Cancel.clicked.connect(lambda: self.save_quit_just_quit())
            self.SaveWindow.Ok.clicked.connect(lambda: self.save_quit_accepted())
            self.SaveWindow.Cancel.setText('Quit without saving')
        else:
            # This is the case where we are just choosing to 'Save' in the file menu
            # so we never quit the app.
            self.SaveWindow.Cancel.clicked.connect(lambda: self.save_quit_rejected())
            self.SaveWindow.Ok.clicked.connect(lambda: self.save_accepted())
            self.SaveWindow.Cancel.setText('Cancel')
        
        self.SaveWindow.exec()

    def save_accepted(self):
        self.should_really_close = False
        compress = self.SaveWindow.widgets['compress_field'].isChecked()
        self.SaveWindow.close()
        self.SaveSession(self.SaveWindow.widgets['session_name_field'].text(), compress, None)

    def save_quit_accepted(self):
        #Load Saved Session
        self.should_really_close = True
        compress = self.SaveWindow.widgets['compress_field'].isChecked()
        self.SaveWindow.close()
        self.SaveSession(self.SaveWindow.widgets['session_name_field'].text(), compress, QCloseEvent())
        
    def save_quit_just_quit(self):
        event = QCloseEvent()
        self.SaveWindow.close()
        self.RemoveTemp(event) # remove tempdir for this session.
        self.should_really_close = True
        self.close()

    def save_quit_rejected(self):
        self.should_really_close = False
        self.SaveWindow.close()

    def SaveSession(self, text_value, compress, event):
        # Save window geometry and state of dockwindows
        # https://doc.qt.io/qt-5/qwidget.html#saveGeometry
        g = self.saveGeometry()
        # print( str(g.toHex().data(), encoding='utf-8'))
        # qsettings = QtCore.QSettings(parent=self)
        # qsettings.setValue('geometry', self.saveGeometry())
        
        # can't save qbyte array to json so have to convert it
        self.config['geometry'] = str(g.toHex().data(), encoding='utf-8')
        w = self.saveState()
        self.config['window_state'] = str(g.toHex().data(), encoding='utf-8')

        #save values for select image panel:
        if len(self.image[0]) > 0: 
            if(self.copy_files):
                self.config['copy_files'] = self.copy_files

            #we need to change location of image to being the name of the image w/o directories
            image = [[],[]]
            for i in self.image[0]:
                image[0].append(i)
            for j in self.image[1]:
                image[1].append(j)

            self.config['image']=image
            self.config['image_copied']=self.image_copied
            self.config['image_orientation']=self.vis_widget_2D.frame.viewer.getSliceOrientation()
            self.config['current_slice']=self.vis_widget_2D.frame.viewer.getActiveSlice()

            #we need to do the same for the dvc input image:
            dvc_input_image = [[],[]]
            for i in self.dvc_input_image[0]:
                if self.image_copied[0] or self.dvc_input_image_in_session_folder:
                    dvc_input_image[0].append(os.path.basename(i))
                else:
                    dvc_input_image[0].append(i)
            for j in self.dvc_input_image[1]:
                if self.image_copied[1] or self.dvc_input_image_in_session_folder:
                    dvc_input_image[1].append(os.path.basename(j))
                else:
                   dvc_input_image[1].append(j)
            self.config['dvc_input_image']=dvc_input_image
            self.config['dvc_input_image_in_session_folder'] = self.dvc_input_image_in_session_folder

            # print("ROI: ", self.roi)
            # print("temp", tempfile.tempdir)
            if (self.roi):
                self.roi = os.path.abspath(self.roi)
                if os.path.abspath(tempfile.tempdir) in self.roi:
                    self.config['roi_file'] =  self.roi[len(os.path.abspath(tempfile.tempdir))+1:]
                    self.config['roi_ext'] = False
                else:
                    self.config['roi_file'] = self.roi
                    self.config['roi_ext'] = True 
            else:
                self.config['roi_file'] = None
                self.config['roi_ext'] = False 
            

            if hasattr(self, 'mask_file'):
                self.config['mask_details']=self.mask_details
                if tempfile.tempdir in os.path.abspath(self.mask_file):
                    self.config['mask_file']=self.mask_file[len(os.path.abspath(tempfile.tempdir))+1:]
                    self.config['mask_ext'] = False
                else:
                    self.config['mask_file']=self.mask_file
                    self.config['mask_ext'] = True 
  

        self.config['pointCloud_details']=self.pointCloud_details

        #save values for Run DVC panel
        if hasattr(self,'subvolume_points'): #check if this test correct
            if self.subvolume_points is not None:
                self.config['subvol_points'] = self.subvolume_points
                self.config['points'] = self.points
                self.config['run_button_enabled'] = True
        self.config['pointcloud_loaded'] = self.pointCloudLoaded

        #Image Registration:
        
        if hasattr(self, 'translate'):
            if self.translate is not None:
                self.config['reg_translation'] = (self.translate.GetTranslation()[0],self.translate.GetTranslation()[1],self.translate.GetTranslation()[2])
            else:
                self.config['reg_translation'] = None

        else:
            self.config['reg_translation'] = None
        if hasattr(self, 'point0_world_coords'):
            self.config['point0'] = eval(self.registration_parameters['point_zero_entry'].text())
        else:
            self.config['point0'] = None

        self.config['reg_sel_size'] = self.registration_parameters['registration_box_size_entry'].value()
        # size of reg box
        # if tickbox checked

        pc = self.pointcloud_parameters

        #Pointcloud panel:
        self.config['pc_subvol_rad'] = pc['pointcloud_size_entry'].text()
        self.config['pc_subvol_shape'] = pc['pointcloud_volume_shape_entry'].currentIndex()
        self.config['pc_dim'] = pc['pointcloud_dimensionality_entry'].currentIndex()
        self.config['pc_overlapx'] = pc['pointcloud_overlap_x_entry'].value()
        self.config['pc_overlapy'] = pc['pointcloud_overlap_y_entry'].value()
        self.config['pc_overlapz'] = pc['pointcloud_overlap_z_entry'].value()
        self.config['pc_rotx'] = pc['pointcloud_rotation_x_entry'].text()
        self.config['pc_roty'] = pc['pointcloud_rotation_y_entry'].text()
        self.config['pc_rotz'] = pc['pointcloud_rotation_z_entry'].text()

        #Downsampling level
        if self.settings.value("gpu_size") is not None: 
            self.config['gpu_size'] = self.settings.value("gpu_size")
        else:
            self.config['gpu_size'] = 1

        if self.settings.value("vis_size") is not None:
            self.config['vis_size'] = self.settings.value("vis_size")
        else:
            self.config['vis_size'] = 1
        
  
        now = datetime.now()
        now_string = now.strftime("%d-%m-%Y-%H-%M")
        self.config['datetime'] = now_string
        #save time to temp file

        user_string = text_value
        
        suffix_text = "_" + user_string + "_" + now_string 

        os.chdir(self.temp_folder)
        tempdir = shutil.move(tempfile.tempdir, suffix_text)
        tempfile.tempdir = os.path.abspath(tempdir)

        fd, f = tempfile.mkstemp(suffix=suffix_text + ".json", dir = tempfile.tempdir) #could not delete this using rmtree?

        with open(f, "w+") as tmp:
            json.dump(self.config, tmp)
            #print("Saving")

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
            self.ShowZipProgress(tempfile.tempdir, tempfile.tempdir +'.zip', 0.7)
        else:
            self.ShowZipProgress(tempfile.tempdir, tempfile.tempdir +'.zip', 1)

        #give variables filepath including new name of temp folder:
        # print("temp", tempfile.tempdir)
        # print("roi ext", self.config['roi_ext'])
        # print(self.roi, self.config['roi_file'])
        if (self.roi and not self.config['roi_ext']):
            self.roi = os.path.join(os.path.abspath(tempfile.tempdir), self.config['roi_file'])
            #print(self.roi)

        if hasattr(self, 'mask_file'):
            if 'mask_file' in self.config:
                self.mask_file = os.path.join(os.path.abspath(tempfile.tempdir), self.config['mask_file'])

        count = 0
        for i in self.image[0]:
            if self.image_copied[0]:
                # print(os.path.join(os.path.abspath(tempfile.tempdir), self.config['image'][0][count]) )
                self.image[0][count] = os.path.join(os.path.abspath(tempfile.tempdir), self.config['image'][0][count]) 
            count +=1
        count = 0
        for j in self.image[1]:
            if self.image_copied[1]:
                self.image[1][count] = os.path.join(os.path.abspath(tempfile.tempdir), self.config['image'][1][count]) 
            count += 1

        count = 0
        for i in self.dvc_input_image[0]:
            if self.image_copied[0] or self.dvc_input_image_in_session_folder:
                self.dvc_input_image[0][count] = os.path.join(os.path.abspath(tempfile.tempdir), self.config['dvc_input_image'][0][count]) 
            count+=1

        count=0    
        for j in self.dvc_input_image[1]:      
            if self.image_copied[1] or self.dvc_input_image_in_session_folder:
                self.dvc_input_image[1][count] = os.path.join(os.path.abspath(tempfile.tempdir), self.config['dvc_input_image'][1][count]) 
            count+=1

        results_folder = os.path.join(tempfile.tempdir, "Results", self.result_widgets['run_entry'].currentText())
        self.results_folder = results_folder
   
    def CloseSaveWindow(self):
        if hasattr(self, 'progress_window'):
            self.progress_window.setValue(100)
    
        self.SaveWindow.close()
        self.should_really_close = True
       
    def ZipDirectory(self, *args, **kwargs):
        directory, compress = args
        progress_callback = kwargs.get('progress_callback', None)

        zip = zipfile.ZipFile(directory + '.zip', 'a')

        for r, d, f in os.walk(directory):
            for _file in f:
                if compress:
                    compress_type = zipfile.ZIP_DEFLATED
                else:
                    compress_type = zipfile.ZIP_STORED

                zip.write(os.path.join(r, _file),os.path.join(r, _file)[len(directory)+1:],compress_type=compress_type)
        zip.close()

        # print("Finished zip")

    def RemoveTemp(self, event):
        # ensure we are not 'in' a directory we will be deleting:
        os.chdir(self.temp_folder)
        if hasattr(self, 'progress_window'):
            self.progress_window.setLabelText("Closing")
            self.progress_window.setMaximum(100)
            self.progress_window.setValue(98)
        #print("removed temp", tempfile.tempdir)
        shutil.rmtree(tempfile.tempdir)

        if hasattr(self, 'progress_window'):
            self.progress_window.setValue(100)
        if hasattr(self, 'SaveWindow'):
            self.SaveWindow.close()

        if event != "new session":
            self.close()
        
    def ShowZipProgress(self, folder, new_file_dest,ratio):
       
        self.progress_window.setValue(10)

        temp_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                temp_size += os.path.getsize(fp)

        while not os.path.exists(new_file_dest):
            time.sleep(0.01)

        zip_size = os.path.getsize(new_file_dest)

        while temp_size*ratio != zip_size and self.progress_window.value() < 98 and self.progress_window.value() !=-1:
            zip_size = os.path.getsize(new_file_dest)
            self.progress_window.setValue((float(zip_size)/(float(temp_size)*ratio))*100)
            time.sleep(0.1)

    def ShowExportProgress(self, folder, new_file_dest):
        
        self.progress_window.setValue(10)

        temp_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    temp_size += os.path.getsize(fp)

        while not os.path.exists(new_file_dest):
                time.sleep(0.01)

        exp_size = 0
        for dirpath, dirnames, filenames in os.walk(new_file_dest):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    #print(fp)
                    exp_size += os.path.getsize(fp) 

        while temp_size != exp_size and self.progress_window.value() < 98 and self.progress_window.value() !=-1:
            # print((float(exp_size)/(float(temp_size)))*100)
            self.progress_window.setValue((float(exp_size)/(float(temp_size)))*100)
            time.sleep(0.01)

            exp_size = 0
            for dirpath, dirnames, filenames in os.walk(folder):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    #print(fp)
                    exp_size += os.path.getsize(fp)

    def ExportSession(self):
        #print("In select image")
        dialogue = QFileDialog()
        folder= dialogue.getExistingDirectory(self, "Select a Folder")
        now = datetime.now()
        now_string = now.strftime("%d-%m-%Y-%H-%M")
        export_location = os.path.join(folder, "_" + now_string)
        if folder:
            self.create_progress_window("Exporting","Exporting Files",max=100)
            self.progress_window.setValue(5)
            export_worker = Worker(self.exporter, export_location)
            export_worker.signals.finished.connect(self.progress_complete)
            self.threadpool.start(export_worker)
            self.ShowExportProgress(tempfile.tempdir, export_location)

    def exporter(self, *args, **kwargs):
        export_location = args[0]
        shutil.copytree(tempfile.tempdir, export_location)

#Dealing with loading sessions:
         
    def CreateSessionSelector(self, stage): 
        temp_folders = []
        #print ("Session folder: ", self.temp_folder)

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
            # self.show()
            return
        elif len(temp_folders) == 0:
            self.e('', '', '')
            error_title = "LOAD ERROR"
            error_text = "There are no previously saved sessions to load."
            self.displayFileErrorDialog(message=error_text, title=error_title)
            return #Exits the LoadSession function

        else:
            
            dialog = FormDialog(parent=self, title='Load a Session')
            
            self.label = QLabel("Select a session:")
            combo = QComboBox(dialog.groupBox)
            combo.addItems(temp_folders)
            dialog.addWidget(combo, 'Select a session:', 'select_session')

            dialog.Ok.setText('Load')
            dialog.Cancel.setText('New Session')
            dialog.Ok.clicked.connect(self.load_session_load)
            dialog.Cancel.clicked.connect(self.load_session_new)
            self.SessionSelectionWindow = dialog
            # Try to centre the load session window
            # from PySide2.QtGui import QScreen
            # geom = QScreen().availableGeometry()
            # print (geom)
            # centrex = geom.topRight().x() + geom.topLeft().x()
            # centrey = geom.topRight().y() + geom.bottomRight().y()
            # dialog.move(centrex/2,centrey/2)
            dialog.open()
        
    def load_session_load(self):
        #Load Saved Session
        self.InitialiseSessionVars()

        config_worker = Worker(self.LoadConfigWorker, selected_text=self.SessionSelectionWindow.widgets['select_session_field'].currentText())
        self.create_progress_window("Loading", "Loading Session")
        config_worker.signals.progress.connect(self.progress)
        config_worker.signals.message.connect(self.updateProgressDialogMessage)
        config_worker.signals.finished.connect(self.LoadSession)
        self.threadpool.start(config_worker)
        self.progress_window.setValue(10)
        #self.parent.loaded_session = True
        self.SessionSelectionWindow.close()

    def load_session_new(self):
        self.NewSession()
        self.SessionSelectionWindow.close()

    def NewSession(self):
        self.RemoveTemp("new session")
        self.CreateWorkingTempFolder()
        self.InitialiseSessionVars()
        self.LoadSession() #Loads blank session
        #self.resetRegistration()

        #other possibility for loading new session is closing and opening window:
        # self.close()
        # subprocess.Popen(['python', 'dvc_interface.py'], shell = True) 
    
    def LoadConfigWorker(self, **kwargs): 
        selected_text = kwargs.get('selected_text', None)
        progress_callback = kwargs.get('progress_callback', PrintCallback())
        message_callback = kwargs.get('message_callback', PrintCallback())
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
        if progress_callback is not None:
            progress_callback.emit(20)
        
        message_callback.emit('Unpacking session file...')
        import zipfile
        
        with zipfile.ZipFile(selected_folder, 'r') as zip_ref:
            infolist = zip_ref.infolist()
            start_progress = 20
            end_progress = 70
            for i,info in enumerate(infolist):
                message_callback.emit('Extracting ' + info.filename)
                zip_ref.extract(info.filename, selected_folder[:-4])
                progress_callback.emit(int(start_progress + (end_progress - start_progress) * (i / len(infolist))))
        # shutil.unpack_archive(selected_folder, selected_folder[:-4])
        loaded_tempdir = selected_folder[:-4]
        
        if progress_callback is not None:
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

        # if tempfile.tempdir != loaded_tempdir: # if we are not loading the same session that we already had open
        #     shutil.rmtree(tempfile.tempdir) 

        if progress_callback is not None:
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

        message_callback.emit('Loading session configuration')
        with open(selected_file) as tmp:
            self.config = json.load(tmp)
        
        os.remove(selected_file)
        if progress_callback is not None:
            progress_callback.emit(100)

    def LoadSession(self):
        os.chdir(tempfile.tempdir)
        self.resetRegistration()
        
        self.loading_session = True

        self.mask_parameters['masksList'].clear()
        self.pointcloud_parameters['pointcloudList'].clear()
        
        #use info to update the window:
        if 'geometry' in self.config:
            # g = QByteArray.fromHex(bytes(self.config['geometry'], 'utf-8'))
            w = QByteArray.fromHex(bytes(self.config['window_state'], 'utf-8'))
            # self.restoreGeometry(g)
            self.restoreState(w)

        if 'pointcloud_loaded' in self.config: #whether a pointcloud was displayed when session saved
            self.pointCloudLoaded = self.config['pointcloud_loaded']
            if self.pointCloudLoaded:
                self.roi = self.config['roi_file']
                # if 'roi_ext' in self.config:
                #     if not self.config['roi_ext']:
                #         self.roi = os.path.abspath(
                #             os.path.join(tempfile.tempdir, self.roi))

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
                    path = i
                    self.image[j].append(i)
                    if not os.path.exists(path):
                        search_button = QPushButton('Select Image')
                        search_button.clicked.connect(lambda: self.SelectImage(j,self.image))
                        self.e(
                        '', '', 'This file has been deleted or moved to another location. Therefore this session cannot be loaded. \
Please select the new location of the file, or move it back to where it was originally saved and reload the session.')
                        error_title = "READ ERROR"
                        error_text = "Error reading file: ({filename})".format(filename=i)
                        self.displayFileErrorDialog(message=error_text, title=error_title, action_button=search_button)

                if self.config['dvc_input_image'] == self.config['image']:
                    self.dvc_input_image = copy.deepcopy(self.image)
                else:
                    for num, i in enumerate(self.config['dvc_input_image'][j]):

                        #save paths to images to variable
                        if self.config['image_copied'][j]:
                            path = os.path.abspath(os.path.join(tempfile.tempdir, i))
                            # print("The DVC input path is")
                            # print(path)
                            self.dvc_input_image[j].append(path)
                        elif('dvc_input_image_in_session_folder' in self.config):
                            #TODO: check this?
                            self.dvc_input_image_in_session_folder = self.config['dvc_input_image_in_session_folder']
                        else:
                            path = i
                            self.dvc_input_image[j].append(i)
                        if not os.path.exists(path):
                            if [path] == self.image[j][num]:
                                self.dvc_input_image.append(self.image[j][num])

                            else:
                                search_button = QPushButton('Select Image')
                                search_button.clicked.connect(lambda: self.SelectImage(j,self.dvc_input_image))
                                self.e(
                                '', '', 'This file has been deleted or moved to another location. Therefore this session cannot be loaded. \
        Please select the new location of the file, or move it back to where it was originally saved and reload the session.')
                                error_title = "READ ERROR"
                                error_text = "Error reading file: ({filename})".format(filename=i)
                                self.displayFileErrorDialog(message=error_text, title=error_title, action_button=search_button)
            
             # Set labels to display file names:
            if len(self.config['image'][0])>1:
                self.si_widgets['ref_file_label'].setText(os.path.basename(self.config['image'][0][0]) + " + " + str(len(self.config['image'][0])-1) + " more files.")
            else:
                self.si_widgets['ref_file_label'].setText(os.path.basename(self.config['image'][0][0]))
            
            if len(self.config['image'][1])>1:
                self.si_widgets['cor_file_label'].setText(os.path.basename(self.config['image'][1][0]) + " + " + str(len(self.config['image'][1])-1) + " more files.")
            elif self.config['image'][1]:
                self.si_widgets['cor_file_label'].setText(os.path.basename(self.config['image'][1][0]))                      

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
                if 'gpu_size' in self.config and 'vis_size' in self.config:
                    if float(self.settings.value('gpu_size')) != float(self.config['gpu_size']) \
                            or float(self.settings.value('vis_size')) != float(self.config['vis_size']):

                        self.mask_load = False

                        self.e('', '', "If you would like to load the mask, open the settings and change the GPU size field to {gpu_size}GB and the maximum visualisation size to {vis_size} GB.\
    Then reload the session.".format(gpu_size=self.config['gpu_size'], vis_size = self.config['vis_size']))
                        error_title = "LOAD ERROR"
                        error_text = 'This session was saved with a different level of downsampling. This means the mask could not be loaded.'
                        self.displayFileErrorDialog(message=error_text, title=error_title)
                        #return #Exits the LoadSession function

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

            self.points = self.config['points']
            self.rdvc_widgets['run_points_spinbox'].setValue(self.points)

            #self.run_folder = self.config['run_folder']

        else:
            self.subvolume_points = None 
            # set default to 10000 instead of minimum
            # value = self.rdvc_widgets['subvol_points_spinbox'].minimum()
            value = 10000
            self.rdvc_widgets['subvol_points_spinbox'].setValue(value)

            self.points = None
            self.rdvc_widgets['run_points_spinbox'].setValue(self.rdvc_widgets['run_points_spinbox'].minimum())

            #self.run_folder = [None]
            #self.rdvc_widgets['dir_name_label'].setText("")

        if 'results_folder' in self.config:
            self.results_folder = self.config['results_folder']
            if(self.config['results_open']):
                #print("results open")
                if (hasattr(self, 'graph_window')):
                    plt.close('all') #closes all open figures
                    self.graph_window.close()
                self.CreateGraphsWindow()
        else:
            self.results_folder = None
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
                        mask_files.append(_file)
            self.mask_parameters['masksList'].addItems(mask_files)
            self.mask_parameters['masksList'].setEnabled(True)
            self.mask_parameters['masksList'].setCurrentText("latest_selection.mha")
            
        else:
            self.mask_parameters['masksList'].setEnabled(False)
            self.mask_parameters['loadButton'].setEnabled(False)   


        results_directory = os.path.join(tempfile.tempdir, "Results")
        
        for i in range(self.result_widgets['run_entry'].count()):
            self.result_widgets['run_entry'].removeItem(i)

        for folder in glob.glob(os.path.join(results_directory,"*")):
            if os.path.isdir(folder):
                self.result_widgets['run_entry'].addItem(os.path.basename(folder))

        self.reg_load = False
        if 'point0' in self.config:
            if self.config['point0']:
                self.reg_load = True

        #PC panel:

        pc = self.pointcloud_parameters

        if 'pc_subvol_rad' in  self.config:

            pc['pointcloud_size_entry'].setText(str(self.config['pc_subvol_rad']))
            pc['pointcloud_volume_shape_entry'].setCurrentIndex(self.config['pc_subvol_shape'])
            pc['pointcloud_dimensionality_entry'].setCurrentIndex(self.config['pc_dim'])
            pc['pointcloud_overlap_x_entry'].setValue(self.config['pc_overlapx'])
            pc['pointcloud_overlap_y_entry'].setValue(self.config['pc_overlapy'])
            pc['pointcloud_overlap_z_entry'].setValue(self.config['pc_overlapz'])
            pc['pointcloud_rotation_x_entry'].setText(str(self.config['pc_rotx']))
            pc['pointcloud_rotation_y_entry'].setText(str(self.config['pc_roty']))
            pc['pointcloud_rotation_z_entry'].setText(str(self.config['pc_rotz']))

        #bring image loading panel to front if it isnt already:        
        self.select_image_dock.raise_()

    def warningDialog(self, message='', window_title='', detailed_text=''):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Information)
        dialog.setText(message)
        dialog.setWindowTitle(window_title)
        dialog.setDetailedText(detailed_text)
        dialog.setStandardButtons(QMessageBox.Ok)
        retval = dialog.exec_()
        return retval

# Loading and Error windows:
    def progress(self, value):
        # print("progress emitted", value)
        if int(value) == 0:
            value = 1
        self.progress_window.setValue(value)
        



        
