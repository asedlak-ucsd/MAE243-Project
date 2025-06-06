import pandas as pd
import geopandas as gpd
import os
from os.path import join
import scipy.io 

'''
Basic utility functions for reading pandas DataFrames
'''

# Path to the datasets directories
PATH = join(os.getcwd(), 'data')

def read_csv(filename, subdir='cats', standard=True, **kargs):
    '''
    Returns standardized dataframe
    '''
    df = pd.read_csv(join(PATH, subdir, filename), **kargs)
    # Should the dataframe be standardized?
    if standard:
        df = standardize(df)
    return df

def read_geocsv(filename):
    '''
    Read a dataset with Lat and Lon columns and 
    return a geopandas DataFrame with point geometries
    '''
    df = read_csv(filename)
    gdf = gpd.GeoDataFrame(df,
           geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")
    return gdf

def read_mat(filename, columns=None, subdir='cats'):
    '''
    Read a MATLAB .mat file of a matrix 
    and return dataframe where each columns is labeled
    '''
    # If no columns provided assume reading gencosts.m 
    if columns == None:
        columns = ['model', 'startup', 'shutdown', 'n', 'c2', 'c1', 'c0']
    
    # Assume object has the same name as the file
    object_name = filename.split(".")[0]
    
    # Read data and place in dataframe
    path = join(PATH, subdir, filename)
    data = scipy.io.loadmat(path)[object_name]
    df = pd.DataFrame(data=data, columns=columns)
    df = standardize(df)
    return df

def standardize(df):
    '''
    Standardize dataframes to 1 indexed and 
    lowercase columns.
    '''
    # Adjust index to start at 1 not 0
    df.index += 1
    # Make all columns lowercase
    df.columns = [s.lower() for s in df.columns]
    return df

def add_id(df):
    '''
    Add an id column to the dataframe from the index
    '''
    df['id'] = df.index
    return df

def read_loads(filename):
    # Column names
    names = pd.date_range(start='2018-01-01 01:00:00-05:00',
             end='2019-01-01 00:00:00-05:00', freq='h').astype(str)
    # Read CATS dataframe for loads
    path = join(PATH, 'cats', filename)
    loads = pd.read_csv(path, header=None, names=names)
    loads.index.name = 'bus'
    loads.index += 1
    real = lambda x: float(x.split('+')[0])
    loads = loads.apply(lambda col: col.apply(real))
    return loads
        