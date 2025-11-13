
import pytest
import numpy as np
import random
import math

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import *



@pytest.mark.basic
def testSTBasic():

    # Use a smaller window since we'll have a lot of entries
    #random.seed(42)
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    #endTs = pd.Timestamp(year=2020, month=1, day=5, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2020, month=4, day=1, hour=0, minute=0, second=0)

    allSamplesDf, allAnswerKeysDf, countyGdf, gator = GenerateSTSample(startTs, endTs, TID.DAY)

    # Use the gator to aggregate them to daily by county

    # Get the result
    resDf = gator.SpatioTemporalEqualize(allSamplesDf, pd.DataFrame(countyGdf), TID.MONTH,
                                         GEID.ZCTA, GEID.COUNTY, ZCTA_COL, 'GISJOIN', 
                                         T_INTERVAL_COL, 'NONE', T_DATA_COL,
                                         'geometry', 'geometry',
                                         AggMethod.SUM, AggMethod.SUM,
                                         EdgeType.AREA, True, True)
    
    # Realistically, the only check we can do is total sum
    # Allow for some error since the spatial data isn't perfectly complete
    assert math.isclose(resDf[T_DATA_COL].sum(),
                        allAnswerKeysDf[T_DATA_COL].sum(),
                        rel_tol=.001)
    

@pytest.mark.basic
def testSTNoInterval():

    # Use time-series data (not already intervaled) to test
    # the gator's ability to make intervals

    # Generate the original sample
    #random.seed(42)
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    #endTs = pd.Timestamp(year=2020, month=1, day=5, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2020, month=4, day=1, hour=0, minute=0, second=0)

    allSamplesDf, allAnswerKeysDf, countyGdf, gator = GenerateSTSample(startTs, endTs, TID.HOUR)

    # Use the answer key as the sample; it emulates (hour)ly data
    resDf = gator.SpatioTemporalEqualize(allAnswerKeysDf, pd.DataFrame(countyGdf), TID.MONTH,
                                         GEID.ZCTA, GEID.COUNTY, ZCTA_COL, 'GISJOIN', T_ID_COL,
                                         'NONE', T_DATA_COL,
                                         AggMethod.SUM, AggMethod.SUM,
                                         EdgeType.AREA, True, True)
    
    # Best we can do is make sure the total sums match
    assert math.isclose(allSamplesDf[T_DATA_COL].sum(),
                        resDf[T_DATA_COL].sum(),
                        rel_tol=.001)
