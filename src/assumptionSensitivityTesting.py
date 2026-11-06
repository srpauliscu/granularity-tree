
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
Level 1 chargers take ~45 hours to go from 0-80%
Level 2 takes ~7 hours to go 0-80%
Level 3 takes ~ 40 minutes for 0-80%


'''

from typing import Literal
from collections.abc import Callable


# Power functions at different levels for integration

def LinearPower(level: Literal[1,2,3]) -> Callable[[float], float]:
    # Assume completely linear from 0-100,
    # with coefficients based on the level

    match level:

        case 1:
            def LPL1(t: float) -> float:
                return ((.8) / (45*60)) * t
            
            return LPL1

        case 2:
            def LPL2(t: float) -> float:
                return ((.8) / (7*60)) * t
            
            return LPL2

        case 3:
            def LPL3(t: float) -> float:
                return ((.8) / (40)) * t
            return LPL3
            

def CCCVPower(level: Literal[1,2,3]) -> Callable([float], float):

    # Constant current/constant voltage profile

    '''
    Each level is a piecewise function to mimic CCCV,
    using the provided cutoff.  Our data is based on
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
            def CCCVL1(t: float) -> float:
                vMax = 120.
                aMax = 1000. / vMax
                
                if t < (45*60):
                    # CC
                    current = aMax
                    voltage = 

                    pass

                else:
                    # CV
                    current = 
                    voltage = 120
                    pass


        case 2:
            def CCCVL1(t: float) -> float:
                if t < (7*60):
                    # CC
                    pass

                else:
                    # CV
                    pass

        case 3:
            def CCCVL1(t: float) -> float:
                if t < (40):
                    # CC
                    pass

                else:
                    # CV
                    pass


def LinearProfile(t0, t1, level: Literal[1,2,3]):

    


# Given an initial SoC, an ending SoC, and a duration,
# generate by-the-minute power draw (kW = A*V)

def GeneratePowerDraw(batProfile, startSoC, endSoC, duration) -> float:

    # We can do this recursively, with the base case being 1 minute
    if duration == 1:




