

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
FACTORCOL = '_value_factor_'
ADJUSTEDENERGY = '_adjusted_energy_'
INTERVALCOL = '_time_interval_'


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


def LoadCSUData(filepath: Path, nrows: int = 1000) -> tuple[pd.DataFrame, list]:

    # We don't need all of the columns
    cols = ['Station Name', 'MAC Address', 'Start Date',
            'Start Time Zone', 'End Date', 'End Time Zone',
            'Total Duration (hh:mm:ss)', 'Energy (kWh)', 'City', 'State/Province',
            'Postal Code', 'Country', 'Latitude', 'Longitude',
            'Driver Postal Code', 'User ID', 'County']
    
    # Allow for a smaller sample for testing
    csuDf = pd.read_csv(filepath, usecols=cols, low_memory=False, nrows=nrows)

    # Make sure we have the right data types
    fmt = "%m/%d/%Y %H:%M"
    csuDf['Start Date'] = pd.to_datetime(csuDf['Start Date'], format=fmt)
    csuDf['End Date'] = csuDf.apply(ConvertEndDate, args=(fmt,), axis=1)

    return csuDf, cols


def main(load: bool = True, overwrite: bool = True, relTol: float = .00001):

    # We don't actually need a graph object since the edges
    # are calculated dynamically

    # Load in the charging station data
    csuDf, cols = LoadCSUData(Path('./data/temporal/EVChargingStationUsage.csv'), 1000)

    # Setup a column of intervals
    csuDf[INTERVALCOL] = csuDf.apply(lambda x: pd.Interval(left=x['Start Date'], right=x['End Date']), axis=1)

    # Initialize the gator
    gator = Gator(None, Path('./logs/csuGator.log'))

    # Use the gator to get hourly data
    resDf = gator.TemporalEqualize(csuDf, TID.HOUR, INTERVALCOL, 'Energy (kWh)', AggMethod.SUM)

    print(csuDf['Energy (kWh)'].sum())
    print(resDf['Energy (kWh)'].sum())

    # Sanity check: the sum of the data columns should be the same
    assert math.isclose(csuDf['Energy (kWh)'].sum(), resDf['Energy (kWh)'].sum())

    # Plot by hour of day
    resDf['Hour'] = resDf.index.hour

    resDf.plot(x='Hour', y='Energy (kWh)', kind='scatter')
    plt.show()

    print('Yay!')








def manualMain(load: bool = True, overwrite: bool = True, relTol: float = .00001):

    # Folder information
    graphsDir = Path("./graphs")

    # Load up the graph
    graph = GranularityGraph('chargingStationUsageGraph', Path('./logs/chargingStationUsageGraph.log'))
    if load:
        # This will run even if we don't have a save file
        graph.LoadGraph(graphsDir)


    # Load the data
    csuDf, cols = LoadCSUData(Path('./data/temporal/EVChargingStationUsage.csv'), 1000)


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
            newRow[FACTORCOL] = overlap / ((row['End Date'] - row['Start Date']).total_seconds() / 60.)

            # Calculate the energy used in that hour
            newRow[ADJUSTEDENERGY] = newRow[FACTORCOL] * newRow['Energy (kWh)']

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




if __name__ == "__main__":

    #manualMain()
    main()








