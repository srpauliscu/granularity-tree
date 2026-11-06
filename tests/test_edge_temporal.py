import pytest
import numpy as np
import random
import math

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import *


# Reduce code duplication for comparing against answer keys
def CompareWithAnswer(resDf: pd.DataFrame, answerKeyDf: pd.DataFrame) -> None:

    # Check that the lengths are the same
    assert resDf.shape[0] == answerKeyDf.shape[0]

    # Join them on their timestamps
    joinedDf = pd.merge(answerKeyDf, resDf, left_index=True,
                        right_index=True)
    
    # They should also be the same length
    assert joinedDf.shape[0] == answerKeyDf.shape[0]

    # Check that all of them match
    joinedDf['Matching'] = joinedDf.apply(lambda x: math.isclose(
        x[T_DATA_COL + '_x'], x[T_DATA_COL + '_y']), axis=1)
    
    print(joinedDf[joinedDf['Matching'] == False])
    
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
def testHourlyBoundary():

    # Specific test to ensure we can handle intervals
    # that cross hourly boundaries

    # Seed the generator for testing the test, as needed
    #random.seed(42)

    # Generate the test data
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=1, minute=5, second=0)
    endTs = pd.Timestamp(year=2020, month=1, day=1, hour=20, minute=45, second=0)

    # While this does not technically guarantee a boundary crossing, it is very unlikely that
    # there would be none.  Repeated tests help with this.
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE, maxBlocks=60)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testHourlyBoundary.log'))

    # Have the gator aggregate to the hourly level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.HOUR, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    # Manually aggregate to the hour level
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.HOUR.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)

@pytest.mark.equalize
def testDailyBoundary():

    # Specific test to ensure we can handle intervals
    # that cross daily boundaries

    # Seed the generator for testing the test, as needed
    #random.seed(42)

    # Generate the test data
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=1, minute=5, second=0)
    endTs = pd.Timestamp(year=2020, month=1, day=20, hour=15, minute=45, second=0)

    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE, maxBlocks=120)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testDailyBoundary.log'))

    # Have the gator aggregate to the daily level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.DAY, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    # Manually aggregate to the day level
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.DAY.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)


@pytest.mark.equalize
def testSpringForward():

    # Specific test for starting DST
    # To simulate it, do not generate data between 2-3am

    # In 2026, DST started March 8, 2:00am

    startTs = pd.Timestamp(year=2026, month=3, day=7, hour=18, minute=0, second=0)
    endTs = pd.Timestamp(year=2026, month=3, day=8, hour=2, minute=0, second=0)

    # Any number of blocks should be fine
    lSampleDf, lAnswerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE, maxBlocks=60)

    # Generate the second half
    startTs = pd.Timestamp(year=2026, month=3, day=8, hour=3, minute=0, second=0)
    endTs = pd.Timestamp(year=2026, month=3, day=8, hour=12, minute=0, second=0)

    rSampleDf, rAnswerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE, maxBlocks=60)

    # Concatenate the datasets
    sampleDf = pd.concat([lSampleDf, rSampleDf], ignore_index=True)
    answerKeyDf = pd.concat([lAnswerKeyDf, rAnswerKeyDf], ignore_index=True)

    pd.set_option('display.max_rows', None)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testDailyBoundary.log'))

    # Have the gator aggregate to the hourly level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.HOUR, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    # Manually aggregate to the hour level and drop the empty 2am row
    # (the pd.Grouper forces each interval to have a row, despite no data being there)
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.HOUR.value)).sum()
    aggAnswerDf = aggAnswerDf[aggAnswerDf.index != pd.Timestamp(year=2026, month=3, day=8, hour=2, minute=0, second=0)]

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)



    # Do the same thing but for daily aggregation
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.DAY, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.DAY.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)



    # Repeat again at the minute level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.MINUTE, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.MINUTE.value)).sum()

    # Again, drop all results within the 2-3am block
    aggAnswerDf = aggAnswerDf[aggAnswerDf.index.hour != 2]


    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)


@pytest.mark.equalize
def testFallBack():

    # Specific test for ending DST
    # To simulate, generate data for the 2-3am block twice

    # In 2026, DST ended November 1, 2:00am

    np.random.seed(43)

    startTs = pd.Timestamp(year=2026, month=10, day=31, hour=19, minute=0, second=0)
    endTs = pd.Timestamp(year=2026, month=11, day=1, hour=3, minute=0, second=0)

    # Any number of blocks should be fine, with repeated tests
    lSampleDf, lAnswerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE, maxBlocks=120)

    startTs = pd.Timestamp(year=2026, month=11, day=1, hour=2, minute=0, second=0)
    endTs = pd.Timestamp(year=2026, month=11, day=1, hour=13, minute=0, second=0)

    # Any number of blocks should be fine, with repeated tests
    rSampleDf, rAnswerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE, maxBlocks=120)

    # Concatenate them
    sampleDf = pd.concat([lSampleDf, rSampleDf], ignore_index=True)
    answerKeyDf = pd.concat([lAnswerKeyDf, rAnswerKeyDf], ignore_index=True)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testDailyBoundary.log'))

    # Have the gator aggregate to the hourly level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.HOUR, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    # Manually aggregate to the hour level
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.HOUR.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)



    # Do the same thing but for daily aggregation
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.DAY, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.DAY.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)



    # Repeat again at the minute level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.MINUTE, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.MINUTE.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)



@pytest.mark.equalize
def testMissingTimes():

    # Specific test to ensure we can handle intervals
    # with randomly missing values

    # Seed the generator for testing the test, as needed
    #random.seed(42)

    # Generate the test data
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=1, minute=5, second=0)
    endTs = pd.Timestamp(year=2020, month=1, day=20, hour=15, minute=45, second=0)

    missingChance = (.75 - .25) * np.random.random() + .25
    sampleDf, answerKeyDf = GenerateTemporalSample(startTs, endTs, unit=TID.MINUTE,
                                                   maxBlocks=120, missingChance=missingChance)

    # Get a gator for aggregating
    gator = Gator(None, Path('./logs/testDailyBoundary.log'))

    # Have the gator aggregate to the daily level
    gatorResDf = gator.TemporalEqualize(sampleDf, TID.DAY, T_INTERVAL_COL,
                                        T_DATA_COL, AggMethod.SUM)
    
    # Manually aggregate to the day level
    aggAnswerDf = answerKeyDf.groupby(pd.Grouper(key=T_ID_COL, freq=TID.DAY.value)).sum()

    # Compare the results
    CompareWithAnswer(gatorResDf, aggAnswerDf)


if __name__ == "__main__":
    main()