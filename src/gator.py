


import numpy as np
import logging
import json
import pandas as pd
from pandas.core.groupby import DataFrameGroupBy # For type hints
from pathlib import Path
import math

from kGraph import *


class Gator(object):

    # Class variables for column names
    FACTOR_COL = '_factor_'
    DEST_COL = '_destId_'
    VALUE_FACTOR_COL = '_vf_'
    NEW_VALUE_COL = '_value_'
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
        if method == AggMethod.MEAN:
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
        resDf = resDf.rename(columns={self.VALUE_FACTOR_COL: dataCol})
        
        # Return it as a dataframe
        return resDf


    def DeAggregate(self, df: pd.DataFrame, idCol: str,
                    dataCol: str, method: DeAggMethod) -> pd.DataFrame:
        
        raise NotImplementedError
        
        # Input validation
        if not type(method) == DeAggMethod:
            msg = f"Incorrect method type of {type(method)} for Gator.DeAggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Grab the data
        data = df[dataCol]



        # Store the resulting rows as dicts
        allRows = []

    
        # Depending on the method, do the deaggregation
        if method == DeAggMethod.COPY:
            # Simply copy the value to all sub-entities
            # Good for stats like averages

            for dn in factors:




                # Form the new row
                newRow = {'result': 1}

            

            pass
        elif method == DeAggMethod.DISTRIBUTE:
            # Distribute the total to all sub-entities by factor
            # Good for numerical stats, e.g. population

            pass


    def Equalize(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
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
        sourceNodes, destNodes = self.MakeNodes(sourceDf[sourceIdCol], destDf[destIdCol], GEID.AIANNHA, GEID.BLOCK)

        # 2.) For each source node, find all matching destNodes
        allMatches = {}
        for sn in sourceNodes:

            # Check if the node exists
            if not self.kGraph.NodeExists(sn):
                msg = f"Node {sn} does not exist in the graph."

                # Throw an error if specified
                if not ignoreMissing:
                    self.logger.error(msg)
                    raise RuntimeError(msg)
                
                # Otherwise just log the miss
                else:
                    self.logger.warning(msg)

                    
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
                if not sn in allFactors:
                    allFactors[sn] = {}
                allFactors[sn][dn] = factor



        # Set the index so we can iterrate over it
        sourceDf = sourceDf.set_index(sourceIdCol)

        # Flatten the dataframe for easy groupby operations
        expandedDf = self.FlattenDataframe(sourceDf, allFactors, sourceIdCol, sourceDataCol)

        # Calculate the value*factor as a new column for easy agg/deagg
        expandedDf[self.VALUE_FACTOR_COL] = expandedDf[sourceIdCol] * expandedDf[self.FACTOR_COL]

        # If ignoreIncomplete is false, check that each destination is 100% covered
        # We are assuming the sources are mutually exclusive (since they are the same type)
        if not ignoreIncomplete:

            # Group by destination node
            groupedDf = expandedDf.groupby(self.DEST_COL)

            # Sum the factors
            factorSums = groupedDf[self.FACTOR_COL].sum()

            # Check that they are all close to 1
            factorSums['_valid_sum_'] = math.isclose(factorSums[self.FACTOR_COL], 1.0, abs_tol=0.1)

            if not factorSums['_valid_sum_'].all():
                msg = f"Total weight is invalid.\nFactors: {factorSums}\n"
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



        # 6.) Clean up before returning
        if not self.DEBUG:
            # Reset the index column
            sourceDf = sourceDf.reset_index()

        return resDf
        

    def MakeNodes(self, ids1: pd.Series, ids2: pd.Series,
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







    
