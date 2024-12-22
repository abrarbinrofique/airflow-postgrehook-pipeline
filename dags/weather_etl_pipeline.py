from airflow import DAG
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.decorators import task
from airflow.utils.dates import days_ago


#Latitude and ongitude for desired location,here i took DHAKA
Latitude='23.8103'
Longitude= '90.4125'

POSTGRES_CONN_ID='supabase_postgre'
API_CONN_ID='open_meteo_api'

default_args={

    'owner':'airflow',
    'start_date':days_ago(1)
}

##Our DAG

with DAG(dag_id='weather_et_pipeline',default_args=default_args,
         schedule_interval='@daily',
         catchup=False) as dags:
    @task()
    def extract_weather_data():
        """
        Extract weather data from open mateo api using Airflow connection
        """ 
        #Use http hook to get the weather data
        http_hook=HttpHook(http_conn_id=API_CONN_ID,method='GET')
        
        ##Build the API endpoint
        #https://api.open-meteo.com/v1/forecast?latitude=23.8103&longitude=90.4125&current_weather=true
        
        endpoint=f'v1/forecast?latitude={Latitude}&longitude={Longitude}&current_weather=true'
        
        ##Make the request via the http hook
        response=http_hook.run(endpoint)


        if response.status_code==200:
            return response.json()
        else:
            raise Exception(f"failed to fetch weather data:{response.status_code}")
        




    @task()
    def transform_data(weather_data):
        """
        Transform the extract weather data
        """
        current_weather=weather_data['current_weather']
        transform_weather_data={
            'latitude':Latitude,
            'longitude':Longitude,
            'temperature':current_weather['temperature'],
            'windspeed':current_weather['windspeed'],
            'winddirection':current_weather['winddirection'],
            'weathercode':current_weather['weathercode']
        }

        return transform_weather_data
    
    
    
    
    @task()
    def load_weather_data(transform_weather_data):

        """
        Load transform data into postgresql
        """
        pg_hook=PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn=pg_hook.get_conn()
        cursor=conn.cursor()

        ##create db tabe if doesn't exist

        cursor.execute("""
          
          CREATE TABLE IF NOT EXISTS weather_data(
                       latitude  FLOAT,
                       longitude FLOAT,
                       temperature FLOAT,
                       windspeed FLOAT,
                       winddirection FLOAT,
                       weathercode INT,
                       timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       
                       
                       );
              



           """)
        

       ##insert transform weather data into the table
        cursor.execute("""
          INSERT INTO weather_data(latitude,longitude,temperature,windspeed, winddirection,weathercode)
                       VALUES(%s,%s,%s,%s,%s,%s)
       """,(
           
           transform_weather_data['latitude'],
           transform_weather_data['longitude'],
           transform_weather_data['temperature'],
           transform_weather_data['windspeed'],
           transform_weather_data['winddirection'],
           transform_weather_data['weathercode'],
           

       ))
        
        conn.commit()
        cursor.close()

   ##DAG WORKFlOW-ETL PIPELINE
    weather_data=extract_weather_data()
    transform_weather_data=transform_data(weather_data)
    load_weather_data(transform_weather_data)