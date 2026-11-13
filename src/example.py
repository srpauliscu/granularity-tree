


# Use a dummy dataset mimicking the NTDAS data
# as a runnable example.

from pathlib import Path
import pandas as pd
import numpy as np
import random

from connecticutGraph import *
import ntdas
import math
from tqdm import tqdm

from gator import *

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('qt5agg')


def CreateNTDASDummy(dataDir: Path = Path('./data/ntdas'), nRows: int = 100000):

    # Arbitrarily select Oct 1, 2020 as the start date
    startTs = pd.Timestamp(year=2020, month=10, day=1, hour=0, minute=0, second=0)

    # We don't actually need to do a join to assign ZIP codes to roads,
    # as we are making up the ZIP codes


    '''
    For each row, generate:

    Random GISJOIN ID (in the Denver area)
    Random new starting timestamp (can use a timedelta) starting from a random day
    Random speed, reference speed
    Random travel time in minutes
    
    We can simply blank out historical, data density, and NPMRDS2, as
    those columns are not used.
    '''

    # Use the asked for number of rows to determine
    # the max allowed starting timestamp
    maxDays = int(2*math.log(nRows, 10) + 1)

    allRows = []

    for i in range(nRows):

        newRow = {}

        # Generate a random GISJOIN ID in Denver, which is just
        # the ZCTA with a leading G
        
        curZcta = random.sample(ntdas.DENVER_ZIPS, 1)[0]
        newRow['GISJOIN'] = f'G{curZcta}'

        # Generate a new starting timestamp
        newTd = pd.Timedelta(minutes=random.randint(1, maxDays*24*60))
        newRow['startTs'] = startTs + newTd

        # Generate a random speed based on timestamp to simualte
        # rush hour traffic between 7-9am and 4-6pm

        if ((newRow['startTs'].hour >= 7 and newRow['startTs'].hour <= 9) or
            (newRow['startTs'].hour >= 16 and newRow['startTs'].hour <= 18)):

            newRow['speed'] = np.random.normal(20, 8)

        else:
            newRow['speed'] = np.random.normal(70, 4)
            

        # Select a random reference speed
        # between realistic highway speed limits
        newRow['referenceSpeed'] = random.sample([55, 60, 65, 70], 1)[0]

        # Calculate the speed ration
        newRow['speedRatio'] = newRow['speed'] / newRow['referenceSpeed']

        # Select a random travel time in minutes,
        # with at least 1 minute of travel time
        travelTime = np.round(max(np.random.normal(17, 7), (3-1) * np.random.random_sample() + 1), 2)

        # Using the travel time and startTs, calculate newRow['endTs']
        newRow['endTs'] = newRow['startTs'] + pd.Timedelta(minutes=travelTime)

        # The interval will be generated after loading

        # Save out the new row
        allRows.append(newRow)

    
    # Make it into a dataframe
    resDf = pd.DataFrame(allRows)

    # Save out the dataframe
    resDf.to_csv(dataDir / Path('dummySample.csv'), index=False)




