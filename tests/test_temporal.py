import pytest
import numpy as np
import random
import math

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import *



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
        nextTs = min(curTs + pd.Timedelta(numHours, unit=TID.HOUR.value), endTs)
        numHours = (nextTs - curTs).total_seconds() / (60*60)

        # Initialize new rows
        curKeyRows = []
        curSampleRows = []

        # Generate some random data for it
        value = random.randint(1, 100)*numHours

        # Each hour in the interval will evenly split the value
        tempTs = curTs
        curKeyRows = []
        while tempTs < curTs + (ONE_HOUR * numHours):

            # Initialize a new row
            newKeyRow = {}

            # Use the temp timestamp as the "id"
            newKeyRow['Hour Start'] = tempTs

            # Add in its share of the value
            newKeyRow['Value'] = value / numHours

            # Add the row in
            curKeyRows.append(newKeyRow)

            # Increment the tempTs
            tempTs += ONE_HOUR


        # Generate a bunch of intervals of random lengths
        # and use their size to determine their value
        curEndHour = min(curTs + (ONE_HOUR*numHours), endTs)

        lastIntervalTs = curTs
        nextIntervalTs = None
        curSampleRows = []
        minIntervals = 4
        while lastIntervalTs < curEndHour:

            # Initialize a new row
            newSampleRow = {}

            # Get the next endpoint based on a random number of mins
            # We should have multiple intervals per chunk
            numMins = random.randint(1, int(60. * numHours / minIntervals))

            # Cut off the last interval so as to not mess with future intervals
            nextIntervalTs = min(lastIntervalTs + pd.Timedelta(numMins, unit=TID.MINUTE.value), curEndHour)
            numMins = (nextIntervalTs - lastIntervalTs).total_seconds() / 60.

            # Form the interval
            curInterval = pd.Interval(left=lastIntervalTs, right=nextIntervalTs)
            newSampleRow['Interval'] = curInterval

            # Calculate the value as a fraction of the total time
            newSampleRow['Value'] = value * (numMins / (numHours * 60))

            # Add the row
            curSampleRows.append(newSampleRow)

            # Increment the counter
            lastIntervalTs = nextIntervalTs
        
        # Sanity checks:

        # The total value should match the original
        assert math.isclose(value, sum([row['Value'] for row in curKeyRows]))
        assert math.isclose(value, sum([row['Value'] for row in curSampleRows]))

        # Make sure each interval value is realistic
        for row in curSampleRows:
            assert row['Value'] <= (value * (1./minIntervals))

        
        # Add the rows to their respoective lists
        answerKeyRows.extend(curKeyRows)
        sampleRows.extend(curSampleRows)

        # Increment the counter
        curTs = nextTs

    # Make them into dataframes
    answerKeyDf = pd.DataFrame(data=answerKeyRows)
    sampleDf = pd.DataFrame(data=sampleRows)

    # Final sanity check: the totals should match
    assert math.isclose(answerKeyDf['Value'].sum(), sampleDf['Value'].sum())

    return sampleDf, answerKeyDf


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

if __name__ == "__main__":
    main()