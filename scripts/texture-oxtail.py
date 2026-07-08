#%%
from tracemalloc import start

import numpy as np
from skimage.feature import graycomatrix, graycoprops
import matplotlib.pyplot as plt
import vtk
from ccpi.viewer.utils.conversion import cilRawCroppedReader
import os

output_dir = os.path.abspath( "/Users/edoardo.pasca/Analysis/ALC-421/plots" )

#%%
# data = np.load("/Users/edoardo.pasca/Data/DVC_test_images/frame_000_f.npy")
# /Users/edoardo.pasca/Data/ALC-421/CC/123744_854xy_720z_8bitEP.raw
data_file = "/Users/edoardo.pasca/Data/ALC-421/CC/123744_854xy_720z_8bitEP.raw"
reader = cilRawCroppedReader()
reader.SetFileName(data_file)
reader.SetStoredArrayShape((720, 854, 854))
reader.SetTargetZExtent((270, 270))
reader.SetOutputVTKType(vtk.VTK_UNSIGNED_CHAR)
reader.Update()
vtkdata = reader.GetOutput()

#%%
# from ccpi.viewer import CILViewer2D as viewer
# v = viewer.CILViewer2D()
# v.setInputData(vtkdata)
# v.startRenderLoop()
# exit()
#%%
from ccpi.viewer.utils.conversion import Converter
data = Converter.vtk2numpy(vtkdata)[0]

#%%
fig, ax = plt.subplots()
ax.imshow(data, cmap='gray')

start = 700
dsize = 20
ax.plot([start + i for i in range(dsize)], [750 for i in range(dsize)], color='C1', linewidth=2)
plt.show()

# %%
# get a subsection of the image
registration_region = 250
registration_p0 = [500,500]

sub_image = data[
                 registration_p0[0]:registration_p0[0]+registration_region,
                 registration_p0[1]:registration_p0[1]+registration_region]

fig, ax = plt.subplots()

ax.imshow(sub_image, cmap='gray')
start = 100
xlength = 150
ax.plot([start + i for i in range(dsize)], [xlength for i in range(dsize)], color='C1', linewidth=2)
plt.show()
#%%

# Visualise the sub-image within the whole image
# and the size of the features we are tracking on
from matplotlib.patches import Rectangle
box = Rectangle((registration_p0[1], registration_p0[0]), registration_region, registration_region, linewidth=2, edgecolor='white', facecolor='none')

fig, ax = plt.subplots()
ax.imshow(data, cmap='gray')
start = 600
ax.plot([start + i for i in range(dsize)], [registration_p0[0] + registration_region//2 for i in range(dsize)], color='C1', linewidth=2)
ax.add_patch(box)
sax = ax.inset_axes([0, 0.5, 0.5, 0.5])
sax.imshow(sub_image, cmap='gray')
sax.get_xaxis().set_visible(False)
sax.get_yaxis().set_visible(False)
start = start - registration_p0[1]
sax.plot([start + i for i in range(dsize)], [registration_region//2 for i in range(dsize)], color='C1', linewidth=2)
plt.show()

# %%
distances = np.asarray([i for i in range(40)])
angles = [ i * np.pi/4 for i in range(4)]

result = graycomatrix(sub_image, distances=distances, angles=angles, levels=256, 
                      symmetric=False, normed=False)

# %%
contrast = graycoprops(result, 'contrast')
dissimilarity = graycoprops(result, 'dissimilarity')
homogeneity = graycoprops(result, 'homogeneity')
ASM = graycoprops(result, 'ASM')
energy = graycoprops(result, 'energy')
#%%
plt.style.use('tableau-colorblind10')

plt.plot(homogeneity.T[0], label='Homogeneity')
plt.plot(ASM.T[0], label='ASM')
plt.plot(energy.T[0], label='Energy')
plt.legend()
# %%
# plt.plot(dissimilarity.T[0], label='Dissimilarity')

# yy = np.gradient(contrast.T[0], distances/2)
# threshold = yy < (yy.max() * 0.1)
# for i in range(len(yy)):
#     if threshold[i]:
#         break
# print (i, distances[i]*2)

for a in angles:
    plt.plot(distances*2,contrast.T[angles.index(a)], label=f'angle {np.degrees(a)}')
    # plt.plot(distances*2,
    #          yy,
    #          label=f'angle {np.degrees(a)}')
plt.title('Contrast')
plt.xlabel('Subvolume size')
plt.legend()
# plt.legend()
# %%
for a in angles:
    plt.plot(distances*2,dissimilarity.T[angles.index(a)], label=f'angle {np.degrees(a)}')
plt.title('Dissimilarity')
plt.xlabel('Subvolume size')
plt.legend()
# %%
fig, ax = plt.subplots(2, 1, figsize=(10, 10))
x = distances*2
for a in angles:
    ax[0].plot(x, contrast.T[angles.index(a)], label=f'angle {np.degrees(a)}')
    ax[1].plot(x, dissimilarity.T[angles.index(a)], label=f'angle {np.degrees(a)}')
ax[0].set_title('Contrast')
ax[1].set_title('Dissimilarity')
ax[1].set_xlabel('Subvolume size')
ax[0].legend()
ax[1].legend()
# %%
fig.savefig(os.path.join(output_dir, "oxtail-texture_analysis.png"), 
            dpi=300,
            bbox_inches="tight")
# %%
