from airflow import DAG
from airflow.operators.http_operator import SimpleHttpOperator
from airflow.sensors.http_sensor import HttpSensor
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import requests
import json
from pytz import timezone
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv('API_KEY')

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

with DAG(
    'weather_data_pipeline',
    default_args=default_args,
    description='A dag to fetch and store daily weather data for Portland',
    schedule_interval='@daily',
    start_date=datetime(2024, 12, 2),
    catchup=False,
) as dag:
    
    check_weather_api = HttpSensor(
        task_id='check_weather_api',
        http_conn_id=api_conn_id,
        endpoint='data/2.5/weather?q=Portland&appid={{ var.value.api_key }}',
        response_check=lambda response: response.status_code == 200,
        poke_interval=5,
        timeout=20,
    )

    # Fetching weather data for Portland from API and returning a few values
    def fetch_weather(ti):
        url = f"http://api.openweathermap.org/data/2.5/weather?q=Portland&APPID={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            portland_weather_data = {
                'id': data['id'],
                'city': data['name'],   
                'temperature': data['main']['temp'],
                'pressure': data['main']['pressure'],
                'humidity': data['main']['humidity'],
            }
            ti.xcom_push(key="p_weather_data", value=portland_weather_data)
            return portland_weather_data
        else:
            raise Exception(f'Failed to fetch weather. Status code: {response.status_code}')
    
    fetch_weather_data = PythonOperator(
        task_id='fetch_weather_data',
        python_callable=fetch_weather,
        dag=dag,
    )

    # Transforming the data to a more suitable format (Temperature)
    def transform_data(ti):
        weather_data = ti.xcom_pull(key="p_weather_data", task_ids='fetch_weather_data')

        # Transforming temperature to Fahrenheit
        weather_data['temperature'] = (weather_data['temperature'] - 273.15) * 9/5 + 32


        ti.xcom_push(key="p_weather_data", value=weather_data)
        return weather_data

    transform_weather_data = PythonOperator(
        task_id='transform_weather_data',
        python_callable=transform_data,
        dag=dag,
    )

    create_table = PostgresOperator(
        task_id='create_table',
        postgres_conn_id=postgres_database_conn_id,
        sql="""
        CREATE TABLE IF NOT EXISTS weather_data.daily_weather (
            id INTEGER PRIMARY KEY,
            city TEXT NOT NULL,
            temperature DOUBLE PRECISION NOT NULL,
            pressure INTEGER NOT NULL,
            humidity INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        dag=dag,
    )

    # Storing weather data in postgres database
    def load_to_postgres(ti):
        weather_data = ti.xcom_pull(key="p_weather_data", task_ids='transform_weather_data')
        if not weather_data:
            raise ValueError("Weather data not found")
            
        postgres_hook = PostgresHook(postgres_conn_id=postgres_database_conn_id)
        conn = postgres_hook.get_conn()
        cursor = conn.cursor()

        #Create table if it does not exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_weather (
            id INTEGER PRIMARY KEY,
            city TEXT NOT NULL,
            temperature DOUBLE PRECISION NOT NULL,
            pressure INTEGER NOT NULL,
            humidity INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        #Inserting transformed data into table
        insert_query = """
        INSERT INTO  weather_data.daily_weather (id, city, temperature, pressure, humidity)
        VALUES (%s, %s, %s, %s, %s);
        """
        cursor.execute(insert_query,(
            weather_data['id'], 
            weather_data['city'], 
            weather_data['temperature'], 
            weather_data['pressure'], 
            weather_data['humidity']
        ))

        conn.commit()
        cursor.close()

    load_weather_data = PythonOperator(
        task_id='load_weather_data',
        python_callable=load_to_postgres,
        dag=dag,
    )

# Dependencies
check_weather_api >> fetch_weather_data >> transform_weather_data >>  create_table >> load_weather_data
