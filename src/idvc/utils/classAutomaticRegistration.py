import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import scipy.signal
from matplotlib.patches import Rectangle


class AutomaticRegistration:

    def __init__(self,
                 im0,
                 im1,
                 p3d_0,
                 size,
                 log_folder=None,
                 err_thresh=2,
                 max_iterations=30):
        """
        Instances an object with attributes `image0` and `image1`, which are automatically
        registered from `im0` and `im1`.

        Parameters
        ------------
        im0 : 3D numpy.array
            Image 0 (reference)
        im1 : 3D numpy.array
            Image 1 (to perform DVC wrt to a reference image)
        p3d_0 : [int, int, int]
            Point zero from which DVC starts. A good choice is a point which
                is known to be unchanged.
        size : numpy.array [[int, int], [int, int], [int, int]]
            Size of the volume in which the registration is performed.
                Usually a volume which is known to be unchanged.
                The shape is a right parallelepiped (edges not necessarily the same)
        log_folder : path, default: None
            folder where to save log file for automatic registration. If None, no logging is saved
        err_thresh : int
            Error allowed by the procedure in each direction (units of pixels).
        max_iterations : int
            maximum number of iterations allowed


        """
        # image0 and image1 are redefined in `run`
        self.image0 = im0
        self.image1 = im1
        self.p3d_0 = p3d_0
        self.size = size
        self.edge = self.calc_edge()
        datatype = im0.dtype
        if datatype == 'int8' or datatype == '>u1':
            self.datatype_slice = 'int16'
        elif datatype == 'int16' or datatype == '>u2':
            self.datatype_slice = 'int32'
        self.err_thresh = err_thresh
        self.max_iterations = max_iterations
        if log_folder is not None:
            self.log_folder = log_folder
            logger = logging.getLogger()
            file_handler = logging.FileHandler(
                filename=log_folder + r'\automatic_registration_logging.log',
                mode='w')
            formatter = logging.Formatter("%(asctime)s %(message)s")
            file_handler.setFormatter(formatter)
            logger.setLevel(logging.INFO)
            logger.addHandler(file_handler)

    def calc_edge(self):
        """
        Given the vertices position of the parallelepiped, it outputs an array with the egdes
        values (in pixels) plus the first and second edge repeated.
        The repetition is to simplify the coding in other methods.
        """
        edge = []
        for dim in range(0, 3):
            edge.append(abs(self.size[dim, 0] - self.size[dim, 1]))
        edge.append(edge[0])
        edge.append(edge[1])
        return edge

    def cross_image(self, sel0, sel1):
        """
        Calculate cross image of two 2D images, they can have any size as
        long as they are equal size.

        Parameters
        ------------
        sel0 : 2D numpy.array
        sel1 : 2D numpy.array

        Returns
        --------
        corr_img : 2D numpy.array
            correlation matrix of `sel0`, `sel1`.
        """
        sel0_float = sel0.astype('float')
        sel1_float = sel1.astype('float')
        sel0_float -= np.mean(sel0_float)
        sel1_float -= np.mean(sel1_float)
        # calculate the correlation image by doing a convolution and flipping of one of the images,
        # this is faster than correlate2D
        # ::-1 returns a new list or string with all elements in reverse order
        corr_img = scipy.signal.fftconvolve(sel0_float,
                                            sel1_float[::-1, ::-1],
                                            mode='same')
        return corr_img

    def func_slicing_uservolume(self, im0, im1, selected_slice, dimension):
        """
        Function to output the slices at position `selectedslice` of two 3D images.
        Selects the slice in a smaller volume defined by the user with `self.size`.
        This function also changes the type of the data so the values can be signed
        when calculating the difference diff.

        Parameters
        ------------
        im0 : 3D numpy.array
        im1 : 3D numpy.array
        selected_slice : int
            along `dimension`, position of the element in the 3D arrays.
        dimension : int {`0`, `1`, `2`}
            represents one of the xyz spatial axis in the 3D images.
        size : np.array, [[int, int], [int, int], [int, int]]

        Returns
        --------
        sel0 : 2D numpy.array
            Selected slice in `im0`.
        sel1 : 2D numpy.array
            Selected slice in `im1`.
        diff : 2D numpy.array
            Difference between `sel0` and `sel1`.
        """
        size = self.size
        datatype_slice = self.datatype_slice

        if dimension == 0:
            sel0 = im0[selected_slice, size[1, 0]:size[1, 1],
                       size[2, 0]:size[2, 1]].astype(datatype_slice)
            sel1 = im1[selected_slice, size[1, 0]:size[1, 1],
                       size[2, 0]:size[2, 1]].astype(datatype_slice)
        elif dimension == 1:
            sel0 = im0[size[0, 0]:size[0, 1], selected_slice,
                       size[2, 0]:size[2, 1]].astype(datatype_slice)
            sel1 = im1[size[0, 0]:size[0, 1], selected_slice,
                       size[2, 0]:size[2, 1]].astype(datatype_slice)
        elif dimension == 2:
            sel0 = im0[size[0, 0]:size[0, 1], size[1, 0]:size[1, 1],
                       selected_slice].astype(datatype_slice)
            sel1 = im1[size[0, 0]:size[0, 1], size[1, 0]:size[1, 1],
                       selected_slice].astype(datatype_slice)

        diff = sel0 - sel1

        return sel0, sel1, diff

    def func_slicing(self, im0, im1, selected_slice, dimension):
        """
        Function to output the slices at position `selectedslice` of two 3D images.
        This function also changes the type of the data so the values can be signed
        when calculating the difference diff.

        Parameters
        ------------
        im0 : 3D numpy.array
        im1 : 3D numpy.array
        selected_slice : int
            along `dimension`, position of the element in the 3D arrays.
        dimension : int {`0`, `1`, `2`}
            represents one of the xyz spatial axis in the 3D images.
        size : np.array, [[int, int], [int, int], [int, int]]

        Returns
        --------
        sel0 : 2D numpy.array
            Selected slice in `im0`.
        sel1 : 2D numpy.array
            Selected slice in `im1`.
        diff : 2D numpy.array
            Difference between `sel0` and `sel1`.
        """
        datatype_slice = self.datatype_slice

        if dimension == 0:
            sel0 = im0[selected_slice, :, :].astype(datatype_slice)
            sel1 = im1[selected_slice, :, :].astype(datatype_slice)
        elif dimension == 1:
            sel0 = im0[:, selected_slice, :].astype(datatype_slice)
            sel1 = im1[:, selected_slice, :].astype(datatype_slice)
        elif dimension == 2:
            sel0 = im0[:, :, selected_slice].astype(datatype_slice)
            sel1 = im1[:, :, selected_slice].astype(datatype_slice)

        diff = sel0 - sel1

        return sel0, sel1, diff

    def func_2D_displacement(self, sel0, sel1):
        """
        Calculates the maximum of the correlation matrix between two images and its position,
        which could represent the displacement of two shifted images.

        Parameters
        -----------------------
        sel0 : 2D numpy.array
        sel1 : 2D numpy.array

        Returns
        -----------------------
        shift2D : [int, int]
            displacement wrt to centre of images `sel0` and `sel1`. Be aware of the sign covention.
        max : float
            value of `corr_img` at position `DD`
        """
        corr_img = self.cross_image(sel0, sel1)
        displacement = np.array(
            np.unravel_index(np.argmax(corr_img), corr_img.shape))
        max = corr_img[displacement[0], displacement[1]]
        centre = np.array([round(sel0.shape[0] / 2), round(sel0.shape[1] / 2)])
        shift2D = centre - displacement
        return shift2D, max

    def shift_3D_arrays(self, im0, im1, shift3D):
        """
        Implements the shift of two 3D images by the quantity `shift3D`.
        The result could crop both images and change the size of the returned 3D arrays.

        Parameters
        -----------------------
        im0 : 3D numpy.array
        im1 : 3D numpy.array
        shift3D : [int, int, int]
            The sign convention is taken into account to shift the 3D
                arrays in the right directions.

        Returns
        -----------------------
        im0 : 3D numpy.array
            Could have reduced size wrt input.
        im1 : 3D numpy.array
            Could have reduced size wrt input.
        """
        if shift3D[0] > 0:
            im0 = im0[:-shift3D[0], :, :]
            im1 = im1[shift3D[0]:, :, :]
        elif shift3D[0] < 0:
            im0 = im0[abs(shift3D[0]):, :, :]
            im1 = im1[:-abs(shift3D[0]), :, :]
        if shift3D[1] > 0:
            im0 = im0[:, :-shift3D[1], :]
            im1 = im1[:, shift3D[1]:, :]
        elif shift3D[1] < 0:
            im0 = im0[:, abs(shift3D[1]):, :]
            im1 = im1[:, :-abs(shift3D[1]), :]
        if shift3D[2] > 0:
            im0 = im0[:, :, :-shift3D[2]]
            im1 = im1[:, :, shift3D[2]:]
        elif shift3D[2] < 0:
            im0 = im0[:, :, abs(shift3D[2]):]
            im1 = im1[:, :, :-abs(shift3D[2])]
        return (im0, im1)

    def shift_point_zero(self, p3d, shift3D, im0):
        """
        Revaluate the coordinates of a fixed point zero, `p3d`, whose 3d images have
        been shifted by `shift_3D`. If the shift is negative, the value is reassigned
        by subtracting the shift. If the shift is positive, the value is reassigned to that
        corresponding to the maximum index for `im0` in the axis of the shift.

        Parameters
        -----------------------
        p3d : [int, int, int]
        shift3d : [int, int, int]
        im0 : 3D numpy.array

        Returns
        -----------------------
        p3d : [int, int, int]
        """
        for dim in range(0, 3):
            if shift3D[dim] < 0:
                p3d[dim] = p3d[dim] + shift3D[dim]
            if shift3D[dim] > 0 and p3d[dim] >= np.shape(im0)[dim]:
                p3d[dim] = np.shape(im0)[dim] - 1
        return p3d

    def iterative_func(self, im0, im1):
        """
        Isolates the methods which will be iterated in a while loop. This can be redefined to
        add functionality to the iterations, e.g. in the plotting class.
        """
        DD3d, err = self.calc_shift(im0, im1)
        return DD3d, err

    def calc_shift(self, im0, im1):
        """        Calculates

        Parameters
        ------------
        im0 : 3D numpy.array
        im1 : 3D numpy.array

        Returns
        --------
        DD3d : numpy.array [int, int, int]
            3D shift evaluated from im0 and im1, in units of pixels
        err : numpy.array [int, int, int]
            error on shift calculation in untis of pixels
        """

        logging.info("Size of ref is " + str(np.shape(im0)) + ".")
        logging.info("Size of image 1 is " + str(np.shape(im1)) + ".\n")

        # centre3d = np.array([
        #     round(im0.shape[0] / 2),
        #     round(im0.shape[1] / 2),
        #     round(im0.shape[2] / 2)
        # ])
        # initialise the array to store 2 displacements in 3 directions
        DD6d = []
        # store max values of correlation matrices in the 3 directions
        for dim in range(0, 3):
            [sel0,
             sel1] = self.func_slicing_uservolume(im0, im1, self.p3d_0[dim],
                                                  dim)[0:2]
            DD = self.func_2D_displacement(sel0, sel1)[0]
            DD6d.append(DD)

        DD6d = np.array(DD6d)
        logging.info(
            "Array of displacements from the correlation images in 3 directions is \n"
            + str(DD6d) + ".\n")
        logging.info("Couplets are " + str([DD6d[2, 0], DD6d[1, 0]]) +
                     str([DD6d[0, 0], DD6d[2, 1]]) +
                     str([DD6d[0, 1], DD6d[1, 1]]) + ".")
        DD3d = np.array([0, 0, 0])
        err = [
            abs(DD6d[2, 0] - DD6d[1, 0]),
            abs(DD6d[0, 0] - DD6d[2, 1]),
            abs(DD6d[0, 1] - DD6d[1, 1])
        ]
        if err[0] <= self.err_thresh:
            DD3d[0] = DD6d[2, 0]
        if err[1] <= self.err_thresh:
            DD3d[1] = DD6d[0, 0]
        if err[2] <= self.err_thresh:
            DD3d[2] = DD6d[1, 1]

        if sum(abs(DD3d)) == 0:
            DD3d = self.calc_alternative_shift(DD3d, DD6d)
        logging.info("Calculated shift for this cycle is " + str(DD3d) + ".\n")

        return DD3d, err

    def calc_alternative_shift(self, DD3d, DD6d):
        """
        Only a shift in one direction is selected. This is selected as the minimum shift among
        the couplets whose members have the same sign.

        Parameters:
        ----------------
        DD3d: np.array [int, int, int]
              The shift in the 3 directions.
        DD6d: np.array [int, int, int, int, int, int]
              The couplets of shifts in the 3 directions calculated as the position
                of the maximum in the correlation matrices.

        Returns:
        DD3d: np.array [int, int, int]
        The shift in the 3 directions. Only one of the values could be updated by this method.

        """
        tmp = np.array([
            self.choose_shift(DD6d[2, 0], DD6d[1, 0]),
            self.choose_shift(DD6d[0, 0], DD6d[2, 1]),
            self.choose_shift(DD6d[0, 1], DD6d[1, 1])
        ])
        uDD3d = abs(tmp)
        if sum(abs(uDD3d)) != 0:
            minval = np.min(uDD3d[np.nonzero(uDD3d)])
            index = np.where(uDD3d == minval)[0][0]
            DD3d[index] = tmp[index]
        return np.array(DD3d)

    def choose_shift(self, a, b):
        """The shift between two numbers is chosen as follows.
        If sign of two numbers is the same return the minimum, otherwise return 0.

        Parameters:
        ----------------------
        a, b: np int
        """
        return np.sign(a) * np.min(abs(np.array([a, b]))) if np.sign(
            a) == np.sign(b) else 0

    def run(self):
        """Run the automatic registration algorithm."""
        # overall 3D shift
        self.DD3d_accumulate = [0, 0, 0]
        for counter in range(0, self.max_iterations):
            logging.info("\n\nCycle number " + str(counter) + ".\n")
            DD3d, err = self.iterative_func(self.image0, self.image1)
            err_rel = (err[0] / self.image0.shape[0] +
                       err[1] / self.image0.shape[1] +
                       err[2] / self.image0.shape[2]) / 3
            self.DD3d_accumulate = np.add(self.DD3d_accumulate, DD3d)
            logging.info("Relative error is " + str(err_rel) + ".\n")
            self.image0, self.image1 = self.shift_3D_arrays(
                self.image0, self.image1, DD3d)
            self.p3d_0 = self.shift_point_zero(self.p3d_0, DD3d, self.image0)
            logging.info("New point zero is" + str(self.p3d_0) + ".\n")
            if sum(abs(DD3d)) == 0:
                break

        logging.info("\n\nResults:\n")
        DD3d, err = self.iterative_func(self.image0, self.image1)
        logging.info("Relative error is " + str(err_rel) + ".\n\n\n\n\n")

        logging.info("Overall shift is" + str(self.DD3d_accumulate) + ".\n")
        logging.info(
            '-----------------Automatic registration ends successfully.-----------------\n\n\n\n\n'
        )


