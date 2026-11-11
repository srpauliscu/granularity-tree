
# Good sources for battery charging profiles
#https://ieeexplore.ieee.org/abstract/document/5535237
#https://dl.acm.org/doi/full/10.1145/3565268
#https://ieeexplore.ieee.org/abstract/document/6360973

# Charging speeds:
# https://www.transportation.gov/rural/ev/toolkit/ev-basics/charging-speeds


''' Process:

Generate 2 profiles:
1 linear, to represent even charge distribution
1 to mimic CC/CV, the standard for Li-ion batteries

Use Figure 2 from the 2 document for realistic numbers

Use both of them to generate test data of random time intervals
starting and ending at random SoCs to get power usage per minute

Then, aggregate both of them to the hour and daily levels and compare the results


According to the charging speed data, let's assume that:
Level 1 chargers take ~45  hours to go from 0-80%
Level 2 takes ~7 hours to go 0-80%
Level 3 takes ~ 40 minutes for 0-80%

for a 60kWh battery

'''

from typing import Literal
from collections.abc import Callable
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import scipy.integrate as integrate
from tqdm import tqdm
import pickle

matplotlib.use('qt5agg')


from gator import *
from allEval import FIG_DPI, FIG_LABEL_FONT_SIZE, FIG_MAJOR_AXIS_TICK_SIZE, FIG_MINOR_AXIS_TICK_SIZE,\
FIG_SIZE, FIG_SIZE_FACTOR, FIG_TITLE_FONT_SIZE


# Power functions at different levels for integration

def ConstantPower(level: Literal[1,2,3]) -> Callable[[float], float]:

    # Constant power draw = even distribution over session
    # Naive assumption model

    match level:

        case 1:
            def CPL1(t: float) -> float:
                # 45 hours to get to 80% of 60
                return (60*.8*1000*60) / (45*60.)
            
            return CPL1

        case 2:
            def CPL2(t: float) -> float:
                # 7 hours to get to 80% of 60
                return (60*.8*1000*60) / (7*60.)

            return CPL2

        case 3:
            def CPL3(t: float) -> float:
                # 40 mins to get to 80%
                return (60 * .8 * 1000 * 60) / 40.
            
            return CPL3




# Tau = battery's time constant, which varies widely, so add it
# as a parameter

def CCCVPower(level: Literal[1,2,3], tau: float = 100.) -> Callable[[float], float]:

    # Constant current/constant voltage profile

    '''
    Each level is a piecewise function to mimic CCCV,
    using the provided cutoff (except L1).  Our data is based on
    0-80, and 80% is a standard cutoff, so we'll use 80%,
    which we already have the times for.

    According to the .gov source, let's just use the average
    voltage/power draw to calculate the constants for CC and CV
    '''

    '''
    
    We're going to use a parabola for the rising voltage (judged by look)
    and exponential for current decay (from the paper)

    Parabola
    y = a(x-h)^2 + k
    y-intercept = a*h^2 + k
    vertex (h, k)

    
    
    '''

    match level:

        case 1:

            # Note: level 1 is often household charging, so assume ~constant 120V
            # for the entire session
            def CCCVL1(t: float) -> float:
                vMax = 120.
                cutoff = 45*60
                aMax = (60*.8*1000*60) / (vMax * cutoff)
                
                if t < (cutoff):
                    # CC
                    voltage = vMax
                    current = aMax


                else:
                    # CV
                    current = aMax * np.exp(-(t - cutoff) / tau)
                    voltage = vMax
                    
                return voltage*current
            
            return CCCVL1


        case 2:
            def CCCVL2(t: float) -> float:
                vMax = 240.
                cutoff = 7*60
                aMax = 19000 / vMax
                # Calculate what the constant current should be knowing what the energy
                # total is at the cutoff (80% of 60)

                k = vMax
                yInt = 10
                a = (yInt - vMax) / (cutoff**2)

                voltage = a*(t - cutoff)**2 + k
                tMax = cutoff

                # Integral of voltage
                vInt = (1./3) * a * (tMax**3) - a*cutoff*(tMax**2) + a*(cutoff**2)*tMax + k*tMax + yInt
                
                current = (60*.8*1000*60) / (vInt)



                if t <= cutoff:
                    # Just use the already calculated values
                    pass

                else:

                    # CV
                    voltage = vMax

                    # Re-calculate where the current should be
                    current = current * np.exp(-(t - cutoff) / tau)

                return voltage*current

            return CCCVL2

        case 3:
            def CCCVL3(t: float) -> float:
                # Same as L2, just different numbers
                vMax = (400 + 1000) / 2.
                aMax = ((50+350) * 1000 / 2.) / vMax
                cutoff = 40

                # Calculate what the constant current should be knowing what the energy
                # total is at the cutoff (80% of 60)

                k = vMax
                yInt = 100
                a = (yInt - vMax) / (cutoff**2)

                voltage = a*(t - cutoff)**2 + k
                tMax = cutoff

                # Integral of voltage
                vInt = (1./3) * a * (tMax**3) - a*cutoff*(tMax**2) + a*(cutoff**2)*tMax + k*tMax + yInt
                
                current = (60*.8*1000*60) / (vInt)



                if t <= cutoff:
                    # Just use the already calculated values
                    pass

                else:

                    # CV
                    voltage = vMax

                    # Re-calculate where the current should be
                    current = current * np.exp(-(t - cutoff) / tau)

                return voltage*current
            
            return CCCVL3


