import PySide2
from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from idvc.pointcloud_conversion import PointCloudConverter
from functools import partial
import shutil
import os
import tempfile
from eqt.threading import Worker




class SingleRunResultsWidget(QtWidgets.QWidget):
    '''creates a dockable widget which will display results from a single run of the DVC code
    '''
    def __init__(self, parent, plot_data, displ_wrt_point0 = False):
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

        self.CreateHistogram(plot_data, displ_wrt_point0)

    def CreateHistogram(self, result, displ_wrt_point0):
        displ = np.asarray(
        PointCloudConverter.loadPointCloudFromCSV(result.disp_file,'\t')[:]
        )
        if displ_wrt_point0:
            point0_disp = [displ[0][6],displ[0][7], displ[0][8]]
            for count in range(len(displ)):
                for i in range(3):
                    displ[count][i+6] = displ[count][i+6] - point0_disp[i]

        plot_data = [displ[:,i] for i in range(5, displ.shape[1])]

        numGraphs = len(plot_data)
        if numGraphs <= 3:
            numRows = 1
        else:
            numRows = np.round(np.sqrt(numGraphs))
        numColumns = np.ceil(numGraphs/numRows)

        plotNum = 0
        for array in plot_data:
            plotNum = plotNum + 1
            ax = self.figure.add_subplot(int(numRows), int(numColumns), int(plotNum))
            ax.set_ylabel("")
            #ax.set_xlabel(plot_titles[plotNum-1])
            ax.set_title(result.plot_titles[plotNum-1])
            ax.hist(array,20)

        plt.tight_layout() # Provides proper spacing between figures

        self.canvas.draw() 

