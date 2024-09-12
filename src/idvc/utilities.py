import PySide2
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import numpy as np
import os


        
class RunResults(object):
    def __init__(self, folder):
        file_name = os.path.join(folder, os.path.basename(folder))
        self.points = None
        disp_file_name = file_name + ".disp"
        stat_file_name = file_name + ".stat"
        print("disp file name",disp_file_name)

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

        data_label_dict = {
            'objmin': "Objective minimum", 'u': "Displacement x component (pixels)", 'v':"Displacement y component (pixels)", 'w':"Displacement z component (pixels)",
            'phi':"Change in phi",'the':"Change in theta", 'psi':"Change in psi"}

        with open(disp_file_name) as f:
            # first 4 columns are: n, x, y, z, status - we don't want these
            self.data_label = f.readline().split()[5:]
            self.data_label = [data_label_dict.get(text, text) for text in self.data_label]

        self.disp_file = disp_file_name
        self.run_name = os.path.basename(os.path.dirname(folder))

        self.title =  str(self.subvol_points) + "," + str(self.subvol_size)

    def __str__(self):

        a = "subvol_size {}".format(self.subvol_size)
        n = "subvol_points {}".format(self.subvol_points)
        return "RunResults:\n{}\n{}".format(a , n)

def generateUIDockParameters(self, title): #copied from dvc_configurator.py
    '''creates a dockable widget with a form layout group to add things to

    basically you can add widget to the returned groupBoxFormLayout and paramsGroupBox
    The returned dockWidget must be added with
    self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
    '''
    dockWidget = QDockWidget(self)
    dockWidget.setFeatures(QDockWidget.NoDockWidgetFeatures)
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
    internalWidgetVerticalLayout.setAlignment(Qt.AlignTop)

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

class PrintCallback(object):
    '''Class to handle the emit call when no callback is provided'''
    def emit(self, *args, **kwargs):
        print (args, kwargs)

def reduce_displ(raw_displ, min_size, max_size, pzero=False):
    '''filter the diplacement vectors based on their size'''
    offset = 6 # 6 in the case of the iDVC
    
    # sizes = []
    # dmin = np.inf
    # dmax = 0.
    # for el in raw_displ:
    #     size = 0
    #     for i in range(3):
    #         #calculate size of vector
    #         size += el[i+offset]*el[i+offset]
    #     size = np.sqrt(size)
    #     if size > dmax:
    #         dmax = size
    #     if size < dmin:
    #         dmin = size
    #     sizes.append(size)
    vec = np.asarray(raw_displ)[:,offset:offset+3]
    if pzero:
        vec -= np.asarray(raw_displ[0][offset:offset+3])

    sizes = np.sqrt( np.sum( np.power(vec, 2), axis=1) )

    dmin = sizes.min()
    dmax = sizes.max()
    if min_size is None and max_size is None:
        displ = raw_displ
    else:
        displ = []
        if pzero:
            for i in range(len(raw_displ)):
                size = sizes[i]
                if size > min_size  and size < max_size :
                    line = raw_displ[i]
                    line[offset:offset+3] -= vec[0]
                    displ.append(line)
        else:
            for i in range(len(raw_displ)):
                size = sizes[i]
                if size > min_size  and size < max_size :
                    displ.append(raw_displ[i])
    displ = np.asarray(displ)
    return displ, dmin, dmax