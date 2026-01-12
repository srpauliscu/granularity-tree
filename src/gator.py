


import numpy as np
import logging
import json
import pandas as pd
from pandas.core.groupby import DataFrameGroupBy # For type hints
from pathlib import Path
from typing import Callable
from pprint import pprint

# For kriging
from shapely import centroid, distance
from shapely.geometry import Point, shape, MultiPoint
from scipy.optimize import curve_fit

import math

from kGraph import *
#from src.kGraph import GEID, TID, AggMethod, DeAggMethod, EdgeType


# Function for pd.apply to calculate error bound
def CalculateError(row: pd.Series, origDataCol: str, newDataCol: str):

    # If the factor is 1, there is no error
    if math.isclose(row[Gator.FACTOR_COL], 1.0, abs_tol=.01):
        return (0,0)
    
    # Calculate min and max estimates
    lower = row[newDataCol] - row[Gator.VALUE_FACTOR_COL]
    upper = lower + row[origDataCol]

    actual = row[newDataCol]
    lowerError = abs((lower - actual) / actual) * 100
    upperError = abs((upper - actual) / actual) * 100

    return (round(lowerError, 2), round(upperError,2))
    
def FormInterval(row: pd.Series, tsCol: str, unit: TID) -> pd.Interval:

    # A function for df.apply() to form an interval
    # for the timestamp of a given row

    ts = row[tsCol]

    # Months and years can't use floor()
    if unit == TID.MONTH:
        startTs = ts.to_period(unit.value).to_timestamp()
        endTs = startTs + pd.tseries.offsets.MonthBegin(1)

    elif unit == TID.YEAR:
        startTs = ts.to_period(unit.value).to_timestamp()
        endTs = startTs + pd.tseries.offsets.YearBegin(1)
    
    else:
        startTs = ts.floor(freq=unit.value)
        endTs = ts.ceil(freq=unit.value)
    
    return pd.Interval(startTs, endTs)

