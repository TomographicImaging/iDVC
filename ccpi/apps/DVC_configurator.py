"""
DataExplorer

UI to configure a DVC run

Usage:
 DataExplorer.py [ -h ] [ -i <path> ] [ --subvol=10 ]

Options:
 -i path            input filename
 --subvol=n         the max size of the subvolume in voxel
 -h       display help

Example:
    DVC_Configurator -i ..\..\..\CCPi-Simpleflex\data\head.mha
"""

import sys
from PyQt5 import QtCore
from PyQt5 import QtGui
#from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QDockWidget
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QFormLayout
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QLineEdit, QSpinBox
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QProgressBar, QStatusBar
import vtk
from ccpi.viewer.QVTKCILViewer import QVTKCILViewer
from ccpi.viewer.QVTKWidget import QVTKWidget
from ccpi.viewer.utils import Converter
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XZ
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_YZ
from ccpi.viewer.utils import cilRegularPointCloudToPolyData
from ccpi.viewer.utils import cilMaskPolyData, cilClipPolyDataBetweenPlanes
from ccpi.viewer.utils import cilNumpyMETAImageWriter
from ccpi.viewer.QtThreading import Worker, WorkerSignals, ErrorObserver#, \
                                    #QtThreadedProgressBarInterface

from ccpi.dvc import dvcw as dvc
from ccpi.dvc import DVC
from natsort import natsorted
import imghdr
import os
import csv
from functools import reduce
from numbers import Number
from docopt import docopt
import tempfile
import json
import numpy



# Import linking class to join 2D and 3D viewers
import ccpi.viewer.viewerLinker as vlink
from ccpi.viewer.CILViewer import CILViewer
from ccpi.viewer.CILViewer2D import CILViewer2D

from vtk.util.vtkAlgorithm import VTKPythonAlgorithmBase

from ccpi.apps import vtkutils





class cilNumpyPointCloudToPolyData(VTKPythonAlgorithmBase):
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
        if not isinstance (value) == numpy.ndarray :
            raise ValueError('Data must be a numpy array. Got', value)

        if value != self.__Data:
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




def sentenceCase(string):
    if string:
        first_word = string.split()[0]
        world_len = len(first_word)

        return first_word.capitalize() + string[world_len:]

    else:
        return ''


class QtThreadedProgressBarInterface(object):
    def updateProgressBar(self, value):
        """
        Set progress bar percentage.
        :param (int) value:
            Integer value between 0-100.
        """

        self.progressBar.setValue(value)

    def completeProgressBar(self):
        """
        Set the progress bar to 100% complete and hide
        """
        self.progressBar.setValue(100)
        self.progressBar.hide()

    def showProgressBar(self):
        """
        Set the progress bar to 0% complete and show
        """
        self.progressBar.setValue(0)
        self.progressBar.show()


