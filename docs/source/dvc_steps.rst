Digital Volume Correlation
**************************

The DVC app allows a digital volume correlation analysis to be performed on a reference and correlate image volume. You may either use a point cloud you have pre-created, or generate this in the app.
This manual was written at the time of version 21.1.0 being the latest release.

Settings
========
Under File->Settings you can set the maximum down-sampled size of the image, which limits how heavily the image is down-sampled. The settings appear as below:
 
For the volume render on the 3D viewer, it is recommended to use GPU volume rendering, otherwise the render will be very slow. You will need to set the memory of your GPU for this.
If the memory of your GPU is lower than the maximum down-sampling size you have set, then it will be the size of your GPU that dictates how much the image will be down-sampled if you choose to use the GPU for volume rendering.
You will have to click “View Image” on the Select Image panel to update the down-sampling of the image once you have saved the new settings.

Viewer Settings
===============
The viewer settings panel shows how much the image has been down-sampled:
 
If it has been down-sampled, the image will be interpolated, but you can turn this off by clicking on the viewer and then pressing “i”. It shows the “Loaded Image Size” and the “Displayed Image Size”. The displayed image size is the size of the image shown on the viewer, in this case it has been down-sampled. The “Loaded Image Size” is the original size of your chosen image.
You can choose to display the viewer coordinates in the loaded image or the down-sampled image. This will change how the slices and coordinates are labelled in the corner annotation of the 2D viewer.
If the image has not been down-sampled then it will only display the “Loaded Image Size” which is the size of the image you selected.

Help
====
When moving between each panel, the Help section is updated. Additional help can be viewed by hovering the mouse over some of the buttons and labels on the interface.
The rest of the manual will take you through panels 2-6….

Manual Registration
===================
The first step of the DVC analysis is to line up the reference and correlate images. The rigid body translation between the images will be input to the DVC analysis code. Go to the “Manual Registration” tab to get started with this.

The Point 0 Location
~~~~~~~~~~~~~~~~~~~~
First you will need to click on “Select point 0”. This will allow you to press shift and left click on a point in the image. Then change the size of the registration box.
If you scroll through slices of the image, clicking “Center on Point 0” will return you to the slice where point 0 is.
You should try to select point 0 to be at the position you would like to start your DVC analysis from. Later when you select your mask, if your point 0 lies within the mask then when you generate a point cloud, it will guarantee that a point lies at the location of point 0. Then this will be used as the global starting point in the DVC analysis, as well as the reference point for the translation. Otherwise, a random point will be selected to begin with.

Registering the Images
~~~~~~~~~~~~~~~~~~~~~~
You can set an initial translation if you already know some information about how the images are translated relative to each other.
When you click “Start Registration” this will crop the image to the size of the reference box you chose, centred on the point 0. It will do the same for the correlate image, and then it will subtract one image from the other, and display that on the viewer. It does this for the original images, not the down-sampled versions.
If you were to load two identical images, then the subtraction would result in nothing, so you would just see a black square. The idea is that to register the images, you need to align them such that the subtraction results in as uniform an image as possible.
If you have set an initial translation then the images will start off being translated relative to each other accordingly.
You can then move the two images relative to each other by using the keys: j, n, b and m. You can also still change the orientation using the x, y and z keys, and scroll through the image slices. 

Here is an example of what an image registration would look like as you begin to align the images – you can see it becomes more grey where you have a good overlap.

Once you are satisfied with the registration, click “Confirm Registration” to save the translation. This will be provided to the DVC analysis code later on.
Then move on to the “Mask” tab. 

Mask
====

Creating a mask
~~~~~~~~~~~~~~~
A mask needs to be created to dictate where the point cloud will lie.
To draw a mask, click on the 2D viewer and then press “t”. You can then trace a region freehand. To extend the mask above and below the current slice, you may adjust the “Slices Above” and “Slices Below” settings, before clicking “create mask”. The “Slices Above” and “Slices Below” are in the coordinate system of the down-sampled image (if your image has been down-sampled).
If you would like your mask to cover more than one area, or you would like to increase the area of the mask, tick the “Extend Mask” checkbox. Then you can draw another region and press “Extend Mask” to extend the mask to this region as well.