class Kriger(object):

    # Column names for relevant new columns
    NODE_BINNED_DIST_COL = "nodeBinnedDist__"
    NODE_ACT_DIST_COL = "nodeActDist__"
    COV_COL = "covariance__"

    def __init__(self, samples: pd.DataFrame, idCol: str,
                 dataCol: str, centroidCol: str, dist: Callable):



        # Save the info relevant to these samples
        self.samples = samples
        self.idCol = idCol
        self.dataCol = dataCol
        self.centroidCol = centroidCol

        # Function to calculate "distance" between nodes
        # (allows for flexible defintion of distance)
        self.dist = dist

        # The cross join of the samples
        self.samplePairs: pd.DataFrame

        # The data used to fit the semivariogram
        self.sampleCovs: pd.DataFrame

        # Parameters for the function currently fit to the semivariogram
        self.curParams: list
        self.model: Callable

        # Lagrange parameter (used in error calc)
        self.langrange: float

        # Covariance matrix (matrix C)
        self.C: np.ndarray

    def CalcSemivariogram(self) -> None:
        
        # 1.) Do a cross join to get a row for each pair of nodes
        self.samplePairs = pd.merge(self.samples, self.samples, how="cross")

        # 2.) Calculate the distance between each pair of nodes
        # Assume that the distance function floors the result for us
        # when a binSize is provided
        self.samplePairs[self.NODE_BINNED_DIST_COL] = \
            self.samplePairs.apply(lambda x: 
                                   self.dist(x[self.centroidCol+'_x'], 
                                             x[self.centroidCol+'_y'],
                                             binSize=5.), 
                                             axis=1)
        
        # Also calculate the real distance, for constructing matrix C
        self.samplePairs[self.NODE_ACT_DIST_COL] = \
            self.samplePairs.apply(lambda x:
                                   self.dist(x[self.centroidCol+'_x'],
                                             x[self.centroidCol+'_y']),
                                             axis=1)

        # 3.) Calculate the covariance (?) for each pair
        self.samplePairs[self.COV_COL] = \
            self.samplePairs.apply(lambda x: 
                                   (x[self.dataCol+'_y'] - x[self.dataCol + '_x'])**2, 
                                   axis=1)
        
        # 4.) Get average values for each distance bin
        self.sampleCovs = self.samplePairs[
            [self.NODE_BINNED_DIST_COL, self.COV_COL]]\
                .groupby(self.NODE_BINNED_DIST_COL).mean()
        
        # Make sure to use the semivariogram
        self.sampleCovs[self.COV_COL] *= .5

    def FitSemivariogram(self, 
                         model: Callable = VariogramModel.EXPONENTIAL)\
                            -> np.ndarray:
        
        # Make sure the avgs have been calced
        if self.sampleCovs is None:
            raise RuntimeError("You must call CalcSemivariogram before FitSemivariogram.")

        # Use the averaged covariances to fit the given model
        params, cov = curve_fit(model,
                                self.sampleCovs.index,
                                self.sampleCovs[self.COV_COL])
        
        # Save the params and the model
        #print(self.sampleCovs.index)
        self.curParams = list(params)
        self.model = model

        print(self.curParams)

        # Return the covariance from fitting the model
        # in case we want to use it for error calcs
        return cov
    
    def CalcC(self) -> None:

        # Function to calculate matrix C since it doesn't depend
        # on the POI

        # Make sure that the semivariogram has been fit
        if self.model is None:
            raise RuntimeError("Call FitSemivariogram first.")
        
        # Use CW = D to calculate the weights vector W

        # First, form an empty C
        # Add in the extra row/column for the Lagrage restraint
        numRows = self.samples.shape[0]
        self.C = np.ones(shape=(numRows+1, numRows+1))

        # TODO: There might be a more efficient way to do this
        # Populate C using the fit semivariogram
        for i in range(numRows):
            for j in range(numRows):
                cov = self.model(self.samplePairs.iloc[i*numRows+j][self.NODE_ACT_DIST_COL], *self.curParams)

                # Symmetric matrix assumes the value is isotropic
                self.C[i,j] = cov
                self.C[j,i] = cov

        # Make the last entry 0 for the Lagrange
        self.C[-1,-1] = 0
        


    def CalcWeights(self, noi: Node, gridWidth: int = 5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:

        # Make sure that the C matrix has been constructed first
        if self.C is None:
            raise RuntimeError("Call CalcC first.")
        
        # For block kriging, first we discretize the geometry of interest (goi)
        goi = noi.geometry

        # Grab the vertices of the goi
        xmin, ymin, xmax, ymax = goi.bounds

        # Form a grid using the bounds
        x, y = np.meshgrid(
            np.arange(xmin, xmax, (xmax - xmin) / gridWidth),
            np.arange(ymin, ymax, (ymax - ymin) / gridWidth)
        )

        # Use only points inside the polygon
        allPoints = MultiPoint(list(zip(x.flatten(), y.flatten())))
        gridPoints = list(allPoints.intersection(goi).geoms)
        
        # Calculate the D vector
        numRows = self.samples.shape[0]
        D = np.ones(shape=(numRows+1, 1))

        # Iterate through each sample again for matrix D
        curRow = 0
        for row in self.samples.itertuples():

            # Grab the centroid
            curCentroid = row.__getattribute__(self.centroidCol)

            # We need to calculate covariance of current sample
            # to each grid point, then average
            curSum = 0
            for p in gridPoints:
                
                # Calculate distance between current grid point
                # and sample centroid
                curDist = self.dist(p, curCentroid)

                # Use the semi-variogram to estimate covariance
                curSum += self.model(curDist, *self.curParams)

            # Calculate average covariance
            D[curRow, 0] = curSum / len(gridPoints)

            # Increment counter
            curRow += 1
        
        # Use linear algebra to calculate weights
        W = np.linalg.inv(self.C) @ D

        # Sanity check that the weights sum to 1
        assert math.isclose(np.sum(W[:numRows, 0]), 1)

        # Return all matrices for testing purposes
        return W, self.C, D


class Gator(object):


    # Class variables for column names
    FACTOR_COL = 'factor__'
    DEST_COL = 'destId__'
    VALUE_FACTOR_COL = 'vf__'
    NEW_VALUE_COL = 'value__'
    ERROR_COL = 'error__'
    MATCHING_DEST_NODES_COL = 'matchingDestNodes__'

    # Variables for spatio-temporal agg/deagg
    S_FACTOR_COL = 'sFactor__'
    T_FACTOR_COL = 'tFactor__'
    S_VALUE_FACTOR_COL = 'svf__'
    T_VALUE_FACTOR_COL = 'tvf__'
    S_DEST_COL = 'sDestId__'
    T_DEST_COL = 'tDestId__'
    S_NODE_COL = 'sNode__'
    S_CENTROID_COL = 'sCentroid__'

    INTERVAL_COL = 'newInterval__'

    # Flag for doing additional cleanup
    DEBUG = True


    def __init__(self, _kGraph: GranularityGraph | None, logFile: Path):

        self.kGraph = _kGraph

        #: logging.Logger: A logging object
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename=str(logFile), encoding='utf-8', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        self.logger = logger

    def MakeSample(self, sampleSize: int, idCol: str, dataCol: str) \
        -> tuple[pd.DataFrame, pd.DataFrame]:
        
        # Function to make a sample for testing that uses the correct
        # column names

        # Make the 'smaller' dataframe
        rows = {}
        rows[idCol] = [i for i in range(sampleSize)]
        rows[dataCol] = [i*2 for i in range(sampleSize)]
        rows[self.FACTOR_COL] = [{int(i/2): 1} for i in range(sampleSize)]
        rows[self.DEST_COL] = [(int(i / 2.),) for i in range(sampleSize)]
        rows[self.VALUE_FACTOR_COL] = [i*2*1 for i in range(sampleSize)]

        smallDf = pd.DataFrame(rows)
        smallDf = smallDf.set_index(idCol)

        # Make the 'larger' dataframe
        lss = int(sampleSize / 2.)
        rows = {}
        rows[idCol] = [i for i in range(lss)]
        rows[dataCol] = [i*4 + (i*2+1)*2 for i in range(lss)]
        rows[self.FACTOR_COL] = [{i*2: i*4/v, i*2+1: (i*2+1)*2/v} for i,v in enumerate(rows[dataCol])]
        rows[self.DEST_COL] = [(i*2, i*2+1) for i in range(lss)]

        temp = []
        for rowi, dv in enumerate(rows[dataCol]):
            tempd = {}
            for k in rows[self.FACTOR_COL][rowi]:
                tempd[k] = dv*rows[self.FACTOR_COL][rowi][k]
            temp.append(tempd)

        rows[self.VALUE_FACTOR_COL] = temp

        largeDf = pd.DataFrame(rows)
        largeDf = largeDf.set_index(idCol)

        return smallDf, largeDf

    def FlattenDataframe(self, df: pd.DataFrame, allFactors: dict, 
                         idCol: str, dataCol: str) -> pd.DataFrame:

        # Unnest the dest and factor columns

        # Iterrows is slow, but only needs to be done once here
        newDicts = []
        for ind, row in df.iterrows():
            factors = allFactors[ind]
            
            # Add a row for each destination
            for did in factors:
                curDict = {}

                # New/hardcoded values first
                curDict[idCol] = ind
                curDict[self.DEST_COL] = did
                curDict[self.FACTOR_COL] = factors[did]
                curDict[self.VALUE_FACTOR_COL] = row[dataCol] * factors[did]

                # Copy over the rest of the row
                for col, value in row.items():
                    if not col in curDict:
                        curDict[col] = value

                newDicts.append(curDict)
        
        # Make it a dataframe
        expandedDf = pd.DataFrame(newDicts)

        return expandedDf



    def Aggregate(self, df: pd.DataFrame, dataCol: str,
                  method: AggMethod, destIdCol: list | str,
                  fCol: str, vfCol: str)-> pd.DataFrame:
        
        # Input validation
        if not type(method) == AggMethod:
            msg = f"Incorrect method type of {type(method)} for Gator.Aggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Setup the output
        resDf = None
        
        # Depending on the method, do the aggregation
        if method == AggMethod.COUNT:

            # Ignore the data column, simply sum up the factors
            # Equivalent to adding a column of 1s for count and
            # multiplying by the factor
            groupedDf = df.groupby(destIdCol)
            resDf = groupedDf[[fCol]].sum()
            #resDf = groupedDf[[self.FACTOR_COL]].count()

        elif method == AggMethod.MEAN:
            # Weighted mean of the source data, via the factor
            groupedDf = df.groupby(destIdCol).sum()
            groupedDf[vfCol] = \
                pd.DataFrame(groupedDf[vfCol] / groupedDf[fCol])
            
            # We only want the index and the result column
            resDf = groupedDf[[vfCol]]
            

        elif method == AggMethod.MEDIAN:
            # Median of the source data, weighted by factor
            raise NotImplementedError
        
        elif method == AggMethod.SUM:
            '''
            Group by destination and add.

            Make sure to use the value*factor so that each source
            contributes only its share to each destination.
            '''

            groupedDf = df.groupby(destIdCol)
            resDf = groupedDf[[vfCol]].sum()

        # Check that something was actually added
        if resDf is None or resDf.shape[0] == 0:
            msg = f"resDf is empty in Gator.Aggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Rename the column to match the original
        if method == AggMethod.COUNT:
            # Need to keep the dataCol name for error calc
            resDf = resDf.rename(columns={fCol: dataCol})
        else:
            resDf = resDf.rename(columns={vfCol: dataCol})

        
        # Return it as a dataframe
        return resDf


    def DeAggregate(self, df: pd.DataFrame, dataCol: str,
                    method: DeAggMethod, destIdCol: list | str,
                    fCol: str, vfCol: str) -> pd.DataFrame:
        

        # Input validation
        if not type(method) == DeAggMethod:
            msg = f"Incorrect method type of {type(method)} for Gator.DeAggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
    
 
        # Depending on the method, do the deaggregation
        if method == DeAggMethod.COPY:
            # Simply copy the value to all sub-entities
            # Good for aggregate summary stats, e.g. averages

            # We can ignore the factor and vf columns for this
            #print(df)

            # Just take the original data and make the destId the index
            resDf = df[[destIdCol, dataCol]].set_index(destIdCol)


        elif method == DeAggMethod.DISTRIBUTE:
            # Distribute the total to all sub-entities by factor
            # Good for quantities, e.g. population

            # This was essentially already calculated, in the value*factor column
            resDf = df[[vfCol]]


        # Check that something was actually added
        if resDf is None or resDf.shape[0] == 0:
            msg = f"resDf is empty in Gator.DeAggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Rename the column to match the original
        resDf = resDf.rename(columns={vfCol: dataCol})

        # Return it
        return resDf

    def MakeNodeObjects(self, ids1: pd.DataFrame, ids2: pd.DataFrame,
                        id1IdCol: str, id2IdCol: str,
                        id1GeoCol: str | None, id2GeoCol: str | None,
                        entityType1: GEID | TID, entityType2: GEID | TID) -> tuple[list[Node], list[Node]]:
        
        """
        Make actual node objects from the given data

        """

        # Go through each id and instantiate the matching dummy node
        # TODO: Should have a way to check the validity of the ids

        nodes1 = []
        for row in ids1.itertuples():

            # Don't include geometry if not provided
            if id1GeoCol is None:
                nodes1.append(Node(row.__getattribute__(id1IdCol),
                                None, entityType1, None))
            else:

                nodes1.append(Node(row.__getattribute__(id1IdCol),
                                None, entityType1,
                                row.__getattribute__(id1GeoCol)))
        

        nodes2 = []
        for row in ids2.itertuples():

            # Don't include geometry if not provided
            if id2GeoCol is None:
                nodes2.append(Node(row.__getattribute__(id2IdCol),
                                None, entityType2, None))             
            else:
                nodes2.append(Node(row.__getattribute__(id2IdCol),
                                None, entityType2,
                                row.__getattribute__(id2GeoCol)))
            
        return nodes1, nodes2
    

    def SpatialKriging(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
                       sourceType: GEID, destType: GEID,
                       sourceIdCol: str, destIdCol: str,
                       sourceDataCol: str,
                       sourceGeoCol: str, destGeoCol: str,
                       edgeType: EdgeType,
                       distFunction: Callable,
                       model: Callable,
                       ignoreMissing: bool = False,
                       ignoreIncomplete: bool = False) -> pd.DataFrame:
        
        # First, calculate the weights
        samples, matrices = self.CalcKrigingWeights(sourceDf, destDf,
                                                   sourceType, destType,
                                                   sourceIdCol, destIdCol,
                                                   sourceDataCol,
                                                   sourceGeoCol, destGeoCol,
                                                   edgeType,
                                                   distFunction,
                                                   model,
                                                   ignoreMissing,
                                                   ignoreIncomplete)
        
        
        # Kriging will always be a summation of the value factors
        allNewRows = []
        for dn in samples:
            curSamples = samples[dn]

            # Calculate value factors
            curSamples[self.VALUE_FACTOR_COL] = \
                curSamples[sourceDataCol] * curSamples[self.FACTOR_COL]
            
            # Do the summation
            estimatedVal = curSamples[self.VALUE_FACTOR_COL].sum()

            # Add a new row to the ouput
            newRow = {sourceIdCol: dn.id,
                      sourceDataCol +"_est": estimatedVal
                      }
            allNewRows.append(newRow)
            
        return pd.DataFrame(data = allNewRows)
        


    def CalcKrigingWeights(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
                           sourceType: GEID, destType: GEID,
                           sourceIdCol: str, destIdCol: str,
                           sourceDataCol: str,
                           sourceGeoCol: str, destGeoCol: str,
                           edgeType: EdgeType,
                           distFunction: Callable,
                           model: Callable,
                           ignoreMissing: bool = False,
                           ignoreIncomplete: bool = False) \
                            -> tuple[dict[Node, pd.DataFrame], dict[Node, tuple]]:
        
        '''
        Use kriging to calculate the linear weights for each destination
        '''

        # 1.) Make the nodes
        sourceNodes, destNodes = self.MakeNodeObjects(sourceDf, destDf,
                                                      sourceIdCol, destIdCol,
                                                      sourceGeoCol, destGeoCol,
                                                      sourceType, destType)
        
        # Get the populated version of each node from the graph
        newSourceNodes = []
        sourceNodeDict = {}
        newDestNodes = []
        for sn in sourceNodes:
            if not self.kGraph.NodeExists(sn):
                msg = f"Source node {sn.id} does not exist in the graph."

                # Throw an error if specified
                if not ignoreMissing:
                    self.logger.error(msg)
                    raise RuntimeError(msg)
                
                # Otherwise just log the miss and continue
                else:
                    self.logger.warning(msg)
                    continue
            
            # Get the real node from the graph
            newSn = self.kGraph.GetNode(sn.id, sourceType)
            newSourceNodes.append(newSn)

            # Also, populate a dictionary of id: node for later
            sourceNodeDict[sn.id] = newSn

        # Do the same thing but with the destination nodes
        for dn in destNodes:
            if not self.kGraph.NodeExists(dn):
                msg = f"Dest node {dn.id} does not exist in the graph."

                # Throw an error if specified
                if not ignoreMissing:
                    self.logger.error(msg)
                    raise RuntimeError(msg)
                
                # Otherwise just log the miss and continue
                else:
                    self.logger.warning(msg)
                    continue
            
            # Get the real node from the graph
            newDn = self.kGraph.GetNode(dn.id, destType)
            newDestNodes.append(newDn)
        
        # Override the dummy nodes
        sourceNodes = newSourceNodes
        destNodes = newDestNodes

        # 2.) For each dest node, find all matching source nodes
        allMatches = {}

        for dn in destNodes:

            # Get the matching source nodes
            matches = self.kGraph.GetMatches(dn, sourceNodes, edgeType)

            # We can discard the weights since we're calculating new ones
            allMatches[dn] = list(matches.keys())
        
        # allMatches: {destNode: [sourceNode1, sourceNode2, ...], ...}

        #pprint(allMatches)
        #assert False

        # 3.) For each destNode, we need to separate the corresponding
        # samples from the full dataframe
        sepSamples = {}
        for dn in allMatches:
            sourceIds = [sn.id for sn in allMatches[dn]]

            # Make sure to add in a copy to avoid the SettingWithCopyWarning from pandas
            sepSamples[dn] = sourceDf[sourceDf[sourceIdCol].isin(sourceIds)].copy()

            # We also need to add the node objects as a column so we can
            # access their centroids
            sepSamples[dn][self.S_NODE_COL] = \
                sepSamples[dn].apply(lambda x:
                                     sourceNodeDict[x[sourceIdCol]], axis=1)

            # Calculate the "centroids" depending on the type of scaling
            # (e.g. spatial, temporal, spatio-temporal)

            # TODO: for now, assume spatial (one step at a time...)
            sepSamples[dn][self.S_CENTROID_COL] = \
                sepSamples[dn].apply(lambda x:
                                     x[self.S_NODE_COL].centroid, axis=1)


        # separatedSamples: {destNode: pd.DataFrame, ...}


        # 4.) For each set of samples, make a Kriger object to handle
        # the math
        krigers = {dn: Kriger(sepSamples[dn].reset_index(), sourceIdCol,
                          sourceDataCol, self.S_CENTROID_COL, distFunction)
                   for dn in sepSamples}

        # Have each Kriger fit their variogram
        for dn in krigers:
            k = krigers[dn]
            k.CalcSemivariogram()
            k.FitSemivariogram(model)
            k.CalcC()
        
        # 5.) Use each kriger to calculate weights
        weights = {}
        for dn in krigers:
            weights[dn] = krigers[dn].CalcWeights(dn)

        # Now, each entry in weights corresponds to the set of
        # source samples for that destination node

        # weights[dn] = (W, C, D)

        for dn in sepSamples:

            W = weights[dn][0]
            curSamples = sepSamples[dn]

            # Sanity check
            # Account for lagrange
            assert len(W) - 1 == curSamples.shape[0]

            # Now, add the weights into the sample data as a new column,
            # dropping the lagrange
            curSamples[self.FACTOR_COL] = W[:len(W) - 1, 0]

            # Make sure the new dataframe is saved
            sepSamples[dn] = curSamples

        return sepSamples, weights


        

        



    def CalcSpatialFactors(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
                           sourceType: GEID, destType: GEID,
                           sourceIdCol: str, destIdCol: str,
                           sourceDataCol: str,
                           sourceGeoCol: str, destGeoCol: str,
                           edgeType: EdgeType,
                           ignoreMissing: bool = False,
                           ignoreIncomplete: bool = False) -> pd.DataFrame:
        
        '''
        Find matching destination nodes for the given source column.
        Return the same dataframe with a new column of [destination nodes].
        
        '''

        # 1.) Make the nodes
        sourceNodes, destNodes = self.MakeNodeObjects(sourceDf, destDf,
                                                      sourceIdCol, destIdCol,
                                                      sourceGeoCol, destGeoCol,
                                                      sourceType, destType)
        
        # Get the populated version of each node from the graph
        newSourceNodes = []
        newDestNodes = []
        for sn in sourceNodes:
            if not self.kGraph.NodeExists(sn):
                msg = f"Source node {sn.id} does not exist in the graph."

                # Throw an error if specified
                if not ignoreMissing:
                    self.logger.error(msg)
                    raise RuntimeError(msg)
                
                # Otherwise just log the miss and continue
                else:
                    self.logger.warning(msg)
                    continue
            
            # Get the real node from the graph
            newSn = self.kGraph.GetNode(sn.id, sourceType)
            newSourceNodes.append(newSn)

        # Do the same thing but with the destination nodes
        for dn in destNodes:
            if not self.kGraph.NodeExists(dn):
                msg = f"Dest node {dn.id} does not exist in the graph."

                # Throw an error if specified
                if not ignoreMissing:
                    self.logger.error(msg)
                    raise RuntimeError(msg)
                
                # Otherwise just log the miss and continue
                else:
                    self.logger.warning(msg)
                    continue
            
            # Get the real node from the graph
            newDn = self.kGraph.GetNode(dn.id, destType)
            newDestNodes.append(newDn)

        # Override the dummy nodes
        sourceNodes = newSourceNodes
        destNodes = newDestNodes

        # 2.) For each source node, find all matching destNodes
        allMatches = {}

        for sn in sourceNodes:

            # Get the matching dest nodes
            matches = self.kGraph.GetMatches(sn, destNodes, edgeType)
            allMatches[sn] = matches

        # allMatches: {sourceNode: {destNode1: weight1, destNode2: weight2, ...}, ...}

        # 3.) Calculate mult factors
        allFactors = {}
        for sn in allMatches:
            for dn in allMatches[sn]:

                # Grab the weight
                weight = allMatches[sn][dn]

                # Divide the weight by the value (e.g. area) of the source
                factor = weight / sn.values[edgeType]

                # Sanity check
                if factor > 1 and not math.isclose(factor, 1):
                    msg = f"Factor of {factor} for {dn} - {sn} is invalid.\n \
                            destValues = {dn.values}\n \
                            sourceValues = {dn.values}\n \
                            weight = {weight}"
                    self.logger.error(msg)
                    raise RuntimeError(msg)

                # Save it into a new dict
                if not sn.id in allFactors:
                    allFactors[sn.id] = {}
                allFactors[sn.id][dn.id] = factor

        # Sanity check to make sure the ids were indeed unique
        if not len(allMatches) == len(allFactors):
            msg = f"allMatches and allFactors did not match up in length."
            self.logger.error(msg)
            raise RuntimeError(msg)
        for sn in allMatches:
            if not len(allMatches[sn]) == len(allFactors[sn.id]):
                msg = f"allMatches and allFactors did not match up in length for source node {sn.id}."
                self.logger.error(msg)
                raise RuntimeError(msg)
        
        # Set the index so we can iterrate over it
        sourceDf = sourceDf.set_index(sourceIdCol)

        # Flatten the dataframe for easy grouby operations
        expandedDf = self.FlattenDataframe(sourceDf, allFactors, sourceIdCol, sourceDataCol)

        # If ignoreIncomplete is false, check that each destination is 100% covered
        # We are assuming the sources are mutually exclusive (since they are the same type)
        if not ignoreIncomplete:

            # Just need to add the weights up for each edge for each dest Node
            allTots = {}
            for sn in allMatches:
                for dn in allMatches[sn]:

                    # Make a new entry as needed
                    if not dn in allTots:
                        allTots[dn] = 0
                    
                    allTots[dn] += allMatches[sn][dn]

            # Check that they are all close to the value recorded in the graph
            for dn in allTots:
                if not math.isclose(allTots[dn], dn.values[edgeType], rel_tol=0.1):
                    msg = f"Total weight {allTots[dn]} for {dn.id} is invalid.\nFactors: {allTots}\n"
                    #self.logger.error()
                    self.logger.error(msg)
                    raise RuntimeError(msg)

        # Return it
        return expandedDf




    def SpatialEqualize(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
                sourceType: GEID, destType: GEID,
                sourceIdCol: str, destIdCol: str,
                sourceDataCol: str,
                sourceGeoCol: str,
                destGeoCol: str,
                method: AggMethod | DeAggMethod,
                edgeType: EdgeType, ignoreMissing: bool = False,
                ignoreIncomplete: bool = False,
                distFunction: Callable = None,
                model: Callable = None) -> pd.DataFrame:

        """
        Attempt to make the data in sourceDf match the granularity of destDf via 'edgeType'
        and using the given method.  Returns the source Dataframe in the granularity
        of the dest Dataframe.

        Steps:
        1.) Make nodes out of the ids of each dataframe.
        2.) Assign a destination node(s) to each source node
        3.) Group operations by destination node
        4.) Calculate the mult factor based on the edge weight and the node values
        5.) Perform the operations, using the 'method' to inform how to combine/distribute
            the results.
        
        """

        # 0.) Input validation
        if not (type(method) == AggMethod or type(method) == DeAggMethod):
            msg = f"SpatialEqualize method was invalid type {type(method)}."
            self.logger.error(msg)
            raise TypeError(msg)
        
        # We need a graph for spatial scaling
        if self.kGraph is None:
            msg = f"SpatialEqualize requires a kGraph for scaling."
            self.logger.error(msg)
            raise RuntimeError(msg)

        # If kriging, calculate weights using the data
        if method == AggMethod.KRIGING or method == DeAggMethod.KRIGING:

            # Make sure a dist function and model were passed in
            if distFunction is None:
                msg = "A distance function must be passed in when kriging is selected."
                self.logger.error(msg)
                raise RuntimeError(msg)
            
            if model is None:
                msg = "A model must be passed in when kriging is selected."
                self.logger.error(msg)
                raise RuntimeError(msg)

            # Just call the appropriate function
            resDf = self.SpatialKriging(sourceDf, destDf, sourceType, destType,
                                        sourceIdCol, destIdCol, sourceDataCol,
                                        sourceGeoCol, destGeoCol, edgeType,
                                        distFunction, model)
            
            # TODO: For now, just return the results.  We probably
            # want error calculation later though.
            
            # Clean up first
            if not self.DEBUG:
                sourceDf = sourceDf.reset_index()
            
            return resDf
        
        else:
            # Use the graph to calculate the factors and valueFactors
            expandedDf = self.CalcSpatialFactors(sourceDf, destDf, sourceType, destType,
                                                sourceIdCol, destIdCol, sourceDataCol,
                                                sourceGeoCol, destGeoCol,
                                                edgeType, ignoreMissing=ignoreMissing,
                                                ignoreIncomplete=ignoreIncomplete)


        # 5.) Do the calculation
        # We have everything we need: the destNodes, what nodes belong to each destNode, and
        # the factor to multiply the numerical data by
        # The actual operation depends on 'method'

        if type(method) == AggMethod:
            resDf = self.Aggregate(expandedDf, sourceDataCol, method,
                                   self.DEST_COL, self.FACTOR_COL, self.VALUE_FACTOR_COL)
        elif type(method) == DeAggMethod:
            resDf = self.DeAggregate(expandedDf, sourceDataCol, method,
                                     self.DEST_COL, self.FACTOR_COL, self.VALUE_FACTOR_COL)
        else:
            # Catch all
            msg = f"Invalid method of type {type(method)} used."
            self.logger.error(msg)
            raise TypeError(msg)
        
        # 6.) Error calculation

        # Do a one-sided join to inform each source-dest node pair of the result
        #print(expandedDf)
        #print(resDf)

        rsuffix = '_r'
        lsuffix = '_l'
        joinedDf = expandedDf.join(resDf, on=self.DEST_COL, how='left', rsuffix='_r', lsuffix='_l')

        # Rename the columns for clarity
        origDataCol = f'source_{sourceDataCol}'
        newDataCol = f'dest_{sourceDataCol}'
        joinedDf = joinedDf.rename(columns={sourceDataCol + lsuffix: origDataCol,
                                            sourceDataCol + rsuffix: newDataCol})

        ''' Error calculation
        For sources with a factor of 1, there can be no error
        since it is not split with another destination.

        For sources with a factor < 1, the possibilities range from complete to no overlap,
        which gives a range of new totals.

        To properly calculate error, calculate what the new total would be with
        a factor of 1 and a factor of 0 to get the error bound for each s-d pair.

        Then, do the same for all sources of a given destination at the same time.
        This gives an overall error bound.

        
        '''

        # Use apply for the special case of factor == 1
        joinedDf[self.ERROR_COL] = joinedDf.apply(CalculateError, axis=1,
                                                  args=[origDataCol, newDataCol])

        #assert False
        



        # 6.) Clean up before returning
        if not self.DEBUG:
            # Reset the index column
            sourceDf = sourceDf.reset_index()

        return resDf
    
    def TemporalEqualize(self, sourceDf: pd.DataFrame, destType: TID,
                         intervalCol: str, dataCol: str,
                         method: AggMethod | DeAggMethod) -> pd.DataFrame:
        
        """
        Steps:
        1.) For each interval, get bounding timestamps of the given destType
        2.) For each unit in that period, calculate the overlap with the entire period
            Ex: 11:45 - 14:20: hours 11, 12, 13, 14 with weights
            (in minutes) 15, 60, 60, 20.
        3.) Calculate the factor for multiplying with the dataCol
        4.) Multiply the dataCol by the factor for each unit
        5.) Group by destType and agg/deagg

        Same method as the tree structure, but the graph is calculated dynamically    
        """

        # Note that we don't need a stored kGraph for this,
        # as the "graph" is generated dyanmically

        newRows = []

        argDict = {TID_TO_STRING[destType]: 1}
        ONE_UNIT = pd.DateOffset(**argDict)

        for row in sourceDf.itertuples():

            # Get the two endpoints of the interval
            startTs = row.__getattribute__(intervalCol).left
            endTs = row.__getattribute__(intervalCol).right

            # Get the data once for efficiency
            actualData = row.__getattribute__(dataCol)

            # Calculate the value of the origin "node"
            origSize = (endTs - startTs).total_seconds()

            # Grab the full interval in the right units
            # Months and years can't use floor()
            if destType == TID.MONTH:
                intervalStartTs = startTs.to_period(destType.value).to_timestamp()
                intervalEndTs = endTs.to_period(destType.value).to_timestamp() + pd.tseries.offsets.MonthBegin(1)#endTs.month)

            elif destType == TID.YEAR:
                intervalStartTs = startTs.to_period(destType.value).to_timestamp()
                intervalEndTs = endTs.to_period(destType.value).to_timestamp() + pd.tseries.offsets.YearBegin(1)#endTs.year)

            else:
                intervalStartTs = startTs.floor(freq=destType.value)
                intervalEndTs = endTs.ceil(freq=destType.value)

            # Generate timestamps for each unit between the two endpoints
            tempNewRows = []
            curTimeCounter = intervalStartTs

            #print(f'\n{row[intervalCol]}')
            
            while curTimeCounter < intervalEndTs:
                #print(curTimeCounter)
                newRow = {}

                # Copy over the data column
                newRow[dataCol] = actualData

                # Add in the current timestamp
                newRow[self.DEST_COL] = curTimeCounter

                # Calculate the overlap, in seconds
                overlap = None
                if intervalEndTs == (intervalStartTs + ONE_UNIT):
                    # Special case: the interval is entirely within one unit
                    overlap = origSize


                elif curTimeCounter + ONE_UNIT >= intervalEndTs:
                    # We're in the last unit

                    if intervalEndTs == endTs:
                        # Special case: endTs is exactly on an interval
                        overlap = min(origSize, ((intervalStartTs + ONE_UNIT) - intervalStartTs).total_seconds())
                    else:
                        overlap = min(origSize, (endTs - endTs.to_period(destType.value).to_timestamp()).total_seconds())

                elif curTimeCounter == intervalStartTs:
                    # We're in the first unit
                    overlap = ((intervalStartTs + ONE_UNIT) - startTs).total_seconds()
                else:
                    # Any units inbetween are fully covered
                    overlap = ((curTimeCounter + ONE_UNIT) - curTimeCounter).total_seconds()

                # Sanity check: the overlap should never be bigger than
                #print(f"Second overlap: {overlap}")
                assert overlap <= origSize

                # Calculate the factor
                # TODO: Is this correct for both agg/deagg?
                if origSize == 0:
                    # Avoid divide by zero error
                    newRow[self.FACTOR_COL] = 1
                else:
                    newRow[self.FACTOR_COL] = overlap / origSize

                # Calculate the value-factor
                newRow[self.VALUE_FACTOR_COL] = newRow[self.FACTOR_COL] * actualData

                # Add the new row to the list
                tempNewRows.append(newRow)

                # Increment the time
                curTimeCounter += ONE_UNIT

            # Sanity check: the data column sum should match the original
            valueFactors = [r[self.VALUE_FACTOR_COL] for r in tempNewRows]
            #print(sum(valueFactors))
            #print(row[dataCol])
            
            if not math.isclose(sum(valueFactors), actualData):
                raise RuntimeError
            assert math.isclose(sum(valueFactors), actualData)

            # Cutoff the last entry if the overlap is 0
            # This is just an inclusive/exclusive interval problem
            if math.isclose(tempNewRows[-1][self.FACTOR_COL], 0):
                tempNewRows = tempNewRows[:-1]

            # Add the new rows to the new dataframe
            newRows.extend(tempNewRows)
                


        '''
        What we have now is each row of the original dataframe
        has been split into multiple rows, one for each unit of time
        it covers, with a timestamp starting at that time being
        the "destination ID".

        We can now groupBy the destination ID and perform the operation.

        '''
        expandedDf = pd.DataFrame(data=newRows)

        if type(method) == AggMethod:
            resDf = self.Aggregate(expandedDf, dataCol, method,
                                   self.DEST_COL, self.FACTOR_COL, self.VALUE_FACTOR_COL)
        elif type(method) == DeAggMethod:
            resDf = self.DeAggregate(expandedDf, dataCol, method,
                                     self.DEST_COL, self.FACTOR_COL, self.VALUE_FACTOR_COL)
        else:
            # Catch all
            msg = f"Invalid method of type {type(method)} used."
            self.logger.error(msg)
            raise RuntimeError(msg)

        return resDf
    

    def SpatioTemporalEqualize(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame, destTType: TID,
                               sourceSType: GEID, destSType: GEID, sourceSIdCol: str,
                               destSIdCol: str, sourceTIdCol: str, destTIdCol: str,
                               sourceDataCol: str, sourceGeoCol: str, destGeoCol: str,
                               sMethod: AggMethod | DeAggMethod, tMethod: AggMethod | DeAggMethod,
                               edgeType: EdgeType, ignoreMissing: bool = False,
                               ignoreIncomplete: bool = False) -> pd.DataFrame:
        

        '''
        Do a combination spatio-temporal scaling, grouping by spatial last

        1.) Group into spatial destination type and get an interval for
            the time periods it covers.
            TODO: What do we do with the data?  Do we start aggregating?
        2.) 
        
        '''

        # 0.) Input validation
        if not (type(sMethod) == AggMethod or type(sMethod) == DeAggMethod):
            msg = f"SpatioTemporalEqualize spatial method was invalid type {type(sMethod)}."
            self.logger.error(msg)
            raise TypeError(msg)
        
        if not (type(tMethod) == AggMethod or type(sMethod) == DeAggMethod):
            msg = f"SpatioTemporalEqualize temporal method was invalid type {type(sMethod)}."
            self.logger.error(msg)
            raise TypeError(msg)
        
        # We need a graph for spatial scaling
        if self.kGraph is None:
            msg = f"SpatioTemporalEqualize requires a kGraph for scaling."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Use the graph to calculate the spatial factors and value factors
        expandedDf = self.CalcSpatialFactors(sourceDf, destDf, sourceSType, destSType,
                                             sourceSIdCol, destSIdCol, sourceDataCol,
                                             sourceGeoCol, destGeoCol,
                                             edgeType, ignoreMissing, ignoreIncomplete)
        
        # Rename to avoid clashes later
        expandedDf = expandedDf.rename(columns={self.FACTOR_COL: self.S_FACTOR_COL,
                                                self.VALUE_FACTOR_COL: self.S_VALUE_FACTOR_COL,
                                                self.DEST_COL: self.S_DEST_COL})
        
        # Print options for debugging
        pd.set_option('display.max_columns', 500)
        pd.set_option('display.width', 1000)
        
        # If we have time-series data, we need to make intervals
        if not isinstance(expandedDf[sourceTIdCol].dtype, pd.IntervalDtype):

            # Our "intervals" will just be one unit, starting at the floor
            # of the timestamp and ending at the ceil

            # We can just overwrite the previous time column
            # since it will go away with aggregation anyway
            expandedDf[sourceTIdCol] = expandedDf.apply(FormInterval,
                                                        args=[sourceTIdCol, destTType],
                                                        axis=1)
            

        # We can include the factor to copy it over, as the factor will always be
        # the same for each s-d pair, so it won't affect the output
        sdGroups = expandedDf.groupby([sourceSIdCol, self.S_DEST_COL, self.S_FACTOR_COL])
        allRows = []
        for group in sdGroups:
            curDf = group[1]

            curResDf = self.TemporalEqualize(curDf, destTType,
                                             sourceTIdCol, self.S_VALUE_FACTOR_COL,
                                             tMethod)
            
            # Copy in the source-dest pair
            curResDf[sourceSIdCol] = group[0][0]
            curResDf[self.S_DEST_COL] = group[0][1]
            curResDf[self.S_FACTOR_COL] = group[0][2]


            # Save the current results
            allRows.append(curResDf)

        
        # Concat them into one dataframe
        concatDf = pd.concat(allRows)


        # Do the spatial scaling now
        if type(sMethod) == AggMethod:
            resDf = self.Aggregate(concatDf, self.VALUE_FACTOR_COL, sMethod,
                                   [concatDf.index, self.S_DEST_COL], self.S_FACTOR_COL, self.S_VALUE_FACTOR_COL)
        elif type(sMethod) == DeAggMethod:
            resDf = self.DeAggregate(concatDf, self.VALUE_FACTOR_COL, sMethod,
                                     [concatDf.index, self.S_DEST_COL], self.S_FACTOR_COL, self.S_VALUE_FACTOR_COL)
        else:
            # Catch all
            msg = f"Invalid spatial method of type {type(sMethod)} used."
            self.logger.error(msg)
            raise TypeError(msg)
        
        # Rename it to match the original columns
        resDf.index = resDf.index.set_names({
            self.S_DEST_COL: sourceSIdCol,
            self.DEST_COL: sourceTIdCol
        })
        
        resDf = resDf.rename(columns={self.VALUE_FACTOR_COL: sourceDataCol})

        return resDf

        