class Window(QMainWindow, QtThreadedProgressBarInterface):

    def __init__(self):
        super(Window, self).__init__()
        self.setWindowTitle('DVC Configurator')
        self.setGeometry(50, 50, 1200, 600)

        self.e = ErrorObserver()





        self.frame = QFrame()
        self.vl = QVBoxLayout()

        # CILViewer2D is the central widget
        self.vtkWidget = QVTKWidget(
                viewer=CILViewer2D,
                interactorStyle=vlink.Linked2DInteractorStyle
                )
        self.vtkWidget.viewer.debug = False
        self.vtkWidget.viewer.style.debug = True
        
        self.iren = self.vtkWidget.getInteractor()
        self.vl.addWidget(self.vtkWidget)

        self.frame.setLayout(self.vl)
        self.setCentralWidget(self.frame)

        # create the various panels in the order one should execute them
        self.createDock3DWidget()
        self.createRegistrationWidget()
        self.createMaskWidget()
        self.createPointCloudWidget()        
        self.createRangeWidget()
        self.createRunConfigurationWidget()
        self.toolbar()


        # show/hide panels
        for panel in self.panels:
            if panel[0].isChecked():
                panel[1].show()
            else:
                panel[1].hide()


        # add observer to viewer events
        self.vtkWidget.viewer.style.AddObserver("MouseWheelForwardEvent",
                                                self.UpdateClippingPlanes, 1.9)
        self.vtkWidget.viewer.style.AddObserver("MouseWheelBackwardEvent",
                                                self.UpdateClippingPlanes, 1.9)
        #self.vtkWidget.viewer.style.AddObserver('LeftButtonReleaseEvent',
        #                                        self.OnLeftButtonReleaseEvent, 0.5)
        #self.vtkWidget.viewer.style.AddObserver('KeyPressEvent',
        #                                        self.OnKeyPressEvent, 0.5)

        # self.toolbar()

        # self.createTableWidget()

        #Create status bar
        self.statusbar = QStatusBar(self)
        self.setStatusTip('Open file to begin visualisation...')
        self.setStatusBar(self.statusbar)
        
        self.setStatusTip('Open file to begin visualisation...')
        
        # Add progress bar
        # self.progressBar = QProgressBar(self)
        # initialize the progress bar interface
        self.progressbar = QProgressBar(self)
        self.progressBar = self.progressbar
        
        self.progressBar.setMaximumWidth(250)
        self.progressBar.hide()
        self.statusbar.addPermanentWidget(self.progressBar)

        self.subvol = 80
        self.displaySpheres = True

        # self.pointcloud = []
        self.start_selection = True
        self.pointCloudCreated = False
        # Add threading
        self.threadpool = QtCore.QThreadPool()
        self.e = ErrorObserver()


        self.show()
        
        
    def setApp(self, App):
        self.App = App

    def createDock3DWidget(self):
        # Add the 3D viewer widget
        self.viewer3DWidget = QVTKWidget(
                viewer=CILViewer,
                interactorStyle=vlink.Linked3DInteractorStyle
                )
        self.viewer3DWidget.viewer.debug = False

        self.Dock3DContents = QWidget()
        self.Dock3DContents.setStyleSheet("background-color: rgb(25,51,101)")
        f_layout3D = QFormLayout(self.Dock3DContents)

        self.Dock3D = QDockWidget(self)
        self.Dock3D.setMinimumWidth(300)
        self.Dock3D.setWindowTitle("3D View")
        self.Dock3D.setFeatures(
                QDockWidget.DockWidgetFloatable |
                QDockWidget.DockWidgetMovable)

        f_layout3D.addWidget(self.viewer3DWidget)
        self.Dock3D.setWidget(self.Dock3DContents)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.Dock3D)
        # Initially link viewers
        self.link2D3D = vlink.ViewerLinker(self.vtkWidget.viewer,
                                           self.viewer3DWidget.viewer)
        self.link2D3D.setLinkPan(False)
        self.link2D3D.setLinkZoom(False)
        self.link2D3D.setLinkWindowLevel(True)
        self.link2D3D.setLinkSlice(True)
        self.link2D3D.enable()


    def setup2DPointCloudPipeline(self):
        bpcpoints = cilClipPolyDataBetweenPlanes()
        # save reference
        self.bpcpoints = bpcpoints
        polydata_masker = self.polydata_masker
        bpcpoints.SetInputConnection(polydata_masker.GetOutputPort())
        bpcpoints.SetPlaneOriginAbove((0,0,3))
        bpcpoints.SetPlaneOriginBelow((0,0,1))
        bpcpoints.SetPlaneNormalAbove((0,0,1))
        bpcpoints.SetPlaneNormalBelow((0,0,-1))
        # bpcpoints.Update()

        mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.pointmapper = mapper
        # mapper.SetInputConnection(bpc.GetOutputPort())
        # mapper.SetInputConnection(polydata_masker.GetOutputPort())
        # mapper.SetInputConnection(pointCloud.GetOutputPort())
        mapper.SetInputConnection(bpcpoints.GetOutputPort())

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
        # save reference
        self.cubesphere = subv_glyph
        subv_glyph.SetScaleFactor(1.)

        
        spacing = self.vtkWidget.viewer.img3D.GetSpacing()
        pointCloud = self.pointCloud
        radius = pointCloud.GetSubVolumeRadiusInVoxel()

        # Spheres may be a bit complex to visualise if the spacing of the image is not homogeneous
        sphere_source = vtk.vtkSphereSource()
        # save reference
        self.sphere_source = sphere_source
        sphere_source.SetRadius(radius * spacing[0])
        sphere_source.SetThetaResolution(12)
        sphere_source.SetPhiResolution(12)

        # Cube source
        cube_source = vtk.vtkCubeSource()
        # save reference
        self.cube_source = cube_source
        cube_source.SetXLength(spacing[0]*radius*2)
        cube_source.SetYLength(spacing[1]*radius*2)
        cube_source.SetZLength(spacing[2]*radius*2)
        
        

        # clip between planes
        bpcvolume = cilClipPolyDataBetweenPlanes()
        # save reference
        self.bpcvolume = bpcvolume
        bpcvolume.SetInputConnection(subv_glyph.GetOutputPort())
        bpcvolume.SetPlaneOriginAbove((0,0,3))
        bpcvolume.SetPlaneOriginBelow((0,0,1))
        bpcvolume.SetPlaneNormalAbove((0,0,1))
        bpcvolume.SetPlaneNormalBelow((0,0,-1))

        # bpcvolume.Update()


        # mapper for the glyphs
        sphere_mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.cubesphere_mapper = sphere_mapper
        # sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )
        sphere_mapper.SetInputConnection( bpcvolume.GetOutputPort() )

        subv_glyph.SetInputConnection( polydata_masker.GetOutputPort() )


        if self.subvolumeShapeValue.currentIndex() == 0 or \
           self.subvolumeShapeValue.currentIndex() == 2:
            self.glyph_source = cube_source
        else:
            self.glyph_source = sphere_source
        
        subv_glyph.SetSourceConnection( self.glyph_source.GetOutputPort() )
        
        # subv_glyph.SetSourceConnection( sphere_source.GetOutputPort() )
        # subv_glyph.SetSourceConnection( cube_source.GetOutputPort() )

        subv_glyph.SetVectorModeToUseNormal()

        # actor for the glyphs
        sphere_actor = vtk.vtkActor()
        # save reference
        self.cubesphere_actor = sphere_actor
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1, 0, 0)
        #sphere_actor.GetProperty().SetOpacity(0.2)
        sphere_actor.GetProperty().SetRepresentationToWireframe()

        self.vtkWidget.viewer.getRenderer().AddActor(actor)
        self.vtkWidget.viewer.getRenderer().AddActor(sphere_actor)
    def setup3DPointCloudPipeline(self):
        polydata_masker = self.polydata_masker

        mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.pointmapper = mapper
        # mapper.SetInputConnection(bpc.GetOutputPort())
        # mapper.SetInputConnection(polydata_masker.GetOutputPort())
        # mapper.SetInputConnection(pointCloud.GetOutputPort())
        mapper.SetInputConnection(polydata_masker.GetOutputPort())

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

        # Spheres may be a bit complex to visualise if the spacing of the image is not homogeneous
        # get reference
        sphere_source = self.sphere_source

        # get reference
        cube_source = self.cube_source

        # mapper for the glyphs
        sphere_mapper = vtk.vtkPolyDataMapper()
        # save reference
        self.cubesphere_mapper3D = sphere_mapper
        sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )

        subv_glyph.SetInputConnection( polydata_masker.GetOutputPort() )
        if self.subvolumeShapeValue.currentIndex() == 0 or \
           self.subvolumeShapeValue.currentIndex() == 2:
            subv_glyph.SetSourceConnection( cube_source.GetOutputPort() )
        else:
            subv_glyph.SetSourceConnection( sphere_source.GetOutputPort() )
        subv_glyph.Modified()

        # actor for the glyphs
        sphere_actor = vtk.vtkActor()
        # save reference
        self.cubesphere_actor3D = sphere_actor
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1, 0, 0)
        sphere_actor.GetProperty().SetOpacity(0.2)
        # sphere_actor.GetProperty().SetRepresentationToWireframe()

        self.viewer3DWidget.viewer.getRenderer().AddActor(actor)
        self.viewer3DWidget.viewer.getRenderer().AddActor(sphere_actor)

    def setupPointCloudPipelineOld(self):
        self.vtkPointCloud = vtk.vtkPoints()
        self.pointActor = vtk.vtkActor()
        self.vertexActor = vtk.vtkActor()
        self.selectActor = vtk.vtkLODActor()
        self.vertices = vtk.vtkCellArray()
        self.pointActorsAdded = False
        self.pointPolyData = vtk.vtkPolyData()
        self.visPlane = [ vtk.vtkPlane() , vtk.vtkPlane() ]
        self.planeClipper =  [ vtk.vtkClipPolyData() , vtk.vtkClipPolyData() ]

        self.pointMapper = vtk.vtkPolyDataMapper()

        self.glyph3D = vtk.vtkGlyph3D()
        self.sphereMapper = vtk.vtkPolyDataMapper()
        self.sphereActor = vtk.vtkActor()

        self.selectMapper = vtk.vtkPolyDataMapper()
        return False

    def toolbar(self):
        # openAction = QAction("Open", self)
        # openAction.setShortcut("Ctrl+O")
        # openAction.triggered.connect(lambda: self.openFile('reference'))

        closeAction = QAction("Close", self)
        closeAction.setShortcut("Ctrl+Q")
        closeAction.triggered.connect(self.close)

        # tableAction = QAction("Point Cloud Setup", self)
        # tableAction.setShortcut("Ctrl+T")
        # tableAction.triggered.connect(self.showPointCloudWidget)

        # define actions
        # load data reference
        openAction = QAction(self.style().standardIcon(
            QStyle.SP_DirOpenIcon), 'Open Reference Volume', self)
        openAction.triggered.connect(lambda: self.openFile('reference'))
        # load data correlate
        openActionCorrelate = QAction(self.style().standardIcon(
            QStyle.SP_DirOpenIcon), 'Open Correlate Volume', self)
        openActionCorrelate.triggered.connect(lambda: self.openFile('correlate'))
        # define load mask
        openMask = QAction(self.style().standardIcon(
            QStyle.SP_FileDialogStart), 'Open Mask Data', self)
        openMask.triggered.connect(self.openMask)
        # define load PointCloud
        # openPointCloud = QAction(self.style().standardIcon(
        #    QStyle.SP_DirOpenIcon), 'Open Point Cloud', self)
        #openPointCloud.triggered.connect(self.openPointCloud)

        # define save mask
        saveMask = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton), 'Save Mask Data', self)
        saveMask.triggered.connect(self.saveMask)
        # define save dataset voi
        saveVOI = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton), 'Save Volume of Interest', self)
        saveVOI.triggered.connect(self.saveVOI)

        saveAction = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton), 'Save current render as PNG', self)
        saveAction.triggered.connect(self.saveFileRender)

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('File')
        fileMenu.addAction(openAction)
        fileMenu.addAction(openActionCorrelate)
        fileMenu.addAction(openMask)

        fileMenu.addAction(saveMask)
        fileMenu.addAction(saveVOI)
        # fileMenu.addAction(savePointCloud)

        fileMenu.addAction(closeAction)
        # fileMenu.addAction(tableAction)

        panels = []

        self.show3D = QAction("Show 3D View", self)
        self.show3D.setCheckable(True)
        self.show3D.setChecked(False)
        self.show3D.setEnabled(False)
        # self.show3D.setShortcut("Ctrl+T")
        self.show3D.triggered.connect(self.showHide3D)

        self.showRegistrationPanel = QAction("1 - Manual Registration Panel", self)
        self.showRegistrationPanel.setCheckable(True)
        self.showRegistrationPanel.setChecked(False)
        self.showRegistrationPanel.setEnabled(False)
        self.showRegistrationPanel.triggered.connect(
                lambda: self.registration_panel[0].show() \
                   if self.showRegistrationPanel.isChecked() else \
                       self.registration_panel[0].hide()
                )

        
        self.showMaskConfigurator = QAction("2 - Configure Mask Panel", self)
        self.showMaskConfigurator.setCheckable(True)
        self.showMaskConfigurator.setChecked(False)
        self.showMaskConfigurator.setEnabled(False)
        self.showMaskConfigurator.triggered.connect(
                lambda: self.mask_panel[0].show() \
                   if self.showMaskConfigurator.isChecked() else \
                       self.mask_panel[0].hide()
                )
        

        self.showPointCloudConfigurator = QAction("3 - Configure Point Cloud Panel", self)
        self.showPointCloudConfigurator.setCheckable(True)
        self.showPointCloudConfigurator.setChecked(False)
        self.showPointCloudConfigurator.setEnabled(False)
        self.showPointCloudConfigurator.triggered.connect(
                lambda: self.pointCloudDockWidget.show() \
                   if self.showPointCloudConfigurator.isChecked() else \
                       self.pointCloudDockWidget.hide()
                )

        self.showRangesConfigurator = QAction("4 - Configure Ranges Panel", self)
        self.showRangesConfigurator.setCheckable(True)
        self.showRangesConfigurator.setChecked(False)
        self.showRangesConfigurator.setEnabled(False)
        self.showRangesConfigurator.triggered.connect(
                lambda: self.range_panel[0].show() \
                   if self.showRangesConfigurator.isChecked() else \
                       self.range_panel[0].hide()
                )

        self.showRunConfigurator = QAction("5 - Configure Run Panel", self)
        self.showRunConfigurator.setCheckable(True)
        self.showRunConfigurator.setChecked(False)
        self.showRunConfigurator.setEnabled(False)
        self.showRunConfigurator.triggered.connect(
                lambda: self.runconf_panel[0].show() \
                   if self.showRunConfigurator.isChecked() else \
                       self.runconf_panel[0].hide()
                )


        #popupMenu = self.createPopupMenu()

        # viewMenu = mainMenu.addMenu('Panels')
        # viewMenu.addAction(self.show3D)
        # viewMenu.addAction(self.showMaskConfigurator)
        # viewMenu.addAction(self.showPointCloudConfigurator)
        # viewMenu.addAction(self.showRangesConfigurator)

        panels.append((self.show3D, self.Dock3D))
        panels.append((self.showPointCloudConfigurator, self.pointCloudDockWidget))
        panels.append((self.showMaskConfigurator, self.mask_panel[0] ))
        panels.append((self.showRangesConfigurator, self.range_panel[0]))
        panels.append((self.showRegistrationPanel, self.registration_panel[0]))
        panels.append((self.showRunConfigurator, self.runconf_panel[0]))
        
        self.panels = panels

        # Initialise the toolbar
        self.toolbar = self.addToolBar('Viewer tools')



        # Add actions to toolbar
        #self.toolbar.addAction(openAction)
        #self.toolbar.addAction(openActionCorrelate)
        #self.toolbar.addAction(saveAction)
        self.toolbar.addAction(self.show3D)
        self.toolbar.addAction(self.showRegistrationPanel)
        self.toolbar.addAction(self.showMaskConfigurator)
        self.toolbar.addAction(self.showPointCloudConfigurator)
        self.toolbar.addAction(self.showRangesConfigurator)
        self.toolbar.addAction(self.showRunConfigurator)
        
        



    def showHide3D(self):
        if self.show3D.isChecked():
            self.Dock3D.show()
        else:
            self.Dock3D.hide()
       

    def openFile(self, dataset='reference'):
        fn = QFileDialog.getOpenFileNames(self, 'Open File')

        # If the user has pressed cancel, the first element of the tuple will be empty.
        # Quit the method cleanly
        if not fn[0]:
            return
        if not dataset:
            raise ValueError('dataset is False')
        print ("doSomething", fn, dataset)
        self.showProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(0)
        self.progressBar.setValue(0)
        
        self.openFileByPath(fn, dataset)

        if dataset == 'reference':
            rp = self.registration_parameters
            self.show3D.setEnabled(True)
        elif dataset == 'correlate':
            self.showRegistrationPanel.setEnabled(True)
            rp = self.registration_parameters
            rp['start_registration_button'].setEnabled(True)
            rp['register_on_selection_check'].setEnabled(True)
            

