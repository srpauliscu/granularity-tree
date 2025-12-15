


from enum import Enum, StrEnum
import numpy as np
import math


# Global delimeter to denote different entities in an ID chain
ENTITY_DELIMETER = '_;_'



class Status(Enum):
    """
    Enumeration to provide more information when performing graph operations.
    """
    ERROR = 0
    SUCCESS = 1
    EXISTS = 2
    NOTEXISTS = 3


class EdgeType(StrEnum):
    
    """
    Enumeration that specifies what methods of sectioning
    are currently supported (e.g. by population, by area, etc.)    
    """

    AREA = "Area"
    POPULATION = "Population"


class AggMethod(StrEnum):

    """
    Enumeration that defines what aggregation operations are supported.
    """

    COUNT = "Count"
    MEAN = "Mean"   # Weighted mean
    MEDIAN = "Median"   # Weighted median
    SUM = "Sum"

    KRIGING = "Kriging" # Best linear unbiased predictor (BLUP)

class DeAggMethod(StrEnum):

    """
    Enumeration that defines what deaggregation operations are supported.
    """

    DISTRIBUTE = "Distribute"
    COPY = "Copy"

    KRIGING = "Kriging" # BLUP

class VariogramModel(Enum):

    """
    Enumeration that defines currently accepted models for fitting
    the semivariogram for kriging.    
    """
    GAUSSIAN = lambda x,a,b,c: np.where(x <=.0001, 0, 1-a*np.exp(-(((x-b)**2)/(2.*c**2))))
    EXPONENTIAL = lambda x,a,b,c: np.where(x <= .0001, 0, a*np.exp(b*x) + c)
    LINEAR = lambda x,a,b,c: np.where(x <= .0001, 0, np.where(x <= a, c + b*(x / a), c + b))
    SPHERICAL = lambda x,a,b,c: np.where(x <= .0001, 0, np.where(x <= a, c + b*((3*x)/(2*a) - .5*((x**3)/(a**3))), c + b))


class GEID(StrEnum):

    """
    Enumeration to define U.S. geographic entities.
    """

    ### ID only used in testing ###
    TEST = 'Test'

    ### Primary IDs ###
    NATION = 'Nation'
    REGION = 'Region'
    DIVISION = 'Division'
    STATE = 'State'
    COUNTY = 'County'
    TRACT = 'Tract'
    BLOCKGROUP = 'BlockGroup'
    BLOCK = 'Block'

    ### Secondary IDs ###

    # Children of Nation
    ZCTA = 'ZIPCodeTabulationArea' 
    UA = 'UrbanArea'
    CBSA = 'CoreBasedStatisticalArea'
    
    # Children of State
    SD = 'SchoolDistrict'
    CD = 'CongressionalDistrict'
    UGA = 'UrbanGrowthArea'
    SLD = 'StateLegislativeDistrict'
    PUMA = 'PublicUseMicrodataArea'
    PLACE = 'Place'
    CITY = 'City'

    # Children of County
    VD = 'VotingDistrict'
    TAZ = 'TrafficAnalysisZone'
    CS = 'CountySubdivision'

    # Children of CountySubdivision
    SCD = 'SubminorCivilDivision'

    # Misc
    AIANNHA = "AmericanIndianAlaksaNativeNativeHawaiianArea"
    ZIP = "ZIP"

class TID(StrEnum):

    """
    Enumeration to define the various temporal units. Use Pandas time frequency
    strings for compability.
    
    See https://pandas.pydata.org/docs/user_guide/timeseries.html#offset-aliases
    """

    # Primary time units
    YEAR = "Y"
    MONTH = "M"
    WEEK = "W"
    DAY = "D"
    HOUR = "h"
    MINUTE = "min"
    SECOND = "s"

    # Secondary time units
    WORKWEEK = "Workweek" # Monday-Friday, inclusive
    MORNING = "Morning" # Times from 00:00 to 11:59
    AFTERNOON = "Afternoon" # Times from 12:00 to 23:59

    # Could include peak power hours, but those can change in a given location,
    # so might be difficult

# Sometimes we need the full name of the time unit
TID_TO_STRING = {

    TID.YEAR: 'years',
    TID.MONTH: 'months',
    TID.DAY: 'days',
    TID.HOUR: 'hours',
    TID.MINUTE: 'minutes',
    TID.SECOND: 'seconds'
}

# The Grouper sometimes reqiures different strings that the other functions
TID_TO_PERIOD = {

    TID.YEAR: 'YS',
    TID.MONTH: 'MS',
    TID.WEEK: 'W',
    TID.DAY: 'D',
    TID.HOUR: 'h',
    TID.MINUTE: 'min',
    TID.SECOND: 's'
}