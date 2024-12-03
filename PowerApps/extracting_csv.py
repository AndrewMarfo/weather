import pandas as pd


# Loading the YellowTaxi Data csv file
df = pd.read_csv('PowerApps/YelloTaxiData.csv')

new_yellow_taxi_data = df.head(100)

# saving the newly extracted data to a new csv file
new_yellow_taxi_data.to_csv('PowerApps/ExtractedYellowTaxiData.csv', index=False)