#        worker = Worker(self.openFileByPath, fn=fn, read_mask=read_mask)
#        
#        # Progress bar signal handling
#        worker.signals.result.connect(self.getResult)
#        worker.signals.finished.connect(self.completeProgressBar)
#        worker.signals.progress.connect(self.updateProgressBar)
#        # self.openFileByPath(fn, read_mask)
#        print ("doSomething start Worker")
#        self.progressBar.show()
#        self.threadpool.start(worker)

    def getResult(self, result):
        out = result[0]
        args = result[1]
        kwargs = result[2]
        print (**kwargs)
        
    def openMask(self):
        print("openMask")
        v = self.vtkWidget.viewer
        if not isinstance(v.img3D, vtk.vtkImageData):
            return self.warningDialog(window_title="Error", 
                               message="Load a dataset on the viewer first" )
            
        
        self.openFile('mask')
        v = self.vtkWidget.viewer
        # save the mask to a temporary file
        writer = vtk.vtkMetaImageWriter()
        tmpdir = tempfile.gettempdir()
        writer.SetFileName(os.path.join(tmpdir, "selection.mha"))
        writer.SetInputConnection(self.mask_reader.GetOutputPort())
        writer.Write()
        self.mask_reader = vtk.vtkMetaImageReader()
        self.mask_reader.SetFileName(os.path.join(tmpdir, "selection.mha"))
        self.mask_reader.Update()
        
        dims = v.img3D.GetDimensions()
        if not dims == self.mask_reader.GetOutput().GetDimensions():
            return self.warningDialog( 
                    window_title="Error", 
                    message="Mask and Dataset are not compatible",
                    detailed_text='Dataset dimensions {}\nMask dimensions {}'\
                           .format(dims, 
                                   self.mask_reader.GetOutput().GetDimensions()
                                   ))
            
        v.setInputData2(self.mask_reader.GetOutput())
        

    def openFileByPath(self, fn, dataset='reference', progress_callback=None):
        '''Reads dataset from file

        :param dataset: can be 'reference' , 'correlate' or 'mask'
        '''
        if dataset not in ['reference' , 'correlate' ,'mask']:
            return self.warningDialog(
                message='Load dataset can be done only for Reference, Correlate and Mask image.\nGot {}'.format(dataset),
                    window_title='Load Error')
        print ("Worker")
        print (type(self))
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(0)
        self.progressBar.setValue(0)
        
        # Single file selection
        if len(fn[0]) == 1:
            file = fn[0][0]

            if imghdr.what(file) == None:
                if file.split(".")[1] == 'mha' or\
                        file.split(".")[1] == 'mhd':
                    reader = vtk.vtkMetaImageReader()
                    reader.AddObserver("ErrorEvent", self.e)
                    reader.SetFileName(file)
                    if dataset != 'correlate':
                        reader.Update()
                        print("update reader")
                elif file.split(".")[1] == 'csv':
                    self.pointcloud = []
                    self.loadPointCloudFromCSV(file)
                    return
            else:
                return
        # Multiple TIFF files selected
        else:
            # Make sure that the files are sorted 0 - end
            filenames = natsorted(fn[0])

            # Basic test for tiff images
            for file in filenames:
                ftype = imghdr.what(file)
                if ftype != 'tiff':
                    # A non-TIFF file has been loaded, present error message and exit method
                    self.e(
                        '', '', 'When reading multiple files, all files must TIFF formatted.')
                    file = file
                    self.displayFileErrorDialog(file)
                    return

            # Have passed basic test, can attempt to load
            #numpy_image = Converter.tiffStack2numpyEnforceBounds(filenames=filenames)
            #reader = Converter.numpy2vtkImporter(numpy_image)
            # reader.Update()
            reader = vtk.vtkTIFFReader()
            sa = vtk.vtkStringArray()
            #i = 0
            # while (i < 1054):
            for fname in filenames:
                #fname = os.path.join(directory,"8bit-1%04d.tif" % i)
                i = sa.InsertNextValue(fname)

            print("read {} files".format(i))

            reader.SetFileNames(sa)
            if dataset != 'correlate':
                print("update reader")
                reader.Update()

        dtype = vtk.VTK_UNSIGNED_CHAR
        # deactivate this path
        if reader.GetOutput().GetScalarType() != dtype and False:
            # need to cast to 8 bits unsigned

            stats = vtk.vtkImageAccumulate()
            stats.SetInputConnection(reader.GetOutputPort())
            stats.Update()
            iMin = stats.GetMin()[0]
            iMax = stats.GetMax()[0]
            if (iMax - iMin == 0):
                scale = 1
            else:
                scale = vtk.VTK_UNSIGNED_CHAR_MAX / (iMax - iMin)

            shiftScaler = vtk.vtkImageShiftScale()
            shiftScaler.SetInputConnection(reader.GetOutputPort())
            shiftScaler.SetScale(scale)
            shiftScaler.SetShift(-iMin)
            shiftScaler.SetOutputScalarType(dtype)
            shiftScaler.Update()

            tmpdir = tempfile.gettempdir()
            writer = vtk.vtkMetaImageWriter()
            writer.SetInputConnection(shiftScaler.GetOutputPort())
            writer.SetFileName(os.path.join(tmpdir, 'input8bit.mhd'))
            writer.Write()

            reader = shiftScaler
        if self.e.ErrorOccurred():
            self.displayFileErrorDialog(file)

        else:
            if dataset == 'mask':
                self.mask_reader = reader
            elif dataset == 'reference':
                self.reader = reader
            else:
                self.correlate_reader = reader 
