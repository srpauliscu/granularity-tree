import pytest
import numpy as np
import random
import math

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import *


# Global vars for column names
T_ID_COL = "_hour_start_"
T_DATA_COL = "_value_"
T_INTERVAL_COL = "_interval_"

# Use simple dataframes to test agg/deagg

def GenerateTemporalSample(startTs: pd.Timestamp, endTs: pd.Timestamp) \
    -> tuple[pd.DataFrame, pd.DataFrame]:

    # Use this function to generate temporal test data

    answerKeyRows = []
    sampleRows = []
    curTs = startTs
    ONE_HOUR = pd.Timedelta(1, unit=TID.HOUR.value)

    # Generate the test data in blocks of hours that are subdivided
    # into intervals randomly

    while curTs < endTs:

        # Generate a random length
        numHours = random.randint(1,16)

        # Get the end point
        nextTs = min(curTs + (ONE_HOUR * numHours), endTs)
        numHours = (nextTs - curTs).total_seconds() / (60*60)

        # Initialize new rows
        curKeyRows = []
        curSampleRows = []

        # Generate some random data for it
        value = random.randint(1, 100)*numHours

        # Each hour in the interval will evenly split the value
        tempTs = curTs
        curKeyRows = []
        while tempTs < nextTs:

            # Initialize a new row
            newKeyRow = {}

            # Use the temp timestamp as the "id"
            newKeyRow[T_ID_COL] = tempTs

            # Add in its share of the value
            newKeyRow[T_DATA_COL] = value / numHours

            # Add the row in
            curKeyRows.append(newKeyRow)

            # Increment the tempTs
            tempTs += ONE_HOUR


        # Generate a bunch of intervals of random lengths
        # and use their size to determine their value

        lastIntervalTs = curTs
        nextIntervalTs = None
        curSampleRows = []
        minIntervals = 4
        while lastIntervalTs < nextTs:

            # Initialize a new row
            newSampleRow = {}

            # Get the next endpoint based on a random number of mins
            # We should have multiple intervals per chunk
            numMins = random.randint(1, int(60. * numHours / minIntervals))

            # Cut off the last interval so as to not mess with future intervals
            nextIntervalTs = min(lastIntervalTs + pd.Timedelta(numMins, unit=TID.MINUTE.value), nextTs)
            numMins = (nextIntervalTs - lastIntervalTs).total_seconds() / 60.

            # Form the interval
            curInterval = pd.Interval(left=lastIntervalTs, right=nextIntervalTs)
            newSampleRow[T_INTERVAL_COL] = curInterval

            # Calculate the value as a fraction of the total time
            newSampleRow[T_DATA_COL] = value * (numMins / (numHours * 60))

            # Add the row
            curSampleRows.append(newSampleRow)

            # Increment the counter
            lastIntervalTs = nextIntervalTs
        
        # Sanity checks:

        # The total value should match the original
        assert math.isclose(value, sum([row[T_DATA_COL] for row in curKeyRows]))
        assert math.isclose(value, sum([row[T_DATA_COL] for row in curSampleRows]))

        # Make sure each interval value is realistic
        for row in curSampleRows:
            assert row[T_DATA_COL] <= (value * (1./minIntervals))

        
        # Add the rows to their respective lists
        answerKeyRows.extend(curKeyRows)
        sampleRows.extend(curSampleRows)

        # Increment the counter
        curTs = nextTs

    # Make them into dataframes
    answerKeyDf = pd.DataFrame(data=answerKeyRows)
    sampleDf = pd.DataFrame(data=sampleRows)

    # Final sanity check: the totals should match
    assert math.isclose(answerKeyDf[T_DATA_COL].sum(), sampleDf[T_DATA_COL].sum())

    return sampleDf, answerKeyDf


# Reduce code duplication for comparing against answer keys
def CompareWithAnswer(resDf: pd.DataFrame, answerKeyDf: pd.DataFrame) -> None:

    # Check that the lengths are the same
    print(resDf)
    print(answerKeyDf)
    assert resDf.shape[0] == answerKeyDf.shape[0]

    # Join them on their timestamps
    joinedDf = pd.merge(answerKeyDf, resDf, left_index=True,
                        right_index=True)
    
    # They should also be the same length
    assert joinedDf.shape[0] == answerKeyDf.shape[0]

    # Check that all of them match
    joinedDf['Matching'] = joinedDf.apply(lambda x: math.isclose(
        x[T_DATA_COL + '_x'], x[T_DATA_COL + '_y']), axis=1)
    
    assert all(joinedDf['Matching'])


@pytest.mark.basic
def testTemporalGeneration():

    # Use this to test the sample generation
    # function above

    # Seed the generator for testing, as needed
    #random.seed(42)

    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    #endTs = pd.Timestamp(year=2020, month=2, day=2, hour=23, minute=0, second=0)
    endTs = pd.Timestamp(year=2021, month=1, day=1, hour=0, minute=0, second=0)

    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

@pytest.mark.equalize
def testTemporalSumBasic():

    # Generate the test data
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2020, month=10, day=1, hour=0, minute=0, second=0)
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testTemporalSumBasic.log'))

    # Have the gator aggregate to the hour level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.HOUR, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    # Manually aggregate to the hour level in the answer key
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL,freq=TID.HOUR.value)).sum()

    # Compare the result with the answer
    CompareWithAnswer(gatorResDf, aggAnswerDf)


@pytest.mark.equalize
def testTemporalSumHard():

    # Generate the test data
    #random.seed(42)
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2024, month=2, day=1, hour=0, minute=0, second=0)
    #endTs = pd.Timestamp(year=2020, month=2, day=1, hour=1, minute=0, second=0)
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testTemporalSumHard.log'))


    # Get the gator to aggregate to different levels
    levels = [TID.HOUR, TID.DAY, TID.MONTH, TID.YEAR]

    resDfDict = {}
    for unit in levels:
        resDfDict[unit] = gator.TemporalEqualize(sampleDf, unit, T_INTERVAL_COL,
                                                 T_DATA_COL, AggMethod.SUM)
        
    # Manually aggregate the answer key to the same levels
    answerDfDict = {}
    for unit in levels:
        answerDfDict[unit] = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID_TO_PERIOD[unit])).sum()
    
    # Check that each result matches the corresponding answer
    for unit in levels:
        CompareWithAnswer(resDfDict[unit], answerDfDict[unit])


@pytest.mark.equalize
def testTemporalCount():

    # Generate the test data
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2021, month=2, day=3, hour=0, minute=0, second=0)
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testTemporalCount.log'))

    # Have the gator aggregate to different levels
    levels = [TID.HOUR, TID.DAY, TID.MONTH]

    resDfDict = {}
    for unit in levels:
        resDfDict[unit] = gator.TemporalEqualize(sampleDf, unit, T_INTERVAL_COL,
                                                 T_DATA_COL, AggMethod.COUNT)
        
    # Manually aggregate the answer key to the same levels
    answerDfDict = {}
    for unit in levels:
        answerDfDict[unit] = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=unit.value)).count()
    
    # Check that each result matches the corresponding answer
    for unit in levels:
        CompareWithAnswer(resDfDict[unit], answerDfDict[unit])


if __name__ == "__main__":
    main()