

import os
import PySide2
from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import (QAction, QComboBox,
                               QDockWidget,
                               QLabel,
                               QMainWindow,  QTabWidget)
import numpy as np

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt

from functools import partial

import glob

from idvc.pointcloud_conversion import  PointCloudConverter

'''
Classes for dealing with and displaying results from DVC runs
'''

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
                ax = self.figure.add_subplot(numRows, numColumns, plotNum)
                
                if row ==1:
                    ax.set_title("Subvolume Size:" + str(result.subvol_size) )
                if column == 1:
                    text = str(result.subvol_points) 
                    ax.set_ylabel(text + " " + "Points in subvol")

            else:
                plotNum = plotNum + 1
                ax = self.figure.add_subplot(numRows, numColumns, plotNum)
    
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
        
class RunResults(object):
    def __init__(self, file_name):
        
        self.points = None

        disp_file_name = file_name + ".disp"
        stat_file_name = file_name + ".stat"

        with open(stat_file_name,"r") as stat_file:
            
            count = 0
            offset = 0
            for line in stat_file:
                if count == 9:
                    if line.split('\t')[0] == "vol_endian":
                        offset = 1

                if count == 14 + offset:
                    self.subvol_geom = str(line.split('\t')[1])
                if count == 15 + offset:
                    self.subvol_size = round(int(line.split('\t')[1]))
                if count == 16 +offset:
                    self.subvol_points = int(line.split('\t')[1])
                if count == 20 + offset:
                    self.disp_max = int(line.split('\t')[1])
                if count == 21 + offset:
                    self.num_srch_dof = int(line.split('\t')[1])
                if count == 22 + offset:
                    self.obj_function = str(line.split('\t')[1])
                if count == 23 + offset:
                    self.interp_type = str(line.split('\t')[1])
                if count == 25 + offset:
                    self.rigid_trans = [int(line.split('\t')[1]),int(line.split('\t')[2]), int(line.split('\t')[3])]
                # if count == 26 + offset:
                #     self.basin_radius = int(line.split('\t')[1])
                # if count == 27 + offset:
                #     self.subvol_aspect = [int(line.split('\t')[1]),int(line.split('\t')[2]), int(line.split('\t')[3])]
                count+=1

        plot_titles_dict = {
            'objmin': "Objective Minimum", 'u': "Displacement in x", 'v':"Displacement in y", 'w':"Displacement in z",
            'phi':"Change in phi",'the':"Change in theta", 'psi':"Change in psi"}

        with open(disp_file_name) as f:
            # first 4 columns are: n, x, y, z, status - we don't want these
            self.plot_titles = f.readline().split()[5:]
            self.plot_titles = [plot_titles_dict.get(text, text) for text in self.plot_titles]

        
        self.disp_file = disp_file_name

        self.title =  str(self.subvol_points) + " Points in Subvolume," + " Subvolume Size: " + str(self.subvol_size)

    def __str__(self):

        a = "subvol_size {}".format(self.subvol_size)
        n = "subvol_points {}".format(self.subvol_points)
        return "RunResults:\n{}\n{}".format(a , n)