import os
import numpy as np
from PySide2 import QtCore
from datetime import datetime
from PySide2.QtWidgets import QMessageBox, QProgressDialog
import json
import time
import shutil
import platform
import pysnooper
from brem import AsyncCopyOverSSH, BasicRemoteExecutionManager
import tempfile
import ntpath, posixpath

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
'''

def update_progress(main_window, process, total_points, required_runs, run_succeeded):
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
            main_window.progress_window.setValue(count/(total_points+3*required_runs)*100)
            label_text = main_window.progress_window.labelText().split("\n")[0]
            main_window.progress_window.setLabelText(
                    "{}\n{}".format(label_text, line)
                )
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
        main_window.progress_window.setMinimumDuration(100)
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

    def __init__(self, main_window, input_file, finish_fn, run_succeeded, session_folder, remote_os=None):
        # print("The session folder is", session_folder)
        self.main_window = main_window
        self.input_file = input_file
        self.finish_fn = finish_fn
        self.run_succeeded = run_succeeded

        self.processes = []
        self.process_num = 0
        
        # created in dvc_interface create_run_config
        with open(input_file) as tmp:
            config = json.load(tmp)

        subvolume_points = config['subvolume_points'] 
        subvolume_sizes = config['subvolume_sizes']
        points = int(config['points'])

        roi_files = config['roi_files']
        reference_file = config['reference_file']
        correlate_file = config['correlate_file']
        vol_bit_depth = int(config['vol_bit_depth'])
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

        # Change directory into the folder where the run will be saved:
        os.chdir(session_folder)
        # this is the one directory we created where we will run the dvc command in
        # we want to change this to create multiple directories first and then run through
        # all the directory created https://github.com/TomographicImaging/iDVC/issues/37
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
            #print(i)
            if i < points:
                total_points += i
            else:
                total_points += points

        total_points = total_points * len(subvolume_points)

        #print("Total points", total_points)

        #process.readyRead.connect(lambda: update_progress(main_window, process, total_points, 
        #    required_runs, run_succeeded))
        


        file_count = -1
        point0 = main_window.getPoint0WorldCoords()
            
        for roi_num, roi_file in enumerate(roi_files):
            file_count +=1
            subvolume_size = int(subvolume_sizes[file_count])
            #print(roi_file)
            distances = []
                
            with open(roi_file, "r") as entire_central_grid:
                
                for line in entire_central_grid:
                    line_array = line.split()

                    distance = np.sqrt(np.square(float(line_array[1]) - point0[0]) + \
                        np.square(float(line_array[2])-point0[1]) + np.square(float(line_array[3])-point0[2]))

                    distances.append(distance)
                
            lines_to_write = []

            # sort the points in euclidean distance to the point0
            # add to the list of points to be run (selected_central_grid) by adding to 
            # the point list only the files with index in lines_to_write
            order = [ i for i in range(len(distances))]
            sorted_list_index = [ el for el in zip(distances, order)]
            sorted_list_index.sort()
            # this contains the indices of the sorted list
            lines_to_write = [ el for el in zip(*sorted_list_index) ] [1][:points]

            for subv_num, subvolume_point in enumerate(subvolume_points):
                now = datetime.now()
                # use a counter for both for loops
                counter = subv_num + roi_num * len(subvolume_points)
                # dt_string = now.strftime("%d%m%Y_%H%M%S")
                # new_output_filename = "%s/dvc_result_%s" % (self.run_folder, dt_string)
                # config_filename = "%s/dvc_config_%s" % (self.run_folder, dt_string)
                # config_filename = config_filename + ".txt"
                this_run_folder = os.path.join(self.run_folder, "dvc_result_{}".format(counter))
                os.mkdir(this_run_folder)
                output_filename = os.path.join(this_run_folder, "dvc_result_{}".format(counter))
                config_filename = os.path.join(this_run_folder,"dvc_config.txt")
                
                grid_roi_fname = os.path.join(this_run_folder, "grid_input.roi")
                with open(grid_roi_fname,"w") \
                    as selected_central_grid:
                    with open(roi_file, "r") as entire_central_grid:
                        for i,line in enumerate(entire_central_grid):
                            if i in lines_to_write:
                                selected_central_grid.write(line)

                newline = None    
                if remote_os is not None:
                    if remote_os in ['Windows', 'POSIX'] :    
                        # on remote we aim at running in the directory
                        grid_roi_fname  = os.path.basename(grid_roi_fname)
                        output_filename = os.path.basename(output_filename)
                        if remote_os == 'POSIX':
                            newline = "\n"
                    

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
                    subvol_aspect='1.0 1.0 1.0') # image spacing
                time.sleep(1)


                with open(config_filename,"w", newline=newline) as config_file:
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
                    (exe_file, [ config_filename ], required_runs, total_points)
                )

    def zip_workdir_and_upload(self, **kwargs):
        # TODO this is already in a worker and does not need to run the AsyncCopyOverSSH
        
        #param_file is a list with at least 1 item but we are interested in the first
        # because we want to know the path to it and all files will be in the same directory
        exe_file, param_file, required_runs,\
            total_points = self.processes[0]
        # config is in the directory

        configdir = os.path.join(os.path.dirname(param_file[0]),'..')
        zipped = shutil.make_archive(os.path.join(configdir, '..', 'remote_run'), 'zip',  configdir)

        self.asyncCopy = AsyncCopyOverSSH()
        if not hasattr(self.main_window, 'connection_details'):
            self.main_window.statusBar().showMessage("define the connection")
            return
        username = self.main_window.connection_details['username']
        port = self.main_window.connection_details['server_port']
        host = self.main_window.connection_details['server_name']
        private_key = self.main_window.connection_details['private_key']
        
        self.asyncCopy.setRemoteConnectionSettings(username=username, 
                                    port=port, host=host, private_key=private_key)

        
        
        remote_dir = self.main_window.settings_window.fw.widgets['remote_workdir_field'].text()
        # this shouldn't be necessary, however the signals and the workers are created before the async copy
        # object is created and then the local dir is not set in the worker.
        self.asyncCopy.SetRemoteDir(remote_dir)
        self.asyncCopy.SetCopyToRemote()
        self.asyncCopy.SetLocalDir(os.path.dirname(zipped))
        self.asyncCopy.SetFileName(os.path.basename(zipped))

        self.asyncCopy.signals.status.connect(print)
        self.asyncCopy.signals.finished.connect(
            lambda: self._unzip_on_remote(remote_dir, os.path.basename(zipped))
            )

        self.asyncCopy.threadpool.start(self.asyncCopy.worker)

    @pysnooper.snoop()
    def _unzip_on_remote(self, workdir, filename, **kwargs):
        
        # 1 create a BasicRemoteExecutionManager
        username = self.main_window.connection_details['username']
        port = self.main_window.connection_details['server_port']
        host = self.main_window.connection_details['server_name']
        private_key = self.main_window.connection_details['private_key']
        remote_os = self.main_window.connection_details['remote_os']
        logfile = os.path.join(tempfile.tempdir, 'ssh.log')
        conn = BasicRemoteExecutionManager(port, host, username, private_key, remote_os, logfile=logfile)
        conn.login(passphrase=False)
        # 2 go to workdir
        conn.changedir(workdir)
        # 2 run 'unzip filename'
        # -o forces to overwrite the files being unzipped
        # unzip should be substituted with some python like
        # import zipfile
        # with zipfile.ZipFile("remote_run.zip", 'r') as mz:
        #     mz.extractall()
        stdout, stderr = conn.run('cd {} && unzip -o {}'.format(workdir, filename))
        status_callback = kwargs.get('status_callback', None)
        if status_callback is not None:
            status_callback.emit((stdout, stderr))

    @pysnooper.snoop()        
    def run_dvc_on_remote(self, workdir, **kwargs):
        # 1 create a BasicRemoteExecutionManager
        username = self.main_window.connection_details['username']
        port = self.main_window.connection_details['server_port']
        host = self.main_window.connection_details['server_name']
        private_key = self.main_window.connection_details['private_key']
        remote_os = self.main_window.connection_details['remote_os']
        logfile = os.path.join(tempfile.tempdir, 'ssh.log')

        progress_callback = kwargs.get('progress_callback', None)

        if remote_os == 'POSIX':
            dpath = posixpath
        else:
            dpath = ntpath
            
        conn = BasicRemoteExecutionManager(port, host, username, private_key, remote_os, logfile=logfile)
        conn.login(passphrase=False)
        # 2 go to workdir
        conn.changedir(workdir)
        for i,el in enumerate(self.processes):
            if progress_callback is not None:
                progress_callback.emit(i)

            param_file = el[1][0]
            
            wdir = dpath.join(workdir, 'dvc_result_{}'.format(i))    
            # 2 run 'unzip filename'
            stdout, stderr = conn.run('cd {} && . ~/condarc && conda activate dvc && dvc dvc_config.txt'.format(wdir))


    def run_dvc(self):
        main_window = self.main_window
        input_file = self.input_file
        finish_fn = self.finish_fn
        run_succeeded = self.run_succeeded
        
        process = QtCore.QProcess()
        
        # print("Processes: ", self.processes)
        # print("num: ", self.process_num)        

        exe_file, param_file, required_runs,\
            total_points = self.processes[self.process_num]

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
                                    run_succeeded))
        # process.finished.connect(self.run_dvc())
        process.start( exe_file , param_file )

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

            