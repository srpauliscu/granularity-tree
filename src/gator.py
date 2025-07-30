


import numpy as np
import logging
import json
import pandas as pd
from pandas.core.groupby import DataFrameGroupBy # For type hints
from pathlib import Path
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
    

class Gator(object):

    # Class variables for column names
    FACTOR_COL = '_factor_'
    DEST_COL = '_destId_'
    VALUE_FACTOR_COL = '_vf_'
    NEW_VALUE_COL = '_value_'
    ERROR_COL = '_error_'

    # Flag for doing additional cleanup
    DEBUG = True


    def __init__(self, _kGraph: GranularityGraph, logFile: Path):

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
                newDicts.append(
                    {
                        idCol: ind,
                        dataCol: row[dataCol],
                        self.DEST_COL: did,
                        self.FACTOR_COL: factors[did],
                        self.VALUE_FACTOR_COL: row[dataCol] * factors[did]
                    }
                )
        
        # Make it a dataframe
        expandedDf = pd.DataFrame(newDicts)

        return expandedDf



    def Aggregate(self, df: pd.DataFrame, idCol: str, 
                  dataCol: str, method: AggMethod)-> pd.DataFrame:
        
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
            groupedDf = df.groupby(self.DEST_COL)
            resDf = groupedDf[[self.FACTOR_COL]].sum()

        elif method == AggMethod.MEAN:
            # Weighted mean of the source data, via the factor
            groupedDf = df.groupby(self.DEST_COL).sum()
            groupedDf[self.VALUE_FACTOR_COL] = \
                pd.DataFrame(groupedDf[self.VALUE_FACTOR_COL] / groupedDf[self.FACTOR_COL])
            
            # We only want the index and the result column
            resDf = groupedDf[[self.VALUE_FACTOR_COL]]
            

        elif method == AggMethod.MEDIAN:
            # Median of the source data, weighted by factor
            raise NotImplementedError
        
        elif method == AggMethod.SUM:
            '''
            Group by destination and add.

            Make sure to use the value*factor so that each source
            contributes only its share to each destination.
            '''

            groupedDf = df.groupby(self.DEST_COL)
            resDf = groupedDf[[self.VALUE_FACTOR_COL]].sum()

        # Check that something was actually added
        if resDf is None or resDf.shape[0] == 0:
            msg = f"resDf is empty in Gator.Aggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Rename the column to match the original
        if method == AggMethod.COUNT:
            # Need to keep the dataCol name for error calc
            resDf = resDf.rename(columns={self.FACTOR_COL: dataCol})
        else:
            resDf = resDf.rename(columns={self.VALUE_FACTOR_COL: dataCol})

        
        # Return it as a dataframe
        return resDf


    def DeAggregate(self, df: pd.DataFrame, idCol: str,
                    dataCol: str, method: DeAggMethod) -> pd.DataFrame:
        

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
            resDf = df[[self.DEST_COL, dataCol]].set_index(self.DEST_COL)


        elif method == DeAggMethod.DISTRIBUTE:
            # Distribute the total to all sub-entities by factor
            # Good for quantities, e.g. population

            # This was essentially already calculated, in the value*factor column
            resDf = df[[self.VALUE_FACTOR_COL]]


        # Check that something was actually added
        if resDf is None or resDf.shape[0] == 0:
            msg = f"resDf is empty in Gator.DeAggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Rename the column to match the original
        resDf = resDf.rename(columns={self.VALUE_FACTOR_COL: dataCol})

        # Return it
        return resDf


    def Equalize(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
                sourceType: GEID | TID, destType: GEID | TID,
                sourceIdCol: str, destIdCol: str,
                sourceDataCol: str,
                method: AggMethod | DeAggMethod,
                edgeType: EdgeType, ignoreMissing: bool = False,
                ignoreIncomplete: bool = False) -> pd.DataFrame:

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
            msg = f"Equalize method was invalid type {type(method)}."
            self.logger.error(msg)
            raise TypeError(msg)


        # 1.) Make the nodes
        sourceNodes, destNodes = self.MakeNodeObjects(sourceDf[sourceIdCol],
                                                      destDf[destIdCol],
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
                
                # Otherwise just log the miss and skip it
                else:
                    self.logger.warning(msg)
                    continue
            
            # Get the real node from the graph
            newSn = self.kGraph.GetNode(sn.id, sourceType)
            newSourceNodes.append(newSn)
        
        for dn in destNodes:
            if not self.kGraph.NodeExists(dn):
                msg = f"Source node {dn.id} does not exist in the graph."

                # Throw an error if specified
                if not ignoreMissing:
                    self.logger.error(msg)
                    raise RuntimeError(msg)
                
                # Otherwise just log the miss and skip it
                else:
                    self.logger.warning(msg)
                    continue
            
            # Get the real node from the graph
            newDn = self.kGraph.GetNode(dn.id, destType)
            newDestNodes.append(newDn)

        # Override the old lists
        sourceNodes = newSourceNodes
        destNodes = newDestNodes


        # 2.) For each source node, find all matching destNodes
        allMatches = {}
        for sn in sourceNodes:

            # Get the matching dest nodes
            matches = self.kGraph.GetMatches(sn, destNodes, edgeType)
            allMatches[sn] = matches

        # allMatches: {sourceNode: {destNode1: weight1, destNode2: weight2, ...}, ...}

        # 4.) Calculate mult factors
        allFactors = {}
        for sn in allMatches:
            for dn in allMatches[sn]:
                
                # Grab the weight
                weight = allMatches[sn][dn]

                # Divide the weight by the value (e.g. area) of the source
                factor = weight / sn.values[edgeType]

                # Sanity check
                if factor > 1:
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

        # Flatten the dataframe for easy groupby operations
        expandedDf = self.FlattenDataframe(sourceDf, allFactors, sourceIdCol, sourceDataCol)

        # Calculate the value*factor as a new column for easy agg/deagg
        expandedDf[self.VALUE_FACTOR_COL] = expandedDf[sourceDataCol] * expandedDf[self.FACTOR_COL]

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
        

        # 5.) Do the calculation
        # We have everything we need: the destNodes, what nodes belong to each destNode, and
        # the factor to multiply the numerical data by
        # The actual operation depends on 'method'

        if type(method) == AggMethod:
            resDf = self.Aggregate(expandedDf, destIdCol, sourceDataCol, method)
        elif type(method) == DeAggMethod:
            resDf = self.DeAggregate(expandedDf, destIdCol, sourceDataCol, method)
        else:
            # Catch all
            msg = f"Invalid method of type {type(method)} used."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
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
        

    def MakeNodeObjects(self, ids1: pd.Series, ids2: pd.Series,
                  entityType1: GEID | TID, entityType2: GEID | TID) -> tuple[list[Node], list[Node]]:
        
        """
        Make actual node objects from the given data

        """

        # Go through each id and instantiate the matching dummy node
        # TODO: Should have a way to check the validity of the ids

        nodes1 = []
        for id in ids1:
            nodes1.append(Node(id, None, entityType1))

        nodes2 = []
        for id in ids2:
            nodes2.append(Node(id, None, entityType2))

        return nodes1, nodes2


class TimeGator(object):

    # Class variables for column names
    DEST_COL = "_dest_timestamp_"
    WEIGHT_COL = "_overlap_value_"
    FACTOR_COL = Gator.FACTOR_COL
    VALUE_FACTOR_COL = Gator.VALUE_FACTOR_COL
    NEW_VALUE_COL = Gator.NEW_VALUE_COL

    def __init__(self, logFile: Path):

        # We only need to initialize a logger object
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename=str(logFile), encoding='utf-8', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        self.logger = logger

    def Aggregate(self, df: pd.DataFrame, dataCol: str, method: AggMethod) -> pd.DataFrame:

        # Input validation
        if not type(method) == AggMethod:
            msg = f"Incorrect method type of {type(method)} for TimeGator.Aggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Setup the ouput
        resDf = None

        # Depending on the method, do the aggregation
        if method == AggMethod.COUNT:
            
            # Ignore the data column, simply sum
            # up the factors.  Equivalent to adding a column
            # of 1s for count and multiplying by the factor.

            groupedDf = df.groupby(self.DEST_COL)
            resDf = groupedDf[[self.FACTOR_COL]].sum()

        elif method == AggMethod.MEAN:
            # Weighted mean of the source data, via the factor
            groupedDf = df.groupby(self.DEST_COL).sum()
            groupedDf[self.VALUE_FACTOR_COL] = \
                pd.DataFrame(groupedDf[self.VALUE_FACTOR_COL] / groupedDf[self.FACTOR_COL])

            # We only want the index and the result column
            resDf = groupedDf[[self.VALUE_FACTOR_COL]]

        elif method == AggMethod.MEDIAN:
            # Weighted median of the source data, by factor
            raise NotImplementedError
        
        elif method == AggMethod.SUM:
            # Get the total for each unit
            groupedDf = df.groupby(self.DEST_COL)
            resDf = groupedDf[[self.VALUE_FACTOR_COL]].sum()

        # Check that something was actually added
        if resDf is None or resDf.shape[0] == 0:
            msg = f"resDf is empty in TimeGator.Aggregate"

        return resDf

    def Equalize(self, sourceDf: pd.DataFrame, destType: TID,
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

        newRows = []
        ONE_UNIT = pd.Timedelta(1, unit=destType.value)
        for i, row in sourceDf.iterrows():

            # Get the two endpoints of the interval
            startTs = row[intervalCol].left
            endTs = row[intervalCol].right

            # Calculate the value of the origin "node"
            origSize = (endTs - startTs).total_seconds()

            # Grab the full interval in the right units
            intervalStartTs = startTs.floor(freq=destType.value)
            intervalEndTs = endTs.ceil(freq=destType.value)

            # Generate timestamps for each unit between the two endpoints
            tempNewRows = []
            curTimeCounter = intervalStartTs
            
            while curTimeCounter < intervalEndTs:
                newRow = {}

                # Copy over the data column
                newRow[dataCol] = row[dataCol]

                # Add in the current timestamp
                newRow[self.DEST_COL] = curTimeCounter

                # Calculate the overlap, in seconds
                overlap = None
                if intervalEndTs == (intervalStartTs + ONE_UNIT):
                    # Special case: the interval is entirely within one unit
                    overlap = origSize

                elif curTimeCounter + ONE_UNIT >= intervalEndTs:
                    # We're in the last unit
                    overlap = (ONE_UNIT - (intervalEndTs - endTs)).total_seconds()

                elif curTimeCounter == intervalStartTs:
                    # We're in the first unit
                    overlap = (ONE_UNIT - (startTs - curTimeCounter)).total_seconds()

                else:
                    # Any units inbetween are fully covered
                    overlap = ONE_UNIT.total_seconds()

                # Add the overlap to the row -
                # this is essentially the edge weight
                newRow[self.WEIGHT_COL] = overlap

                # Calculate the factor
                # TODO: Is this correct for both agg/deagg?
                newRow[self.FACTOR_COL] = overlap / origSize

                # Calculate the value-factor
                newRow[self.VALUE_FACTOR_COL] = newRow[self.FACTOR_COL] * row[dataCol]

                # Add the new row to the list
                tempNewRows.append(newRow)

                # Increment the hour
                curTimeCounter += ONE_UNIT

            # Sanity check: the data column sum should match the original
            valueFactors = [r[self.VALUE_FACTOR_COL] for r in tempNewRows]
            assert math.isclose(sum(valueFactors), row[dataCol])

            # Add the new rows to the new dataframe
            newRows.extend(tempNewRows)
                


        '''
        What we have now is each row of the original dataframe
        has been split into multiple rows, one for each unit of time
        it covers, with a timestamp starting at that time being
        the "destination ID".

        We can now groupBy the destination ID and perform the operation.

        '''

        if type(method) == AggMethod:
            resDf = None
        elif type(method) == DeAggMethod:
            resDf = None
        else:
            # Catch all
            msg = f"Invalid method of type {type(method)} used."
            self.logger.error(msg)
            raise RuntimeError(msg)



        # TODO: Agg/deagg goes here

        # Make a dataframe out of the new rows
        retDf = pd.DataFrame(data=newRows)

        return retDf

