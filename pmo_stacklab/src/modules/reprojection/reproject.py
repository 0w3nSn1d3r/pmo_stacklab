from align import Align
from register import Register
from astropy.nddata import CCDData


class Reproject:
    def __init__(self, register: str, align: str):
        # Prevent case errors
        register = register.lower()
        align = align.lower()

        # Define registration and alignment functions as specified;
        # allow for stack pipeline customizability
        match register:
            case 'triangulate':
                self.register = Register.triangulation
            case 'feature-match':
                self.register = Register.feature_match
            case 'logpolar-match':
                self.register = Register.logpolar_match
            case 'plate-solve':
                self.register = Register.plate_solve
            case _:
                raise ValueError(
                    'Function register() must be a string of value'
                    '"triangulate", "feature-match", "logpolar-match", or "plate-solve"'
                )

        match align:
            case 'bilinear':
                self.align = Align.bilinear
            case 'lanczos':
                self.align = Align.lanczos
            case 'area-overlap':
                self.align = Align.area_overlap
            case 'flux-conserving':
                self.align = Align.flux_conserving

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
