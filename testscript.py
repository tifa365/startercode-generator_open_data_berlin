import pandas as pd
pd.options.mode.chained_assignment = None
pd.options.display.max_rows = 500
pd.options.display.max_seq_items = 500

import numpy as np
import requests
import json
import re
import glob
import os
from datetime import datetime
import time
import copy
from tqdm.notebook import tqdm

from bs4 import BeautifulSoup as bs4

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

print("Hello world... All import seem to be ok.")