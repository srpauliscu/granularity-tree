

# Functions to generate temporal test data
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import math
from tqdm import tqdm

from gator import *
from kGraph import Node, GranularityGraph
from populateGraph import AddLevel, AddNodes, LoadShapefile, OVERLAY_AREA_COLUMN


# Global vars
HOURCOL = '_hour_ts_'
OVERLAPCOL = '_overlap_'
VALFACTORCOL = '_value_factor_'
ADJUSTEDENERGY = '_adjusted_energy_'


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

def ConvertEndDate(row, fmt: str):

    # When the format doesn't match, use the duration as
    # an offset from the start date
    try:
        ts = pd.to_datetime(row['End Date'], format=fmt)

        # Check if the end date was erroneously recorded
        duration = pd.to_timedelta(row['Total Duration (hh:mm:ss)'])
        if ts == row['Start Date'] and duration != pd.to_timedelta(0, unit='min'):
            # Use the duration to calculate the end date
            raise ValueError
        
        # End date recorded as earlier than start date
        if ts < row['Start Date']:
            raise ValueError
        
        return ts
    
    except ValueError as e:
        # Get the duration as a timedelta
        td = pd.to_timedelta(row['Total Duration (hh:mm:ss)'])

        # Calculate end date using the duration
        return row['Start Date'] + td

    except Exception as e:
        raise e


