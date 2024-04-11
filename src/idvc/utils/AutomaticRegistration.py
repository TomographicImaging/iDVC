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
        Initialize an object for automatic registration of images.

        Parameters
        ----------
        im0 : numpy.ndarray
            The reference image (3D numpy array).
        im1 : numpy.ndarray
            The image to be registered (3D numpy array).
        p3d_0 : list[int, int, int]
            The starting point for the registration process.
        size : numpy.ndarray
            The size of the volume in which the registration is performed.
            Format: [[int, int], [int, int], [int, int]]
        log_folder : str, optional
            The folder path where the log file for automatic registration will be saved.
            If not provided, no logging will be saved.
        err_thresh : int, optional
            The error threshold allowed by the registration procedure in each direction (in pixels).
        max_iterations : int, optional
            The maximum number of iterations allowed for the registration process.
        """
        # image0 and image1 are redefined in `run`
        self.image0 = im0
        self.image1 = im1
        self.p3d_0 = p3d_0
        self.size = size
        self.edge = self.calc_edge()
        datatype = im0.dtype
        if datatype == 'int8' or datatype == 'uint8' or datatype == '>u1' or datatype == '<u1':
            self.datatype_slice = 'int16'
        elif datatype == 'int16' or datatype == 'uint16' or datatype == '>u2' or datatype == '<u2':
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
        Given the vertices position of the parallelepiped, it outputs an array with the edges
        values (in pixels) plus the first and second edge repeated.
        The repetition is to simplify the coding in other methods.

        Returns:
            list: A list containing the edge lengths of the parallelepiped.
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
            The correlation matrix of `sel0`, `sel1`.
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
            The position of the slice along the `dimension` axis in the 3D arrays.
        dimension : int {`0`, `1`, `2`}
            Represents one of the xyz spatial axis in the 3D images.

        Returns
        --------
        sel0 : 2D numpy.array
            The selected slice in `im0`.
        sel1 : 2D numpy.array
            The selected slice in `im1`.
        diff : 2D numpy.array
            The difference between `sel0` and `sel1`.
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
        Function to output the slices at position `selected_slice` of two 3D images.
        This function also changes the type of the data so the values can be signed
        when calculating the difference diff.

        Parameters
        ----------
        im0 : numpy.ndarray
            The first 3D image.
        im1 : numpy.ndarray
            The second 3D image.
        selected_slice : int
            The position of the slice along the specified `dimension` in the 3D arrays.
        dimension : int {0, 1, 2}
            The axis representing one of the xyz spatial dimensions in the 3D images.

        Returns
        -------
        sel0 : numpy.ndarray
            The selected slice in `im0`.
        sel1 : numpy.ndarray
            The selected slice in `im1`.
        diff : numpy.ndarray
            The difference between `sel0` and `sel1`.
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
        ----------
        sel0 : numpy.ndarray
            The first 2D image array.
        sel1 : numpy.ndarray
            The second 2D image array.

        Returns
        -------
        shift2D : list[int, int]
            The displacement of the two images with respect to the center of `sel0` and `sel1`.
            The convention for the sign of the displacement is considered.
        max : float
            The maximum value of the correlation matrix corresponding to the displacement.
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
        ----------
        im0 : numpy.ndarray
            The first 3D image array.
        im1 : numpy.ndarray
            The second 3D image array.
        shift3D : numpy.ndarray or list[int, int, int]
            The amount of shift to be applied to the images along each axis.
            The sign convention is taken into account to shift the 3D
            arrays in the right directions.

        Returns
        -------
        tuple[numpy.ndarray, numpy.ndarray]
            A tuple containing the shifted 3D image arrays.
            The first element is the shifted version of `im0`.
            The second element is the shifted version of `im1`.
            The size of the arrays may be reduced depending on the shift values.
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
        return im0, im1

    def shift_point_zero(self, p3d, shift3D, im0):
        """
        Revaluate the coordinates of a fixed point zero, `p3d`, whose 3d images have
        been shifted by `shift_3D`. If the shift is negative, the value is reassigned
        by subtracting the shift. If the shift is positive, the value is reassigned to that
        corresponding to the maximum index for `im0` in the axis of the shift.

        Parameters
        ----------
        p3d : numpy.ndarray or list[int, int, int]
            The coordinates of the fixed point zero.
        shift3d : numpy.ndarray or list[int, int, int]
            The shift values in each dimension.
        im0 : numpy.ndarray
            The 3D numpy array representing the image.

        Returns
        -------
        numpy.ndarray or list[int, int, int]
            The updated coordinates of the fixed point zero.
        """
        for dim in range(0, 3):
            if shift3D[dim] < 0:
                p3d[dim] = p3d[dim] + shift3D[dim]
            if shift3D[dim] > 0 and p3d[dim] >= np.shape(im0)[dim]:
                p3d[dim] = np.shape(im0)[dim] - 1
        return p3d

    def iterative_func(self, im0, im1):
        """
        Iterates the shift calculation process between two 3D image arrays.

        This method isolates the steps that will be iterated in a while loop. It can be redefined to
        add additional functionality to the iterations, such as plotting.

        Parameters
        ----------
        im0 : numpy.ndarray
            The first 3D image array.
        im1 : numpy.ndarray
            The second 3D image array.

        Returns
        -------
        DD3d : numpy.ndarray
            The calculated 3D shift between im0 and im1, in units of pixels.
        err : numpy.ndarray
            The error on the shift calculation, in units of pixels.
        """
        DD3d, err = self.calc_shift(im0, im1)
        return DD3d, err

    def calc_shift(self, im0, im1):
        """
        Calculates the 3D shift between two 3D numpy arrays

        Parameters
        ----------
        im0 : numpy.ndarray
            The reference image.
        im1 : numpy.ndarray
            The target image.

        Returns
        -------
        DD3d : numpy.ndarray
            The 3D shift evaluated from im0 and im1, in units of pixels.
        err : numpy.ndarray
            The error on shift calculation in units of pixels.
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
        Calculates the alternative shift in one direction. This method selects the
        minimum shift among the couplets whose elements have the same sign.

        Parameters:
        ----------
        DD3d : numpy.ndarray [int, int, int]
            The current shift in the 3 directions.
        DD6d : numpy.ndarray [int, int, int, int, int, int]
            The couplets of shifts in the 3 directions calculated as the position
            of the maximum in the correlation matrices.

        Returns:
        -------
        numpy.ndarray [int, int, int]
            The updated shift in the 3 directions.
                Only one of the values could be updated by this method.
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
        """
        Choose the shift between two numbers.

        The shift between two numbers is determined based on the following rules:
        - If the signs of the two numbers are the same, the shift is set to the
          minimum of their absolute values.
        - If the signs are different, the shift is set to 0.

        Parameters:
        -----------
        a : np.int
            The first number.
        b : np.int
            The second number.

        Returns:
        --------
        np.int
            The chosen shift value.
        """
        return np.sign(a) * np.min(abs(np.array([a, b]))) if np.sign(
            a) == np.sign(b) else 0

    def run(self):
        """
        Run the automatic registration algorithm.

        This method performs the automatic registration algorithm by iteratively
        shifting 3D arrays and updating the point zero. It accumulates the overall
        3D shift and calculates the relative error at each iteration. The algorithm
        stops when the accumulated shift is zero or the maximum number of iterations
        is reached.

        Returns:
        --------
            None
        """
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
        """
        Initializes an instance of the AutomaticRegistrationWithPlotting class.

        Parameters
        ----------
        intermediate_plot : bool
            Flag indicating whether to generate intermediate plots.
        filename0 : str
            Path to the first input file.
        filename1 : str
            Path to the second input file.
        outputfolder : str
            Path to the output folder.
        save : bool
            Flag indicating whether to save the output.
        *args :
            Variable length argument list.
        **kwargs :
            Arbitrary keyword arguments.
        """
        self.intermediate_plot = intermediate_plot
        self.filenames = [filename0, filename1]
        self.outputfolder = outputfolder
        self.save = save
        super(AutomaticRegistrationWithPlotting,
              self).__init__(*args, **kwargs)

    def iterative_func(self, im0, im1):
        """
        Redefines the iterative function in the parent class.
        As in the parent class, this method iterates the shift calculation process
        between two 3D image arrays.
        It adds additional functionality by plotting the intermediate results.

        Parameters
        ----------
        im0 : numpy.ndarray
            The first 3D image array.
        im1 : numpy.ndarray
            The second 3D image array.

        Returns
        -------
        DD3d : numpy.ndarray
            The calculated 3D shift between im0 and im1, in units of pixels.
        err : numpy.ndarray
            The error on the shift calculation, in units of pixels.
        """
        DD3d, err = self.calc_shift(im0, im1)
        self.plot_three_directions(im0, im1)
        return DD3d, err

    def intensity_plot_array(self, a0, a1, a2, a3, dim, displacementpar,
                             rect00, rect10):
        """
        This method plots four images: a0, a1, a2, and a3, along with their corresponding colorbars.
        It also adds rectangle patches to the first and second images.
        The plot is saved as a figure if the 'save' parameter is set to True.

        Parameters
        ----------
        a0 : numpy.ndarray
            The first image array.
        a1 : numpy.ndarray
            The second image array.
        a2 : numpy.ndarray
            The cross-correlation image array.
        a3 : numpy.ndarray
            The difference image array.
        dim : int
            The dimension along which the slice is taken.
        displacementpar : str
            The displacement parameter.
        rect00 : matplotlib.patches.Rectangle
            The rectangle patch for the first image.
        rect10 : matplotlib.patches.Rectangle
            The rectangle patch for the second image.

        Returns
        -------
        None
        """
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
        txt = "\nImage0 = " + self.filenames[
            0] + ".\nImage1 = " + self.filenames[1] + ".\npoint zero = " + str(
                self.p3d_0) + ". uservolume = " + str(self.size[0]) + str(
                    self.size[1]) + str(self.size[2])
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
        if self.save is True:
            fig.savefig(os.path.join(
                self.outputfolder,
                'full_figure_' + displacementpar + str(dim) + '.png'),
                        dpi=600)
        return

    def plot_three_directions(self, im0, im1):
        """
        Plots image slices indicated by `self.p3d_0` and `self.size` in the three dimensions.

        Parameters
        ----------
        im0 : numpy.ndarray
            The first 3D image array.
        im1 : numpy.ndarray
            The second 3D image array.

        Returns
        ------
        None
        """
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
                self.intensity_plot_array(largesel0, largesel1,
                                          corr_img, diff, dim,
                                          str(self.DD3d_accumulate), rect1,
                                          rect2)

    def show_plots(self):
        """
        Show all the plots on the screen.

        This method displays all the plots generated by the class on the screen.
        If the `intermediate_plot` flag is set to True, the plots will be shown.
        """
        if self.intermediate_plot is True:
            self.plt.show()
