



import numpy as np
from pprint import pprint
import pandas as pd
import xxhash
import geopandas as gpd
from shapely.geometry import Polygon, shape, mapping

from src.entities import *





testd = {'value': [1,2,3],
 'geometry': [
     Polygon(((0,0),(0,1),(1,1),(1,0))),
     Polygon(((0,0),(0,2),(2,2),(2,0))),
     Polygon(((0,0),(0,2),(2,2),(2,0)))
 ]}

testGpd = gpd.GeoDataFrame(testd)

testGpd['mappedGeo'] = testGpd['geometry'].apply(mapping)

print(testGpd)

testGpd.to_csv("./testGeo.csv", index=False)

testGpd2 = gpd.read_file("./testGeo.csv")




testGpd2['mappedGeo'] = testGpd2['mappedGeo'].apply(lambda x: shape(eval(x)))

print(type(testGpd2['mappedGeo'].iloc[0]))



quit()


colName = 'aaacol1_'
def IterTest():

    col1 = [i for i in range(5)]
    testDf = pd.DataFrame({colName: col1})

    #for i, row in testDf.iterrows():
    #    res = row['col1'] + 1

    for row in testDf.itertuples():
        res = row.__getattribute__(colName) + 1
        print(res)

IterTest()

def HashTest():

    hasher = xxhash.xxh64()
    d = {}
    for i in range(4*(10**7)):
        res = f"{i}"#.__hash__()
        #res = hash(f"{i}")
        d[res] = i
        a = d[res]


def AssignmentTest():

    size = 4*(10**4)
    ar = np.ones((size, size))


    testList = [ar, ar, ar]

    for i in range(size - 1):


        #adjMat = testList[0]
        #res1 = adjMat[i, i+1] == adjMat[i+1, i]
        #res2 = not adjMat[i, i+1] == 0

        res1 = testList[0][i, i+1] == testList[0][i+1, i]
        res2 = not testList[0][i,i+1] == 0

#testDf = pd.DataFrame()
#HashTest()
#AssignmentTest()












quit()

df1 = pd.DataFrame([[0, 2, 3], [-1, -1, -1], [0, 4, 1], [10, 20, 30]],
                  index=[1,2,3,4], columns=['A', 'B', 'C'])

df2 = pd.DataFrame([[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11], [12]],
                   index = [1,1,1,2,2,2,3,3,3,4,4,4], columns=['D'])

mergedDf = pd.merge(df1, df2, left_index=True, right_index=True)

print (df1)
print(df2)

print(mergedDf)


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