PROFILE_GENERATORS = {'naive': ConstantPower,
                      'cccv': CCCVPower}

# Taus to get matching total energy
TAUS = {1: -1,
        2: 130,
        3: 15.5}

START_TS = pd.Timestamp(year=2019, month=10, day=1, hour=0, minute=0, second=0, tz='US/Pacific')
END_TS = pd.Timestamp(year=2019, month=10, day=10, hour=0, minute=0, second=0, tz='US/Pacific')
NUM_ROWS = 100000

# Time cutoffs to reach 80% charge from 0,
# in minutes
CUTOFF80 = {1: 45*60,
            2: 7*60,
            3: 40}

def GenerateInstances(outDir: Path, powerLevels: list[Literal[1,2,3]]):

    print('\nGenerating instances...')

    # Generate random charging instances for sensitivity testing
    
    # Generate each power level separately
    for pl in powerLevels:

        print(f'\nPower level {pl}:')

        # Generate the appropriate power curves
        curProfiles = []
        for ppk in PROFILE_GENERATORS:
            
            if 'cccv' in ppk:
                # Pass in the correct tau
                curProfiles.append(PROFILE_GENERATORS[ppk](pl, TAUS[pl]))

            else:
                curProfiles.append(PROFILE_GENERATORS[ppk](pl))

        
        # Use the start and end ts to generate a bunch of random instances
        maxTd = int((END_TS - START_TS).total_seconds())
        allRows = []
        for i in tqdm(range(NUM_ROWS)):

            # Get a random timedelta between 0 and maxTd
            curTd = np.random.randint(0, maxTd)

            # Make this the current starting point
            curStartTs = START_TS + pd.Timedelta(seconds=curTd)

            # Generate a random starting SoC (basically, a t0)
            # between 0 and 70%, based on the power level
            curT0 = pd.Timedelta(minutes=np.random.randint(0, int(.70 * CUTOFF80[pl])))

            # Generate a random duration, between 5 minutes and 8 hours
            curLen = pd.Timedelta(seconds=np.random.randint(5*60, 8*60*60))

            # Cut off the session if 80% is reached
            cutoffP = 1.25#.80
            tMax = pd.Timedelta(minutes=int(cutoffP*CUTOFF80[pl]))
            if curT0 + curLen > tMax:
                curLen = tMax - curT0

            # Calculate how much total energy is provided using each profile
            # using the start time and the duration
            actualT0 = curT0.total_seconds() / 60.
            actualT1 = (curT0 + curLen).total_seconds() / 60.

            curRow = {'vid': i,
                      'startTs': curStartTs,
                      'endTs': curStartTs + curLen,
                      'tsInterval': pd.Interval(curStartTs, curStartTs+curLen)}            
            for ppk in PROFILE_GENERATORS:
                # Don't forget to translate from WMins to kWh
                curEnergy = integrate.quad(PROFILE_GENERATORS[ppk](pl), actualT0, actualT1)[0] / (1000*60)

                # Add in a little random noise for good measure
                a = .95
                b = 1.05
                curRow[ppk] = curEnergy * ((b - a) * np.random.random() + a)

            # Save the row out
            allRows.append(curRow)
        
        # Turn the rows into a dataframe
        outDf = pd.DataFrame(allRows)

        # Cache the dataframe on disk
        outDf.to_csv(outDir / Path(f'powerLevel{pl}.csv'), index=False)
            


def PlotPowerProfiles(powerLevels: list[Literal[1,2,3]]):

    for pl in powerLevels:

        # Get functions for naive and CCCV profiles
        # This is in W/min
        nProfile = ConstantPower(pl)

        # Use the tau that gets the total energy usage of
        # each profile to be roughly equivalent
        cccvProfile = CCCVPower(pl, tau=TAUS[pl])

        # Plot them for now
        allX = np.linspace(0, int(CUTOFF80[pl]*1.25), num=5000)

        ny = []
        cccvy = []
        for x in allX:
            ny.append(nProfile(x))
            cccvy.append(cccvProfile(x))


        fig, ax = plt.subplots()
        plt.plot(allX, ny)
        plt.plot(allX, cccvy)
        
        plt.title(f'Power level {pl}')

        ni = integrate.quad(nProfile, min(allX), max(allX))[0] / (1000*60)
        cccvi = integrate.quad(cccvProfile, min(allX), max(allX))[0] / (1000*60)

        print(ni)
        print(cccvi)





    plt.show()


