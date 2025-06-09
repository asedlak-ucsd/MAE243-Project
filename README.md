# Overview
This repository contains code to run a preliminary test model of capacity expansion at the substation-level in San Diego. A Julia model `Initial-Model-Formulation.ipynb` can be found in `src` along with a data preprocessing notebook `Test-System-Data-Processing.ipynb`. 

# Code
- `Initial-Model-Formulation.ipynb`: Used to run initial model with DCOPF and a basic budget variable. This model was developed with Julia version 1.8 and utilizes an academic license for Gurobi. Compatibility with other Julia version and optimizers is not guaranteed but should work. 
- `Test-System-Data-Processing.ipynb`: Used to prepare input file to `Initial-Model-Formulation.ipynb`. All test system files are included in this repository under `../data/test_system` but you can also create them yourself by downloading the full CATS model data described in the following section. Unfortunately the full CATS data are too large to include in a GitHub upload.

# Data
This model leverages data from several sources. To run the prepossessing script please take the following steps. CATS, `lines.json`, `buses.csv`, and `gens.csv` should be downloaded directly from the [CATS model repository](https://github.com/WISPO-POP/CATS-CaliforniaTestSystem/tree/master) and placed in a folder named `cats` within the data directory. Data for power flow, specifically generator costs can be found in `CaliforniaTestSystem.m`. To extract this data run the file in MATLAB and save the `gencost` and `bus` matrices to a folder named `opf` within the data directory. An IOU shapefile is needed to extract generators in the SDGE area, it can be downloaded from the [CEC website](https://cecgis-caenergy.opendata.arcgis.com/datasets/CAEnergy::electric-load-serving-entities-iou-pou/about). To download, loads and capacity factors please contact the REAM Lab.  These files are currently being developed for related research but are not **yet** publicly available. 


link for cpuc data https://www.cpuc.ca.gov/industries-and-topics/wildfires/fire-threat-maps-and-fire-safety-rulemaking 