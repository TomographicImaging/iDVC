DVC Executable
**************
Whether you have installed the full gui, or just the executable, you are able to run the DVC from the command line, in the environment where you have installed it.

DVC Commands
============
The DVC executable can be called using the following commands:

**dvc** ``dvc_in`` - execute dvc code with **dvc_in** (a txt dvc input file) controlling the run

**dvc help** - provide additional detail about running the dvc code

**dvc example** - print dvc_in_example with brief keyword descriptions

**dvc manual** - print dvc_manual with more detailed information

Example DVC Input File
=======================

This is the contents of the **dvc_in_example** file mentioned above::

        ###############################################################################
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

        reference_filename	frame_000_f.npy		### reference tomography image volume
        correlate_filename	frame_010_f.npy		### correlation tomography image volume

        point_cloud_filename	central_grid_5.roi	### file of search point locations
        output_filename		central_grid_5_test		### base name for output files

        ### description of the image data files, all must be the same size and structure

        vol_bit_depth		8			### 8 or 16
        vol_hdr_lngth		96		### fixed-length header size, may be zero
        vol_wide		1520			### width in pixels of each slice
        vol_high		1257			### height in pixels of each slice
        vol_tall		1260			### number of slices in the stack

        ### parameters defining the subvolumes that will be created at each search point

        subvol_geom		sphere			### cube, sphere
        subvol_size		80			### side length or diameter, in voxels
        subvol_npts		8000			### number of points to distribute within the subvol

        subvol_thresh		off			### on or off, evaluate subvolumes based on threshold
        gray_thresh_min	27			### lower limit of a gray threshold range if subvol_thresh is on
        gray_thresh_max	127			### upper limit of a gray threshold range if subvol_thresh is on
        min_vol_fract	0.2			### only search if subvol fraction is greater than

        ### required parameters defining the basic the search process

        disp_max		38			### in voxels, used for range checking and global search limits
        num_srch_dof		6			### 3, 6, or 12
        obj_function		znssd			### sad, ssd, zssd, nssd, znssd 
        interp_type		tricubic		### trilinear, tricubic

        ### optional parameters tuning and refining the search process

        rigid_trans		34.0 4.0 0.0		### rigid body offset of target volume, in voxels
        basin_radius		0.0			### coarse-search resolution, in voxels, 0.0 = none
        subvol_aspect		1.0 1.0 1.0		### subvolume aspect ratio

    

DVC Configuration
=================

Details about most of the options can be found in the :ref:`Running DVC Analysis <Running DVC Analysis>` section.

However, the DVC executable has some options which have not yet made their way into the app. These are as follows:


**subvol_thresh**

	examplar:	subvol_thresh	off
	required:	yes
	suitable:	on, off

   Defines the state of subvolume thresholding to active (on) or inactive (off).

   Useful if there is a simple gray level segmentation between foreground and background.

   Subvolumes with little foreground content are not searched and flagged on output.

**gray_thresh_min**

	examplar:	gray_thresh_min	25

	required:	If subvol_thresh is on

	suitable:	0 <= int <= 2^vol_bit_depth, and < gray_thresh_max

   Defines the lower limit of a gray scale threshold range.

   Voxels between (min) and (max) are included in the threshold range.

**gray_thresh_max**

	examplar:	gray_thresh_max	125

	required:	If subvol_thresh is on

	suitable:	0 <= int <= 2^vol_bit_depth, and > gray_thresh_min

   Defines the upper limit of a gray scale threshold range.

   Voxels between (min) and (max) are included in the threshold range.

**min_vol_fract**

	examplar:	min_vol_fract	0.2

	required:	If subvol_thresh is on

	suitable:	0.000000 <= double <= 1.000000

   Defines a parameter for pre-checking subvolumes for content.

   The fraction of subvolume points within the gray_thresh_min/max range is determined.

   If below min_vol_fract, the subvolume is likely in a void or in a background region.

   A point failing the test is not searched and flagged on output.

More detailed information about all parameters can be found in by running the **dvc_manual** command.