def CompareProfiles(dataDir: Path, powerLevels: list[Literal[1,2,3]]):

    print('\nComparing profiles...')

    # We can use one Gator object for the whole thing
    gator = Gator(None, Path('./logs/sensitivityTesting.log'))

    startTsCol = 'startTs'
    endTsCol = 'endTs'
    intervalCol = 'tsInterval'
    resIdCol = 'destId__'


    # Compare each power level separately
    for pl in powerLevels:

        # Load the corresponding sample data
        curDf = pd.read_csv(dataDir / Path(f'powerLevel{pl}.csv'))#, nrows=1000)

        # We need to generate the actual interval objects
        curDf[startTsCol] = pd.to_datetime(curDf[startTsCol])
        curDf[endTsCol] = pd.to_datetime(curDf[endTsCol])

        # We need to convert the interval column from string to pd.Interval
        curDf[intervalCol] = curDf.apply(lambda x: pd.Interval(x[startTsCol], x[endTsCol]), axis=1)

        # Run the gator thrice for each power profile: minutes, hours, days
        # Pre-populate to appease the IDE
        curResDfs = {#TID.MINUTE: pd.DataFrame(),
                     TID.HOUR: pd.DataFrame(),
                     TID.DAY: pd.DataFrame()
                     }
        
        for timeType in curResDfs:
            for ppk in PROFILE_GENERATORS:

                # Do the aggregation
                curResDf = gator.TemporalEqualize(curDf, timeType, intervalCol,
                                                ppk, AggMethod.MEAN)
                
                # Add the results to the new dataframe, OR
                # join them with previous results
                if len(curResDfs[timeType]) == 0:
                    curResDfs[timeType] = curResDf
                else:
                    curResDfs[timeType] = curResDfs[timeType].merge(curResDf, how='inner', on=resIdCol)
    

            # Now, calculate pairwise difference for all profile types
            curComparisonDf = curResDfs[timeType]
            for ppk0 in PROFILE_GENERATORS:
                for ppk1 in PROFILE_GENERATORS:

                    # Don't need to self compare
                    if ppk0 == ppk1:
                        continue

                    # Skip pairs we've already done
                    if (f'{ppk0}-{ppk1}' in curComparisonDf.columns or
                        f'{ppk1}-{ppk0}' in curComparisonDf.columns):
                        continue

                    # Do a simple subtraction
                    curComparisonDf[f'{ppk0}-{ppk1}'] = curComparisonDf[ppk0] - curComparisonDf[ppk1]

            # Plot the comparisons?
            
            fig, ax = plt.subplots(figsize=FIG_SIZE)
            for c in curComparisonDf.columns:
                
                # Skip the non-result columns
                if (c == resIdCol or
                    c in PROFILE_GENERATORS):
                    continue

                curComparisonDf.plot(y=c, ax=ax, lw=2)

                # Beautify
                plt.xlabel('Date (day)', fontsize=FIG_LABEL_FONT_SIZE, labelpad=-35)
                plt.ylabel('Difference (kWh)', fontsize=FIG_LABEL_FONT_SIZE)
                plt.title(f'Power Level {pl}, {timeType.name}', fontsize=FIG_TITLE_FONT_SIZE)

                ax.tick_params(axis='x', which='both', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
                ax.tick_params(axis='y', which='both', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)

                plt.legend(fontsize=FIG_MAJOR_AXIS_TICK_SIZE, loc='upper center')

            # Save out the plots
            outDir = dataDir / Path(f'powerLevel{pl}')
            if not outDir.exists():
                outDir.mkdir(parents=True)
            
            plt.savefig(outDir / Path(f'{timeType.name}.svg'), dpi=300)
            plt.savefig(outDir / Path(f'{timeType.name}.png'), dpi=300)

            with open(outDir / Path(f'{timeType.name}.pickle'), 'wb') as f:
                pickle.dump(fig, f)






    plt.show()



if __name__ == "__main__":
    
    powerLevels: list[Literal[1,2,3]] = [1,2,3]

    dataDir = Path.cwd() / Path('./data/sensitivitySamples')

    GenerateInstances(dataDir, powerLevels)

    #PlotPowerProfiles(powerLevels)

    CompareProfiles(dataDir, powerLevels)

    

