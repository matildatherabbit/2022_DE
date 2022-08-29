from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.hooks.postgres_hook import PostgresHook

from datetime import datetime
from datetime import timedelta
# from plugins import slack

import requests
import logging
import psycopg2
import json


def get_Redshift_connection(autocommit=False):
    hook = PostgresHook(postgres_conn_id='redshift_dev_db')
    conn = hook.get_conn()
    conn.autocommit = autocommit
    return conn.cursor()


def extract(**context):
    link = context["params"]["api"]
    task_instance = context['task_instance']
    execution_date = context['execution_date']

    logging.info(execution_date)
    f = requests.get(link)
    f_js = f.json()
    return (f_js)


def transform(**context):
    content = context["task_instance"].xcom_pull(key="return_value", task_ids="extract")
    weather_info = content.loads(f_js)
    return weather_info
    logging.info(weather_info)


def load(**context):
    schema = context["params"]["schema"]
    table = context["params"]["table"]

    cur = get_Redshift_connection()
    weather_info = context["task_instance"].xcom_pull(key="return_value", task_ids="transform")
    main_table = '''CREATE TABLE helennearing.weather_forecast (
                date date primary key,
                temp float,
                min_temp float,
                max_temp float,
                created_date timestamp default GETDATE())'''
    for date, temp, min_temp, max_temp in weather_info['daily']:
        print(date['dt'], temp['day'], min_temp['min'], max_temp['max'])
        sql += f"""INSERT INTO {schema}.{table} VALUES  ('{date}, '{temp}', '{min}', '{max}');"""
    sql += "END;"
    logging.info(sql)
    cur.execute(main_table)
#     temp_table = 

# def reload(**context):
#     sql = "BEGIN; DELETE FROM {schema}.{table};".format(schema=schema, table=table)
    
#     logging.info(sql)
#     cur.execute(sql)

dag_weather_assignment = DAG(
    dag_id = 'dag_weather_assignment',
    start_date = datetime(2022,8,27), # 날짜가 미래인 경우 실행이 안됨
    schedule_interval = '0 2 * * *',  # 적당히 조절
    max_active_runs = 1,
    catchup = False,
    default_args = {
        'retries': 1,
        'retry_delay': timedelta(minutes=3),
        # 'on_failure_callback': slack.on_failure_callback,
    }
)


extract = PythonOperator(
    task_id = 'extract',
    python_callable = extract,
    params = {
        'api':  Variable.get("open_weather_api_key")
    },
    provide_context=True,
    dag = dag_weather_assignment)

transform = PythonOperator(
    task_id = 'transform',
    python_callable = transform,
    params = { 
    },  
    provide_context=True,
    dag = dag_weather_assignment)

load = PythonOperator(
    task_id = 'load',
    python_callable = load,
    params = {
        'schema': 'helennearing',   ## 자신의 스키마로 변경
        'table': 'weather_forecast'
    },
    provide_context=True,
    dag = dag_weather_assignment)

extract >> transform >> load