#            self.vtkWidget.viewer.setInput3DData(reader.GetOutput())
#            self.viewer3DWidget.viewer.setInput3DData(self.vtkWidget.viewer.img3D)
#            self.viewer3DWidget.viewer.sliceActor.GetProperty().SetOpacity(0.99)
        
        self.setStatusTip('Ready')
        if dataset == 'reference':
            self.vtkWidget.viewer.setInput3DData(self.reader.GetOutput())
            self.viewer3DWidget.viewer.setInput3DData(self.vtkWidget.viewer.img3D)
            self.viewer3DWidget.viewer.sliceActor.GetProperty().SetOpacity(0.99)
        
        self.progressBar.setMaximum(100)
        

    def openPointCloud(self):
        fn = QFileDialog.getOpenFileNames(self, 'Open File')

        # If the user has pressed cancel, the first element of the tuple will be empty.
        # Quit the method cleanly
        if not fn[0]:
            return
        points = numpy.loadtxt(fn)
        # save reference
        self.polydata_masker = cilNumpyPointCloudToPolyData()
        self.polydata_masker.SetData(points)
        self.polydata_masker.Update()

    def savePointCloud(self):
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)

        fn = dialog.getSaveFileName(self, 'Save As', '.', "CSV files (*.csv)|*.csv|XML files (*.xml)|*.xml")

        # Only save if the user has selected a name
        if fn[0]:
            # get the points

            pointcloud = self.polydata_masker.GetOutputDataObject(0)
            array = numpy.zeros((pointcloud.GetNumberOfPoints(), 4))
            for i in range(pointcloud.GetNumberOfPoints()):
                pp = pointcloud.GetPoint(i)
                array[i] = (i, *pp)
            numpy.savetxt(fn[0], array, '%d\t%.3f\t%.3f\t%.3f', delimiter=';')

    def saveFileRender(self):
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)

        fn = dialog.getSaveFileName(self, 'Save As', '.', "Images (*.png)")

        # Only save if the user has selected a name
        if fn[0]:
            self.vtkWidget.viewer.saveRender(fn[0])

    def saveMask(self):
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)

        fn = dialog.getSaveFileName(self, 'Save Mask As', '.', "Meta Image (.mhd)")

        # Only save if the user has selected a name
        if fn[0]:
            print ("Well done, ", fn)
            v = self.vtkWidget.viewer
            writer = vtk.vtkMetaImageWriter()
            writer.SetInputData(v.image2)
            writer.SetFileName(fn[0])
            writer.Write()
    def saveVOI(self):
        v = self.vtkWidget.viewer
        if v.getROI() == ():
            return self.warningDialog(window_title='Error', 
                               message='Select a Volume of Interest')
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)

        fn = dialog.getSaveFileName(self, 'Save Mask As', '.', "Meta Image (.mhd)")

        # Only save if the user has selected a name
        if fn[0]:
            print ("extract VOI, ", fn)
            
            extent = v.getROIExtent()
            voi = vtk.vtkExtractVOI()
            voi.SetVOI(*extent)
            voi.SetInputData(v.img3D)
            voi.Update()
            print ("save VOI, ", fn)
            writer = vtk.vtkMetaImageWriter()
            writer.SetInputConnection(voi.GetOutputPort())
            writer.SetFileName(fn[0])
            writer.Write()    
        
    def displayFileErrorDialog(self, file):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("READ ERROR")
        msg.setText("Error reading file: ({filename})".format(filename=file))
        msg.setDetailedText(self.e.ErrorMessage())
        msg.exec_()

    def close(self):
        self.App.quit()

    def loadPointCloudFromCSV(self, filename):
        print("loadPointCloudFromCSV")
        with open(filename, 'r') as csvfile:
            read = csv.reader(csvfile)

            for row in read:
                # read in only numerical values
                # print (row)
                try:
                    row = list(map(lambda x: float(x), row))
                # print ("reduce " , reduce( lambda x,y: isinstance(x,Number) and \
                #          isinstance(y,Number) , row))
                # if reduce( lambda x,y: isinstance(x,Number) and \
                #          isinstance(y,Number) , row):
                    self.pointcloud.append(row)
                except ValueError as ve:
                    print(ve)

            print(self.pointcloud)

            # load data in the QTableWidget
            self.loadIntoTableWidget(self.pointcloud)
            self.renderPointCloud()



    def UpdateClippingPlanes(self, interactor, event):
        try:
            normal = [0, 0, 0]
            origin = [0, 0, 0]
            norm = 1
            v = self.vtkWidget.viewer
            bpcpoints = self.bpcpoints
            bpcvolume = self.bpcvolume
            orientation = v.GetSliceOrientation()
            if orientation == SLICE_ORIENTATION_XY:
                norm = 1
            elif orientation == SLICE_ORIENTATION_XZ:
                norm = -1
            elif orientation == SLICE_ORIENTATION_YZ:
                norm = 1
            beta = 0
            if event == "MouseWheelForwardEvent":
                # this is pretty absurd but it seems the
                # plane cuts too much in Forward...
                beta =+ 2

            spac = v.img3D.GetSpacing()
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
            self.viewer3DWidget.viewer.sliceActor.GetProperty().SetOpacity(0.8)
            # print (">>>>>>>>>>>>>>>>>>>>>")
        except AttributeError as ae:
            print (ae)
            print ("Probably Point Cloud not yet created")

    def setSubvolSize(self, subvolume):
        self.subvol = subvolume
        try:
            self.isoValueEntry.setText(str(subvolume))
        except AttributeError as ae:
            pass

    def dislayPointCloudAsSpheres(self, should):
        self.displaySpheres = should

    def editPointCloud(self):
        self.tableDock.show()
    def showPointCloudWidget(self):
        self.pcDock.show()

    def createTableWidget(self):
        self.tableDock = QDockWidget(self)
        self.tableWindow = QMainWindow()
        self.tableWidget = QTableWidget()
        self.tableWindow.setCentralWidget(self.tableWidget)
        self.tableDock.setMinimumWidth(300)
        self.tableDock.setWidget(self.tableWindow)
        self.tableDock.setWindowTitle("Edit Point Cloud")

        sphereAction = QAction("Toggle Sphere visualisation", self)
        sphereAction.setShortcut("Ctrl+S")
        sphereAction.setCheckable(True)
        sphereAction.setChecked(False)
        sphereAction.triggered.connect(
            self.dislayPointCloudAsSpheres, sphereAction.isChecked())

        self.interactiveEdit = QAction("Interactive Edit of Point Cloud", self)
        self.interactiveEdit.setCheckable(True)
        self.interactiveEdit.setChecked(True)

        tableAction = QAction("Update Point Cloud", self)
        tableAction.setShortcut("Ctrl+T")
        tableAction.triggered.connect(self.updatePointCloud)

        mainMenu = self.tableWindow.menuBar()
        fileMenu = mainMenu.addMenu('Edit')
        fileMenu.addAction(self.interactiveEdit)

        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.tableDock)

        self.tableDock.show()

    def generateUIDockParameters(self, title):
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

    def createPointCloudWidget(self):
        self.treeWidgetInitialElements = []
        self.treeWidgetUpdateElements = []


        self.pointCloudDockWidget = QDockWidget(self)
        self.pointCloudDockWidget.setWindowTitle('3 - Point Cloud')
        self.pointCloudDockWidgetContents = QWidget()


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
        dockWidget.visibilityChanged.connect(lambda: self.showRangesConfigurator.setEnabled(True))


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
        self.dimensionalityValue.addItem("3D")
        self.dimensionalityValue.addItem("2D")
        self.dimensionalityValue.setCurrentIndex(1)
        self.dimensionalityValue.currentIndexChanged.connect(lambda: \
                    self.overlapZValueEntry.setEnabled(True) \
                    if self.dimensionalityValue.currentIndex() == 0 else \
                       self.overlapZValueEntry.setEnabled(False))
        self.treeWidgetUpdateElements.append(self.dimensionalityValue)
        self.treeWidgetUpdateElements.append(self.dimensionalityValue)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.dimensionalityValue)
        widgetno += 1
        pc['pointcloud_dimensionality_entry'] = self.dimensionalityValue



        # Add Log Tree field
        # Add Overlap X
        self.overlapXLabel = QLabel(self.graphParamsGroupBox)
        self.overlapXLabel.setText("Overlap X")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapXLabel)
        self.overlapXValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.overlapXValueEntry.setValidator(validator)
        self.overlapXValueEntry.setText("0.20")
        self.treeWidgetUpdateElements.append(self.overlapXValueEntry)
        self.treeWidgetUpdateElements.append(self.overlapXLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.overlapXValueEntry)
        widgetno += 1
        pc['pointcloud_overlap_x_entry'] = self.overlapXValueEntry
        # Add Overlap Y
        self.overlapYLabel = QLabel(self.graphParamsGroupBox)
        self.overlapYLabel.setText("Overlap Y")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapYLabel)
        self.overlapYValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.overlapYValueEntry.setValidator(validator)
        self.overlapYValueEntry.setText("0.20")
        self.treeWidgetUpdateElements.append(self.overlapYValueEntry)
        self.treeWidgetUpdateElements.append(self.overlapYLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.overlapYValueEntry)
        widgetno += 1
        pc['pointcloud_overlap_y_entry'] = self.overlapYValueEntry
        # Add Overlap Z
        self.overlapZLabel = QLabel(self.graphParamsGroupBox)
        self.overlapZLabel.setText("Overlap Z")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapZLabel)
        self.overlapZValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.overlapZValueEntry.setValidator(validator)
        self.overlapZValueEntry.setText("0.20")
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
        self.graphParamsSubmitButton.clicked.connect( self.createPointCloud )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.graphParamsSubmitButton)
        self.treeWidgetUpdateElements.append(self.graphParamsSubmitButton)
        widgetno += 1
        # Add elements to layout
        self.graphWidgetVL.addWidget(self.graphParamsGroupBox)
        self.graphDockVL.addWidget(self.dockWidget)
        self.pointCloudDockWidget.setWidget(self.pointCloudDockWidgetContents)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.pointCloudDockWidget)

        # Set update elements to disabled when first opening the window
        #if self.segmentor.dimensions is None:
        #    for element in self.treeWidgetUpdateElements:
        #        element.setEnabled(False)

        #self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.pcDock)

        # self.pointCloudDockWidget.show()

    def createMaskWidget(self):

        #self.treeWidgetInitialElements = []
        #self.treeWidgetUpdateElements = []

        self.mask_panel = self.generateUIDockParameters('2 - Mask')
        dockWidget = self.mask_panel[0]
        groupBox = self.mask_panel[5]
        groupBox.setTitle('Mask Parameters')
        formLayout = self.mask_panel[6]

        dockWidget.visibilityChanged.connect(lambda: self.showPointCloudConfigurator.setEnabled(True))

        # Create validation rule for text entry
        validator = QtGui.QDoubleValidator()
        validator.setDecimals(2)
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        mp = {}
        self.mask_parameters = mp
        # extend above field
        # self.extendAboveLabel = QLabel(groupBox)
        # self.extendAboveLabel.setText("Extend Above ")
        # formLayout.setWidget(widgetno, QFormLayout.LabelRole, self.extendAboveLabel)
        # self.extendAboveEntry= QLineEdit(groupBox)
        # self.extendAboveEntry.setValidator(validatorint)
        # self.extendAboveEntry.setText("10")
        # formLayout.setWidget(widgetno, QFormLayout.FieldRole, self.extendAboveEntry)
        mp['mask_extend_above_label'] = QLabel(groupBox)
        mp['mask_extend_above_label'].setText("Extend Above ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, mp['mask_extend_above_label'])
        mp['mask_extend_above_entry'] = QSpinBox(groupBox)
        mp['mask_extend_above_entry'].setSingleStep(1)
        mp['mask_extend_above_entry'].setValue(10)
        mp['mask_extend_above_entry'].setEnabled(True)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp['mask_extend_above_entry'])
        widgetno += 1
        # extend below field
        # self.extendBelowLabel = QLabel(groupBox)
        # self.extendBelowLabel.setText("Extend Below ")
        # formLayout.setWidget(widgetno, QFormLayout.LabelRole, self.extendBelowLabel)
        # self.extendBelowEntry= QLineEdit(groupBox)
        # self.extendBelowEntry.setValidator(validatorint)
        # self.extendBelowEntry.setText("10")
        # formLayout.setWidget(widgetno, QFormLayout.FieldRole, self.extendBelowEntry)
        # widgetno += 1
        mp['mask_extend_below_label'] = QLabel(groupBox)
        mp['mask_extend_below_label'].setText("Extend Above ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, mp['mask_extend_below_label'])
        mp['mask_extend_below_entry'] = QSpinBox(groupBox)
        mp['mask_extend_below_entry'].setSingleStep(1)
        mp['mask_extend_below_entry'].setValue(10)
        mp['mask_extend_below_entry'].setEnabled(True)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, mp['mask_extend_below_entry'])
        widgetno += 1



        # Add should extend checkbox
        self.extendMaskCheck = QCheckBox(groupBox)
        self.extendMaskCheck.setText("Extend mask")
        self.extendMaskCheck.setEnabled(False)

        formLayout.setWidget(widgetno,QFormLayout.FieldRole, self.extendMaskCheck)
        widgetno += 1

        # Add submit button
        submitButton = QPushButton(groupBox)
        submitButton.setText("Create Mask")
        submitButton.clicked.connect(self.extendMask)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, submitButton)
        widgetno += 1

        self.extendMaskCheck.stateChanged.connect(lambda: submitButton.setText("Extend Mask") \
                                                 if self.extendMaskCheck.isChecked() \
                                                 else submitButton.setText("Create Mask"))


        # Add elements to layout
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
    def createRangeWidget(self):
        '''create the multi run configuration dockable widget'''
        panel = self.generateUIDockParameters('4 - Ranges')
        self.range_panel = panel
        dockWidget = panel[0]
        groupBox = panel[5]
        groupBox.setTitle('Multi Run Configuration Parameters')
        formLayout = panel[6]
        
        dockWidget.visibilityChanged.connect(lambda: self.showRunConfigurator.setEnabled(True))


        # Create validation rule for text entry
        validator = QtGui.QDoubleValidator()
        validator.setDecimals(2)
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        
        ranges = {}
        
        self.ranges = ranges
        # radius range min
        ranges['radius_range_min_label'] = QLabel(groupBox)
        ranges['radius_range_min_label'].setText("Radius min ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['radius_range_min_label'])
        ranges['radius_range_min_value'] = QLineEdit(groupBox)
        ranges['radius_range_min_value'].setValidator(validatorint)
        
        current_radius = self.isoValueEntry.text()
        
        ranges['radius_range_min_value'].setText(current_radius)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['radius_range_min_value'])
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        # radius range max
        ranges['radius_range_max_label'] = QLabel(groupBox)
        ranges['radius_range_max_label'].setText("Radius max ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['radius_range_max_label'])
        ranges['radius_range_max_value'] = QLineEdit(groupBox)
        ranges['radius_range_max_value'].setValidator(validatorint)
        ranges['radius_range_max_value'].setText("10")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['radius_range_max_value'])
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        # radius range step
        ranges['radius_range_step_label'] = QLabel(groupBox)
        ranges['radius_range_step_label'].setText("Radius step ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['radius_range_step_label'])
        ranges['radius_range_step_value'] = QLineEdit(groupBox)
        ranges['radius_range_step_value'].setValidator(validatorint)
        ranges['radius_range_step_value'].setText("0")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['radius_range_step_value'])
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        
        separators = [QFrame(groupBox)]
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1
        
        # NUMBER OF POINTS IN SUBVOLUME min
        ranges['points_in_subvol_range_min_label'] = QLabel(groupBox)
        ranges['points_in_subvol_range_min_label'].setText("number of points in subvolume min ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['points_in_subvol_range_min_label'])
        ranges['points_in_subvol_range_min_value'] = QLineEdit(groupBox)
        ranges['points_in_subvol_range_min_value'].setValidator(validatorint)
        ranges['points_in_subvol_range_min_value'].setText("10")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['points_in_subvol_range_min_value'])
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        # overlap range max
        ranges['points_in_subvol_range_max_label'] = QLabel(groupBox)
        ranges['points_in_subvol_range_max_label'].setText("number of points in subvolume max ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['points_in_subvol_range_max_label'])
        ranges['points_in_subvol_range_max_value'] = QLineEdit(groupBox)
        ranges['points_in_subvol_range_max_value'].setValidator(validatorint)
        ranges['points_in_subvol_range_max_value'].setText("10")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['points_in_subvol_range_max_value'])
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        # overlap range step
        ranges['points_in_subvol_range_step_label'] = QLabel(groupBox)
        ranges['points_in_subvol_range_step_label'].setText("number of points in subvolume step ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['points_in_subvol_range_step_label'])
        ranges['points_in_subvol_range_step_value'] = QLineEdit(groupBox)
        ranges['points_in_subvol_range_step_value'].setValidator(validatorint)
        ranges['points_in_subvol_range_step_value'].setText("0")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['points_in_subvol_range_step_value'])
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        
        
        separators.append(QFrame(groupBox))
        separators[-1].setFrameShape(QFrame.HLine)
        separators[-1].setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separators[-1])
        widgetno += 1
        
        # Add submit button
        ranges['generate_button'] = QPushButton(groupBox)
        ranges['generate_button'].setText("Generate Multi-run DVC Config")
        ranges['generate_button'].clicked.connect(self.generateMultiRunDVCConfig)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, ranges['generate_button'])
        widgetno += 1

        # Add elements to layout
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
    
    def createRegistrationWidget(self):
        '''Create the Registration Dockable Widget'''

        #self.treeWidgetInitialElements = []
        #self.treeWidgetUpdateElements = []

        self.registration_panel = self.generateUIDockParameters('1 - Manual Registration')
        dockWidget = self.registration_panel[0]
        groupBox = self.registration_panel[5]
        groupBox.setTitle('Registration Parameters')
        formLayout = self.registration_panel[6]

        dockWidget.visibilityChanged.connect(lambda: self.showMaskConfigurator.setEnabled(True))

        # Create validation rule for text entry
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        rp = {}
        
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
        rp['register_on_selection_check'].setEnabled(True)
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
        rp['start_registration_button'].setEnabled(False)
        rp['start_registration_button'].clicked.connect(self.manualRegistration)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['start_registration_button'])
        widgetno += 1

        # rp['start_registration_button'].stateChanged.connect(lambda: rp['start_registration_button'].setText("Stop Registration") \
        #                                          if rp['start_registration_button'].isChecked() \
        #                                          else rp['start_registration_button'].setText("Start Registration"))


        # Add elements to layout
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
        # save to instance
        self.registration_parameters = rp

    def manualRegistration(self):
        rp = self.registration_parameters
        v = self.vtkWidget.viewer
        if rp['start_registration_button'].isChecked():
            print ("Start Registration Checked")
            rp['register_on_selection_check'].setEnabled(True)
            rp['start_registration_button'].setText("Stop Registration")

            # setup the appropriate stuff to run the registration
            print("translate")
            translate = vtk.vtkImageTranslateExtent()
            translate.SetTranslation(-1,1,2)
            
            if rp['register_on_selection_check'].isChecked():
                print ("Extracting selection")
                # get the selected ROI
                voi = vtk.vtkExtractVOI()
                voi.SetInputData(self.reader.GetOutput())
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
                
                print ("Reading image 2")
                self.correlate_reader.Update()
                print ("image 2", self.correlate_reader.GetOutput().GetDimensions())
                
                # copy the data to be registered if selection 
                voi.SetInputConnection(self.correlate_reader.GetOutputPort())
                print ("Extracting selection")
                voi.Update()
                data2 = vtk.vtkImageData()
                data2.DeepCopy(voi.GetOutput())
                translate.SetInputData(data2)
            
                print ("clearing memory")
                del voi
                fname = self.correlate_reader.GetFileName()
                print ("filename", fname, type(self.correlate_reader))
                cr = type(self.correlate_reader)()
                cr.SetFileName(fname)
                self.correlate_reader = cr
                print ("clearing memory done")

            else:
                print ("Registration on whole image")
                data1 = vtk.vtkImageData()
                data1.DeepCopy(self.reader.GetOutput())
                
                # data1 = self.reader.GetOutput()
                self.correlate_reader.Update()
                data2 = vtk.vtkImageData()
                data2.DeepCopy(self.correlate_reader.GetOutput())
                translate.SetInputData(data2)
                print ("clearing memory")
                fname = self.correlate_reader.GetFileName()
                print ("filename", fname, type(self.correlate_reader))
                cr = type(self.correlate_reader)()
                cr.SetFileName(fname)
                self.correlate_reader = cr
                print ("clearing memory done")

                #data2 = self.correlate_reader.GetOutput()
                #translate.SetInputConnection(self.correlate_reader.GetOutputPort())
                print ("Reading image 2")

            print ("Done")

            
            #voi = reader
            translate.Update()

            v.style.AddObserver('KeyPressEvent', self.OnKeyPressEventForRegistration, 0.5)

            # print ("out of the reader", reader.GetOutput())

            cast1 = vtk.vtkImageCast()
            cast2 = vtk.vtkImageCast()
            cast1.SetInputData(data1)
            cast1.SetOutputScalarTypeToFloat()
            cast2.SetInputConnection(translate.GetOutputPort())
            cast2.SetOutputScalarTypeToFloat()
            
            subtract = vtk.vtkImageMathematics()
            subtract.SetOperationToSubtract()
            subtract.SetInputConnection(1,cast1.GetOutputPort())
            subtract.SetInputConnection(0,cast2.GetOutputPort())
            
            subtract.Update()
            
            print ("subtract type", subtract.GetOutput().GetScalarTypeAsString(), subtract.GetOutput().GetDimensions())
            
            stats = vtk.vtkImageHistogramStatistics()
            stats.SetInputConnection(subtract.GetOutputPort())
            stats.Update()
            print ("stats ", stats.GetMinimum(), stats.GetMaximum(), stats.GetMean(), stats.GetMedian())

            v.setInputData(subtract.GetOutput())
            # trigger visualisation by programmatically click 'z'
            interactor = v.getInteractor()
            interactor.SetKeyCode("z")
            v.style.OnKeyPress(interactor, 'KeyPressEvent')
            #v.startRenderLoop()
            self.translate = translate
            self.subtract = subtract
            self.cast = [cast1, cast2]

        else:
            print ("Start Registration Unchecked")
            rp['start_registration_button'].setText("Start Registration")
            # hide registration box
            self.registration_box['actor'].VisibilityOff()
            v.setInput3DData(self.reader.GetOutput())
            v.style.UpdatePipeline()

    def OnKeyPressEventForRegistration(self, interactor, event):
        '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''
        print('OnKeyPressEventForRegistration', event)
        rp = self.registration_parameters
        if interactor.GetKeyCode() in ['j','n','b','m'] and \
            rp['start_registration_button'].isChecked():

            translate = self.translate
            v = self.vtkWidget.viewer
            subtract = self.subtract
            trans = list(translate.GetTranslation())
            orientation = v.style.GetSliceOrientation()
            ij = [0,1]
            if orientation == SLICE_ORIENTATION_XY:
                ij = [0,1]
            elif orientation == SLICE_ORIENTATION_XZ:
                ij = [0,2]
            elif orientation == SLICE_ORIENTATION_YZ:
                ij = [1,2]
            if interactor.GetKeyCode() == "j":
                trans[ij[1]] += 1
            elif interactor.GetKeyCode() == "n":
                trans[ij[1]] -= 1
            elif interactor.GetKeyCode() == "b":
                trans[ij[0]] -= 1
            elif interactor.GetKeyCode() == "m":
                trans[ij[0]] += 1
            translate.SetTranslation(*trans)
            translate.Update()
            subtract.Update()
            print ("Translation", trans)
            # update the current translation on the interface?
            rp = self.registration_parameters
            rp['translate_X_entry'].setText(str(trans[0]))
            rp['translate_Y_entry'].setText(str(trans[1]))
            rp['translate_Z_entry'].setText(str(trans[2]))
            v.setInputData(subtract.GetOutput())
            print ("OnKeyPressEventForRegistration", v.img3D.GetDimensions(), subtract.GetOutput().GetDimensions())
            v.style.UpdatePipeline()

    def selectPointZero(self):

        rp = self.registration_parameters
        v = self.vtkWidget.viewer
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
        
        




    def OnLeftButtonPressEventForPointZero(self, interactor, event):
        print('OnLeftButtonPressEventForPointZero', event)
        v = self.vtkWidget.viewer
        shift = interactor.GetShiftKey()
        point0actor = 'Point0' in v.actors
        rp = self.registration_parameters
        if shift and rp['select_point_zero'].isChecked():
            print ("Shift pressed", shift)
            position = interactor.GetEventPosition()
            #vox = v.style.display2world(position)
            p0l = v.style.display2imageCoordinate(position)[:-1]
            spacing = v.img3D.GetSpacing()
            origin = v.img3D.GetOrigin()
            p0 = [ el * spacing[i] + origin[i] for i,el in enumerate(p0l) ]
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
                v.AddActor(point0Actor, 'Point0')
                self.viewer3DWidget.viewer.getRenderer().AddActor(point0Actor)
                self.point0 = [ point0 , point0Mapper, point0Actor ] 
            else:
                self.point0[0].SetFocalPoint(*vox)
                self.point0[0].SetModelBounds(-10 + vox[0], 10 + vox[0], -10 + vox[1], 10 + vox[1], -10 + vox[2], 10 + vox[2])
                self.point0[0].Update()
            rp = self.registration_parameters
            rp['point_zero_entry'].setText(str(v.style.display2imageCoordinate(position)[:-1]))


    def centerOnPointZero(self):
        '''Centers the viewing slice where Point 0 is'''
        rp = self.registration_parameters
        v = self.vtkWidget.viewer
        #v3 = 
        point0 = eval (rp['point_zero_entry'].text())
        if isinstance (point0, tuple):
            orientation = v.style.GetSliceOrientation()
            gotoslice = point0[orientation]
            v.style.SetActiveSlice( gotoslice )
            v.style.UpdatePipeline(True)

    def displayRegistrationSelection(self):
        print ("displayRegistrationSelection")
        rp = self.registration_parameters
        rp['registration_box_size_entry'].setEnabled( rp['register_on_selection_check'].isChecked() )
        v = self.vtkWidget.viewer
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
                v.AddActor(point0Actor, 'RegistrationBox')
                self.viewer3DWidget.viewer.getRenderer().AddActor(point0Actor)
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



    def createRunConfigurationWidget(self):

        #self.treeWidgetInitialElements = []
        #self.treeWidgetUpdateElements = []

        self.runconf_panel = self.generateUIDockParameters('5 - Run Configuration')
        dockWidget = self.runconf_panel[0]
        groupBox = self.runconf_panel[5]
        groupBox.setTitle('Run Parameters')
        formLayout = self.runconf_panel[6]

        # Create validation rule for text entry
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        rp = {}
        self.run_configuration_parameter = rp

        rp['run_points_in_subvolume_label'] = QLabel(groupBox)
        rp['run_points_in_subvolume_label'].setText("Points in subvolume")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['run_points_in_subvolume_label'])
        rp['run_points_in_subvolume_entry'] = QSpinBox(groupBox)
        rp['run_points_in_subvolume_entry'].setValue(1000)
        rp['run_points_in_subvolume_entry'].setSingleStep(10)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['run_points_in_subvolume_entry'])
        widgetno += 1

        rp['run_max_displacement_label'] = QLabel(groupBox)
        rp['run_max_displacement_label'].setText("Maximum Displacement (voxels)")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['run_max_displacement_label'])
        rp['run_max_displacement_entry'] = QSpinBox(groupBox)
        rp['run_max_displacement_entry'].setValue(10)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['run_max_displacement_entry'])
        widgetno += 1

        rp['run_ndof_label'] = QLabel(groupBox)
        rp['run_ndof_label'].setText("Number of Degrees of Freedom")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['run_ndof_label'])
        rp['run_ndof_entry'] = QComboBox(groupBox)
        rp['run_ndof_entry'].addItem('3')
        rp['run_ndof_entry'].addItem('6')
        rp['run_ndof_entry'].addItem('12')
        rp['run_ndof_entry'].setCurrentIndex(1)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['run_ndof_entry'])
        widgetno += 1

        rp['run_objf_label'] = QLabel(groupBox)
        rp['run_objf_label'].setText("Objective Function")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['run_objf_label'])
        rp['run_objf_entry'] = QComboBox(groupBox)
        rp['run_objf_entry'].addItem('sad')
        rp['run_objf_entry'].addItem('ssd')
        rp['run_objf_entry'].addItem('zssd')
        rp['run_objf_entry'].addItem('nssd')
        rp['run_objf_entry'].addItem('znssd')
        rp['run_objf_entry'].setCurrentIndex(4)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['run_objf_entry'])
        widgetno += 1

        rp['run_iterp_type_label'] = QLabel(groupBox)
        rp['run_iterp_type_label'].setText("Interpolation type")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['run_iterp_type_label'])
        rp['run_iterp_type_entry'] = QComboBox(groupBox)
        rp['run_iterp_type_entry'].addItem('Nearest')
        rp['run_iterp_type_entry'].addItem('Trilinear')
        rp['run_iterp_type_entry'].addItem('Tricubic')
        rp['run_iterp_type_entry'].setCurrentIndex(2)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, rp['run_iterp_type_entry'])
        widgetno += 1
        # Add horizonal seperator
        separator = QFrame(groupBox)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Raised)
        formLayout.setWidget(widgetno, QFormLayout.SpanningRole, separator)
        widgetno += 1
        

        # Add submit button
        rp['run_dvc_button'] = QPushButton(groupBox)
        rp['run_dvc_button'].setText("Test Run DVC")
        rp['run_dvc_button'].clicked.connect(self.testRun)
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, rp['run_dvc_button'])
        widgetno += 1

        # Add elements to layout
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
        
    def generateMultiRunDVCConfig(self):
        '''Generates the Multi run DVC configuration with the given input'''
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        
        # select output directory
        fn = dialog.getExistingDirectory()
        # print (fn)
        outdir = os.path.abspath(fn)
        
        # read the ranges
        ranges = self.ranges
        xmin = int(ranges['radius_range_min_value'].text())
        xmax = int(ranges['radius_range_max_value'].text())
        xstep = int(ranges['radius_range_step_value'].text())
        if xstep != 0:
            if xmax > xmin:
                N = (xmax-xmin)//xstep + 1
                radius = [xmin + i * xstep for i in range(N)]
            else:
                self.warningDialog("Radius. Min ({}) value higher than Max ({})".format(
                        xmin, xmax), window_title="Value Error", 
                     )
                return
        else:
            radius = [xmin]
            
        
        print ("radii ", radius)
        
        xmin = int(ranges['points_in_subvol_range_min_value'].text())
        xmax = int(ranges['points_in_subvol_range_max_value'].text())
        xstep = int(ranges['points_in_subvol_range_step_value'].text())
        if xstep != 0:
            if xmax > xmin:
                N = (xmax-xmin)//xstep + 1
                npoints = [xmin + i * xstep for i in range(N)]
            else:
                self.warningDialog("Points in subvolume. Min ({}) value higher than Max ({})".format(
                        xmin, xmax) , window_title="Value Error")
                return
        else:
            npoints = [xmin]
        print ("npoints", npoints)
        
        
        config = {}
        
        dims = self.vtkWidget.viewer.img3D.GetDimensions()
        
        # 1 save the mask ?
        # Mask is read from temp file
        tmpdir = tempfile.gettempdir() 
        reader = vtk.vtkMetaImageReader()
        reader.SetFileName(os.path.join(tmpdir, "selection.mha"))
        reader.Update()
        
        print ("save mask")
        writer = vtk.vtkMetaImageWriter()
        writer.SetInputConnection(reader.GetOutputPort())
        writer.SetFileName(os.path.join(outdir,"mask.mhd"))
        writer.SetCompression(1)
        writer.Write()
        # 2 save the dataset
        print ("save dataset")
        writer.SetInputData(self.vtkWidget.viewer.img3D)
        writer.SetCompression(0)
        writer.Write()
        # 2 create the point clouds config
        config['radius_range'] = radius
        config['mask_file'] = os.path.join('mask.mhd')
        
        shapeselected = self.subvolumeShapeValue.currentIndex()
        shape = 'cube' if shapeselected == 0 or shapeselected == 1 else 'sphere'
        
        config['subvol_geom'] = shape #: cube, sphere
        # config['subvol_size'] = r * 2 #: side length or diameter, in voxels
        ### description of the image data files, 
        # all must be the same size and structure
        # these will be checked when creating the dvc input files. 
        config['vol_wide'] = dims[0] #: width in pixels of each slice
        config['vol_high'] = dims[1] #: height in pixels of each slice
        config['vol_tall'] = dims[2] #: number of slices in the stack
        config['subvol_npoints_range'] = npoints
        
        config['shape'] = shape
        dimensionality = [3,2]
        config['dimensionality'] = \
                        dimensionality[self.dimensionalityValue.currentIndex()]
        #slice is read from the viewer this is relevant for 2D 
        v = self.vtkWidget.viewer
        config['current_slice'] = v.GetActiveSlice()
        config['overlap'] = [ float(self.overlapXValueEntry.text()),
                              float(self.overlapYValueEntry.text()),
                              float(self.overlapZValueEntry.text()) ]
        
        rotate = (
                float(self.rotateXValueEntry.text()),
                float(self.rotateYValueEntry.text()),
                float(self.rotateZValueEntry.text())
                )
        config['rotation'] = rotate
        
        
        config_fname = os.path.join(outdir, 'dvcrun_config.json')
        print ("DVC config:", config_fname)
        print (config)

        with open(config_fname, 'w') as f:
            json.dump(config, f)
    

    def generateTestDVCConfig(self):
        '''Generates Test DVC configuration with the given input'''
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        
        # select output directory
        fn = dialog.getExistingDirectory()
        # print (fn)
        outdir = os.path.abspath(fn)
        
        # reference to data stored in the panel
        rp = self.registration_parameters
        pc = self.pointcloud_parameters
        rc = self.run_configuration_parameter
        
        config = {}
        
        
        
        # # 1 save the mask ?
        # # Mask is read from temp file
        # tmpdir = tempfile.gettempdir() 
        # reader = vtk.vtkMetaImageReader()
        # reader.SetFileName(os.path.join(tmpdir, "selection.mha"))
        # reader.Update()
        
        # print ("save mask")
        # writer = vtk.vtkMetaImageWriter()
        # writer.SetInputConnection(reader.GetOutputPort())
        # writer.SetFileName(os.path.join(outdir,"mask.mhd"))
        # writer.SetCompression(1)
        # writer.Write()
        # 2 save the dataset
        print ("save dataset")
        reference_fname = self.reader.GetFileName()
        if isinstance(self.reader, vtk.vtkTIFFReader):
            reference_fname = os.path.join(outdir,"reference.mhd")
            writer = vtk.vtkMetaImageWriter()
            writer.SetInputData(self.reader.GetOutput())
            writer.SetFileName(reference_fname)
            writer.SetCompression(0)
            writer.Write()
        reference_fname = self.correlate_reader.GetFileName()
        if isinstance(self.correlate_reader, vtk.vtkTIFFReader):
            correlate_fname = os.path.join(outdir,"correlate.mhd")
            writer = vtk.vtkMetaImageWriter()
            writer.SetInputData(self.correlate_reader.GetOutput())
            writer.SetFileName(correlate_fname)
            writer.SetCompression(0)
            writer.Write()


        config['reference_filename'] = reference_fname
        config['correlate_filename'] = correlate_fname
        # 2 create the point clouds config
        #config['mask_file'] = os.path.join('mask.mhd')
        
        shapeselected = pc['pointcloud_volume_shape_entry'].currentIndex()
        shape = 'cube' if shapeselected == 0 or shapeselected == 1 else 'sphere'
        
        config['subvol_geom'] = shape #: cube, sphere
        # config['subvol_size'] = r * 2 #: side length or diameter, in voxels
        ### description of the image data files, 
        # all must be the same size and structure
        # these will be checked when creating the dvc input files. 
        dims = self.reader.GetOutput().GetDimensions()
        dtype = self.reader.GetOutput().GetScalarType()
        if dtype == vtk.VTK_CHAR or dtype == vtk.VTK_UNSIGNED_CHAR:
            vdepth = 8
        elif dtype == vtk.VTK_SHORT or dtype == vtk.VTK_UNSIGNED_SHORT:
            vdepth = 16
        else:
            self.warningDialog(
                message='Can process only 8 or 16 integer data. Got {}'.format(
                   self.reader.GetOutput().GetScalarTypeAsString()),
                window_title="ERROR"
                )
            return
        config['vol_wide'] = dims[0] #: width in pixels of each slice
        config['vol_high'] = dims[1] #: height in pixels of each slice
        config['vol_tall'] = dims[2] #: number of slices in the stack
        config['vol_bit_depth'] = vdepth
        config['subvol_thresh'] = 'off'
        
        config['shape'] = shape
        dimensionality = [3,2]
        
        config['dimensionality'] = \
                        dimensionality[pc['pointcloud_dimensionality_entry'].currentIndex()]
        

        config['overlap'] = [ float(pc['pointcloud_overlap_x_entry'].text()),
                              float(pc['pointcloud_overlap_y_entry'].text()),
                              float(pc['pointcloud_overlap_z_entry'].text()) ]
        
        rotate = (
                float(pc['pointcloud_rotation_x_entry'].text()),
                float(pc['pointcloud_rotation_y_entry'].text()),
                float(pc['pointcloud_rotation_z_entry'].text())
                )
        config['rotation'] = rotate
        
        obj_funcs = ['sad','ssd','zssd','nssd','znssd']
        config['obj_function'] = abj_funcs[rc['run_objf_entry'].currentIndex()]
        
        interp_types = ['nearest' , 'trilinear' , 'tricubic' ]
        config['interp_type'] = interp_types[rc['run_iterp_type_entry'].currentIndex()]

        config['displ_max'] = rc['run_max_displacement_entry'].value()

        ndofs = [3,6,12]
        config['num_src_dof'] = ndofs[rc['run_ndof_entry'].currentIndex()]

        config['rigid_trans'] = [ int(rp['translate_X_entry'].text()) , 
                                  int(rp['translate_Y_entry'].text()) ,
                                  int(rp['translate_Z_entry'].text()) ]
        config['subvol_npts'] = rc['run_points_in_subvolume_entry'].value()
        config['subvol_size'] = int(pc['pointcloud_radius_entry'].text())


        config_fname = os.path.join(outdir, 'dvcrun_config.json')
        print ("DVC config:", config_fname)
        print (config)

        with open(config_fname, 'w') as f:
            json.dump(config, f)
    

        controller = DVC()
        controller.config_run(config_fname)

        pointcloud = dvc.DataCloud()
        # the points are in self.polydata_masker
        pointcloud.loadPointCloudFromNumpy(roi[:10])
        pointcloud.organize_cloud(controller.run)

        #controller.run.run_dvc_cmd(pc)
        
        
    def loadIntoTableWidget(self, data):
        if len(data) <= 0:
            return
        self.tableWidget.setRowCount(len(data))
        self.tableWidget.setColumnCount(len(data[0]))
        for i, v in enumerate(data):
            for j, w in enumerate(v):
                self.tableWidget.setItem(i, j, QTableWidgetItem(str(w)))

    def updatePointCloud(self):
        print("should read the table here and save to csv")

    def warningDialog(self, message='', window_title='', detailed_text=''):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Information)
        dialog.setText(message)
        dialog.setWindowTitle(window_title)
        dialog.setDetailedText(detailed_text)
        dialog.setStandardButtons(QMessageBox.Ok)
        retval = dialog.exec_()
        return retval
        

    def createPointCloud(self):
        ## Create the PointCloud
        # 
        
        
        # Mask is read from temp file
        tmpdir = tempfile.gettempdir() 
        reader = vtk.vtkMetaImageReader()
        reader.SetFileName(os.path.join(tmpdir, "selection.mha"))
        reader.Update()
        origin = reader.GetOutput().GetOrigin()
        spacing = reader.GetOutput().GetSpacing()
        dimensions = reader.GetOutput().GetDimensions()
        
        if not self.pointCloudCreated:
            pointCloud = cilRegularPointCloudToPolyData()
            # save reference
            self.pointCloud = pointCloud
        else:
            pointCloud = self.pointCloud
        
        
        shapes = [cilRegularPointCloudToPolyData.SPHERE,
                  cilRegularPointCloudToPolyData.CUBE,
                  cilRegularPointCloudToPolyData.CIRCLE,
                  cilRegularPointCloudToPolyData.SQUARE]
        dimensionality = [3,2]
        
        
        pointCloud.SetMode(shapes[self.subvolumeShapeValue.currentIndex()])
        pointCloud.SetDimensionality(
                dimensionality[self.dimensionalityValue.currentIndex()]
                ) 
        
        #slice is read from the viewer
        v = self.vtkWidget.viewer
        pointCloud.SetSlice(v.GetActiveSlice())
        
        pointCloud.SetInputConnection(0, reader.GetOutputPort())
        
        pointCloud.SetOverlap(0,float(self.overlapXValueEntry.text()))
        pointCloud.SetOverlap(1,float(self.overlapYValueEntry.text()))
        pointCloud.SetOverlap(2,float(self.overlapZValueEntry.text()))
        
        pointCloud.SetSubVolumeRadiusInVoxel(int(self.isoValueEntry.text()))
                
        pointCloud.Update()
        
        print ("pointCloud number of points", pointCloud.GetNumberOfPoints())
             
        # Erode the transformed mask of SubVolumeRadius because we don't want to have subvolumes 
        # outside the mask
        if not self.pointCloudCreated:
            erode = vtk.vtkImageDilateErode3D()
            erode.SetErodeValue(1)
            erode.SetDilateValue(0) 
            # save reference
            self.erode = erode
            self.erode_pars = {'selection_mtime':os.path.getmtime(
                    os.path.join(tmpdir, "selection.mha"))}
            
        else:
            erode = self.erode
            
        
        
        
        # FIXME: Currently the 2D case is only XY
        # For 2D we need to set the Kernel size in the plane to 1, 
        # otherwise the erosion would erode the whole mask.
        ks = [pointCloud.GetSubVolumeRadiusInVoxel(), pointCloud.GetSubVolumeRadiusInVoxel(), 1]
        if pointCloud.GetDimensionality() == 3:
            ks[2]= pointCloud.GetSubVolumeRadiusInVoxel()
            
        #else:
        #    # erode in 2D
        #    voi = vtk.vtkExtractVOI()
        #    voi.SetInputConnection(reader.GetOutputPort())
        #    voi.SetVOI(self.vtkWidget.viewer.voi.GetVOI())
        #    voi.Update()
        #    erode.SetInputConnection(0,voi.GetOutputPort())
            
        # if shape is box or square to be sure that the subvolume is within
        # the mask we need to take the half of the diagonal rather than the
        # half of the size
        if self.subvolumeShapeValue.currentIndex() == 0 or \
           self.subvolumeShapeValue.currentIndex() == 2:
               ks = [round(1.41 * l) for l in ks]
        
        
        # the mask erosion takes a looong time. Try not do it all the 
        # time if neither mask nor other values have changed
        if not self.pointCloudCreated:
            self.erode_pars['ks'] =  ks[:]        
            run_erode = True
        else:
            run_erode = False
            # test if mask is different from last one by checking the modification
            # time
            mtime = os.path.getmtime(os.path.join(tmpdir, "selection.mha"))
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
        print ("mask created")
        
        
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
        rotate = (
                float(self.rotateXValueEntry.text()),
                float(self.rotateYValueEntry.text()),
                float(self.rotateZValueEntry.text())
                )
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
        transform.Translate(dimensions[0]/2*spacing[0], dimensions[1]/2*spacing[1],0)
        # rotation angles
        transform.RotateX(rotate[0])
        transform.RotateY(rotate[1])
        transform.RotateZ(rotate[2])
        transform.Translate(-dimensions[0]/2*spacing[0], -dimensions[1]/2*spacing[1],0)
        
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
        
        if not self.pointCloudCreated:
            # visualise polydata
            self.setup2DPointCloudPipeline()
            self.vtkWidget.viewer.setInputData2(reader.GetOutput())
            self.setup3DPointCloudPipeline()
            self.pointCloudCreated = True
        else:
            spacing = self.vtkWidget.viewer.img3D.GetSpacing()
            radius = pointCloud.GetSubVolumeRadiusInVoxel()
    
            if self.subvolumeShapeValue.currentIndex() == 0 or \
               self.subvolumeShapeValue.currentIndex() == 2:
               #cube
                self.glyph_source = self.cube_source
                self.cube_source.SetXLength(spacing[0]*radius*2)
                self.cube_source.SetYLength(spacing[1]*radius*2)
                self.cube_source.SetZLength(spacing[2]*radius*2)    
                self.cubesphere.SetSourceConnection(self.cube_source.GetOutputPort())
            else:
                self.glyph_source = self.sphere_source
                self.sphere_source.SetRadius(radius * spacing[0])
                self.cubesphere.SetSourceConnection(self.sphere_source.GetOutputPort())
            
            
            self.cubesphere.Update()
            # self.polydata_masker.Modified()
