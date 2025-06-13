# Overview
This repository contains code to run a model of capacity expansion at the substation-level in California. The main model can be run from `run_model.ipynb` while code for the main model can be found in `capex_model`. The `models` directory contains potential models that the capacity expansion model can be run with. As of now the San Diego model is the only model for which there is data.

## San Diego Model
### Code
- `preprocessing`: This directory contains all code needed to create the input files for capacity expansion. To do so run all cells in `run_preprocessing.ipynb`. This will create and populate an `inputs` folder in the model directory.
- `postprocessing`: This directory contains all code needed to visualize and process model outputs.
- `inputs`: All datafiles needed for the San Diego model.
### Data
This model leverages data from several sources. To run the prepossessing script please take the following steps. CATS, `lines.json`, `buses.csv`, `loads.csv`, and `gens.csv` should be downloaded directly from the [CATS model repository](https://github.com/WISPO-POP/CATS-CaliforniaTestSystem/tree/master) and placed in a folder named `cats` within the data directory. Data for power flow, specifically generator costs can be found in `CaliforniaTestSystem.m`. To extract this data run the file in MATLAB and save the `gencost` and `bus` matrices to a folder named `opf` within the data directory. To download capacity factors please contact the REAM Lab.  These files are currently being developed for related research but are not **yet** publicly available. An IOU shapefile is needed to extract generators in the SDGE area, it can be downloaded from the [CEC website](https://cecgis-caenergy.opendata.arcgis.com/datasets/CAEnergy::electric-load-serving-entities-iou-pou/about). A shapefile for CPUC wildfire risk tier zones can be found on the [CPUC website](https://www.cpuc.ca.gov/industries-and-topics/wildfires/fire-threat-maps-and-fire-safety-rulemaking).
