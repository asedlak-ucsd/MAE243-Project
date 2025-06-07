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
PATH = join(os.getcwd(), 'data')
INPUTS = join(os.getcwd(), '..', 'inputs')

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
    # Base units of the system
    baseMVA = 100
    
    line_cols = ['f_bus', 't_bus', 'r', 'x', 'b', 'rate_a', 'geometry']
    # Select all lines with both buses in N
    line_mask = lines['f_bus'].isin(N) & lines['t_bus'].isin(N)
    sub_lines = lines.loc[line_mask, line_cols]
    
    # Add lines in the reverse direction
    cpy = sub_lines.copy()
    cpy['f_bus'], cpy['t_bus'] = cpy['t_bus'], cpy['f_bus']
    sub_lines = pd.concat((sub_lines, cpy)).reset_index(drop=True)

    # Add line susceptance B = baseMVA * X / (R² + X²)
    sub_lines['sus'] = baseMVA * sub_lines['x'] / (sub_lines['r']**2 + sub_lines['x']**2)
    # Combine parallel lines
    sub_lines = (sub_lines
                 .groupby(['f_bus', 't_bus'])
                 .agg({'rate_a':'sum', 'sus':'sum', 'geometry':'first'})
                 .reset_index())
    # Convert nominal rating to MVA
    sub_lines['rate_a'] = baseMVA * sub_lines['rate_a']

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

    # Remove any generators (e.g., synchronous condensers) with 
    # zero active power output
    sub_gens = sub_gens[sub_gens['pmax'] > 0]
    # Group all generators of same type and cost at each node into a single generator
    sub_gens = (sub_gens
                .groupby(['bus', 'fueltype', 'c2', 'c1', 'c0'])
                .sum()
                .reset_index())

    # Add an indicator for whether generator is an energy storage system (ESS) 
    storage_gens = ["Hydroelectric Pumped Storage", "Batteries"]
    sub_gens["ess"] = sub_gens['fueltype'].isin(storage_gens)
    sub_gens['canidate'] = sub_gens['fueltype'].isin(['Batteries', 'Solar Photovoltaic']).astype(int)
    # Set import max to 200MW
    sub_gens.loc[sub_gens['fueltype'] == 'IMPORT', 'pmax'] = 200
    
    return sub_gens[['bus', 'fueltype', 'c2','c1','c0', 'pmax', 'ess', 'canidate']]


def subset_cf(df, fueltype, N, N_import, bus_map):
    '''
    Return the subset of capacity factors in N
    '''
    sub_df = (df
                [df.index.isin(N)]
                .reset_index()
                .replace({'bus':bus_map})
                .set_index('bus')).copy()
    
    sub_df['fueltype'] = fueltype

    return sub_df


def add_canidate_gens(sub_solar_cf_demand, sub_gens):
    """
    Returns a dataframe with canidate solar and ESS added
    to the generators dataframe.
    """
    # Set of nodes that can get canidate solar and/or ESS 
    G_new = list(sub_solar_cf_demand.index)
    # Create 2 dataframes for solar and ESS with no existing capacity
    # Assume default O&M costs
    G_new_solar = pd.DataFrame({'bus':G_new})
    G_new_solar['fueltype'] = 'Solar Photovoltaic'
    G_new_solar[['c2', 'c1', 'c0', 'pmax', 'ess']] = 0
    G_new_solar['canidate'] = 1
    
    G_new_batteries = pd.DataFrame({'bus':G_new})
    G_new_batteries['fueltype'] = 'Batteries'
    G_new_batteries[['c2', 'c1', 'c0', 'pmax', 'ess']] = 0.06757, 16.371712, 401.19412, 0, 1
    G_new_batteries['canidate'] = 1
    
    # Add to existing gens
    sub_gens = pd.concat((sub_gens, G_new_solar, G_new_batteries))
    sub_gens['gen_id'] = sub_gens.reset_index().index +1

    return sub_gens

def subset_system(area, lines, buses, gens, loads, 
                  solar_cf_gens, solar_cf_demand, wind_cf_gens):
    # Get all buses in the service area
    N, N_import = subset(area, lines, buses)
    
    # Select sach of the datasets
    sub_lines = subset_lines(lines, N)
    sub_gens = subset_gens(gens, N, N_import)
    sub_buses = buses[buses['bus'].isin(N)]
    
    # Set of solar and wind generators in service area
    G_solar = set(sub_gens[sub_gens['fueltype'] == "Solar Photovoltaic"].bus)
    G_wind = set(sub_gens[sub_gens['fueltype'] == "Onshore Wind Turbine"].bus)
    
    # Map from old bus index to new bus index
    bus_map = dict(zip(sub_buses.index, range(1, len(sub_buses)+1)))
    
    # Reindex all buses (to make model indexing consistent)
    sub_buses.loc[:, 'bus'] = sub_buses['bus'].replace(bus_map)
    sub_lines.loc[:, ['f_bus', 't_bus']] = sub_lines[['f_bus', 't_bus']].replace(bus_map)
    sub_gens.loc[:, 'bus'] = sub_gens['bus'].replace(bus_map)
    
    # Select loads
    sub_loads = loads[loads.index.isin(N)].copy()
    # Set all import loads to zero
    sub_loads.loc[list(N_import), :] *= 0
    # Reindex buses 
    sub_loads = sub_loads.reset_index().replace({'bus':bus_map}).set_index('bus')
    
    # Select all solar and wind CFs within the selected area 
    sub_solar_cf = subset_cf(solar_cf_gens, "Solar Photovoltaic", N, N_import, bus_map)
    sub_solar_cf_demand = subset_cf(solar_cf_demand, "Solar Photovoltaic", N, N_import, bus_map)
    sub_wind_cf = subset_cf(wind_cf_gens, "Onshore Wind Turbine", N, N_import, bus_map).drop_duplicates()
    sub_cf = pd.concat((sub_solar_cf, sub_solar_cf_demand, sub_wind_cf))

    # Add canidate gens to the gens dataframe
    sub_gens = add_canidate_gens(sub_solar_cf_demand, sub_gens)
    
    # Create a variability dataframe with one row for every generator
    # If there is no match then the gen is not variable and should 
    # have a cpacity factor of one for all time (i.e. fill NA with 1).
    sub_cf = pd.merge(sub_cf.reset_index(),
                           sub_gens[['fueltype', 'bus', 'gen_id']],
                           on=['bus', 'fueltype'], 
                           how='right').fillna(1)
    # Re-organize columns
    sub_cf = sub_cf.drop(columns=['fueltype', 'bus'])
    sub_cf = sub_cf[['gen_id']+list(sub_cf.columns)[1:-1]]

    # Write all datasets to test system folder
    inputs_dir = join(os.getcwd(), '..', 'inputs')
    sub_buses[sub_buses.columns[:-1]].to_csv(join(INPUTS, "buses.csv"), index=False)
    sub_lines[sub_lines.columns[:-1]].to_csv(join(INPUTS, "lines.csv"), index=False)
    sub_gens.to_csv(join(INPUTS, "generators.csv"), index=False)
    sub_cf.to_csv(join(INPUTS, "variability.csv"), index=False)
    sub_loads.to_csv(join(INPUTS, "loads.csv"), index=True)

    return (sub_lines, sub_buses, sub_gens, sub_cf)