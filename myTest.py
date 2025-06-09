



import numpy as np

from src.entities import *

e = EdgeType.AREA
e2 = EdgeType('Area')
print()
print(e2)

quit()

s = 4

a = np.zeros((s,s))


quit()

a = np.pad(a, (0,s), mode='constant', constant_values=None)


print(a)


quit()


class Test(object):
    pass

a = np.random.rand(4,4)

print(a)

print(a[1,3])

a[1,3] = Test()

print(a)