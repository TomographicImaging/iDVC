#%%
from tracemalloc import start

import numpy as np
from skimage.feature import graycomatrix, graycoprops
import matplotlib.pyplot as plt

#%%
data = np.load("/Users/edoardo.pasca/Data/DVC_test_images/frame_000_f.npy")

fig, ax = plt.subplots()
ax.imshow(data[500], cmap='gray')

start = 700
ax.plot([start + i for i in range(40)], [750 for i in range(40)], color='C1', linewidth=2)
plt.show()

# %%
# get a subsection of the image
registration_region = 250
registration_p0 = [600,600]

sub_image = data[500,
                 registration_p0[0]:registration_p0[0]+registration_region,
                 registration_p0[1]:registration_p0[1]+registration_region]

fig, ax = plt.subplots()

ax.imshow(sub_image, cmap='gray')
start = 100
ax.plot([start + i for i in range(40)], [150 for i in range(40)], color='C1', linewidth=2)
plt.show()
#%%

# Visualise the sub-image within the whole image
# and the size of the features we are tracking on

fig, ax = plt.subplots()
ax.imshow(data[500], cmap='gray')
start = 700
ax.plot([start + i for i in range(40)], [750 for i in range(40)], color='C1', linewidth=2)
sax = ax.inset_axes([0, 0.5, 0.5, 0.5])
sax.imshow(sub_image, cmap='gray')
sax.get_xaxis().set_visible(False)
sax.get_yaxis().set_visible(False)
start = start - registration_p0[0]
sax.plot([start + i for i in range(40)], [150 for i in range(40)], color='C1', linewidth=2)
plt.show()

# %%
distances = [i for i in range(80)]
angles = [0, np.pi/4, np.pi/2, 3*np.pi/4]

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
for a in angles:
    plt.plot(contrast.T[angles.index(a)], label=f'angle {np.degrees(a)}')
plt.title('Contrast')
plt.xlabel('Distance')
plt.legend()
# plt.legend()
# %%
for a in angles:
    plt.plot(dissimilarity.T[angles.index(a)], label=f'angle {np.degrees(a)}')
plt.title('Dissimilarity')
plt.xlabel('Distance')
plt.legend()
# %%
fig, ax = plt.subplots(2, 1, figsize=(10, 10))

for a in angles:
    ax[0].plot(contrast.T[angles.index(a)], label=f'angle {np.degrees(a)}')
    ax[1].plot(dissimilarity.T[angles.index(a)], label=f'angle {np.degrees(a)}')
ax[0].set_title('Contrast')
ax[1].set_title('Dissimilarity')
ax[1].set_xlabel('Distance')
ax[0].legend()
ax[1].legend()
# %%
