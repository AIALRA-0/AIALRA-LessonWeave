import sys
from report import readings, means

if __name__ == "__main__":
    for station, value in means(readings(sys.argv[1])):
        print(f"{station}: {value:.1f} C")