def RunSampleAnalysis(dataFile: Path = Path('./data/ntdas/dummySample.csv'),
                      graphDir: Path = Path('./graphs')):

    # Generate a logger for this example
    logger = logging.getLogger('Example')
    logging.basicConfig(filename="./logs/example.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Load in the data
    dataDf = pd.read_csv(dataFile, header=0)

    # Convert from string to datetime objects
    dataDf['startTs'] = pd.to_datetime(dataDf['startTs'])
    dataDf['endTs'] = pd.to_datetime(dataDf['endTs'])

    # Generate actual interval objects
    dataDf['interval'] = dataDf.apply(lambda x: pd.Interval(x['startTs'], x['endTs']), axis=1)

    # Load in the pre-made graph
    # NOTE: see allEval.STEval() to see how the graph is built
    graph = GranularityGraph('STEvalGraph', Path('./logs/exampleGraph.log'))

    lStatus = graph.LoadGraph(graphDir)
    if lStatus == Status.NOTEXISTS:
        msg = f"Please ensure the graph files exist in {graphDir}"
        logger.error(msg)
        raise RuntimeError(msg)
    
    if lStatus != Status.SUCCESS:
        msg = f"There was an error loading the graph."
        logger.error(msg)
        raise RuntimeError(msg)


    #for nid in graph.indexMap:
    #    print(nid.id)
    #quit()

    # Load in the school districts
    sdGdf = LoadShapefile(Path('./data/tiger'), 'school')

    # We only need CO districts
    sdGdf = sdGdf[sdGdf['STATEFP'] == ntdas.CO_FIPS]

    # Get a gator
    gator = Gator(graph, Path('./logs/STEvalGator.log'))

    # Do the scaling
    msg = "Starting example scaling operation..."
    print(msg)
    logger.info(msg)

    resDf = gator.SpatioTemporalEqualize(dataDf, sdGdf,
                                         TID.HOUR, GEID.ZCTA, GEID.SD,
                                         'GISJOIN', 'GISJOIN', 'interval',
                                         None, 'speedRatio', None, None,
                                         AggMethod.MEAN, AggMethod.MEAN, EdgeType.AREA,
                                         True, True)
    
    # Swap the ordering of the multiindex
    resDf = resDf.swaplevel().sort_index(level=0, inplace=False)
    
    dayOrder = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    # Plot the speeds for a random GISJOIN ID
    for lv, group in resDf.groupby(level=0):

        # Generate the figure
        curFig, ax = plt.subplots(1, 1, figsize=(15,9))

        # Get rid of the GISJOIN as an axis label
        group = group.droplevel(0)

        # Group and plot each day as separate lines
        days = group.groupby(group.index.get_level_values(0).day_name())
        legendList = []
        handleList = []
        for day, dayGroup in days:

            if day == "Saturday" or day == "Sunday":
                # Skip weekends
                continue

            # Plot by hour of the day
            dayGroup.set_index(dayGroup.index.get_level_values(0).hour, inplace=True)
            dayGroup.plot(kind='line', rot=0, ax=ax, linewidth=2.5)

            # Save handles and labels to fix legend later
            handleList.append(ax.get_lines()[-1])
            legendList.append(day)

        # Set labels
        ax.set_xlabel('Hour of Day', fontsize=40)
        ax.set_ylabel('Ratio of Recorded to\nReference Speed', fontsize=40)

        if lv in ntdas.DENVER_SD_IDS:
            ax.set_title(ntdas.DENVER_SD_IDS[lv], fontsize=40)

            # Set limits for specific graphs
            if 'Denver' in ntdas.DENVER_SD_IDS[lv]:
                ax.set_ylim(bottom=0.5, top=1.0)
            elif 'Gilpin' in ntdas.DENVER_SD_IDS[lv]:
                ax.set_ylim(bottom=0.6, top=1.2)
        
        else:
            ax.set_title(f'SD {lv}', fontsize=40)

        # Fix tick sizes and fonts
        ax.tick_params(axis='x', which='major', labelsize=28)
        ax.tick_params(axis='y', which='major', labelsize=28)
        ax.tick_params(axis='x', which='minor', labelsize=23)
        ax.tick_params(axis='both', length=12, width=3)

        # Reorder the legend labels
        newHandleList = []
        for d in dayOrder:
            if d not in legendList:
                continue
            curI = legendList.index(d)
            newHandleList.append(handleList[curI])


        # Fix the legend label
        ax.legend(newHandleList, dayOrder, fontsize=28, loc='upper center')

        # Add lines for the times
        xticks = ax.get_xticks()
        ymin, ymax = ax.get_ylim()
        for i, xt in enumerate(xticks):
            if i==0:
                continue
            ax.vlines(xt, ymin-.2, ymax+.2, color='gray', linestyle=':', linewidth=2)

        # Fix overlapping labels
        plt.tight_layout()
        curFig.tight_layout()
        curFig.set_tight_layout(True)


        # Comment out to display all graphs, though it
        # may overload and crash.
        break

    plt.show()






if __name__ == "__main__":
    
    # Uncomment to generate new dummy data
    #CreateNTDASDummy()

    # Run the sample analysis
    RunSampleAnalysis()





