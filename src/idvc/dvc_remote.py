import os
from brem import RemoteRunControl
import brem
from PySide2 import QtCore
import ntpath, posixpath
import pysnooper
import json

class PrepareDVCRemote(object):
    def __init__(self, parent):
        self._config_json = None
        self._remote_workdir = None
        self.parent = parent

    
    @property
    def config_json(self):
        return self._config_json


    def set_config_json(self, value):
        self._config_json = os.path.abspath(value)


    @property
    def remote_workdir(self):
        return self._remote_workdir

    
    def set_remote_workdir(self):
        self._remote_workdir = self.parent.settings_window


class DVCRemoteRunControlSignals(QtCore.QObject):
    status = QtCore.Signal(tuple)
    progress = QtCore.Signal(int)

class DVCRemoteRunControl(object):
    def __init__(self, connection_details):

        super(DVCRemoteRunControl, self).__init__()
        # self.signals is a property of RemoteRunControl
        self.signals = DVCRemoteRunControlSignals()
        self._num_runs = 0
        self._workdir = None
        self.connection_details = connection_details


    def set_num_runs(self, value):
        self._num_runs = value


    def set_workdir(self, value):
        self._workdir = value

    
    @property
    def num_runs(self):
        return self._num_runs


    @property
    def workdir(self):
        return self._workdir

    def _create_connection(self):
        # 1 create a BasicRemoteExecutionManager
        username = self.connection_details['username']
        port = self.connection_details['server_port']
        host = self.connection_details['server_name']
        private_key = self.connection_details['private_key']
        remote_os = self.connection_details['remote_os']
        logfile = os.path.join('ssh.log')

        conn = brem.BasicRemoteExecutionManager(port, host, username, private_key, remote_os, logfile=logfile)
        conn.login(passphrase=False)
        # 2 go to workdir
        conn.changedir(self.workdir)

        return conn

    @pysnooper.snoop()        
    def run_dvc_on_remote(self, **kwargs):
        # 1 create a BasicRemoteExecutionManager
        
        conn = self._create_connection()
        remote_os = conn.remote_os
        
        progress_callback = kwargs.get('progress_callback', None)

        if remote_os == 'POSIX':
            dpath = posixpath
        else:
            dpath = ntpath
        
        for i in range(self.num_runs):
            if progress_callback is not None:
                progress_callback.emit(i)
            
            wdir = dpath.join(self.workdir, 'dvc_result_{}'.format(i))    
            # 2 run 'unzip filename'
            stdout, stderr = conn.run('cd {} && . ~/condarc && conda activate dvc && dvc dvc_config.txt'.format(wdir))

    @pysnooper.snoop()
    def retrieve_results(self, config_file, **kwargs):

        # created in dvc_interface create_run_config
        with open(config_file) as tmp:
            config = json.load(tmp)
        run_folder = config['run_folder']

        conn = self._create_connection()
        remote_os = conn.remote_os
        
        progress_callback = kwargs.get('progress_callback', None)

        if remote_os == 'POSIX':
            dpath = posixpath
        else:
            dpath = ntpath

        # retrieve the results in each directory and store it locally
        for i in range(self.num_runs):
            if progress_callback is not None:
                progress_callback.emit(i)
            fname = 'dvc_result_{}'.format(i)
            
            localdir = os.path.join(run_folder, "dvc_result_{}".format(i))

            for extension in ['stat', 'disp']:
                path_to_file = dpath.join(self.workdir, fname)
                file_to_get = '{}.{}'.format(fname, extension)
                conn.changedir(path_to_file)
                conn.get_file(file_to_get, localdir)  