Saving and Loading a mask
~~~~~~~~~~~~~~~~~~~~~~~~~
The most recent mask you have created will automatically be saved, but if you would like to create a new mask, you will be prompted to then save the previous one, otherwise it will be discarded. The names of all of the masks you have saved will appear in a dropdown list. You can select one from here and reload it.
Note that the mask is created in the coordinate system of the down-sampled image, so if you change the down-sampling level, you may not be able to reload a mask you have previously generated.
Alternatively, you may load a mask from a file you have saved. This must be an uncompressed metaimage file, with the extension .mha.
Once you are satisfied with the mask, move on to the “Point Cloud” panel.

Point Cloud
===========

Creating a point cloud
~~~~~~~~~~~~~~~~~~~~~~
First of all, set a size for the subvolumes in the point cloud. This is the diameter of a spherical subvolume region, or the side length of a cubic one. If you have ticked the option to display the subvolume preview, then it will display a preview of the size of each subvolume, centred on the location of the reference point 0.
If you select a 2D point cloud, then the point cloud will only be created on the currently displayed slice of the image. A 3D point cloud will be created across the entire extent of the mask. 
The overlap is the percentage overlap of the subvolume regions. You can also set a rotation of the subvolumes in degrees, relative to any of the three axes.
You may choose to erode the mask. Without doing this, although all of the points will lie within the mask, areas of some of the subvolumes may lie outside of this. Eroding the mask will help to ensure the entirety of all of the subvolume regions lies within the mask.
Be aware that this is quite a time consuming process. You may also adjust the multiplier on the erosion, which will change how heavily this erosion process takes place – you may decrease the multiplier if it does not matter to you if some subvolumes are partially outside of the mask.
The display subvolume regions option allows you to turn on/off viewing the subvolumes, but the points themselves will still be displayed. The display registration region toggles on/off the view of the registration box centred on point 0.

Saving and Loading a point cloud
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The most recent point cloud you have created will automatically be saved, but if you would like to create a new point cloud, you will be prompted to then save the previous one, otherwise it will be discarded. The names of all of the point clouds you have saved to the current session will appear in a dropdown list. You can select one from here and reload it.
Alternatively, you may load a point cloud from a file you have saved. This must be a tab-delimited text file with the point number in the first column, followed by the x, y and z coordinates of each point. An example is shown below. The first point in the file will be used as the starting point for the DVC analysis. Note that you may use non-integer coordinates.
 
Note that the point cloud is in the coordinate system of the original image, and is not affected by the down-sampling, it is displayed at the true location of the points.
Once you are happy with your point cloud, you can move on to the “Run DVC” panel.
Running the DVC Analysis
First, set a name for your run. This is how the run will be saved, and you will need to refer to this name later when you would like to view the results.
The settings you can change for your run are as follows:
*Points in run - the number of points you would like to perform the run on. This will automatically start off being set to the total number of points in the cloud you have created, but you may wish to run with less points to begin with, as a test for instance. If you choose less points than the total number in the cloud, and your reference point 0 lies within your point cloud, the points will be selected starting with point 0 and working outwards from there.


*Maximum displacement - defines the maximum displacement expected within the reference image volume. This is a very important parameter used for search process control and memory allocation. Set to a reasonable value just greater than the actual sample maximum displacement. Be cautious: large displacements make the search process slower and less reliable. It is best to reduce large rigid body displacements through image volume manipulation. Future code development will introduce methods for better management of large displacements.
- Suitable values: 1 -> smallest dimension of the image volumes

*Number of degrees of freedom - defines the degree-of-freedom set for the final stage of the search. The actual search process introduces degrees-of-freedom in stages up to this value. Translation only suffices for a quick, preliminary investigation. Adding rotation will significantly improve displacement accuracy in most cases. Reserve strain degrees-of-freedom for cases when the highest precision is required.
- 3 = translation only
- 6  = translation plus rotation
- 12 = translation, rotation and strain

