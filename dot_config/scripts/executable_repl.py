#!/usr/bin/env -S uv run --python 3.14 --with numpy --with matplotlib python -i

import numpy as np
import matplotlib.pyplot as plt

class TempConverter:
    def __init__(self, func):
        self.func = func
    def __rmul__(self, value):
        return self.func(value)

mile2m             = 1609.34
yard2m             = 0.9144
foot2m             = 0.3048
ft2m               = 0.3048
in2m               = 0.0254
inch2m             = 0.0254
nmi2m              = 1852.0
nauticalmile2m     = 1852.0
fah2c              = TempConverter(lambda f: (f - 32) * 5/9)
c2fah              = TempConverter(lambda c: (c * 9/5) + 32)
lb2kg              = 0.453592
