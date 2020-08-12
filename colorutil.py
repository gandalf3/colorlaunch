import Vector

class Color(Vector.Vector):
    def __init__(self, *args):
        if len(args) == 0:
            color = (0, 0, 0)
        elif len(args) == 3:
            color = args
        else:
            raise ValueError("Color needs at least three values")

        self.values = color

    def as_8bit(self):
        return self.new(*map(int, (self * 255)))

    @classmethod
    def from_8bit(cls, *args):
        self = cls()

        if len(args) != 3:
            raise ValueError("Color needs at least three values")

        super().__init__(self, *map(lambda x : int(x)/255, args[0:3]))
        return self


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