class DVCSLURMRemoteRunControl(RemoteRunControl):
    def __init__(self, connection_details=None, 
                 reference_filename=None, correlate_filename=None,
                 dvclog_filename=None,
                 dev_config=None):

        super(DVCSLURMRemoteRunControl, self).__init__(connection_details=connection_details)
        self.reference_fname    = reference_filename
        self.correlate_fname    = correlate_filename
        self.dvclog_fname       = dvclog_filename
        
        # try to create a worker
        self.create_job(self.run_worker, 
            reference_fname=self.reference_fname, 
            correlate_fname=self.correlate_fname, 
            update_delay=10, logfile=self.dvclog_fname)

    # Not required for base class
    @property
    def reference_fname(self):
        return self._reference_fname
    @reference_fname.setter
    def reference_fname(self, value):
        '''setter for reference file name.'''
        self._reference_fname = value
        
    @property
    def correlate_fname(self):
        return self._correlate_fname
    @correlate_fname.setter
    def correlate_fname(self, value):
        '''setter for correlate file name.'''
        self._correlate_fname = value
        
    @property
    def dvclog_fname(self):
        return self._dvclog_fname
    @dvclog_fname.setter
    def dvclog_fname(self, value):
        '''setter for dvclog file name.'''
        self._dvclog_fname = value
        
    
            
    
    # @pysnooper.snoop()
    def run_worker(self, **kwargs):
        # retrieve the appropriate parameters from the kwargs
        host         = kwargs.get('host', None)
        username     = kwargs.get('username', None)
        port         = kwargs.get('port', None)
        private_key  = kwargs.get('private_key', None)
        logfile      = kwargs.get('logfile', None)
        update_delay = kwargs.get('update_delay', None)
        # get the callbacks
        message_callback  = kwargs.get('message_callback', None)
        progress_callback = kwargs.get('progress_callback', None)
        status_callback   = kwargs.get('status_callback', None)
        
        reference_fname   = kwargs.get('reference_fname', None)
        correlate_fname   = kwargs.get('correlate_fname', None)
        
        
        from time import sleep
        
        a = brem.BasicRemoteExecutionManager( host=host,
                                              username=username,
                                              port=22,
                                              private_key=private_key)

        a.login(passphrase=False)

        inp="input.dvc"
        # folder="/work3/cse/dvc/test-edo"
        folder = dpath.dirname(logfile)
        datafolder="/work3/cse/dvc/test_data"

        with open(inp,'w', newline='\n') as f:
            print("""###############################################################################
#
#
#               example dvc process control file
#
#
###############################################################################

# all lines beginning with a # character are ignored
# some parameters are conditionally required, depending on the setting of other parameters
# for example, if subvol_thresh is off, the threshold description parameters are not required

### file names

reference_filename\t{0}/frame_000_f.npy\t### reference tomography image volume
correlate_filename\t{0}/frame_010_f.npy\t### correlation tomography image volume

point_cloud_filename\t{1}/medium_grid.roi\t### file of search point locations
output_filename\t{1}/medium_grid\t### base name for output files

### description of the image data files, all must be the same size and structure

vol_bit_depth           8                       ### 8 or 16
vol_hdr_lngth           96                      ### fixed-length header size, may be zero
vol_wide                1520                    ### width in pixels of each slice
vol_high                1257                    ### height in pixels of each slice
vol_tall                1260                    ### number of slices in the stack

### parameters defining the subvolumes that will be created at each search point

subvol_geom             sphere                  ### cube, sphere
subvol_size             80                      ### side length or diameter, in voxels
subvol_npts             8000                    ### number of points to distribute within the subvol

subvol_thresh           off                     ### on or off, evaluate subvolumes based on threshold
#   gray_thresh_min     27                      ### lower limit of a gray threshold range if subvol_thresh is on
#   gray_thresh_max     127                     ### upper limit of a gray threshold range if subvol_thresh is on
#   min_vol_fract       0.2                     ### only search if subvol fraction is greater than

### required parameters defining the basic the search process

disp_max                38                      ### in voxels, used for range checking and global search limits
num_srch_dof            6                       ### 3, 6, or 12
obj_function            znssd                   ### sad, ssd, zssd, nssd, znssd
interp_type             tricubic                ### trilinear, tricubic

### optional parameters tuning and refining the search process

rigid_trans             34.0 4.0 0.0            ### rigid body offset of target volume, in voxels
basin_radius            0.0                     ### coarse-search resolution, in voxels, 0.0 = none
subvol_aspect           1.0 1.0 1.0             ### subvolume aspect ratio



""".format(datafolder,folder),file=f)

        a.put_file(inp, remote_filename=dpath.join(folder, inp))


        job="""

module purge
module load AMDmodules foss/2019b

/work3/cse/dvc/codes/CCPi-DVC/build-amd/Core/dvc {0} > {1} 2>&1
#{0}
        """.format(inp, logfile)



        jobid = a.submit_job(folder,job)
        self.job_id = jobid
        print(jobid)
        status = a.job_status(jobid)
        print(status)
        i = 0
        start_at = 0
        while status in [b'PENDING',b'RUNNING']:
            i+=1
            # widgets['jobid'].setText("Job id: {} {}".format(jobid, str(status)))
            status_callback.emit((jobid, status.decode('utf-8')))
            self.internalsignals.status.emit((jobid, status.decode('utf-8')))
            if status == b'PENDING':
                print("job is queueing")
                # message_callback.emit("Job {} queueing".format(jobid))
            else:
                print("job is running")
                # widgets['buttonBox'].button(QtWidgets.QDialogButtonBox.Apply).setText('Running')
                
                # tails the output of dvc
                tail = self.pytail(a, logfile, start_at)
                # count the number of newlines
                for i in tail:
                    if i == "\n":
                        start_at+=1
                message_callback.emit("{}".format(tail.decode('utf-8')))
                # try to infer the progress
                def progress(line):
                    import re
                    try:
                        match = re.search('^([0-9]*)/([0-9]*)', line.decode('utf-8'))
                        if match is not None:
                            return eval(match.group(0))
                    except Exception as err:
                        print (err)

                line = tail.splitlines()
                if len(line) >= 2:
                    line = line[-2]

                curr_progress = progress(line)
                if curr_progress is not None:
                    # widgets['progressBar'].setValue(int(progress(line)*100))
                    progress_callback.emit(int(progress(line)*100))
                    print ("attempt evaluate progress ", progress(line))
                
            sleep(update_delay)
            status = a.job_status(jobid)
        

        # dvc computation is finished, we get the last part of the output
        tail = self.pytail(a, logfile, start_at)
        message_callback.emit("{}".format(tail.decode('utf-8')))
        # set the progress to 100
        progress_callback.emit(100)

        a.changedir(folder)
        a.get_file("slurm-{}.out".format(jobid))
        a.get_file("dvc.out".format(jobid))
        # here we should fetch also all the output files defined at
        # output_filename\t{1}/small_grid\t### base name for output files

        a.logout()
        self.internalsignals.status.emit((jobid, 'FINISHED'))
        
