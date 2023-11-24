# Imports
import os
import sys
import numpy as np
#from cil.utilities.display import show2D, show_geometry

# User inputs
simulate=False
raw = True #True: input files are raw

pointzero = True #True if pointzero is inputted by user, False is automatically generated
intermediate_plot= True #plots the slices and the correlation images and the diff

slice_plot=False #plots things with islicer
save = False #save results in a file in the output folder
saveonlyfew = True #save results in a file in the output folder


uservolume = True #the user has selected a volume to analyse

# User defined in the gui
size =np.array([[1180,1380],[1180,1380],[1300,1500]]) #size of the volume in which to calculate the overall shift
p3d_0 = [1280,1280,1400] #point zero on which to calculate the overall shift

#brian point1
size =np.array([[1300,1500],[1180,1380],[1180,1380]]) #size of the volume in which to calculate the overall shift
p3d_0 = [1400,1280,1280]

#brian point2
#size =np.array([[500,700],[1180,1380],[2100,2300]]) #size of the volume in which to calculate the overall shift
#p3d_0 = [600,1280,2200]

#brian point3
#size =np.array([[500,700],[1180,1380],[450,650]]) #size of the volume in which to calculate the overall shift
#p3d_0 = [600,1280,550]


if (size[0,0]<=p3d_0[0]<=size[0,1]) and (size[1,0]<=p3d_0[1]<=size[1,1]) and (size[2,0]<=p3d_0[2]<=size[2,1])==False:
    print("Point zero is out of the selected volume")
    sys.exit() 
from class_automatic_registration import automatic_registration, automatic_registration_with_plotting
#%%
'Code introduction'
print("\nThis code implements the automatic registration of two volumetric images.\n")


'insert data location'
#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset'
inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\Dataset_example2'
#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\image_volumes'
#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\image_volumes\Set2'
#inputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_dataset\image_volumes\Set3'

outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Dataset_example2\point1_20231110'
#outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Set2\uservolume_analysis_test_code2_20231109'
#outputfolder = r'C:\Users\zvm34551\Coding_environment\DATA\DVC_output\image_volumes\Set3\uservolume_analysis_1_20231005'
if not os.path.exists(outputfolder):
    os.makedirs(outputfolder)
#print("Input folder is "+inputfolder+".\n")


# insert filenames of reference and image

if raw ==True:
    filename0 = "104506_distortion_corrected_2560_2560_1600_16bit.raw"
    filename1 = "104507_distortion_corrected_2560_2560_1600_16bit.raw"
    bit=[16,'big']
    datatype = '16'

    Nx=2560
    Ny=Nx
    stopz= 1600

    
    'August 2023 data from Catherine'
    #filename0 = "104531_distortion_corrected_2560_2560_1500_8bit.raw"
    #filename1 = "104532_distortion_corrected_2560_2560_1500_8bit.raw"

    # Nx=2560 #854 #
    # Ny=Nx
    # stopz= 1500#720 #number of slices imported

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
    'function to import image'
    path =os.path.join(inputfolder,filename)
    if raw==False:
        image = np.load(path)
    else:
        Dim_size=np.array((Nx,Ny,stopz))#((2560,2560,1600))#,dtype=np.dtype('>u2')) #Or read that from your mhd info File
        #Dim_size=np.array((2560,2560,10))#((2560,2560,1600))#,dtype=np.dtype('>u2')) #Or read that from your mhd info File
        f=open(path,'rb')
        if bit == 8:
            img_arr=np.fromfile(f,dtype=np.dtype('>u1'))
        elif bit == 16:
            img_arr=np.fromfile(f,dtype=np.dtype('>u2'))
        elif bit == [16,'big']:
            img_arr=np.fromfile(f,dtype=np.dtype('>u2'))
            image =img_arr[0:2560*2560*stopz].reshape(Dim_size[2],Dim_size[1],Dim_size[0])#reshape(Dim_size[2],Dim_size[1],Dim_size[0])
        #image =img_arr[0:65536000].reshape(Dim_size[2],Dim_size[1],Dim_size[0])#reshape(Dim_size[2],Dim_size[1],Dim_size[0])
        #image =img_arr[4916548:9501082948].reshape(Dim_size[2],Dim_size[1],Dim_size[0])#reshape(Dim_size[2],Dim_size[1],Dim_size[0])
        #ImageReader
    return image

def func_simulate_data():
    """simulates data"""
    x = np.arange(0,0.300,0.00025) #1200
    y = np.arange(0,0.400,0.0005) #800
    z = np.arange(0,500,0.75) #667
    XX,YY,ZZ =np.meshgrid(y,z,x)
    image = (XX+YY+ZZ)
    
    return image





#main code for this script, not necessary in gui
image0=importimage(filename0)
image1=importimage(filename1)

if simulate ==True:
    image0=func_simulate_data()
    image1=image0*0.00000000000000001
centre3d_0=np.array([round(image0.shape[0]/2),round(image0.shape[1]/2),round(image0.shape[2]/2)])
if pointzero == False:
    p3d_0=centre3d_0


#invoke the class
#code = automatic_registration(image0,image1,p3d_0,size,centre3d_0, uservolume,datatype)
code = automatic_registration_with_plotting(intermediate_plot,filename0,filename1,outputfolder,save, saveonlyfew, image0,image1,p3d_0,size,centre3d_0, uservolume,datatype)
image0 = code.image0
image1 = code.image1



'make plots'
#intensityplot(sel0,'Reference image')
#intensityplot(sel1,'Image 1')
#intensityplot(diff,'Im0-Im1')
#intensityplot(corr_img0,'')
#intensityplot(corr_img1,'')
#intensityplot(corr_imgdiff,DD)

#cutdiff=cutsel0-cutsel1
#print(cutsel0.shape)
#print(cutsel1.shape)
#intensityplot(diff[000:700,000:700],'Section diff')
#intensityplot(cutdiff[000:700,000:700],'Section diff translated')
#intensityplot(cutdiff,'Diff translated whole')

if slice_plot==True:
    diff3D=image0-image1
    for ii in range (0,stopz,100):
        show2D(diff3D[ii,:,:])


# %%
