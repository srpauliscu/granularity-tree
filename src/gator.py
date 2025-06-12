


import numpy as np
import logging
import json
import pandas as pd
from pathlib import Path
import math

from kGraph import *


class Gator(object):


    def __init__(self, _kGraph: GranularityGraph, logFile: Path):

        self.kGraph = _kGraph

        #: logging.Logger: A logging object
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename=str(logFile), encoding='utf-8', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        self.logger = logger

    
    def Equalize(self, sourceDf: pd.DataFrame, destDf: pd.DataFrame,
                sourceType: GEID | TID, destType: GEID | TID,
                sourceIdCol: str, destIdCol: str,
                sourceDataCol: str, destDataCol: str,
                method: AggMethod | DeAggMethod,
                edgeType: EdgeType, ignoreMissing: bool = False) -> pd.DataFrame:

        """
        Attempt to make the data in sourceDf match the granularity of destDf via 'edgeType'
        and using the given method.

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
        sourceNodes, destNodes = self.MakeNodes(sourceDf['a'], destDf['b'], GEID.AIANNHA, GEID.BLOCK)

        # 2.) For each source node, find all matching destNodes
        allMatches = {}
        for sn in sourceNodes:
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

        # If ignoreMissing is false, check that each destination is 100% covered
        # We are assuming the sources are mutually exclusive (since they are the same type)
        if not ignoreMissing:
            for dn in factors:
                totalWeight = 0
                for sn in factors[dn]:
                    totalWeight += factors[dn][sn]
            
                # Should be really close to 100%
                if not math.isclose(totalWeight, 1.0, abs_tol = 0.1):
                    msg = f"Total weight of {totalWeight} for node {dn} is invalid."
        

        # 5.) Do the calculation
        # We have everything we need: the destNodes, what nodes belong to each destNode, and
        # the factor to multiply the numerical data by
        # The actual operation depends on 'method'


        






    
                






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







    
