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

def GenerateTemporalSample(startTs: pd.Timestamp, endTs: pd.Timestamp,
                           unit: TID = TID.HOUR) \
    -> tuple[pd.DataFrame, pd.DataFrame]:

    # Use this function to generate temporal test data

    answerKeyRows = []
    sampleRows = []
    curStartTs = startTs
    argDict = {TID_TO_STRING[unit]: 1}
    ONE_UNIT = pd.DateOffset(**argDict)
    UNIT_TO_SEC_FACTOR = ((curStartTs + ONE_UNIT) - curStartTs).total_seconds()

    # Generate the test data in blocks of units that are subdivided
    # into intervals randomly

    while curStartTs < endTs:

        # Generate a random length
        numUnits = 5#random.randint(1,16)

        # Get the end point
        nextEndTs = min(curStartTs + (ONE_UNIT * numUnits), endTs)
        numUnits = (nextEndTs - curStartTs).total_seconds() / UNIT_TO_SEC_FACTOR

        # Generate some random data for it
        value = random.randint(1, 100)*numUnits

        print("\n")
        print(value)
        print(numUnits)
        print(math.ceil(numUnits))

        # Each hour in the interval will evenly split the value
        lastTs = curStartTs
        curKeyRows = []
        while lastTs < nextEndTs:# and len(curKeyRows) <= numUnits:
            print(lastTs)
            print(nextEndTs)

            # Initialize a new row
            newKeyRow = {}

            # Use the temp timestamp as the "id"
            newKeyRow[T_ID_COL] = lastTs

            # Cut off the last interval so as to not mess with future intervals
            nextTs = min(lastTs + ONE_UNIT, nextEndTs)

            # Calculate the relative size of the current unit
            curSize = (nextTs - lastTs).total_seconds() / (numUnits * UNIT_TO_SEC_FACTOR)

            # Add in its share of the value
            newKeyRow[T_DATA_COL] = value * curSize

            # Add the row in
            curKeyRows.append(newKeyRow)

            # Increment the tempTs
            #lastTs += ONE_UNIT
            lastTs = nextTs


        # Generate a bunch of intervals of random lengths
        # and use their size to determine their value

        lastIntervalTs = curStartTs
        nextIntervalTs = None
        curSampleRows = []
        minIntervals = 4
        while lastIntervalTs < nextEndTs:

            # Initialize a new row
            newSampleRow = {}

            # Get the next endpoint based on a random number of mins
            # We should have multiple intervals per chunk
            numMins = random.randint(1, int((UNIT_TO_SEC_FACTOR / 60.) * numUnits / minIntervals))
            #print("\n")
            #print(UNIT_TO_SEC_FACTOR)
            #print(numUnits)
            #print(numMins)

            # Cut off the last interval so as to not mess with future intervals
            nextIntervalTs = min(lastIntervalTs + pd.Timedelta(numMins, unit=TID.MINUTE.value), nextEndTs)
            numMins = (nextIntervalTs - lastIntervalTs).total_seconds() / 60.

            # Form the interval
            curInterval = pd.Interval(left=lastIntervalTs, right=nextIntervalTs)
            newSampleRow[T_INTERVAL_COL] = curInterval

            # Calculate the value as a fraction of the total time
            newSampleRow[T_DATA_COL] = value * (numMins / (numUnits * (UNIT_TO_SEC_FACTOR / 60.)))

            # Add the row
            curSampleRows.append(newSampleRow)

            # Increment the counter
            lastIntervalTs = nextIntervalTs
        
        # Sanity checks:

        # The total value should match the original
        #print("\n")
        #print(numMins)
        #print(numUnits)
        
        #print(f"Value: {value}")
        assert math.isclose(value, sum([row[T_DATA_COL] for row in curKeyRows]))
        assert math.isclose(value, sum([row[T_DATA_COL] for row in curSampleRows]))

        # Make sure each interval value is realistic
        for row in curSampleRows:
            assert row[T_DATA_COL] <= (value * (1./minIntervals))

        
        # Add the rows to their respective lists
        answerKeyRows.extend(curKeyRows)
        sampleRows.extend(curSampleRows)

        # Increment the counter
        curStartTs = nextEndTs

    # Make them into dataframes
    answerKeyDf = pd.DataFrame(data=answerKeyRows)
    sampleDf = pd.DataFrame(data=sampleRows)

    # Final sanity check: the totals should match
    assert math.isclose(answerKeyDf[T_DATA_COL].sum(), sampleDf[T_DATA_COL].sum())

    return sampleDf, answerKeyDf


def GenerateTemporalSampleOld(startTs: pd.Timestamp, endTs: pd.Timestamp,
                           unit: TID = TID.HOUR) \
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
    endTs = pd.Timestamp(year=2023, month=2, day=1, hour=0, minute=0, second=0)
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