#            self.cubesphere_actor3D.VisibilityOff()
#            self.pointactor.VisibilityOff()
#            self.cubesphere_actor.VisibilityOff()
            print ("should be already changed")
#            self.cubesphere_actor3D.VisibilityOn()
#            self.pointactor.VisibilityOn()
#            self.cubesphere_actor.VisibilityOn()


    def OnKeyPressEvent(self, interactor, event):
        if interactor.GetKeyCode() == "t":
            if not self.start_selection:
                self.extendMask()

            self.start_selection = not self.start_selection

    def extendMaskWorker(self):
        """
        Trigger method to allow threading of long running process
        """
        print ("doSomething")
        self.showProgressBar()

        worker = Worker(self.extendMaskThread)
        print ("doSomething start Worker")
        self.threadpool.start(worker)

        # Progress bar signal handling
        worker.signals.finished.connect(self.completeProgressBar)
        worker.signals.progress.connect(self.updateProgressBar)

    def extendMask(self, progress_callback=None):
        # FIXME, needs to get the orientation from the viewer and
        # copy to slices below
        poly = vtk.vtkPolyData()
        v = self.vtkWidget.viewer
        v.imageTracer.GetPath(poly)
        pathpoints = poly.GetPoints()
        # for i in range(poly.GetPoints().GetNumberOfPoints()):
        #    print (poly.GetPoints().GetPoint(i))
        lasso = vtk.vtkLassoStencilSource()
        self.lasso = lasso

        lasso.SetShapeToPolygon()
        # pass the slice at which the lasso has to process
        sliceno = v.style.GetActiveSlice()
        lasso.SetSlicePoints(sliceno , pathpoints)
        lasso.SetSliceOrientation(2)
        lasso.SetInformationInput(self.reader.GetOutput())

        # create a blank image
        dims = self.reader.GetOutput().GetDimensions()

        mask0 = Converter.numpy2vtkImporter(numpy.zeros(
                                             (dims[0],dims[1],dims[2]),
                                             order='C', dtype=numpy.uint8) ,
                                           spacing = self.reader.GetOutput().GetSpacing(),
                                           origin = self.reader.GetOutput().GetOrigin(),
                                           transpose=[2,1,0]
                                           )
        # create an image with 1 in it
        mask1 = Converter.numpy2vtkImporter(numpy.ones(
                                             (dims[0],dims[1],dims[2]),
                                             order='C', dtype=numpy.uint8),
                                           spacing = self.reader.GetOutput().GetSpacing(),
                                           origin = self.reader.GetOutput().GetOrigin(),
                                           transpose=[2,1,0]
                                           )


        mask0.Update()
        mask1.Update()
        # progress_callback.emit(20)

        # Create a Mask from the lasso.
        stencil = vtk.vtkImageStencil()
        self.mask_reader = stencil
        stencil.SetInputConnection(mask1.GetOutputPort())
        stencil.SetBackgroundInputData(mask0.GetOutput())
        stencil.SetStencilConnection(lasso.GetOutputPort())
        stencil.Update()
        dims = stencil.GetOutput().GetDimensions()

        # down = int(self.extendBelowEntry.text())
        # up   = int(self.extendAboveEntry.text())
        down = self.mask_parameters['mask_extend_below_entry'].value()
        up = self.mask_parameters['mask_extend_above_entry'].value()


        # do not extend outside the image
        zmin = sliceno -down if sliceno-down>=0 else 0
        zmax = sliceno + up if sliceno+up < dims[2] else dims[2]

        # progress_callback.emit(25)
        vtkutils.copyslices(stencil.GetOutput(), sliceno , zmin, zmax, None)
