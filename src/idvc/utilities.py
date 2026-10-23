import qtpy
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
import numpy as np
import os
from eqt.ui.NoBorderScrollArea import NoBorderScrollArea

import re
import sys

def parse_stat_file(filepath):
    data = {}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    in_echo = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line == '### echo of the input file for this run':
            in_echo = True
            continue
        elif line == '### end of input file echo':
            in_echo = False
            continue
            
        if in_echo:
            parts = line.split()
            if not parts:
                continue
            key = parts[0]
            values = parts[1:]
            
            parsed_values = []
            for v in values:
                try:
                    if '.' in v or 'e' in v.lower():
                        parsed_values.append(float(v))
                    else:
                        parsed_values.append(int(v))
                except ValueError:
                    parsed_values.append(v)
            
            if len(parsed_values) == 1:
                data[key] = parsed_values[0]
            elif len(parsed_values) > 1:
                data[key] = parsed_values
                
        else:
            # Parse the post-echo summary stats
            try:
                if line.startswith("Point Cloud contains"):
                    m = re.search(r'contains (\d+) points', line)
                    if m: data['point_cloud_points'] = int(m.group(1))
                
                elif line.startswith("bounding box min"):
                    m = re.search(r'\[(.*?)\]', line)
                    if m: data['bounding_box_min'] = [int(x) for x in m.group(1).split()]
                    
                elif line.startswith("bounding box max"):
                    m = re.search(r'\[(.*?)\]', line)
                    if m: data['bounding_box_max'] = [int(x) for x in m.group(1).split()]
                    
                elif line.startswith("running under dvc code version:"):
                    parts = line.split(": ")
                    if len(parts) > 1:
                        data['dvc_code_version'] = parts[1].strip()
                    
                elif line.startswith("Run start:"):
                    data['run_start'] = line.split(":\t")[1].strip() if ":\t" in line else line.replace("Run start:", "").strip()
                    
                elif line.startswith("Run finish:"):
                    data['run_finish'] = line.split(":\t")[1].strip() if ":\t" in line else line.replace("Run finish:", "").strip()
                    
                elif "points processed in" in line:
                    m = re.search(r'(\d+) points processed in (\d+) seconds', line)
                    if m:
                        data['points_processed'] = int(m.group(1))
                        data['time_seconds'] = int(m.group(2))
                        
                elif line.endswith("sec/pt"):
                    parts = line.split()
                    if parts:
                        data['sec_per_pt'] = float(parts[0])
                    
                elif line.endswith("pt/sec"):
                    parts = line.split()
                    if parts:
                        data['pt_per_sec'] = float(parts[0])
                    
                elif line.startswith("number successful"):
                    m = re.search(r'number successful = (\d+)\s+\((.*?)\%\)', line)
                    if m:
                        data['num_successful'] = int(m.group(1))
                        data['pct_successful'] = float(m.group(2))
                        
                elif line.startswith("number range fail"):
                    m = re.search(r'number range fail = (\d+)\s+\((.*?)\%\)', line)
                    if m:
                        data['num_range_fail'] = int(m.group(1))
                        data['pct_range_fail'] = float(m.group(2))
                        
                elif line.startswith("number convg fail"):
                    m = re.search(r'number convg fail = (\d+)\s+\((.*?)\%\)', line)
                    if m:
                        data['num_convg_fail'] = int(m.group(1))
                        data['pct_convg_fail'] = float(m.group(2))
            except (ValueError, IndexError, AttributeError) as e:
                print(f"Warning: Failed to parse line '{line}'. Error: {e}", file=sys.stderr)

    return data
        
class RunResults(object):
    def __init__(self, folder):
        file_name = os.path.join(folder, os.path.basename(folder))
        self.points = None
        disp_file_name = file_name + ".disp"
        stat_file_name = file_name + ".stat"

        stat_data = parse_stat_file(stat_file_name)
        self.stat_data = stat_data
        self.subvol_geom = stat_data.get('subvol_geom')
        self.subvol_size = stat_data.get('subvol_size')
        self.subvol_points = stat_data.get('subvol_npts')
        self.disp_max = stat_data.get('disp_max')
        self.num_srch_dof = stat_data.get('num_srch_dof')
        self.obj_function = stat_data.get('obj_function')
        self.interp_type = stat_data.get('interp_type')
        self.rigid_trans = stat_data.get('rigid_trans')
        

        data_label_dict = {
            'objmin': "Objective minimum", 'u': "Displacement x component", 'v':"Displacement y component", 'w':"Displacement z component",
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



def generateUIDockParameters(self, title, scrollable = True): #copied from dvc_configurator.py
    '''creates a dockable widget with a form layout group to add things to

    basically you can add widget to the returned groupBoxFormLayout and paramsGroupBox
    The returned dockWidget must be added with
    self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
    A scoll area can be added to the widget by setting the flag to True.
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

    if scrollable == True:
        scrollArea = NoBorderScrollArea(dockWidgetContents)
        dockWidget.setWidget(scrollArea)
    else:
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