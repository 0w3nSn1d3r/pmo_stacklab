from astropy.nddata import CCDData


class Reproject:
    """
    Contains all reprojection coordination logic,
    including the selection of alignment and 
    registration functions
    """

    def __init__(self, register: function, align: function):
        # Assign registration and alignment functions as specified;
        # allow for stack pipeline customizability

        self.register = register
        self.align = align

    def reproject(self, data: CCDData) -> CCDData:
        """
        Coordinates specified registration and alignment functions
        from Reproject class to produce a fully reprojected image.

        :param self: references Reproject class

        :param data: contains pixel-value image data;
        expected to be 3D and calibrated
        :type data: CCDData

        :return: contains registered and aligned
        pixel-value image data
        :rtype: CCDData
        """

        registered_data = self.register(data)
        final_data = self.align(registered_data)

        return final_data
