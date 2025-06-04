import networkx as nx
import numpy as np
import geopandas as gpd
import pandas as pd
import os
from os.path import join

'''
Helper functions for selecting/creating a power system
model based on a subset of the CATS data
'''

# Path to the datasets directories
PATH = join(os.getcwd(), '..', 'data')

def subset(area, lines, buses):
    '''
    Given an GIS area, returns a subset of nodes within
    the GIS area as well as all nodes that should be
    treated as import nodes.
    '''
    # Set of all lines and buses that fall within a GIS service area
    sub_lines = gpd.sjoin(lines, area).drop(columns='index_right')
    sub_buses = gpd.sjoin(buses, area).drop(columns='index_right')
    
    # Graph form of lines
    graph = nx.from_pandas_edgelist(sub_lines, source='f_bus', target='t_bus')
    # List of all connected areas in SDG&E
    areas = np.array(list(nx.connected_components(graph)))
    idx_sorted = np.argsort([len(s) for s in areas])[::-1]
    
    # Buses sets
    N = areas[idx_sorted][0] # Largest fully connected area 
    N_import = N - set(sub_buses['bus']) # Set of import buses
    
    print("Created a system with", len(N), "buses. Removed", 
          sum([len(s) for s in areas[idx_sorted][1:]]), "isolated buses.")

    return (N, N_import)


def subset_lines(lines, N):
    '''
    Returns the set of lines with nodes in N
    '''
    line_cols = ['id', 'f_bus', 't_bus', 'r', 'x', 'b', 'rate_a', 'kv', 'geometry']
    # Select all lines with both buses in N
    line_mask = lines['f_bus'].isin(N) & lines['t_bus'].isin(N)
    sub_lines = lines.loc[line_mask, line_cols]
    
    # Add lines in the reverse direction
    cpy = sub_lines.copy()
    cpy['f_bus'], cpy['t_bus'] = cpy['t_bus'], cpy['f_bus']
    sub_lines = pd.concat((sub_lines, cpy)).reset_index(drop=True)

    return sub_lines

def subset_gens(gens, N, N_import):
    '''
    Returns the set of generators in N
    '''
    gen_cols = ['id', 'bus', 'startup', 'shutdown', 'n', 'c2', 'c1', 'c0',  
        'fueltype', 'pg', 'pmax', 'pmin', 'qg', 'qmax', 'qmin']
    # Select all generators strictly in N, excluding import generators
    sub_gens = gens[gens['bus'].isin(N)][gen_cols]
    
    # Add "import generators" with CATS parameters to any nodes with a 
    # transmission line exiting the test system area (same parameters for all)
    import_gens = gens[gens['fueltype'] == 'IMPORT'].head(len(N_import))[gen_cols].copy()
    import_gens['bus'] = list(N_import)
    sub_gens = pd.concat((sub_gens, import_gens))

    return sub_gens


def subset_loads(loads, timeslice, name):
    '''
    Select a load for a representative time period
    '''
    # Representative load for a sampled time period
    p_load = loads.loc[:, timeslice]
    
    # Scale outlier loads to be roughly less than 100MW
    load_t0 = loads.iloc[:, 0]
    alpha = np.where(load_t0 > 30, 30/load_t0, 1)
    p_load = (p_load.T*alpha).T

    # Save time period load as a CSV
    p_load.to_csv(join(PATH, "test_system", name))


def subset_system(area, lines, buses, gens, loads):
    # Get all buses in the service area
    N, N_import = subset(area, lines, buses)

    # Select sach of the datasets
    sub_lines = subset_lines(lines, N)
    sub_gens = subset_gens(gens, N, N_import)
    sub_buses = buses[buses['bus'].isin(N)]
    
    # Map from old bus index to new bus index
    bus_map = dict(zip(sub_buses.index, range(1, len(sub_buses)+1)))
    
    # Reindex all buses (to make model indexing consistent)
    sub_buses.loc[:, 'bus'] = sub_buses['bus'].replace(bus_map)
    sub_lines.loc[:, ['f_bus', 't_bus']] = sub_lines[['f_bus', 't_bus']].replace(bus_map)
    sub_gens.loc[:, 'bus'] = sub_gens['bus'].replace(bus_map)
    
    
    # Select loads (and convert to MW)
    sub_loads = loads[loads.index.isin(N)] / 1000
    # Set all import loads to zero
    sub_loads.loc[list(N_import), :] *= 0
    # Reindex buses 
    sub_loads = sub_loads.reset_index().replace({'bus':bus_map}).set_index('bus')

    # Select 24 hours of load from a representative week in each season
    # Representative weeks are determined using k-means clustering on all load profiles
    P = [slice("2018-04-02T01:00:00", "2018-04-03T01:00:00"),
         slice("2018-08-11T01:00:00", "2018-08-12T01:00:00"), 
         slice("2018-10-22T01:00:00", "2018-10-23T01:00:00"),
         slice("2018-12-07T01:00:00", "2018-12-08T01:00:00")]
    
    for timeslice, name in zip(P, ['sp','su','fa','wi']):
        subset_loads(sub_loads, timeslice, f"loads_24h_{name}.csv")

    # Write all datasets to test system folder
    sub_buses[sub_buses.columns[:-1]].to_csv(join(PATH, "test_system", "buses.csv"), index=False)
    sub_lines[sub_lines.columns[:-1]].to_csv(join(PATH, "test_system", "lines.csv"), index=False)
    sub_gens.to_csv(join(PATH, "test_system", "gens.csv"), index=False)

    return (sub_lines, sub_buses, sub_gens)