import os
import subprocess

# Pre-defined Input/Output Zone
input_BO = 'sample/BO/Selected_B2.shp'
input_GML = 'sample/gml/LOD2_sby.gml'
output_dir = 'out/sample_sby/'
os.makedirs(output_dir, exist_ok=True)