*Objective function - defines the objective function template matching form. See B. Pan, Equivalence of Digital Image Correlation Criteria for Pattern Matching, 2010. Functions become increasingly expensive and more robust as you progress from sad to znssd. Minimizing squared-difference and maximizing cross-correlation are functionally equivalent.
- sad  = sum of absolute differences
- ssd  = sum of squared differences
- zssd  = intensity offset insensitive sum of squared differences (value not normalized)
- nssd  = intensity range insensitive sum of squared differences (0.0 = perfect match, 1.0 = max value)
- znssd  = intensity offset and range insensitive sum of squared differences (0.0 = perfect match, 1.0 = max value)
Notes on objective function values:
1.	The normalized quantities nssd and znssd are preferred, as quality of match can be assessed.
2.	The natural range of nssd is [0.0 to 2.0], and of znssd is [0.0 to 4.0].
3.	Both are scaled for output into the [0.0 to 1.0] range for ease of comparison.

*Interpolation type - Defines the interpolation method used during template matching.
- Options: nearest, trilinear, tricubic.
- Trilinear is significantly faster, but with known template matching artefacts. 
- Trilinear is most useful for tuning other search parameters during preliminary runs.
- Tricubic is computationally expensive, but is the choice if strain is of interest.

*Sampling Points in subvolume - Defines the number of points within each subvolume (max is 50000). In this code, subvolume point locations are NOT voxel-centred and the number is INDEPENDENT of subvolume size. Interpolation within the reference image volume is used to establish templates with arbitrary point locations.
-    For cubes a uniform grid of sampling points is generated.
-    For spheres, the sampling points are randomly distributed within the subvolume.
This parameter has a strong effect on computation time, so be careful.
You can then either run a “Single” run, or a “Bulk” run:
*A single run will run with the current point cloud you have generated, you only need to select the number of sampling points in the subvolume region.
*If you select to run in bulk, this will generate multiple point clouds and perform runs on them, instead of your current point cloud. You can set the minimum and maximum subvolume size you would like, and the size of the step between these values, and similar for the sampling points. In the example above, this would perform runs on point clouds with sizes 30, 40 and 50, and number of sampling points 9000, 9500 and 10000, so 9 runs in total. Note that the other settings for the point clouds generated will be taken from what you selected on the point cloud panel, including the subvolume shape, dimensionality, overlaps and rotation angles.
For every run, any point clouds and input files to the DVC analysis code that are generated are saved in the session files, which you are able to access if you export your session (see the later section on this).
Run Progress
Whilst the DVC analysis is running, you will see updates on its progress, as below:

The 1/8 on the first line indicates that it is on run 1 out of a total of 8 runs, and then on the next line it shows it is on point 26 out of a total of 191 for this run. Following this we have:
*[x,y,z] location of the point.
*The search status:
- Point_Good = successful search convergence within the max displacement.
- Range_Fail = max displacement exceeded; consider increasing the disp_max parameter.
- Convg_Fail = maximum iterations exceeded; consider increasing subvol_size &/or npts
*The magnitude of the objective function value at the end of the search is listed as obj=.
- For obj_function = sad, ssd, and zssd the value is relative, depending on subvolume size and pixel values.
- For obj_function = nssd and znssd the value is scaled between 0 and 2, with zero a perfect match.
*The point [x,y,z] displacement is listed next for successful searches.
DVC Results
Once your run has completed, you can look at the results on the “DVC Results” panel. There are two ways of doing this – looking at graphs, and viewing the displacement vectors. First, you need to select the run you would like to view the results for from the dropdown list of all of the runs you have saved.
Graphs of the Results
Then click on “Display Graphs”. Another window will open (once you are done looking at the graphs you can either close or minimize this window and it will take you back to the main app just fine).
It will start you off on the “Summary” tab. This isn’t so useful if you only performed one run. For each run that you performed, there will be a separate tab. If you navigate to one of these it will show you graphs for the objective minimum, and displacements in x, y, z as well as changes in φ, θ, ψ for that run. The title of the tab also gives the number of sampling points in the subvolume and the subvolume size.
 
