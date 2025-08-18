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

    # Run our own sum on it first for our manual answer key
    groupedDf = smallDf.groupby(gator.DEST_COL)
    tot = groupedDf[[dataCol]].sum()

    # Now, get the gator to do it
    resDf = gator.Aggregate(smallDf, dataCol, AggMethod.SUM,
                            gator.DEST_COL, gator.FACTOR_COL, gator.VALUE_FACTOR_COL)

    # Result df should look exactly like largeDf/totalDf, though in a real-world use case,
    # the data would be different.

    # Go through one at a time to make sure it all matches
    for ind, row in largeDf.iterrows():

        assert tot.at[(ind,), dataCol] == row[dataCol]
        assert resDf.at[(ind,), dataCol] == row[dataCol]

@pytest.mark.aggregate
def testMean():


    # We need a graph for instantiation
    _, _, kGraph = ResetForTest(1, 1, 'testSum', BasicWeight)

    gator = Gator(kGraph, Path('./logs/testGator.log'))

    # Get the sample data
    idCol = 'sid'
    dataCol = 'pop'
    smallDf, largeDf = GetGatorSamples(gator, 8, idCol, dataCol)

    # Flatten the dataframe
    smallDf = gator.FlattenDataframe(smallDf, smallDf[gator.FACTOR_COL].to_dict(), idCol, dataCol)

    # Calculate the mean manually based on the largedf's value*factor column
    # This means we need to flatten the large dataframe too
    largeDf = gator.FlattenDataframe(largeDf, largeDf[gator.FACTOR_COL].to_dict(), idCol, dataCol)

    print(largeDf)

    groupedDf = largeDf.groupby(idCol)[[gator.VALUE_FACTOR_COL]].mean()
    groupedDf = groupedDf.rename(columns={gator.VALUE_FACTOR_COL: dataCol})

    #print(smallDf)
    #print(largeDf)
    print(groupedDf)
    
    # Get the gator to do it
    resDf = gator.Aggregate(smallDf, dataCol, AggMethod.MEAN,
                            gator.DEST_COL, gator.FACTOR_COL, gator.VALUE_FACTOR_COL)

    # Check that the results match
    for ind, row in groupedDf.iterrows():
        assert resDf.at[(ind,), dataCol] == row[dataCol]


@pytest.mark.deaggregate
def testDistribute():

    # We need a graph for instantiation
    _, _, kGraph = ResetForTest(1, 1, 'testSum', BasicWeight)

    gator = Gator(kGraph, Path('./logs/testGator.log'))

    # Get the sample data
    idCol = 'sid'
    dataCol = 'pop'
    smallDf, largeDf = GetGatorSamples(gator, 8, idCol, dataCol)

    # Flatten the dataframe
    largeDf = gator.FlattenDataframe(largeDf, largeDf[gator.FACTOR_COL].to_dict(), idCol, dataCol)

    # Get the gator to to the distribution
    resDf = gator.DeAggregate(largeDf, dataCol, DeAggMethod.DISTRIBUTE,
                              gator.DEST_COL, gator.FACTOR_COL, gator.VALUE_FACTOR_COL)

    # Check that the results match
    for ind, row in smallDf.iterrows():
        assert resDf.at[ind, dataCol] == row[dataCol]



@pytest.mark.deaggregate
def testCopy():

    # We need a graph for instantiation
    _, _, kGraph = ResetForTest(1, 1, 'testSum', BasicWeight)

    gator = Gator(kGraph, Path('./logs/testGator.log'))

    # Get the sample data
    idCol = 'sid'
    dataCol = 'pop'
    smallDf, largeDf = GetGatorSamples(gator, 8, idCol, dataCol)

    # Flatten the dataframe
    largeDf = gator.FlattenDataframe(largeDf, largeDf[gator.FACTOR_COL].to_dict(), idCol, dataCol)

    # Get the gator to to the copying
    resDf = gator.DeAggregate(largeDf, dataCol, DeAggMethod.COPY,
                              gator.DEST_COL, gator.FACTOR_COL, gator.VALUE_FACTOR_COL)

    print(smallDf)
    print(largeDf)
    print(resDf)

    # Check that each id in the smallDf was correctly assigned
    # the value of its owner id
    for ind, row in smallDf.iterrows():
        for did in row[gator.DEST_COL]:
            assert resDf.at[(did,), dataCol] == largeDf.at[did, dataCol]
