from pathlib import Path

import pytest
import numpy as np

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import * 


# Use simple dataframes to test agg/deagg

@pytest.mark.aggregate
def testSum():

    # We need a graph for instantiation
    _, _, kGraph = ResetForTest(1, 1, 'testSum', BasicWeight)

    gator = Gator(kGraph, Path('./logs/testGator.log'))

    # Get the sample data
    idCol = 'sid'
    dataCol = 'pop'
    smallDf, largeDf = GetGatorSamples(gator, 8, idCol, dataCol)

    # Flatten the dataframe
    smallDf = gator.FlattenDataframe(smallDf, smallDf[gator.FACTOR_COL].to_dict(), idCol, dataCol)

    print(smallDf)

    # Run our own sum on it first for our answer key
    groupedDf = smallDf.groupby(gator.DEST_COL)
    tot = groupedDf[[dataCol]].sum()

    print(tot)

    # Now, get the gator to do it
    resDf = gator.Aggregate(smallDf, idCol, dataCol, AggMethod.SUM)
    
    # Result df should look exactly like largeDf/totalDf, though in a real-world use case,
    # the data would be different.

    print(resDf)

    # Go through one at a time to make sure it all matches
    #for ind, row in 
    print(largeDf)

    for ind, row in largeDf.iterrows():

        assert tot.at[ind, dataCol] == row[dataCol]
        assert resDf.at[ind, dataCol] == row[dataCol]