def main(load: bool = True, overwrite: bool = True, relTol: float = .00001):

    # Folder information
    graphsDir = Path("./graphs")

    # Load up the graph
    graph = GranularityGraph('chargingStationUsageGraph', Path('./logs/chargingStationUsageGraph.log'))
    if load:
        # This will run even if we don't have a save file
        graph.LoadGraph(graphsDir)

    # Load in the charging station data
    cols = ['Station Name', 'MAC Address', 'Start Date',
            'Start Time Zone', 'End Date', 'End Time Zone',
            'Total Duration (hh:mm:ss)', 'Energy (kWh)', 'City', 'State/Province',
            'Postal Code', 'Country', 'Latitude', 'Longitude',
            'Driver Postal Code', 'User ID', 'County']
    
    # Use a smaller sample for testing
    csuDf = pd.read_csv(Path('./data/temporal/EVChargingStationUsage.csv'), 
                        usecols=cols, low_memory=False)#, nrows=1000)

    # Make sure we have the right data types
    fmt = "%m/%d/%Y %H:%M"
    csuDf['Start Date'] = pd.to_datetime(csuDf['Start Date'], format=fmt)
    csuDf['End Date'] = csuDf.apply(ConvertEndDate, args=(fmt,), axis=1)

    # Use the bounds of the data to seed the graph
    startTime = csuDf['Start Date'].min()
    endTime = csuDf['End Date'].max()

    totMins = int((endTime - startTime).total_seconds() / 60.)


    '''
    Want: Calculate total cost per hour for charging station usage to see
        if TOU hours have an impact.

    Input: charging station usage (start/end time, total energy used)
    Output: power usage per hour

    Steps:
    1.) For each charging interval, break it into hourly data and
        calculate the overlap amount for each hour it covers.
        Ex: 11:45 - 14:20: hours 11, 12, 13, 14 with weights
        (in minutes) 15, 60, 60, 20.
    2.) Calculate the factor for multiplying with the total energy
        used during that session for each hour it covers.
    3.) Group by hour and sum the value_factor * total energy

    
    '''

    # 1.) Find the timestamps representing the hours each session covers
    newRows = []
    for i, row in tqdm(csuDf.iterrows()):

        # Start and end timestamps
        startHour = row['Start Date'].floor(freq='h')
        endHour = row['End Date'].ceil(freq='h')

        # Generate timestamps for each hour between the two endpoints
        tempNewRows = []
        shTemp = startHour
        while shTemp < endHour:
            newRow = {}

            # Copy over relevant data
            for c in cols:
                newRow[c] = row[c]
            
            # Add in the hour timestamp
            newRow[HOURCOL] = shTemp

            # Special cases for overlap
            overlap = None
            if endHour == (startHour + pd.Timedelta(1, unit='h')):
                # Special case: the session was entirely contained in one hour
                overlap = (row['End Date'] - row['Start Date']).total_seconds() / 60.

            elif shTemp + pd.Timedelta(1, unit='h') >= endHour:
                # We're in the last hour
                overlap = (pd.Timedelta(60, unit='min') - (endHour - row['End Date'])).total_seconds() / 60.

            elif shTemp == startHour:
                # We're in the first hour
                overlap = (pd.Timedelta(60, unit='min') - (row['Start Date'] - shTemp)).total_seconds() / 60.

            else:
                # Any hours in between are fully covered
                overlap = 60

            # Add the overlap to the row
            newRow[OVERLAPCOL] = overlap

            # Calculate the value factor too (all "destinations" are one hour in size)
            newRow[VALFACTORCOL] = overlap / ((row['End Date'] - row['Start Date']).total_seconds() / 60.)

            # Calculate the energy used in that hour
            newRow[ADJUSTEDENERGY] = newRow[VALFACTORCOL] * newRow['Energy (kWh)']

            # Add the new row to the list
            tempNewRows.append(newRow)


            # Increment the hour
            shTemp += pd.Timedelta(1, unit='h')

        # Sanity check: the total wattage used should match the original
        valueFactors = [r[ADJUSTEDENERGY] for r in tempNewRows]
        if not math.isclose(sum(valueFactors), row['Energy (kWh)']):
            print(sum(valueFactors))
            print(row['Energy (kWh)'])
            print(f"Index {i}")
        assert math.isclose(sum(valueFactors), row['Energy (kWh)'])

        # Add them to the new dataframe
        newRows.extend(tempNewRows)


   
    # Make a dataframe out of the new rows
    hourlyCsuDf = pd.DataFrame(data=newRows)
    print(hourlyCsuDf)

    # Sanity check: the total energy usage should match
    assert math.isclose(hourlyCsuDf[ADJUSTEDENERGY].sum(), csuDf['Energy (kWh)'].sum())
    
    return


    # Start by generating the timestamps
    startTime = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTime = pd.Timestamp(year=2020, month=2, day=1, hour=0, minute=0, second=0)
    totMins = int((endTime - startTime).total_seconds() / 60.)


    # Generate intervals for each frequency
    mins = pd.interval_range(startTime, endTime, freq='min', closed='left')
    hours = pd.interval_range(startTime, endTime, freq='h', closed='left')
    days = pd.interval_range(startTime, endTime, freq='D', closed='left')
    months = pd.interval_range(startTime, endTime, freq='MS', closed='left')
    years = pd.interval_range(startTime, endTime, freq='YS', closed='left')

    # Put them in a dict for organization
    allTimes = {
        'hours': hours,
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

        # Each hour column should have 60 + 60 minutes
        if i >= hStart and i < hEnd:
            assert (adjMat[i].sum() == 60 + 60)
                
        
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
        if i >= hStart and i < hEnd:
            assert adjMat[i].sum() == 60*3

        # Each month column should have twice its number of minutes
        if i >= moStart and i < moEnd:
            # Get a copy of that month's timestamp
            moTs = allTimes['months'][i - moStart].left

            # Calculate the number of minutes it should have based on days,
            # then double to account for min and hour matching
            if moTs.month == 12:
                moMins = 60*24*31
            else:
                moMins = int((pd.Timestamp(year=moTs.year, month=moTs.month + 1, day=1) - moTs).total_seconds() / 60.)
            moMins *= 2

            if adjMat[i].sum() != moMins:
                print(adjMat[i].sum())
                print(moMins)
            assert adjMat[i].sum() == moMins


            

        



        







if __name__ == "__main__":


    main()