class SummaryGraphsWidget(QtWidgets.QWidget):
    '''creates a dockable widget which will display results from all runs in a bulk run
    '''
    def __init__(self, parent, result_list, displ_wrt_point0 = False):
        super().__init__()
        self.parent = parent

        #Layout
        self.layout = QtWidgets.QGridLayout()
        #self.layout.setSpacing(1)
        self.layout.setAlignment(Qt.AlignTop)

        widgetno=0

        if len(result_list) >=1:
            result = result_list[0] #These options were the same for all runs:

            self.results_details_label = QLabel(self)
            self.results_details_label.setText("Subvolume Geometry: {subvol_geom}\n\
Maximum Displacement: {disp_max}\n\
Degrees of Freedom: {num_srch_dof}\n\
Objective Function: {obj_function}\n\
Interpolation Type: {interp_type}\n\
Rigid Body Offset: {rigid_trans}".format(subvol_geom=result.subvol_geom, \
            disp_max=result.disp_max, num_srch_dof=str(result.num_srch_dof), obj_function=result.obj_function, \
            interp_type=result.interp_type, rigid_trans=str(result.rigid_trans)))
            self.layout.addWidget(self.results_details_label,widgetno,0,5,1)
            self.results_details_label.setAlignment(Qt.AlignTop)        
            widgetno+=1


        self.label = QLabel(self)
        self.label.setText("Select which variable would like to compare: ")
        self.layout.addWidget(self.label,widgetno,1)

        self.combo = QComboBox(self)
        self.combo.addItems(result.plot_titles)
        self.layout.addWidget(self.combo,widgetno,2)  
        widgetno+=1

        self.label1 = QLabel(self)
        self.label1.setText("Select which parameter you would like to compare: ")
        self.layout.addWidget(self.label1,widgetno,1)  
        
        self.combo1 = QComboBox(self)
        self.param_list = ["All","Sampling Points in Subvolume", "Subvolume Size"]
        self.combo1.addItems(self.param_list)
        self.layout.addWidget(self.combo1,widgetno,2)
        widgetno+=1

        self.subvol_points=[]
        self.subvol_sizes=[]

        for result in result_list:
            if result.subvol_points not in self.subvol_points:
                self.subvol_points.append(result.subvol_points)
            if result.subvol_size not in self.subvol_sizes:
                self.subvol_sizes.append(result.subvol_size)
        self.subvol_points.sort()
        self.subvol_sizes.sort()

        self.secondParamLabel = QLabel(self)
        self.secondParamLabel.setText("Subvolume size:")
        self.layout.addWidget(self.secondParamLabel,widgetno,1)
        
        self.secondParamCombo = QComboBox(self)
        self.secondParamList = [str(i) for i in self.subvol_sizes]
        self.secondParamCombo.addItems(self.secondParamList)
        self.layout.addWidget(self.secondParamCombo,widgetno,2)
        widgetno+=1

        self.combo1.currentIndexChanged.connect(self.showSecondParam)
        self.secondParamLabel.hide()
        self.secondParamCombo.hide()

        self.button = QtWidgets.QPushButton("Plot Histograms")
        self.button.clicked.connect(partial(self.CreateHistogram,result_list, displ_wrt_point0))
        self.layout.addWidget(self.button,widgetno,2)
        widgetno+=1

        self.figure = plt.figure()
        
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.toolbar,widgetno,0,1,3)
        widgetno+=1
        self.layout.addWidget(self.canvas,widgetno,0,3,3)
        widgetno+=1

        self.setLayout(self.layout)

    def showSecondParam(self):
        index = self.combo1.currentIndex()
        if index ==0:
            self.secondParamLabel.hide()
            self.secondParamCombo.hide()

        elif index == 1:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Subvolume Size:")
            self.secondParamCombo.clear()
            self.secondParamCombo.addItems([str(i) for i in self.subvol_sizes])

        elif index == 2:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Points in Subvolume:")
            self.secondParamCombo.clear()
            newList = []
            self.secondParamCombo.addItems([str(i) for i in self.subvol_points])   
        
    
    def CreateHistogram(self, result_list, displ_wrt_point0):

        self.figure.clear()

        index = self.combo1.currentIndex()
        
        points_list = []

        resultsToPlot= []

        displacements = []

        for result in result_list:
            displ = np.asarray(
            PointCloudConverter.loadPointCloudFromCSV(result.disp_file,'\t')[:]
            )
            if displ_wrt_point0:
                point0_disp = [displ[0][6],displ[0][7], displ[0][8]]
                for count in range(len(displ)):
                    for i in range(3):
                        displ[count][i+6] = displ[count][i+6] - point0_disp[i]

            no_points = np.shape(displ[0])

            if no_points not in points_list:
                points_list.append(no_points)

            if index == 1: # Points in subvolume is compared
                if result.subvol_size != float(self.secondParamCombo.currentText()):
                    pass

            elif index ==2:
                if result.subvol_points != float(self.secondParamCombo.currentText()):
                    pass
            
            resultsToPlot.append(result)
            displacements.append(displ)

        points_list.sort()

        if index ==0:
            numRows = len(self.subvol_points)
            numColumns = len(self.subvol_sizes)

        else:
            if len(resultsToPlot) <= 3:
                numRows = 1
            else:
                numRows = np.round(np.sqrt(len(resultsToPlot)))
            numColumns = np.ceil(len(resultsToPlot)/numRows)

        plotNum = 0
        for i, result in enumerate(resultsToPlot):
            if index ==0:
                row = self.subvol_points.index(result.subvol_points) + 1
                column= self.subvol_sizes.index(result.subvol_size) + 1
                plotNum = (row-1)*numColumns + column
                ax = self.figure.add_subplot(int(numRows), int(numColumns), int(plotNum))
                
                if row ==1:
                    ax.set_title("Subvolume Size:" + str(result.subvol_size) )
                if column == 1:
                    text = str(result.subvol_points) 
                    ax.set_ylabel(text + " " + "Points in subvol")

            else:
                plotNum = plotNum + 1
                ax = self.figure.add_subplot(int(numRows), int(numColumns), int(plotNum))
    
                if index ==1:
                    text = str(result.subvol_points) 
                if index ==2:
                    text = str(result.subvol_size) 
                ax.set_ylabel(text + " " + self.combo1.currentText())

            plot_data = [displacements[i][:,k] for k in range(5, displacements[i].shape[1])]

            #get variable to display graphs for:
            ax.hist(plot_data[self.combo.currentIndex()], 20)

        self.figure.suptitle(self.combo.currentText(),size ="large")

        plt.tight_layout() # Provides proper spacing between figures
        plt.subplots_adjust(top=0.88) # Means heading doesn't overlap with subplot titles
        self.canvas.draw()


class SaveObjectWindow(QtWidgets.QWidget):
    '''a window which will appear when saving a mask or pointcloud
    '''
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent, object_type, save_only):
        super().__init__()

        #print(save_only)

        self.parent = parent
        self.object = object_type

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
            shutil.copyfile(os.path.join(tempfile.tempdir, self.parent.mask_file), os.path.join(tempfile.tempdir, "Masks", filename))
            self.parent.mask_parameters['masksList'].addItem(filename)
            self.parent.mask_details[filename] = self.parent.mask_details['current']
            #print(self.parent.mask_details)

            self.parent.mask_parameters['loadButton'].setEnabled(True)
            self.parent.mask_parameters['masksList'].setEnabled(True)


            if not save_only:
                #print("Not save only")
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
            #print(self.parent.pointCloud_details)
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
