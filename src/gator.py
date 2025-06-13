


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
    NEW_VALUE_COL = '_value_'
    DEBUG = True


    def __init__(self, _kGraph: GranularityGraph, logFile: Path):

        self.kGraph = _kGraph

        #: logging.Logger: A logging object
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename=str(logFile), encoding='utf-8', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        self.logger = logger

    def Aggregate(self, df: pd.DataFrame, idCol: str, dataCol: str, method: AggMethod,
                  factors: dict[Node, dict[Node, float]]) -> pd.DataFrame:
        
        # Input validation
        if not type(method) == AggMethod:
            msg = f"Incorrect method type of {type(method)} for Gator.Aggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Depending on the method, do the aggregation
        retDf = None
        if method == AggMethod.MEAN:
            # Mean of the source data, weighted by factor
            
            # Calculate the value*factor as a new column
            df['_vf_'] = df[dataCol] * df[self.FACTOR_COL]

            # Group by destination node
            groupedDf = df.groupby(self.DEST_COL)

            # For each destination, the weighted avg is
            # sum(value*factor) / sum(weight)
            summedDf = groupedDf.sum()
            summedDf[self.NEW_VALUE_COL] = summedDf['_vf_'] / summedDf[self.FACTOR_COL]

            # Remove the temp column we created
            retDf = summedDf.drop('_vf_')

        elif method == AggMethod.MEDIAN:
            # Median of the source data, weighted by factor
            raise NotImplementedError
        
        elif method == AggMethod.SUM:
            # Simple total across all sources
            # Factor not needed

            # Group by destination node
            groupedDf = df.groupby(self.DEST_COL)

            # Just do a simple sum
            retDf = groupedDf.sum()

        # Check that something was actually added
        if retDf is None or retDf.shape[0] == 0:
            msg = f"retDf is empty in Gator.Aggregate."
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        # Return it as a dataframe
        return retDf


    def DeAggregate(self, df: pd.DataFrame, idCol: str, dataCol: str, method: DeAggMethod,
                    factors: dict[Node, dict[Node, float]]) -> pd.DataFrame:
        
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
        
        # 3.) Group operations by destination node
    
        # Reverse the dict to group by destination node
        destMatches = {}
        for sn in allMatches:
            
            for dn in allMatches[sn]:
                
                # Grab the weight
                weight = allMatches[sn][dn]

                # Make a new dict if needed
                if not dn in destMatches:
                    destMatches[dn] = {}
                
                # Add the source to the dict
                destMatches[dn][sn] = weight
        
        # destMatches = {destNode: {sourceNode1: weight1, sourceNode2: weight2, ...}, ...}

        # 4.) Calculate mult factors

        factors = {} # Same form as destMatches, but factors instead of weights
        for dn in destMatches:
            for sn in destMatches[dn]:

                # Grab the weight
                weight = destMatches[dn][sn]

                # Divide the weight by the value (e.g. area) of the source
                factor = sn.values[edgeType] / weight

                # Sanity check
                if factor > 1:
                    msg = f"Factor of {factor} for {dn} - {sn} is invalid.\n \
                            destValues = {dn.values}\n \
                            sourceValues = {dn.values}\n \
                            weight = {weight}"
                    self.logger.error(msg)
                    raise RuntimeError(msg)

                # Save it into a new dict
                if not dn in factors:
                    factors[dn] = {}
                factors[dn][sn] = factor

        # 4.1) Append as columns for groupby operations
        sourceDf[self.DEST_COL] = [None for i in range(sourceDf.shape[0])]
        sourceDf[self.FACTOR_COL] = [None for i in range(sourceDf.shape[0])]

        # We need to set the index to use .at
        sourceDf = sourceDf.set_index(sourceIdCol)

        # Have to do this one at a time
        for dn in factors:
            for sn in factors[dn]:
                sourceDf.at[sn.id, self.DEST_COL] = dn.id
                sourceDf.at[sn.id, self.FACTOR_COL] = factors[dn][sn]

        # If ignoreIncomplete is false, check that each destination is 100% covered
        # We are assuming the sources are mutually exclusive (since they are the same type)
        if not ignoreIncomplete:

            # Group by destination node
            groupedDf = sourceDf.groupby(self.DEST_COL)

            # Factor sum for each destination node
            sums = groupedDf.sum()[self.FACTOR_COL]

            for dn in factors:

                # Get the factor sum for that destination node
                totalWeight = sums[dn.id].item()

                # Should be really close to 100%
                if not math.isclose(totalWeight, 1.0, abs_tol = 0.1):
                    msg = f"Total weight of {totalWeight} for node {dn} is invalid."
        
        else:
            # Included to make intellisense happy
            groupedDf = None
        

        # 5.) Do the calculation
        # We have everything we need: the destNodes, what nodes belong to each destNode, and
        # the factor to multiply the numerical data by
        # The actual operation depends on 'method'



        # 6.) Clean up before returning
        if not self.DEBUG:
            # Drop extra columns
            sourceDf = sourceDf.drop([self.FACTOR_COL])
        


        






    
                






        pass

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







    
