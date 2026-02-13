



import numpy as np
from pprint import pprint
import pandas as pd
import xxhash
import math
import geopandas as gpd
from shapely import centroid, distance
from shapely.geometry import Polygon, Point, shape, mapping, LineString, MultiPoint
from scipy.optimize import curve_fit

from matplotlib import pyplot as plt
from typing import Callable

from src.entities import *





class Node(object):

    def __init__(self, id):

        self.id = id
        self.values = {}

    def __hash__(self) -> int:
        return hash(self.id)
    
    def __eq__(self, value: object) -> bool:
        return self.id == value.id

    def AddValue(self, k, v):
        self.values[k] = v
    
    def UpdateValue(self, k, v):
        self.values[k] = v

class Graph(object):

    def __init__(self):
        
        self.indexMap = {}
    
    def AddNode(self, n):
        self.indexMap[n] = len(self.indexMap)

    def UpdateNode(self, n, nk, v):
        
        for k in self.indexMap:
            if k == n:
                k.values[nk] = v


testNode = Node('n1')
testNode.AddValue('a', 1)

testNodeCopy = Node('n1')

print(testNode.values)

g = Graph()
g.AddNode(testNode)

for k in g.indexMap:
    if k == testNode:
        print(k.values)

g.UpdateNode(testNodeCopy, 'a', 5)

for k in g.indexMap:
    if k == testNode:
        print(k.values)




quit()


l = (1,2,3)
l1 = (4,5)

print(4 in l1[2:])

quit()



s0 = '011123US12345'
s1 = '9182391629683US01'

i0 = s1.index('US')
print(s1[i0+2:])


quit()



a = 'c'

match a:
    case 'a':
        print('It is a!')
    case 'b' | 'c':
        print('It is b or c!')


quit()

l = [1,2,3,4,5,6]

r = {f'e{k}' if k % 2 == 0 else f'o{k}': k for k in l}

print(r)

print(l[-2:])

quit()





col = 'FM'
v = (ord(col[0]) - 64)*26 + ord(col[1]) - 64
print(v)


quit()

a = np.zeros((10,1))

print(a[:len(a)-1, 0])


quit()

td = {'a': [1,2,3], 'b': [4,5,6]}
tdf = pd.DataFrame(td)

print(tdf)

tdf['c'] = 1

print(tdf)







quit()


p = Polygon(((0,0), (0,1), (2,1), (2,0)))
mp = MultiPoint(((1,1),(-1,1),(1.5,.5)))

mpi = mp.intersection(p)
for point in mpi.geoms:
    print(point)


quit()


p0 = Point((0,0))
p1 = Point((1,2))
print(p0.x + p1.x)

print(p0 == p0)


quit()

l = [i for i in range(20)]
lf = [math.floor(i / 7.)*7. for i in l]

print(lf)



quit()



testd = {
    'id': ['a','b','c','d'],
    'value': [1,3,4,5],
    'centroid': [
            Point((0,0)),
            Point((0,3)),
            Point((4,0)),
            Point((4,3))
        ]}
testDf = pd.DataFrame(testd)

def ManualKriging(samplesDf: pd.DataFrame, idCol: str,
                  dataCol: str, geoColumn: str,
                  poi: Point,
                  model: Callable = VariogramModel.EXPONENTIAL,
                  binPercentage: float = .01):
    

    # Use the samples to perform kriging to estimate the value at the poi

    # Column names
    CENTROID_COL = "centroid__"
    DIST_COL = "dist__"
    COV_COL = "covariance__"


    # 1.) Estimate semivariogram

    # First, extract centroids for all samples
    CENTROID_COL = "centroid"
    samplesDf[CENTROID_COL] = samplesDf[geoColumn].apply(centroid)

    # Iterate over all pairs of sample points to calculate distances
    newRows = []
    maxDist = -1
    for i, curSample in samplesDf.iterrows():
        for j, compSample in samplesDf.iterrows():

            # Add the ids
            newRow = {'id1': curSample[idCol],
                      'id2': compSample[idCol]}

            # Distance for same point is zero
            dist = -1
            if i == j:
                dist = 0
            else:
                dist = distance(curSample[CENTROID_COL], compSample[CENTROID_COL])
            
            # Reset max dist if needed
            if dist > maxDist:
                maxDist = dist
            
            # Add the distance to the new row
            newRow[DIST_COL] = dist

            # Calculate the covariance
            newRow[COV_COL] = (compSample[dataCol] - curSample[dataCol])**2

            # Add the new row to the list of all new rows
            newRows.append(newRow)

    # Now, bin the distances
    print(newRows)
    binSize = math.ceil(binPercentage * maxDist)
    for row in newRows:
        flooredDist = math.floor(row[DIST_COL] / binSize)
        row[DIST_COL] = flooredDist
    
    # Make it a df for maniuplation
    pairsDf = pd.DataFrame(data=newRows)

    print(pairsDf)

    # We can group by distance to get an average for each bin
    binAvgsDf = pairsDf[[DIST_COL, COV_COL]].groupby(DIST_COL).mean()

    print(binAvgsDf)

    # Use the data to fit a curve
    params, cov = curve_fit(model, binAvgsDf.index, binAvgsDf[COV_COL])
    params = list(params)

    x = [i for i in range(7)]
    y = [model(i, *params) for i in x ]
    


    # 2.) Use the SEMI-variogram to calculate matrix C and D
    numRows = samplesDf.shape[0]
    C = np.ones(shape=(numRows+1, numRows+1))
    D = np.ones(shape=(numRows+1, 1))

    for i in range(numRows):
        for j in range(numRows):
            cov = .5*model(pairsDf.iloc[i*numRows][DIST_COL], *params)
            C[i,j] = cov
            C[j,i] = cov
    
    # Make the last entry 0 for the lagrange multiplier
    C[-1, -1] = 0

    # Iterate through each sample again for matrix D
    for i, row in samplesDf.iterrows():

        # Calc the distance from this point to the poi
        poiDist = distance(poi, row[CENTROID_COL])

        # Estimate covariance
        D[i, 0] = .5*model(poiDist, *params)

    # 3.) Use linear algebra to calculate weights
    print(C)
    print(D)

    W = np.linalg.inv(C) @ D

    # 4.) Sanity check that the weights sum to 1
    assert math.isclose(np.sum(W[:numRows,0]), 1)

    # 5.) Use the weights to estimate the value at the poi
    val = np.dot(samplesDf[dataCol].to_numpy(), W[:numRows,0])
    return val


    plt.scatter(binAvgsDf.index, binAvgsDf[COV_COL])
    plt.plot(x, y)


    plt.show()

    



v = ManualKriging(testDf, 'id', 'value', 'centroid', poi=Point((4,3)))
#v = ManualKriging(testDf, 'id', 'value', 'centroid', poi=centroid(Polygon(testd['centroid'])))
print(v)


quit()




















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