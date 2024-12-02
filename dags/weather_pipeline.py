from airflow import DAG
from airflow.sensors.http_sensor import HttpSensor
from airflow.hooks.base import BaseHook
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta, timezone
import requests

postgres_database_conn_id = 'weather_data'
api_conn_id = 'weather_api_connection'


default_args = {
    'owner': 'airflow',
    'email': ['andrew.marfo@amalitech.com'],
    "start_date": datetime(2024, 12, 2),
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    "email_on_success": True,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}
weather_connection = BaseHook.get_connection(api_conn_id)
api_key = weather_connection.extra_dejson.get('api_key')

with DAG(
    'weather_data_pipeline',
    default_args=default_args,
    description='A dag to fetch and store daily weather data for Portland',
    schedule_interval=timedelta(minutes=5),
    start_date=datetime(2024, 11, 28),
    catchup=False,
) as dag:
    
    check_weather_api = HttpSensor(
        task_id='check_weather_api',
        http_conn_id=api_conn_id,
        endpoint=f'data/2.5/weather?q=Portland&APPID={api_key}',
        poke_interval=5,
        timeout=20,
    )

    # Fetching weather data for Portland from API and returning a few values
    def fetch_weather(ti):
        url = f"http://api.openweathermap.org/data/2.5/weather?q=Portland&APPID={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            ti.xcom_push(key="p_weather_data", value=data)
            return data
        else:
            raise Exception(f'Failed to fetch weather. Status code: {response.status_code}')
    
    fetch_weather_data = PythonOperator(
        task_id='fetch_weather_data',
        python_callable=fetch_weather,
        dag=dag,
    )

    # Transforming the data to a more suitable format and converting temperature from Kelvin to Fahrenheight
    def transform_data(ti):
        weather_data = ti.xcom_pull(key="p_weather_data", task_ids='fetch_weather_data')
        city = weather_data['name']
        temperature_k = weather_data['main']['temp']

        # Transforming temperature to Fahrenheit
        temperature_f = (temperature_k - 273.15) * 9/5 + 32
        pressure = weather_data['main']['pressure']
        humidity = weather_data['main']['humidity']
        timestamp = datetime.fromtimestamp(weather_data['dt'], timezone.utc)
        portland_weather_data = {
            'city': city,   
            'temperature': temperature_f,
            'pressure': pressure,
            'humidity': humidity,
            'timestamp': timestamp,
        }

        ti.xcom_push(key="p_weather_data", value=portland_weather_data)
        return portland_weather_data

    transform_weather_data = PythonOperator(
        task_id='transform_weather_data',
        python_callable=transform_data,
        dag=dag,
    )

    # Storing weather data in postgres database
    def load_to_postgres(ti):
        weather_data = ti.xcom_pull(key="p_weather_data", task_ids='transform_weather_data')     
        postgres_hook = PostgresHook(postgres_conn_id=postgres_database_conn_id)
        conn = postgres_hook.get_conn()
        cursor = conn.cursor()

        #Create table if it does not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_weather (
                city TEXT NOT NULL,
                temperature DOUBLE PRECISION NOT NULL,
                pressure INTEGER NOT NULL,
                humidity INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL
            );
        """)

        #Inserting transformed data into table
        insert_query = """
        INSERT INTO  daily_weather (city, temperature, pressure, humidity, timestamp)
        VALUES (%s, %s, %s, %s, %s);
        """
        cursor.execute(insert_query,( 
            weather_data['city'], 
            weather_data['temperature'], 
            weather_data['pressure'], 
            weather_data['humidity'],
            weather_data['timestamp'],
        ))

        conn.commit()
        cursor.close()

    load_weather_data = PythonOperator(
        task_id='load_weather_data',
        python_callable=load_to_postgres,
        dag=dag,
    )

# Dependencies
# check_weather_api >> 
fetch_weather_data >> transform_weather_data  >> load_weather_data
