



import numpy as np
from pprint import pprint
import pandas as pd

from src.entities import *


rows = [{'id': 'ABC', 'a': 1, 'b': 2}, {'id': 'XYZ', 'a': 3, 'b': 4}, {'id': 'ANY', 'a': 1, 'b': 7}]

df = pd.DataFrame(rows)

df['c'] = [i*5 for i in range(df.shape[0])]

df = df.set_index('id')

g = df.groupby('a')
sums = g.sum()

print(sums)

print(sums['b'] / sums['c'])




quit()


s = 4

a = np.zeros((s,s))

print(a)

a = np.pad(a, (0,s), mode='constant', constant_values=None)

print(a)


quit()


def foo() -> Status:
    return Status.SUCCESS

s = foo()
print(s == Status.SUCCESS)
assert s == Status.SUCCESS

quit()



for i in range(5):
    for j in range(i+1, 5):
        print(i,j)



quit()


testSize = 10
testMat = np.zeros((testSize, testSize))
for i in range(testSize):
    for j in range(testSize):
        if i == j:
            testMat[i, j] = -1
        else:
            testMat[i, j] = (i * j) + min(i, j)
            #testMat[i, j] = (min(i, j) ** max(i, j)) % (max(i, j))

np.set_printoptions(precision=3)
print(testMat)

quit()


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