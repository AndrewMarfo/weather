# weather

## Aiflow Pipeline

The airflow dag is located in the `airflow/dags` directory.
Screenshots of the various logs, database schemas , and other relevant information are located in the `AIRFLOW/Part 1 (Airflow Screenshots)` directory.

## Power Apps
DETaxiDemo solution file is located in the `airflow/PowerApps` directory.


### Email workflow
Attaching the Taxi Data csv file to the email and sending it to myself to trigger the flow was not working because of the file size of the attachment so I wrote a python script to get the first 100 rows of the data. I attached the extrated data csv file to the email and sent it to myself to trigger the workflow

Both the script and the extracted data is provided in the `PowerApps` directory

#### Notification 
Couldn't configure the notification (sending an email with an HTML 
table of the data profile to  mentor and instructor). This was because my access was restricted and i couldn't select the environment in which my solutions were.
Screenshots of the flow was provided though it couldn't be triggered triggered.