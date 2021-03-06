import json
import os
import shutil
import sys
from datetime import datetime

import pandas as pd
from airflow import DAG
from airflow.operators.python_operator import PythonOperator


def filter_data(**kwargs):
    # read data
    path_vids = kwargs['dag_run'].conf['path_vids']
    date = str(kwargs['dag_run'].conf['date'])

    print(os.getcwd())
    print(path_vids)

    df_vids = pd.read_csv(path_vids, compression='zip') \
        .query('trending_date==@date')
    # cache
    try:
        df_vids.to_csv('./tmp/data_vids.csv', index=False)
    except FileNotFoundError:
        os.mkdir('./tmp')
        df_vids.to_csv('./tmp/data_vids.csv', index=False)


def preprocess_data(**kwargs):
    # read data
    path_cats = kwargs['dag_run'].conf['path_cats']
    data_cats = json.load(open(path_cats, 'r'))
    # convert json to dataframe
    df_cat = pd.DataFrame(data_cats)
    df_cat['category'] = df_cat['items'].apply(lambda x: x['snippet']['title'])
    df_cat['id'] = df_cat['items'].apply(lambda x: int(x['id']))
    df_cat_drop = df_cat.drop(columns=['kind', 'etag', 'items'])
    # cache
    try:
        df_cat_drop.to_csv('./tmp/data_cats.csv', index=False)
    except FileNotFoundError:
        os.mkdir('./tmp')
        df_cat_drop.to_csv('./tmp/data_cats.csv', index=False)


def join_data(**kwargs):
    try:
        df_vids = pd.read_csv('./tmp/data_vids.csv')
        df_cats = pd.read_csv('./tmp/data_cats.csv')
    except Exception as e:
        print('>>>>>>>>>>>> Error: {}'.format(e))
        sys.exit(1)
    # join data
    df_join = df_vids.merge(df_cats, left_on='category_id', right_on='id')
    # cache joined data
    df_join.to_csv('./tmp/data_joined.csv', index=False)


def calc_ratio(**kwargs):
    try:
        df_join = pd.read_csv('./tmp/data_joined.csv')
    except Exception as e:
        print('>>>>>>>>>>>> Error: {}'.format(e))
        sys.exit(1)
    # aggregate likes and dislikes by category
    df_agg = df_join[['category', 'likes', 'dislikes']].groupby('category').sum()
    # calculate ratio
    df_agg['ratio_likes_dislikes'] = df_agg['likes'] / df_agg['dislikes']
    df_agg.reset_index('category').to_csv('./tmp/data_ratio.csv', index=False)


def sort_data(**kwargs):
    try:
        df_ratio = pd.read_csv('./tmp/data_ratio.csv')
    except Exception as e:
        print('>>>>>>>>>>>> Error: {}'.format(e))
        sys.exit(1)
    # sort data
    df_sorted = df_ratio.sort_values('ratio_likes_dislikes', ascending=False)
    # cache joined data
    df_sorted.to_csv('./tmp/data_sorted.csv', index=False)


def store_data(**kwargs):
    # read data from cache
    path_output = kwargs['dag_run'].conf['path_output']
    try:
        df_sorted = pd.read_csv('./tmp/data_sorted.csv')
    except Exception as e:
        print('>>>>>>>>>>>> Error: {}'.format(e))
        sys.exit(1)
    # cache joined data
    df_sorted.to_csv(path_output, index=False)
    # clean up tmr
    shutil.rmtree('./tmp')

# create DAG
args = {
    'owner': 'Airflow',
    'description': 'Calculate Ratio of Likes-Dislikes',
    'start_date': datetime(2017, 11, 14),
    'catchup': False,
    'provide_context': True
}

dag = DAG(
    dag_id='ratio_dag',
    default_args=args,
    schedule_interval=None,
)

op1 = PythonOperator(
    task_id='filter_data',
    python_callable=filter_data,
    dag=dag)

op2 = PythonOperator(
    task_id='preprocess_data',
    python_callable=preprocess_data,
    dag=dag)

op3 = PythonOperator(
    task_id='join_data',
    python_callable=join_data,
    dag=dag)

op4 = PythonOperator(
    task_id='calc_ratio',
    python_callable=calc_ratio,
    dag=dag)

op5 = PythonOperator(
    task_id='sort_data',
    python_callable=sort_data,
    dag=dag)

op6 = PythonOperator(
    task_id='store_data',
    python_callable=store_data,
    dag=dag)

[op1, op2] >> op3 >> op4 >> op5 >> op6

cd ../Data/