This will automatically show the displacements including the translation that you set in the manual registration. You can adjust the displacements to exclude this translation by going to Settings and selecting “Show displacement relative to reference point 0”.
Now, coming back to the summary tab, this shows the settings for the runs including the subvolume geometry, maximum displacement etc., and if you have done a bulk run then you can select a particular variable (such as the objective minimum) and then compare the graphs for this variable in each of the runs. You can select to just compare for a certain subvolume size or number of sampling points, or you can choose to compare them all (which is what is chosen in the image below).
 
Displacement Vectors
To view the displacements as vectors overlaid on the reference image, return to the main app. For each run you are able to select and visualise the different point clouds with different sizes and number of sampling points in the subvolumes. Then when viewing the vectors, you can select “None” to just view the point cloud, or you can select “Total Displacement” or “Displacement with respect to reference point 0”. Both of these latter options will display the displacements of each point in the cloud as arrows overlaid on the reference image, but “Total displacement” will show the displacement including the rigid translation set in the manual registration panel, whereas displacement with respect to point 0 will not. 
 
If the vector scaling is set to 1, this will show the displacement vectors true to size, but you may modify this to make them easier to see. You will need to click “View Pointcloud/Vectors” once again to reload them with the new scaling.
On the 2D viewer, the vectors will be shown as 2D arrows, showing only the displacements in the current plane. E.g. if you pressed the ‘x’ key you would be viewing the YZ plane, so would just see the y and z components of the displacement. Whereas on the 3D viewer, it shows the total displacement, taking into account all components. Below is a comparison of some vectors shown in 2D compared to 3D.
 
The arrows are coloured according to their relative size. Red arrows are the largest and dark blue the smallest. Note that the colours of the arrows may differ between the 2D and 3D viewer because the colouring of the 2D arrows is only taking into account the size of the displacements in two, rather than all three directions. 
Results Files
The DVC analysis code generates two files for each run it performs. These aren’t directly accessible from the app, but you are able to access them if you export your session (see the later section). The two files it produces for each run are as follows:
1.	Status file (.stat) 
This contains: 
*An echo of the input file used to control program execution.
*Information about the point cloud, dvc program version, and run date/time.
*Search statistics and timing.
2.	Displacement file (.disp) 
This is a tab-delimited text file of the dev results. A header line appears first identifying columns: 
*n = the point identifier
*x y z = the point location within the reference volume
*status = the search outcome: 0 = successful (no error), -1 = Range_Fail, -2 = Convg_Fail
*objmin = the objective function magnitude at the end of the search
*u v w = the point displacement: [location in target volume] - [location in reference volume]
*<phi the psi> = subvolume rotation, if num_srch_dof = 6 or 12
*<exx eyy ezz exy eyz exz> = subvolume strain, if num_srch_dof = 12
Saving and Loading Sessions
At any stage, you can save your session by going to File->Save. You will then be prompted to set a name for the session. You can also choose if you wish to compress the session files. If you do, this will take longer to save, but will take up less storage space. Upon closing the session, you will be automatically prompted to save it.
Next time you open up the app, if you have any sessions saved, you will automatically be provided with a dropdown list where you can select a session to load. Alternatively you can load a new session.
Note that sessions are saved in a folder called “DVC_Sessions” which will have been created in the location that you opened up the app from. Therefore it is important that you always open up the app from the same location, to ensure all of your sessions are found. Going into this folder and opening or editing the files can cause problems with reloading the sessions, so instead of doing this, if you would like to access the session files you should export the session.
Exporting Sessions
At any point, you can export the session files by going to File->Export. This allows you to choose any location in your directories to save a copy of the session files. This is the best way to store your results if you would like to open the files.
