
import pytest
import numpy as np
import random
import math

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import *



@pytest.mark.basic
def testSTBasic():

    load = True
    overwrite = True

    # Use a smaller window since we'll have a lot of entries
    random.seed(42)
    startTs = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTs = pd.Timestamp(year=2020, month=1, day=5, hour=0, minute=0, second=0)
    #endTs = pd.Timestamp(year=2020, month=4, day=1, hour=0, minute=0, second=0)

    allSamplesDf, allAnswerKeysDf, countyGdf, gator = GenerateSTSample(startTs, endTs, TID.HOUR)

    # Use the gator to aggregate them to daily by county

    # Get the result
    resDf = gator.SpatioTemporalEqualize(allSamplesDf, pd.DataFrame(countyGdf), TID.DAY,
                                         GEID.ZCTA, GEID.COUNTY, ZCTA_COL, 'GISJOIN', 
                                         T_INTERVAL_COL, 'NONE', T_DATA_COL,
                                         AggMethod.SUM, AggMethod.SUM,
                                         EdgeType.AREA, True, True)
    
    print(resDf)
    assert False
