


from enum import Enum, StrEnum


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

    MEAN = "Mean"   # Weighted mean
    MEDIAN = "Median"   # Weighted median
    SUM = "Sum"

class DeAggMethod(StrEnum):

    """
    Enumeration that defines what deaggregation operations are supported.
    """

    DISTRIBUTE = "Distribute"
    COPY = "Copy"


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
    Enumeration to define the various temporal units.
    """

    # Primary time units
    DECADE = "Decade"
    YEAR = "Year"
    MONTH = "Month"
    WEEK = "Week"
    DAY = "Day"
    HOUR = "Hour"
    MINUTE = "Minute"
    SECOND = "Second"

    # Secondary time units
    WORKWEEK = "Workweek" # Monday-Friday, inclusive
    MORNING = "Morning" # Times from 00:00 to 11:59
    AFTERNOON = "Afternoon" # Times from 12:00 to 23:59

    # Could include peak power hours, but those can change in a given location,
    # so might be difficult