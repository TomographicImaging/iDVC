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
import numpy as np
from PySide2 import QtCore
from datetime import datetime
from PySide2.QtWidgets import QMessageBox
import json
import time
import shutil
import platform
from .io import save_tiff_stack_as_raw, save_nxs_as_raw

class PrintCallback(object):
    '''Class to handle the emit call when no callback is provided'''
    def emit(self, *args, **kwargs):
        print (args, kwargs)

count = 0
runs_completed = 0

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
num_points_to_process   {num_points_to_process}  ### Number of points in the point cloud to process
starting_point  {starting_point}    ### x,y,z location of starting point for DVC analysis
'''

def update_progress(main_window, process, total_points, required_runs, run_succeeded, start_time, num_points_to_process):
    # print("Required runs", required_runs)
    while(process.canReadLine()):
        #print("READ")
        string = process.readLine()  
        line = str(string, "utf-8")
        
        global count
        count+=1
        #print("{:.0f} \n".format(count/(total_points+3*required_runs)*100))
        if hasattr(main_window, 'progress_window'):
            #print(count/(total_points+3*required_runs)*100)
            # main_window.progress_window.setValue(count/(total_points+3*required_runs)*100)

            try:
                # try to infer the number of points processed from the output of the dvc executable
                num_processed_points = int(string.split('/')[0])
                etcs = 0
                prog = 0
                if num_processed_points > 0:
                    prog = int(num_processed_points/num_points_to_process*100)-1
                    etcs = ((time.time()-start_time) * num_points_to_process / num_processed_points) - (time.time()-start_time)
                try:
                    etc = time.strftime("%H:%M:%S s", time.gmtime(etcs))
                except:
                    etc = 'Error estimating time to completion'

                ETC_line = "\nEstimated time to completion of this step {} ".format(etc)
            except ValueError:
                num_processed_points = 0
                prog = 0
                ETC_line = ''
                
            main_window.progress_window.setValue(prog)
            label_text = main_window.progress_window.labelText().split("\n")[0]
            main_window.progress_window.setLabelText(
                    "{}\n{}{}".format(label_text, line, ETC_line))
                
        if line[:11] == "Input Error":
            run_succeeded = False
            if hasattr(main_window, 'progress_window'):
                main_window.progress_window.setValue(100)
            if hasattr(main_window, 'alert'):
                main_window.alert.close() #finish fn triggers before update_progress so has already made an alert saying it succeeded
            displayFileErrorDialog(main_window, line, "Error")
            process.kill()
            return
    #sys.stdout.flush()

def create_progress_window(main_window, title, text, max = 100, cancel = None):
        main_window.progress_window = QProgressDialog(text, "Cancel", 0,max, main_window, QtCore.Qt.Window) 
        main_window.progress_window.setWindowTitle(title)
        main_window.progress_window.setWindowModality(QtCore.Qt.ApplicationModal) #This means the other windows can't be used while this is open
        main_window.progress_window.setMinimumDuration(0.1)
        main_window.progress_window.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        main_window.progress_window.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)
        if cancel is None:
            main_window.progress_window.setCancelButton(None)
        else:
            main_window.progress_window.canceled.connect(cancel)

def displayFileErrorDialog(main_window, message, title):
    msg = QMessageBox(main_window)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    #msg.setDetailedText(main_window.e.ErrorMessage())
    msg.exec_()

def cancel_run(main_window, process, run_succeeded):
    
    if not run_succeeded:
        # print ("run cancelled?")
        process.kill()
        main_window.alert = QMessageBox(QMessageBox.NoIcon,"Cancelled","The run was cancelled.", QMessageBox.Ok)  
        main_window.alert.show()
        run_succeeded = False
    # else:
    #     print ("all OK, all processes ended")


def finished_run(main_window, exitCode, exitStatus, process = None, required_runs = 1, run_succeeded = False, finish_fn = None):
    global runs_completed
    runs_completed+=1
    # print ("DVC command ended.", exitCode, exitStatus)
    # print("Completed, ", runs_completed)

    if run_succeeded:
        if runs_completed == required_runs:
            if hasattr(main_window, 'progress_window'):
                main_window.progress_window.close()
            main_window.alert = QMessageBox(QMessageBox.NoIcon,"Success","The DVC code ran successfully.", QMessageBox.Ok) 
            main_window.alert.show()
            if finish_fn is not None:
                finish_fn()
            runs_completed = 0
            global count
            count = 0
    #print ("DVC command ended.", exitCode, exitStatus)
    

    # if( runs_completed >=  required_runs): #and  cancelled == False):
    #     runs_completed = 0
    # print("did")

class DVC_runner(object):
    def __init__(self, main_window, input_file, finish_fn, run_succeeded, session_folder):
        # print("The session folder is", session_folder)
        self.main_window = main_window
        self.input_file = input_file
        self.finish_fn = finish_fn
        self.run_succeeded = run_succeeded
        self.session_folder = session_folder

    def set_up(self, *args, **kwargs):
        '''This function sets up the DVC run, creating the run configurations and setting up the run folders.
        
        Parameters:
        -----------
        *args: not used
        **kwargs: 
            message_callback: callback function for messages
            progress_callback: callback function for progress updates

        Returns:
        --------
        None

        This function reads a json file containing the run configuration and creates the run configurations.
        The json file contains the following:
        - subvolume_points: list of number of points to process at each subvolume
        - subvolume_sizes: list of subvolume sizes, if not an integer multiple runs will be created
        - points: number of points to process in the point cloud
        - roi_files: list of point cloud files
        - reference_file: reference image volume
        - correlate_file: correlation image volume
        - vol_bit_depth: bit depth of the image volumes. If loading an image not of type int8 or int16, the image will be converted to uint16.
        - vol_hdr_lngth: header length of the image volumes
        - dims: dimensions of the image volumes
        - subvol_geom: geometry of the subvolume, either cube or sphere
        - subvol_npts: number of points in the subvolume, not used
        - disp_max: maximum displacement in voxels
        - dof: number of parameters in the optimisation, 3,6, or 12
        - obj: objective function, either sad, ssd, zssd, nssd, or znssd
        - interp_type: interpolation type, either trilinear or tricubic
        - run_folder: folder to save the run results and configurations
        - rigid_trans: rigid translation between the reference and correlation volumes
        - point0_world_coordinate: world coordinates of the starting point for the DVC analysis
        '''
        self.processes = []
        self.process_num = 0
        message_callback = kwargs.get('message_callback', PrintCallback())
        progress_callback = kwargs.get('progress_callback', PrintCallback())  
        
        # created in dvc_interface create_run_config
        with open(self.input_file) as tmp:
            config = json.load(tmp)

        subvolume_points = config['subvolume_points'] 
        subvolume_sizes = config['subvolume_sizes']
        points = int(config['points'])
        num_points_to_process = points

        roi_files = config['roi_files']
        reference_file = config['reference_file']
        correlate_file = config['correlate_file']
        
        progress_callback.emit(10)
        # Convert to raw if files are a list of tiffs
        if isinstance(reference_file, (list, tuple)):
            base = os.path.abspath(self.session_folder)
            results_folder = os.path.dirname(os.path.join(base, config['run_folder']))
            raw_reference_file_fname = os.path.join(results_folder, 'reference.raw')
            if not os.path.exists(raw_reference_file_fname):
                message_callback.emit("Converting reference file to raw format")
                save_tiff_stack_as_raw(reference_file, raw_reference_file_fname, progress_callback, 10, 50)
            reference_file = raw_reference_file_fname
        elif reference_file.endswith(('.nxs', '.h5', '.hdf5')):
            base = os.path.abspath(self.session_folder)
            results_folder = os.path.dirname(os.path.join(base, config['run_folder']))
            raw_reference_file_fname = os.path.join(results_folder, 'reference.raw')
            if not os.path.exists(raw_reference_file_fname):
                message_callback.emit("Converting reference file to raw format")
                save_nxs_as_raw(reference_file, self.main_window.hdf5_dataset_path, raw_reference_file_fname)
            reference_file = raw_reference_file_fname
        progress_callback.emit(50)

        if isinstance(correlate_file, (list, tuple)):
            base = os.path.abspath(self.session_folder)
            results_folder = os.path.dirname(os.path.join(base, config['run_folder']))
            raw_correlate_file_fname = os.path.join(results_folder, 'correlate.raw')
            if not os.path.exists(raw_correlate_file_fname):
                message_callback.emit("Converting correlate file to raw format")
                save_tiff_stack_as_raw(correlate_file, raw_correlate_file_fname, progress_callback, 50, 90)
            correlate_file = raw_correlate_file_fname

        elif correlate_file.endswith(('.nxs', '.h5', '.hdf5')):
            base = os.path.abspath(self.session_folder)
            results_folder = os.path.dirname(os.path.join(base, config['run_folder']))
            raw_correlate_file_fname = os.path.join(results_folder, 'correlate.raw')
            if not os.path.exists(raw_correlate_file_fname):
                message_callback.emit("Converting correlate file to raw format")
                save_nxs_as_raw(correlate_file, self.main_window.hdf5_dataset_path, raw_correlate_file_fname)
            correlate_file = raw_correlate_file_fname

        progress_callback.emit(90)

        message_callback.emit("Creating run configurations")
        vol_bit_depth = int(config['vol_bit_depth'])
        if vol_bit_depth not in [8, 16]:
            # the data will be converted to 16 bit by save_tiff_stack_as_raw
            # it won't work with other formats
            vol_bit_depth = 16
        vol_hdr_lngth = int(config['vol_hdr_lngth'])

        if 'vol_endian' in config:
            endian = config['vol_endian']
        else:
            endian = None

        dims= config['dims'] #image dimensions

        subvol_geom = config['subvol_geom']

        subvol_npts = config['subvol_npts']

        disp_max = int(config['disp_max'][0]) #TODO: need to change
        dof = int(config['dof'])
        obj = config['obj']
        interp_type = config['interp_type']

        rigid_trans = config['rigid_trans']
        starting_point = config['point0_world_coordinate']

        # Change directory into the folder where the run will be saved:
        os.chdir(self.session_folder)
        # this is the one directory we created where we will run the dvc command in
        # we want to change this to create multiple directories first and then run through
        # all the directory created https://github.com/TomographicImaging/iDVC/issues/37
        # see also https://github.com/TomographicImaging/iDVC/pull/69
        self.run_folder = config['run_folder']

        #running the code:

        # this should be renamed to num_optimisations
        required_runs = len(subvolume_points)*len(subvolume_sizes)   

        # check for the extension
        if platform.system() in ['Linux', 'Darwin']:    
            exe_file = 'dvc'
        elif platform.system() == 'Windows':
            exe_file = 'dvc.exe'
        else:
            raise ValueError('Not supported platform, ', platform.system())
        
        total_points = 0
        for cloud in roi_files:
            i=0
            with open(cloud) as f:
                for i, l in enumerate(f):
                    pass
            i+=1
            if i < points:
                total_points += i
            else:
                total_points += points

        total_points = total_points * len(subvolume_points)

        #print("Total points", total_points)

        #process.readyRead.connect(lambda: update_progress(main_window, process, total_points, 
        #    required_runs, run_succeeded))
        

        start_progress = 90
        end_progress = 99
        file_count = -1
        # point0 = main_window.getPoint0WorldCoords()
            
        for roi_num, roi_file in enumerate(roi_files):
            file_count +=1
            subvolume_size = int(subvolume_sizes[file_count])
            #print(roi_file)
            distances = []

            for subv_num, subvolume_point in enumerate(subvolume_points):
                now = datetime.now()
                # use a counter for both for loops
                counter = subv_num + roi_num * len(subvolume_points)
                
                this_run_folder = os.path.join(self.run_folder, "dvc_result_{}".format(counter))
                os.mkdir(this_run_folder)
                output_filename = os.path.join(this_run_folder, "dvc_result_{}".format(counter))
                config_filename = os.path.join(this_run_folder,"dvc_config.txt")
                
                grid_roi_fname = os.path.join(this_run_folder, "grid_input.roi")
                # copies the pointcloud file as a whole in the run directory
                try:
                    shutil.copyfile(roi_file, grid_roi_fname)
                except Exception as err:
                    # this is not really a nice way to open an error message!
                    self.main_window.displayFileErrorDialog(message=str(err), title="Error creating config files")
                    return
                
                
                config =  blank_config.format(
                    reference_filename=  reference_file, # reference tomography image volume
                    correlate_filename=  correlate_file, # correlation tomography image volume
                    point_cloud_filename = grid_roi_fname,
                    output_filename= output_filename,
                    vol_bit_depth=  vol_bit_depth, # get from ref, 8 or 16
                    vol_hdr_lngth=vol_hdr_lngth,# get from ref, fixed-length header size, may be zero
                    vol_wide= dims[0], # number of x slices
                    vol_high= dims[1], # number of y slices
                    vol_tall= dims[2], #number of z slices
                    vol_endian = endian,
                    subvol_geom=  subvol_geom,
                    subvol_size=  subvolume_size, 
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
                    subvol_aspect='1.0 1.0 1.0',# image spacing
                    num_points_to_process=num_points_to_process, 
                    starting_point='{} {} {}'.format(*starting_point)) 
                time.sleep(1)
                with open(config_filename,"w") as config_file:
                    config_file.write(config)
            
                #if run_count == len( subvolume_points):
                # process.start( exe_file , [ param_file ] )          
                cancelled=False

                # TODO: 
                # ideally we should start a new process from the main thread once the previous
                # has finished
                # wait for process to finish before doing next run
                
                # process.waitForFinished(msecs=2147483647)
                self.processes.append( 
                    (exe_file, [ config_filename ], required_runs, total_points, num_points_to_process)
                )
                progress_callback.emit(int(start_progress + (end_progress - start_progress) * (subv_num / len(roi_files))))
            progress_callback.emit(100)
        
    def run_dvc(self, **kwargs):
        main_window = self.main_window
        input_file = self.input_file
        finish_fn = self.finish_fn
        run_succeeded = self.run_succeeded
        
        process = QtCore.QProcess()
        
        env = QtCore.QProcessEnvironment.systemEnvironment()
        try:
            nthreads = main_window.settings.value('omp_threads')
        except Exception as err:
            nthreads = '4'
            print (err)
        env.insert("OMP_NUM_THREADS", nthreads)
        process.setProcessEnvironment(env)

        # print("Processes: ", self.processes)
        # print("num: ", self.process_num)        

        # start time
        start_time = time.time()

        exe_file, param_file, required_runs,\
            total_points, num_points_to_process = self.processes[self.process_num]

        process.setWorkingDirectory(os.getcwd())
        # process.finished.connect(partial(finished_run, main_window, 
        #             process = process, required_runs = required_runs, 
        #             run_succeeded = run_succeeded, finish_fn = finish_fn))
        process.finished.connect(self.finished_run)
        process.started.connect(self.onStarted)
        if self.process_num == 0:
            main_window.create_progress_window("Running", 
                "Running DVC code {}/{}".format(self.process_num +1, len(self.processes)), 100,
                #lambda: cancel_run(main_window, process, run_succeeded)
                lambda: self.onCancel(process)
                )
        else:
            main_window.progress_window.setLabelText(
                "Running DVC code {}/{}".format(self.process_num +1, len(self.processes))
            )
            main_window.progress_window.canceled.connect(lambda: self.onCancel(process))
        process.readyRead.connect(
            lambda: update_progress(main_window, process, total_points, required_runs,\
                                    run_succeeded, start_time, num_points_to_process))
        # process.finished.connect(self.run_dvc())
        process.start(exe_file , param_file )

    def onStarted(self):
        pass

    def onCancel(self, process):
        main_window = self.main_window
        run_succeeded = self.run_succeeded
        state = process.state()
        # print ("Process state", state)
        if state in [2,1]:
            # print ("Cancelling run")
            process.kill()
            main_window.alert = QMessageBox(QMessageBox.NoIcon,"Cancelled","The run was cancelled.", QMessageBox.Ok)  
            main_window.alert.show()
            self.run_succeeded = False
        elif state == 0:
            print ("all OK, all processes ended")

    def finished_run(self, exitCode, exitStatus):
        main_window = self.main_window
        input_file = self.input_file
        finish_fn = self.finish_fn
        run_succeeded = self.run_succeeded
        required_runs = self.processes[self.process_num][2]

        print("finished {}/{} (or {}) with {} {}"
              .format(self.process_num + 1, required_runs,
                len(self.processes), exitCode, exitStatus))
        
        if exitStatus == 0:
            self.run_succeeded = self.run_succeeded and True
        else:
            self.run_succeeded = self.run_succeeded and False
            
        if self.process_num == required_runs-1:
            main_window.progress_window.close()
            if self.run_succeeded:
                main_window.alert = QMessageBox(QMessageBox.NoIcon,
                    "Success","The DVC code ran successfully.", QMessageBox.Ok)
            else:
                main_window.alert = QMessageBox(QMessageBox.NoIcon,
                    "Fail","The DVC code had some troubles.", QMessageBox.Ok) 
            main_window.alert.show()
            if finish_fn is not None:
                finish_fn() 
        else:
            self.process_num += 1
            self.run_dvc()

            