from ccpi.viewer.standaloneQT import *
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY, SLICE_ORIENTATION_YZ, SLICE_ORIENTATION_XZ
class RegistrationGUI(Window):
    '''Extends the standaloneQT app'''
    def __init__(self):
        self.loaded = [False, False]
        self.ROI = None
        super(RegistrationGUI, self).__init__()
        self.createRoiDock()

        # add event to viewer
        self.vtkWidget.viewer.style.AddObserver('KeyPressEvent', self.OnKeyPressEventTranslate, 0.5)
        

    def setApp(self, app):
        self.app = app
    def close(self):
        self.app.quit()
    def toolbar(self):
        # Initialise the toolbar
        self.toolbar = self.addToolBar('Pippo tools')

        # define actions
        
        # openAction = QAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), 'Open file', self)
        # openAction.triggered.connect(lambda: self.openFile(0))
        
        openAction1 = QAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), 'Open file', self)
        openAction1.triggered.connect(lambda: self.openFile(1))

        # saveAction = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), 'Save current render as PNG', self)
        # saveAction.setShortcut("Ctrl+S")
        # saveAction.triggered.connect(self.saveFile)


        mainMenu = self.menuBar()
        self.mainMenu = mainMenu
        fileMenu = mainMenu.addMenu('File2')
        action = fileMenu.addAction(openAction1)
        self.menu2 = {'menu' : fileMenu,
                      'action' : action}
        fileMenu.setEnabled(False)
        # fileMenu.addAction(closeAction)

        # Add actions to toolbar
        

    def openFile(self, number=0):
        fn = QFileDialog.getOpenFileNames(self, 'Open File')

        # If the user has pressed cancel, the first element of the tuple will be empty.
        # Quit the method cleanly
        if not fn[0]:
            return

        # Single file selection
        if len(fn[0]) == 1:
            file = fn[0][0]

            reader = vtk.vtkMetaImageReader()
            reader.AddObserver("ErrorEvent", self.e)
            reader.SetFileName(file)
            reader.Update()

        # Multiple TIFF files selected
        else:
            # Make sure that the files are sorted 0 - end
            filenames = natsorted(fn[0])

            # Basic test for tiff images
            for file in filenames:
                ftype = imghdr.what(file)
                if ftype != 'tiff':
                    # A non-TIFF file has been loaded, present error message and exit method
                    self.e('','','When reading multiple files, all files must TIFF formatted.')
                    file = file
                    self.displayFileErrorDialog(file)
                    return

            # Have passed basic test, can attempt to load
            #numpy_image = Converter.tiffStack2numpyEnforceBounds(filenames=filenames)
            #reader = Converter.numpy2vtkImporter(numpy_image)
            #reader.Update()

            reader = vtk.vtkTIFFReader()
            sa = vtk.vtkStringArray()
            #i = 0
            #while (i < 1054):
            for fname in filenames:
                #fname = os.path.join(directory,"8bit-1%04d.tif" % i)
                i = sa.InsertNextValue(fname)
                
            print ("read {} files".format( i ))
            
            reader.SetFileNames(sa)
            reader.Update()
            if number == 0:
                self.reader0 = reader
                self.loaded[0] = True
                self.menu2['menu'].setEnabled(False)
            elif number == 1:
                self.reader1 = reader
                self.loaded[1] = True
        if self.e.ErrorOccurred():
            self.displayFileErrorDialog(file)

        else:
            if self.loaded[0] and self.loaded[1]:
                # should be able to load the diff data
                if self.ROI is None:
                    print ("should select a voi")
                else:
                    self.load_difference()
            elif self.loaded[0]:
                self.vtkWidget.viewer.setInput3DData(self.reader0.GetOutput())

        self.setStatusTip('Ready')

    def createRoiDock(self):
        self.roi_panel = self.generateUIDockParameters('ROI')
        dockWidget = self.roi_panel[0]
        groupBox = self.roi_panel[5]
        groupBox.setTitle('ROI Parameters')
        formLayout = self.roi_panel[6]

        # Create validation rule for text entry
        validator = QtGui.QDoubleValidator()
        validator.setDecimals(2)
        validatorint = QtGui.QIntValidator()

        widgetno = 1

        # self.dock_labels = []
        # self.dock_entries = []
        # # extend above field
        # self.dock_labels.append( QLabel(groupBox) )
        # self.dock_labels[-1].setText("X min")
        # formLayout.setWidget(widgetno, QFormLayout.LabelRole, 
        #                      self.dock_labels[-1])
        # self.dock_entries.append( QLineEdit(groupBox) )
        # self.dock_entries[-1].setValidator(validatorint)
        # self.dock_entries[-1].setText("10")
        # formLayout.setWidget(widgetno, QFormLayout.FieldRole, 
        #                      self.dock_entries[-1])
        
        # Add submit button
        submitButton = QPushButton(groupBox)
        submitButton.setText("Create ROI from selection")
        submitButton.clicked.connect(self.read_roi_from_viewer)
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, submitButton)
        widgetno += 1

        # Add elements to layout
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)

    def read_roi_from_viewer(self):
        self.ROI = self.vtkWidget.viewer.getROIExtent()
        print (self.ROI)
        self.menu2['menu'].setEnabled(True)

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

        return (dockWidget, dockWidgetContents,
                dockContentsVerticalLayout, internalDockWidget,
                internalWidgetVerticalLayout, paramsGroupBox,
                groupBoxFormLayout)

    def load_difference(self):
        reader0 = self.reader0
        reader1 = self.reader1
        extent = self.ROI
        voi0 = vtk.vtkExtractVOI()
        voi0.SetInputData(reader0.GetOutput())
        voi0.SetVOI(*extent)
        voi0.Update()

        voi1 = vtk.vtkExtractVOI()
        voi1.SetInputData(reader1.GetOutput())
        voi1.SetVOI(*extent)
        voi1.Update()
        self.voi = [ voi0, voi1 ]

        translate = vtk.vtkImageTranslateExtent()
        translate.SetTranslation(0,0,0)
        translate.SetInputData(voi1.GetOutput())
        translate.Update()
        self.translate = translate



        cast1 = vtk.vtkImageCast()
        cast2 = vtk.vtkImageCast()
        cast1.SetInputConnection(voi0.GetOutputPort())
        cast1.SetOutputScalarTypeToFloat()
        cast2.SetInputConnection(translate.GetOutputPort())
        cast2.SetOutputScalarTypeToFloat()
        
        self.cast = [cast1,cast2]

        subtract = vtk.vtkImageMathematics()
        subtract.SetOperationToSubtract()
        # subtract.SetInput1Data(voi.GetOutput())
        # subtract.SetInput2Data(translate.GetOutput())
        subtract.SetInputConnection(1,cast1.GetOutputPort())
        subtract.SetInputConnection(0,cast2.GetOutputPort())
        
        subtract.Update()
        self.subtract = subtract

        print ("subtract type", subtract.GetOutput().GetScalarTypeAsString())
        
        stats = vtk.vtkImageHistogramStatistics()
        stats.SetInputConnection(subtract.GetOutputPort())
        stats.Update()
        print ("stats ", stats.GetMinimum(), stats.GetMaximum(), stats.GetMean(), stats.GetMedian())
        
        self.vtkWidget.viewer.setInputData(subtract.GetOutput())

    def OnKeyPressEventTranslate(self, interactor, event):
        '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''

        if interactor.GetKeyCode() not in ['b','n','m','j']:
            return
        translate = self.translate
        subtract = self.subtract
        trans = list(translate.GetTranslation())
        orientation = self.vtkWidget.viewer.GetSliceOrientation()

        viewer_translation = [0,1,2]

        if orientation == SLICE_ORIENTATION_XY:
            pass
        elif orientation == SLICE_ORIENTATION_XZ:
            viewer_translation = [0,2,1]
        elif orientation == SLICE_ORIENTATION_YZ:
            viewer_translation = [1,2,0]

        if interactor.GetKeyCode() == "j":
            # up
            trans[viewer_translation[1]] += 1
        elif interactor.GetKeyCode() == "n":
            # down
            trans[viewer_translation[1]] -= 1
        elif interactor.GetKeyCode() == "b":
            # left
            trans[viewer_translation[0]] -= 1
        elif interactor.GetKeyCode() == "m":
            # right
            trans[viewer_translation[0]] += 1
        translate.SetTranslation(*trans)
        translate.Update()
        subtract.Update()
        
        print ("current translation", trans)
        
        self.vtkWidget.viewer.setInputData(subtract.GetOutput())

def main():
    err = vtk.vtkFileOutputWindow()
    err.SetFileName("viewer.log")
    vtk.vtkOutputWindow.SetInstance(err)
    
    App = QApplication(sys.argv)
    gui = RegistrationGUI()
    gui.setApp(App)
    sys.exit(App.exec())

if __name__ == "__main__":
    main()