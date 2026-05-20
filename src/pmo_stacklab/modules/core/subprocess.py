

class Subprocess:
    """
    The parent class for image-stacking subprocesses;
    allows key properties of all subprocesses
    to be reliably accessed using dot notation.

    :param: name - A string containing the subprocess name

    :param: operators - A tuple of the first-order functions 
                        used in the subprocess

    :param: coordinator - A function coordinating the operators 
                        to produce the final result of the subprocess
    """

    def __init__(self, name, operators, coordinator):
        self.name = name
        self.operators = operators
        self.coordinator = coordinator
