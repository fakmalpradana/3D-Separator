import os
import argparse

from utils.main_func import GMLSeparator, MergeOBJ, toCityJSON, upgradeCityJSON2, verticeClean, cleanTemp

PARSER = argparse.ArgumentParser(description='Convert a CityGML to OBJ.')
PARSER.add_argument('-bo', '--building_filepath',
                    help='Path to CityGML file(s).', required=False)
PARSER.add_argument('-gml', '--gml_filepath',
                    help='Path to GML file(s).', required=False)
PARSER.add_argument('-o', '--output_dir',
                    help='Directory for store all output', required=False)
PARSER.add_argument('-e', '--epsg',
                    help='EPSG code numeric only, ex: "32749"', required=False)

ARGS = vars(PARSER.parse_args())

dirpath = os.getcwd()

# Pre-defined Input/Output Zone
input_BO = os.path.join(dirpath, ARGS['building_filepath'])
input_GML = os.path.join(dirpath, ARGS['gml_filepath'])
output_dir = os.path.join(dirpath, ARGS['output_dir'])
epsg = ARGS['epsg']

os.makedirs(output_dir, exist_ok=True)

if __name__ == '__main__':
    # Separate GML into OBJ
    os.makedirs(f'{output_dir}OBJ', exist_ok=True)
    GMLSeparator(input_GML, f'{output_dir}OBJ')

    # Merge each OBJ with BO
    os.makedirs(f'{output_dir}merged_OBJ', exist_ok=True)
    MergeOBJ(f'{output_dir}OBJ', input_BO, f'{output_dir}merged_OBJ')

    # Convert to CityJSON
    os.makedirs(f'{output_dir}cityjson', exist_ok=True)
    toCityJSON(f'{output_dir}merged_OBJ', f'{output_dir}cityjson', input_BO, epsg)

    # Upgrade to CityJSON v2 and clean duplicate vertices
    upgradeCityJSON2(f'{output_dir}cityjson/buildings_cityjson.json')
    verticeClean(f'{output_dir}cityjson/buildings_cityjson_v2.json')

    # Delete temporary file (OBJ)
    cleanTemp()