from pathlib import Path

import pytest
import numpy as np

from tests.util import ResetForTest, TEST_GRAPH_NAME, HashWeight

# Gator imports the entities, so we don't need to import them here
from src.gator import * 


@pytest.mark.basic
def testGatorBasic():

    # Simple test for basic errors