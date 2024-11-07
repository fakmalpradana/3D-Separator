import subprocess
import geopandas as gpd
import trimesh
import os
import json
import uuid

from shapely.geometry import Polygon
from shapely.ops import unary_union

def GMLSeparator(input:str, output:str):
    subprocess.call(
        [
            'python',
            'utils/CityGML2OBJs.py',
            '-i', input,
            '-o', output,
            '-sepC', '1'
        ]
    )

def MergeOBJ(input_obj:str, input_bo:str, output:str):
    # Load building outline shapefile
    building_outlines = gpd.read_file(input_bo)

    # Load each face from OBJ files, project to 2D, and store with filename
    faces = []
    for file in os.listdir(input_obj):
        if file.endswith(".obj"):
            mesh = trimesh.load(os.path.join(input_obj, file))
            # Project to 2D by taking only x and y values
            for face in mesh.faces:
                vertices = mesh.vertices[face][:, :2]  # ignore z-values for projection
                poly_2d = Polygon(vertices)
                faces.append((poly_2d, mesh))

    # Convert faces list to a GeoDataFrame
    face_gdf = gpd.GeoDataFrame(
        {"geometry": [f[0] for f in faces], "mesh": [f[1] for f in faces]},
        crs=building_outlines.crs
    )

    # Buffer slightly to ensure intersection accuracy, then join with building outlines
    buffered_faces = face_gdf.copy()
    buffered_faces['geometry'] = face_gdf['geometry'].buffer(0.001)  # adjust buffer as needed (meters)
    merged_buildings = []

    # Step-by-step process for each building outline
    for _, outline in building_outlines.iterrows():
        print(f"Processing Building ID: {outline['id']}")  # Check outline ID

        # Select faces intersecting or within the building outline
        contained_faces = buffered_faces[buffered_faces.intersects(outline.geometry)]
        
        # Log the number of faces found
        if contained_faces.empty:
            print("No faces found for this building outline.")
            continue
        else:
            print(f"Found {len(contained_faces)} faces for Building ID: {outline['id']}")
        
        # Extrude and merge faces for this building
        extruded_meshes = []
        for _, face_row in contained_faces.iterrows():
            face_mesh = face_row['mesh']
            extruded_mesh = face_mesh.copy()
            extruded_mesh.vertices[:, 2] += 1000.0  # Set your custom extrusion height here
            extruded_meshes.append(extruded_mesh)
        
        # If faces are selected, merge them!!
        if extruded_meshes:
            # Merge all extruded faces for this building into a single mesh
            merged_mesh = trimesh.util.concatenate(extruded_meshes)
            merged_buildings.append(merged_mesh)

            # Save the merged building as single OBJ
            output_filename = f"{output}/merged_building_{outline['id']}.obj"
            merged_mesh.export(output_filename)
            print(f"Merged building saved as: {output_filename}")
        else:
            print(f"No extruded meshes for Building ID: {outline['id']}")

    print("Process complete. Check the output directory for merged OBJ files.")

def parse_obj(file_path):
    """Parse OBJ file and extract vertices and faces."""
    vertices = []
    faces = []
    
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == 'v':
                # Vertex line
                vertices.append([float(coord) for coord in parts[1:]])
            elif parts[0] == 'f':
                # Face line
                face_indices = [int(index.split('/')[0]) - 1 for index in parts[1:]]
                faces.append(face_indices)
    
    return vertices, faces

def get_geographical_extent(shapefile_path):
    """Get XY extent from a shapefile and set Z bounds."""
    gdf = gpd.read_file(shapefile_path)
    xmin, ymin, xmax, ymax = gdf.total_bounds
    zmin, zmax = 0, 2000  # Set Z bounds as instructed
    return [xmin, ymin, zmin, xmax, ymax, zmax]

def create_cityjson_structure(geographical_extent):
    """Create the base CityJSON structure with specified extent."""
    return {
        "type": "CityJSON",
        "version": "1.0",
        "metadata": {
            "referenceSystem": "urn:ogc:def:crs:EPSG::32749",
            "geographicalExtent": geographical_extent
        },
        "CityObjects": {},
        "vertices": [],
        "appearance": {
            "materials": [
                {
                    "name": "roofandground",
                    "ambientIntensity": 0.2,
                    "diffuseColor": [0.9, 0.1, 0.75],
                    "transparency": 0.0,
                    "isSmooth": False
                },
                {
                    "name": "wall",
                    "ambientIntensity": 0.4,
                    "diffuseColor": [0.1, 0.1, 0.9],
                    "transparency": 0.0,
                    "isSmooth": False
                }
            ]
        }
    }

def add_building_to_cityjson(cityjson, building_id, vertices, faces, building_index):
    """Add building geometry, semantics, and materials to CityJSON structure."""
    vertex_offset = len(cityjson["vertices"])
    cityjson["vertices"].extend(vertices)  # Append vertices to the global list
    
    # Format faces and add to geometry
    solid_geometry = [[[[vertex_offset + idx for idx in face]] for face in faces]]
    
    # Prepare semantics and materials arrays with the correct number of elements
    num_faces = len(faces)
    semantics_values = [[0] * 1 + [1] * 1 + [2] * (num_faces - 2)]
    material_values = [[0] * 1 + [0] * 1 + [1] * (num_faces - 2)]
    
    semantics = {
        "values": semantics_values,
        "surfaces": [
            {"type": "RoofSurface"},
            {"type": "GroundSurface"},
            {"type": "WallSurface"}
        ]
    }
    
    material = {"": {"values": material_values}}
    
    # Define building object
    cityjson["CityObjects"][building_id] = {
        "type": "Building",
        "attributes": {
            "level_0": building_index,
            "level_1": 0,
            "Id": building_index + 1,
            "uuid_bgn": building_id
        },
        "geometry": [{
            "type": "Solid",
            "lod": 1,
            "boundaries": solid_geometry,
            "semantics": semantics,
            "material": material
        }]
    }

def save_cityjson(cityjson, output_path):
    """Save CityJSON data to a JSON file."""
    with open(output_path, 'w') as f:
        json.dump(cityjson, f, indent=2)

def toCityJSON(input_folder, output_folder, shapefile_path):
    """Main function to convert OBJ files to CityJSON format with extent from shapefile."""
    geographical_extent = get_geographical_extent(shapefile_path)
    cityjson = create_cityjson_structure(geographical_extent)
    
    os.makedirs(output_folder, exist_ok=True)
    
    for index, obj_file in enumerate(os.listdir(input_folder)):
        if obj_file.endswith('.obj'):
            obj_path = os.path.join(input_folder, obj_file)
            vertices, faces = parse_obj(obj_path)
            building_id = str(uuid.uuid4())
            add_building_to_cityjson(cityjson, building_id, vertices, faces, index)
            print(f"Processed {obj_file} with ID {building_id}")
    
    output_path = os.path.join(output_folder, 'buildings_cityjson.json')
    save_cityjson(cityjson, output_path)
    print(f"CityJSON saved to {output_path}")