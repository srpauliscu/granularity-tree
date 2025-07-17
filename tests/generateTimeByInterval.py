

# Functions to generate temporal test data
import datetime
import pandas as pd
import numpy as np
import math


# Function to test basic invariants
def GenericValidityCheck(adjMat: np.typing.NDArray) -> bool:

    for i in range(adjMat.shape[0]):
        for j in range(adjMat.shape[1]):
            # Diag should be 0s
            if i == j:
                assert adjMat[i, j] == 0
            
            # It should be symmetric
            assert adjMat[i, j] == adjMat[j, i]

    return True

# Functions to fill in the specified block
def FillMat(adjMat: np.typing.NDArray,
            tsl1: pd.IntervalIndex, tsl2: pd.IntervalIndex,
            start1: int, start2: int, freq: str, weight: int):
    
    for v1i, v1 in enumerate(tsl1):
        for v2i, v2 in enumerate(tsl2):

            if v1.overlaps(v2):
                # We shouldn't be overriding anything
                assert adjMat[v2i + start2, v1i + start1] == 0
                assert adjMat[v1i + start1, v2i + start2] == 0

                # Assign the weight
                adjMat[v2i + start2, v1i + start1] = weight
                adjMat[v1i + start1, v2i + start2] = weight

    
    return adjMat





def main():

    # Start by generating the timestamps
    startTime = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTime = pd.Timestamp(year=2020, month=1, day=5, hour=0, minute=0, second=0)
    totMins = int((endTime - startTime).total_seconds() / 60.)


    # Generate intervals for each frequency
    mins = pd.interval_range(startTime, endTime, freq='min', closed='left')
    hours = pd.interval_range(startTime, endTime, freq='h', closed='left')
    days = pd.interval_range(startTime, endTime, freq='D', closed='left')
    months = pd.interval_range(startTime, endTime, freq='MS', closed='left')
    years = pd.interval_range(startTime, endTime, freq='YS', closed='left')

    # Put them in a dict for organization
    allTimes = {
        'minutes': mins,
        'hours': hours,
        'days': days,
        'months': months,
        'years': years
    }



    # Make a blank matrix of the proper size
    totalLen = sum([len(allTimes[k]) for k in allTimes])
    adjMat = np.zeros((totalLen, totalLen))


    ### Minutes - hours ###

    mStart = 0
    mEnd = mStart + len(allTimes['minutes'])
    hStart = mEnd
    hEnd = hStart + len(allTimes['hours'])

    print('Minutes - hours...')
    adjMat = FillMat(adjMat, allTimes['hours'], allTimes['minutes'], hStart, mStart, 'h', 1)

    # Sanity checks
    assert GenericValidityCheck(adjMat)

    for i in range(adjMat.shape[0]):
        

        # Each minute row/column should have a single 1, since each
        # minute overlaps 1 minute with a single hour
        if i < mStart:
            assert adjMat[i].sum() == 1

        # Each hour row/column should have 60 1s in it at this point
        if i >= hStart and i < hEnd:
            assert adjMat[i].sum() == 60 or adjMat[i].sum() == totMins % 60


    ### Minutes - days ###
    dStart = hEnd
    dEnd = dStart + len(allTimes['days'])

    print('Minutes - days...')
    adjMat = FillMat(adjMat, allTimes['days'], allTimes['minutes'], dStart, mStart, 'd', 1)

    # Sanity checks
    assert GenericValidityCheck(adjMat)

    for i in range(adjMat.shape[0]):

        # Each minute row/column should have two 1s
        if i < mStart:
            assert adjMat[i].sum() == 2
        
        # Each day row/column should have 60*24 1s in it, or the entirety
        # of the mins we have (for when we're testing)
        if i >= dStart and i < dEnd:
            assert adjMat[i].sum() == 60*24 or adjMat[i].sum() == totMins % (60*24)


    ### Minutes - months ###
    moStart = dEnd
    moEnd = moStart + len(allTimes['months'])

    print('Minutes - months...')
    adjMat = FillMat(adjMat, allTimes['months'], allTimes['minutes'], moStart, mStart, 'mo', 1)

    # Sanity checks
    assert GenericValidityCheck(adjMat)

    for i in range(adjMat.shape[0]):

        # Each minute row/column should have three 1s
        if i < mStart:
            assert adjMat[i].sum() == 3
        
        # Each month row/column should have the total number of minutes
        # for that month
        if i >= moStart and i < moEnd:
            # Get a copy of that month's timestamp
            moTs = allTimes['months'][i - moStart].left

            # Calculate the appropriate number of minutes for that month
            if moTs.month == 12:
                moMins = 60*24*31
            else:
                moMins = int((pd.Timestamp(year=moTs.year, month=moTs.month + 1, day=1) - moTs).total_seconds() / 60.)

            assert adjMat[i].sum() == moMins or adjMat[i].sum() == totMins % moMins

    ### Minutes - years ###
    yStart = moEnd
    yEnd = yStart + len(allTimes['years'])

    print('Minutes - years...')
    adjMat = FillMat(adjMat, allTimes['years'], allTimes['minutes'], yStart, mStart, 'y', 1)

    # Sanity checks
    assert GenericValidityCheck(adjMat)

    for i in range(adjMat.shape[0]):

        # Each minute row/column should have four 1s
        if i < mStart:
            assert adjMat[i].sum() == 4
        
        # Each month row/column should have the total number of minutes
        # for that year
        if i >= yStart and i < yEnd:
            # Get a copy of that year's timestamp
            yTs = allTimes['years'][i - yStart].left

            # Calculate the appropriate number of minutes for that month
            # This accounts for leap years
            yMins = int((pd.Timestamp(year=yTs.year + 1, month=1, day=1) - yTs).total_seconds() / 60.)

            assert adjMat[i].sum() == yMins or adjMat[i].sum() == totMins % yMins


    ### Hours - days ###
    print('\nHours - days...')
    adjMat = FillMat(adjMat, allTimes['days'], allTimes['hours'], dStart, hStart, 'd', 60)

    # Sanity checks
    assert GenericValidityCheck(adjMat)

    np.set_printoptions(threshold=np.inf)

    for i in range(adjMat.shape[0]):

        # Each hour column should have 60 + leftovers,
        # if not matched with a full 60 minutes
        if i >= hStart and i < hEnd:
            assert (adjMat[i].sum() == 60 + 60 or
                    adjMat[i].sum() == 60)
                
        
        if i >= dStart and i < dEnd:

            # Each day column should have 24 hours and 24*60 minutes
            assert (adjMat[i].sum() == 24*60 + 24*60)
    
    ### Hours - months ###
    print('\nHours - months...')
    adjMat = FillMat(adjMat, allTimes['months'], allTimes['hours'], moStart, hStart, 'mo', 60)

    # Sanity checks
    assert GenericValidityCheck(adjMat)

    for i in range(adjMat.shape[0]):
        
        # Each hour column should have another 60 minutes in it
        # or just what it already had if it wasn't matched with a full month
        if i >= hStart and i < hEnd:
            if adjMat[i].sum() != 60*3:
                print(adjMat[i].sum())
            assert (adjMat[i].sum() == 60*3)
        

        



        







if __name__ == "__main__":


    main()