class AutomaticRegistrationWithPlotting(AutomaticRegistration):

    def __init__(self, intermediate_plot, filename0, filename1, outputfolder,
                 save, *args, **kwargs):
        self.intermediate_plot = intermediate_plot
        self.filenames = [filename0, filename1]
        self.outputfolder = outputfolder
        self.save = save
        super(AutomaticRegistrationWithPlotting,
              self).__init__(*args, **kwargs)

    def iterative_func(self, im0, im1):
        DD3d, err = self.calc_shift(im0, im1)
        self.plot_three_directions(im0, im1)
        return DD3d, err

    def intensity_plot_array(self, a0, a1, a2, a3, dim, p3d_0, size,
                             displacementpar, rect00, rect10, filename0,
                             filename1, outputfolder, save):
        """function to plot intensity - array of four images"""
        # needs transpose because dim 1 has inverted axes
        if dim == 1:
            a0 = np.transpose(a0)
            a1 = np.transpose(a1)
            a2 = np.transpose(a2)
            a3 = np.transpose(a3)
        self.plt = plt
        fig, axs = plt.subplots(2, 2, sharex=False, sharey=False)
        fig.suptitle("Results after displacement of " + displacementpar +
                     ". Slice along dimension " + str(dim))
        txt = "\nImage0 = " + filename0 + ".\nImage1 = " + filename1 + ".\npoint zero = " + str(
            p3d_0) + ". uservolume = " + str(size[0]) + str(size[1]) + str(
                size[2])
        plt.figtext(0.5,
                    0.01,
                    txt,
                    wrap=True,
                    horizontalalignment='center',
                    fontsize=8)
        fig.tight_layout(h_pad=2)
        ax00 = axs[0, 0].imshow(a0,
                                origin='lower',
                                cmap='gray',
                                vmin=np.min(a0),
                                vmax=np.max(a0),
                                interpolation='none')
        axs[0, 0].set_title('Image 0')
        fig.colorbar(mappable=ax00, location='right', shrink=0.6)

        ax10 = axs[1, 0].imshow(a1,
                                origin='lower',
                                cmap='gray',
                                vmin=np.min(a1),
                                interpolation='none')
        axs[1, 0].set_title('Image 1')
        fig.colorbar(mappable=ax10, location='right', shrink=0.6)
        ax01 = axs[0, 1].imshow(a2,
                                origin='lower',
                                cmap='gray',
                                vmin=np.min(a2),
                                interpolation='none')
        axs[0, 1].set_title('Cross correlation')
        fig.colorbar(mappable=ax01, location='right', shrink=0.6)
        ax11 = axs[1, 1].imshow(a3,
                                origin='lower',
                                cmap='gray',
                                vmin=np.min(a3),
                                interpolation='none')
        axs[1, 1].set_title('Diff')
        fig.colorbar(mappable=ax11, location='right', shrink=0.6)
        axs[0, 0].set_ylabel('Dimension ' + str(np.mod(dim + 1, 3)))
        axs[1, 0].set_ylabel('Dimension ' + str(np.mod(dim + 1, 3)))
        axs[1, 0].set_xlabel('Dimension ' + str(np.mod(dim + 2, 3)))
        axs[1, 1].set_xlabel('Dimension ' + str(np.mod(dim + 2, 3)))
        # resize the figure to match the aspect ratio of the axes
        fig.set_size_inches(10, 12, forward=True)
        axs[0, 0].add_patch(rect00)
        axs[1, 0].add_patch(rect10)
        if save is True:
            fig.savefig(os.path.join(
                outputfolder,
                'full_figure_' + displacementpar + str(dim) + '.png'),
                        dpi=600)
        return

    def plot_three_directions(self, im0, im1):
        for dim in range(0, 3):
            [sel0, sel1,
             diff] = self.func_slicing_uservolume(im0, im1, self.p3d_0[dim],
                                                  dim)
            corr_img = self.cross_image(sel0, sel1)
            if self.intermediate_plot is True:
                # stored to plot the large images too
                [largesel0,
                 largesel1] = self.func_slicing(im0, im1, self.p3d_0[dim],
                                                dim)[0:2]
                # rect must be repeated otherwise it gives errors when plotting
                rect1 = Rectangle(
                    (self.size[np.mod(dim + 2, 3),
                               0], self.size[np.mod(dim + 1, 3), 0]),
                    self.edge[dim + 2],
                    self.edge[dim + 1],
                    linewidth=1,
                    edgecolor='r',
                    facecolor="none")
                rect2 = Rectangle(
                    (self.size[np.mod(dim + 2, 3),
                               0], self.size[np.mod(dim + 1, 3), 0]),
                    self.edge[dim + 2],
                    self.edge[dim + 1],
                    linewidth=1,
                    edgecolor='r',
                    facecolor="none")
                self.intensity_plot_array(largesel0, largesel1, corr_img, diff,
                                          dim, self.p3d_0, self.size,
                                          str(self.DD3d_accumulate), rect1,
                                          rect2, self.filenames[0],
                                          self.filenames[1], self.outputfolder,
                                          self.save)

    def show_plots(self):
        "This method shows all the plots on the screen."
        if self.intermediate_plot is True:
            self.plt.show()
