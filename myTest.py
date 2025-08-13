



import numpy as np
from pprint import pprint
import pandas as pd

from src.entities import *



ts1 = pd.Timestamp(year=2020, month=6, day=1, hour=0, minute=0, second=0)
ts2 = pd.Timestamp(year=2020, month=7, day=1, hour=0, minute=0, second=0)

print((ts2 - ts1).total_seconds())


quit()

df = pd.DataFrame([[0, 2, 3], [-1, -1, -1], [0, 4, 1], [10, 20, 30]],
                  index=[4, 4, 5, 6], columns=['A', 'B', 'C'])

for ind, row in df.loc[4].iterrows():
    print(row['A'])


quit()

def foo(a1=1, a2=2, a3=3):


    print(a1, a2, a3)


d = {1: 'a1',
     2: 'a2',
     3: 'a3'
}

d2 = {'a1': 102}

foo(**d2)



quit()




def TestApp(row, t: int):
    t += row['a']

rows = [{'id': 'ABC', 'a': 1, 'b': 2}, {'id': 'XYZ', 'a': 3, 'b': 4}, {'id': 'ANY', 'a': 1, 'b': 7}]

df = pd.DataFrame(rows)
t = 0
df.apply(TestApp, axis=1, args=[t])
print(t)






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