#                for x in range(dims[0]):
#                    for y in range(dims[1]):
#                        for z in range(zmin, zmax):
#                            if z != sliceno:
#                                val = stencil.GetOutput().GetScalarComponentAsFloat(x,y,sliceno,0)
#                                stencil.GetOutput().SetScalarComponentFromFloat(x,y,z,0,val)
#
        # progress_callback.emit(80)
        # save the mask to a file temporarily
        writer = vtk.vtkMetaImageWriter()
        tmpdir = tempfile.gettempdir()
        writer.SetFileName(os.path.join(tmpdir, "selection.mha"))

        # if extend mask -> load temp saved mask
        if self.extendMaskCheck.isChecked():
            self.setStatusTip('Extending mask')
            if os.path.exists(os.path.join(tmpdir, "selection.mha")):
                print  ("extending mask ", os.path.join(tmpdir, "selection.mha"))
                reader = vtk.vtkMetaImageReader()
                reader.SetFileName(os.path.join(tmpdir, "selection.mha"))
                reader.Update()

                math = vtk.vtkImageMathematics()
                math.SetOperationToAdd()
                math.SetInput1Data(stencil.GetOutput())
                math.SetInput2Data(reader.GetOutput())
                math.Update()

                threshold = vtk.vtkImageThreshold()
                threshold.ThresholdBetween(1, 255)
                threshold.ReplaceInOn()
                threshold.SetInValue(1)
                threshold.SetInputConnection(math.GetOutputPort())
                threshold.Update()

                writer.SetInputData(threshold.GetOutput())
                #print (math.GetOutput().GetDimensions())
                v.setInputData2(threshold.GetOutput())
            else:
                print  ("extending mask failed ", tmpdir)
        else:
            writer.SetInputData(stencil.GetOutput())
            v.setInputData2(stencil.GetOutput())



        writer.Write()
        self.extendMaskCheck.setEnabled(True)
        self.setStatusTip('Done')

    def testRun(self):
        '''run a DVC optimisation with the current parameters'''
        self.run_control = dvc.RunControl()
        self.data_cloud = dvc.DataCloud()

