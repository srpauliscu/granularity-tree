

# Functions to generate temporal test data
import datetime
import pandas as pd


def main():

    # Start by generating the timestamps
    startTime = pd.Timestamp(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    endTime = pd.Timestamp(year=2020, month=12, day=31, hour=23, minute=59)
    timestamps = [startTime + datetime.timedelta(seconds=s) for s in range((endTime - startTime).seconds)]

    # Split them into their components
    allTimes = {
        'seconds': timestamps,
        'minutes': list({ts.floor('min'): None for ts in timestamps}.keys()),
        'hours': list({ts.floor('h'): None for ts in timestamps}.keys()),
        'days': list({ts.floor('d'): None for ts in timestamps}.keys()),
        'months': list({ts.floor('M'): None for ts in timestamps}.keys())
    }

    print(allTimes['months'])



if __name__ == "__main__":
    main()