@pytest.mark.basic
def testTemporalGenerationHard():

    # Use summing to test a bunch of units for sample generation
    #random.seed(42)
    levels = [TID.HOUR, TID.DAY, TID.MONTH, TID.YEAR]

    # Use a smaller timespan than other tests
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2021, month=4, day=6, hour=5, minute=0, second=0)

    sampleDfDict = {}
    answerKeyDfDict = {}
    for unit in levels:
        sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs, unit)
        sampleDfDict[unit] = sampleDf
        answerKeyDfDict[unit] = answerKeyDf

    
    # Rely on the gator for the sample
    # Yes, this is circular testing
    gator = Gator(None, Path('./logs/testGenerationHard.log'))
        
    
    # Test summation for all valid units for each sample unit
    for baseI, baseU in enumerate(levels[:-1]):
        curSampleDf = sampleDfDict[baseU]
        curAnswerDf = answerKeyDfDict[baseU]

        for testU in levels[baseI + 1:]:

            # Get the sample and answer mean at this level
            sampleMean = gator.TemporalEqualize(curSampleDf, testU, T_INTERVAL_COL,
                                                T_DATA_COL, AggMethod.MEAN)
            answerMean = curAnswerDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID_TO_PERIOD[testU])).mean()

            # Get the counts at this level
            sampleCount = gator.TemporalEqualize(curSampleDf, testU, T_INTERVAL_COL,
                                                 T_DATA_COL, AggMethod.COUNT)
            answerCount = curAnswerDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID_TO_PERIOD[testU])).count()

            # Merge the counts and means
            sampleMergedDf = pd.merge(sampleMean, sampleCount, left_index=True, right_index=True)
            answerMergedDf = pd.merge(answerMean, answerCount, left_index=True, right_index=True)

            # Form the final column
            sampleMergedDf[T_DATA_COL] = sampleMergedDf[T_DATA_COL + '_x']*sampleMergedDf[T_DATA_COL + '_y']
            answerMergedDf[T_DATA_COL] = answerMergedDf[T_DATA_COL + '_x']*answerMergedDf[T_DATA_COL + '_y']

            # Drop the other columns
            sampleFinalDf = sampleMergedDf.drop(labels=[T_DATA_COL + '_x', T_DATA_COL + '_y'], axis=1)
            answerFinalDf = answerMergedDf.drop(labels=[T_DATA_COL + '_x', T_DATA_COL + '_y'], axis=1)

            # Now, they should match
            print(f"\nCurrent units: {baseU}, {testU}")
            CompareWithAnswer(sampleFinalDf, answerFinalDf)


@pytest.mark.equalize
def testTemporalCountBasic():

    # Generate the test data
    #random.seed(42)
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2023, month=2, day=4, hour=0, minute=0, second=0)
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testTemporalCount.log'))

    # Have the gator aggregate to different levels
    levels = [TID.HOUR, TID.DAY, TID.MONTH, TID.YEAR]

    resDfDict = {}
    for unit in levels:
        resDfDict[unit] = gator.TemporalEqualize(sampleDf, unit, T_INTERVAL_COL,
                                                 T_DATA_COL, AggMethod.COUNT)

    """    
    We can't just compare to the "answerKey" in this case, as they, by their
    construction, will have different numbers of entries.  Best we can do
    is make sure the totals before and after counting are the same.
    """

    for unit in levels:
        assert math.isclose(resDfDict[unit][T_DATA_COL].sum(), sampleDf.shape[0])


@pytest.mark.equalize
def testTemporalMeanAndCount():

    # Generate the test data
    #random.seed(42)
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    #endTs = pd.Timestamp(year=2021, month=2, day=4, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2023, month=2, day=4, hour=0, minute=0, second=0)
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testTemporalMean.log'))

    # Have the gator aggregate to different levels
    levels = [TID.HOUR, TID.DAY, TID.MONTH, TID.YEAR]

    resDfDictMean = {}
    resDfDictCount = {}
    for unit in levels:
        resDfDictMean[unit] = gator.TemporalEqualize(sampleDf, unit, T_INTERVAL_COL,
                                                 T_DATA_COL, AggMethod.MEAN)
        resDfDictCount[unit] = gator.TemporalEqualize(sampleDf, unit, T_INTERVAL_COL,
                                                      T_DATA_COL, AggMethod.COUNT)
    
    # Manually aggregate the answer key to the same levels
    answerDfDictMean = {}
    answerDfDictCount = {}
    for unit in levels:
        answerDfDictMean[unit] = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID_TO_PERIOD[unit])).mean()
        answerDfDictCount[unit] = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID_TO_PERIOD[unit])).count()
    
    # The means and counts won't match, but the mean*count should

    # Join the respective dataframes and calculate the mean*count
    for unit in levels:
        curResDf = pd.merge(resDfDictMean[unit], resDfDictCount[unit],
                            left_index=True, right_index=True)
        curAnswerDf = pd.merge(answerDfDictMean[unit], answerDfDictCount[unit],
                               left_index=True, right_index=True)


        # Form the final column
        curResDf[T_DATA_COL] = curResDf[T_DATA_COL + '_x']*curResDf[T_DATA_COL + '_y']
        curAnswerDf[T_DATA_COL] = curAnswerDf[T_DATA_COL + '_x']*curAnswerDf[T_DATA_COL + '_y']

        # Drop the other columns
        curResDf = curResDf.drop(labels=[T_DATA_COL + '_x', T_DATA_COL + '_y'], axis=1)
        curAnswerDf = curAnswerDf.drop(labels=[T_DATA_COL + '_x', T_DATA_COL + '_y'], axis=1)

        # Now, they should match
        CompareWithAnswer(curResDf, curAnswerDf)



def testTemporalCopy():

    # Generate the test data
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2020, month=10, day=1, hour=0, minute=0, second=0)
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs)

    # Get a gator for deaggregating
    gator = Gator(None, Path('./logs/testTemporalCopy.log'))

    # TMinutes is (currently) the only supported granularity
    # more granular that the sample data
    levels = [TID.MINUTE, TID.HOUR]

    resDfDict = {}
    for unit in levels:
        resDfDict[unit] = gator.TemporalEqualize(sampleDf, unit, T_INTERVAL_COL,
                                                 T_DATA_COL, DeAggMethod.COPY)


    



if __name__ == "__main__":
    main()