"""
DataExplorer

UI to configure a DVC run

Usage:
 DataExplorer.py [ -h ] [ --imagedata=<path> ] [ --spheres=0 ] [ --subvol=10 ]

Options:
 --imagedata=path      input filename
 --spheres=n        whether to show spheres
 --subvol=n         the max size of the subvolume in voxel
 -h       display help

Example:
    python DVC_configurator.py --imagedata ..\..\..\CCPi-Simpleflex\data\head.mha
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
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QMessageBox
import vtk
from ccpi.viewer.QVTKCILViewer import QVTKCILViewer
from ccpi.viewer.QVTKWidget import QVTKWidget
from ccpi.viewer.utils import Converter
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XZ
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_YZ
from ccpi.viewer.utils import cilRegularPointCloudToPolyData
from ccpi.viewer.utils import cilMaskPolyData , cilClipPolyDataBetweenPlanes
from ccpi.viewer.utils import cilNumpyMETAImageWriter
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


class ErrorObserver:

    def __init__(self):
        self.__ErrorOccurred = False
        self.__ErrorMessage = None
        self.CallDataType = 'string0'

    def __call__(self, obj, event, message):
        self.__ErrorOccurred = True
        self.__ErrorMessage = message

    def ErrorOccurred(self):
        occ = self.__ErrorOccurred
        self.__ErrorOccurred = False
        return occ

    def ErrorMessage(self):
        return self.__ErrorMessage


def sentenceCase(string):
    if string:
        first_word = string.split()[0]
        world_len = len(first_word)

        return first_word.capitalize() + string[world_len:]

    else:
        return ''


class Window(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('CIL Viewer')
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
        self.iren = self.vtkWidget.getInteractor()
        self.vl.addWidget(self.vtkWidget)

        self.frame.setLayout(self.vl)
        self.setCentralWidget(self.frame)

        self.createDock3DWidget()
        self.createPointCloudWidget()
        self.createMaskWidget()
        self.createRangeWidget()
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

        self.statusBar()
        self.setStatusTip('Open file to begin visualisation...')

        self.subvol = 80
        self.displaySpheres = True

        # self.pointcloud = []
        self.start_selection = True
        self.pointCloudCreated = False

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
        actor.GetProperty().SetColor(.2, .2, 1)
        actor.VisibilityOn()
        actor.AddObserver("ModifiedEvent", lambda: print ("point actor modified"))
        # create a mapper/actor for the point cloud with a CubeSource and with vtkGlyph3D
        # which copies oriented and scaled glyph geometry to every input point

        subv_glyph = vtk.vtkGlyph3D()
        # save reference
        self.cubesphere = subv_glyph
        subv_glyph.SetScaleFactor(1.)

        erode = self.erode
        spacing = erode.GetOutput().GetSpacing()
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
        sphere_actor.GetProperty().SetOpacity(0.2)
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
        openAction = QAction("Open", self)
        openAction.setShortcut("Ctrl+O")
        openAction.triggered.connect(self.openFile)

        closeAction = QAction("Close", self)
        closeAction.setShortcut("Ctrl+Q")
        closeAction.triggered.connect(self.close)

        tableAction = QAction("Point Cloud Setup", self)
        tableAction.setShortcut("Ctrl+T")
        tableAction.triggered.connect(self.showPointCloudWidget)

        # define actions
        # load data
        openAction = QAction(self.style().standardIcon(
            QStyle.SP_DirOpenIcon), 'Open Volume Data', self)
        openAction.triggered.connect(self.openFile)
        # define load mask
        openMask = QAction(self.style().standardIcon(
            QStyle.SP_FileDialogStart), 'Open Mask Data', self)
        openMask.triggered.connect(self.openMask)
        # define load PointCloud
        openPointCloud = QAction(self.style().standardIcon(
            QStyle.SP_DirOpenIcon), 'Open Point Cloud', self)
        openMask.triggered.connect(self.openPointCloud)

        # define save mask
        saveMask = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton), 'Save Mask Data', self)
        saveMask.triggered.connect(self.saveMask)
        # define save pointcloud
        savePointCloud = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton), 'Save point cloud', self)
        savePointCloud.triggered.connect(self.savePointCloud)

        saveAction = QAction(self.style().standardIcon(
            QStyle.SP_DialogSaveButton), 'Save current render as PNG', self)
        saveAction.triggered.connect(self.saveFileRender)

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('File')
        fileMenu.addAction(openAction)
        fileMenu.addAction(openMask)
        fileMenu.addAction(openPointCloud)

        fileMenu.addAction(saveMask)
        fileMenu.addAction(savePointCloud)

        fileMenu.addAction(closeAction)
        fileMenu.addAction(tableAction)

        panels = []

        self.show3D = QAction("Show 3D View", self)
        self.show3D.setCheckable(True)
        self.show3D.setChecked(False)
        # self.show3D.setShortcut("Ctrl+T")
        self.show3D.triggered.connect(self.showHide3D)

        self.showPointCloudConfigurator = QAction("Configure Point Cloud Panel", self)
        self.showPointCloudConfigurator.setCheckable(True)
        self.showPointCloudConfigurator.setChecked(False)
        self.showPointCloudConfigurator.triggered.connect(
                lambda: self.pointCloudDockWidget.show() \
                   if self.showPointCloudConfigurator.isChecked() else \
                       self.pointCloudDockWidget.hide()
                )

        self.showMaskConfigurator = QAction("Configure Mask Panel", self)
        self.showMaskConfigurator.setCheckable(True)
        self.showMaskConfigurator.setChecked(True)
        self.showMaskConfigurator.triggered.connect(
                lambda: self.mask_panel[0].show() \
                   if self.showMaskConfigurator.isChecked() else \
                       self.mask_panel[0].hide()
                )
        
        self.showRangesConfigurator = QAction("Configure Ranges Panel", self)
        self.showRangesConfigurator.setCheckable(True)
        self.showRangesConfigurator.setChecked(False)
        self.showRangesConfigurator.triggered.connect(
                lambda: self.range_panel[0].show() \
                   if self.showRangesConfigurator.isChecked() else \
                       self.range_panel[0].hide()
                )
        viewMenu = mainMenu.addMenu('Panels')
        viewMenu.addAction(self.show3D)
        viewMenu.addAction(self.showMaskConfigurator)
        viewMenu.addAction(self.showPointCloudConfigurator)
        viewMenu.addAction(self.showRangesConfigurator)

        panels.append((self.show3D, self.Dock3D))
        panels.append((self.showPointCloudConfigurator, self.pointCloudDockWidget))
        panels.append((self.showMaskConfigurator, self.mask_panel[0] ))
        panels.append((self.showRangesConfigurator, self.range_panel[0]))
        self.panels = panels

        # Initialise the toolbar
        self.toolbar = self.addToolBar('Viewer tools')



        # Add actions to toolbar
        self.toolbar.addAction(openAction)
        self.toolbar.addAction(saveAction)



    def showHide3D(self):
        if self.show3D.isChecked():
            self.Dock3D.show()
        else:
            self.Dock3D.hide()

    def openFile(self, read_mask=False):
        fn = QFileDialog.getOpenFileNames(self, 'Open File')

        # If the user has pressed cancel, the first element of the tuple will be empty.
        # Quit the method cleanly
        if not fn[0]:
            return
        self.openFileByPath(fn, read_mask)
    def openMask(self):
        self.openFile(True)

    def openFileByPath(self, fn, read_mask=False):
        # Single file selection
        if len(fn[0]) == 1:
            file = fn[0][0]

            if imghdr.what(file) == None:
                if file.split(".")[1] == 'mha' or\
                        file.split(".")[1] == 'mhd':
                    reader = vtk.vtkMetaImageReader()
                    reader.AddObserver("ErrorEvent", self.e)
                    reader.SetFileName(file)
                    reader.Update()
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
            reader.Update()

        dtype = vtk.VTK_UNSIGNED_CHAR
        if reader.GetOutput().GetScalarType() != dtype:
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
            self.vtkWidget.viewer.setInput3DData(reader.GetOutput())
            self.viewer3DWidget.viewer.setInput3DData(self.vtkWidget.viewer.img3D)
            self.viewer3DWidget.viewer.sliceActor.GetProperty().SetOpacity(0.99)
        if read_mask:
            self.mask_reader = reader
        else:
            self.reader = reader
        self.setStatusTip('Ready')


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

        fn = dialog.getSaveFileName(self, 'Save Mask As', '.', "NumpyMETAImage")

        # Only save if the user has selected a name
        if fn[0]:
            print ("Well done")
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
            #from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY
            #from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XZ
            #from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_YZ
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
            # print("event {} origin above {} beta {}".format(event, origin, beta))

            # print("slice {} beta {} orig {} spac {} normal {}".format(v.GetActiveSlice(), beta,
            #      orig, spac , normal))
            # print("origin", origin, orientation)
            # print("<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>")

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
            print("event {} origin below {} beta {}".format(event, origin_below, beta))

            bpcpoints.SetPlaneOriginBelow(origin_below)
            bpcpoints.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))
            bpcvolume.SetPlaneOriginBelow(origin_below)
            bpcvolume.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))

            bpcpoints.Update()
            bpcvolume.Update()
            self.viewer3DWidget.viewer.sliceActor.VisibilityOff()
            self.viewer3DWidget.viewer.sliceActor.GetProperty().SetOpacity(0.99)
            self.viewer3DWidget.viewer.sliceActor.VisibilityOn()
            print (">>>>>>>>>>>>>>>>>>>>>")
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
        self.pointCloudDockWidget.setWindowTitle('Point Cloud')
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

        widgetno = 1


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
        # Add collapse priority field
        self.subvolumeShapeLabel = QLabel(self.graphParamsGroupBox)
        self.subvolumeShapeLabel.setText("Subvolume shape")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.subvolumeShapeLabel)
        self.subvolumeShapeValue = QComboBox(self.graphParamsGroupBox)
        self.subvolumeShapeValue.addItem("Cube")
        self.subvolumeShapeValue.addItem("Sphere")
        self.subvolumeShapeValue.addItem("Box")
        self.subvolumeShapeValue.addItem("Circle")
        self.subvolumeShapeValue.setCurrentIndex(0)

        self.treeWidgetUpdateElements.append(self.subvolumeShapeValue)
        self.treeWidgetUpdateElements.append(self.subvolumeShapeLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.subvolumeShapeValue)
        widgetno += 1

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
        self.dimensionalityValue.setCurrentIndex(0)
        self.dimensionalityValue.currentIndexChanged.connect(lambda: \
                    self.overlapZValueEntry.setEnabled(True) \
                    if self.dimensionalityValue.currentIndex() == 0 else \
                       self.overlapZValueEntry.setEnabled(False))
        self.treeWidgetUpdateElements.append(self.dimensionalityValue)
        self.treeWidgetUpdateElements.append(self.dimensionalityValue)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.dimensionalityValue)
        widgetno += 1



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
        # Add Overlap Z
        self.overlapZLabel = QLabel(self.graphParamsGroupBox)
        self.overlapZLabel.setText("Overlap Z")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapZLabel)
        self.overlapZValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.overlapZValueEntry.setValidator(validator)
        self.overlapZValueEntry.setText("0.20")
        self.treeWidgetUpdateElements.append(self.overlapZValueEntry)
        self.treeWidgetUpdateElements.append(self.overlapZLabel)

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.overlapZValueEntry)
        widgetno += 1

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

        # Add submit button
        self.graphParamsSubmitButton = QPushButton(self.graphParamsGroupBox)
        self.graphParamsSubmitButton.setText("Generate Point Cloud")
        self.graphParamsSubmitButton.clicked.connect( self.createPointCloud )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.graphParamsSubmitButton)
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

        self.mask_panel = self.generateUIDockParameters('Mask')
        dockWidget = self.mask_panel[0]
        groupBox = self.mask_panel[5]
        groupBox.setTitle('Mask Parameters')
        formLayout = self.mask_panel[6]

        # Create validation rule for text entry
        validator = QtGui.QDoubleValidator()
        validator.setDecimals(2)
        validatorint = QtGui.QIntValidator()

        widgetno = 1


        # extend above field
        self.extendAboveLabel = QLabel(groupBox)
        self.extendAboveLabel.setText("Extend Above ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, self.extendAboveLabel)
        self.extendAboveEntry= QLineEdit(groupBox)
        self.extendAboveEntry.setValidator(validatorint)
        self.extendAboveEntry.setText("10")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveEntry)
        #self.treeWidgetUpdateElements.append(self.extendAboveLabel)
        widgetno += 1
        # extend below field
        self.extendBelowLabel = QLabel(groupBox)
        self.extendBelowLabel.setText("Extend Below ")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, self.extendBelowLabel)
        self.extendBelowEntry= QLineEdit(groupBox)
        self.extendBelowEntry.setValidator(validatorint)
        self.extendBelowEntry.setText("10")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, self.extendBelowEntry)
        #self.treeWidgetUpdateElements.append(self.extendBelowEntry)
        #self.treeWidgetUpdateElements.append(self.extendBelowLabel)
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
        panel = self.generateUIDockParameters('Ranges')
        self.range_panel = panel
        dockWidget = panel[0]
        groupBox = panel[5]
        groupBox.setTitle('Range Parameters')
        formLayout = panel[6]
        
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
        ranges['generate_button'].setText("Generate DVC Config")
        ranges['generate_button'].clicked.connect(self.generateDVCConfig)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, ranges['generate_button'])
        widgetno += 1
        
        
        
        
        # Add elements to layout
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
        
    def generateDVCConfig(self):
        '''Generates the DVC configuration with the given input'''
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
                        xmin, xmax) )
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
                        xmin, xmax) )
                return
        else:
            npoints = [xmin]
        print ("npoints", npoints)
        
        
        config = {}
        
        dims = self.vtkWidget.viewer.img3D.GetDimensions()
        shapeselected = self.subvolumeShapeValue.currentIndex()
        shape = 'cube' if shapeselected == 0 or shapeselected == 2 else 'sphere'
        
        # 1 save the mask ?
        # 2 create the point clouds
        for r in radius:
            self.isoValueEntry.setText(str(r))
            self.createPointCloud()
            pointcloud = self.polydata_masker.GetOutputDataObject(0)
            array = numpy.zeros((pointcloud.GetNumberOfPoints(), 4))
            for i in range(pointcloud.GetNumberOfPoints()):
                pp = pointcloud.GetPoint(i)
                array[i] = (i, *pp)
            config['subvol_geom'] = shape #: cube, sphere
            config['subvol_size'] = r * 2 #: side length or diameter, in voxels
            ### description of the image data files, all must be the same size and structure
            # these will be checked when creating the dvc input files. 
            config['vol_wide'] = dims[0] #: width in pixels of each slice
            config['vol_high'] = dims[1] #: height in pixels of each slice
            config['vol_tall'] = dims[2] #: number of slices in the stack
            for n in npoints:
                # the number of points in the subvolume are not influencing the
                # actual point cloud
                run_dir = os.path.join(outdir, 'r{:d}_np{:d}'.format(r,n))
                os.mkdir(run_dir)
                fname = os.path.join(run_dir, 'pointcloud_r{:d}.roi'.format(r))
                numpy.savetxt(fname, array, '%d\t%.3f\t%.3f\t%.3f', delimiter=';')
                
                config['point_cloud_filename'] = os.path.basename(fname)
                config['subvol_npts'] =	n #: number of points to distribute within the subvol
                config_fname = os.path.join(run_dir, 'pointcloud_config.json')
                with open(config_fname, 'w') as f:
                    json.dump(config, f)
            
        
        
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

    def warningDialog(self, message):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Information)
        dialog.setText(message)
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
            # save reference
            self.erode = erode
        else:
            erode = self.erode
        erode.SetInputConnection(0,reader.GetOutputPort())
        erode.SetErodeValue(1)
        erode.SetDilateValue(0) 
        
        # FIXME: Currently the 2D case is only XY
        # For 2D we need to set the Kernel size in the plane to 1, 
        # otherwise the erosion would erode the whole mask.
        ks = [pointCloud.GetSubVolumeRadiusInVoxel(), pointCloud.GetSubVolumeRadiusInVoxel(), 1]
        if pointCloud.GetDimensionality() == 3:
            ks[2]= pointCloud.GetSubVolumeRadiusInVoxel()
        # if shape is box or square to be sure that the subvolume is within
        # the mask we need to take the half of the diagonal rather than the
        # half of the size
        if self.subvolumeShapeValue.currentIndex() == 0 or \
           self.subvolumeShapeValue.currentIndex() == 2:
               ks = [round(1.41 * l) for l in ks]
        
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
        polydata_masker.SetInputConnection(1, erode.GetOutputPort())
        
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
        if rotate != [0.,0.,0.]:
            polydata_masker.SetInputConnection(0, t_filter.GetOutputPort())
        else:
            polydata_masker.SetInputConnection(0, pointCloud.GetOutputPort())
            polydata_masker.Modified()
        
        polydata_masker.Update()
        # print ("polydata_masker type", type(polydata_masker.GetOutputDataObject(0)))
        
        if not self.pointCloudCreated:
            # visualise polydata
            self.setup2DPointCloudPipeline()
            self.vtkWidget.viewer.setInputData2(reader.GetOutput())
            self.setup3DPointCloudPipeline()
            self.pointCloudCreated = True
        else:
            if self.subvolumeShapeValue.currentIndex() == 0 or \
               self.subvolumeShapeValue.currentIndex() == 2:
                self.glyph_source = self.cube_source
                self.cubesphere.SetSourceConnection(self.cube_source.GetOutputPort())
            else:
                self.glyph_source = self.sphere_source
                self.cubesphere.SetSourceConnection(self.sphere_source.GetOutputPort())
            self.cubesphere.Update()
            # self.polydata_masker.Modified()
            self.cubesphere_actor3D.VisibilityOff()
            self.pointactor.VisibilityOff()
            self.cubesphere_actor.VisibilityOff()
            print ("should be already changed")
            self.cubesphere_actor3D.VisibilityOn()
            self.pointactor.VisibilityOn()
            self.cubesphere_actor.VisibilityOn()


    def OnKeyPressEvent(self, interactor, event):
        if interactor.GetKeyCode() == "t":
            if not self.start_selection:
                self.extendMask()

            self.start_selection = not self.start_selection

    def extendMask(self):
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

        # Create a Mask from the lasso.
        stencil = vtk.vtkImageStencil()
        self.mask_reader = stencil
        stencil.SetInputConnection(mask1.GetOutputPort())
        stencil.SetBackgroundInputData(mask0.GetOutput())
        stencil.SetStencilConnection(lasso.GetOutputPort())
        stencil.Update()
        dims = stencil.GetOutput().GetDimensions()

        down = int(self.extendBelowEntry.text())
        up   = int(self.extendAboveEntry.text())
        # do not extend outside the image
        zmin = sliceno -down if sliceno-down>=0 else 0
        zmax = sliceno + up if sliceno+up < dims[2] else dims[2]

        vtkutils.copyslices(stencil.GetOutput(), sliceno , zmin, zmax)
#                for x in range(dims[0]):
#                    for y in range(dims[1]):
#                        for z in range(zmin, zmax):
#                            if z != sliceno:
#                                val = stencil.GetOutput().GetScalarComponentAsFloat(x,y,sliceno,0)
#                                stencil.GetOutput().SetScalarComponentFromFloat(x,y,z,0,val)
#

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
    show_spheres = False
    if not args['--spheres'] is None:
        show_spheres = True if args["--spheres"] == 1 else False

    subvol_size = 5
    if not args['--subvol'] is None:
        subvol_size = int(args["--subvol"])

    if not args['--imagedata'] is None:
        fname = os.path.abspath(args["--imagedata"])
        gui.openFileByPath(( (fname , ),))

    gui.setSubvolSize(subvol_size)
    gui.dislayPointCloudAsSpheres(show_spheres)


    sys.exit(App.exec())




if __name__ == "__main__":
    main()
