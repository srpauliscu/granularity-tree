



import numpy as np

class Test(object):
    pass

a = np.random.rand(4,4)

print(a)

print(a[1,3])

a[1,3] = Test()

print(a)