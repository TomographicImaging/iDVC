import os
import numpy as np
from PyQt5 import QtCore
from datetime import datetime

import json

import sys

count = 0

blank_config = '''###############################################################################
#																	
#
#		example dvc process control file		
#
#
###############################################################################

# all lines beginning with a # character are ignored
# some parameters are conditionally required, depending on the setting of other parameters
# for example, if subvol_thresh is off, the threshold description parameters are not required

### file names

reference_filename	{reference_filename}		### reference tomography image volume
correlate_filename	{correlate_filename}		### correlation tomography image volume

point_cloud_filename	{point_cloud_filename}	### file of search point locations
output_filename		{output_filename}		### base name for output files

### description of the image data files, all must be the same size and structure

vol_bit_depth		{vol_bit_depth}			### 8 or 16
vol_hdr_lngth		{vol_hdr_lngth}		### fixed-length header size, may be zero
vol_wide		{vol_wide}			### width in pixels of each slice
vol_high		{vol_high}			### height in pixels of each slice
vol_tall		{vol_tall}			### number of slices in the stack
vol_endian		{vol_endian}        ### big or little endian byte ordering

### parameters defining the subvolumes that will be created at each search point

subvol_geom		{subvol_geom}			### cube, sphere
subvol_size		{subvol_size}			### side length or diameter, in voxels
subvol_npts		{subvol_npts}			### number of points to distribute within the subvol

subvol_thresh		{subvol_thresh}			### on or off, evaluate subvolumes based on threshold
gray_thresh_min		{gray_thresh_min}			### lower limit of a gray threshold range if subvol_thresh is on
gray_thresh_max		{gray_thresh_max}			### upper limit of a gray threshold range if subvol_thresh is on
min_vol_fract		{min_vol_fract}			### only search if subvol fraction is greater than

### required parameters defining the basic the search process

disp_max		{disp_max}			### in voxels, used for range checking and global search limits
num_srch_dof		{num_srch_dof}			### 3, 6, or 12
obj_function		{obj_function}			### sad, ssd, zssd, nssd, znssd 
interp_type		{interp_type}		### trilinear, tricubic

### optional parameters tuning and refining the search process

rigid_trans		{rigid_trans}		### rigid body offset of target volume, in voxels
basin_radius		{basin_radius}			### coarse-search resolution, in voxels, 0.0 = none
subvol_aspect		{subvol_aspect}		### subvolume aspect ratio
'''

def update_progress(process):
    global count
    count+=1
    print("{:.0f} \n".format(count/(total_points+required_runs)*100))
    string = process.readLine()
    #line = str(string,"utf-8")
    #print(line)
    #print ("DVC update", string)
    sys.stdout.flush()

def finished_run(exitCode, exitStatus):
    #print ("DVC command ended.", exitCode, exitStatus)
    global runs_completed
    runs_completed+=1

    if( runs_completed >=  required_runs): #and  cancelled == False):

        runs_completed = 0


working_directory = os.getcwd()
#print ("We are here ", working_directory)
os.chdir(working_directory)

runs_completed = 0

input_file = sys.argv[1]


with open(input_file) as tmp:
        config = json.load(tmp)

subvolume_points = config['subvolume_points'] 
radii = config['cloud_radii']
points = int(config['points'])

roi_files = config['roi_files']
reference_file = config['reference_file']
correlate_file = config['correlate_file']
vol_bit_depth = int(config['vol_bit_depth'])
vol_hdr_lngth = int(config['vol_hdr_lngth'])

endian = config['vol_endian']

dims= config['dims'] #image dimensions

subvol_geom = config['subvol_geom']

subvol_npts = config['subvol_npts']

disp_max = int(config['disp_max'][0]) #TODO: need to change
dof = int(config['dof'])
obj = config['obj']
interp_type = config['interp_type']

rigid_trans = config['rigid_trans']

run_folder = config['run_folder']

#running the code:

required_runs = len(subvolume_points)*len(radii)   

#print("Required runs", required_runs)


exe_file = "dvc.exe"


