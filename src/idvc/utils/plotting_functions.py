import numpy as np

def intensityplot(intensity_matrix,title):
   """function to plot intensity - single image"""
   plt.imshow(intensity_matrix, cmap='gray',vmin=np.min(intensity_matrix),interpolation='none')
   plt.colorbar()
   plt.xlabel('x')
   plt.ylabel('y')
   plt.title('Intensity plot '+str(title))
   plt.show()
   return