#    def updateProgressBar(self, value):
#        """
#        Set progress bar percentage.
#
#        :param (int) value:
#            Integer value between 0-100.
#        """
#
#        self.progressBar.setValue(value)
#
#    def completeProgressBar(self):
#        """
#        Set the progress bar to 100% complete and hide
#        """
#        self.progressBar.setValue(100)
#        self.progressBar.hide()
#
#    def showProgressBar(self):
#        """
#        Set the progress bar to 0% complete and show
#        """
#        self.progressBar.setValue(0)
#        self.progressBar.show()


def main():
    err = vtk.vtkFileOutputWindow()
    err.SetFileName("viewer.log")
    vtk.vtkOutputWindow.SetInstance(err)

    __version__ = '0.1.0'
    print ("Starting ... ")
    args = docopt(__doc__, version=__version__)
    print ("Parsing args")
    print ("Passed args " , args)

    App = QApplication(sys.argv)
    gui = Window()
    gui.setApp(App)
    
    if not args['--subvol'] is None:
        subvol_size = int(args["--subvol"])
        gui.setSubvolSize(subvol_size)

    if not args['-i'] is None:
        fname = os.path.abspath(args["-i"])
        gui.openFileByPath(( (fname , ),))

    # this should be deleted
    # show_spheres = False
    # if not args['--spheres'] is None:
    #    show_spheres = True if args["--spheres"] == 1 else False
    # gui.dislayPointCloudAsSpheres(show_spheres)


    sys.exit(App.exec())




if __name__ == "__main__":
    main()
