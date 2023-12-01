# imports
#---------------------------------------------------------
import os
import sys
import numpy as np
from idvc.utils.class_automatic_registration import automatic_registration, automatic_registration_with_plotting
#from cil.utilities.display import show2D, show_geometry

# Code introduction
#------------------------------------------------------------------------------
print("\nThis code implements the automatic registration of two volumetric images.\n")

# User inputs, flags
#----------------------------------------------------------------------------------
simulate=False # simulate data 
raw = True # True: input files are raw. False: input files are numpy arrays.
pointzero = True # True: pointzero is inputted by user. False: point zero automatically generated
intermediate_plot= True # plots the slices and the correlation images and the diff on the screen
slice_plot=False # plots sices with islicer from CIL, uncomment the CIL import if so
save = False # save all results in a file in the output folder --- all steps

# User inputs defined in the iDVC gui, point zero and user defined volume:
#---------------------------------------------------------------------------------------

size =np.array([[1180,1380],[1180,1380],[1300,1500]]) #size of the volume in which to calculate the overall shift
p3d_0 = [1280,1280,1400] # point zero on which to calculate the overall shift

# brian point1
#-----------------
size =np.array([[1300,1500],[1180,1380],[1180,1380]]) 
p3d_0 = [1400,1280,1280]

# brian point2
#------------------
#size =np.array([[500,700],[1180,1380],[2100,2300]]) 
#p3d_0 = [600,1280,2200]

# brian point3
#-----------------
#size =np.array([[500,700],[1180,1380],[450,650]]) 
#p3d_0 = [600,1280,550]

# check that point zero is inside the `size` volume
if (size[0,0]<=p3d_0[0]<=size[0,1]) and (size[1,0]<=p3d_0[1]<=size[1,1]) and (size[2,0]<=p3d_0[2]<=size[2,1])==False:
    print("Point zero is out of the selected volume")
    sys.exit() 

# insert data location
#---------------------------------------------------------------------------------------------------------------------------

#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset'
inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\Dataset_example2'
#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\image_volumes'
inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\image_volumes\Set2'
#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\image_volumes\Set3'

outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Dataset_example2\test'
#outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Dataset_example2\point1_20231110'
#outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Set2\uservolume_analysis_test_code2_20231109'
#outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Set3\uservolume_analysis_1_20231005'
if not os.path.exists(outputfolder):
    os.makedirs(outputfolder)

print("Input folder is "+inputfolder+".\n")


# insert filenames of reference and image

if raw ==True:
    filename0 = "104506_distortion_corrected_2560_2560_1600_16bit.raw"
    filename1 = "104507_distortion_corrected_2560_2560_1600_16bit.raw"
    bit=16

    Nx=2560
    Ny=Nx
    stopz= 1600

    
    # August 2023 data from Catherine
    filename0 = "104531_distortion_corrected_2560_2560_1500_8bit.raw"
    filename1 = "104532_distortion_corrected_2560_2560_1500_8bit.raw"

    Nx=2560 #854 
    Ny=Nx
    stopz= 1500 #720 #number of slices imported
    bit = 8

    #filename0 = "123744_854xy_720z_8bitEP.raw"
    #filename1 = "123745_854xy_720z_8bitEP.raw"
    #filename1 = "123746_854xy_720z_8bitEP.raw"
    #filename1 = "123747_854xy_720z_8bitEP.raw"
    #filename1 = "123748_854xy_720z_8bitEP.raw"
    #filename1 = "123749_854xy_720z_8bitEP.raw"

    # Nx=854 
    # Ny=Nx
    # stopz= 720 

else:
    filename0 = "dataset_0.npy"
    filename1 = "dataset_1.npy"



def importimage(filename):
    """Function to import 1 image. This can be numpy, raw 8 bits or 16 bits, big endian."""
    path =os.path.join(inputfolder,filename)
    if raw==False:
        image = np.load(path)
    else:
        Dim_size=np.array((Nx,Ny,stopz)) #Or read that from your mhd info File
        f=open(path,'rb')
        if bit == 8:
            image=np.fromfile(f,dtype=np.dtype('>u1'))
        elif bit == 16:
            image=np.fromfile(f,dtype=np.dtype('>u2'))
        image = image[0:Nx*Ny*stopz].reshape(Dim_size[2],Dim_size[1],Dim_size[0])#reshape(Dim_size[2],Dim_size[1],Dim_size[0])
        
    return image

# sometimes it is useful to simulate data e.g. to check positive axes direction
#-------------------------------------------
def func_simulate_data():
    """Simulates data."""
    x = np.arange(0,0.300,0.00025) #1200
    y = np.arange(0,0.400,0.0005) #800
    z = np.arange(0,500,0.75) #667
    XX,YY,ZZ =np.meshgrid(y,z,x)
    image = (XX+YY+ZZ)
    
    return image


# main code below
#------------------------------------------------------
image0=importimage(filename0)
image1=importimage(filename1)

# simulate data if desired
if simulate ==True:
    image0=func_simulate_data()
    image1=image0*0.00000000000000001

# if point zero is not defined, it calculates one
#-----------------------------------------------------
if pointzero == False:
    centre3d_0=np.array([round(image0.shape[0]/2),round(image0.shape[1]/2),round(image0.shape[2]/2)])
    p3d_0=centre3d_0

# run automatic registration
#-----------------------------------------------------------------
# create an object of the class or the class with plottings
if intermediate_plot is False:
    object = automatic_registration(image0,image1,p3d_0,size)
    # run automatic registration
    object.run()
else:
    object  = automatic_registration_with_plotting(intermediate_plot,filename0,filename1,outputfolder,save, image0,image1,p3d_0,size)
    # run automatic registration
    object.run()
    #visualise plots
    object.show_plots()

# extract results
image0 = object.image0
image1 = object.image1

# use cil to visualise every slice in the volume, uncomment the cil import to use this functionality
#---------------------------------------------------
if slice_plot==True:
    diff3D=image0-image1
    for ii in range (0,stopz,100):
        show2D(diff3D[ii,:,:])

