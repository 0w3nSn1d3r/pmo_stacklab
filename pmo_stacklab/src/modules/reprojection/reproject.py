from align import Align
from register import Register
from astropy.nddata import CCDData


class Reproject:
    def __init__(self, register: str, align: str):
        match register:
            case 'triangulate':
                self.register = Register.triangulation
            case 'feature-match':
                self.register = Register.feature_match
            case 'logpolar-match':
                self.register = Register.logpolar_match
            case 'plate-solve':
                self.register = Register.plate_solve

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
        registered_data = self.register(data)
        final_data = self.align(registered_data)

        return final_data