# Process to run the DVC executable:
process = QtCore.QProcess()
process.setWorkingDirectory(run_folder)
process.finished.connect(finished_run)
# process.setStandardOutputFile(os.path.join(run_folder, "QProcess_Output.txt")) #use in testing to get errors from QProcess
# process.setStandardErrorFile(os.path.join(run_folder, "QProcess_Error.txt"))

process.readyRead.connect(lambda: update_progress(process))

# blank_config_file = open("dvc_config_template.txt","r")
# blank_config = blank_config_file.read()
# blank_config_file.close()


total_points = 0
for cloud in roi_files:
    i=0
    with open(cloud) as f:
        for i, l in enumerate(f):
            pass
    i+=1
    #print(i)
    if i < points:
        total_points += i
    else:
        total_points += points

#print("Total points", total_points)



file_count = -1
for roi_file in roi_files:
    file_count +=1
    pointcloud_diameter = int(radii[file_count])*2
    #print(roi_file)
    entire_central_grid = open(roi_file, "r")
        
    line_num = 1
    distances = []
    for line in entire_central_grid:
        line_array = line.split()

        if line_num == 1:
            point1_x = float(line_array[1]) #was previously int, not sure which is correct
            point1_y = float(line_array[2])
            point1_z = float(line_array[3])
        distance = np.sqrt(np.square(float(line_array[1]) - point1_x) + np.square(float(line_array[2])-point1_y) + np.square(float(line_array[3])-point1_z))

        distances.append(distance)
        line_num+=1

    entire_central_grid.close()

    lines_to_write = []

    for i in range(points):
        index = distances.index(min(distances))
        lines_to_write.append(index)
        distances[index]=max(distances)+1

    selected_central_grid = open(os.path.join(os.path.abspath(run_folder), "grid_input.roi"),"w")
    entire_central_grid = open(roi_file, "r")

    i=0
    for line in entire_central_grid:
        if i in lines_to_write:
            selected_central_grid.write(line)
        i+=1

    selected_central_grid.close()
    entire_central_grid.close()


    for subvolume_point in subvolume_points:
        now = datetime.now()
        dt_string = now.strftime("%d%m%Y_%H%M%S")
        new_output_filename = "%s/dvc_result_%s" %( run_folder,dt_string)
        config_filename = "%s/dvc_config_%s" %( run_folder,dt_string)
        config_filename = config_filename + ".txt"
        param_file = os.path.abspath(config_filename)
        
        outfile = new_output_filename #.strip('/') TODO: allow file to be saved in base working directory
        #print(outfile)

        config =  blank_config.format(
            reference_filename=  reference_file, # reference tomography image volume
            correlate_filename=  correlate_file, # correlation tomography image volume
            point_cloud_filename=os.path.join(run_folder, 'grid_input.roi'),
            output_filename= new_output_filename,
            vol_bit_depth=  vol_bit_depth, # get from ref, 8 or 16
            vol_hdr_lngth=vol_hdr_lngth,# get from ref, fixed-length header size, may be zero
            vol_wide= dims[0], # number of x slices
            vol_high= dims[1], # number of y slices
            vol_tall= dims[2], #number of z slices
            vol_endian = endian,
            subvol_geom=  subvol_geom,
            subvol_size=  pointcloud_diameter, #subvolume diameter
            subvol_npts= subvolume_point,
            subvol_thresh='off',
            gray_thresh_min='27',
            gray_thresh_max='127',
            min_vol_fract='0.2',
            disp_max=  disp_max, #38 for test image
            num_srch_dof=  dof, #6 for test image
            obj_function=  obj, 
            interp_type=  interp_type, #tricubic for test image
            rigid_trans= rigid_trans, #translation between ref and cor - determined from image registration
            basin_radius='0.0',
            subvol_aspect='1.0 1.0 1.0') # image spacing

        config_file = open(param_file,"w")
        config_file.write(config)
        config_file.close()
    
        #if run_count == len( subvolume_points):
        process.start( exe_file , [ param_file ] )          
        cancelled=False

        process.waitForFinished(msecs=2147483647) #wait for process to finish before doing next run

