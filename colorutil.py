import Vector

class Color(Vector.Vector):
    def __init__(self, *args):
        if len(args) < 3:
            raise ValueError("Color needs at least three values")
        color = args[0:3]
        super().__init__(self, color)

    @property
    def r(self):
        return self.values[0]

    @property
    def g(self):
        return self.values[1]

    @property
    def b(self):
        return self.values[2]

    @property
    def w(self):
        return self.values[3]



